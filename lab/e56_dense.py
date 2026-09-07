"""Pinned, local Qwen file retrieval. No benchmark labels enter this module."""
import hashlib
import json
from pathlib import Path
import sqlite3
import time

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

MODEL = "Qwen/Qwen3-Embedding-0.6B"
REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
INSTRUCTION = "Instruct: Given a software issue, retrieve source code relevant to fixing the issue.\nQuery: "


class Retriever:
    def __init__(self, cache):
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION, padding_side="left")
        self.model = AutoModel.from_pretrained(MODEL, revision=REVISION,
            torch_dtype=torch.float16 if self.device == "mps" else torch.float32,
            attn_implementation="sdpa").to(self.device).eval()
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(cache)
        self.db.execute("CREATE TABLE IF NOT EXISTS embeddings (key TEXT PRIMARY KEY, vector BLOB NOT NULL)")
        self.namespace = json.dumps([MODEL, REVISION, self.device, str(self.model.dtype),
                                    torch.__version__, "last-token-leftpad-max512-v1"])

    def encode(self, texts):
        started = time.monotonic()
        result = [None] * len(texts)
        missing = {}
        for i, text in enumerate(texts):
            key = hashlib.sha256((self.namespace + text).encode()).hexdigest()
            row = self.db.execute("SELECT vector FROM embeddings WHERE key=?", (key,)).fetchone()
            if row:
                result[i] = np.frombuffer(row[0], dtype=np.float32).copy()
            else:
                missing.setdefault(key, []).append(i)
        keys = sorted(missing, key=lambda k: len(texts[missing[k][0]]))
        for start in range(0, len(keys), 8):
            batch = keys[start:start + 8]
            tokens = self.tokenizer([texts[missing[k][0]] for k in batch], padding=True,
                                    truncation=True, max_length=512, return_tensors="pt").to(self.device)
            with torch.inference_mode():
                vectors = self.model(**tokens).last_hidden_state[:, -1].float()
                vectors = torch.nn.functional.normalize(vectors, dim=1).cpu().numpy()
            assert np.isfinite(vectors).all(), "non-finite embeddings"
            for key, vector in zip(batch, vectors):
                self.db.execute("INSERT OR REPLACE INTO embeddings VALUES (?,?)", (key, vector.tobytes()))
                for i in missing[key]:
                    result[i] = vector
            self.db.commit()
            if start % 256 == 0:
                print(f"embedding {min(start + 8, len(keys))}/{len(keys)} new chunks", flush=True)
        return np.stack(result), {"n_texts": len(texts), "new_unique": len(keys),
                                  "seconds": time.monotonic() - started}

    def rank(self, query, corpus):
        docs, owners = [], []
        for path, source in sorted(corpus.items()):
            body = self.tokenizer.encode(source, add_special_tokens=False)
            for start in range(0, max(1, len(body)), 320):
                docs.append(path + "\n" + self.tokenizer.decode(body[start:start + 384]))
                owners.append(path)
        vectors, cost = self.encode(docs)
        q, qcost = self.encode([INSTRUCTION + query])
        similarities = vectors @ q[0]
        scores = {}
        for owner, score in zip(owners, similarities):
            scores[owner] = max(scores.get(owner, -1.0), float(score))
        ranked = sorted(scores, key=lambda f: (-scores[f], f))
        return ranked, {"model": MODEL, "revision": REVISION, "device": self.device,
                        "documents": cost, "query": qcost, "top_scores": [[f, scores[f]] for f in ranked[:30]]}


def fuse(dense, lexical):
    """Equal-weight reciprocal-rank fusion, fixed k=60."""
    scores = {}
    for ranking in (dense, lexical):
        for rank, path in enumerate(ranking, 1):
            scores[path] = scores.get(path, 0) + 1 / (60 + rank)
    return sorted(scores, key=lambda f: (-scores[f], f))
