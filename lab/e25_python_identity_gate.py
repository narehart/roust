"""E25 Python identity gate (issue #56 follow-on, campaign #4 wave 6).

Claim under test: `--shape-blocks` cannot change any Python-bench result.

The STRUCTURAL half of that claim is settled by reading the dispatch in
roust-rs/src/core.rs (~line 4998):

    let spans = if rel.ends_with(".py") {
        python_blocks(text)
    } else if let Some(shape) = shape_blocks(text, rel).filter(|_| blocks == BlockMode::Shape) {
        shape
    } else if ...

`.py` is tested FIRST, so a Python file never reaches the shape branch
regardless of the flag. But that is NOT the whole story, and this gate
exists because of the gap: a Python-BENCH repo is not a Python-ONLY repo.
sphinx ships .js, scikit-learn and numpy ship .c/.cpp, and those files ARE
indexed (c-family indexing became a default in WS2c) and DO reach the shape
branch. So the flag has a real surface on Python benches via non-.py files,
and identity must be measured, not assumed.

Method: byte-compare the retrieval payload (md5 of query/files/regions/
bundle) with the flag OFF vs ON, two runs each for determinism, cold
.roust cache, pinned binary, private clone dir. Deterministic stride
sample across the sorted split so the selection is reproducible and
spans repos rather than clustering.

Usage:
  uv run --no-project --with pandas --with pyarrow python \
      lab/e25_python_identity_gate.py --bin BIN \
      --lite-clones DIR --ver-clones DIR --n-lite 40 --n-ver 20
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd

LAB = Path("/Users/nicholasarehart/programming-projects/bgrep/lab")

# Extensions that reach a linked tree-sitter grammar, i.e. the files on which
# --shape-blocks can actually change the packing units. Mirrors is_ts_family +
# sitter_family in roust-rs/src/core.rs.
GRAMMAR_EXT = (".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
               ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh")


def payload_hash(binary, query, repo, extra=()):
    argv = [str(binary), "--json", "--budget", "8192", query, str(repo), *extra]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
    if p.returncode != 0:
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}"
    obj = json.loads(p.stdout)
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def stride_sample(df, n):
    """Deterministic evenly-spaced sample of n rows across the sorted split."""
    df = df.sort_values("instance_id").reset_index(drop=True)
    if n >= len(df):
        return df
    idx = [round(i * (len(df) - 1) / (n - 1)) for i in range(n)]
    return df.iloc[sorted(set(idx))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--lite-clones", required=True)
    ap.add_argument("--ver-clones", required=True)
    ap.add_argument("--n-lite", type=int, default=40)
    ap.add_argument("--n-ver", type=int, default=20)
    args = ap.parse_args()

    plan = []
    for bench, pq, clones, n in (
            ("lite", LAB / "swebench_lite.parquet", args.lite_clones, args.n_lite),
            ("verified", LAB / "swebench_verified_heldout.parquet", args.ver_clones, args.n_ver)):
        df = stride_sample(pd.read_parquet(pq), n)
        for _, r in df.iterrows():
            plan.append((bench, clones, r["instance_id"], r["repo"],
                         r["base_commit"], r["problem_statement"]))

    print(f"sampled {sum(1 for p in plan if p[0]=='lite')} lite + "
          f"{sum(1 for p in plan if p[0]=='verified')} verified instances")

    n_fail = n_differ = n_exposed = 0
    rows = []
    for bench, clones, iid, repo, sha, q in plan:
        rp = Path(clones) / repo.replace("/", "__")
        if not rp.is_dir():
            print(f"  [{bench:8}] {iid:38} SKIP (no clone at {rp})", flush=True)
            continue
        subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True, capture_output=True)
        subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True, capture_output=True)

        # Does this tree even contain a file the shape branch could touch?
        ls = subprocess.run(["git", "ls-tree", "-r", "--name-only", sha],
                            cwd=rp, capture_output=True, text=True)
        exposed = sum(1 for f in ls.stdout.splitlines() if f.endswith(GRAMMAR_EXT))
        if exposed:
            n_exposed += 1

        shutil.rmtree(rp / ".roust", ignore_errors=True)
        off1 = payload_hash(args.bin, q, rp)
        off2 = payload_hash(args.bin, q, rp)
        on1 = payload_hash(args.bin, q, rp, ("--shape-blocks",))
        on2 = payload_hash(args.bin, q, rp, ("--shape-blocks",))

        det = off1 == off2 and on1 == on2 and not off1.startswith("__ERROR__")
        same = off1 == on1
        if not det:
            n_fail += 1
        if not same:
            n_differ += 1
        rows.append({"bench": bench, "instance_id": iid, "repo": repo,
                     "grammar_files": exposed, "deterministic": det,
                     "identical": same, "hash_off": off1, "hash_on": on1})
        print(f"  [{bench:8}] {iid:38} grammar_files={exposed:5d} "
              f"det={'OK' if det else 'FAIL'} "
              f"shape={'IDENTICAL' if same else 'DIFFERS'}", flush=True)

    print(f"\nchecked {len(rows)} instances "
          f"({n_exposed} whose tree contains >=1 grammar-covered non-.py file)")
    print(f"determinism failures: {n_fail}; shape-differs: {n_differ}")
    out = LAB / "results_regions" / "e25" / "python_identity_gate.json"
    out.write_text(json.dumps(rows, indent=1))
    print(f"wrote {out}")
    print("E25_PYTHON_GATE_DONE")


if __name__ == "__main__":
    main()
