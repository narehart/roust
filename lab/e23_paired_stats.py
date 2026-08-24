"""E23 paired per-instance stats between the two MSWE arms.

FILE / LINE(all-or-nothing): paired binary outcomes -> gains/losses +
two-sided exact sign (binomial) test on the discordant pairs.
fraction: paired mean difference + sign counts.
FUNCTION: taken from the scored metric JSONs' per-instance detail
(needs --ts-functions scoring), same gains/losses + sign test.
"""
import json
import sys
from math import comb
from pathlib import Path

R = Path("/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions")


def load(p):
    recs = {}
    with open(p) as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                recs[r["instance_id"]] = r
    return recs


def sign_test(g, l):
    n = g + l
    if n == 0:
        return 1.0
    k = max(g, l)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n)


base = load(R / "mswe_jsts_e23_baseline.jsonl")
tsb = load(R / "mswe_jsts_e23_tsblocks.jsonl")
ids = sorted(set(base) & set(tsb))
print(f"paired instances: {len(ids)}")

for name, fn in [
    ("FILE  (all gold files)", lambda r: 1 if r.get("all_gold_files_retrieved") else 0),
    ("LINE  (all-or-nothing)", lambda r: 1 if r.get("hunk_line_recall") == 1.0 else 0),
]:
    g = sum(1 for i in ids if fn(tsb[i]) > fn(base[i]))
    l = sum(1 for i in ids if fn(tsb[i]) < fn(base[i]))
    nb = sum(fn(base[i]) for i in ids)
    nt = sum(fn(tsb[i]) for i in ids)
    print(f"{name}: base {nb}/{len(ids)} ({100*nb/len(ids):.2f}) -> ts {nt}/{len(ids)} "
          f"({100*nt/len(ids):.2f})  +{g}/-{l}  sign p={sign_test(g, l):.4g}")

fb = [base[i].get("hunk_line_recall") or 0.0 for i in ids]
ft = [tsb[i].get("hunk_line_recall") or 0.0 for i in ids]
d = [t - b for b, t in zip(fb, ft)]
g = sum(1 for x in d if x > 0)
l = sum(1 for x in d if x < 0)
print(f"fraction: base {sum(fb)/len(fb):.4f} -> ts {sum(ft)/len(ft):.4f}  "
      f"mean diff {sum(d)/len(d):+.4f}  +{g}/-{l}  sign p={sign_test(g, l):.4g}")

# FUNCTION from scored metric detail (if present)
try:
    mb = json.load(open(R / "agentless_metric_mswe_e23_baseline.json"))
    mt = json.load(open(R / "agentless_metric_mswe_e23_tsblocks.json"))
    db = {d["instance_id"]: d["correct"] for d in mb["all_instances"]["function"]["detail"]}
    dt = {d["instance_id"]: d["correct"] for d in mt["all_instances"]["function"]["detail"]}
    common = sorted(set(db) & set(dt))
    g = sum(1 for i in common if dt[i] and not db[i])
    l = sum(1 for i in common if db[i] and not dt[i])
    print(f"FUNCTION (exact, judged both arms n={len(common)}): "
          f"base {sum(db[i] for i in common)} -> ts {sum(dt[i] for i in common)}  "
          f"+{g}/-{l}  sign p={sign_test(g, l):.4g}")
    ngb = [d["n_gold_functions"] for d in mb["all_instances"]["function"]["detail"]]
    print(f"gold-function extraction: baseline-arm instances with n_gold_functions>0: "
          f"{sum(1 for n in ngb if n > 0)}/{len(ngb)}")
except FileNotFoundError as e:
    print(f"(FUNCTION detail pending: {e})")
