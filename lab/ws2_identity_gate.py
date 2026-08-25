"""WS2 byte-identity gates (campaign #56 workstream 2; private clones only).

Modeled on lab/e23_identity_gate.py (same retrieval-payload md5, same
two-runs-per-binary determinism check). Binaries are PINNED WORKTREE builds:

  BASE_BIN: ws2-main-baseline @ 0d8113e (origin/main, E23 adoption tip)
  NEW_BIN:  ws2-grammar-batch @ 96b77da (engine + harness twin commits)

Gate A -- defaults byte-identity, BASE vs NEW, two runs per binary:
  12 SWE-bench Lite Python instances (6 repos x 2) + 6 Multi-SWE JS/TS
  instances (axios/dayjs/express x 2). Nothing may change for the existing
  languages: the grammar batch only touches extensions main sends to
  window_blocks (.java/.go/.rs) or never indexes (C family).

Gate B -- NEW binary, defaults vs --cfamily-ext, the 12 Python instances:
  the flag must be inert on repos without C-family files (the six Lite
  repos are pure Python); a diff is attributed by listing the bundle's
  C-family files (flag working) vs none (wiring bug).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

WT = Path(__file__).resolve().parent.parent
BASE_BIN = WT.parent / "ws2-main-baseline/roust-rs/target/release/roust"
NEW_BIN = WT / "roust-rs/target/release/roust"
CLONES = WT / "lab/ws2_gate_clones"
PY_REPOS = ["pallets__flask", "psf__requests", "pytest-dev__pytest",
            "mwaskom__seaborn", "pydata__xarray", "pylint-dev__pylint"]
JS_REPOS = ["axios__axios", "iamkun__dayjs", "expressjs__express"]

import pandas as pd

lite = pd.read_parquet(WT / "lab/swebench_lite.parquet")
lite = lite.sort_values(["repo", "instance_id"]).reset_index(drop=True)
lite["slug"] = lite["repo"].str.replace("/", "__")
py_pool = lite[lite["slug"].isin(PY_REPOS)].groupby("slug").head(2)  # 12

jsts = pd.read_parquet(WT / "lab/mswe_jsts.parquet")
jsts = jsts.sort_values(["repo", "instance_id"]).reset_index(drop=True)
jsts["slug"] = jsts["repo"].str.replace("/", "__")
js_pool = jsts[jsts["slug"].isin(JS_REPOS)].groupby("slug").head(2)  # 6

print(f"gate pool: {len(py_pool)} Python + {len(js_pool)} JS/TS instances", flush=True)


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
    p = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}"
    obj = json.loads(p.stdout)
    # Retrieval payload only (e23 lesson: stats.cache flips cold/warm).
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


fail_a = 0
print("=== Gate A: defaults identity, BASE(0d8113e) vs NEW(96b77da), two runs each ===", flush=True)
for _, row in pd.concat([py_pool, js_pool]).iterrows():
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h = [run(BASE_BIN, q, rp), run(BASE_BIN, q, rp), run(NEW_BIN, q, rp), run(NEW_BIN, q, rp)]
    ok = len(set(h)) == 1 and not h[0].startswith("__ERROR__")
    if not ok:
        fail_a += 1
    print(f"  {row['instance_id']:45} {'OK' if ok else 'MISMATCH ' + str(h)}", flush=True)

print("=== Gate B: NEW binary, defaults vs --cfamily-ext, 12 Python instances ===", flush=True)
b_diff = []
for _, row in py_pool.iterrows():
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h_off = run(NEW_BIN, q, rp)
    h_on = run(NEW_BIN, q, rp, extra=("--cfamily-ext",))
    same = h_off == h_on and not h_off.startswith("__ERROR__")
    if not same:
        p = subprocess.run([str(NEW_BIN), "--json", "--budget", "8192", q, str(rp),
                            "--cfamily-ext"], capture_output=True, text=True)
        files = list(json.loads(p.stdout).get("regions", {}).keys())
        cfam = [f for f in files if f.endswith((".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh"))]
        b_diff.append((row["instance_id"], cfam))
    print(f"  {row['instance_id']:45} {'IDENTICAL' if same else 'DIFFERS'}", flush=True)

print(f"\nGate A failures: {fail_a}")
print(f"Gate B diffs: {len(b_diff)}")
for iid, cfam in b_diff:
    print(f"  {iid}: C-family files in bundle: {cfam}")
sys.exit(1 if fail_a else 0)
