"""WS3d adoption proofs (default flip, PR #68): retrieval-payload md5,
two runs per configuration, cold `.roust` per instance.

Proof A -- NEW defaults == OLD(82c8d2f) + `--displacement-guard`, on the
  17 changed jsts instances the round itemized (3 metric-changed +
  14 pack-only-changed; all mui, the entire changed population).
Proof B -- NEW defaults == OLD defaults on 12 Lite Python instances (one
  per repo, pytest deliberately included -- its instances are the entire
  Python fixture-dir exposure and the 31-instance micro-gate proved them
  byte-identical under the guard, so defaults must match exactly; there
  is NO known differ class this round, any mismatch is a failure).
Proof C -- NEW + `--no-displacement-guard` == OLD defaults on the
  proof-A pool (the escape hatch reproduces the pre-adoption engine
  byte-identically exactly where the mechanism fires).

Usage:
  uv run --no-project --with pandas --with pyarrow python \
    lab/ws3d_adoption_gate.py --old-bin <82c8d2f roust> --new-bin <adoption roust>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd

WT = Path(os.environ.get("ROUST_LAB_ROOT",
                         "/Users/nicholasarehart/programming-projects/bgrep"))

ap = argparse.ArgumentParser()
ap.add_argument("--old-bin", type=Path, required=True)
ap.add_argument("--new-bin", type=Path, required=True)
args = ap.parse_args()

for b in (args.old_bin, args.new_bin):
    v = subprocess.run([str(b), "--version"], capture_output=True, text=True).stdout.strip()
    print(f"binary: {b} -> {v}", flush=True)

# The round's full changed population (3 metric + 14 pack-only; itemize_jsts.txt
# + the pack-only list in ws3d-displacement-guard.md).
JSTS_CHANGED = [
    "mui__material-ui-31172", "mui__material-ui-34337", "mui__material-ui-35178",
    "mui__material-ui-30788", "mui__material-ui-32182", "mui__material-ui-32713",
    "mui__material-ui-32987", "mui__material-ui-33801", "mui__material-ui-33820",
    "mui__material-ui-33880", "mui__material-ui-34247", "mui__material-ui-34548",
    "mui__material-ui-35364", "mui__material-ui-36056", "mui__material-ui-36403",
    "mui__material-ui-36853", "mui__material-ui-38247",
]
LITE_REPOS = ["astropy__astropy", "django__django", "matplotlib__matplotlib",
              "mwaskom__seaborn", "pallets__flask", "psf__requests",
              "pydata__xarray", "pylint-dev__pylint", "pytest-dev__pytest",
              "scikit-learn__scikit-learn", "sphinx-doc__sphinx", "sympy__sympy"]


def checkout(clones, slug, sha):
    rp = Path(clones) / slug
    subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True, capture_output=True)
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    return rp


def run(binary, query, repo, extra=()):
    argv = [str(binary), "--json", "--budget", "8192", query, str(repo), *extra]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
    if p.returncode != 0:
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}"
    obj = json.loads(p.stdout)
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def two(binary, query, repo, extra=()):
    h1 = run(binary, query, repo, extra)
    shutil.rmtree(Path(repo) / ".roust", ignore_errors=True)
    h2 = run(binary, query, repo, extra)
    return h1 if h1 == h2 else f"__NONDET__ {h1} != {h2}"


jsts = pd.read_parquet(WT / "lab/mswe_jsts.parquet")
jsts = jsts[jsts["instance_id"].isin(JSTS_CHANGED)].copy()
jsts["slug"] = jsts["repo"].str.replace("/", "__")

fail_a = fail_c = 0
print(f"=== Proof A + C: {len(jsts)} changed jsts instances ===", flush=True)
for _, row in jsts.iterrows():
    rp = checkout(WT / "lab/mswe_repos_private", row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h_old_flag = two(args.old_bin, q, rp, ("--displacement-guard",))
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    h_new_def = two(args.new_bin, q, rp)
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    h_old_def = two(args.old_bin, q, rp)
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    h_new_off = two(args.new_bin, q, rp, ("--no-displacement-guard",))
    a_ok = h_new_def == h_old_flag and not h_new_def.startswith("__")
    c_ok = h_new_off == h_old_def and not h_new_off.startswith("__")
    fail_a += 0 if a_ok else 1
    fail_c += 0 if c_ok else 1
    print(f"  {row['instance_id']:35} A={'OK' if a_ok else 'FAIL'} "
          f"C={'OK' if c_ok else 'FAIL'}", flush=True)
print(f"Proof A failures: {fail_a} / {len(jsts)}", flush=True)
print(f"Proof C failures: {fail_c} / {len(jsts)}", flush=True)

lite = pd.read_parquet(WT / "lab/swebench_lite.parquet")
lite = lite.sort_values(["repo", "instance_id"]).reset_index(drop=True)
lite["slug"] = lite["repo"].str.replace("/", "__")
lb = lite[lite["slug"].isin(LITE_REPOS)].groupby("slug").head(1)
fail_b = 0
print(f"=== Proof B: {len(lb)} Lite instances (one per repo) ===", flush=True)
for _, row in lb.iterrows():
    rp = checkout(WT / "lab/ws3a_repos/repos_lite_base", row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h_old = two(args.old_bin, q, rp)
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    h_new = two(args.new_bin, q, rp)
    ok = h_old == h_new and not h_old.startswith("__")
    fail_b += 0 if ok else 1
    print(f"  {row['instance_id']:35} B={'OK' if ok else 'FAIL'}", flush=True)
print(f"Proof B failures: {fail_b} / {len(lb)}", flush=True)
print("ADOPTION_GATE_DONE", flush=True)
