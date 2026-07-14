#!/usr/bin/env python3
"""ContextBench adapter for roust: one-shot region retrieval -> single-step trajectory.

Protocol
--------
For each task in the ContextBench Verified parquet (filtered to --language):
  1. Check out repo@base_commit using ContextBench's own `checkout()` helper
     (blob-filtered base clone per repo + detached worktree per commit).
  2. Run the frozen roust release binary once:
         roust --json --budget <B> "<problem_statement>" <worktree>
  3. Map roust's `regions: {file: [[start_line, end_line], ...]}` to a
     SINGLE-STEP ContextBench trajectory:
         traj_data.pred_steps  = [ {files, spans} ]   (the one and only step)
         traj_data.pred_files  = files that made it into the packed bundle
         traj_data.pred_spans  = {file: [{"start": s, "end": e}, ...]}
  4. (--evaluate) score each repo-group chunk with ContextBench's OWN
     evaluator (`python -m contextbench.evaluate`), then prune that repo's
     worktrees so peak disk stays bounded; base clones are kept.

Scoring is 100% ContextBench code: this script only formats predictions and
merges the evaluator's per-chunk JSONL outputs with their own
`aggregate_results()` (micro-average).

Efficiency metrics (AUC-Coverage / Redundancy) are N/A for roust: it is a
one-shot retrieval tool, so the "trajectory" has exactly one step and
AUC == final coverage by construction. We report final Coverage/Precision at
file / symbol("block") / line granularity only.

Run with the evaluator's venv python (needs pyarrow + tree-sitter):
    <evaluator>/.venv/bin/python run_contextbench.py \
        --evaluator <ContextBench clone> \
        --cache lab/contextbench_repos/cache \
        --tmp-root lab/contextbench_repos/tmp \
        --out-dir lab/contextbench_repos/run1 \
        --language python --evaluate
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROUST_DEFAULT = "/Users/nicholasarehart/programming-projects/bgrep/roust-rs/target/release/roust"
MAX_QUERY_CHARS = 200_000  # argv safety margin (macOS ARG_MAX is 1 MiB)


def load_tasks(gold_path: str, language: str, ids: set[str] | None) -> list[dict]:
    import pyarrow.parquet as pq

    cols = [
        "instance_id", "original_inst_id", "repo", "repo_url", "language",
        "base_commit", "problem_statement", "source",
    ]
    rows = pq.read_table(gold_path, columns=cols).to_pylist()
    if language:
        rows = [r for r in rows if (r.get("language") or "").lower() == language.lower()]
    if ids:
        rows = [r for r in rows if r["instance_id"] in ids or (r.get("original_inst_id") or "") in ids]
    rows.sort(key=lambda r: (r.get("repo") or "", r["instance_id"]))
    return rows


def roust_version(roust_bin: str) -> str:
    return subprocess.run(
        [roust_bin, "--version"], capture_output=True, text=True, timeout=30
    ).stdout.strip()


def run_roust(roust_bin: str, query: str, repo_dir: str, budget: int, timeout: int) -> tuple[dict | None, str, float]:
    """Run roust once. Returns (parsed_json | None, error_string, wall_seconds)."""
    q = query if len(query) <= MAX_QUERY_CHARS else query[:MAX_QUERY_CHARS]
    t0 = time.perf_counter()
    try:
        p = subprocess.run(
            [roust_bin, "--json", "--budget", str(budget), q, repo_dir],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, f"roust_timeout_{timeout}s", time.perf_counter() - t0
    dt = time.perf_counter() - t0
    if p.returncode != 0:
        return None, f"roust_exit_{p.returncode}: {p.stderr.strip()[-300:]}", dt
    try:
        return json.loads(p.stdout), "", dt
    except json.JSONDecodeError as e:
        return None, f"roust_bad_json: {e}", dt


def to_trajectory_row(task: dict, roust_out: dict, version: str, budget: int, wall_s: float) -> dict:
    regions = roust_out.get("regions") or {}
    pred_spans = {
        f: [{"start": int(s), "end": int(e)} for s, e in spans]
        for f, spans in regions.items() if spans
    }
    pred_files = sorted(pred_spans.keys())
    step = {"files": pred_files, "spans": pred_spans}
    return {
        "instance_id": task["instance_id"],
        "original_inst_id": task.get("original_inst_id") or "",
        "repo_url": task.get("repo_url") or "",
        "commit": task["base_commit"],
        "traj_data": {
            "pred_steps": [step],           # one-shot tool -> single-step trajectory
            "pred_files": pred_files,
            "pred_spans": pred_spans,
        },
        "model_patch": "",                   # roust retrieves context; it does not edit
        "roust_version": version,
        "roust_budget": budget,
        "roust_wall_s": round(wall_s, 3),
        "roust_stats": roust_out.get("stats") or {},
    }


def prune_worktrees(base_dir: str, worktree_root: str) -> None:
    """Remove all per-commit worktrees for one repo; keep the base clone."""
    root = Path(worktree_root)
    if root.is_dir():
        for wt in root.iterdir():
            if wt.is_dir():
                subprocess.run(
                    ["git", "-C", base_dir, "worktree", "remove", "--force", str(wt)],
                    capture_output=True, text=True,
                )
        shutil.rmtree(root, ignore_errors=True)
    if os.path.isdir(base_dir):
        subprocess.run(["git", "-C", base_dir, "worktree", "prune"], capture_output=True)


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--evaluator", required=True, help="path to the ContextBench repo clone")
    ap.add_argument("--gold", default="", help="gold parquet (default: <evaluator>/data/contextbench_verified.parquet)")
    ap.add_argument("--cache", required=True, help="repo cache dir (base clones)")
    ap.add_argument("--tmp-root", required=True, help="CONTEXTBENCH_TMP_ROOT (per-commit worktrees)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--roust", default=ROUST_DEFAULT)
    ap.add_argument("--budget", type=int, default=8192)
    ap.add_argument("--language", default="python")
    ap.add_argument("--ids", default="", help="optional file with one instance_id per line (pilot)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=600, help="per-task roust timeout (s)")
    ap.add_argument("--evaluate", action="store_true", help="run ContextBench's evaluator per repo chunk")
    ap.add_argument("--keep-worktrees", action="store_true")
    args = ap.parse_args()

    evaluator = os.path.abspath(args.evaluator)
    gold = os.path.abspath(args.gold or os.path.join(evaluator, "data", "contextbench_verified.parquet"))
    cache = os.path.abspath(args.cache)
    tmp_root = os.path.abspath(args.tmp_root)
    out_dir = Path(args.out_dir).absolute()

    os.makedirs(cache, exist_ok=True)
    os.makedirs(tmp_root, exist_ok=True)
    for sub in ("chunks", "results", "logs"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)

    os.environ["CONTEXTBENCH_TMP_ROOT"] = tmp_root
    sys.path.insert(0, evaluator)
    from contextbench.core import checkout
    from contextbench.core.repo import _normalize_url

    ids = None
    if args.ids:
        ids = {l.strip() for l in open(args.ids, encoding="utf-8") if l.strip()}
    tasks = load_tasks(gold, args.language, ids)
    if args.limit:
        tasks = tasks[: args.limit]

    version = roust_version(args.roust)
    print(f"roust: {version}", file=sys.stderr)
    print(f"tasks: {len(tasks)} (language={args.language or 'all'})", file=sys.stderr)

    preds_path = out_dir / "predictions.jsonl"
    skips_path = out_dir / "skips.jsonl"
    done = {r["instance_id"] for r in read_jsonl(preds_path)}
    skipped_prev = {r["instance_id"] for r in read_jsonl(skips_path)}

    by_repo: dict[str, list[dict]] = defaultdict(list)
    for t in tasks:
        by_repo[t.get("repo") or "unknown"].append(t)

    manifest = {
        "roust_version": version,
        "roust_binary": args.roust,
        "budget": args.budget,
        "language": args.language,
        "gold": gold,
        "n_tasks": len(tasks),
        "n_repos": len(by_repo),
        "protocol": "single-step trajectory from one roust --json call per task",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    n_ok = n_skip = 0
    for ri, (repo, group) in enumerate(sorted(by_repo.items()), 1):
        repo_url = group[0].get("repo_url") or f"https://github.com/{repo}.git"
        repo_key = _normalize_url(repo_url)
        chunk_path = out_dir / "chunks" / f"{repo_key}.jsonl"
        result_path = out_dir / "results" / f"{repo_key}.jsonl"
        print(f"[{ri}/{len(by_repo)}] {repo}: {len(group)} tasks", file=sys.stderr)

        chunk_rows = [r for r in read_jsonl(chunk_path)]
        chunk_ids = {r["instance_id"] for r in chunk_rows}

        with open(preds_path, "a", encoding="utf-8") as pf, \
             open(skips_path, "a", encoding="utf-8") as sf, \
             open(chunk_path, "a", encoding="utf-8") as cf:
            for t in group:
                iid = t["instance_id"]
                if iid in done or iid in skipped_prev:
                    n_ok += iid in done
                    n_skip += iid in skipped_prev
                    continue
                repo_dir = checkout(repo_url, t["base_commit"], cache, verbose=False)
                if not repo_dir:
                    sf.write(json.dumps({"instance_id": iid, "error": "checkout_failed"}) + "\n")
                    sf.flush()
                    n_skip += 1
                    print(f"    SKIP {iid}: checkout_failed", file=sys.stderr)
                    continue
                obj, err, wall = run_roust(args.roust, t["problem_statement"] or "", repo_dir, args.budget, args.timeout)
                if obj is None or not (obj.get("regions") or {}):
                    reason = err or "empty_regions"
                    sf.write(json.dumps({"instance_id": iid, "error": reason}) + "\n")
                    sf.flush()
                    n_skip += 1
                    print(f"    SKIP {iid}: {reason}", file=sys.stderr)
                    continue
                row = to_trajectory_row(t, obj, version, args.budget, wall)
                pf.write(json.dumps(row) + "\n")
                pf.flush()
                if iid not in chunk_ids:
                    cf.write(json.dumps(row) + "\n")
                    cf.flush()
                done.add(iid)
                n_ok += 1
                print(f"    ok {iid}: {len(row['traj_data']['pred_files'])} files, {wall:.1f}s", file=sys.stderr)

        if args.evaluate and chunk_path.is_file() and chunk_path.stat().st_size > 0:
            need_eval = not result_path.is_file() or len(read_jsonl(result_path)) < len(read_jsonl(chunk_path))
            if need_eval:
                log_path = out_dir / "logs" / f"{repo_key}.log"
                with open(log_path, "w", encoding="utf-8") as lf:
                    ev = subprocess.run(
                        [sys.executable, "-m", "contextbench.evaluate",
                         "--gold", gold, "--pred", str(chunk_path),
                         "--cache", cache, "--out", str(result_path)],
                        cwd=evaluator, stdout=lf, stderr=subprocess.STDOUT,
                        env={**os.environ, "CONTEXTBENCH_TMP_ROOT": tmp_root},
                    )
                if ev.returncode != 0:
                    print(f"    EVAL FAILED for {repo} (see {log_path})", file=sys.stderr)

        if not args.keep_worktrees:
            base_dir = os.path.join(cache, repo_key)
            prune_worktrees(base_dir, os.path.join(tmp_root, "contextbench_worktrees", repo_key))

    # ---- merge + aggregate with ContextBench's own code ----
    if args.evaluate:
        all_results: list[dict] = []
        for rp in sorted((out_dir / "results").glob("*.jsonl")):
            all_results.extend(read_jsonl(rp))
        with open(out_dir / "results_all.jsonl", "w", encoding="utf-8") as f:
            for r in all_results:
                f.write(json.dumps(r) + "\n")
        from contextbench.evaluate import aggregate_results
        agg = aggregate_results(all_results)
        agg["roust_version"] = version
        agg["budget"] = args.budget
        agg["language"] = args.language
        agg["n_predicted"] = n_ok
        agg["n_skipped"] = n_skip
        agg["n_tasks"] = len(tasks)
        (out_dir / "aggregate.json").write_text(json.dumps(agg, indent=2) + "\n")
        print(json.dumps(agg, indent=2))

    print(f"done: predicted={n_ok} skipped={n_skip} of {len(tasks)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
