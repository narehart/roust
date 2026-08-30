"""E29 residual-cost probe: at a LARGE budget, what does breadth still cost?

E29's curve arms move the cap and the budget together, and its decomposition
arm (a5: cap 16 @ 24576) holds the cap still while the budget moves. Pairing
a4 against a5 does the complementary thing -- both arms sit at 24576, and only
the cap differs. That isolates the quantity E28 could not see:

    the cost of breadth WHEN THE BUDGET IS NOT THE BINDING CONSTRAINT.

E28 measured that cost at a fixed 8192 and found it negative everywhere on
FUNCTION/LINE. If the same comparison at 24576 comes back null, then E28's
depth cost was a property of the budget it was measured under, not of breadth
itself -- while the FILE gain, which E29 shows is budget-invariant, survives.

Usage:
  uv run --no-project --with scipy python lab/e29_residual.py --dir DIR
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e29_common import (load_records, load_function_detail,  # noqa: E402
                        headline, mcnemar_exact)
from scipy import stats  # noqa: E402

SLICES = [("jsts", "JS/TS"), ("java", "Java"), ("go", "Go"), ("rust", "Rust"),
          ("c", "C"), ("cpp", "C++"), ("ver", "Python Verified")]
LO, HI = "a5_c16b24576", "a4_c32b24576"   # same budget, cap 16 vs cap 32


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, type=Path)
    args = ap.parse_args()
    out = {}
    print("## Residual cost of breadth at 24576 (cap 32 vs cap 16, budget held)\n")
    print("| slice | dFILE | McNemar FILE | dFUNCTION | McNemar FUNCTION "
          "| dfrac | Wilcoxon frac |")
    print("|---|---|---|---|---|---|---|")
    for s, lab in SLICES:
        lo_r = load_records(args.dir / "arms" / f"{s}_{LO}.jsonl")
        lo_f = load_function_detail(args.dir / "metrics" / f"{s}_{LO}.json")
        hi_r = load_records(args.dir / "arms" / f"{s}_{HI}.jsonl")
        hi_f = load_function_detail(args.dir / "metrics" / f"{s}_{HI}.json")
        ids = sorted(set(lo_r) & set(hi_r))
        h_lo, h_hi = headline(lo_r, lo_f, ids), headline(hi_r, hi_f, ids)
        mc_file = mcnemar_exact([((lo_r[i].get("hunk_file_covered") or 0) == 1.0,
                                  (hi_r[i].get("hunk_file_covered") or 0) == 1.0)
                                 for i in ids])
        mc_func = mcnemar_exact([(lo_f.get(i, False), hi_f.get(i, False)) for i in ids])
        f_lo = [lo_r[i].get("hunk_line_recall") or 0 for i in ids]
        f_hi = [hi_r[i].get("hunk_line_recall") or 0 for i in ids]
        nz = [a - b for a, b in zip(f_hi, f_lo) if a != b]
        p = float(stats.wilcoxon(nz, alternative="two-sided").pvalue) if nz else 1.0
        out[s] = {"n": len(ids),
                  "delta_file": round(h_hi["file_pct"] - h_lo["file_pct"], 2),
                  "delta_function": round(h_hi["function_pct"] - h_lo["function_pct"], 2),
                  "delta_fraction": round(h_hi["mean_fraction"] - h_lo["mean_fraction"], 6),
                  "file_mcnemar": mc_file, "function_mcnemar": mc_func,
                  "fraction_wilcoxon_p": p}
        print(f"| {lab} | {h_hi['file_pct'] - h_lo['file_pct']:+.2f} "
              f"| {mc_file['b_def_only']}/{mc_file['c_arm_only']}, p={mc_file['p']:.4f} "
              f"| {h_hi['function_pct'] - h_lo['function_pct']:+.2f} "
              f"| {mc_func['b_def_only']}/{mc_func['c_arm_only']}, p={mc_func['p']:.4f} "
              f"| {h_hi['mean_fraction'] - h_lo['mean_fraction']:+.5f} | p={p:.4f} |")
    (args.dir / "residual.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
