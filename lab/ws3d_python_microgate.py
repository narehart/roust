"""WS3d Python micro-gate (issue #56): guard inertness on the 31
fixture-dir-bearing Lite/Verified instances.

The WS3d fixture census (lab/ws3d_fixture_census.py) found the ENTIRE
Python-bench exposure of --displacement-guard is 15 Lite + 16 Verified
pytest instances whose trees carry exactly one matching path,
`extra/setup-py.test/setup.py`. This gate byte-compares defaults vs
--displacement-guard (retrieval-payload md5, two runs each, cold .roust,
BRANCH binary, private clone) on every one of them. Expected: all
IDENTICAL (that setup.py never wins a rare-symbol anchor); any DIFFERS
row must be escalated to a full Lite/Verified arm before adoption.

Usage:
  uv run --no-project --with pandas --with pyarrow python \
      lab/ws3d_python_microgate.py --bin BIN --clones DIR
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


def run(binary, query, repo, extra=()):
    argv = [str(binary), "--json", "--budget", "8192", query, str(repo), *extra]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
    if p.returncode != 0:
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}"
    obj = json.loads(p.stdout)
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--clones", required=True)
    args = ap.parse_args()

    ids = []
    for bench, pq in (("lite", LAB / "swebench_lite.parquet"),
                      ("verified", LAB / "swebench_verified_heldout.parquet")):
        df = pd.read_parquet(pq)
        df = df[df["repo"] == "pytest-dev/pytest"]
        for _, r in df.iterrows():
            p = subprocess.run(["git", "ls-tree", "-r", "--name-only", r["base_commit"]],
                               cwd=f"{args.clones}/pytest-dev__pytest",
                               capture_output=True, text=True)
            if any(".test/" in f or ".spec/" in f for f in p.stdout.splitlines()):
                ids.append((bench, r["instance_id"], r["base_commit"], r["problem_statement"]))
    print(f"{len(ids)} fixture-dir-bearing pytest instances (expect 31)")

    rp = Path(args.clones) / "pytest-dev__pytest"
    n_fail = n_differ = 0
    for bench, iid, sha, q in ids:
        subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True, capture_output=True)
        subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True, capture_output=True)
        shutil.rmtree(rp / ".roust", ignore_errors=True)
        h = [run(args.bin, q, rp), run(args.bin, q, rp),
             run(args.bin, q, rp, ("--displacement-guard",)),
             run(args.bin, q, rp, ("--displacement-guard",))]
        det = h[0] == h[1] and h[2] == h[3] and not h[0].startswith("__ERROR__")
        same = h[0] == h[2]
        if not det:
            n_fail += 1
        if not same:
            n_differ += 1
        print(f"  [{bench:8}] {iid:35} det={'OK' if det else 'FAIL'} "
              f"guard={'IDENTICAL' if same else 'DIFFERS'}", flush=True)
    print(f"determinism failures: {n_fail}; guard-differs: {n_differ}")
    print("MICROGATE_DONE")


if __name__ == "__main__":
    main()
