"""E25 table assembler: emits the round's markdown tables straight from the
paired artifacts, so no number in the writeup is hand-transcribed."""
from __future__ import annotations
import json
from pathlib import Path

R = Path("/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e25")
SLICES = [("jsts", "jsts"), ("java", "java"), ("go", "go"), ("rust", "rust"),
          ("c", "c"), ("cpp", "cpp"),
          ("python Lite", "lite300"), ("python Verified", "ver407")]

print("| slice | n | arm | FILE | FUNCTION (exact) | LINE (all-or-nothing) | line mean-fraction |")
print("|---|---|---|---|---|---|---|")
for name, key in SLICES:
    f = R / f"{key}_paired.json"
    if not f.exists():
        print(f"| {name} | - | (pending) | | | | |")
        continue
    d = json.loads(f.read_text())
    de, sh, dl = d["default"], d["shape"], d["delta"]
    print(f"| **{name}** | {de['n']} | default | {de['file_pct']:.2f} ({de['file_n']}) | "
          f"{de['function_pct']:.2f} ({de['function_n']}) | {de['line_pct']:.2f} ({de['line_n']}) | "
          f"{de['mean_fraction']:.5f} |")
    print(f"| | | shape | {sh['file_pct']:.2f} ({sh['file_n']}) | {sh['function_pct']:.2f} ({sh['function_n']}) | "
          f"{sh['line_pct']:.2f} ({sh['line_n']}) | {sh['mean_fraction']:.5f} |")
    print(f"| | | **delta** | {dl['file']:+.2f} | {dl['function']:+.2f} | {dl['line']:+.2f} | "
          f"{dl['mean_fraction']:+.5f} |")

print()
print("| slice | McNemar FILE (def-only/shape-only, p) | FUNCTION | LINE | Wilcoxon fraction (up/down, p) | changed |")
print("|---|---|---|---|---|---|")
for name, key in SLICES:
    f = R / f"{key}_paired.json"
    if not f.exists():
        print(f"| {name} | (pending) | | | | |")
        continue
    d = json.loads(f.read_text())
    s = d["paired_stats"]
    def mc(m):
        return f"{s[m]['b_def_only']}/{s[m]['c_shape_only']}, p={s[m]['p']:.4f}"
    w = s["fraction_wilcoxon"]
    wtxt = ("no change" if w["n_nonzero"] == 0
            else f"{w['n_up']}/{w['n_down']}, p={w['p']:.4f}")
    print(f"| **{name}** | {mc('FILE')} | {mc('FUNCTION')} | {mc('LINE')} | {wtxt} | "
          f"{d['n_changed']}/{d['default']['n']} |")


def drift_table() -> str:
    rows = json.loads((R / "drift_audit.json").read_text())
    out = ["| slice | committed baseline (engine) | FILE | FUNCTION | LINE | frac | abb96af default | drift |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        b, n, d = r["baseline"], r["abb96af_default"], r["drift"]
        drift = ("**none**" if not any(d.values()) else
                 f"FILE {d['file']:+.2f} / FUNC {d['function']:+.2f} / "
                 f"LINE {d['line']:+.2f} / frac {d['mean_fraction']:+.5f}")
        out.append(f"| **{r['slice']}** | `{r['baseline_artifact']}` ({b['sha']}) | "
                   f"{b['file']:.2f} | {b['function']:.2f} | {b['line']:.2f} | {b['mean_fraction']:.5f} | "
                   f"{n['file']:.2f}/{n['function']:.2f}/{n['line']:.2f}/{n['mean_fraction']:.5f} | {drift} |")
    return "\n".join(out)


def gap_table() -> str:
    out = ["| slice | gold files | emitted by both | allowlist-only: TRUE field-rule misses | allowlist-only: one-line only | shape-only (false positives) |",
           "|---|---|---|---|---|---|"]
    for lang in ("jsts", "java", "go", "rust", "c", "cpp"):
        d = json.loads((R / f"gap_{lang}.json").read_text())
        def top(key, k=3):
            items = sorted(d[key].items(), key=lambda x: -x[1])[:k]
            return ", ".join(f"`{a}` {b}" for a, b in items) or "—"
        ml = sum(d["allowlist_only_multiline"].values())
        ol = sum(d["allowlist_only_oneline"].values())
        so = sum(d["shape_only"].values())
        out.append(f"| **{lang}** | {d['n_gold_files']} | {sum(d['both'].values())} | "
                   f"**{ml}** — {top('allowlist_only_multiline')} | {ol} — {top('allowlist_only_oneline', 2)} | "
                   f"{so} — {top('shape_only')} |")
    return "\n".join(out)
