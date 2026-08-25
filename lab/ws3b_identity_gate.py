"""WS3b pre-arm gates (campaign #56 round WS3b; private clones only).

Modeled on lab/ws3a_identity_gate.py (same retrieval-payload md5, same
two-runs-per-config determinism check).

Gate A -- defaults byte-identity, MAIN(de96114) vs BRANCH(0c0fc79) binary,
  two runs each, on a THIRDPARTY-FREE mixed pool: 6 Lite Python + 4 jsts
  (2 mui + axios + vuejs/core) + 3 rust + 2 cpp (Catch2, fmt -- nlohmann
  deliberately excluded) + 2 java = 17. PASS = all four hashes identical
  per instance. (The unconditional `thirdparty` vendor alternate is the
  ONLY defaults-visible change; on thirdparty-free trees the corpus walk
  is unchanged, so identity must be exact.)

Gate B -- thirdparty itemization: ALL nlohmann__json cpp instances, MAIN
  vs BRANCH defaults. Differences EXPECTED exactly where the checkout
  carries a `thirdparty` path; each diff lists the thirdparty bundle files
  main packed that the branch now excludes.

Gate C -- Python disjointness for --trace-formats-v2: BRANCH binary,
  defaults vs flag, two runs each, on EVERY CPython-trace-bearing Lite
  (50) and Verified (41) instance. The WS3b census proved zero Lite/
  Verified/full instances match any new-format regex, so flag-ON must be
  byte-identical; this is the empirical proof.

Usage:
  uv run --no-project --with pandas --with pyarrow python \
    lab/ws3b_identity_gate.py --base-bin <main roust> --new-bin <branch roust> \
    [--gates ABC]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

WT = Path(__file__).resolve().parent.parent
THIRDPARTY_RE = re.compile(r"(?i)(^|/)thirdparty(/|$)")
TB_FRAME_RE = re.compile(r'^\s*File "([^"]+)", line \d+(?:, in (\S.*))?\s*$')

ap = argparse.ArgumentParser()
ap.add_argument("--base-bin", type=Path, required=True)
ap.add_argument("--new-bin", type=Path, required=True)
ap.add_argument("--gates", default="ABC")
args = ap.parse_args()

for b in (args.base_bin, args.new_bin):
    v = subprocess.run([str(b), "--version"], capture_output=True, text=True).stdout.strip()
    print(f"binary: {b} -> {v}", flush=True)


def checkout(clones: str, slug: str, sha: str) -> Path:
    rp = Path(clones) / slug
    subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True, capture_output=True)
    shutil.rmtree(rp / ".roust", ignore_errors=True)  # deterministic cold start
    return rp


def run(binary: Path, query: str, repo: Path, extra=()):
    argv = [str(binary), "--json", "--budget", "8192", query, str(repo), *extra]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
    if p.returncode != 0:
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}", []
    obj = json.loads(p.stdout)
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    h = hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return h, sorted(obj.get("regions", {}).keys())


def tp_in_tree(rp: Path) -> int:
    out = subprocess.run(["git", "ls-files"], cwd=rp, capture_output=True, text=True)
    return sum(1 for f in out.stdout.splitlines() if THIRDPARTY_RE.search(f))


# ------------------------------------------------------------- pools
lite = pd.read_parquet(WT / "lab/swebench_lite.parquet")
lite = lite.sort_values(["repo", "instance_id"]).reset_index(drop=True)
lite["slug"] = lite["repo"].str.replace("/", "__")

if "A" in args.gates:
    LITE_REPOS = ["astropy__astropy", "matplotlib__matplotlib",
                  "scikit-learn__scikit-learn", "sphinx-doc__sphinx",
                  "django__django", "sympy__sympy"]
    la = lite[lite["slug"].isin(LITE_REPOS)].groupby("slug").head(1).copy()
    la["clones"] = str(WT / "lab/ws3a_repos/repos_gate")
    pool = [la]

    jsts = pd.read_parquet(WT / "lab/mswe_jsts.parquet")
    jsts = jsts.sort_values(["repo", "instance_id"]).reset_index(drop=True)
    jsts["slug"] = jsts["repo"].str.replace("/", "__")
    jm = jsts[jsts["slug"] == "mui__material-ui"].head(2).copy()
    jo = jsts[jsts["slug"].isin(["axios__axios", "vuejs__core"])].groupby("slug").head(1).copy()
    jm["clones"] = jo["clones"] = str(WT / "lab/mswe_repos_e23")
    pool += [jm, jo]

    ws2c = pd.read_parquet(WT / "lab/mswe_ws2c.parquet")
    ws2c = ws2c.sort_values(["repo", "instance_id"]).reset_index(drop=True)
    ws2c["slug"] = ws2c["repo"].str.replace("/", "__")
    rust = ws2c[ws2c["slug"].isin(["BurntSushi__ripgrep", "tokio-rs__tokio",
                                   "serde-rs__serde"])].groupby("slug").head(1).copy()
    rust["clones"] = str(WT / "lab/ws3a_repos/rust_base")
    cpp = ws2c[ws2c["slug"].isin(["catchorg__Catch2", "fmtlib__fmt"])].groupby("slug").head(1).copy()
    cpp["clones"] = str(WT / "lab/ws3a_repos/cpp_base")
    java = ws2c[ws2c["slug"].isin(["fasterxml__jackson-core",
                                   "elastic__logstash"])].groupby("slug").head(1).copy()
    java["clones"] = str(WT / "lab/ws3b_repos/java_base")
    pool += [rust, cpp, java]
    pool_a = pd.concat(pool, ignore_index=True)

    print(f"=== Gate A: defaults identity, MAIN vs BRANCH, two runs each "
          f"({len(pool_a)} thirdparty-free mixed instances) ===", flush=True)
    fail_a = 0
    for _, row in pool_a.iterrows():
        rp = checkout(row["clones"], row["slug"], row["base_commit"])
        ntp = tp_in_tree(rp)
        q = row["problem_statement"]
        h = [run(args.base_bin, q, rp)[0], run(args.base_bin, q, rp)[0],
             run(args.new_bin, q, rp)[0], run(args.new_bin, q, rp)[0]]
        ok = len(set(h)) == 1 and not h[0].startswith("__ERROR__") and ntp == 0
        if not ok:
            fail_a += 1
        print(f"  {row['instance_id']:50} tp_files={ntp} "
              f"{'OK' if ok else 'MISMATCH ' + str(h)}", flush=True)
    print(f"Gate A failures: {fail_a}", flush=True)

if "B" in args.gates:
    ws2c = pd.read_parquet(WT / "lab/mswe_ws2c.parquet")
    ws2c["slug"] = ws2c["repo"].str.replace("/", "__")
    nl = ws2c[ws2c["slug"] == "nlohmann__json"].sort_values("instance_id")
    print(f"=== Gate B: thirdparty itemization, MAIN vs BRANCH defaults, "
          f"all {len(nl)} nlohmann instances ===", flush=True)
    for _, row in nl.iterrows():
        rp = checkout(str(WT / "lab/ws3a_repos/cpp_base"), row["slug"], row["base_commit"])
        ntp = tp_in_tree(rp)
        q = row["problem_statement"]
        h_main, files_main = run(args.base_bin, q, rp)
        shutil.rmtree(rp / ".roust", ignore_errors=True)
        h_new, files_new = run(args.new_bin, q, rp)
        same = h_main == h_new
        tp_main = [f for f in files_main if THIRDPARTY_RE.search(f)]
        tp_new = [f for f in files_new if THIRDPARTY_RE.search(f)]
        status = "IDENTICAL" if same else "DIFFERS"
        print(f"  {row['instance_id']:30} tp_files_in_tree={ntp:4d} {status} "
              f"tp_in_main_bundle={tp_main} tp_in_new_bundle={tp_new}", flush=True)

if "C" in args.gates:
    ver = pd.read_parquet(WT / "lab/swebench_verified_heldout.parquet")
    ver = ver.sort_values(["repo", "instance_id"]).reset_index(drop=True)
    ver["slug"] = ver["repo"].str.replace("/", "__")
    pool_c = []
    for name, df in (("lite", lite), ("verified", ver)):
        tb = df[df["problem_statement"].apply(
            lambda t: any(TB_FRAME_RE.match(ln) for ln in (t or "").splitlines()))].copy()
        tb["clones"] = str(WT / "lab/ws3a_repos/repos_gate")
        tb["pool"] = name
        pool_c.append(tb)
    pool_c = pd.concat(pool_c, ignore_index=True)
    print(f"=== Gate C: --trace-formats-v2 Python disjointness, BRANCH binary, "
          f"two runs each ({len(pool_c)} CPython-trace-bearing instances) ===", flush=True)
    fail_c = 0
    for _, row in pool_c.iterrows():
        rp = checkout(row["clones"], row["slug"], row["base_commit"])
        q = row["problem_statement"]
        h = [run(args.new_bin, q, rp)[0], run(args.new_bin, q, rp)[0],
             run(args.new_bin, q, rp, extra=("--trace-formats-v2",))[0],
             run(args.new_bin, q, rp, extra=("--trace-formats-v2",))[0]]
        ok = len(set(h)) == 1 and not h[0].startswith("__ERROR__")
        if not ok:
            fail_c += 1
        print(f"  [{row['pool']:8}] {row['instance_id']:45} "
              f"{'OK' if ok else 'MISMATCH ' + str(h)}", flush=True)
    print(f"Gate C failures: {fail_c}", flush=True)

print("GATES_DONE", flush=True)
