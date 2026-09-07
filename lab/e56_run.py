#!/usr/bin/env python3
"""Frozen semantic file selection through the existing private-clone rig."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time

import e51_run as rig
from e56_dense import MODEL, REVISION, Retriever, fuse

rig.ARMS = {"baseline": [], "flag-off": [], "dense10": ["dense10"], "hybrid26": ["hybrid26"]}
rig.ISOLATE_BLOCK_CACHE = True
rig.DISCOVERY_ENDPOINTS = 3
original_run = rig.evaluator.run_roust
original_eval = rig.evaluator.eval_verified_instance
retriever = None
rankings = {}
diagnostic = {}


def run(query, repo_path, timeout, pad_lines, len_exp):
    global retriever
    diagnostic.clear()
    if rig.evaluator.ROUST_BIN.name != "research_pack":
        return original_run(query, repo_path, timeout, pad_lines, len_exp)
    request = {"repo": str(repo_path), "query": query}
    flags = rig.evaluator.EXTRA_ENGINE_FLAGS
    if flags:
        key = (str(repo_path), query, subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_path, text=True).strip())
        if key != rankings.get("key"):
            if retriever is None:
                retriever = Retriever("/private/tmp/roust-e56-cache/embeddings.sqlite")
            # The preceding baseline/control built this cache at this commit.
            index = json.loads((repo_path / ".roust/rust-index.bin").read_text())
            source = index["corpus"]["text"]
            dense, info = retriever.rank(query, source)
            control = subprocess.run([str(rig.evaluator.ROUST_BIN)], input=json.dumps(request),
                capture_output=True, text=True, timeout=timeout, check=True)
            lexical = json.loads(control.stdout)["diagnostic"]["selected_files"]
            rankings.clear()
            rankings.update(key=key, dense10=dense[:10], hybrid26=fuse(dense, lexical)[:26], info=info)
        request["files"] = rankings[flags[0]]
        diagnostic.update(rankings["info"])
        diagnostic["arm"] = flags[0]
    try:
        proc = subprocess.run([str(rig.evaluator.ROUST_BIN)], input=json.dumps(request),
                              capture_output=True, text=True, timeout=timeout)
        if proc.returncode:
            return None, f"exit {proc.returncode}: {proc.stderr[:300]}"
        obj = json.loads(proc.stdout)
        diagnostic["packing"] = obj["diagnostic"]
        return obj, None
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        return None, str(exc)


def evaluate(row, *args):
    started = time.monotonic()
    diagnostic.clear()
    result = original_eval(row, *args)
    result["e56_diagnostic"] = dict(diagnostic)
    result["e56_elapsed_seconds"] = time.monotonic() - started
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--slice", required=True)
    args, _ = ap.parse_known_args()
    args.out.mkdir(parents=True, exist_ok=True)
    environment = {"model": MODEL, "revision": REVISION,
        "packages": {p: importlib.metadata.version(p) for p in
                     ["torch", "transformers", "numpy", "tokenizers", "huggingface_hub"]},
        "driver_sha256": rig.sha256(Path(__file__)),
        "retriever_sha256": rig.sha256(Path(__file__).with_name("e56_dense.py"))}
    path = args.out / f"{args.slice}_environment.json"
    assert not path.exists(), "output already exists"
    path.write_text(json.dumps(environment, indent=2) + "\n")
    rig.evaluator.run_roust = run
    rig.evaluator.eval_verified_instance = evaluate
    rig.main()
