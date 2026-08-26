"""WS3a per-instance itemization between a base and a v2 arm (#56 WS3a).

For every paired instance, compares FILE (all_gold_files_retrieved), the
LINE all-or-nothing bit, and hunk_line_recall (fraction), and prints one
row per CHANGED instance with direction and the v2 bundle's doc-dir files
(the mechanism attribution). Also flags any v2 bundle containing a
"thirdparty" path component -- the VENDOR_RE gap the identity gate caught
on nlohmann (`benchmarks/thirdparty/` Google-Benchmark files are undamped
by v2 AND unguarded by VENDOR_RE, which only knows `third_party`) -- and
reports whether such instances lost any metric (displacement) or not.

Usage: python ws3a_itemize.py base.jsonl v2.jsonl
"""

from __future__ import annotations

import json
import re
import sys

DOCLIKE_RE = re.compile(r"(?i)(^|/)(docs?|examples?|benchmarks?|benches)(/|$)")
THIRDPARTY_RE = re.compile(r"(?i)(^|/)thirdparty(/|$)")


def load(p):
    recs = {}
    with open(p) as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                recs[r["instance_id"]] = r
    return recs


def main() -> None:
    a, b = load(sys.argv[1]), load(sys.argv[2])
    ids = sorted(set(a) & set(b))
    print(f"paired: {len(ids)}  (base={sys.argv[1]}  v2={sys.argv[2]})")

    changed = 0
    identical_regions = 0
    tp_hits = []
    for i in ids:
        ra, rb = a[i], b[i]
        if ra.get("regions") == rb.get("regions"):
            identical_regions += 1
        fa = 1 if ra.get("all_gold_files_retrieved") else 0
        fb = 1 if rb.get("all_gold_files_retrieved") else 0
        la = 1 if ra.get("hunk_line_recall") == 1.0 else 0
        lb = 1 if rb.get("hunk_line_recall") == 1.0 else 0
        xa = ra.get("hunk_line_recall") or 0.0
        xb = rb.get("hunk_line_recall") or 0.0
        v2_files = list((rb.get("regions") or {}).keys())
        tp = [f for f in v2_files if THIRDPARTY_RE.search(f)]
        if tp:
            tp_hits.append((i, tp, fa - fb, xa - xb))
        if fa != fb or la != lb or abs(xa - xb) > 1e-12:
            changed += 1
            doc = [f for f in v2_files if DOCLIKE_RE.search(f)]
            print(f"  {i:45s} FILE {fa}->{fb}  LINE {la}->{lb}  "
                  f"frac {xa:.3f}->{xb:.3f} ({xb-xa:+.3f})  "
                  f"doc-dir files in v2 bundle: {doc[:4]}")
    print(f"changed instances: {changed}/{len(ids)}  "
          f"(identical regions dicts: {identical_regions}/{len(ids)})")

    if tp_hits:
        print(f"\nTHIRDPARTY-in-bundle instances (VENDOR_RE gap): {len(tp_hits)}")
        for i, tp, dfile, dfrac in tp_hits:
            harm = "DISPLACED-GOLD" if (dfile > 0 or dfrac > 1e-12) else "no metric loss"
            print(f"  {i:45s} {harm}  files: {tp[:3]}")
    else:
        print("\nno thirdparty paths in any v2 bundle")


if __name__ == "__main__":
    main()
