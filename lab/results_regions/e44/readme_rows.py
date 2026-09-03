#!/usr/bin/env python3
"""Emit the README scoreboard rows for the floor-0.15 default from the E44
metric JSONs. Refuses to print a row whose metric file is missing, so a
stale row can never be pasted by accident."""
import json, os, sys
M = "lab/results_regions/e44/metrics"
rows = [("Python — Lite 300","lite_fl15"),("Python — Verified 407 (held-out)","ver_fl15"),
        ("JS/TS — MSWE 580","jsts_fl15ship"),("Java — MSWE 128","java_fl15ship"),("Go — MSWE 428","go_fl15ship"),
        ("Rust — MSWE 239","rust_fl15ship"),("C — MSWE 128","c_fl15ship"),("C++ — MSWE 129","cpp_fl15ship")]
missing = []
for label, name in rows:
    p = f"{M}/{name}.json"
    if not os.path.exists(p): missing.append(name); continue
    d = json.load(open(p)); a = d.get("all_instances", d)
    print(f"| {label} | {a['file']['pct_correct']:.2f} | {a['function']['pct_correct']:.2f} | "
          f"{a['line']['pct_correct_all_or_nothing']:.2f} | {a['line']['mean_fraction_covered']:.3f} | defaults | `{p}` |")
if missing: print("MISSING:", ", ".join(missing), file=sys.stderr); sys.exit(1)
