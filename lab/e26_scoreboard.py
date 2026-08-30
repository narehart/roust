#!/usr/bin/env python3
"""E26 goal scoreboard: per-language FILE/FUNCTION/LINE stratified by the
number of gold files an instance has (1 / 2 / 3+).

Why stratify. "Get every language to Python-level measurements" is not one
number. A 1-gold-file instance and a 12-gold-file instance are different
retrieval problems, and the aggregate per-language gap is dominated by how
the slices differ in that mix, not only by how well the engine ranks. Split
that way, several non-Python slices already match or beat Python Lite on the
single-file stratum, and the deficit concentrates in the multi-file strata --
which says the remaining distance is a RANKING/BUDGET problem, not a
coverage problem, everywhere the coverage hole has already been closed.

Metric convention matches lab/agentless_metric_full.py and lab/e26_paired.py:
engine errors count as WRONG at every all-or-nothing level (denominator = all
records in the stratum); the line mean-fraction divides by the non-error count.

Usage:
  e26_scoreboard.py --arm LABEL:JSONL:METRIC_JSON [--arm ...] --out OUT.json
"""
from __future__ import annotations
import argparse, json
from pathlib import Path


def load_records(p: Path) -> dict[str, dict]:
    out = {}
    for line in Path(p).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["instance_id"]] = r
    return out


def load_function_detail(p: Path) -> dict[str, bool]:
    d = json.loads(Path(p).read_text())
    return {r["instance_id"]: bool(r["correct"])
            for r in d["all_instances"]["function"]["detail"]}


def headline(recs, func, ids):
    n = len(ids)
    if n == 0:
        return {"n": 0, "file_pct": None, "function_pct": None,
                "line_pct": None, "mean_fraction": None}
    n_err = sum(1 for i in ids if recs[i].get("error"))
    f = sum(1 for i in ids if (recs[i].get("hunk_file_covered") or 0) == 1.0)
    fn = sum(1 for i in ids if func.get(i, False))
    l = sum(1 for i in ids if (recs[i].get("hunk_line_recall") or 0) == 1.0)
    frac = sum((recs[i].get("hunk_line_recall") or 0) for i in ids)
    return {"n": n, "n_errors": n_err,
            "file_pct": round(100 * f / n, 2), "file_n": f,
            "function_pct": round(100 * fn / n, 2), "function_n": fn,
            "line_pct": round(100 * l / n, 2), "line_n": l,
            "mean_fraction": round(frac / ((n - n_err) or 1), 5)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True,
                    help="LABEL:PREDICTIONS_JSONL:METRIC_JSON")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    res = {}
    for spec in a.arm:
        label, jsonl, metric = spec.split(":", 2)
        recs = load_records(Path(jsonl))
        func = load_function_detail(Path(metric))
        ids = sorted(recs)

        def bucket(i):
            n = recs[i].get("n_gold_files") or 1
            return "1" if n <= 1 else ("2" if n == 2 else "3+")

        res[label] = {"all": headline(recs, func, ids),
                      "strata": {b: headline(recs, func, [i for i in ids if bucket(i) == b])
                                 for b in ("1", "2", "3+")},
                      "sources": {"predictions": jsonl, "metric": metric}}

    hdr = f"{'slice':<16}{'stratum':>8}{'n':>6}{'FILE':>9}{'FUNCTION':>10}{'LINE':>8}{'frac':>10}"
    print(hdr); print("-" * len(hdr))
    for label, d in res.items():
        for stratum in ("all", "1", "2", "3+"):
            h = d["all"] if stratum == "all" else d["strata"][stratum]
            if not h["n"]:
                print(f"{label:<16}{stratum:>8}{0:>6}{'--':>9}{'--':>10}{'--':>8}{'--':>10}")
                continue
            print(f"{label:<16}{stratum:>8}{h['n']:>6}{h['file_pct']:>9.2f}"
                  f"{h['function_pct']:>10.2f}{h['line_pct']:>8.2f}{h['mean_fraction']:>10.5f}")
        print()
    a.out.write_text(json.dumps(res, indent=1))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
