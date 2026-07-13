#!/usr/bin/env python3
"""Free (NO API spend) post-hoc analysis of existing tokenbench v2
transcripts: models what a higher turn cap would cost the grep arm, and
whether grep's 11/15 turn-cap-outs are converging (agent closing in on the
gold file) or flailing (never touching it).

Reads ONLY existing artifacts:
  lab/tokenbench/results.jsonl        (per-(instance,arm) summary rows)
  lab/tokenbench/transcripts/*.jsonl  (per-turn request/response log)

Does NOT call the Anthropic API, run the harness, or spend any budget.

Per-turn tiktoken reconstruction reproduces agent.py's own accounting
EXACTLY (system prompt text + resent message history each turn, tiktoken
cl100k_base) so the growth curve is the harness's own headline metric, not
a reimplementation-drift approximation. Validated: summing the
reconstructed per-turn tokens up to `turns_used` reproduces
`tiktoken_total_tokens` in results.jsonl bit-for-bit for every non-error
row (see `_validate_against_results`).

Usage: lab/tokenbench/.venv/bin/python3 lab/tokenbench/growth_analysis.py
Output: lab/tokenbench/growth_analysis.json (+ tables printed to stdout)
"""

from __future__ import annotations

import json
import statistics as stats
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from common import count_tokens

TOKENBENCH_DIR = Path(__file__).resolve().parent
RESULTS_PATH = TOKENBENCH_DIR / "results.jsonl"
TRANSCRIPTS_DIR = TOKENBENCH_DIR / "transcripts"
OUT_PATH = TOKENBENCH_DIR / "growth_analysis.json"

ARMS = ["grep", "roust", "roust_grep", "rag_grep"]
CHECKPOINTS = [5, 10, 15, 20, 25, 30]
EXTRAPOLATE_TO = [45, 60, 100, 150]

# ---------------------------------------------------------------------------
# Reproduced verbatim from agent.py (system prompt text + message serializer)
# so the reconstructed per-turn token counts match the harness's own
# tiktoken accounting exactly. Transcripts already store request_messages /
# response.content as plain dicts (agent.py logs `_block_to_dict(b)`), so no
# SDK-object handling is needed here.
# ---------------------------------------------------------------------------

ARM_TOOLS = {
    "grep": ["run_command", "read_file"],
    "roust": ["roust", "read_file"],
    "roust_grep": ["roust", "run_command", "read_file"],
    "rag_grep": ["rag_search", "run_command", "read_file"],
}

_TOOL_LINES = {
    "run_command": "- run_command: run a single read-only search/exploration command using rg (ripgrep), "
                   "grep, find, ls, head, or sed (for a line-range read, e.g. `sed -n '120,160p' path/to/file.py`).",
    "read_file": "- read_file: read a specific line range of a specific file (path, start_line, end_line). "
                 "Prefer narrow ranges around a hit over reading whole files top to bottom -- it costs you "
                 "tokens and turns to dump whole files, so don't.",
    "roust": "- roust: a recall-first code-retrieval tool built for agents -- call it with a query (the issue "
             "text, an error string, a symbol name, or a refined query) and it returns a token-budgeted bundle "
             "of the files/regions it judges most relevant, ranked, with source packed in.",
    "rag_search": "- rag_search: semantic (embedding) search -- call it with a query and it returns the top "
                  "matching code chunks, ranked by cosine similarity, with file path/line range and source text. "
                  "Semantic similarity is not the same as 'this file needs to change'.",
}

_OPENING_HINT = {
    "grep": "Lead with a targeted rg/grep search for the strongest signal in the issue text (error messages, "
            "tracebacks, class/function/identifier names), then follow the trail (imports, call sites, the "
            "test file(s) that exercise the behavior).",
    "roust": "Call roust with the issue text (or a refined query) as your first move -- it is your only search "
             "tool -- then use read_file to verify/expand on specific hits.",
    "roust_grep": "Call roust with the issue text (or a refined query) as your first move, then use "
                  "run_command/read_file to verify hits or search for anything roust's bundle didn't cover.",
    "rag_grep": "Call rag_search with the issue text (or a refined query) as your first move, then use "
                "run_command/read_file to verify hits or search for anything the retrieved chunks didn't cover.",
}

SYSTEM_PROMPT_TAIL = """
Avoid unfocused exploration (e.g. listing every file with no filter) and avoid reading large files in full -- \
both burn turns and tokens without adding precision.

Answer with FILES: as soon as you are confident. Additional exploration costs tokens and does not improve \
your score. Do not verify beyond what you need -- once the evidence converges on the right file(s), stop \
investigating and answer immediately; do not spend further turns double-checking a conclusion you already \
trust.

When you are confident you have found every file that needs to change, respond with NO further tool calls, \
and end your message with a line of exactly this form:

FILES: path/to/file1.py, path/to/file2.py

List repo-relative paths (as they would appear in `git diff`), comma-separated, on that one line. Only list \
files that need to be *edited* to fix the issue; do not include files you merely inspected along the way."""


def build_system_prompt(arm: str) -> str:
    tool_names = ARM_TOOLS[arm]
    tools_block = "\n".join(_TOOL_LINES[t] for t in tool_names)
    head = (
        "You are an expert code-localization agent. Given a GitHub issue/problem statement and read-only "
        "access to a cloned repository, your job is to identify EVERY file that must be edited to fix the "
        "issue -- not files that are merely related or worth glancing at, but the specific files a correct "
        "patch would touch.\n\nYou have the following tools:\n" + tools_block + "\n\n" + _OPENING_HINT[arm]
    )
    return head + SYSTEM_PROMPT_TAIL


def _serialize_text(role_content: Any) -> str:
    if isinstance(role_content, str):
        return role_content
    parts = []
    for d in role_content:
        t = d.get("type")
        if t == "text":
            parts.append(d.get("text", ""))
        elif t == "tool_use":
            parts.append(f"{d.get('name', '')}({json.dumps(d.get('input', {}))})")
        elif t == "tool_result":
            c = d.get("content", "")
            parts.append(c if isinstance(c, str) else json.dumps(c))
        else:
            parts.append(json.dumps(d, default=str))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Transcript loading / per-turn reconstruction
# ---------------------------------------------------------------------------

def load_results() -> list[dict]:
    return [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]


def load_transcript(instance_id: str, arm: str) -> list[dict]:
    path = TRANSCRIPTS_DIR / f"{instance_id}__{arm}.jsonl"
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def build_turn_records(lines: list[dict], arm: str) -> list[dict]:
    """Per turn: request_text/response_text (for gold-file substring search),
    tiktoken in/out, cumulative tiktoken total, real API usage in/out, and
    the raw response content (for tool_use inspection)."""
    system_prompt = build_system_prompt(arm)
    out = []
    cumulative = 0
    for line in lines:
        msgs = line["request_messages"]
        request_text = system_prompt + "\n\n" + "\n\n".join(
            f"[{m['role']}]\n{_serialize_text(m['content'])}" for m in msgs
        )
        tin = count_tokens(request_text)
        resp = line["response"]
        response_text = _serialize_text(resp["content"])
        tout = count_tokens(response_text)
        cumulative += tin + tout
        usage = resp.get("usage", {}) or {}
        out.append({
            "turn": line["turn"],
            "request_text": request_text,
            "response_text": response_text,
            "response_content": resp["content"],
            "tiktoken_in": tin,
            "tiktoken_out": tout,
            "cumulative_tokens": cumulative,
            "api_input_tokens": usage.get("input_tokens", 0),
            "api_output_tokens": usage.get("output_tokens", 0),
        })
    return out


def _validate_against_results(results: list[dict]) -> list[str]:
    """Sanity check: reconstructed cumulative tiktoken total at turns_used
    must equal results.jsonl's tiktoken_total_tokens for every clean
    (non-error) row. Returns a list of mismatch descriptions (empty = all
    match)."""
    mismatches = []
    for r in results:
        if r.get("error"):
            continue
        try:
            lines = load_transcript(r["instance_id"], r["arm"])
        except FileNotFoundError:
            mismatches.append(f"{r['instance_id']}/{r['arm']}: transcript missing")
            continue
        turns = build_turn_records(lines, r["arm"])
        if not turns:
            continue
        reconstructed = turns[-1]["cumulative_tokens"]
        expected = r["tiktoken_total_tokens"]
        if reconstructed != expected:
            mismatches.append(
                f"{r['instance_id']}/{r['arm']}: reconstructed={reconstructed} vs results.jsonl={expected}"
            )
    return mismatches


# ---------------------------------------------------------------------------
# 1. Token growth curve per arm
# ---------------------------------------------------------------------------

def growth_curve_per_arm(results: list[dict]) -> dict:
    """For each arm, the median cumulative-token curve across runs at every
    turn number reached by at least one run (dense), plus the checkpoint
    table (5/10/15/20/25/30) and linear/quadratic/cubic fits (least-squares
    over the dense per-turn median curve)."""
    out = {}
    for arm in ARMS:
        arm_rows = [r for r in results if r["arm"] == arm and not r.get("error")]
        per_run_curves = []
        for r in arm_rows:
            lines = load_transcript(r["instance_id"], arm)
            turns = build_turn_records(lines, arm)
            per_run_curves.append({t["turn"]: t["cumulative_tokens"] for t in turns})

        max_turn = max((max(c.keys()) for c in per_run_curves if c), default=0)
        dense_turns = list(range(1, max_turn + 1))
        dense_median = []
        dense_n = []
        for t in dense_turns:
            vals = [c[t] for c in per_run_curves if t in c]
            if vals:
                dense_median.append(stats.median(vals))
                dense_n.append(len(vals))
            else:
                dense_median.append(None)
                dense_n.append(0)

        # checkpoint table: median across runs that reached >= that turn
        # (using the run's value AT that turn, i.e. the run must have a
        # turn-N entry -- runs that stopped earlier don't contribute, since
        # "tokens at turn N" is undefined for a run that answered at turn
        # < N).
        checkpoint_table = {}
        for cp in CHECKPOINTS:
            vals = [c[cp] for c in per_run_curves if cp in c]
            checkpoint_table[cp] = {
                "median_tokens": stats.median(vals) if vals else None,
                "n_runs_reaching": len(vals),
                "n_runs_total": len(per_run_curves),
            }

        # fit on the dense median curve (only points with data)
        xs = np.array([t for t, m in zip(dense_turns, dense_median) if m is not None], dtype=float)
        ys = np.array([m for m in dense_median if m is not None], dtype=float)
        fits = {}
        if len(xs) >= 4:
            for deg, name in [(1, "linear"), (2, "quadratic"), (3, "cubic")]:
                coefs = np.polyfit(xs, ys, deg)
                pred = np.polyval(coefs, xs)
                ss_res = float(np.sum((ys - pred) ** 2))
                ss_tot = float(np.sum((ys - np.mean(ys)) ** 2))
                r2 = 1 - ss_res / ss_tot if ss_tot > 0 else None
                fits[name] = {"coefficients_high_to_low": coefs.tolist(), "r2": r2}
        # also try a power-law fit tokens ~ a * turn^b (common for superlinear
        # growth with a non-integer exponent), via log-log least squares on
        # turn>=1 data
        if len(xs) >= 4 and np.all(xs > 0) and np.all(ys > 0):
            log_x, log_y = np.log(xs), np.log(ys)
            b, log_a = np.polyfit(log_x, log_y, 1)
            pred_log = b * log_x + log_a
            ss_res = float(np.sum((log_y - pred_log) ** 2))
            ss_tot = float(np.sum((log_y - np.mean(log_y)) ** 2))
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else None
            fits["power_law"] = {"a": float(np.exp(log_a)), "b": float(b), "r2_on_log_log": r2}

        out[arm] = {
            "n_runs": len(arm_rows),
            "checkpoint_table": checkpoint_table,
            "fits": fits,
            "dense_curve_turns": dense_turns,
            "dense_curve_median_tokens": dense_median,
            "dense_curve_n_runs": dense_n,
        }
    return out


# ---------------------------------------------------------------------------
# 2. Grep extrapolation
# ---------------------------------------------------------------------------

def extrapolate_grep(growth: dict) -> dict:
    grep_fits = growth["grep"]["fits"]
    out = {"note": "EXTRAPOLATION beyond observed data (grep runs only observed to turn 30 max). "
                    "Quadratic fit is on the dense median-cumulative-tokens-per-turn curve "
                    "(turns 1..30, medians of however many of the 15 grep runs reached each turn).",
           "fit_used": "quadratic",
           "fit_quality_r2": grep_fits.get("quadratic", {}).get("r2"),
           "all_fit_quality_r2": {k: v.get("r2", v.get("r2_on_log_log")) for k, v in grep_fits.items()},
           "extrapolated_median_tokens": {}}
    quad = grep_fits.get("quadratic")
    if quad:
        coefs = quad["coefficients_high_to_low"]
        for n in EXTRAPOLATE_TO:
            out["extrapolated_median_tokens"][n] = float(np.polyval(coefs, n))
    lin = grep_fits.get("linear")
    if lin:
        out.setdefault("extrapolated_median_tokens_linear_fit", {})
        for n in EXTRAPOLATE_TO:
            out["extrapolated_median_tokens_linear_fit"][n] = float(np.polyval(lin["coefficients_high_to_low"], n))
    return out


# ---------------------------------------------------------------------------
# 3/4. Convergence signal: gold-file touch detection
# ---------------------------------------------------------------------------

def _normalize_path(p: str) -> str:
    p = p.strip()
    if p.startswith("./"):
        p = p[2:]
    return p


def find_gold_touches(turns: list[dict], gold_files: list[str]) -> dict:
    """For each gold file: first_seen_turn (first turn whose cumulative
    resent context -- request_text -- or that turn's own response_text
    contains the gold path as a substring, i.e. it surfaced in a
    find/grep/ls output, a read_file call, or the model's own reasoning
    text) and first_read_turn (first turn the model issued a read_file
    tool_use call whose path resolves to that gold file)."""
    touches = {g: {"first_seen_turn": None, "first_read_turn": None} for g in gold_files}
    for t in turns:
        haystack = t["request_text"] + "\n" + t["response_text"]
        for g in gold_files:
            if touches[g]["first_seen_turn"] is None and g in haystack:
                touches[g]["first_seen_turn"] = t["turn"]
        for b in t["response_content"]:
            if b.get("type") != "tool_use":
                continue
            if b.get("name") != "read_file":
                continue
            p = _normalize_path((b.get("input") or {}).get("path", ""))
            for g in gold_files:
                if touches[g]["first_read_turn"] is None and (p == g or p.endswith("/" + g) or g.endswith(p)):
                    touches[g]["first_read_turn"] = t["turn"]
    return touches


def convergence_analysis(results: list[dict], arm: str) -> dict:
    arm_rows = [r for r in results if r["arm"] == arm and not r.get("error")]
    succeeded = [r for r in arm_rows if r["success"]]
    failed_capped = [r for r in arm_rows if r["hit_turn_cap"]]
    failed_other = [r for r in arm_rows if not r["success"] and not r["hit_turn_cap"]]

    succeeded_detail = []
    for r in succeeded:
        lines = load_transcript(r["instance_id"], arm)
        turns = build_turn_records(lines, arm)
        touches = find_gold_touches(turns, r["gold_files"])
        seen_turns = [v["first_seen_turn"] for v in touches.values() if v["first_seen_turn"] is not None]
        read_turns = [v["first_read_turn"] for v in touches.values() if v["first_read_turn"] is not None]
        all_read = all(v["first_read_turn"] is not None for v in touches.values())
        succeeded_detail.append({
            "instance_id": r["instance_id"],
            "answered_at_turn": r["turns_used"],
            "gold_files": r["gold_files"],
            "gold_touches": touches,
            "earliest_gold_seen_turn": min(seen_turns) if seen_turns else None,
            "all_gold_files_read_before_answer": all_read,
        })

    capped_detail = []
    for r in failed_capped:
        lines = load_transcript(r["instance_id"], arm)
        turns = build_turn_records(lines, arm)
        touches = find_gold_touches(turns, r["gold_files"])
        seen_turns = [v["first_seen_turn"] for v in touches.values() if v["first_seen_turn"] is not None]
        read_turns = [v["first_read_turn"] for v in touches.values() if v["first_read_turn"] is not None]
        any_seen = len(seen_turns) > 0
        any_read = len(read_turns) > 0
        all_seen = all(v["first_seen_turn"] is not None for v in touches.values())
        capped_detail.append({
            "instance_id": r["instance_id"],
            "gold_files": r["gold_files"],
            "gold_touches": touches,
            "any_gold_file_ever_seen": any_seen,
            "any_gold_file_ever_read": any_read,
            "all_gold_files_seen": all_seen,
            "earliest_gold_seen_turn": min(seen_turns) if seen_turns else None,
            "earliest_gold_read_turn": min(read_turns) if read_turns else None,
            "last_turn": r["turns_used"],
            # "converging" heuristic: touched a gold file (seen or read) at
            # some point AND that touch happened in the back half of the run
            # (turn >= last_turn/2) is weak evidence of narrowing rather than
            # early-and-abandoned; touched only very early with no later
            # engagement is closer to "saw it, moved past it".
        })

    succ_answer_turns = [d["answered_at_turn"] for d in succeeded_detail]
    n_capped_any_seen = sum(1 for d in capped_detail if d["any_gold_file_ever_seen"])
    n_capped_any_read = sum(1 for d in capped_detail if d["any_gold_file_ever_read"])
    n_capped_never_seen = len(capped_detail) - n_capped_any_seen

    return {
        "arm": arm,
        "n_total": len(arm_rows),
        "n_success": len(succeeded),
        "n_hit_turn_cap": len(failed_capped),
        "n_failed_other": len(failed_other),
        "succeeded_detail": succeeded_detail,
        "success_answer_turn_stats": {
            "median": stats.median(succ_answer_turns) if succ_answer_turns else None,
            "mean": stats.mean(succ_answer_turns) if succ_answer_turns else None,
            "min": min(succ_answer_turns) if succ_answer_turns else None,
            "max": max(succ_answer_turns) if succ_answer_turns else None,
            "all_turns": sorted(succ_answer_turns),
        },
        "capped_detail": capped_detail,
        "capped_summary": {
            "n_capped": len(capped_detail),
            "n_ever_saw_a_gold_file": n_capped_any_seen,
            "n_ever_read_a_gold_file": n_capped_any_read,
            "n_never_saw_any_gold_file": n_capped_never_seen,
            "first_seen_turns_of_those_that_saw": sorted(
                d["earliest_gold_seen_turn"] for d in capped_detail if d["earliest_gold_seen_turn"] is not None
            ),
        },
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def print_checkpoint_table(growth: dict) -> None:
    print("\n=== 1. TOKEN GROWTH: median cumulative tiktoken tokens at turn N (across runs reaching turn N) ===")
    header = f"{'arm':11}" + "".join(f"{f'N={n}':>12}" for n in CHECKPOINTS)
    print(header)
    for arm in ARMS:
        cells = []
        for n in CHECKPOINTS:
            cp = growth[arm]["checkpoint_table"][n]
            med = cp["median_tokens"]
            n_reach = cp["n_runs_reaching"]
            n_tot = cp["n_runs_total"]
            cells.append(f"{'-' if med is None else f'{med:,.0f}'} ({n_reach}/{n_tot})")
        print(f"{arm:11}" + "".join(f"{c:>18}" for c in cells))
    print("  (cell = median_tokens (n_runs_reaching_this_turn / n_runs_total_in_arm))")


def print_fits(growth: dict) -> None:
    print("\n=== 1b. CURVE FITS per arm (on the dense median-cumulative-tokens-per-turn curve) ===")
    for arm in ARMS:
        print(f"\n-- {arm} (n={growth[arm]['n_runs']} runs, curve up to turn "
              f"{max(growth[arm]['dense_curve_turns']) if growth[arm]['dense_curve_turns'] else 0}) --")
        for name, f in growth[arm]["fits"].items():
            if name == "power_law":
                print(f"  power_law:  tokens ~ {f['a']:.1f} * turn^{f['b']:.3f}   (R^2 on log-log = "
                      f"{f['r2_on_log_log']:.4f})" if f["r2_on_log_log"] is not None else
                      f"  power_law:  tokens ~ {f['a']:.1f} * turn^{f['b']:.3f}")
            else:
                c = f["coefficients_high_to_low"]
                poly_str = " + ".join(
                    f"{coef:.2f}*turn^{len(c) - 1 - i}" if len(c) - 1 - i > 0 else f"{coef:.2f}"
                    for i, coef in enumerate(c)
                )
                r2 = f["r2"]
                print(f"  {name:10}: tokens ~ {poly_str}   (R^2 = {r2:.4f})" if r2 is not None else
                      f"  {name:10}: tokens ~ {poly_str}")


def print_extrapolation(extrap: dict) -> None:
    print("\n=== 2. GREP EXTRAPOLATION (quadratic fit; EXTRAPOLATION beyond observed turn<=30 data) ===")
    print(f"  quadratic fit R^2 = {extrap['fit_quality_r2']}")
    print(f"  all fit R^2s: {extrap['all_fit_quality_r2']}")
    for n, v in extrap["extrapolated_median_tokens"].items():
        lin_v = extrap.get("extrapolated_median_tokens_linear_fit", {}).get(n)
        print(f"  N={n:>4} turns:  quadratic-fit median tokens ~ {v:,.0f}"
              + (f"   (linear-fit: {lin_v:,.0f})" if lin_v is not None else ""))


def print_convergence(conv: dict) -> None:
    print(f"\n=== 3/4. CONVERGENCE -- arm={conv['arm']} ===")
    print(f"  n_total={conv['n_total']}  n_success={conv['n_success']}  "
          f"n_hit_turn_cap={conv['n_hit_turn_cap']}  n_failed_other={conv['n_failed_other']}")
    st = conv["success_answer_turn_stats"]
    print(f"  successful runs answered at turn: median={st['median']} mean={st['mean']:.1f} "
          f"min={st['min']} max={st['max']}  all_turns={st['all_turns']}" if st["median"] is not None else
          "  (no successful runs)")
    for d in conv["succeeded_detail"]:
        print(f"    {d['instance_id']:38} answered_turn={d['answered_at_turn']:>3}  "
              f"gold_seen_by_turn={d['earliest_gold_seen_turn']}  "
              f"all_gold_read_before_answer={d['all_gold_files_read_before_answer']}")
    cs = conv["capped_summary"]
    if conv["n_hit_turn_cap"]:
        print(f"\n  of {cs['n_capped']} turn-cap-out runs:")
        print(f"    ever SAW a gold file (in search output/read/reasoning text): {cs['n_ever_saw_a_gold_file']}")
        print(f"    ever explicitly READ (read_file) a gold file:                {cs['n_ever_read_a_gold_file']}")
        print(f"    NEVER saw any gold file the entire run (pure flailing):      {cs['n_never_saw_any_gold_file']}")
        print(f"    first-seen turn distribution (of those that saw one): {cs['first_seen_turns_of_those_that_saw']}")
        for d in conv["capped_detail"]:
            print(f"    {d['instance_id']:38} any_seen={d['any_gold_file_ever_seen']!s:5} "
                  f"any_read={d['any_gold_file_ever_read']!s:5} "
                  f"first_seen_turn={d['earliest_gold_seen_turn']} "
                  f"first_read_turn={d['earliest_gold_read_turn']} (of {d['last_turn']} turns)")


def main() -> None:
    results = load_results()

    mismatches = _validate_against_results(results)
    print(f"=== validation: reconstructed tiktoken totals vs results.jsonl ({len(results)} rows) ===")
    if mismatches:
        print(f"  {len(mismatches)} MISMATCHES:")
        for m in mismatches[:20]:
            print(f"    {m}")
    else:
        print("  all rows match exactly (0 mismatches)")

    growth = growth_curve_per_arm(results)
    print_checkpoint_table(growth)
    print_fits(growth)

    extrap = extrapolate_grep(growth)
    print_extrapolation(extrap)

    conv_grep = convergence_analysis(results, "grep")
    print_convergence(conv_grep)
    conv_roust = convergence_analysis(results, "roust")
    print_convergence(conv_roust)

    # ---- verdict ----
    cs = conv_grep["capped_summary"]
    n_capped = cs["n_capped"]
    frac_never_seen = cs["n_never_saw_any_gold_file"] / n_capped if n_capped else None
    frac_seen_not_read = (
        (cs["n_ever_saw_a_gold_file"] - cs["n_ever_read_a_gold_file"]) / n_capped if n_capped else None
    )
    verdict = {
        "grep_capped_runs": n_capped,
        "grep_capped_never_saw_gold_file": cs["n_never_saw_any_gold_file"],
        "grep_capped_saw_but_never_read_gold_file": cs["n_ever_saw_a_gold_file"] - cs["n_ever_read_a_gold_file"],
        "grep_capped_read_gold_file_but_still_failed": cs["n_ever_read_a_gold_file"],
        "fraction_never_seen": frac_never_seen,
        "reasoning": (
            "See gold_touches detail above: a capped run that NEVER surfaces the gold file in any "
            "search/read/reasoning text across 30 turns is flailing -- more turns extend the same "
            "unproductive search, not convergence. A capped run that READ the gold file (opened it via "
            "read_file) and still failed to answer within 30 turns had the evidence in front of it and "
            "either mis-assessed it or kept exploring instead of committing -- more turns MIGHT help there "
            "since the file was already in context, but the failure mode (over-verification / not "
            "recognizing the fix) is not obviously turn-limited either."
        ),
        "grep_turn_cap_needed_estimate": None,  # filled in narratively in the report, see summarize text below
        "confidence": "low-moderate -- extrapolation is from a 2-point x-y quadratic fit on 15 runs, "
                       "never observed beyond turn 30, and the convergence evidence is the more decisive "
                       "signal for the verdict, not the token curve.",
    }

    out = {
        "validation_mismatches": mismatches,
        "growth_curves": growth,
        "grep_extrapolation": extrap,
        "convergence_grep": conv_grep,
        "convergence_roust": conv_roust,
        "verdict": verdict,
    }
    OUT_PATH.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n=== wrote {OUT_PATH} ===")


if __name__ == "__main__":
    main()
