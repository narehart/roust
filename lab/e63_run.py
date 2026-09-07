#!/usr/bin/env python3
"""Rerank frozen E58 regions after exact producer-payload reproduction."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sqlite3
import sys
import time

from transformers import AutoTokenizer
import e57_run as run
from e56_dense import MODEL as EMBED_MODEL, REVISION as EMBED_REVISION
from e57_cached import CachedRegionRetriever
from e58_native import NativeRetriever
from e63_rerank import MODEL, REVISION, Reranker

original_eval = run.original_eval
original_pack = run.pack
published = {}
current = None
reranker = None


def payload_hash(regions, bundle):
    return hashlib.sha256(json.dumps({"regions": regions, "bundle": bundle}, sort_keys=True).encode()).hexdigest()


class CachedNative:
    candidates = NativeRetriever.candidates
    encode = CachedRegionRetriever.encode

    def __init__(self, cache):
        self.namespace = current["e57_diagnostic"]["embedding"]["documents"]["namespace"]
        namespace = json.loads(self.namespace)
        assert namespace[:3] == [EMBED_MODEL, EMBED_REVISION, "mlx-fp16-f32-last-token"]
        assert namespace[3:] == ["0.32.2", "0.31.3", "batch32-max512-causal-leftpad-v1"]
        self.tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL, revision=EMBED_REVISION, padding_side="left")
        self.db = sqlite3.connect(Path(cache).resolve().as_uri() + "?mode=ro", uri=True)


def evaluate(row, *args):
    global current
    if run.rig.evaluator.EXTRA_ENGINE_FLAGS:
        announced = False
        while row["instance_id"] not in published:
            if options.source_producer.exists():
                snapshot = options.source_producer.read_text()
                for line in snapshot[:snapshot.rfind("\n") + 1].splitlines():
                    record = json.loads(line)
                    published[record["instance_id"]] = record
            if row["instance_id"] not in published:
                if not announced:
                    print("waiting for E58 source record:", row["instance_id"], flush=True)
                    announced = True
                time.sleep(1)
        current = published[row["instance_id"]]
        assert current["base_commit"] == row["base_commit"] and current["repo"] == row["repo"]
        assert not current.get("error"), "producer failed; cannot establish a controlled rerank"
    return original_eval(row, *args)


def rerank_pack(corpus, baseline_regions, ranked):
    global reranker
    regions, bundle, _ = original_pack(corpus, baseline_regions, ranked)
    control_hash = payload_hash(regions, bundle)
    if control_hash != current["payload_sha256"]:
        raise ValueError("read-only E58 replay differs from producer payload")
    unique, seen = [], set()
    for item in ranked:
        key = tuple(item[1:])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    pool = unique[:128]
    if reranker is None:
        reranker = Reranker(options.rerank_cache)
    lines = {p: corpus[p].splitlines() for _, p, _, _ in pool}
    documents = [f"{p}:{a}-{b}\n" + "\n".join(lines[p][a - 1:b]) for _, p, a, b in pool]
    started = time.monotonic()
    # The rig passes only issue text to the engine; capture that same string.
    scores = reranker.score(active_query, documents)
    ordering = sorted(range(len(pool)), key=lambda i: (-scores[i], pool[i][1:]))
    reordered = [pool[i] for i in ordering] + unique[128:]
    run.diagnostic["reranking"] = {"model": MODEL, "revision": REVISION,
        "source_control_payload_sha256": control_hash, "source_control_identical": True,
        "producer_record_sha256": hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest(),
        "pool_size": len(pool), "seconds": time.monotonic() - started,
        "scores": [[*pool[i][1:], scores[i]] for i in ordering],
        "namespace": reranker.namespace}
    return original_pack(corpus, baseline_regions, reordered)


def main():
    global options, active_query
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source-producer", type=Path, required=True)
    parser.add_argument("--rerank-cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--slice", required=True)
    options, remaining = parser.parse_known_args()
    source_env = options.source_producer.with_name(options.slice + "_native_environment.json")
    source = json.loads(source_env.read_text())
    for filename in ["e58_native.py", "e58_units.py"]:
        assert run.rig.sha256(Path(__file__).with_name(filename)) == source["source_sha256"][filename]
    source_pack = json.loads(options.source_producer.with_name(options.slice + "_environment.json").read_text())
    assert run.rig.sha256(Path(__file__).with_name("e57_regions.py")) == source_pack["source_sha256"]["e57_regions.py"]
    options.out.mkdir(parents=True, exist_ok=True)
    path = options.out / f"{options.slice}_reranker_environment.json"
    assert not path.exists()
    path.write_text(json.dumps({"model": MODEL, "revision": REVISION,
        "source_producer": str(options.source_producer), "source_environment_sha256": run.rig.sha256(source_env),
        "source_sha256": {f: run.rig.sha256(Path(__file__).with_name(f)) for f in
                          ["e63_run.py", "e63_rerank.py", "e58_native.py", "e58_units.py"]},
        "packages": {p: importlib.metadata.version(p) for p in ["mlx", "mlx-lm", "transformers", "tokenizers"]}}, indent=2) + "\n")
    original_run = run.original_run
    def capture_query(query, *args):
        global active_query
        active_query = query
        return original_run(query, *args)
    run.original_run = capture_query
    run.original_eval = evaluate
    run.RegionRetriever = CachedNative
    run.pack = rerank_pack
    run.rig.ARMS = {"baseline": [], "flag-off": [], "cross-rerank": ["--semantic-regions"]}
    sys.argv = [sys.argv[0], "--out", str(options.out), "--slice", options.slice, *remaining]
    run.main()


if __name__ == "__main__":
    main()
