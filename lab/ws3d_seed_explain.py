"""WS3d step-0 seed characterization (issue #56).

For each seed instance, run the CURRENT-DEFAULT pinned binary under four
configs (defaults / --no-trace-formats-v2 / --no-symbols-v2 / both off)
with --explain, and print per config: anchor_promotions, trace_boost
frame files (gold-flagged), packed files with gold rank, gold-file span
coverage of the pack, and which fired files are testlike/fixture-shaped
or absent from the escape-hatch ranking (zero ranked lexical presence).

Usage:
  uv run --no-project --with pandas --with pyarrow python lab/ws3d_seed_explain.py \
      --bin BIN --repos-dir DIR --out OUT.json \
      PARQUET:INSTANCE_ID [PARQUET:INSTANCE_ID ...]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

CONFIGS = {
    "default": [],
    "guard": ["--displacement-guard"],
    "no_trace_v2": ["--no-trace-formats-v2"],
    "no_symbols_v2": ["--no-symbols-v2"],
    "both_off": ["--no-trace-formats-v2", "--no-symbols-v2"],
}

TESTLIKE_DIR_RE = re.compile(
    r"(^|/)(tests?|testing|__tests__|test_data|testdata|fixtures?|specs?)(/|$)|"
    r"(^|/)[^/]+\.(test|spec)s?(/|$)|\.(test|spec)\.[^/]+$|(^|/)test_[^/]+$|_test\.[^/]+$",
    re.I,
)


def gold_files_lines(patch: str):
    files, lines = [], {}
    cur = None
    new_ln = 0
    for line in (patch or "").splitlines():
        m = re.match(r"^diff --git a/(\S+) b/(\S+)", line)
        if m:
            cur = m.group(2)
            files.append(cur)
            lines.setdefault(cur, set())
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if m:
            new_ln = int(m.group(1))
            continue
        if cur is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines[cur].add(new_ln)
            new_ln += 1
        elif line.startswith("-") and not line.startswith("---"):
            lines[cur].add(new_ln)  # deletion context: neighbor new-side line
        elif not line.startswith(("---", "+++", "diff ", "index ", "@@")):
            new_ln += 1
    return files, {k: sorted(v) for k, v in lines.items()}


def run_one(binary, repo_path, query, extra):
    shutil.rmtree(Path(repo_path) / ".roust", ignore_errors=True)
    p = subprocess.run(
        [str(binary), "--json", "--budget", "8192", "--explain", query, str(repo_path), *extra],
        capture_output=True, text=True, timeout=1800,
    )
    payload = {}
    for ln in p.stdout.splitlines():
        ln = ln.strip()
        if ln.startswith("{"):
            payload = json.loads(ln)
            break
    err = p.stderr
    a, b = err.find("{"), err.rfind("}")
    explain = json.loads(err[a:b + 1]) if a >= 0 else {}
    return payload, explain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--repos-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("seeds", nargs="+", help="PARQUET:INSTANCE_ID")
    args = ap.parse_args()

    import pandas as pd

    cache = {}
    results = {}
    for spec in args.seeds:
        pq, iid = spec.split(":", 1)
        if pq not in cache:
            cache[pq] = pd.read_parquet(pq)
        df = cache[pq]
        row = df[df["instance_id"] == iid]
        if row.empty:
            print(f"!! {iid} not in {pq}")
            continue
        r = row.iloc[0]
        slug = r["repo"].replace("/", "__")
        sha, query, patch = r["base_commit"], r["problem_statement"], r["patch"]
        gold, gold_lines = gold_files_lines(patch)
        rp = Path(args.repos_dir) / slug
        subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True, capture_output=True)
        subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True, capture_output=True)

        inst = {"gold": gold, "configs": {}}
        print(f"\n==== {iid}  gold={gold}")
        for name, extra in CONFIGS.items():
            payload, explain = run_one(args.bin, rp, query, extra)
            packed = [f["path"] for f in payload.get("files", [])]
            regions = payload.get("regions", {})
            stats = payload.get("stats", {})
            tf = (stats.get("trace_boost") or {}).get("trace_files", [])
            anch = explain.get("anchor_promotions", [])
            grank = next((i + 1 for i, f in enumerate(packed) if f in gold), None)
            cov = {}
            for g in gold:
                gl = set(gold_lines.get(g, []))
                got = set()
                for a, b in regions.get(g, []):
                    got |= {x for x in gl if a <= x <= b}
                cov[g] = (len(got), len(gl))
            inst["configs"][name] = {
                "packed": packed, "regions": regions, "gold_rank": grank,
                "trace_files": tf, "anchors": anch, "gold_line_cov": cov,
                "lex_picks": explain.get("lex_picks", []),
            }
            tf_s = [f"{f}{'*G' if f in gold else ''}" for f in tf]
            an_s = [f"{f}({s},{act},{kind}){'*G' if f in gold else ''}{'*T' if TESTLIKE_DIR_RE.search(f) else ''}"
                    for f, s, act, kind in anch]
            print(f"  [{name}] gold_rank={grank} n_packed={len(packed)} "
                  f"cov={ {g: f'{a}/{b}' for g, (a, b) in cov.items()} }")
            if tf_s:
                print(f"    trace_files: {tf_s}")
            if an_s:
                print(f"    anchors:     {an_s}")
        # cross-config: fired files absent from both_off ranking
        base_ranked = set(inst["configs"]["both_off"]["packed"])
        for name in ("default",):
            c = inst["configs"][name]
            fired = [f for f in c["trace_files"]] + [a[0] for a in c["anchors"]]
            absent = [f for f in fired if f not in base_ranked and f not in gold]
            if absent:
                print(f"    non-gold fired files ABSENT from both_off pack: {absent}")
        results[iid] = inst
    with open(args.out, "w") as fh:
        json.dump(results, fh, indent=1)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
