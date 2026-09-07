#!/usr/bin/env python3
"""Compare fixed-window and AST-unit cache reuse without model inference."""
import hashlib
import json

from transformers import AutoTokenizer

import e51_run as rig
from e56_dense import MODEL, REVISION
from e58_units import documents

rig.ARMS = {"baseline": []}
original_run = rig.evaluator.run_roust
original_eval = rig.evaluator.eval_verified_instance
tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
seen = {"windows": set(), "ast": set()}
diagnostic = {}


def run(query, repo_path, *args):
    diagnostic.clear()
    obj, error = original_run(query, repo_path, *args)
    if error:
        return obj, error
    corpus = json.loads((repo_path / ".roust/rust-index.bin").read_text())["corpus"]["text"]
    for method in seen:
        docs = documents(tokenizer, corpus, method == "ast")
        new = {}
        for doc in docs:
            key = hashlib.sha256(doc.encode()).hexdigest()
            if key not in seen[method]:
                new[key] = doc
                seen[method].add(key)
        texts = sorted(new.values(), key=len)
        lengths = [min(512, len(tokenizer.encode(text))) for text in texts]
        batches = [lengths[i:i + 8] for i in range(0, len(lengths), 8)]
        diagnostic[method] = {"n_chunks": len(docs), "new_unique": len(new),
            "new_payload_tokens": sum(lengths),
            "padded_tokens_batch8": sum(max(b) * len(b) for b in batches),
            "attention_cells_batch8": sum(max(b) ** 2 * len(b) for b in batches)}
    return obj, None


def evaluate(row, *args):
    diagnostic.clear()
    result = original_eval(row, *args)
    result["e58_reuse"] = dict(diagnostic)
    return result


if __name__ == "__main__":
    rig.evaluator.run_roust = run
    rig.evaluator.eval_verified_instance = evaluate
    rig.main()
