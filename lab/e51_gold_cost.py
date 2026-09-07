#!/usr/bin/env python3
"""Measure gold-only context size, without retrieving or changing any checkout.

This is a workload diagnostic, not an achievable recall ceiling: the oracle
knows the answer and omits filenames, irrelevant lines, and prompt overhead.
Token counts depend on the declared serialization (sorted lines per file,
joined with newlines); do not treat them as a strict tokenizer lower bound.
"""
import argparse
from collections import defaultdict
from functools import lru_cache
import importlib.metadata
import json
from pathlib import Path

import pandas as pd
import tiktoken

import agentless_metric_verified as metric
from e51_mine import SOURCE_EXT
from e51_run import ROOT, SLICES, sha256


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    encoder = tiktoken.get_encoding("cl100k_base")
    metric.TS_FUNCTIONS = metric.LANG_FUNCTIONS = True
    original_show = metric.git_show
    def readable_show(*args):
        try:
            return original_show(*args)
        except UnicodeDecodeError:
            # Some non-source gold fixtures contain invalid UTF-8. Keep the
            # instance as a reported read failure; do not fabricate its cost.
            return None
    report = {"serialization": "per file: union of gold lines in ascending order joined with newline; sum cl100k_base tokens across files; no headers",
              "tiktoken_version": importlib.metadata.version("tiktoken"), "slices": {}}
    for name, (pq, repo_dir, expected) in SLICES.items():
        if name == "ver":
            continue  # held-out data is not a mining corpus
        metric.SWEBENCH_REPOS = ROOT / "lab" / repo_dir
        metric.git_show = lru_cache(maxsize=128)(readable_show)
        rows = metric_rows = pd.read_parquet(ROOT / "lab" / pq).to_dict("records")
        assert len(rows) == expected
        records = []
        for r in metric_rows:
            hunks = metric.parse_gold_hunks(r["patch"])
            functions, ast_ok = metric.gold_function_spans_for_instance(r["repo"], r["base_commit"], hunks)
            function_lines = defaultdict(set)
            for f, a, b in functions:
                function_lines[f].update(range(a, b + 1))
            line_lines = {f: {ln for a, b in ranges for ln in range(a, b + 1)} for f, ranges in hunks.items()}
            total = {"line_tokens": 0, "source_line_tokens": 0, "function_tokens": 0}
            failures = []
            for f in sorted(set(line_lines) | set(function_lines)):
                text = metric.git_show(r["repo"], r["base_commit"], f)
                if text is None:
                    failures.append(f)
                    continue
                lines = text.splitlines()
                def tokens(indices):
                    chunk = "\n".join(lines[i - 1] for i in sorted(indices) if 1 <= i <= len(lines))
                    return len(encoder.encode(chunk, disallowed_special=()))
                cost = tokens(line_lines.get(f, set()))
                total["line_tokens"] += cost
                if Path(f).suffix.lower() in SOURCE_EXT:
                    total["source_line_tokens"] += cost
                total["function_tokens"] += tokens(function_lines.get(f, set()))
            records.append({"instance_id": r["instance_id"], "n_gold_functions": len(functions),
                            "ast_ok": ast_ok, "read_failures": failures, **total})
        valid = [r for r in records if r["ast_ok"] and not r["read_failures"]]
        summary = {"n": expected, "read_failure_instances": len(records) - len(valid)}
        for key in ("line_tokens", "source_line_tokens", "function_tokens"):
            values = pd.Series([r[key] for r in valid])
            summary[key] = {"median": float(values.median()), "p90": float(values.quantile(.9)),
                            "over_8192_n": int((values > 8192).sum()), "over_16384_n": int((values > 16384).sum())}
        report["slices"][name] = {"gold_sha256": sha256(ROOT / "lab" / pq), "summary": summary, "instances": records}
        print(name, json.dumps(summary), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
