"""WS2b pre-arm identity gates (campaign #56 workstream 2b; private clones only).

Modeled on lab/ws2_identity_gate.py (same retrieval-payload md5, same
two-runs-per-binary determinism check). WS2b changes NO engine code -- the
branch is harness-only -- so Gate A proves the rebuilt branch binary is
byte-identical to the pinned main-tip binary on defaults before any arm runs.

Gate A -- defaults identity, MAIN(3069573) vs BRANCH binary, two runs each:
  12 SWE-bench Lite Python instances (6 repos x 2), pool deliberately biased
  toward the four repos step 0 found C-family files in (astropy, matplotlib,
  scikit-learn, sphinx) plus django/sympy as pure-Python controls.

Gate B -- BRANCH binary, defaults vs --cfamily-ext, same 12 instances:
  on django/sympy the flag must be inert (step 0: zero C-family files); on
  the other four repos differences are EXPECTED (vendored/native C enters
  the index) and each diff is attributed by listing the bundle's C-family
  files. Gate B is diagnostic here, not pass/fail: the pass/fail dilution
  question is the full Lite-300/Verified-407 arms.
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
GATE_REPOS = ["astropy__astropy", "matplotlib__matplotlib",
              "scikit-learn__scikit-learn", "sphinx-doc__sphinx",
              "django__django", "sympy__sympy"]
CFAM = (".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh")

ap = argparse.ArgumentParser()
ap.add_argument("--base-bin", type=Path, required=True)
ap.add_argument("--new-bin", type=Path, required=True)
ap.add_argument("--clones", type=Path, required=True)
args = ap.parse_args()

lite = pd.read_parquet(WT / "lab/swebench_lite.parquet")
lite = lite.sort_values(["repo", "instance_id"]).reset_index(drop=True)
lite["slug"] = lite["repo"].str.replace("/", "__")
pool = lite[lite["slug"].isin(GATE_REPOS)].groupby("slug").head(2)  # 12

for b in (args.base_bin, args.new_bin):
    v = subprocess.run([str(b), "--version"], capture_output=True, text=True).stdout.strip()
    print(f"binary: {b} -> {v}", flush=True)
print(f"gate pool: {len(pool)} Lite Python instances across {pool['slug'].nunique()} repos", flush=True)


def checkout(slug: str, sha: str) -> Path:
    rp = args.clones / slug
    subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True, capture_output=True)
    shutil.rmtree(rp / ".roust", ignore_errors=True)  # deterministic cold start
    return rp


def run(binary: Path, query: str, repo: Path, extra=()) -> str:
    argv = [str(binary), "--json", "--budget", "8192", query, str(repo), *extra]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}"
    obj = json.loads(p.stdout)
    # Retrieval payload only (e23 lesson: stats.cache flips cold/warm).
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


fail_a = 0
print("=== Gate A: defaults identity, MAIN vs BRANCH binary, two runs each ===", flush=True)
for _, row in pool.iterrows():
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h = [run(args.base_bin, q, rp), run(args.base_bin, q, rp),
         run(args.new_bin, q, rp), run(args.new_bin, q, rp)]
    ok = len(set(h)) == 1 and not h[0].startswith("__ERROR__")
    if not ok:
        fail_a += 1
    print(f"  {row['instance_id']:45} {'OK' if ok else 'MISMATCH ' + str(h)}", flush=True)

print("=== Gate B (diagnostic): BRANCH binary, defaults vs --cfamily-ext ===", flush=True)
b_diff = []
for _, row in pool.iterrows():
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h_off = run(args.new_bin, q, rp)
    h_on = run(args.new_bin, q, rp, extra=("--cfamily-ext",))
    same = h_off == h_on and not h_off.startswith("__ERROR__")
    if not same:
        p = subprocess.run([str(args.new_bin), "--json", "--budget", "8192", q, str(rp),
                            "--cfamily-ext"], capture_output=True, text=True)
        files = list(json.loads(p.stdout).get("regions", {}).keys())
        cfam = [f for f in files if f.endswith(CFAM)]
        b_diff.append((row["instance_id"], cfam))
    print(f"  {row['instance_id']:45} {'IDENTICAL' if same else 'DIFFERS'}", flush=True)

print(f"\nGate A failures: {fail_a}")
print(f"Gate B diffs: {len(b_diff)}")
for iid, cfam in b_diff:
    print(f"  {iid}: C-family files in bundle: {cfam}")
sys.exit(1 if fail_a else 0)
