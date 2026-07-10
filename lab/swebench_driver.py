"""SWE-bench Lite file-level localization with the bgrep pipeline.

For each instance: checkout repo@base_commit, run the frozen pipeline with the
RAW problem statement as the query (anchor preservation; no helper keywords),
and score file-level recall of the gold-patch-edited files plus packed tokens.

Writes one JSON line per instance (resume-safe: already-done instances skipped).

Usage:  uv run python swebench_driver.py [--limit N] [--out results.jsonl]
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB_DIR))

import lanes as L  # noqa: E402
from archex.reporting import count_tokens  # noqa: E402

PARQUET_URL = (
    "https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite/"
    "resolve/main/data/test-00000-of-00001.parquet"
)
REPO_CACHE = LAB_DIR / "swebench_repos"
_DIFF_FILE_RE = re.compile(r"^diff --git a/(\S+) b/", re.M)


def load_instances() -> list[dict]:
    import pandas as pd  # provided by archex venv

    cache = LAB_DIR / "swebench_lite.parquet"
    if not cache.exists():
        print("downloading SWE-bench Lite parquet...", flush=True)
        urllib.request.urlretrieve(PARQUET_URL, cache)
    df = pd.read_parquet(cache)
    out = []
    for _, row in df.iterrows():
        gold = sorted(set(_DIFF_FILE_RE.findall(row["patch"])))
        out.append({
            "instance_id": row["instance_id"],
            "repo": row["repo"],
            "base_commit": row["base_commit"],
            "problem_statement": row["problem_statement"],
            "gold_files": gold,
        })
    # group by repo so the shared clone checks out sequentially
    out.sort(key=lambda r: (r["repo"], r["instance_id"]))
    return out


def repo_clone(slug: str) -> Path:
    dest = REPO_CACHE / slug.replace("/", "__")
    if (dest / ".git").exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"cloning {slug} (full history)...", flush=True)
    r = subprocess.run(
        ["git", "clone", "--quiet", f"https://github.com/{slug}.git", str(dest)],
        capture_output=True, text=True, timeout=3600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"clone {slug} failed: {r.stderr.strip()[:300]}")
    return dest


def checkout(repo: Path, sha: str) -> None:
    r = subprocess.run(["git", "checkout", "-f", "-q", sha], cwd=repo,
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"checkout {sha} failed: {r.stderr.strip()[:300]}")
    subprocess.run(["git", "clean", "-fdq"], cwd=repo, capture_output=True,
                   text=True, timeout=300)


def run_instance(inst: dict, repo_path: Path) -> dict:
    t0 = time.perf_counter()
    corpus = L.Corpus(repo_path)
    build_ms = (time.perf_counter() - t0) * 1000
    terms = L.query_terms(inst["problem_statement"], [])
    t1 = time.perf_counter()
    files, scores = L.select_files(corpus, terms, use_ppr=True)
    spans, bundle = L.pack_regions(corpus, files, terms, scores, 8192, count_tokens)
    query_ms = (time.perf_counter() - t1) * 1000
    packed_files = [f for f in files if f in spans]
    gold = [g for g in inst["gold_files"] if g.endswith(tuple(L.CODE_EXTENSIONS))]
    fset = set(packed_files)
    present = [g for g in gold if g in fset]
    recall = len(present) / len(gold) if gold else 1.0
    return {
        "instance_id": inst["instance_id"],
        "repo": inst["repo"],
        "gold_files": gold,
        "n_gold": len(gold),
        "present": present,
        "missing": [g for g in gold if g not in fset],
        "recall": recall,
        "all_present": len(present) == len(gold),
        "n_returned": len(packed_files),
        "returned_files": packed_files,  # ordered: lexical picks then additions
        "tokens_packed": count_tokens(bundle),
        "corpus_files": corpus.n_docs,
        "build_ms": round(build_ms),
        "query_ms": round(query_ms),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(LAB_DIR / "results_swebench" / "lite.jsonl"))
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            try:
                done.add(json.loads(line)["instance_id"])
            except (json.JSONDecodeError, KeyError):
                pass

    instances = load_instances()
    if args.limit:
        instances = instances[: args.limit]
    todo = [i for i in instances if i["instance_id"] not in done]
    print(f"{len(instances)} instances, {len(done)} done, {len(todo)} to run", flush=True)

    with out_path.open("a") as fh:
        for k, inst in enumerate(todo, 1):
            try:
                repo = repo_clone(inst["repo"])
                checkout(repo, inst["base_commit"])
                res = run_instance(inst, repo)
            except Exception as exc:
                res = {"instance_id": inst["instance_id"], "repo": inst["repo"],
                       "error": str(exc)[:300]}
            fh.write(json.dumps(res) + "\n")
            fh.flush()
            r = res.get("recall")
            print(f"[{k}/{len(todo)}] {inst['instance_id']:44} "
                  f"recall={r if r is not None else 'ERR'} "
                  f"tok={res.get('tokens_packed', '-')}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
