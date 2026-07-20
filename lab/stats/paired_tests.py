#!/usr/bin/env python3
"""Paired significance tests for two region-eval runs (paper stats layer).

Inputs are TWO runs (arm A, arm B) over the SAME instance set, each given as:
  - its region-eval predictions JSONL (region_eval2 / region_eval_verified /
    region_eval_full record shape; shard files may be passed as multiple
    paths) -- source of the per-instance FILE / LINE / line-fraction values,
  - its scorer report JSON (agentless_metric_v4 / _verified / _full output)
    -- source of the per-instance FUNCTION-exact values (the
    `all_instances.function.detail` array; an instance absent from the
    detail array was an engine error or git_show failure and counts as
    WRONG, matching the errors-count-as-wrong-at-all-levels/v1 convention).

Per-instance metric definitions (identical to the scorers'):
  FILE      1 iff `all_gold_files_retrieved` (errors -> 0)
  FUNCTION  1 iff the scorer's function detail entry says correct (missing -> 0)
  LINE      1 iff `hunk_line_recall == 1.0` (errors -> 0)
  fraction  `hunk_line_recall` as a float (errors -> 0.0; same denominator)

For each metric this script reports, on the paired per-instance values:
  - delta = mean(B) - mean(A) (percentage points for the binary metrics),
  - a paired bootstrap 95% CI on the delta: resample the n instances with
    replacement (both arms' values move together -- that is what makes it
    paired), percentile interval over --n-boot resamples, seeded and
    deterministic,
  - for the binary metrics, McNemar's EXACT two-sided p on the discordant
    pair counts (n01 = A wrong & B correct, n10 = A correct & B wrong):
    p = min(1, 2 * P(X <= min(n01, n10))) with X ~ Binomial(n01 + n10, 1/2);
    p = 1.0 when there are no discordant pairs.

Usage:
    python lab/stats/paired_tests.py \\
        --a-predictions lab/results_regions/full300_v10.jsonl \\
        --a-metric lab/results_regions/agentless_metric_v4.json --label-a v10 \\
        --b-predictions lab/results_regions/full300_v11.jsonl \\
        --b-metric lab/results_regions/agentless_metric_v11.json --label-b v11 \\
        --out lab/stats/v10_vs_v11.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

DEFAULT_N_BOOT = 10_000
DEFAULT_SEED = 20260718
METRICS = ("file", "function", "line", "fraction")
BINARY_METRICS = ("file", "function", "line")


# ---------------------------------------------------------------------------
# statistics primitives (unit-tested against known answers)
# ---------------------------------------------------------------------------


def mcnemar_exact_p(n01: int, n10: int) -> float:
    """Exact two-sided McNemar p from the discordant counts. n01 and n10 are
    the two off-diagonal cells (which is which does not matter). Returns 1.0
    when there are no discordant pairs."""
    if n01 < 0 or n10 < 0:
        raise ValueError("discordant counts must be non-negative")
    m = n01 + n10
    if m == 0:
        return 1.0
    k = min(n01, n10)
    tail = sum(math.comb(m, i) for i in range(k + 1)) / 2.0 ** m
    return min(1.0, 2.0 * tail)


def paired_bootstrap_ci(a: list[float], b: list[float], n_boot: int = DEFAULT_N_BOOT,
                        seed: int = DEFAULT_SEED) -> tuple[float, float, float]:
    """Paired bootstrap percentile 95% CI on mean(b) - mean(a).

    Resamples INSTANCES (index pairs), so each resample keeps a_i and b_i
    together. Returns (delta, ci_lo, ci_hi). Deterministic for a given seed."""
    if len(a) != len(b) or not a:
        raise ValueError("a and b must be equal-length, non-empty")
    n = len(a)
    diffs = [bv - av for av, bv in zip(a, b)]
    delta = statistics.mean(diffs)
    rng = random.Random(seed)
    boot = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += diffs[rng.randrange(n)]
        boot.append(s / n)
    boot.sort()
    lo = boot[int(round(0.025 * (n_boot - 1)))]
    hi = boot[int(round(0.975 * (n_boot - 1)))]
    return delta, lo, hi


# ---------------------------------------------------------------------------
# per-instance metric extraction
# ---------------------------------------------------------------------------


def load_predictions(paths: list[Path]) -> dict[str, dict]:
    recs: dict[str, dict] = {}
    for p in paths:
        with p.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                iid = r["instance_id"]
                if iid in recs:
                    raise SystemExit(f"duplicate instance_id {iid!r} in {p}")
                recs[iid] = r
    if not recs:
        raise SystemExit(f"no records loaded from {[str(p) for p in paths]}")
    return recs


def load_function_detail(metric_path: Path) -> dict[str, bool]:
    report = json.loads(metric_path.read_text())
    detail = report["all_instances"]["function"]["detail"]
    return {d["instance_id"]: bool(d["correct"]) for d in detail}


def per_instance_metrics(predictions: dict[str, dict],
                          function_detail: dict[str, bool]) -> dict[str, dict[str, float]]:
    """{instance_id: {file: 0/1, function: 0/1, line: 0/1, fraction: float}}"""
    out: dict[str, dict[str, float]] = {}
    for iid, r in predictions.items():
        frac = r.get("hunk_line_recall")
        out[iid] = {
            "file": 1.0 if r.get("all_gold_files_retrieved", False) else 0.0,
            "function": 1.0 if function_detail.get(iid, False) else 0.0,
            "line": 1.0 if frac == 1.0 else 0.0,
            "fraction": float(frac) if frac is not None else 0.0,
        }
    return out


# ---------------------------------------------------------------------------
# run comparison
# ---------------------------------------------------------------------------


def compare_runs(metrics_a: dict[str, dict[str, float]],
                 metrics_b: dict[str, dict[str, float]],
                 n_boot: int = DEFAULT_N_BOOT, seed: int = DEFAULT_SEED) -> dict:
    ids_a, ids_b = set(metrics_a), set(metrics_b)
    if ids_a != ids_b:
        only_a = sorted(ids_a - ids_b)[:3]
        only_b = sorted(ids_b - ids_a)[:3]
        raise SystemExit(f"instance sets differ (|A|={len(ids_a)}, |B|={len(ids_b)}); "
                         f"paired tests need identical sets. only-in-A e.g. {only_a}, "
                         f"only-in-B e.g. {only_b}")
    ids = sorted(ids_a)
    n = len(ids)

    out: dict = {"n": n, "n_boot": n_boot, "seed": seed, "metrics": {}}
    for m in METRICS:
        a = [metrics_a[i][m] for i in ids]
        b = [metrics_b[i][m] for i in ids]
        delta, lo, hi = paired_bootstrap_ci(a, b, n_boot=n_boot, seed=seed)
        scale = 100.0 if m in BINARY_METRICS else 1.0
        rec = {
            "mean_a": round(statistics.mean(a) * scale, 4),
            "mean_b": round(statistics.mean(b) * scale, 4),
            "delta": round(delta * scale, 4),
            "ci95": [round(lo * scale, 4), round(hi * scale, 4)],
            "units": "percentage points" if m in BINARY_METRICS else "fraction",
        }
        if m in BINARY_METRICS:
            n01 = sum(1 for i in ids if metrics_a[i][m] == 0.0 and metrics_b[i][m] == 1.0)
            n10 = sum(1 for i in ids if metrics_a[i][m] == 1.0 and metrics_b[i][m] == 0.0)
            rec["mcnemar"] = {"n01_a_wrong_b_correct": n01,
                              "n10_a_correct_b_wrong": n10,
                              "p_exact_two_sided": mcnemar_exact_p(n01, n10)}
        out["metrics"][m] = rec
    return out


def print_table(report: dict, label_a: str, label_b: str) -> None:
    print(f"\npaired tests: {label_b} - {label_a}  (n={report['n']}, "
          f"n_boot={report['n_boot']}, seed={report['seed']})")
    print(f"{'metric':10} {label_a:>9} {label_b:>9} {'delta':>8} {'95% CI':>20} {'McNemar p':>12}")
    for m in METRICS:
        r = report["metrics"][m]
        ci = f"[{r['ci95'][0]:+.2f}, {r['ci95'][1]:+.2f}]"
        p = f"{r['mcnemar']['p_exact_two_sided']:.2e}" if "mcnemar" in r else "-"
        print(f"{m:10} {r['mean_a']:9.2f} {r['mean_b']:9.2f} {r['delta']:+8.2f} {ci:>20} {p:>12}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a-predictions", type=Path, nargs="+", required=True)
    ap.add_argument("--a-metric", type=Path, required=True)
    ap.add_argument("--b-predictions", type=Path, nargs="+", required=True)
    ap.add_argument("--b-metric", type=Path, required=True)
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    ap.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out", type=Path, default=None, help="write the report JSON here")
    args = ap.parse_args()

    ma = per_instance_metrics(load_predictions(args.a_predictions),
                               load_function_detail(args.a_metric))
    mb = per_instance_metrics(load_predictions(args.b_predictions),
                               load_function_detail(args.b_metric))
    report = compare_runs(ma, mb, n_boot=args.n_boot, seed=args.seed)
    report["source"] = {
        "a": {"label": args.label_a,
              "predictions": [str(p) for p in args.a_predictions],
              "metric": str(args.a_metric)},
        "b": {"label": args.label_b,
              "predictions": [str(p) for p in args.b_predictions],
              "metric": str(args.b_metric)},
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2))
        print(f"wrote {args.out}", file=sys.stderr)
    print_table(report, args.label_a, args.label_b)


if __name__ == "__main__":
    main()
