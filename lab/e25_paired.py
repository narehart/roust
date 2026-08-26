"""E25 paired analysis: default vs --shape-blocks, per language slice.

Consumes the two prediction JSONLs (FILE / LINE / line-fraction, per
instance) plus the two agentless_metric_full JSONs (FUNCTION exact, per
instance, from `all_instances.function.detail`) and emits:

  * the headline row: FILE %, FUNCTION exact %, LINE all-or-nothing %,
    line mean-fraction -- recomputed from the records, and cross-checked
    against the metric JSON's own headline so a mismatch is loud;
  * paired significance: exact McNemar (binomial, two-sided) on each of
    the three all-or-nothing metrics, and Wilcoxon signed-rank on the
    per-instance line fraction;
  * itemization of EVERY instance whose FILE, FUNCTION, LINE or fraction
    changed, with the direction of each change.

Metric convention matches lab/agentless_metric_full.py: engine errors
count as WRONG at every all-or-nothing level (denominator = all records),
while the line mean-fraction divides by the non-error count.

Usage:
  uv run --no-project --with pandas --with scipy python lab/e25_paired.py \
      --label jsts --def-jsonl A.jsonl --shape-jsonl B.jsonl \
      --def-metric A.json --shape-metric B.json --out-prefix DIR/jsts
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scipy import stats


def load_records(jsonl: Path) -> dict[str, dict]:
    out = {}
    for line in Path(jsonl).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out[r["instance_id"]] = r
    return out


def load_function_detail(metric: Path) -> dict[str, bool]:
    d = json.loads(Path(metric).read_text())
    return {row["instance_id"]: bool(row["correct"])
            for row in d["all_instances"]["function"]["detail"]}


def headline(recs: dict[str, dict], func: dict[str, bool]) -> dict:
    ids = sorted(recs)
    n = len(ids)
    n_err = sum(1 for i in ids if recs[i].get("error"))
    file_ok = sum(1 for i in ids if (recs[i].get("hunk_file_covered") or 0) == 1.0)
    # Errors are absent from the function detail list and count as wrong.
    func_ok = sum(1 for i in ids if func.get(i, False))
    line_ok = sum(1 for i in ids if (recs[i].get("hunk_line_recall") or 0) == 1.0)
    frac_sum = sum((recs[i].get("hunk_line_recall") or 0) for i in ids)
    denom = n - n_err if n - n_err else 1
    return {"n": n, "n_errors": n_err,
            "file_pct": round(100 * file_ok / n, 2), "file_n": file_ok,
            "function_pct": round(100 * func_ok / n, 2), "function_n": func_ok,
            "line_pct": round(100 * line_ok / n, 2), "line_n": line_ok,
            "mean_fraction": frac_sum / denom}


def mcnemar_exact(pairs: list[tuple[bool, bool]]) -> dict:
    """Exact (binomial) McNemar on paired booleans (default, shape)."""
    b = sum(1 for d, s in pairs if d and not s)   # default-only wins
    c = sum(1 for d, s in pairs if s and not d)   # shape-only wins
    if b + c == 0:
        return {"b_def_only": 0, "c_shape_only": 0, "p": 1.0, "note": "no discordant pairs"}
    p = stats.binomtest(c, b + c, 0.5, alternative="two-sided").pvalue
    return {"b_def_only": b, "c_shape_only": c, "p": p}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--def-jsonl", required=True)
    ap.add_argument("--shape-jsonl", required=True)
    ap.add_argument("--def-metric", required=True)
    ap.add_argument("--shape-metric", required=True)
    ap.add_argument("--out-prefix", required=True)
    args = ap.parse_args()

    d_recs, s_recs = load_records(args.def_jsonl), load_records(args.shape_jsonl)
    d_func, s_func = load_function_detail(args.def_metric), load_function_detail(args.shape_metric)

    ids = sorted(set(d_recs) & set(s_recs))
    only_d, only_s = sorted(set(d_recs) - set(s_recs)), sorted(set(s_recs) - set(d_recs))
    if only_d or only_s:
        print(f"WARNING: instance-set mismatch -- default-only={len(only_d)} "
              f"shape-only={len(only_s)}; paired stats use the {len(ids)} common ids")

    dh, sh = headline(d_recs, d_func), headline(s_recs, s_func)

    # Cross-check the recomputed headline against each metric JSON's own.
    for tag, metric_path, h in (("default", args.def_metric, dh),
                                ("shape", args.shape_metric, sh)):
        a = json.loads(Path(metric_path).read_text())["all_instances"]
        checks = [("FILE", a["file"]["pct_correct"], h["file_pct"]),
                  ("FUNCTION", a["function"]["pct_correct"], h["function_pct"]),
                  ("LINE", a["line"]["pct_correct_all_or_nothing"], h["line_pct"]),
                  ("frac", round(a["line"]["mean_fraction_covered"], 6),
                   round(h["mean_fraction"], 6))]
        for name, want, got in checks:
            if want != got:
                print(f"CROSSCHECK MISMATCH [{tag}] {name}: metric_json={want} recomputed={got}")

    print(f"\n=== {args.label} ===")
    print(f"{'arm':8} {'n':>5} {'err':>4} {'FILE':>16} {'FUNCTION':>16} "
          f"{'LINE':>16} {'frac':>9}")
    for tag, h in (("default", dh), ("shape", sh)):
        print(f"{tag:8} {h['n']:5d} {h['n_errors']:4d} "
              f"{h['file_pct']:8.2f} ({h['file_n']:3d}) "
              f"{h['function_pct']:8.2f} ({h['function_n']:3d}) "
              f"{h['line_pct']:8.2f} ({h['line_n']:3d}) "
              f"{h['mean_fraction']:9.5f}")
    print(f"{'delta':8} {'':5} {'':4} "
          f"{sh['file_pct'] - dh['file_pct']:+8.2f} {'':5} "
          f"{sh['function_pct'] - dh['function_pct']:+8.2f} {'':5} "
          f"{sh['line_pct'] - dh['line_pct']:+8.2f} {'':5} "
          f"{sh['mean_fraction'] - dh['mean_fraction']:+9.5f}")

    # ---- paired significance -------------------------------------------
    stats_out = {}
    for name, getter in (
            ("FILE", lambda i, r, _f: (r[i].get("hunk_file_covered") or 0) == 1.0),
            ("FUNCTION", lambda i, _r, f: f.get(i, False)),
            ("LINE", lambda i, r, _f: (r[i].get("hunk_line_recall") or 0) == 1.0)):
        pairs = [(getter(i, d_recs, d_func), getter(i, s_recs, s_func)) for i in ids]
        stats_out[name] = mcnemar_exact(pairs)
        m = stats_out[name]
        print(f"McNemar {name:9} default-only={m['b_def_only']:3d} "
              f"shape-only={m['c_shape_only']:3d} p={m['p']:.4f}")

    d_frac = [d_recs[i].get("hunk_line_recall") or 0 for i in ids]
    s_frac = [s_recs[i].get("hunk_line_recall") or 0 for i in ids]
    diffs = [s - d for s, d in zip(s_frac, d_frac)]
    nz = [x for x in diffs if x != 0]
    if nz:
        w = stats.wilcoxon(nz, alternative="two-sided")
        stats_out["fraction_wilcoxon"] = {"n_nonzero": len(nz), "statistic": float(w.statistic),
                                          "p": float(w.pvalue),
                                          "n_up": sum(1 for x in nz if x > 0),
                                          "n_down": sum(1 for x in nz if x < 0)}
        print(f"Wilcoxon frac    n_nonzero={len(nz)} up={stats_out['fraction_wilcoxon']['n_up']} "
              f"down={stats_out['fraction_wilcoxon']['n_down']} p={w.pvalue:.4f}")
    else:
        stats_out["fraction_wilcoxon"] = {"n_nonzero": 0, "p": 1.0, "note": "no changed fractions"}
        print("Wilcoxon frac    no instance changed its line fraction")

    # ---- itemization ----------------------------------------------------
    changed = []
    for i in ids:
        d, s = d_recs[i], s_recs[i]
        df = (d.get("hunk_file_covered") or 0) == 1.0
        sf = (s.get("hunk_file_covered") or 0) == 1.0
        dfn, sfn = d_func.get(i, False), s_func.get(i, False)
        dl = d.get("hunk_line_recall") or 0
        sl = s.get("hunk_line_recall") or 0
        if df == sf and dfn == sfn and dl == sl:
            continue
        changed.append({
            "instance_id": i, "repo": d.get("repo"),
            "file": f"{int(df)}->{int(sf)}" if df != sf else "=",
            "function": f"{int(dfn)}->{int(sfn)}" if dfn != sfn else "=",
            "line_allornothing": (f"{int(dl == 1.0)}->{int(sl == 1.0)}"
                                  if (dl == 1.0) != (sl == 1.0) else "="),
            "fraction": f"{dl:.4f}->{sl:.4f}" if dl != sl else "=",
            "fraction_delta": round(sl - dl, 6),
        })
    changed.sort(key=lambda r: r["fraction_delta"])
    print(f"\nchanged instances: {len(changed)} of {len(ids)}")
    for r in changed:
        print(f"  {r['instance_id']:42} FILE {r['file']:6} FUNC {r['function']:6} "
              f"LINE {r['line_allornothing']:6} frac {r['fraction']:20} "
              f"({r['fraction_delta']:+.4f})")

    out = {"label": args.label, "default": dh, "shape": sh,
           "delta": {"file": round(sh["file_pct"] - dh["file_pct"], 2),
                     "function": round(sh["function_pct"] - dh["function_pct"], 2),
                     "line": round(sh["line_pct"] - dh["line_pct"], 2),
                     "mean_fraction": round(sh["mean_fraction"] - dh["mean_fraction"], 6)},
           "paired_stats": stats_out,
           "n_changed": len(changed), "changed": changed,
           "instance_set_mismatch": {"default_only": only_d, "shape_only": only_s}}
    Path(f"{args.out_prefix}_paired.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {args.out_prefix}_paired.json")


if __name__ == "__main__":
    main()
