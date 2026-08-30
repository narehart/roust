"""E27 tables: turn the paired + seat JSONs into the writeup's markdown.

Emits, in order:
  1. the per-slice headline table (default vs seats 2/3/4, FILE/FUNCTION/LINE/frac)
  2. the STRATIFIED table by gold-file count (1 / 2 / 3+) -- the headline of
     this round, because the 3+ stratum is what the mechanism targets
  3. paired significance per slice/arm
  4. seat-fire anatomy
  5. an adoption-bar scorecard: does any arm clear "material 3+ gain on the
     affected slices, Lite AND Verified non-negative on all four metrics"?

Usage: uv run --no-project python lab/e27_tables.py --dir lab/results_regions/e27
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SLICES = ["jsts", "java", "go", "rust", "c", "cpp", "lite", "ver"]
PRETTY = {"lite": "python Lite", "ver": "python Verified"}
ARMS = ["s2", "s3", "s4"]
SEATS = {"s2": 2, "s3": 3, "s4": 4}


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
    seats = {}
    for s in SLICES:
        for arm in ARMS:
            paired[(s, arm)] = load(d, f"{s}_{arm}_paired.json")
            seats[(s, arm)] = load(d, f"seats_{s}_{arm}.json")

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
            print(f"| | | seats {SEATS[arm]} | {h_cells(p['arm'])} |")
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
            print(f"| | seats {SEATS[arm]} | " + " | ".join(cells) + " |")

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
            print(f"| {PRETTY.get(s,s)} | seats {SEATS[arm]} | {mc('FILE')} | {mc('FUNCTION')} | "
                  f"{mc('LINE')} | {wtxt} | {p['n_changed']}/{p['default']['n']} |")

    # ---- 4. seat anatomy ------------------------------------------------
    print("\n## Seat-fire anatomy\n")
    print("| slice | arm | instances fired | extra seats | mean where fired | seated file was gold | "
          "gold the default LACKED | bundles changed | files +/- (gold) | net gold |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for s in SLICES:
        for arm in ARMS:
            z = seats.get((s, arm))
            if not z:
                continue
            f, c = z["fire_side"], z["consequence_side"]
            print(f"| {PRETTY.get(s,s)} | seats {SEATS[arm]} | "
                  f"{f['instances_with_any_extra_seat']}/{f['instances_traced']} ({f['pct_instances_fired']}%) | "
                  f"{f['total_extra_seats']} | {f['mean_seats_where_fired']} | "
                  f"{f['seated_files_that_are_gold']} ({f['seat_gold_precision_pct']}%) | "
                  f"{f['gold_seats_the_default_lacked']} | "
                  f"{c['bundles_changed']} ({c['pct_bundles_changed']}%) | "
                  f"+{c['files_added']} ({c['files_added_gold']}) / -{c['files_dropped']} ({c['files_dropped_gold']}) | "
                  f"{c['net_gold']:+d} |")

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
        print(f"| seats {SEATS[arm]} | {lt} {'OK' if lok else '**NEG**'} | "
              f"{vt} {'OK' if vok else '**NEG**'} | {', '.join(gains) or 'none'} | "
              f"{', '.join(regress) or 'none'} | **{verdict}** |")


if __name__ == "__main__":
    main()
