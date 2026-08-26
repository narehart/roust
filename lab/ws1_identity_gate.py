"""WS1 (--index-all, campaign #56) byte-identity gates (private clones only).

Gate A: defaults byte-identity vs the main (0d8113e) reference binary --
        two runs per binary per instance (determinism + identity), 12 Lite
        instances across 6 Python repos + 6 MSWE JS/TS instances across 3
        repos (mixed, per the WS1 gate protocol).
Gate B: new binary, defaults vs --index-all, the 12 Lite Python instances --
        the flag may legitimately change output ONLY by newly-admitted files
        entering the pool; every diff is itemized with the non-allowlisted
        files present in the flagged bundle so the change is attributable.

Usage: python lab/ws1_identity_gate.py <ref_bin> <clones_dir>
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

MAIN_REPO = Path(__file__).resolve().parent.parent
REF_BIN = Path(sys.argv[1])
NEW_BIN = MAIN_REPO / "roust-rs/target/release/roust"
CLONES = Path(sys.argv[2])

LITE_REPOS = ["pallets__flask", "psf__requests", "pytest-dev__pytest",
              "mwaskom__seaborn", "pydata__xarray", "pylint-dev__pylint"]
MSWE_REPOS = ["axios__axios", "iamkun__dayjs", "expressjs__express"]

import pandas as pd

CODE_EXTS = (".py", ".ts", ".js", ".go", ".rs", ".java", ".kt", ".cs",
             ".swift", ".tsx", ".jsx")


def pool_from(parquet: str, repos: list[str], per_repo: int) -> pd.DataFrame:
    df = pd.read_parquet(MAIN_REPO / parquet)
    df = df.sort_values(["repo", "instance_id"]).reset_index(drop=True)
    df["slug"] = df["repo"].str.replace("/", "__")
    return df[df["slug"].isin(repos)].groupby("slug").head(per_repo)


def checkout(slug: str, sha: str) -> Path:
    rp = CLONES / slug
    subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True,
                   capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True,
                   capture_output=True)
    shutil.rmtree(rp / ".roust", ignore_errors=True)  # deterministic cold start
    return rp


def run(binary: Path, query: str, repo: Path, extra=()) -> str:
    argv = [str(binary), "--json", "--budget", "8192", query, str(repo), *extra]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}"
    obj = json.loads(p.stdout)
    # RETRIEVAL PAYLOAD only (E23 lesson: stats carries wall-clock + cache
    # miss/hit state and must be excluded from the hash).
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


gate_a = list(pool_from("lab/swebench_lite.parquet", LITE_REPOS, 2).iterrows()) \
       + list(pool_from("lab/mswe_jsts.parquet", MSWE_REPOS, 2).iterrows())
gate_b = pool_from("lab/swebench_lite.parquet", LITE_REPOS, 2)

fail = 0
print(f"=== Gate A: defaults identity, ref({REF_BIN}) vs new, two runs each, "
      f"{len(gate_a)} instances (12 Lite + 6 MSWE) ===", flush=True)
for _, row in gate_a:
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h = [run(REF_BIN, q, rp), run(REF_BIN, q, rp), run(NEW_BIN, q, rp), run(NEW_BIN, q, rp)]
    ok = len(set(h)) == 1 and not h[0].startswith("__ERROR__")
    if not ok:
        fail += 1
    print(f"  {row['instance_id']:45} {'OK' if ok else 'MISMATCH ' + str(h)}", flush=True)

print("=== Gate B: new binary, defaults vs --index-all, 12 Lite instances ===", flush=True)
b_diff = []
for _, row in gate_b.iterrows():
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h_off = run(NEW_BIN, q, rp)
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    h_on = run(NEW_BIN, q, rp, extra=("--index-all",))
    same = h_off == h_on and not h_off.startswith("__ERROR__")
    if not same:
        p = subprocess.run([str(NEW_BIN), "--json", "--budget", "8192", q, str(rp),
                            "--index-all"], capture_output=True, text=True)
        obj = json.loads(p.stdout)
        files = list(obj.get("regions", {}).keys())
        newcomers = [f for f in files if not f.endswith(CODE_EXTS)]
        b_diff.append((row["instance_id"], newcomers,
                       obj.get("stats", {}).get("index_all")))
    print(f"  {row['instance_id']:45} {'IDENTICAL' if same else 'DIFFERS'}", flush=True)

print(f"\nGate A failures: {fail}")
print(f"Gate B diffs (legitimate only if newly-admitted files entered): {len(b_diff)}")
for iid, newcomers, ia_stats in b_diff:
    print(f"  {iid}: non-allowlisted files in flagged bundle: {newcomers}")
    print(f"    index_all stats: {ia_stats}")
sys.exit(1 if fail else 0)
