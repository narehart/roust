#!/usr/bin/env python3
"""Agentless-style "% Correct Location" metric for roust on SWE-bench Lite.

Definition (Agentless, arXiv:2407.01489, Table 1): the fraction of instances
where the PREDICTED location set is a SUPERSET of the GOLD edit locations,
at three granularities (FILE / FUNCTION / LINE). Agentless's own numbers use
an LLM to narrow predicted files down to functions/lines; roust has no LLM
in the loop, so "predicted" here means "covered by roust's returned regions"
(the --json `regions` field: per-file line spans packed under an 8192-token
budget).

STORED-DATA-ONLY: no roust invocations, no repo checkouts. This script reads:
  - lab/results_regions/full300_final.json  (roust's frozen v7 run over all
    300 SWE-bench Lite instances -- parity/region_eval.py's Part A report).
    Per-instance it has hunk_file_covered, hunk_line_recall, hunk_touched
    (all exact fractions) but NOT the raw region spans themselves (those
    were not persisted by that run).
  - lab/swebench_lite.parquet  (gold patches, to recompute exact gold hunk
    line ranges via parity/region_eval.py's parse_gold_hunks, and to walk
    Python ASTs for gold function spans).
  - lab/swebench_repos/<owner>__<name>/  via `git show <base_commit>:<path>`
    ONLY (read-only, no checkout/mutation) -- safe to run alongside another
    process that has repos checked out, per the task's explicit guidance.

FILE-level and LINE-level are computed EXACTLY from the stored aggregate
fractions (see derivations in compute_file_level / compute_line_level
docstrings below). FUNCTION-level cannot be computed exactly from what was
persisted -- see compute_function_level_proxy docstring for why, and what
proxy is reported instead.
"""

from __future__ import annotations

import ast
import json
import statistics
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path("/Users/nicholasarehart/programming-projects/bgrep")
sys.path.insert(0, str(REPO_ROOT / "parity"))
from region_eval import parse_gold_hunks  # noqa: E402

FULL300 = REPO_ROOT / "lab" / "results_regions" / "full300_final.json"
LITE_PARQUET = REPO_ROOT / "lab" / "swebench_lite.parquet"
SWEBENCH_REPOS = REPO_ROOT / "lab" / "swebench_repos"
OUT_PATH = REPO_ROOT / "lab" / "results_regions" / "agentless_metric.json"

# Agentless's own published GPT-4o SWE-bench Lite numbers (Table 1 of
# arXiv:2407.01489) -- for side-by-side reporting only, not reproduced here.
AGENTLESS_GPT4O = {"file": 69.7, "function": 52.0, "line": 35.3}


def mean_median(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    return statistics.mean(values), statistics.median(values)


def pct(x: float | None) -> float | None:
    return None if x is None else round(100.0 * x, 2)


# ---------------------------------------------------------------------------
# gold function spans (AST, via read-only `git show`)
# ---------------------------------------------------------------------------


def git_show(repo_slug: str, sha: str, path: str) -> str | None:
    repo_path = SWEBENCH_REPOS / repo_slug.replace("/", "__")
    if not repo_path.exists():
        return None
    r = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=repo_path,
                        capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return None
    return r.stdout


def function_spans(source: str) -> list[tuple[int, int]]:
    """Returns [(start, end_inclusive), ...] for every function/method
    definition in `source` (def and async def; NOT bare class bodies --
    "function/method" per the task's definition). Span start includes any
    decorator lines; end is ast's end_lineno (Python 3.8+)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            if node.decorator_list:
                start = min(start, min(d.lineno for d in node.decorator_list))
            end = getattr(node, "end_lineno", None) or node.lineno
            spans.append((start, end))
    return spans


def gold_functions_for_instance(repo_slug: str, base_commit: str,
                                 gold_hunks: dict[str, list[tuple[int, int]]]
                                 ) -> tuple[int, bool]:
    """Returns (n_gold_functions, ast_ok). ast_ok is False if any gold
    Python file couldn't be fetched/parsed (informational only -- this
    script never claims an exact function-level correctness number, so a
    parse failure only affects the n_gold_functions context stat)."""
    n = 0
    ast_ok = True
    for path, ranges in gold_hunks.items():
        if not path.endswith(".py"):
            continue
        src = git_show(repo_slug, base_commit, path)
        if src is None:
            ast_ok = False
            continue
        spans = function_spans(src)
        if not spans and src.strip():
            # non-empty file, zero functions found is plausible (module-level
            # code) but also what a silent parse issue looks like; not
            # flagged as ast_ok=False since ast.parse would have raised.
            pass
        line_set: set[int] = set()
        for s, e in ranges:
            line_set.update(range(s, e + 1))
        touched = 0
        for fs, fe in spans:
            if any(fs <= ln <= fe for ln in line_set):
                touched += 1
        n += touched
    return n, ast_ok


# ---------------------------------------------------------------------------
# metric computation
# ---------------------------------------------------------------------------


def compute_file_level(records: list[dict]) -> dict:
    """Exact. Agentless's FILE metric is `predicted files ⊇ gold files`.
    region_eval.py's `all_gold_files_retrieved` is defined identically
    (`hunk_file_covered == 1.0`, i.e. every gold file is a key in the
    returned `regions` dict) -- so this is a direct read, not an
    approximation."""
    vals = [1.0 if r["all_gold_files_retrieved"] else 0.0 for r in records]
    m, _ = mean_median(vals)
    return {"pct_correct": pct(m), "n": len(records), "n_correct": sum(int(v) for v in vals)}


def compute_line_level(records: list[dict]) -> dict:
    """All-or-nothing part is EXACT despite the stored data being an
    aggregate fraction: region_eval.py's `hunk_line_recall` is defined as
    `covered_lines / total_lines` over the exact union of gold lines for
    the instance. Since this is a true fraction of a finite set,
    `hunk_line_recall == 1.0` is logically equivalent to "every gold line
    is covered by a returned region" -- exactly Agentless's LINE
    superset condition. No raw line data was needed to get this exactly
    right, only the stored fraction.

    Also reports the mean-fraction (our own prior "hunk_line_recall"
    metric) for continuity -- NOTE this is a materially easier number
    (partial credit) than the all-or-nothing metric to its left."""
    all_or_nothing = [1.0 if r["hunk_line_recall"] == 1.0 else 0.0 for r in records]
    fractions = [r["hunk_line_recall"] for r in records if r["hunk_line_recall"] is not None]
    aon_m, _ = mean_median(all_or_nothing)
    frac_m, frac_med = mean_median(fractions)
    return {
        "pct_correct_all_or_nothing": pct(aon_m),
        "n": len(records),
        "n_correct_all_or_nothing": sum(int(v) for v in all_or_nothing),
        "mean_fraction_covered": frac_m,
        "median_fraction_covered": frac_med,
    }


def compute_function_level_proxy(records: list[dict]) -> dict:
    """NOT exact -- flagged gap, see report caveats.

    The exact Agentless FUNCTION metric needs, per instance: the set of
    gold functions (any function/method AST span containing >=1 gold-patch
    line -- computable exactly, see gold_functions_for_instance) intersected
    against the set of PREDICTED functions (any function/method AST span
    overlapping ANY of roust's returned region spans for that file). The
    second half requires roust's actual returned region spans
    (`obj["regions"]` from a --json run), which full300_final.json does not
    persist -- it only stored the aggregate `hunk_line_recall` /
    `hunk_touched` fractions per instance, not the spans themselves. Since
    re-running roust right now would checkout the same lab/swebench_repos/
    clones a concurrent token-benchmark process is actively using (see
    report caveats), exact function-level cannot be computed this pass.

    Proxy reported instead: `hunk_touched == 1.0` (every individual gold
    hunk in the instance has >=1 covered line). This is a LOWER-BOUND-ish
    heuristic, not a rigorous bound: if every hunk has >=1 covered line,
    every function that hunk's covered line falls into is trivially in the
    predicted set. But it is NOT a rigorous lower bound in the case of a
    single hunk spanning >1 function where only *one* of those functions'
    lines is the covered one -- the other function in that hunk could be
    missed while hunk_touched still reads 1.0 for the hunk. In practice
    most hunks are single-function, so this under-counts only rarely; still,
    treat it as an approximation, not the metric itself.
    """
    vals = [1.0 if r.get("hunk_touched") == 1.0 else 0.0 for r in records]
    m, _ = mean_median(vals)
    return {
        "pct_correct_PROXY": pct(m),
        "n": len(records),
        "n_correct_PROXY": sum(int(v) for v in vals),
        "caveat": "approximate lower-bound-ish heuristic (hunk_touched==1.0), NOT the exact "
                  "Agentless function-level metric -- exact computation requires roust's raw "
                  "returned region spans, which were not persisted for this stored run and "
                  "could not be re-derived this pass (see top-level caveats).",
    }


def main() -> None:
    full300 = json.loads(FULL300.read_text())
    records = full300["part_a"]["records"]
    assert len(records) == 300, f"expected 300 stored records, got {len(records)}"
    assert all(r["error"] is None for r in records), "unexpected errored records in stored data"

    file_correct_subset = [r for r in records if r["all_gold_files_retrieved"]]

    report: dict = {
        "source": {
            "predictions": str(FULL300.relative_to(REPO_ROOT)),
            "gold": str(LITE_PARQUET.relative_to(REPO_ROOT)),
            "n_instances": len(records),
            "pipeline": "roust frozen v7, --budget 8192, confidence-scheduled packing "
                        "(parity/region_eval.py Part A, no-LLM)",
        },
        "all_instances": {
            "n": len(records),
            "file": compute_file_level(records),
            "function": compute_function_level_proxy(records),
            "line": compute_line_level(records),
        },
        "file_correct_subset": {
            "n": len(file_correct_subset),
            "note": "restricted to instances where FILE-level was already correct -- isolates "
                    "region/line quality from file recall (spec item 4)",
            "file": compute_file_level(file_correct_subset),
            "function": compute_function_level_proxy(file_correct_subset),
            "line": compute_line_level(file_correct_subset),
        },
        "agentless_gpt4o_published": AGENTLESS_GPT4O,
    }

    # Gold-function AST context stats (informational; does not feed into any
    # correctness number above -- see compute_function_level_proxy docstring
    # for why the predicted side can't be joined against it this pass).
    print("Computing gold-function AST context stats via read-only `git show` "
          "(no checkout, safe alongside a running benchmark)...", file=sys.stderr)
    import pandas as pd
    df = pd.read_parquet(LITE_PARQUET)
    patch_by_id = {row["instance_id"]: row["patch"] for _, row in df.iterrows()}
    n_gold_functions_list = []
    n_ast_fail = 0
    for i, r in enumerate(records, 1):
        patch = patch_by_id.get(r["instance_id"])
        if patch is None:
            continue
        gold_hunks = parse_gold_hunks(patch)
        n_fn, ast_ok = gold_functions_for_instance(r["repo"], r["base_commit"], gold_hunks)
        if not ast_ok:
            n_ast_fail += 1
        n_gold_functions_list.append(n_fn)
        if i % 50 == 0:
            print(f"  [{i}/{len(records)}]", file=sys.stderr)
    gf_mean, gf_med = mean_median([float(x) for x in n_gold_functions_list])
    report["gold_function_context"] = {
        "n_gold_functions_per_instance": {"mean": gf_mean, "median": gf_med},
        "n_instances_with_git_show_failures": n_ast_fail,
        "note": "AST-derived gold function counts (context only, per top-level docstring); "
                "not used in any FUNCTION-level correctness number above since the predicted "
                "side (roust's returned region spans) was not available.",
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nwrote {OUT_PATH.relative_to(REPO_ROOT)}", file=sys.stderr)

    print_table(report)


def print_table(report: dict) -> None:
    al = report["agentless_gpt4o_published"]
    a = report["all_instances"]
    fc = report["file_correct_subset"]

    def row(label, ours, theirs):
        ours_s = f"{ours:.1f}%" if ours is not None else "n/a"
        theirs_s = f"{theirs:.1f}%" if theirs is not None else "n/a"
        print(f"{label:38} {ours_s:>10}   {theirs_s:>10}")

    print("\n" + "=" * 78)
    print("Agentless-style %% Correct Location -- roust (no-LLM) vs GPT-4o Agentless")
    print("=" * 78)
    print(f"{'':38} {'roust':>10}   {'GPT-4o Agentless':>10}")
    row("FILE   (predicted ⊇ gold files)", a["file"]["pct_correct"], al["file"])
    row("FUNCTION (PROXY, see caveats)   ", a["function"]["pct_correct_PROXY"], al["function"])
    row("LINE   (all-or-nothing)         ", a["line"]["pct_correct_all_or_nothing"], al["line"])
    print(f"\n{'LINE mean-fraction covered (continuity w/ prior reporting)':60} "
          f"{a['line']['mean_fraction_covered']:.4f}")

    print(f"\n--- restricted to file-correct subset (n={fc['n']}/{a['n']}) ---")
    row("FUNCTION (PROXY, see caveats)   ", fc["function"]["pct_correct_PROXY"], None)
    row("LINE   (all-or-nothing)         ", fc["line"]["pct_correct_all_or_nothing"], None)
    print(f"{'LINE mean-fraction covered':60} {fc['line']['mean_fraction_covered']:.4f}")

    gfc = report["gold_function_context"]
    print(f"\ngold functions/instance (AST context, informational): "
          f"mean={gfc['n_gold_functions_per_instance']['mean']:.2f} "
          f"median={gfc['n_gold_functions_per_instance']['median']:.1f} "
          f"(git-show failures: {gfc['n_instances_with_git_show_failures']})")


if __name__ == "__main__":
    main()
