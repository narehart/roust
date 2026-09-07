"""Pinned native query/document cross-encoder; experimental, not a CLI default."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sqlite3

from huggingface_hub import snapshot_download
import mlx.core as mx
from mlx_lm.models.qwen3 import ModelArgs, Qwen3Model
import numpy as np
from transformers import AutoTokenizer

MODEL = "Qwen/Qwen3-Reranker-0.6B"
REVISION = "e61197ed45024b0ed8a2d74b80b4d909f1255473"
INSTRUCTION = "Given a software issue, retrieve source code relevant to fixing the issue."
PREFIX = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'


class Reranker:
    def __init__(self, cache):
        path = Path(snapshot_download(MODEL, revision=REVISION,
            allow_patterns=["*.json", "*.safetensors", "merges.txt", "vocab.json"]))
        self.tokenizer = AutoTokenizer.from_pretrained(path, padding_side="left")
        self.model = Qwen3Model(ModelArgs.from_dict(json.loads((path / "config.json").read_text())))
        weights = mx.load(str(path / "model.safetensors"))
        assert all(k.startswith("model.") for k in weights), "expected tied-head checkpoint"
        self.model.load_weights([(k.removeprefix("model."), v.astype(mx.float16)) for k, v in weights.items()], strict=True)
        self.model.eval()
        mx.eval(self.model.parameters())
        self.labels = [self.tokenizer.convert_tokens_to_ids(x) for x in ["no", "yes"]]
        self.head = self.model.embed_tokens.weight[mx.array(self.labels)]
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(cache)
        self.db.execute("CREATE TABLE IF NOT EXISTS scores (key TEXT PRIMARY KEY, score REAL NOT NULL)")
        self.namespace = json.dumps([MODEL, REVISION, "mlx-fp16-f32-logit-difference", PREFIX, SUFFIX,
            INSTRUCTION, "query768-document1024-total2048-batch8-v1",
            importlib.metadata.version("mlx"), importlib.metadata.version("mlx-lm"),
            importlib.metadata.version("transformers"), importlib.metadata.version("tokenizers")])

    def inputs(self, query, documents):
        encode = lambda s: self.tokenizer.encode(s, add_special_tokens=False)
        # Bound the two fields independently so a long issue cannot erase code.
        query = self.tokenizer.decode(encode(query)[:768])
        prefix, suffix = encode(PREFIX), encode(SUFFIX)
        rows = []
        for document in documents:
            document = self.tokenizer.decode(encode(document)[:1024])
            middle = encode(f"<Instruct>: {INSTRUCTION}\n<Query>: {query}\n<Document>: {document}")
            row = prefix + middle + suffix
            assert len(row) <= 2048
            rows.append(row)
        return self.tokenizer.pad({"input_ids": rows}, padding=True, return_tensors="np")

    def forward(self, inputs):
        ids, valid = mx.array(inputs["input_ids"]), mx.array(inputs["attention_mask"])
        positions = mx.arange(ids.shape[1])
        mask = (positions[:, None] >= positions[None, :])[None, None] & (valid[:, None, None, :] > 0)
        h = self.model.embed_tokens(ids)
        for layer in self.model.layers:
            h = layer(h, mask, None)
        h = self.model.norm(h)[:, -1]
        logits = (h @ self.head.T).astype(mx.float32)
        scores = logits[:, 1] - logits[:, 0]
        mx.eval(scores)
        return np.array(scores)

    def score(self, query, documents):
        result, missing = [None] * len(documents), {}
        for i, document in enumerate(documents):
            key = hashlib.sha256(json.dumps([self.namespace, query, document]).encode()).hexdigest()
            row = self.db.execute("SELECT score FROM scores WHERE key=?", (key,)).fetchone()
            if row is None:
                missing.setdefault(key, []).append(i)
            else:
                result[i] = row[0]
        keys = sorted(missing)
        for start in range(0, len(keys), 8):
            batch = keys[start:start + 8]
            scores = self.forward(self.inputs(query, [documents[missing[k][0]] for k in batch]))
            assert np.isfinite(scores).all()
            for key, score in zip(batch, scores):
                self.db.execute("INSERT INTO scores VALUES (?,?)", (key, float(score)))
                for i in missing[key]:
                    result[i] = float(score)
            self.db.commit()
        return result
