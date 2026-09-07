#!/usr/bin/env python3
"""Gold-informed duplicate-function workload diagnosis, not retrieval."""
import argparse
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import textwrap

import pandas as pd
import tiktoken

import agentless_metric_verified as metric
from e51_run import ROOT, SLICES, sha256


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slice", choices=["rust", "cpp"], required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    assert not args.out.exists()
    pq, repo_dir, expected = SLICES[args.slice]
    gold = ROOT / "lab" / pq
    metric.SWEBENCH_REPOS = ROOT / "lab" / repo_dir
    metric.TS_FUNCTIONS = metric.LANG_FUNCTIONS = True
    show = metric.git_show
    @lru_cache(maxsize=128)
    def readable(*a):
        try:
            return show(*a)
        except UnicodeDecodeError:
            return None
    metric.git_show = readable
    encoder = tiktoken.get_encoding("cl100k_base")
    records = []
    rows = pd.read_parquet(gold).to_dict("records")
    assert len(rows) == expected
    for index, r in enumerate(rows, 1):
        functions, ok = metric.gold_function_spans_for_instance(
            r["repo"], r["base_commit"], metric.parse_gold_hunks(r["patch"]))
        by_file = defaultdict(list)
        for path, a, b in functions:
            by_file[path].append((a, b))
        groups = {"exact": {}, "dedent": {}}
        total = {"exact": 0, "dedent": 0}
        for path, spans in by_file.items():
            source = metric.git_show(r["repo"], r["base_commit"], path)
            if source is None:
                ok = False
                continue
            lines = source.splitlines()
            outer = []
            for a, b in sorted(spans, key=lambda s: (s[0], -s[1])):
                if outer and a <= outer[-1][1]:
                    outer[-1] = (outer[-1][0], max(outer[-1][1], b))
                else:
                    outer.append((a, b))
            for a, b in outer:
                text = "\n".join(lines[a - 1:b])
                for kind, value in [("exact", text), ("dedent", textwrap.dedent(text))]:
                    key = hashlib.sha256(value.encode()).hexdigest()
                    cost = len(encoder.encode_ordinary(value))
                    total[kind] += cost
                    group = groups[kind].setdefault(key, {"body_tokens": cost, "locations": []})
                    group["locations"].append([path, a, b])
        result = {"instance_id": r["instance_id"], "ast_ok": ok, "n_gold_functions": len(functions)}
        for kind, gg in groups.items():
            shared = [v for v in gg.values() if len({loc[0] for loc in v["locations"]}) > 1]
            result[kind] = {"unshared_body_tokens": total[kind],
                "potential_body_tokens_saved": sum((len(v["locations"]) - 1) * v["body_tokens"] for v in shared),
                "potential_saved_min64": sum((len(v["locations"]) - 1) * v["body_tokens"] for v in shared if v["body_tokens"] >= 64),
                "groups": shared}
        records.append(result)
        if index % 25 == 0 or index == len(rows):
            print(args.slice, index, "/", expected, flush=True)
    report = {"kind": "oracle duplicate-function workload, not a recall or strict budget ceiling",
        "slice": args.slice, "n": expected, "gold_sha256": sha256(gold),
        "driver_sha256": sha256(Path(__file__)), "scoring_helper_sha256": sha256(ROOT / "lab/agentless_metric_verified.py"),
        "serialization": "nonoverlapping outer gold-function bodies, newline joined, body costs summed; no location/format overhead",
        "records": records, "summary": {}}
    for kind in groups:
        valid = [r for r in records if r["ast_ok"]]
        report["summary"][kind] = {"valid_n": len(valid),
            "instances_with_cross_file_duplicates": sum(bool(r[kind]["groups"]) for r in valid),
            "instances_with_substantial_duplicates": sum(r[kind]["potential_saved_min64"] > 0 for r in valid),
            "body_tokens_saved": sum(r[kind]["potential_body_tokens_saved"] for r in valid),
            "body_tokens_saved_min64": sum(r[kind]["potential_saved_min64"] for r in valid)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
