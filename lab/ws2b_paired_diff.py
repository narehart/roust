"""WS2b paired per-instance diff: baseline vs --cfamily-ext arm (campaign #56).

Itemizes every instance whose retrieval payload or correctness changed
between two region_eval jsonl reports (same instances, same binary, flag
off vs on), and attributes each change:

  * direct: C-family files present in the experiment arm's returned regions
  * indirect: payload changed with NO C-family file in the bundle -- the
    index-level df/IDF + candidate-competition shift (WS2b Gate B's
    astropy-14182/sklearn signature)

Correctness per level comes from the same stored fields the scorers read
(`all_gold_files_retrieved`, `hunk_line_recall`) plus the FUNCTION flip
list taken from the two agentless-metric JSONs' `detail` arrays. The
fraction sign test is the two-sided exact binomial (ws2_paired_stats
convention).
"""
import argparse
import json
from math import comb
from pathlib import Path

CFAM = (".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh")


def load_jsonl(p: Path) -> dict[str, dict]:
    out = {}
    with p.open() as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                out[r["instance_id"]] = r
    return out


def sign_test(pos: int, neg: int) -> float:
    n = pos + neg
    if n == 0:
        return 1.0
    k = min(pos, neg)
    p = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n * 2
    return min(1.0, p)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--exp", type=Path, required=True)
    ap.add_argument("--metric-base", type=Path, required=True)
    ap.add_argument("--metric-exp", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    base = load_jsonl(args.base)
    exp = load_jsonl(args.exp)
    assert set(base) == set(exp), "instance sets differ"

    fdet_b = {d["instance_id"]: d["correct"] for d in
              json.load(args.metric_base.open())["all_instances"]["function"]["detail"]}
    fdet_e = {d["instance_id"]: d["correct"] for d in
              json.load(args.metric_exp.open())["all_instances"]["function"]["detail"]}

    changed = []
    frac_pos = frac_neg = 0
    payload_diff_n = 0
    for iid in sorted(base):
        b, e = base[iid], exp[iid]
        pb = {k: b.get(k) for k in ("regions",)}
        pe = {k: e.get(k) for k in ("regions",)}
        payload_diff = pb != pe
        if payload_diff:
            payload_diff_n += 1
        flips = {}
        if bool(b.get("all_gold_files_retrieved")) != bool(e.get("all_gold_files_retrieved")):
            flips["FILE"] = (bool(b.get("all_gold_files_retrieved")),
                             bool(e.get("all_gold_files_retrieved")))
        if fdet_b.get(iid) != fdet_e.get(iid):
            flips["FUNCTION"] = (fdet_b.get(iid), fdet_e.get(iid))
        lb = b.get("hunk_line_recall") == 1.0
        le = e.get("hunk_line_recall") == 1.0
        if lb != le:
            flips["LINE"] = (lb, le)
        db = b.get("hunk_line_recall")
        de = e.get("hunk_line_recall")
        frac_delta = None
        if db is not None and de is not None:
            frac_delta = de - db
            if frac_delta > 0:
                frac_pos += 1
            elif frac_delta < 0:
                frac_neg += 1
        if payload_diff or flips:
            cfam = [f for f in e.get("regions", {}) if f.endswith(CFAM)]
            changed.append({
                "instance_id": iid,
                "payload_diff": payload_diff,
                "flips": flips,
                "frac_delta": frac_delta,
                "cfamily_files_in_exp_bundle": cfam,
                "attribution": "direct" if cfam else ("indirect" if payload_diff else "none"),
            })

    report = {
        "base": str(args.base), "exp": str(args.exp),
        "n": len(base),
        "n_payload_diff": payload_diff_n,
        "n_changed_or_flipped": len(changed),
        "fraction_sign_test": {"pos": frac_pos, "neg": frac_neg,
                               "p_two_sided": sign_test(frac_pos, frac_neg)},
        "changed": changed,
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")

    print(f"n={len(base)} payload_diff={payload_diff_n} "
          f"frac +{frac_pos}/-{frac_neg} p={report['fraction_sign_test']['p_two_sided']:.3g}")
    for c in changed:
        if c["flips"] or c["frac_delta"]:
            print(f"  {c['instance_id']:45} flips={c['flips'] or '-'} "
                  f"dfrac={c['frac_delta'] if c['frac_delta'] is not None else 'n/a'} "
                  f"[{c['attribution']}] cfam={c['cfamily_files_in_exp_bundle']}")


if __name__ == "__main__":
    main()
