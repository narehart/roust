#!/usr/bin/env python3
"""E26 paired analysis: default vs --ext-v2, per language slice.

Structure and metric conventions are lab/e25_paired.py's (engine errors count
as WRONG at every all-or-nothing level, denominator = all records; the line
mean-fraction divides by the non-error count), with three E26 additions:

  * STRATIFICATION by gold-file count (1 / 2 / 3+). "Python-level" is not one
    number: single-gold-file instances and many-gold-file instances are
    different problems, and the per-language gap lives almost entirely in the
    latter. Both arms are reported in every stratum.
  * CEILING RECOVERY. Of the gold files carrying an EXT_V2 suffix -- which the
    default arm cannot retrieve at ANY rank, because the file is never indexed
    -- how many does the flagged arm actually return? This is the number the
    experiment exists to move, and it is bounded above by the census.
  * DISPLACEMENT accounting. Gold files WITHOUT an EXT_V2 suffix that the
    default arm retrieved and the flagged arm lost: the cost side, i.e. real
    source displaced out of the budget by the newly admitted files.

Usage:
  uv run --no-project --with pandas --with pyarrow --with scipy python \\
     lab/e26_paired.py --label c --parquet lab/mswe_c.parquet \\
     --def-jsonl A.jsonl --ext-jsonl B.jsonl \\
     --def-metric A.json --ext-metric B.json --out-prefix DIR/c
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from scipy import stats

EXT_V2 = (".rb", ".pony", ".svelte", ".mjs", ".cjs", ".cts", ".mts", ".vue", ".scala", ".php")
GOLD_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.M)


def load_records(jsonl: Path) -> dict[str, dict]:
    out = {}
    for line in Path(jsonl).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["instance_id"]] = r
    return out


def load_function_detail(metric: Path) -> dict[str, bool]:
    d = json.loads(Path(metric).read_text())
    return {row["instance_id"]: bool(row["correct"])
            for row in d["all_instances"]["function"]["detail"]}


def load_gold(parquet: Path) -> dict[str, list[str]]:
    import pandas as pd
    df = pd.read_parquet(parquet)
    return {r["instance_id"]: sorted({m.group(2) for m in GOLD_RE.finditer(r["patch"] or "")})
            for _, r in df.iterrows()}


def headline(recs: dict[str, dict], func: dict[str, bool], ids: list[str]) -> dict:
    n = len(ids)
    if n == 0:
        return {"n": 0, "n_errors": 0, "file_pct": 0.0, "file_n": 0, "function_pct": 0.0,
                "function_n": 0, "line_pct": 0.0, "line_n": 0, "mean_fraction": 0.0}
    n_err = sum(1 for i in ids if recs[i].get("error"))
    file_ok = sum(1 for i in ids if (recs[i].get("hunk_file_covered") or 0) == 1.0)
    func_ok = sum(1 for i in ids if func.get(i, False))
    line_ok = sum(1 for i in ids if (recs[i].get("hunk_line_recall") or 0) == 1.0)
    frac_sum = sum((recs[i].get("hunk_line_recall") or 0) for i in ids)
    denom = (n - n_err) or 1
    return {"n": n, "n_errors": n_err,
            "file_pct": round(100 * file_ok / n, 2), "file_n": file_ok,
            "function_pct": round(100 * func_ok / n, 2), "function_n": func_ok,
            "line_pct": round(100 * line_ok / n, 2), "line_n": line_ok,
            "mean_fraction": frac_sum / denom}


def mcnemar_exact(pairs: list[tuple[bool, bool]]) -> dict:
    b = sum(1 for d, e in pairs if d and not e)   # default-only wins
    c = sum(1 for d, e in pairs if e and not d)   # ext-only wins
    if b + c == 0:
        return {"b_def_only": 0, "c_ext_only": 0, "p": 1.0, "note": "no discordant pairs"}
    return {"b_def_only": b, "c_ext_only": c,
            "p": float(stats.binomtest(c, b + c, 0.5, alternative="two-sided").pvalue)}


def main() -> None:
    ap = argparse.ArgumentParser()
    for a in ("--label", "--parquet", "--def-jsonl", "--ext-jsonl",
              "--def-metric", "--ext-metric", "--out-prefix"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()

    d_recs, e_recs = load_records(Path(args.def_jsonl)), load_records(Path(args.ext_jsonl))
    d_func = load_function_detail(Path(args.def_metric))
    e_func = load_function_detail(Path(args.ext_metric))
    gold = load_gold(Path(args.parquet))

    ids = sorted(set(d_recs) & set(e_recs))
    only_d, only_e = sorted(set(d_recs) - set(e_recs)), sorted(set(e_recs) - set(d_recs))
    if only_d or only_e:
        print(f"WARNING: instance-set mismatch -- default-only={len(only_d)} "
              f"ext-only={len(only_e)}; paired stats use the {len(ids)} common ids")

    dh, eh = headline(d_recs, d_func, ids), headline(e_recs, e_func, ids)

    for tag, metric_path in (("default", args.def_metric), ("ext-v2", args.ext_metric)):
        a = json.loads(Path(metric_path).read_text())["all_instances"]
        h = dh if tag == "default" else eh
        if len(ids) == len(d_recs) == len(e_recs):
            for name, want, got in (("FILE", a["file"]["pct_correct"], h["file_pct"]),
                                    ("FUNCTION", a["function"]["pct_correct"], h["function_pct"]),
                                    ("LINE", a["line"]["pct_correct_all_or_nothing"], h["line_pct"]),
                                    ("frac", round(a["line"]["mean_fraction_covered"], 6),
                                     round(h["mean_fraction"], 6))):
                if want != got:
                    print(f"CROSSCHECK MISMATCH [{tag}] {name}: metric_json={want} recomputed={got}")

    print(f"\n=== {args.label} (n={len(ids)}) ===")
    print(f"{'arm':9} {'err':>4} {'FILE':>16} {'FUNCTION':>16} {'LINE':>16} {'frac':>10}")
    for tag, h in (("default", dh), ("ext-v2", eh)):
        print(f"{tag:9} {h['n_errors']:4d} {h['file_pct']:9.2f} ({h['file_n']:3d}) "
              f"{h['function_pct']:9.2f} ({h['function_n']:3d}) "
              f"{h['line_pct']:9.2f} ({h['line_n']:3d}) {h['mean_fraction']:10.5f}")
    print(f"{'delta':9} {'':4} {eh['file_pct']-dh['file_pct']:+9.2f} {'':5} "
          f"{eh['function_pct']-dh['function_pct']:+9.2f} {'':5} "
          f"{eh['line_pct']-dh['line_pct']:+9.2f} {'':5} "
          f"{eh['mean_fraction']-dh['mean_fraction']:+10.5f}")

    # ---- paired significance ------------------------------------------
    stats_out = {}
    for name, get in (("FILE", lambda i, r, _f: (r[i].get("hunk_file_covered") or 0) == 1.0),
                      ("FUNCTION", lambda i, _r, f: f.get(i, False)),
                      ("LINE", lambda i, r, _f: (r[i].get("hunk_line_recall") or 0) == 1.0)):
        pairs = [(get(i, d_recs, d_func), get(i, e_recs, e_func)) for i in ids]
        m = stats_out[name] = mcnemar_exact(pairs)
        print(f"McNemar {name:9} default-only={m['b_def_only']:3d} "
              f"ext-only={m['c_ext_only']:3d} p={m['p']:.4f}")

    diffs = [(e_recs[i].get("hunk_line_recall") or 0) - (d_recs[i].get("hunk_line_recall") or 0)
             for i in ids]
    nz = [x for x in diffs if x != 0]
    if nz:
        w = stats.wilcoxon(nz, alternative="two-sided")
        stats_out["fraction_wilcoxon"] = {"n_nonzero": len(nz), "statistic": float(w.statistic),
                                          "p": float(w.pvalue),
                                          "n_up": sum(1 for x in nz if x > 0),
                                          "n_down": sum(1 for x in nz if x < 0)}
        print(f"Wilcoxon frac    n_nonzero={len(nz)} "
              f"up={stats_out['fraction_wilcoxon']['n_up']} "
              f"down={stats_out['fraction_wilcoxon']['n_down']} p={w.pvalue:.4f}")
    else:
        stats_out["fraction_wilcoxon"] = {"n_nonzero": 0, "p": 1.0, "note": "no changed fractions"}
        print("Wilcoxon frac    no instance changed its line fraction")

    # ---- stratification by gold-file count ----------------------------
    def bucket(i: str) -> str:
        # Same rule as lab/e26_scoreboard.py so the two artifacts can never
        # disagree: an errored record carries n_gold_files=0 (the harness
        # never parsed its hunks) and falls in stratum 1. It is counted WRONG
        # at every level regardless, so the placement does not flatter any arm.
        n = d_recs[i].get("n_gold_files") or 1
        return "1" if n <= 1 else ("2" if n == 2 else "3+")

    strata = {}
    print(f"\n{'stratum':8} {'n':>5} {'arm':9} {'FILE':>8} {'FUNCTION':>9} "
          f"{'LINE':>8} {'frac':>9}")
    for b in ("1", "2", "3+"):
        sub = [i for i in ids if bucket(i) == b]
        sd, se = headline(d_recs, d_func, sub), headline(e_recs, e_func, sub)
        strata[b] = {"default": sd, "ext_v2": se}
        for tag, h in (("default", sd), ("ext-v2", se)):
            print(f"{b:8} {len(sub):5d} {tag:9} {h['file_pct']:8.2f} {h['function_pct']:9.2f} "
                  f"{h['line_pct']:8.2f} {h['mean_fraction']:9.5f}")

    # ---- ceiling recovery + displacement ------------------------------
    ceil = {"ext_gold_files": 0, "ext_gold_retrieved_default": 0, "ext_gold_retrieved_ext": 0,
            "instances_with_ext_gold": 0, "detail": []}
    disp = {"nonext_gold_lost": 0, "nonext_gold_gained": 0, "detail": []}
    for i in ids:
        gfs = gold.get(i, [])
        d_have = set((d_recs[i].get("regions") or {}).keys())
        e_have = set((e_recs[i].get("regions") or {}).keys())
        ext_gold = [f for f in gfs if f.endswith(EXT_V2)]
        if ext_gold:
            ceil["instances_with_ext_gold"] += 1
            ceil["ext_gold_files"] += len(ext_gold)
            dr = [f for f in ext_gold if f in d_have]
            er = [f for f in ext_gold if f in e_have]
            ceil["ext_gold_retrieved_default"] += len(dr)
            ceil["ext_gold_retrieved_ext"] += len(er)
            ceil["detail"].append({"instance_id": i, "ext_gold": ext_gold,
                                    "retrieved_default": dr, "retrieved_ext": er,
                                    "n_gold": len(gfs)})
        nonext = [f for f in gfs if not f.endswith(EXT_V2)]
        lost = [f for f in nonext if f in d_have and f not in e_have]
        gained = [f for f in nonext if f not in d_have and f in e_have]
        disp["nonext_gold_lost"] += len(lost)
        disp["nonext_gold_gained"] += len(gained)
        if lost or gained:
            disp["detail"].append({"instance_id": i, "lost": lost, "gained": gained})
    print(f"\nceiling: {ceil['ext_gold_files']} EXT_V2 gold files in "
          f"{ceil['instances_with_ext_gold']} instances -- "
          f"default retrieved {ceil['ext_gold_retrieved_default']}, "
          f"ext-v2 retrieved {ceil['ext_gold_retrieved_ext']}")
    print(f"displacement: non-EXT_V2 gold files lost={disp['nonext_gold_lost']} "
          f"gained={disp['nonext_gold_gained']}")

    # ---- itemization ---------------------------------------------------
    changed = []
    for i in ids:
        d, e = d_recs[i], e_recs[i]
        df = (d.get("hunk_file_covered") or 0) == 1.0
        ef = (e.get("hunk_file_covered") or 0) == 1.0
        dfn, efn = d_func.get(i, False), e_func.get(i, False)
        dl, el = d.get("hunk_line_recall") or 0, e.get("hunk_line_recall") or 0
        if df == ef and dfn == efn and dl == el:
            continue
        changed.append({"instance_id": i, "repo": d.get("repo"),
                        "n_gold": d.get("n_gold_files"),
                        "file": f"{int(df)}->{int(ef)}" if df != ef else "=",
                        "function": f"{int(dfn)}->{int(efn)}" if dfn != efn else "=",
                        "line_allornothing": (f"{int(dl==1.0)}->{int(el==1.0)}"
                                              if (dl == 1.0) != (el == 1.0) else "="),
                        "fraction": f"{dl:.4f}->{el:.4f}" if dl != el else "=",
                        "fraction_delta": round(el - dl, 6)})
    changed.sort(key=lambda r: r["fraction_delta"])
    print(f"\nchanged instances: {len(changed)} of {len(ids)}")
    for r in changed:
        print(f"  {r['instance_id']:42} gold={str(r['n_gold']):>3} FILE {r['file']:6} "
              f"FUNC {r['function']:6} LINE {r['line_allornothing']:6} "
              f"frac {r['fraction']:20} ({r['fraction_delta']:+.4f})")

    Path(f"{args.out_prefix}_paired.json").write_text(json.dumps(
        {"label": args.label, "n": len(ids), "default": dh, "ext_v2": eh,
         "delta": {"file": round(eh["file_pct"] - dh["file_pct"], 2),
                   "function": round(eh["function_pct"] - dh["function_pct"], 2),
                   "line": round(eh["line_pct"] - dh["line_pct"], 2),
                   "mean_fraction": round(eh["mean_fraction"] - dh["mean_fraction"], 6)},
         "paired_stats": stats_out, "strata": strata,
         "ceiling": ceil, "displacement": disp,
         "n_changed": len(changed), "changed": changed,
         "instance_set_mismatch": {"default_only": only_d, "ext_only": only_e}}, indent=1))
    print(f"wrote {args.out_prefix}_paired.json")


if __name__ == "__main__":
    main()
