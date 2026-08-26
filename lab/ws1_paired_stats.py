"""WS1 (--index-all) paired stats + flip anatomy over the gate arms.

Compares {baseline, --index-all} on MSWE-580 and Lite-300 run JSONLs:
per-instance FILE flips (all-gold-superset) with two-sided sign tests,
ceiling-recovery accounting against the 135 blocked-instance list
(lab/ws1_ceiling_analysis.py output), displacement anatomy (which
newly-admitted files sit in lost instances' bundles; which gold suffixes
went missing), and paired line-fraction direction counts.

Usage:
    python lab/ws1_paired_stats.py <ceiling_records.jsonl>
"""
import json
import sys
from collections import Counter
from math import comb
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "parity"))
from region_eval import parse_gold_hunks  # noqa: E402

import pandas as pd

D = Path(__file__).resolve().parent / "results_regions"
CODE_EXTS = ('.py', '.ts', '.js', '.go', '.rs', '.java', '.kt', '.cs', '.swift', '.tsx', '.jsx')


def sign_test(g: int, l: int) -> float:
    n = g + l
    if n == 0:
        return 1.0
    k = min(g, l)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def rows(p: Path) -> dict:
    return {json.loads(l)["instance_id"]: json.loads(l) for l in open(p)}


def file_ok(rec: dict, gold: list[str]) -> bool:
    return rec["error"] is None and set(gold) <= set(rec["regions"].keys())


def flips(base: dict, flag: dict, gold_by_iid: dict):
    gains = [i for i in gold_by_iid if not file_ok(base[i], gold_by_iid[i]) and file_ok(flag[i], gold_by_iid[i])]
    losses = [i for i in gold_by_iid if file_ok(base[i], gold_by_iid[i]) and not file_ok(flag[i], gold_by_iid[i])]
    return gains, losses


def fraction_pairs(base: dict, flag: dict) -> tuple[int, int]:
    g = l = 0
    for iid in base:
        fb, ff = base[iid].get("hunk_line_recall"), flag[iid].get("hunk_line_recall")
        if fb is None or ff is None:
            continue
        g += ff > fb
        l += ff < fb
    return g, l


def main() -> None:
    blocked = {json.loads(l)["instance_id"] for l in open(sys.argv[1])}

    mdf = pd.read_parquet(D.parent / "mswe_jsts.parquet")
    mgold = {r["instance_id"]: sorted(parse_gold_hunks(r["patch"]).keys()) for _, r in mdf.iterrows()}
    mb, mf = rows(D / "mswe_jsts_ws1_baseline.jsonl"), rows(D / "mswe_jsts_ws1_indexall.jsonl")
    gains, losses = flips(mb, mf, mgold)
    print(f"MSWE FILE flips: +{len(gains)}/-{len(losses)}  p={sign_test(len(gains), len(losses)):.2e}")
    print(f"  blocked recovered: {sum(1 for i in blocked if file_ok(mf[i], mgold[i]))}/{len(blocked)}")
    unblocked = [i for i in mgold if i not in blocked]
    print(f"  unblocked (n={len(unblocked)}): "
          f"{sum(1 for i in unblocked if file_ok(mb[i], mgold[i]))} -> "
          f"{sum(1 for i in unblocked if file_ok(mf[i], mgold[i]))} FILE-correct")
    cls = Counter()
    tot_out = ret_out = 0
    for iid in blocked:
        rec, gold = mf[iid], mgold[iid]
        for g in gold:
            if not g.endswith(CODE_EXTS):
                tot_out += 1
                ret_out += g in rec["regions"]
        if rec["error"] is not None:
            cls["engine_error"] += 1
            continue
        missing = [g for g in gold if g not in rec["regions"]]
        if not missing:
            cls["recovered"] += 1
            continue
        m_out = any(not g.endswith(CODE_EXTS) for g in missing)
        m_code = any(g.endswith(CODE_EXTS) for g in missing)
        cls["missing_both_kinds" if (m_out and m_code) else
            "missing_only_outside_gold" if m_out else "missing_only_code_gold"] += 1
    print(f"  blocked classification: {dict(cls)}")
    print(f"  outside-allowlist gold files returned: {ret_out}/{tot_out}")
    disp = Counter()
    for iid in losses:
        for fn in mf[iid]["regions"]:
            if not fn.endswith(CODE_EXTS):
                disp[fn.rsplit("/", 1)[-1]] += 1
    print(f"  displacing newcomers in lost bundles (top): {disp.most_common(10)}")
    g, l = fraction_pairs(mb, mf)
    print(f"  fraction paired: +{g}/-{l}  p={sign_test(g, l):.2e}")

    ldf = pd.read_parquet(D.parent / "swebench_lite.parquet")
    lgold = {r["instance_id"]: sorted(parse_gold_hunks(r["patch"]).keys()) for _, r in ldf.iterrows()}
    lb, lf = rows(D / "ws1_lite300_baseline.jsonl"), rows(D / "ws1_lite300_indexall.jsonl")
    gains, losses = flips(lb, lf, lgold)
    print(f"\nLite FILE flips: +{len(gains)}/-{len(losses)}  p={sign_test(len(gains), len(losses)):.2e}")
    for iid in losses:
        missing = [g for g in lgold[iid] if g not in lf[iid]["regions"]]
        newc = [fn for fn in lf[iid]["regions"] if not fn.endswith(CODE_EXTS)]
        print(f"  LOST {iid}: missing gold {missing}; newcomers: {newc}")
    for iid in gains:
        print(f"  GAINED {iid}")
    g, l = fraction_pairs(lb, lf)
    print(f"  fraction paired: +{g}/-{l}  p={sign_test(g, l):.2e}")


if __name__ == "__main__":
    main()
