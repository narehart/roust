#!/usr/bin/env python3
"""Steelman experiment summary: grep vs roust (from results.jsonl, v2 run)
vs grep_forced vs roust_forced (from results_forced.jsonl), restricted to
the 15 instances the v2 run covered (paired comparison).

Adds the failure-mode breakdown the headline summarize.py doesn't do:
for every failing row, "never_answered" (no FILES: line parsed) vs
"answered_wrong" (a FILES: line was parsed but it didn't match gold) --
this is the whole point of the steelman test (see task spec).

Usage:
    lab/tokenbench/.venv/bin/python3 lab/tokenbench/summarize_steelman.py
"""

from __future__ import annotations

import json
import statistics as stats
from collections import defaultdict
from pathlib import Path

TOKENBENCH_DIR = Path(__file__).resolve().parent
INSTANCES_FILE = TOKENBENCH_DIR / "instances_steelman.txt"
BASE_RESULTS = TOKENBENCH_DIR / "results.jsonl"
FORCED_RESULTS = TOKENBENCH_DIR / "results_forced.jsonl"

ARM_ORDER = ["grep", "roust", "grep_forced", "roust_forced"]


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def failure_mode(row: dict) -> str | None:
    """Returns None if the row succeeded, else one of:
    'never_answered' (no FILES: line ever parsed -- includes turn-cap-outs
    with no answer, and errors), 'answered_wrong' (a FILES: line was
    present but didn't cover every gold file)."""
    if row.get("success"):
        return None
    returned = row.get("returned_files")
    if row.get("error"):
        return "never_answered" if returned is None else "answered_wrong"
    if returned is None:
        return "never_answered"
    return "answered_wrong"


def main() -> None:
    instances = {ln.strip() for ln in INSTANCES_FILE.read_text().splitlines() if ln.strip()}
    print(f"=== steelman summary: {len(instances)} paired instances "
          f"(same set as v2 grep/roust run) ===\n")

    base_rows = [r for r in load_rows(BASE_RESULTS) if r["instance_id"] in instances]
    forced_rows = [r for r in load_rows(FORCED_RESULTS) if r["instance_id"] in instances]
    all_rows = base_rows + forced_rows

    by_arm: dict[str, list[dict]] = defaultdict(list)
    for r in all_rows:
        by_arm[r.get("arm")].append(r)

    header = (f"{'arm':14} {'n':>4} {'success%':>9} {'med_tok':>9} {'mean_tok':>9} "
              f"{'med_turns':>10} {'med_tools':>10} {'hit_cap%':>9} "
              f"{'never_ans':>10} {'ans_wrong':>10}")
    print(header)
    print("-" * len(header))
    for a in ARM_ORDER:
        rows = by_arm.get(a, [])
        if not rows:
            print(f"{a:14} (no rows)")
            continue
        n = len(rows)
        succ = sum(1 for r in rows if r.get("success")) / n * 100
        toks = [r.get("tiktoken_total_tokens", 0) for r in rows]
        turns = [r.get("turns_used", 0) for r in rows]
        tools = [r.get("tool_calls", 0) for r in rows]
        hit_cap = sum(1 for r in rows if r.get("hit_turn_cap")) / n * 100
        modes = [failure_mode(r) for r in rows]
        never = sum(1 for m in modes if m == "never_answered")
        wrong = sum(1 for m in modes if m == "answered_wrong")
        print(f"{a:14} {n:>4} {succ:>8.1f}% {stats.median(toks):>9.0f} {stats.mean(toks):>9.0f} "
              f"{stats.median(turns):>10.1f} {stats.median(tools):>10.1f} {hit_cap:>8.1f}% "
              f"{never:>10} {wrong:>10}")

    print("\n=== per-instance detail (grep, roust, grep_forced, roust_forced) ===")
    row_by = {(r["instance_id"], r["arm"]): r for r in all_rows}
    for iid in sorted(instances):
        cells = []
        for a in ARM_ORDER:
            r = row_by.get((iid, a))
            if not r:
                cells.append(f"{a}=MISSING")
                continue
            if r.get("success"):
                tag = "OK"
            else:
                tag = failure_mode(r) or "FAIL"
            cells.append(f"{a}={tag}/t{r.get('turns_used','-')}")
        print(f"  {iid:38} " + "  ".join(cells))

    missing_forced = [iid for iid in sorted(instances)
                       if (iid, "grep_forced") not in row_by or (iid, "roust_forced") not in row_by]
    if missing_forced:
        print(f"\nWARNING: {len(missing_forced)}/{len(instances)} instances missing a forced-arm row "
              f"(budget cap or in-progress run): {missing_forced}")


if __name__ == "__main__":
    main()
