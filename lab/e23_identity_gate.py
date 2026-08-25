"""E23 byte-identity gates (scratchpad, private clones only).

Gate A: defaults byte-identity vs the main (3f0c77b) reference binary --
        two runs per binary per instance (determinism + identity), >=12
        Lite instances across 6 repos.
Gate B: new binary, defaults vs --ts-blocks, 30 Lite instances -- proves
        the wiring leaves Python instances untouched (any diff must be
        attributable to a .js/.ts file in the bundle, which is the flag
        working, not a wiring bug; report such cases).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRATCH = Path(__file__).resolve().parent
MAIN_REPO = Path("/Users/nicholasarehart/programming-projects/bgrep")
REF_BIN = SCRATCH / "wt-main-ref/roust-rs/target/release/roust"
NEW_BIN = MAIN_REPO / "roust-rs/target/release/roust"
CLONES = SCRATCH / "gate_clones"
REPOS = ["pallets__flask", "psf__requests", "pytest-dev__pytest",
         "mwaskom__seaborn", "pydata__xarray", "pylint-dev__pylint"]

import pandas as pd

df = pd.read_parquet(MAIN_REPO / "lab/swebench_lite.parquet")
df = df.sort_values(["repo", "instance_id"]).reset_index(drop=True)
df["slug"] = df["repo"].str.replace("/", "__")
pool = df[df["slug"].isin(REPOS)]
print(f"pool: {len(pool)} instances across {pool['slug'].nunique()} repos", flush=True)

gate_a = pool.groupby("slug").head(2)          # 12 instances
gate_b = pool.groupby("slug").head(5)          # 30 instances (5 x 6 repos)


def checkout(slug: str, sha: str) -> Path:
    rp = CLONES / slug
    subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True,
                   capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True,
                   capture_output=True)
    import shutil
    shutil.rmtree(rp / ".roust", ignore_errors=True)  # deterministic cold start
    return rp


def run(binary: Path, query: str, repo: Path, extra=()) -> str:
    argv = [str(binary), "--json", "--budget", "8192", query, str(repo), *extra]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}"
    obj = json.loads(p.stdout)
    # Compare the RETRIEVAL PAYLOAD only: files, regions, bundle, query.
    # stats is dropped wholesale -- engine_sha/engine_dirty differ between
    # the binaries, index_ms/query_ms are wall-clock, and cache ("miss" on
    # the first cold run, "hit" on warm reruns) made the v1 gate flag every
    # cold-vs-warm pair as a mismatch.
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


fail = 0
print("=== Gate A: defaults identity, ref(3f0c77b) vs new, two runs each ===", flush=True)
for _, row in gate_a.iterrows():
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h = [run(REF_BIN, q, rp), run(REF_BIN, q, rp), run(NEW_BIN, q, rp), run(NEW_BIN, q, rp)]
    ok = len(set(h)) == 1 and not h[0].startswith("__ERROR__")
    if not ok:
        fail += 1
    print(f"  {row['instance_id']:45} {'OK' if ok else 'MISMATCH ' + str(h)}", flush=True)

print("=== Gate B: new binary, defaults vs --ts-blocks, 30 instances ===", flush=True)
b_diff = []
for _, row in gate_b.iterrows():
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h_off = run(NEW_BIN, q, rp)
    h_on = run(NEW_BIN, q, rp, extra=("--ts-blocks",))
    same = h_off == h_on and not h_off.startswith("__ERROR__")
    if not same:
        # identify which files are in the bundle to attribute the diff
        p = subprocess.run([str(NEW_BIN), "--json", "--budget", "8192", q, str(rp),
                            "--ts-blocks"], capture_output=True, text=True)
        files = list(json.loads(p.stdout).get("regions", {}).keys())
        nonpy = [f for f in files if not f.endswith(".py")]
        b_diff.append((row["instance_id"], nonpy))
    print(f"  {row['instance_id']:45} {'IDENTICAL' if same else 'DIFFERS'}", flush=True)

print(f"\nGate A failures: {fail}")
print(f"Gate B diffs: {len(b_diff)}")
for iid, nonpy in b_diff:
    print(f"  {iid}: non-.py files in bundle: {nonpy}")
sys.exit(1 if fail else 0)
