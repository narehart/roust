"""Read frozen E56 vectors without allocating another model or recomputing."""
import hashlib
import json
from pathlib import Path
import sqlite3
import time

import numpy as np
from transformers import AutoTokenizer

from e56_dense import MODEL, REVISION
from e57_regions import RegionRetriever


class CachedRegionRetriever(RegionRetriever):
    def __init__(self, cache, producer, slice_name):
        env = json.loads(producer.with_name(slice_name + "_environment.json").read_text())
        # The producer appends while this consumer starts; only complete JSONL
        # records establish that all corresponding vectors were committed.
        snapshot = producer.read_text()
        published = snapshot.rsplit("\n", 1)[0] if "\n" in snapshot else ""
        first = next((r for r in map(json.loads, published.splitlines())
                      if r.get("e56_diagnostic", {}).get("device")), None)
        if first is None:
            raise ValueError("producer has no successful embedding record")
        device = first["e56_diagnostic"]["device"]
        assert env["model"] == MODEL and env["revision"] == REVISION
        self.namespace = json.dumps([MODEL, REVISION, device,
            "torch.float16" if device == "mps" else "torch.float32",
            env["packages"]["torch"], "last-token-leftpad-max512-v1"])
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION, padding_side="left")
        self.db = sqlite3.connect(Path(cache).resolve().as_uri() + "?mode=ro", uri=True)

    def encode(self, texts):
        start = time.monotonic()
        vectors = []
        for text in texts:
            key = hashlib.sha256((self.namespace + text).encode()).hexdigest()
            row = self.db.execute("SELECT vector FROM embeddings WHERE key=?", (key,)).fetchone()
            if row is None:
                raise ValueError(f"producer completed but embedding is absent: {key}")
            vectors.append(np.frombuffer(row[0], dtype=np.float32).copy())
        vectors = np.stack(vectors)
        assert np.isfinite(vectors).all()
        return vectors, {"n_texts": len(texts), "new_unique": 0,
                         "seconds": time.monotonic() - start,
                         "vectors_sha256": hashlib.sha256(vectors.tobytes()).hexdigest(),
                         "read_only_producer_cache": True}
