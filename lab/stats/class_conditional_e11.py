#!/usr/bin/env python3
"""E11 class-conditional scoring: partition the Lite-300 by query class
(prose / trace / fence / trace+fence, from the route arm's per-record route
stats) and report per-class FILE/FUNCTION/LINE/fraction per arm + deltas vs
baseline. Also itemizes every FILE flip (instance, direction, which routing
component was active). BLIZZARD worsened 25% of queries -- an aggregate win
hiding a class regression is not adoptable, hence this report."""
import json
import sys
from pathlib import Path

REPO = Path("/Users/nicholasarehart/programming-projects/bgrep")
sys.path.insert(0, str(REPO / "lab" / "stats"))
from paired_tests import (load_predictions, load_function_detail,
                          per_instance_metrics, mcnemar_exact_p,
                          paired_bootstrap_ci)

OUT = REPO / "lab" / "results_regions"
ARMS = {
    "baseline": ("e11_baseline.jsonl", "agentless_metric_e11_baseline.json"),
    "route085": ("e11_route085.jsonl", "agentless_metric_e11_route085.json"),
    "route070": ("e11_route070.jsonl", "agentless_metric_e11_route070.json"),
}

preds = {a: load_predictions([OUT / p]) for a, (p, _) in ARMS.items()}
fdet = {a: load_function_detail(OUT / m) for a, (_, m) in ARMS.items()}
per = {a: per_instance_metrics(preds[a], fdet[a]) for a in ARMS}

# class labels from the route085 arm (query-side, deterministic, arm-invariant)
klass = {}
for iid, rec in preds["route085"].items():
    r = rec.get("route") or {}
    klass[iid] = r.get("class", "prose")

ids = sorted(preds["baseline"].keys())
assert ids == sorted(preds["route085"].keys()) == sorted(preds["route070"].keys())

METRICS = ("file", "function", "line", "fraction")


def mean(v):
    return sum(v) / len(v) if v else float("nan")


report = {"n": len(ids), "classes": {}, "aggregate": {}, "file_flips": {}}

for scope_name, scope_ids in [("ALL", ids)] + [
    (c, [i for i in ids if klass[i] == c]) for c in ("prose", "trace", "fence", "trace+fence")
]:
    row = {"n": len(scope_ids)}
    for arm in ARMS:
        vals = {m: [per[arm][i][m] for i in scope_ids] for m in METRICS}
        row[arm] = {m: round(100 * mean(vals[m]), 2) if m != "fraction" else round(mean(vals[m]), 5)
                    for m in METRICS}
    for arm in ("route085", "route070"):
        deltas = {}
        for m in METRICS:
            a = [per["baseline"][i][m] for i in scope_ids]
            b = [per[arm][i][m] for i in scope_ids]
            if not a:
                continue
            d, lo, hi = paired_bootstrap_ci(a, b)
            entry = {"delta": round(100 * d, 2) if m != "fraction" else round(d, 5),
                     "ci95": [round(100 * lo, 2), round(100 * hi, 2)] if m != "fraction"
                     else [round(lo, 5), round(hi, 5)]}
            if m in ("file", "function", "line"):
                n01 = sum(1 for i in scope_ids if not per["baseline"][i][m] and per[arm][i][m])
                n10 = sum(1 for i in scope_ids if per["baseline"][i][m] and not per[arm][i][m])
                entry["n01"] = n01
                entry["n10"] = n10
                entry["mcnemar_p"] = mcnemar_exact_p(n01, n10)
            deltas[m] = entry
        row[f"{arm}_vs_baseline"] = deltas
    target = report["aggregate"] if scope_name == "ALL" else report["classes"].setdefault(scope_name, {})
    target.update(row)

# FILE flip itemization per route arm
for arm in ("route085", "route070"):
    flips = []
    for i in ids:
        b = per["baseline"][i]["file"]
        a = per[arm][i]["file"]
        if a == b:
            continue
        r = (preds[arm][i].get("route") or {})
        base_files = set((preds["baseline"][i].get("regions") or {}).keys())
        arm_files = set((preds[arm][i].get("regions") or {}).keys())
        flips.append({
            "instance_id": i,
            "direction": "gained" if a > b else "lost",
            "class": klass[i],
            "n_trace_files": len(r.get("trace_files") or []),
            "fence_dominant": bool(r.get("fence_dominant")),
            "files_added": sorted(arm_files - base_files)[:8],
            "files_removed": sorted(base_files - arm_files)[:8],
        })
    report["file_flips"][arm] = flips

out_path = OUT / "e11_class_conditional.json"
out_path.write_text(json.dumps(report, indent=1))
print(json.dumps({"aggregate": report["aggregate"],
                  "class_n": {c: report["classes"][c]["n"] for c in report["classes"]}}, indent=1))
print(f"wrote {out_path}")
