#!/usr/bin/env python3
"""Free (NO API spend) post-hoc analysis extending growth_analysis.py's
convergence study to ALL FOUR v2 arms (grep, roust, roust_grep, rag_grep).

growth_analysis.py already established, for the grep arm, that its 11
turn-cap-outs were not retrieval failures: all 11 found and read_file'd the
gold file (median turn 4) then over-verified until the cap without ever
emitting FILES:. This module asks whether that is grep-specific or a
general agent pathology, across all four arms, and specifically:

  1. Of the FAILED runs per arm: how many ever SAW a gold file (path
     substring anywhere in resent context/reasoning) vs ever explicitly
     READ one (exact read_file tool-call match)? First-seen/first-read
     turn medians.
  2. Split FAILED runs into (a) NEVER ANSWERED (hit_turn_cap -- still
     issuing tool calls at the cap) vs (b) ANSWERED WRONG (emitted a
     FILES: line that didn't cover every gold file).
  3. rag_grep only: did the rag_search tool's OWN returned chunks contain
     the gold file (via tool_call_log's structured `files` list, the same
     dedup'd per-call file list rag_tool.py/roust_tool.py attach to each
     retrieval call -- ground truth, not a text-substring proxy)? If yes
     and the run still failed, that failure is a stopping failure, not a
     retrieval failure.
  4. roust_grep only: in failed runs, did the agent call roust at all, how
     many times, did roust's own result contain the gold file, and did the
     agent then wander off into grep/read_file calls that never re-anchor
     on the gold file? Two illustrative transcript excerpts.
  5. Synthesis, numbers not vibes.

Reads ONLY existing artifacts (results.jsonl + transcripts/*.jsonl) --
does not call the API, run the harness, or touch transcripts_forced/ or
results_forced.jsonl (a concurrently-running steelman sweep may be writing
those; this script never reads or writes them).

Usage: lab/tokenbench/.venv/bin/python3 lab/tokenbench/growth_analysis2.py
Output: lab/tokenbench/convergence_all_arms.json (+ tables printed to stdout)
"""

from __future__ import annotations

import json
import statistics as stats
from pathlib import Path
from typing import Any

from growth_analysis import (
    ARMS,
    TRANSCRIPTS_DIR,
    _normalize_path,
    build_turn_records,
    find_gold_touches,
    load_results,
    load_transcript,
)

TOKENBENCH_DIR = Path(__file__).resolve().parent
OUT_PATH = TOKENBENCH_DIR / "convergence_all_arms.json"


# ---------------------------------------------------------------------------
# helper: map each tool_call_log[i] entry (flat, in-call-order across the
# whole run -- see agent.py run_agent's `tool_call_log.append(call_meta)`
# inside the per-turn `for b in tool_use_blocks` loop, itself in
# response.content order) back to the turn number and tool name/input it
# came from, by walking the raw transcript in the same order.
# ---------------------------------------------------------------------------

def map_tool_calls_to_turns(lines: list[dict]) -> list[dict]:
    out = []
    for line in lines:
        turn = line["turn"]
        for b in line["response"]["content"]:
            if b.get("type") != "tool_use":
                continue
            out.append({"turn": turn, "name": b.get("name", ""), "input": b.get("input") or {}})
    return out


def _gold_in_path_list(paths: list[str], gold_files: list[str]) -> list[str]:
    """Gold files present (by the same exact/endswith normalization
    find_gold_touches uses) in a list of file paths (e.g. a retrieval
    call's `files` meta)."""
    norm_paths = [_normalize_path(p) for p in paths]
    hits = []
    for g in gold_files:
        for p in norm_paths:
            if p == g or p.endswith("/" + g) or g.endswith(p):
                hits.append(g)
                break
    return hits


# ---------------------------------------------------------------------------
# 1 + 2: per-arm failed-run gold-touch + failure-mode breakdown
# ---------------------------------------------------------------------------

def analyze_arm_failures(results: list[dict], arm: str) -> dict:
    arm_rows = [r for r in results if r["arm"] == arm and not r.get("error")]
    failed = [r for r in arm_rows if not r["success"]]

    detail = []
    for r in failed:
        lines = load_transcript(r["instance_id"], arm)
        turns = build_turn_records(lines, arm)
        touches = find_gold_touches(turns, r["gold_files"])
        seen_turns = [v["first_seen_turn"] for v in touches.values() if v["first_seen_turn"] is not None]
        read_turns = [v["first_read_turn"] for v in touches.values() if v["first_read_turn"] is not None]
        category = "never_answered" if r["hit_turn_cap"] else "answered_wrong"
        detail.append({
            "instance_id": r["instance_id"],
            "category": category,
            "gold_files": r["gold_files"],
            "returned_files": r["returned_files"],
            "turns_used": r["turns_used"],
            "any_gold_seen": len(seen_turns) > 0,
            "any_gold_read": len(read_turns) > 0,
            "all_gold_seen": all(v["first_seen_turn"] is not None for v in touches.values()),
            "all_gold_read": all(v["first_read_turn"] is not None for v in touches.values()),
            "first_seen_turn": min(seen_turns) if seen_turns else None,
            "first_read_turn": min(read_turns) if read_turns else None,
        })

    n_failed = len(detail)
    n_seen = sum(1 for d in detail if d["any_gold_seen"])
    n_read = sum(1 for d in detail if d["any_gold_read"])
    n_never_seen = n_failed - n_seen
    seen_turn_vals = sorted(d["first_seen_turn"] for d in detail if d["first_seen_turn"] is not None)
    read_turn_vals = sorted(d["first_read_turn"] for d in detail if d["first_read_turn"] is not None)

    n_never_answered = sum(1 for d in detail if d["category"] == "never_answered")
    n_answered_wrong = sum(1 for d in detail if d["category"] == "answered_wrong")

    return {
        "arm": arm,
        "n_total": len(arm_rows),
        "n_success": len(arm_rows) - n_failed,
        "n_failed": n_failed,
        "failure_mode_split": {
            "never_answered_hit_turn_cap": n_never_answered,
            "answered_wrong_files_line": n_answered_wrong,
        },
        "gold_touch_summary": {
            "n_ever_saw_a_gold_file": n_seen,
            "n_ever_read_a_gold_file": n_read,
            "n_never_saw_any_gold_file": n_never_seen,
            "first_seen_turn_median": stats.median(seen_turn_vals) if seen_turn_vals else None,
            "first_seen_turn_values": seen_turn_vals,
            "first_read_turn_median": stats.median(read_turn_vals) if read_turn_vals else None,
            "first_read_turn_values": read_turn_vals,
        },
        "failed_detail": detail,
    }


# ---------------------------------------------------------------------------
# 3: rag_grep -- did rag_search's OWN chunks contain the gold file?
# ---------------------------------------------------------------------------

def rag_grep_retrieval_check(results: list[dict]) -> dict:
    arm_rows = [r for r in results if r["arm"] == "rag_grep" and not r.get("error")]
    failed = [r for r in arm_rows if not r["success"]]
    succeeded = [r for r in arm_rows if r["success"]]

    def per_run(r: dict) -> dict:
        rag_calls = [c for c in r["tool_call_log"] if c.get("tool") == "rag_search"]
        n_calls = len(rag_calls)
        per_call_hits = []
        any_hit = False
        first_hit_call_idx = None
        for i, c in enumerate(rag_calls):
            hits = _gold_in_path_list(c.get("files", []), r["gold_files"])
            per_call_hits.append({"call_idx": i, "query_files_n": len(c.get("files", [])), "gold_hits": hits})
            if hits and first_hit_call_idx is None:
                first_hit_call_idx = i
                any_hit = True
            elif hits:
                any_hit = True
        return {
            "instance_id": r["instance_id"],
            "gold_files": r["gold_files"],
            "n_rag_search_calls": n_calls,
            "any_rag_call_returned_a_gold_file": any_hit,
            "first_hit_call_idx": first_hit_call_idx,
            "per_call": per_call_hits,
        }

    failed_detail = [per_run(r) for r in failed]
    succeeded_detail = [per_run(r) for r in succeeded]

    n_failed = len(failed_detail)
    n_failed_chunks_had_gold = sum(1 for d in failed_detail if d["any_rag_call_returned_a_gold_file"])
    n_failed_never_had_gold = n_failed - n_failed_chunks_had_gold
    n_succ_chunks_had_gold = sum(1 for d in succeeded_detail if d["any_rag_call_returned_a_gold_file"])

    return {
        "n_failed": n_failed,
        "n_failed_chunks_contained_gold_file": n_failed_chunks_had_gold,
        "n_failed_chunks_never_contained_gold_file": n_failed_never_had_gold,
        "n_succeeded": len(succeeded_detail),
        "n_succeeded_chunks_contained_gold_file": n_succ_chunks_had_gold,
        "interpretation": (
            "If n_failed_chunks_contained_gold_file > 0, rag_search's retrieved chunks DID surface the "
            "gold file in at least that many failed runs -- for those runs, the failure is not a "
            "retrieval-recall failure (the file was in the tool result); it is a stopping/verification "
            "failure, same shape as grep's. Remaining failures (n_failed_chunks_never_contained_gold_file) "
            "are genuine retrieval misses."
        ),
        "failed_detail": failed_detail,
        "succeeded_detail": succeeded_detail,
    }


# ---------------------------------------------------------------------------
# 4: roust_grep -- did roust get called, did it surface gold, did the agent
# then wander off into grep instead of committing?
# ---------------------------------------------------------------------------

def roust_grep_wandering_check(results: list[dict]) -> dict:
    arm_rows = [r for r in results if r["arm"] == "roust_grep" and not r.get("error")]
    failed = [r for r in arm_rows if not r["success"]]

    detail = []
    excerpts = []
    for r in failed:
        roust_calls = [c for c in r["tool_call_log"] if c.get("tool") == "roust"]
        n_roust_calls = len(roust_calls)
        roust_hit_gold = False
        first_hit_idx = None
        for i, c in enumerate(roust_calls):
            hits = _gold_in_path_list(c.get("files", []), r["gold_files"])
            if hits and first_hit_idx is None:
                first_hit_idx = i
                roust_hit_gold = True

        lines = load_transcript(r["instance_id"], "roust_grep")
        call_turns = map_tool_calls_to_turns(lines)
        roust_call_turns = [ct for ct in call_turns if ct["name"] == "roust"]
        first_hit_turn = roust_call_turns[first_hit_idx]["turn"] if first_hit_idx is not None else None

        post_hit_tool_counts: dict[str, int] = {}
        gold_re_touched_after_hit = False
        if first_hit_turn is not None:
            turns = build_turn_records(lines, "roust_grep")
            touches_after = {g: False for g in r["gold_files"]}
            for ct in call_turns:
                if ct["turn"] <= first_hit_turn:
                    continue
                post_hit_tool_counts[ct["name"]] = post_hit_tool_counts.get(ct["name"], 0) + 1
                if ct["name"] == "read_file":
                    p = _normalize_path((ct["input"] or {}).get("path", ""))
                    for g in r["gold_files"]:
                        if p == g or p.endswith("/" + g) or g.endswith(p):
                            touches_after[g] = True
            gold_re_touched_after_hit = any(touches_after.values())

        d = {
            "instance_id": r["instance_id"],
            "category": "never_answered" if r["hit_turn_cap"] else "answered_wrong",
            "gold_files": r["gold_files"],
            "returned_files": r["returned_files"],
            "n_roust_calls": n_roust_calls,
            "roust_ever_returned_gold_file": roust_hit_gold,
            "first_roust_hit_turn": first_hit_turn,
            "turns_used": r["turns_used"],
            "post_hit_tool_call_counts": post_hit_tool_counts,
            "read_file_on_gold_after_roust_hit": gold_re_touched_after_hit,
        }
        detail.append(d)

    n_failed = len(detail)
    n_called_roust = sum(1 for d in detail if d["n_roust_calls"] > 0)
    n_never_called_roust = n_failed - n_called_roust
    n_roust_hit_gold = sum(1 for d in detail if d["roust_ever_returned_gold_file"])
    n_roust_hit_gold_still_failed = n_roust_hit_gold  # by construction (all rows here are failures)
    n_roust_hit_but_never_reread_gold = sum(
        1 for d in detail if d["roust_ever_returned_gold_file"] and not d["read_file_on_gold_after_roust_hit"]
    )

    return {
        "n_failed": n_failed,
        "n_failed_that_called_roust_at_all": n_called_roust,
        "n_failed_that_never_called_roust": n_never_called_roust,
        "n_failed_where_roust_returned_gold_file": n_roust_hit_gold_still_failed,
        "n_failed_where_roust_hit_gold_but_never_read_file_on_gold_afterward": n_roust_hit_but_never_reread_gold,
        "detail": detail,
    }


def build_wandering_excerpts(results: list[dict], wandering: dict, n: int = 2) -> list[dict]:
    """Pull raw transcript excerpts (assistant text + tool calls) for `n`
    failed roust_grep runs where roust returned the gold file but the run
    still failed, spanning from the roust hit turn through the end of the
    run, to show what the agent did instead of committing."""
    arm_rows = {r["instance_id"]: r for r in results if r["arm"] == "roust_grep" and not r.get("error")}
    candidates = [d for d in wandering["detail"] if d["roust_ever_returned_gold_file"]]
    out = []
    for d in candidates[:n]:
        inst = d["instance_id"]
        lines = load_transcript(inst, "roust_grep")
        turn_events = []
        for line in lines:
            if line["turn"] < d["first_roust_hit_turn"]:
                continue
            resp = line["response"]
            texts = [b.get("text", "") for b in resp["content"] if b.get("type") == "text"]
            calls = [
                f"{b.get('name')}({json.dumps(b.get('input', {}))})"
                for b in resp["content"] if b.get("type") == "tool_use"
            ]
            turn_events.append({
                "turn": line["turn"],
                "assistant_text": "\n".join(t for t in texts if t.strip())[:600],
                "tool_calls": calls,
            })
        out.append({
            "instance_id": inst,
            "gold_files": d["gold_files"],
            "returned_files": d["returned_files"],
            "category": d["category"],
            "first_roust_hit_turn": d["first_roust_hit_turn"],
            "turns_used": d["turns_used"],
            "events_from_roust_hit_to_end": turn_events,
        })
    return out


# ---------------------------------------------------------------------------
# print helpers
# ---------------------------------------------------------------------------

def print_gold_touch_table(per_arm: dict) -> None:
    print("\n=== 1. FAILED-RUN GOLD-FILE TOUCH RATES (per arm) ===")
    header = f"{'arm':12}{'n_failed':>9}{'ever_saw':>10}{'ever_read':>10}{'never_saw':>10}{'seen_med':>10}{'read_med':>10}"
    print(header)
    for arm in ARMS:
        a = per_arm[arm]
        g = a["gold_touch_summary"]
        print(f"{arm:12}{a['n_failed']:>9}{g['n_ever_saw_a_gold_file']:>10}{g['n_ever_read_a_gold_file']:>10}"
              f"{g['n_never_saw_any_gold_file']:>10}"
              f"{'-' if g['first_seen_turn_median'] is None else g['first_seen_turn_median']:>10}"
              f"{'-' if g['first_read_turn_median'] is None else g['first_read_turn_median']:>10}")


def print_failure_mode_table(per_arm: dict) -> None:
    print("\n=== 2. FAILURE MODE SPLIT (per arm): never_answered (hit turn cap) vs answered_wrong (bad FILES:) ===")
    header = f"{'arm':12}{'n_failed':>9}{'never_answered':>16}{'answered_wrong':>16}"
    print(header)
    for arm in ARMS:
        a = per_arm[arm]
        s = a["failure_mode_split"]
        print(f"{arm:12}{a['n_failed']:>9}{s['never_answered_hit_turn_cap']:>16}{s['answered_wrong_files_line']:>16}")


def print_rag_check(rc: dict) -> None:
    print("\n=== 3. RAG_GREP: did rag_search's OWN returned chunks contain the gold file? ===")
    print(f"  failed runs: {rc['n_failed']}")
    print(f"    chunks CONTAINED gold file (retrieval succeeded, failure = stopping): "
          f"{rc['n_failed_chunks_contained_gold_file']}")
    print(f"    chunks NEVER contained gold file (genuine retrieval miss):            "
          f"{rc['n_failed_chunks_never_contained_gold_file']}")
    print(f"  (context) succeeded runs where chunks contained gold file: "
          f"{rc['n_succeeded_chunks_contained_gold_file']}/{rc['n_succeeded']}")
    for d in rc["failed_detail"]:
        print(f"    {d['instance_id']:38} n_rag_calls={d['n_rag_search_calls']:>2} "
              f"chunks_had_gold={d['any_rag_call_returned_a_gold_file']!s:5} "
              f"first_hit_call_idx={d['first_hit_call_idx']}")


def print_roust_grep_wandering(wc: dict) -> None:
    print("\n=== 4. ROUST_GREP: did the agent call roust, get gold, then wander off with grep? ===")
    print(f"  failed runs: {wc['n_failed']}")
    print(f"    called roust at all:                    {wc['n_failed_that_called_roust_at_all']}")
    print(f"    never called roust:                     {wc['n_failed_that_never_called_roust']}")
    print(f"    roust returned the gold file AND still failed:  {wc['n_failed_where_roust_returned_gold_file']}")
    print(f"    ...of those, never read_file'd gold again afterward: "
          f"{wc['n_failed_where_roust_hit_gold_but_never_read_file_on_gold_afterward']}")
    for d in wc["detail"]:
        print(f"    {d['instance_id']:38} category={d['category']:15} n_roust_calls={d['n_roust_calls']} "
              f"roust_hit_gold={d['roust_ever_returned_gold_file']!s:5} "
              f"first_hit_turn={d['first_roust_hit_turn']} turns_used={d['turns_used']} "
              f"post_hit_tools={d['post_hit_tool_call_counts']}")


def print_excerpts(excerpts: list[dict]) -> None:
    print("\n=== 4b. TRANSCRIPT EXCERPTS: roust hit gold, run still failed ===")
    for ex in excerpts:
        print(f"\n  --- {ex['instance_id']} (gold={ex['gold_files']}, returned={ex['returned_files']}, "
              f"category={ex['category']}, roust hit gold at turn {ex['first_roust_hit_turn']}, "
              f"run ended turn {ex['turns_used']}) ---")
        for ev in ex["events_from_roust_hit_to_end"]:
            print(f"    turn {ev['turn']}: tool_calls={ev['tool_calls']}")
            if ev["assistant_text"]:
                print(f"      text: {ev['assistant_text'][:300]!r}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    results = load_results()

    per_arm = {arm: analyze_arm_failures(results, arm) for arm in ARMS}
    print_gold_touch_table(per_arm)
    print_failure_mode_table(per_arm)

    rag_check = rag_grep_retrieval_check(results)
    print_rag_check(rag_check)

    roust_wander = roust_grep_wandering_check(results)
    print_roust_grep_wandering(roust_wander)

    excerpts = build_wandering_excerpts(results, roust_wander, n=2)
    print_excerpts(excerpts)

    # ---- synthesis ----
    total_failed = sum(a["n_failed"] for a in per_arm.values())
    total_seen = sum(a["gold_touch_summary"]["n_ever_saw_a_gold_file"] for a in per_arm.values())
    total_read = sum(a["gold_touch_summary"]["n_ever_read_a_gold_file"] for a in per_arm.values())
    per_arm_stopping_fraction = {
        arm: (
            per_arm[arm]["gold_touch_summary"]["n_ever_read_a_gold_file"] / per_arm[arm]["n_failed"]
            if per_arm[arm]["n_failed"] else None
        )
        for arm in ARMS
    }
    synthesis = {
        "total_failed_runs_all_arms": total_failed,
        "total_ever_saw_gold_file": total_seen,
        "total_ever_read_gold_file": total_read,
        "fraction_of_failures_that_are_stopping_failures_per_arm_read_gold_over_failed": per_arm_stopping_fraction,
        "rag_grep_chunks_contained_gold_in_failed_runs": rag_check["n_failed_chunks_contained_gold_file"],
        "rag_grep_n_failed": rag_check["n_failed"],
        "roust_grep_failed_where_roust_hit_gold": roust_wander["n_failed_where_roust_returned_gold_file"],
        "roust_grep_n_failed": roust_wander["n_failed"],
    }

    out = {
        "per_arm_failure_analysis": per_arm,
        "rag_grep_retrieval_check": rag_check,
        "roust_grep_wandering_check": roust_wander,
        "roust_grep_excerpts": excerpts,
        "synthesis_numbers": synthesis,
    }
    OUT_PATH.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n=== wrote {OUT_PATH} ===")


if __name__ == "__main__":
    main()
