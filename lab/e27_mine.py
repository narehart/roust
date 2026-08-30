"""E27 mining: (a) drift audit of the fresh default arms against the committed
README scoreboard, and (b) where each arm's changed instances actually sit.

(a) DRIFT AUDIT. E27 re-ran a default arm for every slice on its own pinned
binary instead of reusing E25/E26 default arms. That is only worth doing if
the fresh arms reproduce the published references -- if they do, the round's
pairing is sound AND the rig is shown to be reproducible across engine
commits and fresh clones. The reference numbers below are transcribed from
the README's eight-row scoreboard, with the source artifact each cites.

(b) CHANGED-INSTANCE ANATOMY. A slice-level delta of -0.67 says nothing about
whether the mechanism misfired once badly or twenty times mildly. This groups
every changed instance by gold-file stratum and counts better/worse, which is
what tells the next round where the mechanism may fire and where it must not.

Usage: uv run --no-project python lab/e27_mine.py --dir lab/results_regions/e27
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

# slice -> (FILE, FUNCTION, LINE) from the committed README scoreboard.
# The fraction column is published rounded to 3dp, so it is compared at 3dp.
README_REF = {
    "lite": (92.33, 54.67, 44.00, 0.527),
    "ver":  (92.38, 47.17, 35.14, 0.476),
    "jsts": (46.38, 31.21, 14.14, 0.262),
    "java": (49.22, 36.72, 14.06, 0.415),
    "go":   (64.95, 28.97, 16.59, 0.410),
    "rust": (60.25, 19.67, 7.53, 0.243),
    "c":    (51.56, 28.12, 13.28, 0.225),
    "cpp":  (65.89, 17.83, 6.98, 0.299),
}
SLICES = ["jsts", "java", "go", "rust", "c", "cpp", "lite", "ver"]
PRETTY = {"lite": "python Lite", "ver": "python Verified"}
ARMS = ["s2", "s3", "s4"]
SEATS = {"s2": 2, "s3": 3, "s4": 4}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    a = ap.parse_args()
    d = a.dir

    print("## Drift audit — fresh E27 default arms vs the committed README scoreboard\n")
    print("| slice | metric | README | E27 fresh default | match |")
    print("|---|---|---|---|---|")
    all_match = True
    for s in SLICES:
        p = d / f"metric_{s}_s0.json"
        if not p.exists():
            print(f"| {PRETTY.get(s,s)} | — | — | MISSING | — |")
            all_match = False
            continue
        ai = json.loads(p.read_text())["all_instances"]
        got = (ai["file"]["pct_correct"], ai["function"]["pct_correct"],
               ai["line"]["pct_correct_all_or_nothing"],
               round(ai["line"]["mean_fraction_covered"], 3))
        ref = README_REF[s]
        for i, name in enumerate(("FILE", "FUNCTION", "LINE", "frac")):
            ok = got[i] == ref[i]
            all_match &= ok
            print(f"| {PRETTY.get(s,s) if i==0 else ''} | {name} | {ref[i]} | {got[i]} | "
                  f"{'yes' if ok else '**NO**'} |")
    print(f"\n**All 32 cells reproduce: {all_match}**\n")

    print("\n## Changed-instance anatomy, by gold-file stratum\n")
    print("`better`/`worse` are by per-instance line fraction; `flips` counts "
          "all-or-nothing metric transitions (FILE/FUNCTION/LINE).\n")
    print("| slice | arm | changed | stratum 1 | stratum 2 | stratum 3+ | better | worse | "
          "FILE flips +/- | FUNC flips +/- | LINE flips +/- |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for s in SLICES:
        for arm in ARMS:
            p = d / f"{s}_{arm}_paired.json"
            if not p.exists():
                continue
            j = json.loads(p.read_text())
            ch = j["changed"]
            by = collections.Counter(c["stratum"] for c in ch)
            better = sum(1 for c in ch if c["fraction_delta"] > 0)
            worse = sum(1 for c in ch if c["fraction_delta"] < 0)

            def flips(key):
                up = sum(1 for c in ch if c[key] == "0->1")
                dn = sum(1 for c in ch if c[key] == "1->0")
                return f"+{up}/-{dn}"

            print(f"| {PRETTY.get(s,s)} | seats {SEATS[arm]} | {len(ch)} | {by.get('1',0)} | "
                  f"{by.get('2',0)} | {by.get('3+',0)} | {better} | {worse} | "
                  f"{flips('file')} | {flips('function')} | {flips('line_allornothing')} |")

    # Python detail: name every changed instance, since these are the ones the
    # adoption decision turns on and there are few enough to itemize in full.
    print("\n### Python changed instances, itemized\n")
    for s in ("lite", "ver"):
        for arm in ARMS:
            p = d / f"{s}_{arm}_paired.json"
            if not p.exists():
                continue
            j = json.loads(p.read_text())
            print(f"\n**{PRETTY[s]}, seats {SEATS[arm]}** — {j['n_changed']} changed")
            if not j["changed"]:
                print("\n(none)")
                continue
            print("\n| instance | gold files | stratum | FILE | FUNCTION | LINE | fraction |")
            print("|---|---|---|---|---|---|---|")
            for c in j["changed"]:
                print(f"| {c['instance_id']} | {c['n_gold_files']} | {c['stratum']} | "
                      f"{c['file']} | {c['function']} | {c['line_allornothing']} | "
                      f"{c['fraction']} ({c['fraction_delta']:+.4f}) |")


if __name__ == "__main__":
    main()
