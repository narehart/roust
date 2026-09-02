#!/usr/bin/env python
"""E44 paired comparison: baseline vs treatment jsonl from the region-eval harness.
Prints FILE (must be identical for a budget-only change), per-instance identity,
fraction/token deltas, and paired significance. Usage: compare.py BASE TREAT [label]"""
import json, sys
from scipy import stats
def load(p): return {json.loads(l)["instance_id"]: json.loads(l) for l in open(p)}
b, t = load(sys.argv[1]), load(sys.argv[2]); label = sys.argv[3] if len(sys.argv) > 3 else ""
com = [k for k in b if k in t]
def ok(r): return r.get("all_gold_files_retrieved") is True
fb = 100*sum(ok(b[k]) for k in com)/len(com); ft = 100*sum(ok(t[k]) for k in com)/len(com)
flips = [k for k in com if ok(b[k]) != ok(t[k])]
db = [t[k].get("hunk_line_recall",0)-b[k].get("hunk_line_recall",0) for k in com]
nz = [x for x in db if abs(x) > 1e-12]
w = stats.wilcoxon(nz).pvalue if len(nz) > 5 else float("nan")
tokb = sum(b[k].get("tokens",0) for k in com)/len(com); tokt = sum(t[k].get("tokens",0) for k in com)/len(com)
gain = sum(1 for x in nz if x > 0); loss = sum(1 for x in nz if x < 0)
print(f"{label:22s} n={len(com)} FILE {fb:.2f}->{ft:.2f} (flips={len(flips)}) | frac d={sum(db)/len(db):+.5f} "
      f"gain/loss={gain}/{loss} wilcoxon p={w:.4f} | tok {tokb:.0f}->{tokt:.0f}")
if flips: print("   FILE flips (should be none for a budget-only change):", flips[:6])
