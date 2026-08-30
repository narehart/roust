"""E28 paired analysis: default vs --max-additions N, per slice.

Adapted from lab/e27_paired.py (same metric convention, same exact-McNemar +
Wilcoxon machinery, same stratified-by-gold-file-count breakdown), with the
one addition this round is actually about: the COST columns.

E28 is explicitly a trade, not a free win. Raising the pool breadth cap admits
more candidates under a FIXED 8192-token budget, so the same budget is spread
across more files. Reporting FILE/FUNCTION/LINE without reporting mean files
returned and mean bundle tokens would hide the entire mechanism -- and
wave-5's Recall Trap finding (arXiv:2608.14838) says a higher-recall config
under a fixed budget measurably HURT the downstream agent. So `files` and
`tokens` are first-class columns here, slice-wide and per stratum.

Usage:
  uv run --no-project --with pandas --with scipy python lab/e28_paired.py \
      --label jsts_m24 --def-jsonl A.jsonl --arm-jsonl B.jsonl \
      --def-metric A.json --arm-metric B.json --out-prefix DIR/jsts_m24
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scipy import stats

STRATA = ("1", "2", "3+")


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


def stratum_of(rec: dict) -> str:
    """Gold-file-count stratum. Mirrors the E26 scoreboard's 1 / 2 / 3+ split."""
    n = int(rec.get("n_gold_files") or 0)
    if n <= 1:
        return "1"
    if n == 2:
        return "2"
    return "3+"


def headline(recs: dict[str, dict], func: dict[str, bool],
             ids: list[str] | None = None) -> dict:
    ids = sorted(recs) if ids is None else sorted(ids)
    n = len(ids)
    if n == 0:
        return {"n": 0, "n_errors": 0, "file_pct": 0.0, "file_n": 0,
                "function_pct": 0.0, "function_n": 0, "line_pct": 0.0,
                "line_n": 0, "mean_fraction": 0.0,
                "mean_files": 0.0, "mean_tokens": 0.0}
    n_err = sum(1 for i in ids if recs[i].get("error"))
    file_ok = sum(1 for i in ids if (recs[i].get("hunk_file_covered") or 0) == 1.0)
    # Errors are absent from the function detail list and count as wrong.
    func_ok = sum(1 for i in ids if func.get(i, False))
    line_ok = sum(1 for i in ids if (recs[i].get("hunk_line_recall") or 0) == 1.0)
    frac_sum = sum((recs[i].get("hunk_line_recall") or 0) for i in ids)
    denom = n - n_err if n - n_err else 1
    # COST columns. Averaged over the OK records only (an errored record has
    # no bundle at all, so folding a 0 into the mean would understate the very
    # cost this round exists to measure). len(regions) is the number of files
    # the bundle actually returns; tokens is stats.bundle_tokens.
    ok_ids = [i for i in ids if not recs[i].get("error")]
    files_list = [len(recs[i].get("regions") or {}) for i in ok_ids]
    tok_list = [recs[i].get("tokens") or 0 for i in ok_ids]
    mean_files = (sum(files_list) / len(files_list)) if files_list else 0.0
    mean_tokens = (sum(tok_list) / len(tok_list)) if tok_list else 0.0
    return {"n": n, "n_errors": n_err,
            "file_pct": round(100 * file_ok / n, 2), "file_n": file_ok,
            "function_pct": round(100 * func_ok / n, 2), "function_n": func_ok,
            "line_pct": round(100 * line_ok / n, 2), "line_n": line_ok,
            "mean_fraction": frac_sum / denom,
            "mean_files": round(mean_files, 3),
            "mean_tokens": round(mean_tokens, 1)}


def mcnemar_exact(pairs: list[tuple[bool, bool]]) -> dict:
    """Exact (binomial) McNemar on paired booleans (default, arm)."""
    b = sum(1 for d, s in pairs if d and not s)   # default-only wins
    c = sum(1 for d, s in pairs if s and not d)   # arm-only wins
    if b + c == 0:
        return {"b_def_only": 0, "c_arm_only": 0, "p": 1.0, "note": "no discordant pairs"}
    p = stats.binomtest(c, b + c, 0.5, alternative="two-sided").pvalue
    return {"b_def_only": b, "c_arm_only": c, "p": float(p)}


def fmt_row(tag: str, h: dict) -> str:
    return (f"{tag:9} {h['n']:5d} {h['n_errors']:4d} "
            f"{h['file_pct']:8.2f} ({h['file_n']:4d}) "
            f"{h['function_pct']:8.2f} ({h['function_n']:4d}) "
            f"{h['line_pct']:8.2f} ({h['line_n']:4d}) "
            f"{h['mean_fraction']:9.5f} "
            f"{h['mean_files']:8.2f} {h['mean_tokens']:9.1f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--def-jsonl", required=True)
    ap.add_argument("--arm-jsonl", required=True)
    ap.add_argument("--def-metric", required=True)
    ap.add_argument("--arm-metric", required=True)
    ap.add_argument("--out-prefix", required=True)
    args = ap.parse_args()

    d_recs, s_recs = load_records(args.def_jsonl), load_records(args.arm_jsonl)
    d_func, s_func = load_function_detail(args.def_metric), load_function_detail(args.arm_metric)

    ids = sorted(set(d_recs) & set(s_recs))
    only_d, only_s = sorted(set(d_recs) - set(s_recs)), sorted(set(s_recs) - set(d_recs))
    if only_d or only_s:
        print(f"WARNING: instance-set mismatch -- default-only={len(only_d)} "
              f"arm-only={len(only_s)}; paired stats use the {len(ids)} common ids")

    dh, sh = headline(d_recs, d_func), headline(s_recs, s_func)

    # Cross-check the recomputed headline against each metric JSON's own, so a
    # scoring/harness disagreement is loud instead of silently averaged away.
    crosscheck_ok = True
    for tag, metric_path, h in (("default", args.def_metric, dh),
                                ("arm", args.arm_metric, sh)):
        a = json.loads(Path(metric_path).read_text())["all_instances"]
        checks = [("FILE", a["file"]["pct_correct"], h["file_pct"]),
                  ("FUNCTION", a["function"]["pct_correct"], h["function_pct"]),
                  ("LINE", a["line"]["pct_correct_all_or_nothing"], h["line_pct"]),
                  ("frac", round(a["line"]["mean_fraction_covered"], 6),
                   round(h["mean_fraction"], 6))]
        for name, want, got in checks:
            if want != got:
                crosscheck_ok = False
                print(f"CROSSCHECK MISMATCH [{tag}] {name}: metric_json={want} recomputed={got}")

    print(f"\n=== {args.label} ===")
    print(f"{'arm':9} {'n':>5} {'err':>4} {'FILE':>16} {'FUNCTION':>16} "
          f"{'LINE':>16} {'frac':>9} {'files':>8} {'tokens':>9}")
    print(fmt_row("default", dh))
    print(fmt_row("arm", sh))
    print(f"{'delta':9} {'':5} {'':4} "
          f"{sh['file_pct'] - dh['file_pct']:+8.2f} {'':6} "
          f"{sh['function_pct'] - dh['function_pct']:+8.2f} {'':6} "
          f"{sh['line_pct'] - dh['line_pct']:+8.2f} {'':6} "
          f"{sh['mean_fraction'] - dh['mean_fraction']:+9.5f} "
          f"{sh['mean_files'] - dh['mean_files']:+8.2f} "
          f"{sh['mean_tokens'] - dh['mean_tokens']:+9.1f}")

    # ---- stratified breakdown: THE headline for this round ---------------
    # Strata are taken from the DEFAULT arm's n_gold_files, which is a
    # property of the gold patch and so identical in both arms; asserting
    # that rather than assuming it catches a mispaired run immediately.
    mismatched_strata = [i for i in ids if stratum_of(d_recs[i]) != stratum_of(s_recs[i])]
    if mismatched_strata:
        print(f"FATAL: {len(mismatched_strata)} instances disagree on gold-file count "
              f"between arms (e.g. {mismatched_strata[:3]}) -- arms are not paired")

    strat_out = {}
    print(f"\n--- stratified by gold-file count ---")
    print(f"{'stratum':9} {'arm':9} {'n':>5} {'err':>4} {'FILE':>16} {'FUNCTION':>16} "
          f"{'LINE':>16} {'frac':>9} {'files':>8} {'tokens':>9}")
    for st in STRATA:
        sids = [i for i in ids if stratum_of(d_recs[i]) == st]
        if not sids:
            continue
        dhs, shs = headline(d_recs, d_func, sids), headline(s_recs, s_func, sids)
        pairs_f = [((d_recs[i].get("hunk_file_covered") or 0) == 1.0,
                    (s_recs[i].get("hunk_file_covered") or 0) == 1.0) for i in sids]
        mc = mcnemar_exact(pairs_f)
        d_fr = [d_recs[i].get("hunk_line_recall") or 0 for i in sids]
        s_fr = [s_recs[i].get("hunk_line_recall") or 0 for i in sids]
        nz = [s - d for s, d in zip(s_fr, d_fr) if s != d]
        wil = (float(stats.wilcoxon(nz, alternative="two-sided").pvalue) if nz else 1.0)
        strat_out[st] = {"n": len(sids), "default": dhs, "arm": shs,
                         "delta_file": round(shs["file_pct"] - dhs["file_pct"], 2),
                         "delta_function": round(shs["function_pct"] - dhs["function_pct"], 2),
                         "delta_line": round(shs["line_pct"] - dhs["line_pct"], 2),
                         "delta_fraction": round(shs["mean_fraction"] - dhs["mean_fraction"], 6),
                         "delta_files": round(shs["mean_files"] - dhs["mean_files"], 3),
                         "delta_tokens": round(shs["mean_tokens"] - dhs["mean_tokens"], 1),
                         "file_mcnemar": mc,
                         "fraction_wilcoxon_p": wil,
                         "frac_up": sum(1 for x in nz if x > 0),
                         "frac_down": sum(1 for x in nz if x < 0)}
        print(f"{st:9} " + fmt_row("default", dhs))
        print(f"{'':9} " + fmt_row("arm", shs))
        print(f"{'':9} {'delta':9} {'':5} {'':4} "
              f"{strat_out[st]['delta_file']:+8.2f} {'':6} "
              f"{strat_out[st]['delta_function']:+8.2f} {'':6} "
              f"{strat_out[st]['delta_line']:+8.2f} {'':6} "
              f"{strat_out[st]['delta_fraction']:+9.5f} "
              f"{strat_out[st]['delta_files']:+8.2f} "
              f"{strat_out[st]['delta_tokens']:+9.1f}"
              f"   FILE McNemar {mc['b_def_only']}/{mc['c_arm_only']} p={mc['p']:.4f}")

    # ---- paired significance, whole slice --------------------------------
    stats_out = {}
    for name, getter in (
            ("FILE", lambda i, r, _f: (r[i].get("hunk_file_covered") or 0) == 1.0),
            ("FUNCTION", lambda i, _r, f: f.get(i, False)),
            ("LINE", lambda i, r, _f: (r[i].get("hunk_line_recall") or 0) == 1.0)):
        pairs = [(getter(i, d_recs, d_func), getter(i, s_recs, s_func)) for i in ids]
        stats_out[name] = mcnemar_exact(pairs)
        m = stats_out[name]
        print(f"McNemar {name:9} default-only={m['b_def_only']:3d} "
              f"arm-only={m['c_arm_only']:3d} p={m['p']:.4f}")

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
            "stratum": stratum_of(d), "n_gold_files": d.get("n_gold_files"),
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
        print(f"  {r['instance_id']:42} [{r['stratum']:2}] FILE {r['file']:6} "
              f"FUNC {r['function']:6} LINE {r['line_allornothing']:6} "
              f"frac {r['fraction']:20} ({r['fraction_delta']:+.4f})")

    out = {"label": args.label, "default": dh, "arm": sh,
           "delta": {"file": round(sh["file_pct"] - dh["file_pct"], 2),
                     "function": round(sh["function_pct"] - dh["function_pct"], 2),
                     "line": round(sh["line_pct"] - dh["line_pct"], 2),
                     "mean_fraction": round(sh["mean_fraction"] - dh["mean_fraction"], 6),
                     "mean_files": round(sh["mean_files"] - dh["mean_files"], 3),
                     "mean_tokens": round(sh["mean_tokens"] - dh["mean_tokens"], 1)},
           "strata": strat_out,
           "paired_stats": stats_out,
           "crosscheck_ok": crosscheck_ok,
           "n_changed": len(changed), "changed": changed,
           "instance_set_mismatch": {"default_only": only_d, "arm_only": only_s}}
    Path(f"{args.out_prefix}_paired.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {args.out_prefix}_paired.json")


if __name__ == "__main__":
    main()
