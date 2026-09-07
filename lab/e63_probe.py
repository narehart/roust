#!/usr/bin/env python3
"""Synthetic native/reference check; does not consume benchmark examples."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

import numpy as np
import torch
from transformers import AutoModelForCausalLM
from e63_rerank import MODEL, REVISION, Reranker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    with tempfile.TemporaryDirectory(prefix="roust-rerank-probe-") as directory:
        reranker = Reranker(Path(directory) / "scores.sqlite")
        query = "Fix decompression of gzip input streams."
        documents = ["decoder.py\nimport gzip\ndef decode(data):\n    return gzip.decompress(data)",
                     "router.py\ndef route(request):\n    return handlers[request.path](request)"]
        native = reranker.score(query, documents)
        assert native[0] > native[1]
        assert native == reranker.score(query, documents)
        inputs = reranker.inputs(query, documents)
        model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, dtype=torch.float16).to("mps").eval()
        tensors = {k: torch.tensor(v, device="mps") for k, v in inputs.items()}
        with torch.no_grad():
            hidden = model.model(**tensors).last_hidden_state[:, -1]
            logits = model.lm_head(hidden).float()[:, reranker.labels]
            reference = (logits[:, 1] - logits[:, 0]).cpu().numpy()
        error = float(np.max(np.abs(reference - np.array(native))))
        assert error < .25 and reference[0] > reference[1], (native, reference, error)
        long = reranker.inputs("issue " * 4000, [documents[0]])
        assert long["input_ids"].shape[1] <= 2048
        assert "gzip.decompress" in reranker.tokenizer.decode(long["input_ids"][0])
        report = {"kind": "synthetic backend probe, not recall evidence", "model": MODEL, "revision": REVISION,
                  "native": native, "torch_reference": reference.tolist(), "max_abs_logit_difference_error": error,
                  "rank_identical": True, "cache_exact": True, "long_query_preserves_document": True,
                  "namespace": reranker.namespace, "torch_version": torch.__version__,
                  "source_sha256": {f: hashlib.sha256(Path(__file__).with_name(f).read_bytes()).hexdigest()
                                    for f in ["e63_rerank.py", "e63_probe.py"]}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
