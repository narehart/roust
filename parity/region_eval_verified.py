#!/usr/bin/env python3
"""Region-eval Part A, re-run on SWE-bench VERIFIED held-out instances.

Modeled directly on `parity/region_eval2.py` (same gold-hunk parsing via
`parse_gold_hunks`, same checkout-then-invoke loop against a PRIVATE repo
checkout, same per-instance record shape: `hunk_file_covered`,
`hunk_line_recall`, `hunk_touched`, `all_gold_files_retrieved`, `tokens`,
plus the persisted `regions` dict and engine provenance `engine_sha` /
`engine_dirty`) -- but the instance source is a SWE-bench VERIFIED parquet
(default: the held-out subset, i.e. Verified minus the Lite overlap) instead
of `region_eval2.py`'s hardcoded Lite parquet.

This script exists for the out-of-sample validation campaign (issue #4
follow-on): confirm or refute, on instances the engine's defaults were never
tuned against, the region-packing gains measured on Lite (the adopted
padding + length-normalization defaults, commit 5e81c8a).

Path differences from region_eval2.py:
  - Gold parquet is a CLI flag (`--gold-parquet`), not a hardcoded constant --
    defaults to `lab/swebench_verified_heldout.parquet` (the held-out subset
    computed once and cached to a durable path, same convention
    `swebench_lite.parquet` uses for Lite).
  - Repo checkouts still read from `lab/swebench_repos/` (REPO_ROOT-relative,
    same as region_eval2.py) -- in THIS worktree that directory is a private
    `cp -R` of the main repo's clones (issue #41 standard), so a Verified run
    here cannot race or corrupt a concurrent Lite run elsewhere.
  - `--pad-lines` / `--len-exp` are ALWAYS forwarded to the roust binary
    (no "0 means omit the flag" sentinel like region_eval2.py's CLI has).
    region_eval2.py's sentinel trick exists because 0/1.0 used to be the
    engine's own pre-adoption defaults and it needed an "unset" value to
    fall back to whatever the shipped binary's default of the moment was;
    that ambiguity is undesirable here where the whole point is a byte-exact
    A/B between two NAMED formulas (new defaults vs the old formula), so
    this script's flags default to the current engine defaults (5 / 0.85)
    and are unconditionally passed through -- there is no implicit-default
    mode. To reproduce the pre-adoption ("old formula") arm, pass
    `--pad-lines 0 --len-exp 1.0` explicitly.

Usage:
    python parity/region_eval_verified.py [--limit N] [--timeout SECONDS] \\
        --report lab/results_regions/full407_verified_new.jsonl
    python parity/region_eval_verified.py --pad-lines 0 --len-exp 1.0 \\
        --report lab/results_regions/full407_verified_old.jsonl

Output: one JSON object per line (JSONL), one line per instance, written as
each instance completes (partial runs are resumable-by-eye). A final summary
line is NOT written to the JSONL -- the aggregate prints to stdout only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from region_eval import parse_gold_hunks, line_in_spans, swebench_driver_guard  # noqa: E402
from region_eval2 import check_engine_provenance  # noqa: E402  (blocking provenance guard)

REPO_ROOT = Path(__file__).resolve().parent.parent

ROUST_BIN = REPO_ROOT / "roust-rs" / "target" / "release" / "roust"
VERIFIED_HELDOUT_PARQUET = REPO_ROOT / "lab" / "swebench_verified_heldout.parquet"
SWEBENCH_REPOS = REPO_ROOT / "lab" / "swebench_repos"

BUDGET = 8192
DEFAULT_TIMEOUT_S = 180
PROGRESS_EVERY = 25
DEFAULT_PAD_LINES = 5    # current engine default (E12, adopted commit 5e81c8a)
DEFAULT_LEN_EXP = 0.85   # current engine default (E14, adopted commit 5e81c8a)

# Additional flags appended to every roust invocation. Empty here (this
# script always runs the default engine); parity/region_eval_full.py sets
# this module global to its BM25_ONLY_FLAGS for the same-harness BM25 arm.
EXTRA_ENGINE_FLAGS: list[str] = []


def engine_version_string() -> str:
    proc = subprocess.run([str(ROUST_BIN), "--version"], capture_output=True, text=True, timeout=30)
    return proc.stdout.strip() or proc.stderr.strip()


def run_roust(query: str, repo_path: Path, timeout: float, pad_lines: int,
              len_exp: float) -> tuple[dict | None, str | None]:
    argv = [str(ROUST_BIN), "--json", "--budget", str(BUDGET), query, str(repo_path),
            "--pad-lines", str(pad_lines), "--len-exp", str(len_exp),
            *EXTRA_ENGINE_FLAGS]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"
    except OSError as exc:
        return None, f"failed to spawn roust: {exc}"
    if proc.returncode != 0:
        return None, f"exit {proc.returncode}: stderr[:300]={proc.stderr[:300]!r}"
    stdout = proc.stdout.strip()
    if not stdout:
        return None, "empty stdout"
    try:
        obj = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return None, f"bad JSON: {exc}"
    if not isinstance(obj, dict) or "regions" not in obj:
        return None, "JSON output has no \"regions\" key"
    return obj, None


def checkout(repo_path: Path, sha: str) -> None:
    r = subprocess.run(["git", "checkout", "-f", "-q", sha], cwd=repo_path,
                        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"checkout {sha} in {repo_path} failed: {r.stderr.strip()[:300]}")
    subprocess.run(["git", "clean", "-fdq"], cwd=repo_path, capture_output=True,
                    text=True, timeout=300)


def load_verified_rows(gold_parquet: Path, limit: int,
                        only: set[str] | None = None) -> list[dict]:
    import pandas as pd
    df = pd.read_parquet(gold_parquet)
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "instance_id": row["instance_id"],
            "repo": row["repo"],
            "base_commit": row["base_commit"],
            "patch": row["patch"],
            "problem_statement": row["problem_statement"],
        })
    # deterministic order (same convention as region_eval2.py's parquet
    # iteration order, which is the parquet's own row order); sort by
    # (repo, instance_id) so shared clones are checked out sequentially.
    rows.sort(key=lambda r: (r["repo"], r["instance_id"]))
    if only is not None:
        missing = only - {r["instance_id"] for r in rows}
        if missing:
            raise SystemExit(f"--instances: not in this parquet: {sorted(missing)}")
        rows = [r for r in rows if r["instance_id"] in only]
    if limit:
        rows = rows[:limit]
    return rows


def eval_verified_instance(row: dict, timeout: float, pad_lines: int, len_exp: float) -> dict:
    instance_id = row["instance_id"]
    gold_hunks = parse_gold_hunks(row["patch"])
    gold_files = sorted(gold_hunks.keys())
    rec: dict = {
        "instance_id": instance_id,
        "repo": row["repo"],
        "base_commit": row["base_commit"],
        "n_gold_files": len(gold_files),
        "n_gold_hunks": sum(len(v) for v in gold_hunks.values()),
        "error": None,
        "regions": {},
        "engine_sha": None,
        "engine_dirty": None,
    }
    if not gold_files:
        rec["error"] = "no old-file hunk lines in gold patch (pure file creation(s) only)"
        return rec

    repo_path = SWEBENCH_REPOS / row["repo"].replace("/", "__")
    if not repo_path.exists():
        rec["error"] = f"repo checkout not found: {repo_path}"
        return rec
    try:
        checkout(repo_path, row["base_commit"])
    except (RuntimeError, OSError) as exc:
        rec["error"] = f"checkout failed: {exc}"
        return rec

    obj, err = run_roust(row["problem_statement"], repo_path, timeout, pad_lines, len_exp)
    if err:
        rec["error"] = err
        return rec

    regions: dict[str, list[list[int]]] = obj.get("regions", {})
    rec["regions"] = regions
    files_in_regions = set(regions.keys())

    stats = obj.get("stats", {})
    rec["engine_sha"] = stats.get("engine_sha")
    rec["engine_dirty"] = stats.get("engine_dirty")
    # E11: routing diagnostics (present only under --route; None otherwise).
    rec["route"] = stats.get("route")
    # E20/E11b diagnostics (present only under --lexboost / --trace-boost).
    rec["lexboost"] = stats.get("lexboost")
    rec["trace_boost"] = stats.get("trace_boost")
    # E21/E22 diagnostics (present only under --file-score / --test-bridge).
    rec["file_score"] = stats.get("file_score")
    rec["test_bridge"] = stats.get("test_bridge")

    # (1) hunk-file-covered
    covered_files = [f for f in gold_files if f in files_in_regions]
    rec["hunk_file_covered"] = len(covered_files) / len(gold_files)
    rec["all_gold_files_retrieved"] = len(covered_files) == len(gold_files)

    # (2) hunk line recall (union of gold lines per file, weighted by
    # how many of those lines fall inside that file's returned spans)
    total_lines = 0
    covered_lines = 0
    for f, ranges in gold_hunks.items():
        line_set: set[int] = set()
        for s, e in ranges:
            line_set.update(range(s, e + 1))
        spans = regions.get(f, [])
        total_lines += len(line_set)
        covered_lines += sum(1 for ln in line_set if line_in_spans(ln, spans))
    rec["hunk_line_recall"] = covered_lines / total_lines if total_lines else None

    # (3) hunk-touched: fraction of individual gold hunks with >=1 line covered
    total_hunks = 0
    touched_hunks = 0
    for f, ranges in gold_hunks.items():
        spans = regions.get(f, [])
        for s, e in ranges:
            total_hunks += 1
            if any(line_in_spans(ln, spans) for ln in range(s, e + 1)):
                touched_hunks += 1
    rec["hunk_touched"] = touched_hunks / total_hunks if total_hunks else None

    # (4) tokens of bundle
    rec["tokens"] = stats.get("bundle_tokens")

    return rec



def _load_instance_filter(path):
    """E26: read an instance_id allowlist (one per line; blank and #-comment
    lines ignored). Returns None when no path was given, so the default code
    path is untouched."""
    if path is None:
        return None
    ids = {l.strip() for l in Path(path).read_text().splitlines()}
    ids = {i for i in ids if i and not i.startswith("#")}
    if not ids:
        raise SystemExit(f"--instances: {path} lists no instance ids")
    return ids

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="cap instance count (0 = all)")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    ap.add_argument("--report", type=Path, required=True, help="JSONL output path")
    ap.add_argument("--gold-parquet", type=Path, default=VERIFIED_HELDOUT_PARQUET,
                     help="SWE-bench Verified parquet to evaluate against "
                          "(default: the pre-computed held-out subset, "
                          "Verified minus Lite overlap)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--pad-lines", type=int, default=DEFAULT_PAD_LINES,
                     help=f"passthrough to roust's --pad-lines (E12); always forwarded "
                          f"(default {DEFAULT_PAD_LINES}, the current engine default); pass "
                          f"`--pad-lines 0` to reproduce the pre-adoption old formula")
    ap.add_argument("--len-exp", type=float, default=DEFAULT_LEN_EXP,
                     help=f"passthrough to roust's --len-exp (E14); always forwarded "
                          f"(default {DEFAULT_LEN_EXP}, the current engine default); pass "
                          f"`--len-exp 1.0` to reproduce the pre-adoption old formula")
    ap.add_argument("--family-enum", action="store_true",
                     help="passthrough to roust's --family-enum (E19 def-name-family sibling "
                          "enumeration); omitted by default (binary default: off)")
    ap.add_argument("--sibling-sim", type=float, default=0.0,
                     help="passthrough to roust's --sibling-sim (E18 identifier-bag similarity "
                          "siblings); 0.0 (default) omits the flag (binary default: disabled)")
    ap.add_argument("--max-siblings", type=int, default=0,
                     help="passthrough to roust's --max-siblings (E18 cap); 0 (default) omits "
                          "the flag (binary default: 3)")
    ap.add_argument("--lexboost", type=float, default=0.0,
                     help="passthrough to roust's --lexboost (E20 LexBoost neighbor score "
                          "smoothing lambda); 0.0 (default) omits the flag (binary default: off)")
    ap.add_argument("--lexboost-graph", type=str, default="",
                     help="passthrough to roust's --lexboost-graph (import|knn); empty (default) "
                          "omits the flag (binary default: import); only meaningful with --lexboost")
    ap.add_argument("--trace-boost", action="store_true",
                     help="passthrough to roust's --trace-boost (E11b trace-frame FILE boost); "
                          "ADOPTED as the binary default (PR #52), redundant-but-accepted")
    ap.add_argument("--no-trace-boost", action="store_true",
                     help="passthrough to roust's --no-trace-boost (disable the adopted E11b "
                          "boost; reproduces the pre-PR-#52 engine byte-identically)")
    ap.add_argument("--route", action="store_true",
                     help="passthrough to roust's --route (E11 structure-aware query routing); "
                          "omitted by default (binary default: off)")
    ap.add_argument("--file-score", type=str, default="",
                     help="passthrough to roust's --file-score (E21 chunk-aggregated FILE "
                          "scoring: accum|chunk-max|chunk-top2|chunk-rank|chunk-top2-rank); empty (default) omits the "
                          "flag, i.e. the binary's own default (accum)")
    ap.add_argument("--test-bridge", type=float, default=0.0,
                     help="passthrough to roust's --test-bridge (E22 static test-bridge FILE "
                          "channel weight); 0.0 (default) omits the flag, i.e. the binary's "
                          "own disabled default")
    ap.add_argument("--route-test-penalty", type=float, default=0.0,
                     help="passthrough to roust's --route-test-penalty (E11 conditional "
                          "test-path downweight); 0.0 (default) omits the flag, i.e. the "
                          "binary's own default (0.85); only meaningful with --route")
    ap.add_argument("--cfamily-ext", action="store_true",
                     help="WS2b (campaign #56): append --cfamily-ext to every roust invocation "
                          "(index .c/.h/.cc/.cpp/.cxx/.hpp/.hh); omitted by default (binary "
                          "default: off). This is the Python-repo dilution gate for flipping "
                          "the engine default.")
    ap.add_argument("--impl-prior-v2", action="store_true",
                     help="WS3a (campaign #56): append --impl-prior-v2 to every roust "
                          "invocation (doc/example/bench dirs stop damping code files); "
                          "omitted by default (binary default: off)")
    ap.add_argument("--trace-formats-v2", action="store_true",
                     help="WS3b (campaign #56): append --trace-formats-v2 to every roust "
                          "invocation (Java/Node/Go/Rust trace-frame parsing for the E11b "
                          "boost); omitted by default (binary default: off)")
    ap.add_argument("--symbols-v2", action="store_true",
                     help="WS3c (campaign #56): append --symbols-v2 to every roust "
                          "invocation (tree-sitter-sourced def_index + un-gated anchor "
                          "seating); omitted by default (binary default: off)")
    ap.add_argument("--shape-blocks", action="store_true",
                     help="E25 (campaign #56 follow-on): append --shape-blocks to every roust invocation -- zero-config SHAPE-based structural headers in place of the per-language node-kind allowlists")
    ap.add_argument("--ext-v2", action="store_true",
                     help="E26 (per-language parity campaign): append --ext-v2 to every roust invocation -- index source extensions the original allowlist never covered (.rb .pony .svelte .mjs .cjs .cts .mts .vue .scala .php)")
    ap.add_argument("--max-additions", type=int, default=0,
                     help="E28 (per-language parity campaign): append --max-additions N to "
                          "every roust invocation -- the pool breadth cap (engine default "
                          "16 = shipped). 0 (the default here) is a SENTINEL meaning forward "
                          "NO flag at all, so a default arm's argv is byte-identical to "
                          "every pre-E28 default arm's.")
    ap.add_argument("--seats-per-source", type=int, default=0,
                     help="E30 (per-language parity campaign): append --seats-per-source N to "
                          "every roust invocation -- how many owned candidates each source "
                          "file seats in the per-source guarantee (engine default 1 = shipped). "
                          "0 (the default here) is a SENTINEL meaning forward NO flag at all, "
                          "so a default arm's argv is byte-identical to every pre-E30 default arm's.")
    ap.add_argument("--import-hops", type=int, default=0,
                     help="E32 (per-language parity campaign): append --import-hops N to "
                          "every roust invocation -- how many hops of the import graph the "
                          "candidate GENERATOR walks from each source (engine default 1 = "
                          "shipped). 0 (the default here) is a SENTINEL meaning forward NO "
                          "flag at all.")
    ap.add_argument("--import-edges-v2", action="store_true",
                     help="E32 (per-language parity campaign): append --import-edges-v2 -- resolve Java and C-family import edges, which the import graph never covered at all.")
    ap.add_argument("--eligible-floor", type=float, default=0.0,
                     help="E33 (per-language parity campaign): append --eligible-floor F -- the pool eligibility cut as a fraction of the best candidate score (engine default 0.15). 0.0 here is a SENTINEL meaning forward NO flag at all.")
    ap.add_argument("--k-lex", type=int, default=0,
                     help="E34 (per-language parity campaign): append --k-lex N -- how many BM25-ranked files seed retrieval as `sources` (engine default 10). 0 here is a SENTINEL meaning forward NO flag at all.")
    ap.add_argument("--budget", type=int, default=0,
                     help="E29 (cost-of-parity curve): override the packer token budget by "
                          "rebinding the module-global BUDGET (run_roust already passes "
                          "--budget positionally, so this must NOT ride EXTRA_ENGINE_FLAGS "
                          "or the flag would be forwarded twice). 0 = leave it at the "
                          "shipped 8192.")
    ap.add_argument("--displacement-guard", action="store_true",
                     help="WS3d (campaign #56): append --displacement-guard to every roust "
                          "invocation (fixture-dir anchor exclusion); omitted by default "
                          "(binary default: off)")
    ap.add_argument("--instances", type=Path, default=None,
                     help="E26: restrict the run to the instance_ids listed in this "
                          "file (one per line, blank/# lines ignored). Applied BEFORE "
                          "--limit. Used for targeted identity checks where a full "
                          "arm would be waste -- e.g. only the repos that contain a "
                          "file the flag under test could possibly touch.")
    ap.add_argument("--repos-dir", type=Path, default=None,
                     help="override the SWE-bench clones directory (default lab/swebench_repos). "
                          "This script MUTATES the clones (checkout -f + clean -fdq per "
                          "instance): per issue #41, point this at a PRIVATE cp -R copy when "
                          "anything else might touch the shared clones.")
    ap.add_argument("--allow-stale-engine", action="store_true",
                     help="override the blocking engine-provenance guard (logs a loud warning "
                          "instead of refusing) when the roust binary's embedded sha/dirty state "
                          "does not match this worktree's roust-rs/ HEAD/dirty state -- NOT "
                          "recommended for real results")
    args = ap.parse_args()

    # E18/E19 passthrough rides the same EXTRA_ENGINE_FLAGS mechanism
    # region_eval_full.py uses for its BM25 arm.
    global SWEBENCH_REPOS, BUDGET
    if args.family_enum:
        EXTRA_ENGINE_FLAGS.append("--family-enum")
    if args.sibling_sim != 0.0:
        EXTRA_ENGINE_FLAGS.extend(["--sibling-sim", str(args.sibling_sim)])
    if args.max_siblings != 0:
        EXTRA_ENGINE_FLAGS.extend(["--max-siblings", str(args.max_siblings)])
    # E11 passthrough, same EXTRA_ENGINE_FLAGS mechanism.
    if args.route:
        EXTRA_ENGINE_FLAGS.append("--route")
    if args.route_test_penalty != 0.0:
        EXTRA_ENGINE_FLAGS.extend(["--route-test-penalty", str(args.route_test_penalty)])
    if args.lexboost != 0.0:
        EXTRA_ENGINE_FLAGS.extend(["--lexboost", str(args.lexboost)])
    if args.lexboost_graph:
        EXTRA_ENGINE_FLAGS.extend(["--lexboost-graph", args.lexboost_graph])
    if args.trace_boost:
        EXTRA_ENGINE_FLAGS.append("--trace-boost")
    if args.no_trace_boost:
        EXTRA_ENGINE_FLAGS.append("--no-trace-boost")
    if args.file_score:
        EXTRA_ENGINE_FLAGS.extend(["--file-score", args.file_score])
    if args.test_bridge != 0.0:
        EXTRA_ENGINE_FLAGS.extend(["--test-bridge", str(args.test_bridge)])
    # WS2b passthrough, same mechanism.
    if args.cfamily_ext:
        EXTRA_ENGINE_FLAGS.append("--cfamily-ext")
    # WS3a passthrough, same mechanism.
    if args.impl_prior_v2:
        EXTRA_ENGINE_FLAGS.append("--impl-prior-v2")
    # WS3b passthrough, same mechanism.
    if args.trace_formats_v2:
        EXTRA_ENGINE_FLAGS.append("--trace-formats-v2")
    # WS3c passthrough, same mechanism.
    if args.symbols_v2:
        EXTRA_ENGINE_FLAGS.append("--symbols-v2")
    # WS3d passthrough, same mechanism.
    if args.displacement_guard:
        EXTRA_ENGINE_FLAGS.append("--displacement-guard")
    if args.shape_blocks:
        EXTRA_ENGINE_FLAGS.append("--shape-blocks")
    if args.ext_v2:
        EXTRA_ENGINE_FLAGS.append("--ext-v2")
    if args.max_additions:
        EXTRA_ENGINE_FLAGS.extend(["--max-additions", str(args.max_additions)])
    if args.seats_per_source:
        EXTRA_ENGINE_FLAGS.extend(["--seats-per-source", str(args.seats_per_source)])
    if args.import_hops:
        EXTRA_ENGINE_FLAGS.extend(["--import-hops", str(args.import_hops)])
    if args.import_edges_v2:
        EXTRA_ENGINE_FLAGS.append("--import-edges-v2")
    if args.eligible_floor:
        EXTRA_ENGINE_FLAGS.extend(["--eligible-floor", str(args.eligible_floor)])
    if args.k_lex:
        EXTRA_ENGINE_FLAGS.extend(["--k-lex", str(args.k_lex)])
    if args.budget:
        BUDGET = args.budget
    if args.repos_dir is not None:
        SWEBENCH_REPOS = args.repos_dir

    if not ROUST_BIN.exists():
        raise SystemExit(f"roust binary not found at {ROUST_BIN}")

    reason = swebench_driver_guard()
    if reason:
        raise SystemExit(f"REFUSED to run: {reason}")

    # Blocking engine-provenance check (shared with region_eval2.py): refuses
    # to run if ROUST_BIN's embedded sha/dirty state does not match this
    # worktree's roust-rs/ HEAD + dirty state. NOTE: region_eval2's guard
    # resolves ROUST_BIN/REPO_ROOT from ITS OWN module constants, which point
    # at the same worktree tree as this script's (__file__-relative), so the
    # comparison is against the correct private checkout.
    version = check_engine_provenance(args.allow_stale_engine)
    print(f"engine version: {version}", file=sys.stderr)
    print(f"EXTRA_ENGINE_FLAGS={EXTRA_ENGINE_FLAGS}", file=sys.stderr, flush=True)
    print(f"gold parquet: {args.gold_parquet}", file=sys.stderr)
    print(f"pad_lines={args.pad_lines} len_exp={args.len_exp} "
          f"max_additions={args.max_additions} budget={BUDGET} "
          f"instances={args.instances}", file=sys.stderr)

    rows = load_verified_rows(args.gold_parquet, args.limit,
                              only=_load_instance_filter(args.instances))
    args.report.parent.mkdir(parents=True, exist_ok=True)

    n_ok = 0
    n_err = 0
    t0 = time.time()
    with args.report.open("w") as fh:
        for i, row in enumerate(rows, 1):
            rec = eval_verified_instance(row, args.timeout, args.pad_lines, args.len_exp)
            rec["max_additions"] = args.max_additions
            rec["seats_per_source"] = args.seats_per_source
            rec["import_hops"] = args.import_hops
            rec["import_edges_v2"] = args.import_edges_v2
            rec["eligible_floor"] = args.eligible_floor
            rec["k_lex"] = args.k_lex
            rec["budget"] = BUDGET
            fh.write(json.dumps(rec, default=str) + "\n")
            fh.flush()
            if rec["error"] is None:
                n_ok += 1
            else:
                n_err += 1
            if not args.quiet and (i % PROGRESS_EVERY == 0 or i == len(rows)):
                elapsed = time.time() - t0
                print(f"[{i}/{len(rows)}] {row['instance_id']:45} elapsed={elapsed:.0f}s "
                      f"({'ERR' if rec['error'] else 'ok'}) ok={n_ok} err={n_err}", flush=True,
                      file=sys.stderr)

    print(f"\nengine version: {version}", file=sys.stderr)
    print(f"wrote {len(rows)} records ({n_ok} ok, {n_err} errors) to {args.report}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
