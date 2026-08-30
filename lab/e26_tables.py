#!/usr/bin/env python3
"""E26 final tables, emitted as markdown straight from the committed artifacts.

Table A -- the three-column per-language result: default / --ext-v2 /
--ext-v2 with the fixture guard, with paired stats against the SAME default.
Table B -- the goal scoreboard, stratified by gold-file count.

Everything is read from the *_paired.json files written by lab/e26_paired.py
and the scoreboard JSON from lab/e26_scoreboard.py, so the prose can never
drift from the measurements.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path


def fmt(h):
    return (f"{h['file_pct']:.2f} ({h['file_n']}) | {h['function_pct']:.2f} ({h['function_n']}) "
            f"| {h['line_pct']:.2f} ({h['line_n']}) | {h['mean_fraction']:.5f}")


def stat_cell(p):
    m = p["paired_stats"]
    w = m["fraction_wilcoxon"]
    return (f"FILE {m['FILE']['b_def_only']}/{m['FILE']['c_ext_only']}, p={m['FILE']['p']:.4f} · "
            f"FUNC {m['FUNCTION']['b_def_only']}/{m['FUNCTION']['c_ext_only']}, p={m['FUNCTION']['p']:.4f} · "
            f"LINE {m['LINE']['b_def_only']}/{m['LINE']['c_ext_only']}, p={m['LINE']['p']:.4f} · "
            f"frac {w.get('n_up',0)}up/{w.get('n_down',0)}down, p={w['p']:.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--scoreboard", type=Path, required=True)
    a = ap.parse_args()
    D = a.dir

    print("### Table A — per-language, default vs --ext-v2 vs --ext-v2 + fixture guard\n")
    print("| slice | n | arm | FILE | FUNCTION (exact) | LINE | line frac |")
    print("|---|---|---|---|---|---|---|")
    order = ["jsts", "java", "c", "rust", "cpp"]
    stats_rows = []
    for s in order:
        u = json.loads((D / f"{s}_ext_paired.json").read_text())
        g_path = D / f"{s}_guard_paired.json"
        g = json.loads(g_path.read_text()) if g_path.exists() else None
        n = u["n"]
        print(f"| **{s}** | {n} | default | {fmt(u['default'])} |")
        print(f"| | | --ext-v2 | {fmt(u['ext_v2'])} |")
        d = u["delta"]
        print(f"| | | *delta* | *{d['file']:+.2f}* | *{d['function']:+.2f}* | "
              f"*{d['line']:+.2f}* | *{d['mean_fraction']:+.5f}* |")
        if g:
            print(f"| | | **+guard** | {fmt(g['ext_v2'])} |")
            dg = g["delta"]
            print(f"| | | ***delta*** | ***{dg['file']:+.2f}*** | ***{dg['function']:+.2f}*** | "
                  f"***{dg['line']:+.2f}*** | ***{dg['mean_fraction']:+.5f}*** |")
        stats_rows.append((s, "--ext-v2", stat_cell(u), u["n_changed"], n))
        if g:
            stats_rows.append((s, "+guard", stat_cell(g), g["n_changed"], n))

    print("\n### Paired significance (McNemar def-only/arm-only; Wilcoxon on line fraction)\n")
    print("| slice | arm | statistics | changed |")
    print("|---|---|---|---|")
    for s, arm, cell, nch, n in stats_rows:
        print(f"| {s} | {arm} | {cell} | {nch}/{n} |")

    print("\n### Ceiling recovery and displacement\n")
    print("| slice | EXT_V2 gold | default got | arm got | ceiling closed | non-ext gold lost | gained |")
    print("|---|---|---|---|---|---|---|")
    for s in order:
        for tag, suf in (("--ext-v2", "ext"), ("+guard", "guard")):
            p = D / f"{s}_{suf}_paired.json"
            if not p.exists():
                continue
            j = json.loads(p.read_text())
            c, dsp = j["ceiling"], j["displacement"]
            eg = c["ext_gold_files"]
            pct = f"{100*c['ext_gold_retrieved_ext']/eg:.1f}%" if eg else "n/a"
            print(f"| {s} ({tag}) | {eg} | {c['ext_gold_retrieved_default']} | "
                  f"{c['ext_gold_retrieved_ext']} | {pct} | {dsp['nonext_gold_lost']} | "
                  f"{dsp['nonext_gold_gained']} |")

    print("\n### Table B — goal scoreboard, stratified by gold-file count\n")
    sb = json.loads(a.scoreboard.read_text())
    print("| slice | arm | stratum | n | FILE | FUNCTION | LINE | line frac |")
    print("|---|---|---|---|---|---|---|---|")
    for label, d in sb.items():
        for st in ("all", "1", "2", "3+"):
            h = d["all"] if st == "all" else d["strata"][st]
            if not h["n"]:
                print(f"| {label} | | {st} | 0 | — | — | — | — |")
                continue
            print(f"| {label} | | {st} | {h['n']} | {h['file_pct']:.2f} | "
                  f"{h['function_pct']:.2f} | {h['line_pct']:.2f} | {h['mean_fraction']:.5f} |")


if __name__ == "__main__":
    main()
