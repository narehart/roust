#!/usr/bin/env python3
"""Emit the README scoreboard rows for the floor-0.15 default from the E44
metric JSONs. Refuses to print a row whose metric file is missing, so a
stale row can never be pasted by accident."""
import json, os, sys
M = "lab/results_regions/e44/metrics"
# Usage: readme_rows.py [PY_SUFFIX MSWE_SUFFIX]  (defaults: fl15 fl15ship)
PY_SUF = sys.argv[1] if len(sys.argv) > 1 else "fl15"
MS_SUF = sys.argv[2] if len(sys.argv) > 2 else "fl15ship"
rows = [("Python — Lite 300",f"lite_{PY_SUF}"),("Python — Verified 407 (held-out)",f"ver_{PY_SUF}"),
        ("JS/TS — MSWE 580",f"jsts_{MS_SUF}"),("Java — MSWE 128",f"java_{MS_SUF}"),("Go — MSWE 428",f"go_{MS_SUF}"),
        ("Rust — MSWE 239",f"rust_{MS_SUF}"),("C — MSWE 128",f"c_{MS_SUF}"),("C++ — MSWE 129",f"cpp_{MS_SUF}")]
missing = []
for label, name in rows:
    p = f"{M}/{name}.json"
    if not os.path.exists(p): missing.append(name); continue
    d = json.load(open(p)); a = d.get("all_instances", d)
    print(f"| {label} | {a['file']['pct_correct']:.2f} | {a['function']['pct_correct']:.2f} | "
          f"{a['line']['pct_correct_all_or_nothing']:.2f} | {a['line']['mean_fraction_covered']:.3f} | defaults | `{p}` |")
if missing: print("MISSING:", ", ".join(missing), file=sys.stderr); sys.exit(1)
