"""Diagnostic: headroom and displacement risk of a BRTracer-style stack-trace
boost (BoostScore = 1/frame_rank, innermost frame = rank 1) for File@1 on
SWE-bench Lite.

Read-only w.r.t. results: uses the existing bgrep pipeline output
(results_swebench/abl_bridges_v7.jsonl) and SWE-bench Lite problem
statements (swebench_lite.parquet). The only mutation performed is `git
checkout` inside the already-cloned repos under swebench_repos/, to list
each repo's *.py files at base_commit for frame-path resolution.

Usage: uv run python diag_stacktrace.py   (run from the archex/ dir so the
archex venv + pandas are on path, per the lab convention)
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
REPO_CACHE = LAB_DIR / "swebench_repos"
RESULTS_PATH = LAB_DIR / "results_swebench" / "abl_bridges_v7.jsonl"
PARQUET_PATH = LAB_DIR / "swebench_lite.parquet"

FRAME_RE = re.compile(r'File "([^"]+)", line \d+(?:, in (\S+))?')

_listing_cache: dict[tuple[str, str], list[str]] = {}


def load_results() -> dict[str, dict]:
    recs = {}
    with RESULTS_PATH.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if "error" in d:
                continue
            recs[d["instance_id"]] = d
    return recs


def load_instances() -> list[dict]:
    import pandas as pd

    df = pd.read_parquet(PARQUET_PATH)
    out = []
    for _, row in df.iterrows():
        out.append({
            "instance_id": row["instance_id"],
            "repo": row["repo"],
            "base_commit": row["base_commit"],
            "problem_statement": row["problem_statement"],
        })
    out.sort(key=lambda r: (r["repo"], r["instance_id"]))
    return out


def checkout(repo_path: Path, sha: str) -> None:
    r = subprocess.run(["git", "checkout", "-f", "-q", sha], cwd=repo_path,
                        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"checkout {sha} failed: {r.stderr.strip()[:300]}")
    subprocess.run(["git", "clean", "-fdq"], cwd=repo_path,
                    capture_output=True, text=True, timeout=300)


def list_py_files(repo_slug: str, sha: str) -> list[str]:
    key = (repo_slug, sha)
    if key in _listing_cache:
        return _listing_cache[key]
    repo_path = REPO_CACHE / repo_slug.replace("/", "__")
    if not (repo_path / ".git").exists():
        _listing_cache[key] = []
        return []
    checkout(repo_path, sha)
    files = []
    for p in repo_path.rglob("*.py"):
        if not p.is_file():
            continue
        if ".git" in p.parts:
            continue
        files.append(p.relative_to(repo_path).as_posix())
    _listing_cache[key] = files
    return files


def resolve_frame(path: str, files: list[str]) -> str | None:
    matches = [F for F in files
               if path.endswith("/" + F) or path == F or path.endswith(F)]
    if not matches:
        return None
    matches.sort(key=len, reverse=True)
    return matches[0]


def main() -> None:
    t0 = time.perf_counter()
    results = load_results()
    instances = [i for i in load_instances() if i["instance_id"] in results]

    total = len(instances)
    traced_n = 0
    traced_resolved_n = 0
    gold_in_frames_traced_n = 0

    upside = []
    downside = []

    fail5_total = 0
    fail5_gold_in_frames = 0
    fail10_total = 0
    fail10_gold_in_frames = 0

    for k, inst in enumerate(instances, 1):
        iid = inst["instance_id"]
        res = results[iid]
        gold = res.get("gold_files", []) or []
        returned = res.get("returned_files", []) or []
        gold_set = set(gold)

        frame_matches = FRAME_RE.findall(inst["problem_statement"])
        frame_paths = [m[0] for m in frame_matches]
        n_frames = len(frame_paths)
        traced = n_frames > 0
        if traced:
            traced_n += 1

        # secondary headroom @5/@10 uses the project's established File@k
        # convention (all gold files present in top-k, matching
        # analyze_v7.py's at_k / driver's all_present), not "any gold".
        fail5 = bool(gold_set) and not gold_set.issubset(set(returned[:5]))
        fail10 = bool(gold_set) and not gold_set.issubset(set(returned[:10]))

        resolved_best_rank: dict[str, int] = {}
        if traced:
            files = list_py_files(inst["repo"], inst["base_commit"])
            if files:
                for idx, path in enumerate(frame_paths):
                    frame_rank = n_frames - idx  # last frame in text = rank 1
                    F = resolve_frame(path, files)
                    if F is None:
                        continue
                    prev = resolved_best_rank.get(F)
                    if prev is None or frame_rank < prev:
                        resolved_best_rank[F] = frame_rank

        if resolved_best_rank:
            traced_resolved_n += 1

        gold_in_frames = any(g in resolved_best_rank for g in gold)
        if traced and gold_in_frames:
            gold_in_frames_traced_n += 1

        if fail5:
            fail5_total += 1
            if gold_in_frames:
                fail5_gold_in_frames += 1
        if fail10:
            fail10_total += 1
            if gold_in_frames:
                fail10_gold_in_frames += 1

        top1 = returned[0] if returned else None
        top1_correct = top1 is not None and top1 in gold_set

        if traced and resolved_best_rank:
            if not top1_correct:
                qualifying = [g for g in gold
                              if g in resolved_best_rank and g in returned]
                if qualifying:
                    g = min(qualifying, key=lambda x: resolved_best_rank[x])
                    g_rank_current = returned.index(g) + 1
                    g_frame_rank = resolved_best_rank[g]
                    top1_frame_rank = (resolved_best_rank.get(top1)
                                        if top1 is not None else None)
                    upside.append({
                        "instance_id": iid,
                        "gold_file": g,
                        "gold_current_rank": g_rank_current,
                        "gold_frame_rank": g_frame_rank,
                        "top1_file": top1,
                        "top1_frame_rank": top1_frame_rank,
                    })
            else:
                candidates = []
                top1_frame_rank = resolved_best_rank.get(top1)
                for f, fr in resolved_best_rank.items():
                    if f in gold_set:
                        continue
                    if fr <= 3 and (top1_frame_rank is None or top1_frame_rank > fr):
                        candidates.append((f, fr))
                if candidates:
                    f, fr = min(candidates, key=lambda x: x[1])
                    f_rank_current = returned.index(f) + 1 if f in returned else None
                    downside.append({
                        "instance_id": iid,
                        "distractor_file": f,
                        "distractor_frame_rank": fr,
                        "distractor_current_rank": f_rank_current,
                        "top1_file": top1,
                        "top1_frame_rank": top1_frame_rank,
                    })

        if k % 25 == 0 or k == total:
            print(f"[{k}/{total}] traced={traced_n} traced_resolved={traced_resolved_n} "
                  f"upside={len(upside)} downside={len(downside)}", flush=True)

    wall = time.perf_counter() - t0

    print("\n" + "=" * 72)
    print("COUNTS")
    print("=" * 72)
    print(f"total instances (with results):      {total}")
    print(f"traced (>=1 traceback frame in text): {traced_n}")
    print(f"traced with >=1 resolved frame:       {traced_resolved_n}")
    print(f"gold_in_frames among traced:           {gold_in_frames_traced_n} "
          f"({gold_in_frames_traced_n / traced_n:.1%} of traced)"
          if traced_n else "gold_in_frames among traced: n/a")
    print("  (CrashLocator reports 59-67% gold-in-frames on their crash-report corpus)")

    print("\n" + "=" * 72)
    print("UPSIDE (top-1 currently wrong, gold file present in both returned "
          "list and resolved frames)")
    print("=" * 72)
    print(f"count: {len(upside)}")
    dist = {}
    for u in upside:
        key = (u["gold_current_rank"], u["gold_frame_rank"])
        dist[key] = dist.get(key, 0) + 1
    print("distribution of (gold_current_rank, gold_frame_rank) -> count:")
    for key in sorted(dist, key=lambda k: (-dist[k], k)):
        print(f"  {key}: {dist[key]}")

    clearly_flip = 0
    for u in upside:
        top1_fr = u["top1_frame_rank"]
        top1_fr_cmp = top1_fr if top1_fr is not None else float("inf")
        if u["gold_frame_rank"] < top1_fr_cmp:
            clearly_flip += 1
    print(f"\nupside instances where gold_frame_rank < current top-1's frame_rank "
          f"(top-1 absent-from-frames treated as +inf, i.e. no boost): {clearly_flip}")

    print(f"\nup to 20 UPSIDE cases:")
    for u in upside[:20]:
        print(f"  {u['instance_id']:44} gold={u['gold_file']!r} "
              f"cur_rank={u['gold_current_rank']:>3} frame_rank={u['gold_frame_rank']:>3} "
              f"| top1={u['top1_file']!r} top1_frame_rank={u['top1_frame_rank']}")

    print("\n" + "=" * 72)
    print("DOWNSIDE (top-1 currently correct, a non-gold file resolves to a "
          "shallow frame that could displace it)")
    print("=" * 72)
    print(f"count: {len(downside)}")
    print(f"\nup to 20 DOWNSIDE cases:")
    for d in downside[:20]:
        print(f"  {d['instance_id']:44} distractor={d['distractor_file']!r} "
              f"frame_rank={d['distractor_frame_rank']:>3} "
              f"cur_rank={d['distractor_current_rank']} "
              f"| top1={d['top1_file']!r} top1_frame_rank={d['top1_frame_rank']}")

    net_upside = sum(1 for u in upside
                      if u["gold_frame_rank"] <= 2 and u["gold_current_rank"] <= 10)
    print("\n" + "=" * 72)
    print("NET NAIVE ESTIMATE")
    print("=" * 72)
    print(f"upside (gold_frame_rank<=2 and gold_current_rank<=10): {net_upside}")
    print(f"downside (all):                                        {len(downside)}")
    print(f"net naive @1 movement bound:                           "
          f"{net_upside - len(downside)}")

    print("\n" + "=" * 72)
    print("SECONDARY HEADROOM (@5 / @10 failures, subset-of-topk convention)")
    print("=" * 72)
    print(f"fail@5:  {fail5_total} total, {fail5_gold_in_frames} have gold_in_frames "
          f"({fail5_gold_in_frames / fail5_total:.1%})" if fail5_total else "fail@5: 0")
    print(f"fail@10: {fail10_total} total, {fail10_gold_in_frames} have gold_in_frames "
          f"({fail10_gold_in_frames / fail10_total:.1%})" if fail10_total else "fail@10: 0")

    print(f"\nwall time: {wall:.1f}s")


if __name__ == "__main__":
    main()
