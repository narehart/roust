"""Mac-native, pinned-weight AST-unit embedding experiment (lab only)."""
from bisect import bisect_right
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sqlite3
import time

from huggingface_hub import snapshot_download
import mlx.core as mx
from mlx_lm.models.qwen3 import ModelArgs, Qwen3Model
import numpy as np
from transformers import AutoTokenizer

from e56_dense import MODEL, REVISION, INSTRUCTION
from e58_units import source_units


class NativeRetriever:
    def __init__(self, cache):
        path = Path(snapshot_download(MODEL, revision=REVISION,
                    allow_patterns=["*.json", "*.safetensors", "merges.txt", "vocab.json"]))
        self.tokenizer = AutoTokenizer.from_pretrained(path, padding_side="left")
        self.model = Qwen3Model(ModelArgs.from_dict(json.loads((path / "config.json").read_text())))
        weights = mx.load(str(path / "model.safetensors"))
        self.model.load_weights([(k, v.astype(mx.float16)) for k, v in weights.items()], strict=True)
        self.model.eval()
        mx.eval(self.model.parameters())
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(cache)
        self.db.execute("CREATE TABLE IF NOT EXISTS embeddings (key TEXT PRIMARY KEY, vector BLOB NOT NULL)")
        self.namespace = json.dumps([MODEL, REVISION, "mlx-fp16-f32-last-token",
            importlib.metadata.version("mlx"), importlib.metadata.version("mlx-lm"),
            "batch32-max512-causal-leftpad-v1"])

    def forward(self, ids, valid):
        ids, valid = mx.array(ids), mx.array(valid)
        pos = mx.arange(ids.shape[1])
        mask = (pos[:, None] >= pos[None, :])[None, None, :, :] & (valid[:, None, None, :] > 0)
        h = self.model.embed_tokens(ids)
        for layer in self.model.layers:
            h = layer(h, mask, None)
        vectors = self.model.norm(h)[:, -1].astype(mx.float32)
        vectors = vectors / mx.linalg.norm(vectors, axis=1, keepdims=True)
        mx.eval(vectors)
        return np.array(vectors)

    def encode(self, texts):
        started = time.monotonic()
        result, missing = [None] * len(texts), {}
        for i, text in enumerate(texts):
            key = hashlib.sha256((self.namespace + text).encode()).hexdigest()
            row = self.db.execute("SELECT vector FROM embeddings WHERE key=?", (key,)).fetchone()
            if row:
                result[i] = np.frombuffer(row[0], dtype=np.float32).copy()
            else:
                missing.setdefault(key, []).append(i)
        keys = sorted(missing, key=lambda k: len(texts[missing[k][0]]))
        padded_tokens = 0
        for start in range(0, len(keys), 32):
            batch = keys[start:start + 32]
            tokens = self.tokenizer([texts[missing[k][0]] for k in batch], padding=True,
                truncation=True, max_length=512, return_tensors="np")
            padded_tokens += tokens["input_ids"].size
            vectors = self.forward(tokens["input_ids"], tokens["attention_mask"])
            assert np.isfinite(vectors).all(), "non-finite native embeddings"
            for key, vector in zip(batch, vectors):
                self.db.execute("INSERT OR REPLACE INTO embeddings VALUES (?,?)", (key, vector.tobytes()))
                for i in missing[key]:
                    result[i] = vector
            self.db.commit()
            if start % 512 == 0:
                print(f"native embedding {min(start + 32, len(keys))}/{len(keys)} new units", flush=True)
        return np.stack(result), {"n_texts": len(texts), "new_unique": len(keys),
            "new_padded_tokens": padded_tokens, "seconds": time.monotonic() - started,
            "backend": "mlx-lm", "namespace": self.namespace}

    def candidates(self, query, corpus):
        docs, locations = [], []
        for path, source in sorted(corpus.items()):
            for first, _, text in source_units(path, source):
                encoded = self.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
                ids, offsets = encoded["input_ids"], encoded["offset_mapping"]
                starts, cursor = [], 0
                for line in text.splitlines(keepends=True):
                    starts.append(cursor)
                    cursor += len(line)
                for start in range(0, len(ids), 320):
                    stop = min(start + 384, len(ids))
                    docs.append(path + "\n" + self.tokenizer.decode(ids[start:stop]))
                    a = first - 1 + bisect_right(starts, offsets[start][0])
                    b = first - 1 + bisect_right(starts, max(offsets[start][0], offsets[stop - 1][1] - 1))
                    locations.append((path, a, b))
        vectors, cost = self.encode(docs)
        q, qcost = self.encode([INSTRUCTION + query])
        scores = vectors @ q[0]
        order = sorted(range(len(docs)), key=lambda i: (-float(scores[i]), locations[i]))
        return [(float(scores[i]), *locations[i]) for i in order], {"documents": cost, "query": qcost}
