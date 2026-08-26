"""WS2c Gate 2: defaults byte-identity vs main on non-matching-dir repos.

The VENDOR_RE extension can only change payloads on repos with cextern/,
extern/, libsvm/ or liblinear/ dirs (census: astropy only carries
default-suffix files under those). Gate A proves defaults byte-identity,
MAIN(3069573) binary vs WS2c branch binary, two runs each, on 9 Lite
instances across django/sympy/sphinx (3 x 3, >= 8 per spec).

Gate B (diagnostic, not pass/fail): same defaults A/B on 2 astropy +
1 matplotlib + 1 scikit-learn instances. Census predicts astropy DIFFERS
(26 vendored default-suffix files under astropy/extern/ leave the index)
while matplotlib/sklearn stay IDENTICAL (their matching dirs hold only
C-family files, which defaults never indexed).

Same retrieval-payload md5 + cold-start convention as ws2b_identity_gate.py.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

WT = Path(__file__).resolve().parent.parent
A_REPOS = ["django__django", "sympy__sympy", "sphinx-doc__sphinx"]
B_REPOS = {"astropy__astropy": 2, "matplotlib__matplotlib": 1, "scikit-learn__scikit-learn": 1}

ap = argparse.ArgumentParser()
ap.add_argument("--base-bin", type=Path, required=True)
ap.add_argument("--new-bin", type=Path, required=True)
ap.add_argument("--clones", type=Path, required=True)
args = ap.parse_args()

lite = pd.read_parquet(WT / "lab/swebench_lite.parquet")
lite = lite.sort_values(["repo", "instance_id"]).reset_index(drop=True)
lite["slug"] = lite["repo"].str.replace("/", "__")
pool_a = lite[lite["slug"].isin(A_REPOS)].groupby("slug").head(3)  # 9
pool_b = pd.concat([lite[lite["slug"] == s].head(n) for s, n in B_REPOS.items()])

for b in (args.base_bin, args.new_bin):
    v = subprocess.run([str(b), "--version"], capture_output=True, text=True).stdout.strip()
    print(f"binary: {b} -> {v}", flush=True)


def checkout(slug: str, sha: str) -> Path:
    rp = args.clones / slug
    subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True, capture_output=True)
    shutil.rmtree(rp / ".roust", ignore_errors=True)  # deterministic cold start
    return rp


def run(binary: Path, query: str, repo: Path) -> str:
    argv = [str(binary), "--json", "--budget", "8192", query, str(repo)]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}"
    obj = json.loads(p.stdout)
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


fail_a = 0
print(f"=== Gate A: defaults identity, MAIN vs WS2c binary, two runs each ({len(pool_a)} instances) ===", flush=True)
for _, row in pool_a.iterrows():
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h = [run(args.base_bin, q, rp), run(args.base_bin, q, rp),
         run(args.new_bin, q, rp), run(args.new_bin, q, rp)]
    ok = len(set(h)) == 1 and not h[0].startswith("__ERROR__")
    if not ok:
        fail_a += 1
    print(f"  {row['instance_id']:45} {'OK' if ok else 'MISMATCH ' + str(h)}", flush=True)

print("=== Gate B (diagnostic): defaults, MAIN vs WS2c on matching-dir repos ===", flush=True)
for _, row in pool_b.iterrows():
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h_main = run(args.base_bin, q, rp)
    h_new = run(args.new_bin, q, rp)
    same = h_main == h_new and not h_main.startswith("__ERROR__")
    print(f"  {row['instance_id']:45} {'IDENTICAL' if same else 'DIFFERS'}", flush=True)

print(f"\nGate A failures: {fail_a}")
sys.exit(1 if fail_a else 0)
