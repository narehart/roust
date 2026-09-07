#!/usr/bin/env python3
"""Evaluate source-only semantic packing through the established E51 rig."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import time

import e51_run as rig
from e56_dense import MODEL, REVISION
from e57_regions import RegionRetriever, pack

rig.ARMS = {"baseline": [], "flag-off": [], "semantic-regions": ["--semantic-regions"]}
rig.ISOLATE_BLOCK_CACHE = True
rig.DISCOVERY_ENDPOINTS = 3
original_run = rig.evaluator.run_roust
original_eval = rig.evaluator.eval_verified_instance
retriever = None
diagnostic = {}


def run(query, repo_path, timeout, pad_lines, len_exp):
    global retriever
    diagnostic.clear()
    flags = rig.evaluator.EXTRA_ENGINE_FLAGS
    if not flags:
        return original_run(query, repo_path, timeout, pad_lines, len_exp)
    assert flags == ["--semantic-regions"]
    rig.evaluator.EXTRA_ENGINE_FLAGS = []
    try:
        obj, error = original_run(query, repo_path, timeout, pad_lines, len_exp)
    finally:
        rig.evaluator.EXTRA_ENGINE_FLAGS = flags
    if error:
        return obj, error
    try:
        if retriever is None:
            retriever = RegionRetriever("/private/tmp/roust-e56-cache/embeddings.sqlite")
        corpus = json.loads((repo_path / ".roust/rust-index.bin").read_text())["corpus"]["text"]
        ranked, embedding = retriever.candidates(query, corpus)
        regions, bundle, stats = pack(corpus, obj["regions"], ranked)
        diagnostic.update(embedding=embedding, packing=stats, model=MODEL, revision=REVISION)
        obj.update(regions=regions, bundle=bundle)
        obj["stats"]["bundle_tokens"] = stats["bundle_tokens"]
        return obj, None
    except (ValueError, RuntimeError, OSError) as exc:
        return None, f"semantic packing failed: {exc}"


def evaluate(row, *args):
    started = time.monotonic()
    diagnostic.clear()
    result = original_eval(row, *args)
    result["e57_diagnostic"] = dict(diagnostic)
    result["e57_elapsed_seconds"] = time.monotonic() - started
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--slice", required=True)
    args, _ = ap.parse_known_args()
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{args.slice}_environment.json"
    assert not path.exists(), "output already exists"
    path.write_text(json.dumps({"model": MODEL, "revision": REVISION,
        "packages": {p: importlib.metadata.version(p) for p in
                     ["torch", "transformers", "numpy", "tokenizers", "tiktoken", "huggingface_hub"]},
        "source_sha256": {f: rig.sha256(Path(__file__).with_name(f)) for f in
                          ["e57_run.py", "e57_regions.py", "e56_dense.py"]}}, indent=2) + "\n")
    rig.evaluator.run_roust = run
    rig.evaluator.eval_verified_instance = evaluate
    rig.main()
