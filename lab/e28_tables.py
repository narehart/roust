"""E28 tables: turn the paired JSONs into the writeup's markdown.

Emits, in order:
  1. the per-slice headline table (default vs --max-additions 24/32)
  2. the STRATIFIED table by gold-file count (1 / 2 / 3+) -- the 3+ column is
     what breadth is supposed to buy
  3. paired significance per slice/arm
  4. THE COST TABLE -- mean files returned, mean bundle tokens, and region
     precision per arm. E28 is a trade, not a free win: the 8192-token budget
     is fixed, so admitting more candidates spreads the same budget over more
     files. Reporting the metrics without this table would hide the mechanism.
  5. an adoption-bar scorecard.

Usage: uv run --no-project python lab/e28_tables.py --dir lab/results_regions/e28
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SLICES = ["jsts", "java", "go", "rust", "c", "cpp", "lite", "ver"]
PRETTY = {"lite": "python Lite", "ver": "python Verified"}
ARMS = ["m24", "m32"]
CAPS = {"m24": 24, "m32": 32}


def load(d: Path, name: str):
    p = d / name
    return json.loads(p.read_text()) if p.exists() else None


def h_cells(h: dict) -> str:
    return (f"{h['file_pct']:.2f} ({h['file_n']}) | {h['function_pct']:.2f} ({h['function_n']}) | "
            f"{h['line_pct']:.2f} ({h['line_n']}) | {h['mean_fraction']:.5f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    a = ap.parse_args()
    d = a.dir

    paired = {}
    for s in SLICES:
        for arm in ARMS:
            paired[(s, arm)] = load(d, f"{s}_{arm}_paired.json")

    missing = [f"{s}_{arm}" for (s, arm), v in paired.items() if v is None]
    if missing:
        print(f"<!-- MISSING paired json: {', '.join(missing)} -->\n")

    # ---- 1. per-slice headline -----------------------------------------
    print("## Per-slice results\n")
    print("| slice | n | arm | FILE | FUNCTION (exact) | LINE | line frac |")
    print("|---|---|---|---|---|---|---|")
    for s in SLICES:
        base = next((paired[(s, x)] for x in ARMS if paired.get((s, x))), None)
        if not base:
            continue
        n = base["default"]["n"]
        label = PRETTY.get(s, s)
        print(f"| **{label}** | {n} | default | {h_cells(base['default'])} |")
        for arm in ARMS:
            p = paired.get((s, arm))
            if not p:
                continue
            dl = p["delta"]
            print(f"| | | cap {CAPS[arm]} | {h_cells(p['arm'])} |")
            print(f"| | | *delta* | *{dl['file']:+.2f}* | *{dl['function']:+.2f}* | "
                  f"*{dl['line']:+.2f}* | *{dl['mean_fraction']:+.5f}* |")

    # ---- 2. stratified --------------------------------------------------
    print("\n## Stratified by gold-file count — the headline\n")
    print("FILE / FUNCTION / LINE per stratum. The 3+ column is the target.\n")
    print("| slice | arm | 1 gold | 2 gold | 3+ gold |")
    print("|---|---|---|---|---|")
    for s in SLICES:
        base = next((paired[(s, x)] for x in ARMS if paired.get((s, x))), None)
        if not base:
            continue
        label = PRETTY.get(s, s)

        def strat_cells(which: str, p: dict) -> list[str]:
            out = []
            for st in ("1", "2", "3+"):
                sd = p["strata"].get(st)
                if not sd:
                    out.append("— (n=0)")
                    continue
                h = sd[which]
                out.append(f"{h['file_pct']:.2f}/{h['function_pct']:.2f}/{h['line_pct']:.2f} (n={sd['n']})")
            return out

        print(f"| **{label}** | default | " + " | ".join(strat_cells("default", base)) + " |")
        for arm in ARMS:
            p = paired.get((s, arm))
            if not p:
                continue
            cells = strat_cells("arm", p)
            # annotate the 3+ cell with its FILE delta and McNemar p
            sd = p["strata"].get("3+")
            if sd:
                mc = sd["file_mcnemar"]
                cells[2] += f" **[FILE {sd['delta_file']:+.2f}, {mc['b_def_only']}/{mc['c_arm_only']}, p={mc['p']:.4f}]**"
            print(f"| | cap {CAPS[arm]} | " + " | ".join(cells) + " |")

    # ---- 3. paired significance ----------------------------------------
    print("\n## Paired significance (whole slice)\n")
    print("| slice | arm | McNemar FILE (def-only/arm-only, p) | FUNCTION | LINE | Wilcoxon frac | changed |")
    print("|---|---|---|---|---|---|---|")
    for s in SLICES:
        for arm in ARMS:
            p = paired.get((s, arm))
            if not p:
                continue
            st = p["paired_stats"]
            def mc(k):
                m = st[k]
                return f"{m['b_def_only']}/{m['c_arm_only']}, p={m['p']:.4f}"
            w = st["fraction_wilcoxon"]
            wtxt = (f"{w.get('n_up',0)}up/{w.get('n_down',0)}down, p={w['p']:.4f}"
                    if w.get("n_nonzero") else "no change")
            print(f"| {PRETTY.get(s,s)} | cap {CAPS[arm]} | {mc('FILE')} | {mc('FUNCTION')} | "
                  f"{mc('LINE')} | {wtxt} | {p['n_changed']}/{p['default']['n']} |")

    # ---- 4. THE COST TABLE ----------------------------------------------
    # The load-bearing section. Breadth is bought with budget: the packer's
    # 8192 tokens do not grow when the cap does, so every extra file admitted
    # is depth taken from the files already there. wave-5's Recall Trap
    # (arXiv:2608.14838) measured that trade going the WRONG way downstream,
    # so it gets reported as prominently as the metrics it pays for.
    print("\n## The cost of breadth — files returned and bundle tokens\n")
    print("Budget is fixed at 8192 tokens, so `files` rising while `tokens` "
          "stays flat IS the trade: the same budget spread thinner.\n")
    print("| slice | arm | mean files returned | mean bundle tokens | "
          "files delta | tokens delta |")
    print("|---|---|---|---|---|---|")
    for s in SLICES:
        base = next((paired[(s, x)] for x in ARMS if paired.get((s, x))), None)
        if not base:
            continue
        label = PRETTY.get(s, s)
        dh = base["default"]
        print(f"| **{label}** | default | {dh['mean_files']:.2f} | "
              f"{dh['mean_tokens']:.1f} | — | — |")
        for arm in ARMS:
            p = paired.get((s, arm))
            if not p:
                continue
            ah, dl = p["arm"], p["delta"]
            print(f"| | cap {CAPS[arm]} | {ah['mean_files']:.2f} | "
                  f"{ah['mean_tokens']:.1f} | {dl['mean_files']:+.2f} | "
                  f"{dl['mean_tokens']:+.1f} |")

    # ---- 4b. cost per stratum -------------------------------------------
    print("\n## Cost by gold-file stratum (mean files returned)\n")
    print("| slice | arm | 1 gold | 2 gold | 3+ gold |")
    print("|---|---|---|---|---|")
    for s in SLICES:
        base = next((paired[(s, x)] for x in ARMS if paired.get((s, x))), None)
        if not base:
            continue
        label = PRETTY.get(s, s)

        def cost_cells(which: str, p: dict) -> list[str]:
            out = []
            for st in ("1", "2", "3+"):
                sd = p["strata"].get(st)
                if not sd:
                    out.append("—")
                    continue
                h = sd[which]
                out.append(f"{h['mean_files']:.2f} files / {h['mean_tokens']:.0f} tok")
            return out

        print(f"| **{label}** | default | " + " | ".join(cost_cells("default", base)) + " |")
        for arm in ARMS:
            p = paired.get((s, arm))
            if not p:
                continue
            print(f"| | cap {CAPS[arm]} | " + " | ".join(cost_cells("arm", p)) + " |")

    # ---- 5. adoption bar ------------------------------------------------
    print("\n## Adoption bar\n")
    print("Bar: 3+ stratum improves materially on affected slices, Lite AND Verified "
          "non-negative on ALL FOUR metrics, no slice regresses significantly.\n")
    print("| arm | Python Lite 4-metric | Python Verified 4-metric | slices with 3+ FILE gain | "
          "slices with significant regression (p<0.05) | verdict |")
    print("|---|---|---|---|---|---|")
    for arm in ARMS:
        def py_ok(slice_name):
            p = paired.get((slice_name, arm))
            if not p:
                return "n/a", False
            dl = p["delta"]
            vals = [dl["file"], dl["function"], dl["line"], dl["mean_fraction"]]
            ok = all(v >= 0 for v in vals)
            return (f"{dl['file']:+.2f}/{dl['function']:+.2f}/{dl['line']:+.2f}/"
                    f"{dl['mean_fraction']:+.5f}"), ok
        lt, lok = py_ok("lite")
        vt, vok = py_ok("ver")
        gains, regress = [], []
        for s in SLICES:
            p = paired.get((s, arm))
            if not p:
                continue
            sd = p["strata"].get("3+")
            if sd and sd["delta_file"] > 0:
                gains.append(f"{PRETTY.get(s,s)} {sd['delta_file']:+.2f}")
            for k in ("FILE", "FUNCTION", "LINE"):
                m = p["paired_stats"][k]
                if m["p"] < 0.05 and m["b_def_only"] > m["c_arm_only"]:
                    regress.append(f"{PRETTY.get(s,s)} {k} p={m['p']:.4f}")
        verdict = "PASS" if (lok and vok and gains and not regress) else "FAIL"
        print(f"| cap {CAPS[arm]} | {lt} {'OK' if lok else '**NEG**'} | "
              f"{vt} {'OK' if vok else '**NEG**'} | {', '.join(gains) or 'none'} | "
              f"{', '.join(regress) or 'none'} | **{verdict}** |")


if __name__ == "__main__":
    main()
