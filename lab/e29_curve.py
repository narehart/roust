"""E29 cost-of-parity curve: what does multi-file localization COST, per language?

E28 rejected the breadth cap because at a FIXED 8192-token budget, FILE rose on
16/16 arms while FUNCTION/LINE fell on 16/16 -- breadth cannibalised depth.
E29 asks the question E28's design could not answer: is that trade a property
of the MECHANISM, or of the fixed budget it was measured under?

Every arm here is restricted to the >=3-gold-file stratum, the only stratum
where multi-file localization is even at issue. Arms:

  a1 (cap 16, budget  8192)  the shipped default -- the baseline all deltas are against
  a2 (cap 32, budget  8192)  E28's rejected arm, replicated on this stratum
  a3 (cap 32, budget 16384)
  a4 (cap 32, budget 24576)
  a5 (cap 16, budget 24576)  DECOMPOSITION arm, not in the original design:
                             a3/a4 move cap and budget together, so without a5
                             the round could not say which of the two bought
                             the gain. a5 holds the cap at its shipped 16 and
                             moves only the budget.

This is a MEASUREMENT, not an adoption. Cross-budget rows are NOT comparable
to the published 8192 scoreboard, and a bigger budget is not a free win: 8192
is a product choice matched to agent context windows, and every extra token
spent localizing is a token the consumer pays for.

Reported per slice per arm: all-gold FILE %, FUNCTION, LINE, mean gold-line
fraction, mean bundle tokens, mean files returned, plus exact-McNemar /
Wilcoxon paired stats against a1. Then the two derived artifacts:

  * the CURVE -- 3+ FILE and gold-line fraction against token budget, per language;
  * BUDGET TO PARITY -- the budget at which each language's 3+ stratum reaches
    Python-Verified's default 3+ FILE baseline (63.64), and whether its line
    fraction at that budget is at or above its OWN 8192 default. A language
    that reaches the FILE bar while sitting below its own default fraction has
    not reached parity; it has bought files with depth at a higher price.

Usage:
  uv run --no-project --with scipy python lab/e29_curve.py --dir DIR > tables.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e28_paired import (load_records, load_function_detail,  # noqa: E402
                        headline, mcnemar_exact)
from scipy import stats  # noqa: E402

SLICES = ["jsts", "java", "go", "rust", "c", "cpp", "ver"]
SLICE_LABEL = {"jsts": "JS/TS", "java": "Java", "go": "Go", "rust": "Rust",
               "c": "C", "cpp": "C++", "ver": "Python Verified"}

# (tag, cap, budget, human label)
ARMS = [
    ("a1_c16b8192",  16,  8192, "cap 16 @ 8192 (default)"),
    ("a2_c32b8192",  32,  8192, "cap 32 @ 8192 (E28)"),
    ("a3_c32b16384", 32, 16384, "cap 32 @ 16384"),
    ("a4_c32b24576", 32, 24576, "cap 32 @ 24576"),
    ("a5_c16b24576", 16, 24576, "cap 16 @ 24576 (decomp)"),
]

# Python Verified's DEFAULT 3+ FILE, measured in E28 on the same 22 instances.
# This is the parity bar the other languages are being priced against.
PARITY_BAR = 63.64


def paired(d_recs, d_func, a_recs, a_func, ids):
    """Exact McNemar on the three all-or-nothing metrics + Wilcoxon on fraction."""
    def mc(key, func_a=None, func_b=None):
        if key == "function":
            pairs = [(d_func.get(i, False), a_func.get(i, False)) for i in ids]
        else:
            f = "hunk_file_covered" if key == "file" else "hunk_line_recall"
            pairs = [((d_recs[i].get(f) or 0) == 1.0,
                      (a_recs[i].get(f) or 0) == 1.0) for i in ids]
        return mcnemar_exact(pairs)

    d_fr = [d_recs[i].get("hunk_line_recall") or 0 for i in ids]
    a_fr = [a_recs[i].get("hunk_line_recall") or 0 for i in ids]
    nz = [a - d for a, d in zip(a_fr, d_fr) if a != d]
    wil = float(stats.wilcoxon(nz, alternative="two-sided").pvalue) if nz else 1.0
    return {"file": mc("file"), "function": mc("function"), "line": mc("line"),
            "frac_p": wil,
            "frac_up": sum(1 for x in nz if x > 0),
            "frac_down": sum(1 for x in nz if x < 0),
            "changed": len(nz)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, type=Path)
    args = ap.parse_args()
    arms_dir, met_dir = args.dir / "arms", args.dir / "metrics"

    data: dict[str, dict[str, dict]] = {}
    missing = []
    for s in SLICES:
        data[s] = {}
        for tag, cap, bud, _lab in ARMS:
            j, m = arms_dir / f"{s}_{tag}.jsonl", met_dir / f"{s}_{tag}.json"
            if not j.exists() or not m.exists():
                missing.append(f"{s}_{tag}")
                continue
            recs, func = load_records(j), load_function_detail(m)
            data[s][tag] = {"recs": recs, "func": func,
                            "h": headline(recs, func), "cap": cap, "budget": bud}
    if missing:
        print(f"> **MISSING ARMS:** {', '.join(missing)}\n")

    # ---------- 1. per-slice per-arm table ---------------------------------
    print("## Per-slice, per-arm results (>=3 gold files only)\n")
    print("| slice | n | arm | budget | FILE | FUNCTION | LINE | line frac "
          "| mean tokens | mean files |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for s in SLICES:
        base = data[s].get("a1_c16b8192")
        for tag, cap, bud, lab in ARMS:
            e = data[s].get(tag)
            if not e:
                continue
            h = e["h"]
            name = SLICE_LABEL[s] if tag == ARMS[0][0] else ""
            n = str(h["n"]) if tag == ARMS[0][0] else ""
            print(f"| **{name}** | {n} | {lab} | {bud} "
                  f"| {h['file_pct']:.2f} ({h['file_n']}) "
                  f"| {h['function_pct']:.2f} ({h['function_n']}) "
                  f"| {h['line_pct']:.2f} ({h['line_n']}) "
                  f"| {h['mean_fraction']:.5f} "
                  f"| {h['mean_tokens']:.0f} | {h['mean_files']:.2f} |")
            if base and tag != "a1_c16b8192":
                b = base["h"]
                print(f"| | | *delta* | | *{h['file_pct']-b['file_pct']:+.2f}* "
                      f"| *{h['function_pct']-b['function_pct']:+.2f}* "
                      f"| *{h['line_pct']-b['line_pct']:+.2f}* "
                      f"| *{h['mean_fraction']-b['mean_fraction']:+.5f}* "
                      f"| *{h['mean_tokens']-b['mean_tokens']:+.0f}* "
                      f"| *{h['mean_files']-b['mean_files']:+.2f}* |")

    # ---------- 2. paired significance vs a1 -------------------------------
    print("\n## Paired significance vs the default arm (a1)\n")
    print("| slice | arm | McNemar FILE (def-only/arm-only, p) | FUNCTION | LINE "
          "| Wilcoxon frac | changed |")
    print("|---|---|---|---|---|---|---|")
    stat_out = {}
    for s in SLICES:
        base = data[s].get("a1_c16b8192")
        if not base:
            continue
        for tag, cap, bud, lab in ARMS[1:]:
            e = data[s].get(tag)
            if not e:
                continue
            ids = sorted(set(base["recs"]) & set(e["recs"]))
            st = paired(base["recs"], base["func"], e["recs"], e["func"], ids)
            stat_out[f"{s}/{tag}"] = st
            f_, fn, ln = st["file"], st["function"], st["line"]
            print(f"| {SLICE_LABEL[s]} | {lab} "
                  f"| {f_['b_def_only']}/{f_['c_arm_only']}, p={f_['p']:.4f} "
                  f"| {fn['b_def_only']}/{fn['c_arm_only']}, p={fn['p']:.4f} "
                  f"| {ln['b_def_only']}/{ln['c_arm_only']}, p={ln['p']:.4f} "
                  f"| {st['frac_up']}up/{st['frac_down']}down, p={st['frac_p']:.4f} "
                  f"| {st['changed']}/{len(ids)} |")

    # ---------- 3. the curve ------------------------------------------------
    print("\n## The cost-of-parity curve\n")
    print("3+ FILE and mean gold-line fraction against token budget. The cap-32 "
          "column is the curve proper; the cap-16 @ 24576 column isolates how "
          "much of the move is budget alone.\n")
    print("| slice | 8192 cap16 | 8192 cap32 | 16384 cap32 | 24576 cap32 "
          "| 24576 cap16 |")
    print("|---|---|---|---|---|---|")
    for s in SLICES:
        cells = []
        for tag, *_ in ARMS:
            e = data[s].get(tag)
            cells.append(f"{e['h']['file_pct']:.2f} / {e['h']['mean_fraction']:.4f}"
                         if e else "—")
        print(f"| {SLICE_LABEL[s]} | " + " | ".join(cells) + " |")

    # ---------- 4. budget to parity ----------------------------------------
    print(f"\n## Budget to parity (bar = Python Verified's default 3+ FILE = "
          f"{PARITY_BAR})\n")
    print("`reached` is the first MEASURED cap-32 budget whose 3+ FILE is at or "
          "above the bar. `est.` linearly interpolates between the two "
          "bracketing measured points -- an estimate, not a measurement. "
          "`depth held` asks whether the line fraction at that budget is at or "
          "above the SAME slice's own 8192 default: a language that clears the "
          "FILE bar while below its own default depth has not reached parity.\n")
    print("| slice | default 3+ FILE | default frac | reached at | est. budget "
          "| FILE there | frac there | depth held? |")
    print("|---|---|---|---|---|---|---|---|")
    parity = {}
    curve_arms = ["a1_c16b8192", "a2_c32b8192", "a3_c32b16384", "a4_c32b24576"]
    for s in SLICES:
        base = data[s].get("a1_c16b8192")
        if not base:
            continue
        d_file, d_frac = base["h"]["file_pct"], base["h"]["mean_fraction"]
        pts = [(data[s][t]["budget"], data[s][t]["h"]["file_pct"],
                data[s][t]["h"]["mean_fraction"])
               for t in curve_arms if t in data[s]]
        hit = next((p for p in pts if p[1] >= PARITY_BAR), None)
        if hit:
            reached, f_there, fr_there = f"{hit[0]}", hit[1], hit[2]
            # interpolate between the last point below the bar and this one
            below = [p for p in pts if p[1] < PARITY_BAR and p[0] < hit[0]]
            if below:
                lo = below[-1]
                span = hit[1] - lo[1]
                est = (lo[0] + (hit[0] - lo[0]) * (PARITY_BAR - lo[1]) / span
                       if span > 0 else hit[0])
                est_s = f"~{est:.0f}"
            else:
                est_s = "already at/above at 8192"
            held = "yes" if fr_there >= d_frac else f"**no** ({fr_there:.4f} < {d_frac:.4f})"
        else:
            reached, est_s, held = "not by 24576", "—", "—"
            f_there = pts[-1][1] if pts else 0.0
            fr_there = pts[-1][2] if pts else 0.0
        parity[s] = {"default_file": d_file, "default_frac": d_frac,
                     "reached": reached, "est": est_s,
                     "file_there": f_there, "frac_there": fr_there,
                     "depth_held": held,
                     "points": [{"budget": b, "file": f, "frac": fr} for b, f, fr in pts]}
        print(f"| {SLICE_LABEL[s]} | {d_file:.2f} | {d_frac:.5f} | {reached} "
              f"| {est_s} | {f_there:.2f} | {fr_there:.5f} | {held} |")

    (args.dir / "curve.json").write_text(json.dumps(
        {"parity_bar": PARITY_BAR, "parity": parity, "paired": stat_out,
         "arms": [{"tag": t, "cap": c, "budget": b, "label": l} for t, c, b, l in ARMS],
         "headline": {s: {t: data[s][t]["h"] for t in data[s]} for s in SLICES}},
        indent=1, default=str))


if __name__ == "__main__":
    main()
