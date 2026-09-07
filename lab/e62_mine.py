#!/usr/bin/env python3
"""Ancillary path/history candidate diagnostic; no bundle or adoption claims."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

import pandas as pd
from e51_run import ROOT, SLICES, sha256

SUFFIXES = {".md", ".rst", ".txt", ".adoc", ".asciidoc", ".json", ".yml", ".yaml", ".toml", ".lock", ".xml", ".gradle", ".kts"}
NAMES = {"Makefile", "CHANGELOG", "CHANGES", "HISTORY", "NEWS", "AUTHORS", "CREDITS"}


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def commits(raw):
    # Git emits NUL + commit hash + NUL before its NUL-delimited path list.
    parts = re.split(rb"\x00[0-9a-f]{40}\x00", raw)
    assert not parts[0], "unexpected git log framing"
    return [{p.decode("utf-8") for p in part.removeprefix(b"\x00\n").split(b"\x00") if p}
            for part in parts[1:]]


def terms(text):
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return set(re.findall(r"[a-z][a-z0-9]+", text.lower()))


def rank(query, seeds, candidates, history):
    counts, pairs = Counter(), Counter()
    for changed in history:
        if len(changed) > 50:
            continue
        counts.update(changed)
        for seed in seeds & changed:
            for path in candidates & changed:
                if seed != path:
                    pairs[seed, path] += 1
    scores = Counter()
    for (seed, path), count in pairs.items():
        scores[path] += count / math.sqrt(counts[seed] * counts[path])
    historical = sorted(scores, key=lambda p: (-scores[p], p))
    bags = {p: terms(p) for p in candidates}
    df = Counter(t for bag in bags.values() for t in bag)
    query_terms = terms(query)
    lexical = {p: sum(math.log(1 + len(bags) / df[t]) for t in sorted(query_terms & bag))
               for p, bag in bags.items()}
    lexical = sorted((p for p in lexical if lexical[p] > 0), key=lambda p: (-lexical[p], p))
    fusion = Counter()
    for ordering in [historical, lexical]:
        for i, p in enumerate(ordering, 1):
            fusion[p] += 1 / (60 + i)
    return {"history": historical, "path-history-rrf": sorted(fusion, key=lambda p: (-fusion[p], p))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slice", choices=["rust", "cpp"], required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    assert not args.out.exists()
    pq, repos, expected = SLICES[args.slice]
    baseline = ROOT / "lab/results_regions/e55/discovery" / f"{args.slice}_baseline.jsonl"
    diagnosis = baseline.with_name(f"{args.slice}_diagnosis.json")
    bases = {r["instance_id"]: r for r in map(json.loads, baseline.read_text().splitlines())}
    absent = json.loads(diagnosis.read_text())["absent_gold"]["by_instance"]
    rows = pd.read_parquet(ROOT / "lab" / pq).to_dict("records")
    assert len(rows) == expected and {r["instance_id"] for r in rows} == set(bases)
    records = []
    for i, row in enumerate(rows, 1):
        repo = ROOT / "lab" / repos / row["repo"].replace("/", "__")
        candidates = set()
        for item in git(repo, "ls-tree", "-rzl", row["base_commit"]).split(b"\x00"):
            if not item:
                continue
            metadata, raw_path = item.split(b"\t", 1)
            mode, kind, oid, size = metadata.split()
            path = raw_path.decode("utf-8")
            if mode in {b"100644", b"100755"} and kind == b"blob" and int(size) <= 2_000_000:
                if Path(path).suffix.lower() in SUFFIXES or Path(path).name in NAMES:
                    candidates.add(path)
        raw = git(repo, "log", row["base_commit"], "--no-merges", "-n", "200", "--format=%x00%H%x00", "--name-only", "-z")
        history = commits(raw)
        rankings = rank(row["problem_statement"], set(bases[row["instance_id"]]["regions"]), candidates, history)
        missing = set(absent.get(row["instance_id"], []))
        records.append({"instance_id": row["instance_id"], "base_commit": row["base_commit"],
            "history_sha256": hashlib.sha256(raw).hexdigest(),
            "n_candidates": len(candidates), "n_history_commits": len(history),
            "absent_gold": sorted(missing), "absent_without_candidate": sorted(missing - candidates),
            "rankings": {arm: {"top26": order[:26], "missing_ranks": {p: order.index(p) + 1 if p in order else None for p in sorted(missing)}}
                         for arm, order in rankings.items()}})
        if i % 20 == 0 or i == len(rows):
            print(args.slice, i, "/", len(rows), flush=True)
    result = {"kind": "path/history diagnostic, not full-context retrieval", "slice": args.slice,
        "n": len(records), "source_sha256": sha256(Path(__file__)), "gold_sha256": sha256(ROOT / "lab" / pq),
        "baseline_sha256": sha256(baseline), "diagnosis_sha256": sha256(diagnosis), "records": records}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
