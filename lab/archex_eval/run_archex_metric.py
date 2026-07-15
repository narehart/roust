#!/usr/bin/env python3
"""Agentless-metric evaluation harness for ARCHEX on SWE-bench Lite.

Sibling of `parity/region_eval2.py` (roust): same gold-hunk parsing
(`parse_gold_hunks`), same checkout-then-invoke loop, same per-instance
aggregate fields (`hunk_file_covered`, `hunk_line_recall`, `hunk_touched`,
`all_gold_files_retrieved`, `tokens`), and the same persisted `regions` dict
({path: [[start, end], ...]}), so `lab/agentless_metric.py`'s exact
FILE/FUNCTION/LINE "% Correct Location" machinery can score the output
unchanged (point it at this script's JSONL instead of full300_v8.jsonl).

archex specifics (v0.19.2, `archex query --format json`):
  - Retrieved content comes back as `chunks[]`, each with `chunk.file_path`,
    `chunk.start_line`, `chunk.end_line` (1-based inclusive). `regions` here
    is the per-file union of those spans (merged when overlapping/adjacent),
    i.e. the archex analogue of roust's packed region spans.
  - `type_definitions[]` also carry file_path/start_line/end_line and their
    source content IS part of the returned bundle, so they are included by
    default; `--chunks-only` restricts regions to `chunks[]`.
  - `tokens` is the bundle's self-reported consumed `token_count`
    (`receipt.token_budget.consumed`), analogous to roust's `bundle_tokens`.

Index lifecycle (measured, not assumed):
  - `archex init` appends its ignore rule to the TRACKED .gitignore; the next
    `git checkout -f` reverts that file, after which `git clean -fd` DELETES
    .archex/. This harness instead writes ".archex/" into .git/info/exclude
    (untracked, survives checkouts) once per repo, so the index persists and
    `archex index` after each checkout is an incremental delta refresh.
  - Default retrieval config is BM25-only (archex's own shipped default;
    strategy reported as "bm25+graph"). `--vector` enables the FastEmbed/ONNX
    vector leg via env overrides (ARCHEX_VECTOR=true, ARCHEX_EMBEDDER=
    fastembed) and queries with --strategy hybrid; instances are processed
    sorted by (repo, base_commit date) to minimize per-step re-embedding.

Usage (pilot, on COPIES of the swebench checkouts):
    .venv-pkg/bin/python lab/archex_eval/run_archex_metric.py \
        --repos-root /path/to/pilot/copies \
        --instances pallets__flask-4045,psf__requests-1963 \
        --report /tmp/archex_pilot.jsonl

Usage (full 300, only when lab/swebench_repos/ is unlocked):
    .venv-pkg/bin/python lab/archex_eval/run_archex_metric.py \
        --report lab/results_regions/archex300_v1.jsonl

Output: pure JSONL, one record per instance, flushed as each completes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "parity"))
from region_eval import line_in_spans, parse_gold_hunks, swebench_driver_guard  # noqa: E402

LITE_PARQUET = REPO_ROOT / "lab" / "swebench_lite.parquet"
LITE_REPOS = REPO_ROOT / "lab" / "swebench_repos"

BUDGET = 8192
DEFAULT_TIMEOUT_S = 300
PROGRESS_EVERY = 10


# ---------------------------------------------------------------------------
# archex invocation
# ---------------------------------------------------------------------------


def archex_env(vector: bool) -> dict[str, str]:
    env = dict(os.environ)
    if vector:
        env["ARCHEX_VECTOR"] = "true"
        env["ARCHEX_EMBEDDER"] = "fastembed"
    return env


def archex_version() -> str:
    proc = subprocess.run(["archex", "--version"], capture_output=True, text=True, timeout=30)
    return proc.stdout.strip() or proc.stderr.strip()


def ensure_git_exclude(repo_path: Path) -> None:
    """Persist .archex/ across `git checkout -f && git clean -fd`.

    archex init appends its rule to the tracked .gitignore, which checkout
    reverts -- after which clean deletes .archex/. .git/info/exclude is not
    tracked, so a rule there survives every checkout."""
    exclude = repo_path / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text() if exclude.exists() else ""
    if ".archex/" not in existing:
        with exclude.open("a") as fh:
            fh.write("\n.archex/\n")


def checkout(repo_path: Path, sha: str) -> None:
    r = subprocess.run(["git", "checkout", "-f", "-q", sha], cwd=repo_path,
                        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"checkout {sha} in {repo_path} failed: {r.stderr.strip()[:300]}")
    subprocess.run(["git", "clean", "-fdq"], cwd=repo_path, capture_output=True,
                    text=True, timeout=300)


def archex_index(repo_path: Path, vector: bool, timeout: float) -> tuple[float, str | None]:
    """Build/refresh the index. Returns (wall_seconds, error)."""
    t0 = time.time()
    try:
        proc = subprocess.run(["archex", "index", str(repo_path)], capture_output=True,
                               text=True, timeout=timeout, env=archex_env(vector))
    except subprocess.TimeoutExpired:
        return time.time() - t0, f"archex index timed out after {timeout}s"
    except OSError as exc:
        return time.time() - t0, f"failed to spawn archex index: {exc}"
    if proc.returncode != 0:
        return time.time() - t0, (f"archex index exit {proc.returncode}: "
                                   f"stderr[:300]={proc.stderr[:300]!r}")
    return time.time() - t0, None


def run_archex_query(query: str, repo_path: Path, vector: bool,
                      timeout: float) -> tuple[dict | None, float, str | None]:
    """Runs archex query --format json. Returns (parsed_json, wall_s, error)."""
    argv = ["archex", "query", "--format", "json", "--budget", str(BUDGET)]
    if vector:
        argv += ["--strategy", "hybrid"]
    argv += ["--", query]
    t0 = time.time()
    try:
        proc = subprocess.run(argv, cwd=repo_path, capture_output=True, text=True,
                               timeout=timeout, env=archex_env(vector))
    except subprocess.TimeoutExpired:
        return None, time.time() - t0, f"archex query timed out after {timeout}s"
    except OSError as exc:
        return None, time.time() - t0, f"failed to spawn archex query: {exc}"
    wall = time.time() - t0
    if proc.returncode != 0:
        return None, wall, f"archex query exit {proc.returncode}: stderr[:300]={proc.stderr[:300]!r}"
    stdout = proc.stdout.strip()
    if not stdout:
        return None, wall, "empty stdout"
    try:
        obj = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return None, wall, f"bad JSON: {exc}"
    if not isinstance(obj, dict) or "chunks" not in obj:
        return None, wall, 'JSON output has no "chunks" key'
    return obj, wall, None


# ---------------------------------------------------------------------------
# archex JSON -> regions dict (roust-compatible shape)
# ---------------------------------------------------------------------------


def merge_spans(spans: list[tuple[int, int]]) -> list[list[int]]:
    """Union of 1-based inclusive spans; overlapping/adjacent spans merge."""
    out: list[list[int]] = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def regions_from_bundle(obj: dict, chunks_only: bool) -> dict[str, list[list[int]]]:
    per_file: dict[str, list[tuple[int, int]]] = {}

    def add(entry: dict) -> None:
        path = entry.get("file_path")
        start = entry.get("start_line")
        end = entry.get("end_line")
        if not path or not isinstance(start, int) or not isinstance(end, int):
            return
        per_file.setdefault(path, []).append((start, end))

    for item in obj.get("chunks", []):
        add(item.get("chunk", {}))
    if not chunks_only:
        for td in obj.get("type_definitions", []):
            add(td)
    return {path: merge_spans(spans) for path, spans in sorted(per_file.items())}


# ---------------------------------------------------------------------------
# instance loop (mirrors parity/region_eval2.py)
# ---------------------------------------------------------------------------


def load_lite_rows(limit: int, instances: set[str] | None,
                    repos_root: Path) -> list[dict]:
    import pandas as pd
    df = pd.read_parquet(LITE_PARQUET)
    rows = []
    for _, row in df.iterrows():
        if instances and row["instance_id"] not in instances:
            continue
        rows.append({
            "instance_id": row["instance_id"],
            "repo": row["repo"],
            "base_commit": row["base_commit"],
            "patch": row["patch"],
            "problem_statement": row["problem_statement"],
        })
    rows = order_rows(rows, repos_root)
    if limit:
        rows = rows[:limit]
    return rows


def order_rows(rows: list[dict], repos_root: Path) -> list[dict]:
    """Group by repo and order each repo's instances by base_commit author
    date (ascending), so consecutive checkouts are near each other in history
    and the incremental index refresh (and, in --vector mode, re-embedding)
    touches the smallest possible delta."""
    dates: dict[str, int] = {}
    for row in rows:
        repo_path = repos_root / row["repo"].replace("/", "__")
        key = row["base_commit"]
        if key in dates or not repo_path.exists():
            continue
        r = subprocess.run(["git", "log", "-1", "--format=%ct", key], cwd=repo_path,
                            capture_output=True, text=True, timeout=60)
        try:
            dates[key] = int(r.stdout.strip())
        except ValueError:
            dates[key] = 0
    return sorted(rows, key=lambda r: (r["repo"], dates.get(r["base_commit"], 0),
                                        r["instance_id"]))


def eval_lite_instance(row: dict, repos_root: Path, vector: bool, chunks_only: bool,
                        timeout: float) -> dict:
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
        "engine": "archex",
        "strategy": None,
        "index_seconds": None,
        "query_seconds": None,
    }
    if not gold_files:
        rec["error"] = "no old-file hunk lines in gold patch (pure file creation(s) only)"
        return rec

    repo_path = repos_root / row["repo"].replace("/", "__")
    if not repo_path.exists():
        rec["error"] = f"repo checkout not found: {repo_path}"
        return rec
    try:
        ensure_git_exclude(repo_path)
        checkout(repo_path, row["base_commit"])
    except (RuntimeError, OSError) as exc:
        rec["error"] = f"checkout failed: {exc}"
        return rec

    index_s, err = archex_index(repo_path, vector, timeout)
    rec["index_seconds"] = round(index_s, 2)
    if err:
        rec["error"] = err
        return rec

    obj, query_s, err = run_archex_query(row["problem_statement"], repo_path, vector, timeout)
    rec["query_seconds"] = round(query_s, 2)
    if err:
        rec["error"] = err
        return rec

    regions = regions_from_bundle(obj, chunks_only)
    rec["regions"] = regions
    files_in_regions = set(regions.keys())

    meta = obj.get("retrieval_metadata", {})
    rec["strategy"] = meta.get("strategy")
    rec["n_chunks"] = len(obj.get("chunks", []))
    rec["n_type_definitions"] = len(obj.get("type_definitions", []))
    rec["truncated"] = obj.get("truncated")

    # (1) hunk-file-covered
    covered_files = [f for f in gold_files if f in files_in_regions]
    rec["hunk_file_covered"] = len(covered_files) / len(gold_files)
    rec["all_gold_files_retrieved"] = len(covered_files) == len(gold_files)

    # (2) hunk line recall
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

    # (3) hunk-touched
    total_hunks = 0
    touched_hunks = 0
    for f, ranges in gold_hunks.items():
        spans = regions.get(f, [])
        for s, e in ranges:
            total_hunks += 1
            if any(line_in_spans(ln, spans) for ln in range(s, e + 1)):
                touched_hunks += 1
    rec["hunk_touched"] = touched_hunks / total_hunks if total_hunks else None

    # (4) tokens of bundle (consumed, self-reported)
    rec["tokens"] = obj.get("token_count")

    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="cap instance count (0 = all)")
    ap.add_argument("--instances", type=str, default="",
                    help="comma-separated instance_id allowlist (pilot mode)")
    ap.add_argument("--repos-root", type=Path, default=LITE_REPOS,
                    help="root of <owner>__<name> checkouts (use a COPY for pilots)")
    ap.add_argument("--vector", action="store_true",
                    help="enable FastEmbed vector leg + hybrid strategy "
                         "(default: archex's shipped BM25-only config)")
    ap.add_argument("--chunks-only", action="store_true",
                    help="regions from chunks[] only (exclude type_definitions[])")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    ap.add_argument("--report", type=Path, required=True, help="JSONL output path")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.repos_root.resolve() == LITE_REPOS.resolve():
        reason = swebench_driver_guard()
        if reason:
            raise SystemExit(f"REFUSED to run on lab/swebench_repos: {reason}")

    version = archex_version()
    print(f"archex version: {version} "
          f"(mode={'vector+hybrid' if args.vector else 'bm25 (default)'})", file=sys.stderr)

    instances = {s.strip() for s in args.instances.split(",") if s.strip()} or None
    rows = load_lite_rows(args.limit, instances, args.repos_root)
    if not rows:
        raise SystemExit("no instances matched")
    args.report.parent.mkdir(parents=True, exist_ok=True)

    n_ok = 0
    n_err = 0
    t0 = time.time()
    with args.report.open("w") as fh:
        for i, row in enumerate(rows, 1):
            rec = eval_lite_instance(row, args.repos_root, args.vector,
                                      args.chunks_only, args.timeout)
            rec["archex_version"] = version
            fh.write(json.dumps(rec, default=str) + "\n")
            fh.flush()
            if rec["error"] is None:
                n_ok += 1
            else:
                n_err += 1
            if not args.quiet and (i % PROGRESS_EVERY == 0 or i == len(rows)):
                elapsed = time.time() - t0
                print(f"[{i}/{len(rows)}] {row['instance_id']:45} elapsed={elapsed:.0f}s "
                      f"({'ERR' if rec['error'] else 'ok'}) ok={n_ok} err={n_err}",
                      flush=True, file=sys.stderr)

    print(f"\narchex version: {version}", file=sys.stderr)
    print(f"wrote {len(rows)} records ({n_ok} ok, {n_err} errors) to {args.report}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
