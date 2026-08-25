"""WS3b adoption proofs (default flip, PR #66): retrieval-payload md5,
two runs per configuration, cold `.roust` per instance.

Proof A -- NEW(ac0b63f) defaults == OLD(0c0fc79) + `--trace-formats-v2`,
  on EVERY trace-firing java (14) + rust (5) instance from the arms.
Proof B -- NEW defaults == OLD defaults on 12 Lite Python instances (one
  per repo; Python is untouched in either flag state).
Proof C -- NEW + `--no-trace-formats-v2` == OLD defaults on the same 19
  trace-firing instances (the escape hatch reproduces the pre-adoption
  engine byte-identically exactly where the mechanism fires).

Usage:
  uv run --no-project --with pandas --with pyarrow python \
    lab/ws3b_adoption_gate.py --old-bin <0c0fc79 roust> --new-bin <ac0b63f roust>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd

WT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--old-bin", type=Path, required=True)
ap.add_argument("--new-bin", type=Path, required=True)
args = ap.parse_args()

for b in (args.old_bin, args.new_bin):
    v = subprocess.run([str(b), "--version"], capture_output=True, text=True).stdout.strip()
    print(f"binary: {b} -> {v}", flush=True)


def fired_ids(report):
    out = []
    for line in open(report):
        r = json.loads(line)
        if (r.get("trace_boost") or {}).get("trace_files"):
            out.append(r["instance_id"])
    return set(out)


def rows_for(parquet, ids, clones):
    df = pd.read_parquet(parquet)
    df = df[df["instance_id"].isin(ids)].copy()
    df["slug"] = df["repo"].str.replace("/", "__")
    df["clones"] = str(clones)
    return df


def checkout(clones, slug, sha):
    rp = Path(clones) / slug
    subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True, capture_output=True)
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    return rp


def h(binary, query, repo, extra=()):
    argv = [str(binary), "--json", "--budget", "8192", query, str(repo), *extra]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
    if p.returncode != 0:
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}"
    obj = json.loads(p.stdout)
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


R = WT / "lab/results_regions/ws3b"
java = rows_for(WT / "lab/ws3b_java.parquet",
                fired_ids(R / "mswe_java_ws3b_v2.jsonl"), WT / "lab/ws3b_repos/java_v2")
rust = rows_for(WT / "lab/ws3a_rust.parquet",
                fired_ids(R / "mswe_rust_ws3b_v2.jsonl"), WT / "lab/ws3a_repos/rust_v2")
traced = pd.concat([java, rust], ignore_index=True).sort_values("instance_id")

lite = pd.read_parquet(WT / "lab/swebench_lite.parquet")
lite = lite.sort_values(["repo", "instance_id"])
lite["slug"] = lite["repo"].str.replace("/", "__")
lite = lite.groupby("slug").head(1).copy()  # one per repo = 12
lite["clones"] = str(WT / "lab/ws3a_repos/repos_gate")

fails = 0

print(f"=== Proof A: NEW defaults == OLD --trace-formats-v2 "
      f"({len(traced)} trace-firing java/rust instances, two runs each) ===", flush=True)
for _, row in traced.iterrows():
    rp = checkout(row["clones"], row["slug"], row["base_commit"])
    q = row["problem_statement"]
    hs = [h(args.new_bin, q, rp), h(args.new_bin, q, rp),
          h(args.old_bin, q, rp, ("--trace-formats-v2",)),
          h(args.old_bin, q, rp, ("--trace-formats-v2",))]
    ok = len(set(hs)) == 1 and not hs[0].startswith("__ERROR__")
    fails += 0 if ok else 1
    print(f"  {row['instance_id']:40} {'OK' if ok else 'MISMATCH ' + str(hs)}", flush=True)

print(f"=== Proof B: NEW defaults == OLD defaults ({len(lite)} Lite Python, "
      f"two runs each) ===", flush=True)
for _, row in lite.iterrows():
    rp = checkout(row["clones"], row["slug"], row["base_commit"])
    q = row["problem_statement"]
    hs = [h(args.new_bin, q, rp), h(args.new_bin, q, rp),
          h(args.old_bin, q, rp), h(args.old_bin, q, rp)]
    ok = len(set(hs)) == 1 and not hs[0].startswith("__ERROR__")
    fails += 0 if ok else 1
    print(f"  {row['instance_id']:40} {'OK' if ok else 'MISMATCH ' + str(hs)}", flush=True)

print(f"=== Proof C: NEW --no-trace-formats-v2 == OLD defaults "
      f"({len(traced)} trace-firing instances, two runs each) ===", flush=True)
for _, row in traced.iterrows():
    rp = checkout(row["clones"], row["slug"], row["base_commit"])
    q = row["problem_statement"]
    hs = [h(args.new_bin, q, rp, ("--no-trace-formats-v2",)),
          h(args.new_bin, q, rp, ("--no-trace-formats-v2",)),
          h(args.old_bin, q, rp), h(args.old_bin, q, rp)]
    ok = len(set(hs)) == 1 and not hs[0].startswith("__ERROR__")
    fails += 0 if ok else 1
    print(f"  {row['instance_id']:40} {'OK' if ok else 'MISMATCH ' + str(hs)}", flush=True)

print(f"\nADOPTION GATE failures: {fails}", flush=True)
print("ADOPTION_GATE_DONE", flush=True)
