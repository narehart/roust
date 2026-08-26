"""WS3c adoption proofs (default flip, PR #67): retrieval-payload md5,
two runs per configuration, cold `.roust` per instance.

Proof A -- NEW(3984d33) defaults == OLD(10967da) + `--symbols-v2`, on the
  19 metric-changed jsts/java/rust instances the round itemized (every
  FILE/LINE/FUNCTION flip instance plus the named fraction movers).
Proof B -- NEW defaults == OLD defaults on 12 Lite Python instances (one
  per repo). Python metrics are digit-identical under the flag, but
  payloads are NOT guaranteed identical (28/300 Lite instances repack
  non-gold content); a defaults mismatch here is re-checked against
  NEW-defaults == OLD+flag -- if THAT holds, the row is the known
  pack-only differ class (reported, not a failure; matplotlib-18869 is
  the expected member of this pool).
Proof C -- NEW + `--no-symbols-v2` == OLD defaults on the proof-A pool
  (the escape hatch reproduces the pre-adoption engine byte-identically
  exactly where the mechanism fires).

Usage:
  uv run --no-project --with pandas --with pyarrow python \
    lab/ws3c_adoption_gate.py --old-bin <10967da roust> --new-bin <3984d33 roust>
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

# The round's itemized metric-flip instances (see ws3c-symbols.md).
AFFECTED = {
    "jsts": (WT / "lab/mswe_jsts.parquet", WT / "lab/mswe_repos_private", [
        "mui__material-ui-32713", "mui__material-ui-34337", "iamkun__dayjs-1953",
        "sveltejs__svelte-11371", "sveltejs__svelte-15083", "mui__material-ui-32962",
        "mui__material-ui-36024", "mui__material-ui-36659", "sveltejs__svelte-10077",
        "sveltejs__svelte-12938",
    ]),
    "java": (WT / "lab/ws3b_java.parquet", WT / "lab/ws3b_repos/java_v2", [
        "fasterxml__jackson-databind-3509", "mockito__mockito-3129",
        "elastic__logstash-15964", "fasterxml__jackson-databind-4219",
        "fasterxml__jackson-databind-4013",
    ]),
    "rust": (WT / "lab/ws3a_rust.parquet", WT / "lab/ws3a_repos/rust_v2", [
        "clap-rs__clap-5015", "clap-rs__clap-4059", "clap-rs__clap-5227",
        "clap-rs__clap-2161",
    ]),
}


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


affected = pd.concat(
    [rows_for(pq, ids, cl) for pq, cl, ids in AFFECTED.values()], ignore_index=True
).sort_values("instance_id")

lite = pd.read_parquet(WT / "lab/swebench_lite.parquet")
lite = lite.sort_values(["repo", "instance_id"])
lite["slug"] = lite["repo"].str.replace("/", "__")
lite = lite.groupby("slug").head(1).copy()  # one per repo = 12
lite["clones"] = str(WT / "lab/ws3a_repos/repos_gate")

fails = 0

print(f"=== Proof A: NEW defaults == OLD --symbols-v2 "
      f"({len(affected)} metric-changed jsts/java/rust instances, two runs each) ===",
      flush=True)
for _, row in affected.iterrows():
    rp = checkout(row["clones"], row["slug"], row["base_commit"])
    q = row["problem_statement"]
    hs = [h(args.new_bin, q, rp), h(args.new_bin, q, rp),
          h(args.old_bin, q, rp, ("--symbols-v2",)),
          h(args.old_bin, q, rp, ("--symbols-v2",))]
    ok = len(set(hs)) == 1 and not hs[0].startswith("__ERROR__")
    fails += 0 if ok else 1
    print(f"  {row['instance_id']:40} {'OK' if ok else 'MISMATCH ' + str(hs)}", flush=True)

print(f"=== Proof B: NEW defaults == OLD defaults ({len(lite)} Lite Python, "
      f"two runs each; known pack-only differ class re-checked vs OLD+flag) ===",
      flush=True)
for _, row in lite.iterrows():
    rp = checkout(row["clones"], row["slug"], row["base_commit"])
    q = row["problem_statement"]
    hs = [h(args.new_bin, q, rp), h(args.new_bin, q, rp),
          h(args.old_bin, q, rp), h(args.old_bin, q, rp)]
    ok = len(set(hs)) == 1 and not hs[0].startswith("__ERROR__")
    if ok:
        print(f"  {row['instance_id']:40} OK", flush=True)
        continue
    # determinism must hold within each config regardless
    det = hs[0] == hs[1] and hs[2] == hs[3] and not hs[0].startswith("__ERROR__")
    flag_hs = [h(args.old_bin, q, rp, ("--symbols-v2",)),
               h(args.old_bin, q, rp, ("--symbols-v2",))]
    flag_eq = det and flag_hs[0] == flag_hs[1] and hs[0] == flag_hs[0]
    if flag_eq:
        print(f"  {row['instance_id']:40} DIFFERS-AS-KNOWN (pack-only class; "
              f"NEW defaults == OLD --symbols-v2)", flush=True)
    else:
        fails += 1
        print(f"  {row['instance_id']:40} MISMATCH {hs} flag={flag_hs}", flush=True)

print(f"=== Proof C: NEW --no-symbols-v2 == OLD defaults "
      f"({len(affected)} metric-changed instances, two runs each) ===", flush=True)
for _, row in affected.iterrows():
    rp = checkout(row["clones"], row["slug"], row["base_commit"])
    q = row["problem_statement"]
    hs = [h(args.new_bin, q, rp, ("--no-symbols-v2",)),
          h(args.new_bin, q, rp, ("--no-symbols-v2",)),
          h(args.old_bin, q, rp), h(args.old_bin, q, rp)]
    ok = len(set(hs)) == 1 and not hs[0].startswith("__ERROR__")
    fails += 0 if ok else 1
    print(f"  {row['instance_id']:40} {'OK' if ok else 'MISMATCH ' + str(hs)}", flush=True)

print(f"\nADOPTION GATE failures: {fails}", flush=True)
print("ADOPTION_GATE_DONE", flush=True)
