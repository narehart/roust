"""E29 shared metric helpers, vendored so the E29 rig is self-contained.

These four functions are lifted VERBATIM from `lab/e28_paired.py` (E28's
analysis, campaign #4 wave 6) so that E29's scripts do not import from an
untracked file. The definitions are byte-identical to E28's; E29's outputs
were re-generated after the move and diffed to confirm no numbers changed.

  load_records          -- instance_id -> record, from an arm's JSONL
  load_function_detail  -- instance_id -> bool, from a scorer's metric JSON
  headline              -- FILE/FUNCTION/LINE/fraction + the COST columns
                           (mean files returned, mean bundle tokens), averaged
                           over OK records only so an errored record with no
                           bundle cannot understate the cost
  mcnemar_exact         -- exact (binomial, two-sided) McNemar on paired booleans
"""

from __future__ import annotations

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
