#!/usr/bin/env python3
"""Quantitative gate for the pack_regions symbol-name-anchoring fix
(w_name sweep): hunk-line-recall on the SWE-bench Lite stride-5 subset,
driving lanes2 IN-PROCESS (no CLI subprocess) with the frozen-v7 wiring
parity/shim_reference.py documents:

    history=True, comments=False, anchors=True, testbridge=True,
    docsbridge=True, use_ppr=True, keywords=[]

i.e. Corpus(history_msgs=..., use_comments=False, build_docs=True),
query_terms(query, []), extract_symbol_anchors(query, corpus),
select_files(..., use_ppr=True, cochange=..., anchors=..., use_testbridge=True,
use_docsbridge=True), pack_regions(..., budget_tokens=8192, count_tokens, w_name=W).

Gold-hunk parsing (parse_gold_hunks) and the line-in-span helper
(line_in_spans) are REUSED from parity/region_eval.py (imported, not
duplicated), along with load_lite_rows/aggregate_lite/mean_median for the
same stride-subset selection and aggregation logic the 0.4149053... subset
baseline (lab/results_regions/subset_stride5_final.json) was measured with.

REV-BASED REPO ACCESS (no `git checkout -f` on the shared lab/swebench_repos
clones): a benchmark (lab/tokenbench/run_bench.py) may be running
concurrently -- it does not touch lab/swebench_repos, but per spec this
script avoids checkout anyway for safety. Each instance's repo tree at
base_commit is materialized via `git archive <sha> | tar -x` into a private
scratch temp dir (never mutates the shared clone's working tree or index);
git-log-based history mining (mine_history) is similarly rev-scoped (an
explicit <sha> positional argument on `git log`, not a bare HEAD-relative
walk) against the shared clone, which only reads .git objects.

Cost note: select_files (and everything feeding it -- Corpus build, history
mining, anchors) is independent of w_name, so it runs ONCE per instance;
only pack_regions (cheap, pure-Python) is re-run per swept w_name value.

Usage:
    python3 lab/region_eval_lanes.py [--stride N] [--offset N] [--limit N]
        [--w-name W [W ...]] [--report PATH.json]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAB_DIR = REPO_ROOT / "lab"
PARITY_DIR = REPO_ROOT / "parity"
sys.path.insert(0, str(LAB_DIR))
sys.path.insert(0, str(PARITY_DIR))

import lanes2 as L  # noqa: E402
import history as H  # noqa: E402
import region_eval as R  # noqa: E402
from region_eval import (  # noqa: E402
    parse_gold_hunks, line_in_spans, load_lite_rows, aggregate_lite,
    mean_median, bucket_of, BUCKET_ORDER, swebench_driver_guard,
)

# region_eval.py's LITE_PARQUET/LITE_REPOS point at a session-specific
# scratch dir (parity/region_eval.py's own _SCRATCH convention) that may not
# exist in this session -- load_lite_rows() reads the module-global
# LITE_PARQUET internally, so it must be repointed at this repo's checked-in
# copy before any row loading happens. LITE_REPOS is not used via the
# region_eval module here (this script defines its own LITE_REPOS, below).
R.LITE_PARQUET = LAB_DIR / "swebench_lite.parquet"

import tiktoken  # noqa: E402

_ENCODER = tiktoken.get_encoding("cl100k_base")
_BUDGET_TOKENS = 8192
LITE_REPOS = LAB_DIR / "swebench_repos"

W_NAME_DEFAULT = [0.0, 1.0, 2.0, 4.0]


def count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text, disallowed_special=()))


# ---------------------------------------------------------------------------
# rev-based repo access (no checkout on the shared clone)
# ---------------------------------------------------------------------------


def archive_snapshot(repo_path: Path, sha: str, dest: Path) -> None:
    """Materializes repo_path's tree at `sha` into `dest` via `git archive`
    piped straight into `tar -x` -- reads .git objects only, never touches
    repo_path's working tree or index."""
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "-C", str(repo_path), "archive", sha],
        capture_output=True, timeout=120,
    )
    if archive.returncode != 0:
        raise RuntimeError(
            f"git archive {sha} in {repo_path} failed: "
            f"{archive.stderr.decode('utf-8', errors='replace')[:300]}"
        )
    tar = subprocess.run(
        ["tar", "-x", "-C", str(dest)], input=archive.stdout,
        capture_output=True, timeout=120,
    )
    if tar.returncode != 0:
        raise RuntimeError(
            f"tar -x into {dest} failed: {tar.stderr.decode('utf-8', errors='replace')[:300]}"
        )


def _list_current_files(snapshot_dir: Path) -> set[str]:
    """Mirror of shim_reference.py's _list_current_files, applied to the
    archived snapshot (identical file content to a real checkout at that
    rev, without ever creating one in the shared clone)."""
    files: set[str] = set()
    for p in snapshot_dir.rglob("*"):
        if not p.is_file() or p.suffix not in L.CODE_EXTENSIONS:
            continue
        rel = str(p.relative_to(snapshot_dir))
        if rel.startswith(".git/") or "/.git/" in rel:
            continue
        try:
            if p.stat().st_size > L.MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        files.add(rel)
    return files


def mine_history_at_rev(
    repo_path: Path, rev: str, max_commits: int = 5000, current_files: set[str] | None = None,
) -> tuple[dict[str, str], dict[str, dict[str, int]], dict[str, dict]]:
    """Byte-for-byte copy of history.mine_history's body, with ONE change:
    `git log` is given an explicit `rev` positional argument instead of
    walking bare (HEAD-relative). This makes history mining rev-scoped
    without requiring repo_path's working tree to be checked out to `rev`
    at all -- `git log <rev> ...` only reads .git objects, exactly like
    git-archive above. Reuses history.py's own parsing helpers
    (_parse_commit, _is_code_file, _bridge_cochange) and constants
    unmodified, so parsing semantics are identical to the real mine_history;
    only the git invocation's revision scope differs."""
    if not repo_path.exists():
        return {}, {}, {}

    r = subprocess.run(
        [
            "git", "log", rev, "--no-merges", "-n", str(max_commits),
            f"--pretty=format:{H._SENTINEL}%at%x00%an%x00%s%n%b",
            "--name-only",
        ],
        cwd=repo_path, capture_output=True, text=True, timeout=600,
        encoding="utf-8", errors="replace",
    )
    if r.returncode != 0 or not r.stdout:
        return {}, {}, {}

    lines = r.stdout.splitlines()
    headers: list[int] = [i for i, ln in enumerate(lines) if ln.startswith(H._SENTINEL)]

    from collections import Counter, defaultdict
    msgs: dict[str, list[str]] = defaultdict(list)
    cochange_counts: dict[str, Counter] = defaultdict(Counter)
    n_commits: Counter = Counter()
    last_ts: dict[str, int] = {}
    authors: dict[str, Counter] = defaultdict(Counter)
    fileset = current_files

    for idx, start in enumerate(headers):
        end = headers[idx + 1] if idx + 1 < len(headers) else len(lines)
        header = lines[start][len(H._SENTINEL):]
        ts_str, _, header_rest = header.partition("\x00")
        author, _, subject = header_rest.partition("\x00")
        try:
            ts = int(ts_str)
        except ValueError:
            ts = 0
        _msg, files = H._parse_commit(subject, lines[start + 1: end])
        if fileset is not None:
            files = [f for f in files if f in fileset]
        code_files = [f for f in files if H._is_code_file(f)]
        if not code_files:
            continue
        for f in code_files:
            n_commits[f] += 1
            if f not in last_ts:
                last_ts[f] = ts
            authors[f][author] += 1
            if len(msgs[f]) < H.MAX_MSGS_PER_FILE:
                msgs[f].append(_msg)
        if len(files) <= H.BULK_COMMIT_FILE_LIMIT and len(code_files) >= 2:
            from itertools import combinations
            for a, b in combinations(sorted(set(code_files)), 2):
                cochange_counts[a][b] += 1
                cochange_counts[b][a] += 1

    out_msgs: dict[str, str] = {}
    for f, parts in msgs.items():
        text = "\n".join(parts)
        out_msgs[f] = text[:H.MAX_MSG_CHARS]

    out_cochange: dict[str, dict[str, int]] = {}
    for f, counter in cochange_counts.items():
        top = [(o, n) for o, n in counter.most_common() if n >= H.MIN_COCHANGE_COUNT][:H.MAX_COCHANGE_PARTNERS]
        if top:
            out_cochange[f] = dict(top)

    bridges = H._bridge_cochange(cochange_counts)
    for f, bcounter in bridges.items():
        top_bridge = dict(sorted(bcounter.items(), key=lambda kv: -kv[1])[:H.MAX_COCHANGE_PARTNERS])
        if not top_bridge:
            continue
        merged = dict(out_cochange.get(f, {}))
        for o, c in top_bridge.items():
            merged[o] = max(merged.get(o, 0), c)
        out_cochange[f] = dict(sorted(merged.items(), key=lambda kv: -kv[1])[:H.MAX_COCHANGE_PARTNERS])

    out_meta: dict[str, dict] = {
        f: {
            "n_commits": n_commits[f], "last_ts": last_ts[f],
            "authors": dict(authors[f].most_common(H.MAX_AUTHORS_PER_FILE)),
        }
        for f in n_commits
    }
    return out_msgs, out_cochange, out_meta


# ---------------------------------------------------------------------------
# per-instance evaluation
# ---------------------------------------------------------------------------


def eval_instance(row: dict, w_names: list[float], scratch_root: Path) -> dict[float, dict]:
    """Runs select_files ONCE (w_name-independent), then pack_regions once
    per swept w_name, reusing the same corpus/files/scores. Returns
    {w_name: record} in the same record shape parity/region_eval.py's
    eval_lite_instance produces (consumed by the reused aggregate_lite)."""
    instance_id = row["instance_id"]
    gold_hunks = parse_gold_hunks(row["patch"])
    gold_files = sorted(gold_hunks.keys())
    base_rec = {
        "instance_id": instance_id, "repo": row["repo"], "base_commit": row["base_commit"],
        "n_gold_files": len(gold_files), "n_gold_hunks": sum(len(v) for v in gold_hunks.values()),
    }
    if not gold_files:
        err = "no old-file hunk lines in gold patch (pure file creation(s) only)"
        return {w: {**base_rec, "error": err} for w in w_names}

    repo_path = LITE_REPOS / row["repo"].replace("/", "__")
    if not repo_path.exists():
        err = f"no local checkout at {repo_path}"
        return {w: {**base_rec, "error": err} for w in w_names}

    snap = scratch_root / f"snap_{instance_id.replace('/', '__')}"
    if snap.exists():
        shutil.rmtree(snap)
    try:
        archive_snapshot(repo_path, row["base_commit"], snap)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        err = f"archive failed: {exc}"
        return {w: {**base_rec, "error": err} for w in w_names}

    try:
        current_files = _list_current_files(snap)
        history_msgs, cochange, _meta = mine_history_at_rev(
            repo_path, row["base_commit"], current_files=current_files,
        )
        corpus = L.Corpus(snap, history_msgs=history_msgs, use_comments=False, build_docs=True)
        terms = L.query_terms(row["problem_statement"], [])
        anchors = L.extract_symbol_anchors(row["problem_statement"], corpus)
        files, scores = L.select_files(
            corpus, terms, use_ppr=True, cochange=cochange, anchors=anchors,
            use_testbridge=True, use_docsbridge=True,
        )
    except Exception as exc:  # best-effort: one bad instance shouldn't kill the sweep
        err = f"select_files failed: {type(exc).__name__}: {exc}"
        return {w: {**base_rec, "error": err} for w in w_names}
    finally:
        shutil.rmtree(snap, ignore_errors=True)

    out: dict[float, dict] = {}
    for w in w_names:
        rec = dict(base_rec)
        rec["error"] = None
        try:
            spans, bundle = L.pack_regions(
                corpus, files, terms, scores, _BUDGET_TOKENS, count_tokens, w_name=w,
            )
        except Exception as exc:
            rec["error"] = f"pack_regions failed: {type(exc).__name__}: {exc}"
            out[w] = rec
            continue

        files_in_regions = set(spans.keys())
        covered_files = [f for f in gold_files if f in files_in_regions]
        rec["hunk_file_covered"] = len(covered_files) / len(gold_files)
        rec["all_gold_files_retrieved"] = len(covered_files) == len(gold_files)

        total_lines = 0
        covered_lines = 0
        for f, ranges in gold_hunks.items():
            line_set: set[int] = set()
            for s, e in ranges:
                line_set.update(range(s, e + 1))
            fspans = spans.get(f, [])
            total_lines += len(line_set)
            covered_lines += sum(1 for ln in line_set if line_in_spans(ln, fspans))
        rec["hunk_line_recall"] = covered_lines / total_lines if total_lines else None

        total_hunks = 0
        touched_hunks = 0
        for f, ranges in gold_hunks.items():
            fspans = spans.get(f, [])
            for s, e in ranges:
                total_hunks += 1
                if any(line_in_spans(ln, fspans) for ln in range(s, e + 1)):
                    touched_hunks += 1
        rec["hunk_touched"] = touched_hunks / total_hunks if total_hunks else None
        rec["tokens"] = count_tokens(bundle)
        rec["schedule"] = None
        rec["deep_files_count"] = None
        rec["skeleton_files_count"] = None
        out[w] = rec
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--w-name", type=float, nargs="+", default=W_NAME_DEFAULT)
    ap.add_argument("--report", type=Path, default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    reason = swebench_driver_guard()
    # Note: swebench_driver_guard() checks for `swebench_driver`, not
    # `run_bench` -- this script uses rev-based git-archive access (never
    # `git checkout -f`), so it is safe regardless; kept as an informational
    # check only, matching the spirit of parity/region_eval.py's guard.
    if reason:
        print(f"NOTE: {reason} (informational only -- this script never checks out "
              f"the shared clones, so it is safe to proceed)", file=sys.stderr)

    scratch_root = Path(tempfile.mkdtemp(prefix="region_eval_lanes_"))
    print(f"scratch snapshots dir: {scratch_root}")

    rows = load_lite_rows(args.limit, stride=args.stride, offset=args.offset)
    print(f"{len(rows)} instances (stride={args.stride}, offset={args.offset})")

    per_w_records: dict[float, list[dict]] = {w: [] for w in args.w_name}
    t0 = time.time()
    for i, row in enumerate(rows, 1):
        recs = eval_instance(row, args.w_name, scratch_root)
        for w, rec in recs.items():
            per_w_records[w].append(rec)
        if not args.quiet:
            base_err = recs[args.w_name[0]].get("error")
            elapsed = time.time() - t0
            print(f"[{i}/{len(rows)}] {row['instance_id']:45} elapsed={elapsed:.0f}s "
                  f"({'ERR: ' + base_err if base_err else 'ok'})", flush=True)

    shutil.rmtree(scratch_root, ignore_errors=True)

    report: dict = {"stride": args.stride, "offset": args.offset, "n_instances": len(rows), "sweep": {}}
    print("\n" + "=" * 78)
    print("W_NAME SWEEP: hunk-line-recall on the SWE-bench Lite stride subset")
    print("=" * 78)
    print(f"{'w_name':>8}  {'n_ok':>5}  {'mean_hlr':>10}  {'median_hlr':>10}  "
          f"{'mean_hlr(all-gold-subset)':>28}")
    for w in args.w_name:
        agg = aggregate_lite(per_w_records[w])
        agg["records"] = per_w_records[w]
        report["sweep"][str(w)] = agg
        b = agg["all_instances"]
        sub = agg["all_gold_files_retrieved_subset"]
        mean_s = f"{b['hunk_line_recall']['mean']:.4f}" if b["hunk_line_recall"]["mean"] is not None else "n/a"
        med_s = f"{b['hunk_line_recall']['median']:.4f}" if b["hunk_line_recall"]["median"] is not None else "n/a"
        sub_mean_s = f"{sub['hunk_line_recall']['mean']:.4f}" if sub["hunk_line_recall"]["mean"] is not None else "n/a"
        print(f"{w:>8.1f}  {agg['n_ok']:>5}  {mean_s:>10}  {med_s:>10}  {sub_mean_s:>28}")

    baseline = report["sweep"].get("0.0")
    if baseline is not None:
        base_mean = baseline["all_instances"]["hunk_line_recall"]["mean"]
        print(f"\nbaseline (w_name=0.0) mean hunk_line_recall: {base_mean}")
        print("expected ~0.4149 (lab/results_regions/subset_stride5_final.json "
              "'all_instances' mean) -- if this doesn't match, the harness "
              "itself is suspect.")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, default=str))
        print(f"\nfull report written to {args.report}")


if __name__ == "__main__":
    main()
