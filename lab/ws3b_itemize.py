"""WS3b per-instance itemization between a base and a v2 arm (issue #56).

For every instance where ANYTHING changed (FILE flag, LINE all-or-nothing,
fraction, FUNCTION verdict, or the v2 arm fired trace frames), print:
gold files, v2 trace_boost.trace_files (which frames fired), gold rank in
the packed-file order before/after, and the metric deltas.

Usage:
  uv run --no-project --with pandas --with pyarrow python lab/ws3b_itemize.py \
      gold.parquet base.jsonl v2.jsonl [metric_base.json metric_v2.json]
"""

from __future__ import annotations

import json
import re
import sys


def load(p):
    recs = {}
    with open(p) as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                recs[r["instance_id"]] = r
    return recs


def gold_files(patch):
    return sorted({m.group(2) for m in
                   re.finditer(r"^diff --git a/(\S+) b/(\S+)", patch or "", re.M)})


def func_detail(metric_path):
    with open(metric_path) as fh:
        d = json.load(fh)
    det = d["all_instances"]["function"].get("detail") or \
        d.get("file_correct_subset", {}).get("function", {}).get("detail", [])
    return {r["instance_id"]: r["correct"] for r in det}


def gold_rank(rec, gold):
    """1-based rank of the first gold file in the packed-region key order."""
    files = list((rec.get("regions") or {}).keys())
    for i, f in enumerate(files):
        if f in gold:
            return i + 1
    return None


def main():
    import pandas as pd
    gold_df = pd.read_parquet(sys.argv[1])
    gold_map = {r["instance_id"]: gold_files(r["patch"]) for _, r in gold_df.iterrows()}
    a, b = load(sys.argv[2]), load(sys.argv[3])
    fa = fb = {}
    if len(sys.argv) > 5:
        fa, fb = func_detail(sys.argv[4]), func_detail(sys.argv[5])
    ids = sorted(set(a) & set(b))
    n_changed = 0
    for i in ids:
        ra, rb = a[i], b[i]
        gold = gold_map.get(i, [])
        tb_b = ((rb.get("trace_boost") or {}).get("trace_files")) or []
        tb_a = ((ra.get("trace_boost") or {}).get("trace_files")) or []
        file_a = bool(ra.get("all_gold_files_retrieved"))
        file_b = bool(rb.get("all_gold_files_retrieved"))
        line_a = ra.get("hunk_line_recall")
        line_b = rb.get("hunk_line_recall")
        fn_a, fn_b = fa.get(i), fb.get(i)
        changed = (file_a != file_b or line_a != line_b or fn_a != fn_b
                   or tb_a != tb_b)
        if not changed:
            continue
        n_changed += 1
        print(f"== {i}")
        print(f"   gold: {gold}")
        print(f"   trace_files base: {tb_a}")
        print(f"   trace_files v2:   {tb_b}")
        print(f"   FILE {int(file_a)}->{int(file_b)}  LINE(frac) {line_a}->{line_b}  "
              f"FUNCTION {fn_a}->{fn_b}")
        print(f"   gold rank in packed order: {gold_rank(ra, set(gold))} -> "
              f"{gold_rank(rb, set(gold))}")
    print(f"\n{n_changed} changed / {len(ids)} paired")


if __name__ == "__main__":
    main()
