"""WS3c pre-arm gates (campaign #56 round WS3c; private clones only).

Modeled on lab/ws3b_identity_gate.py (same retrieval-payload md5, same
two-runs-per-config determinism check).

Gate A -- defaults byte-identity, MAIN(8d86875) vs BRANCH(10967da) binary,
  two runs each, on the WS3b mixed pool: 6 Lite Python + 4 jsts + 3 rust +
  2 cpp + 2 java = 17. WS3c is fully flag-gated (--symbols-v2 default
  OFF), so defaults identity must be EXACT on every instance. PASS = all
  four hashes identical per instance.

Gate B -- flag-ON behavior, BRANCH binary only:
  (1) determinism: two `--symbols-v2` runs per instance must hash
      identically (the new def-entry walk and seating map must be pure
      functions of the tree) -- checked on the same mixed pool;
  (2) Python-inertness itemization (informational, not pass/fail):
      defaults vs --symbols-v2 on the 6 Lite instances. Python's OWN def
      extraction is untouched, but Python repos contain JS/C/C++ files
      whose def_index gains entries under the flag, so an instance may
      legitimately differ iff a new symbol anchor fires; each row reports
      IDENTICAL/DIFFERS. The Lite-300/Verified-407 arms measure the
      metric impact; this itemization names the mechanism.

Usage:
  uv run --no-project --with pandas --with pyarrow python \
    lab/ws3c_identity_gate.py --base-bin <main roust> --new-bin <branch roust> \
    [--gates AB]
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

# Data root: the MAIN repo checkout carries the (untracked) parquets and
# private clone dirs; worktree copies of this script must not resolve
# them relative to themselves. Overridable for future relocations.
WT = Path(os.environ.get("ROUST_LAB_ROOT",
                         "/Users/nicholasarehart/programming-projects/bgrep"))

ap = argparse.ArgumentParser()
ap.add_argument("--base-bin", type=Path, required=True)
ap.add_argument("--new-bin", type=Path, required=True)
ap.add_argument("--gates", default="AB")
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
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}"
    obj = json.loads(p.stdout)
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------- pool (WS3b gate A pool)
lite = pd.read_parquet(WT / "lab/swebench_lite.parquet")
lite = lite.sort_values(["repo", "instance_id"]).reset_index(drop=True)
lite["slug"] = lite["repo"].str.replace("/", "__")
LITE_REPOS = ["astropy__astropy", "matplotlib__matplotlib",
              "scikit-learn__scikit-learn", "sphinx-doc__sphinx",
              "django__django", "sympy__sympy"]
la = lite[lite["slug"].isin(LITE_REPOS)].groupby("slug").head(1).copy()
la["clones"] = str(WT / "lab/ws3a_repos/repos_gate")
la["pool"] = "lite"
pool = [la]

jsts = pd.read_parquet(WT / "lab/mswe_jsts.parquet")
jsts = jsts.sort_values(["repo", "instance_id"]).reset_index(drop=True)
jsts["slug"] = jsts["repo"].str.replace("/", "__")
jm = jsts[jsts["slug"] == "mui__material-ui"].head(2).copy()
jo = jsts[jsts["slug"].isin(["axios__axios", "vuejs__core"])].groupby("slug").head(1).copy()
jm["clones"] = jo["clones"] = str(WT / "lab/mswe_repos_e23")
jm["pool"] = jo["pool"] = "jsts"
pool += [jm, jo]

ws2c = pd.read_parquet(WT / "lab/mswe_ws2c.parquet")
ws2c = ws2c.sort_values(["repo", "instance_id"]).reset_index(drop=True)
ws2c["slug"] = ws2c["repo"].str.replace("/", "__")
rust = ws2c[ws2c["slug"].isin(["BurntSushi__ripgrep", "tokio-rs__tokio",
                               "serde-rs__serde"])].groupby("slug").head(1).copy()
rust["clones"] = str(WT / "lab/ws3a_repos/rust_base")
rust["pool"] = "rust"
cpp = ws2c[ws2c["slug"].isin(["catchorg__Catch2", "fmtlib__fmt"])].groupby("slug").head(1).copy()
cpp["clones"] = str(WT / "lab/ws3a_repos/cpp_base")
cpp["pool"] = "cpp"
java = ws2c[ws2c["slug"].isin(["fasterxml__jackson-core",
                               "elastic__logstash"])].groupby("slug").head(1).copy()
java["clones"] = str(WT / "lab/ws3b_repos/java_base")
java["pool"] = "java"
pool += [rust, cpp, java]
pool_all = pd.concat(pool, ignore_index=True)

if "A" in args.gates:
    print(f"=== Gate A: defaults identity, MAIN vs BRANCH, two runs each "
          f"({len(pool_all)} mixed instances) ===", flush=True)
    fail_a = 0
    for _, row in pool_all.iterrows():
        rp = checkout(row["clones"], row["slug"], row["base_commit"])
        q = row["problem_statement"]
        h = [run(args.base_bin, q, rp), run(args.base_bin, q, rp),
             run(args.new_bin, q, rp), run(args.new_bin, q, rp)]
        ok = len(set(h)) == 1 and not h[0].startswith("__ERROR__")
        if not ok:
            fail_a += 1
        print(f"  [{row['pool']:5}] {row['instance_id']:45} "
              f"{'OK' if ok else 'MISMATCH ' + str(h)}", flush=True)
    print(f"Gate A failures: {fail_a}", flush=True)

if "B" in args.gates:
    print(f"=== Gate B: BRANCH binary flag-ON determinism (2 runs) + "
          f"defaults-vs-flag itemization ({len(pool_all)} instances) ===", flush=True)
    fail_b = 0
    n_differ = 0
    for _, row in pool_all.iterrows():
        rp = checkout(row["clones"], row["slug"], row["base_commit"])
        q = row["problem_statement"]
        h_off = run(args.new_bin, q, rp)
        shutil.rmtree(rp / ".roust", ignore_errors=True)
        h_on1 = run(args.new_bin, q, rp, extra=("--symbols-v2",))
        h_on2 = run(args.new_bin, q, rp, extra=("--symbols-v2",))
        det_ok = h_on1 == h_on2 and not h_on1.startswith("__ERROR__")
        if not det_ok:
            fail_b += 1
        same = h_off == h_on1
        if not same:
            n_differ += 1
        print(f"  [{row['pool']:5}] {row['instance_id']:45} "
              f"det={'OK' if det_ok else 'FAIL'} "
              f"flag={'IDENTICAL' if same else 'DIFFERS'}", flush=True)
    print(f"Gate B determinism failures: {fail_b}; flag-differs: {n_differ} "
          f"(differs is informational -- itemized by the arms)", flush=True)

print("GATES_DONE", flush=True)
