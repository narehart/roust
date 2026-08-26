"""WS3a pre-arm identity gates (campaign #56 round WS3a; private clones only).

Modeled on lab/ws2b_identity_gate.py (same retrieval-payload md5, same
two-runs-per-binary determinism check), with the pool widened to a MIXED
language set -- the round's change surface is exactly the non-Python
slices, so flag-OFF identity is proven where v1 damping actually fires.

Gate A -- defaults identity, MAIN(3cb92d9) vs BRANCH(499ec29) binary, two
  runs each: 6 Lite Python (one per repo: astropy, matplotlib, sklearn,
  sphinx, django, sympy) + 4 jsts (2 mui docs-heavy + axios + vuejs/core)
  + 3 rust (ripgrep, tokio, serde) + 3 cpp (Catch2, fmt, nlohmann) = 16.
  PASS = all four hashes identical per instance, no errors.

Gate B -- BRANCH binary, defaults vs --impl-prior-v2, same 16 instances:
  DIAGNOSTIC. Differences are EXPECTED wherever the corpus holds v1-damped
  doc-dir code files (mui, ripgrep, Catch2, matplotlib galleries/); each
  diff is attributed by listing bundle files whose damped status changed.

Usage:
  uv run --no-project --with pandas --with pyarrow python \
    lab/ws3a_identity_gate.py --base-bin <main roust> --new-bin <branch roust>
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

# v1/v2 predicate ports (ws3a_census_v2.py, mirrors core.rs) for Gate B
# attribution only.
TESTLIKE_RE = re.compile(
    r"(?i)(^|/)(tests?|testing|spec|specs|benches|benchmarks?|examples?|"
    r"fixtures?|mocks?|docs?|__tests__|e2e|docs_src|tutorials?|samples?|"
    r"demos?|playground|scripts?|integration|t)(/|$)|(^|/)(test_|conftest)|"
    r"_test\.(py|go|rs|ts|js)$|\.test\.|\.spec\."
)
TESTLIKE_V2_RE = re.compile(
    r"(?i)(^|/)(tests?|testing|spec|specs|fixtures?|mocks?|__tests__|e2e|"
    r"docs_src|tutorials?|samples?|demos?|playground|scripts?|integration|t)"
    r"(/|$)|(^|/)(test_|conftest)|_test\.[A-Za-z0-9]+$|\.test\.|\.spec\."
)
DOCLIKE_V2_RE = re.compile(r"(?i)(^|/)(docs?|examples?|benchmarks?|benches)(/|$)")
CODE_EXTS = (".py", ".ts", ".js", ".go", ".rs", ".java", ".kt", ".cs",
             ".swift", ".tsx", ".jsx", ".c", ".h", ".cc", ".cpp", ".cxx",
             ".hpp", ".hh")


def damp_status_changed(rel: str) -> bool:
    v1 = bool(TESTLIKE_RE.search(rel))
    v2 = bool(TESTLIKE_V2_RE.search(rel)) or (
        bool(DOCLIKE_V2_RE.search(rel)) and not rel.endswith(CODE_EXTS))
    return v1 != v2


ap = argparse.ArgumentParser()
ap.add_argument("--base-bin", type=Path, required=True)
ap.add_argument("--new-bin", type=Path, required=True)
args = ap.parse_args()

# ------------------------------------------------------------- mixed pool
LITE_REPOS = ["astropy__astropy", "matplotlib__matplotlib",
              "scikit-learn__scikit-learn", "sphinx-doc__sphinx",
              "django__django", "sympy__sympy"]
lite = pd.read_parquet(WT / "lab/swebench_lite.parquet")
lite = lite.sort_values(["repo", "instance_id"]).reset_index(drop=True)
lite["slug"] = lite["repo"].str.replace("/", "__")
lite["clones"] = str(WT / "lab/ws3a_repos/repos_gate")
pool = [lite[lite["slug"].isin(LITE_REPOS)].groupby("slug").head(1)]

jsts = pd.read_parquet(WT / "lab/mswe_jsts.parquet")
jsts = jsts.sort_values(["repo", "instance_id"]).reset_index(drop=True)
jsts["slug"] = jsts["repo"].str.replace("/", "__")
jsts["clones"] = str(WT / "lab/mswe_repos_e23")
pool.append(jsts[jsts["slug"] == "mui__material-ui"].head(2))
pool.append(jsts[jsts["slug"].isin(["axios__axios", "vuejs__core"])].groupby("slug").head(1))

ws2c = pd.read_parquet(WT / "lab/mswe_ws2c.parquet")
ws2c = ws2c.sort_values(["repo", "instance_id"]).reset_index(drop=True)
ws2c["slug"] = ws2c["repo"].str.replace("/", "__")
rust = ws2c[ws2c["slug"].isin(["BurntSushi__ripgrep", "tokio-rs__tokio",
                               "serde-rs__serde"])].groupby("slug").head(1).copy()
rust["clones"] = str(WT / "lab/ws3a_repos/rust_base")
pool.append(rust)
cpp = ws2c[ws2c["slug"].isin(["catchorg__Catch2", "fmtlib__fmt",
                              "nlohmann__json"])].groupby("slug").head(1).copy()
cpp["clones"] = str(WT / "lab/ws3a_repos/cpp_base")
pool.append(cpp)

pool = pd.concat(pool, ignore_index=True)

for b in (args.base_bin, args.new_bin):
    v = subprocess.run([str(b), "--version"], capture_output=True, text=True).stdout.strip()
    print(f"binary: {b} -> {v}", flush=True)
print(f"gate pool: {len(pool)} mixed instances "
      f"({pool['slug'].nunique()} repos)", flush=True)


def checkout(clones: str, slug: str, sha: str) -> Path:
    rp = Path(clones) / slug
    subprocess.run(["git", "checkout", "-f", sha], cwd=rp, check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True, capture_output=True)
    shutil.rmtree(rp / ".roust", ignore_errors=True)  # deterministic cold start
    return rp


def run(binary: Path, query: str, repo: Path, extra=()):
    argv = [str(binary), "--json", "--budget", "8192", query, str(repo), *extra]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=1200)
    if p.returncode != 0:
        return f"__ERROR__ exit {p.returncode}: {p.stderr[:200]}", []
    obj = json.loads(p.stdout)
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    h = hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return h, list(obj.get("regions", {}).keys())


fail_a = 0
print("=== Gate A: defaults identity, MAIN vs BRANCH binary, two runs each ===", flush=True)
for _, row in pool.iterrows():
    rp = checkout(row["clones"], row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h = [run(args.base_bin, q, rp)[0], run(args.base_bin, q, rp)[0],
         run(args.new_bin, q, rp)[0], run(args.new_bin, q, rp)[0]]
    ok = len(set(h)) == 1 and not h[0].startswith("__ERROR__")
    if not ok:
        fail_a += 1
    print(f"  {row['instance_id']:50} {'OK' if ok else 'MISMATCH ' + str(h)}", flush=True)

print("=== Gate B (diagnostic): BRANCH binary, defaults vs --impl-prior-v2 ===", flush=True)
n_diff = 0
for _, row in pool.iterrows():
    rp = checkout(row["clones"], row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h_off, _ = run(args.new_bin, q, rp)
    # --impl-prior-v2 re-keys the cache; no manual clear needed.
    h_on, files_on = run(args.new_bin, q, rp, extra=("--impl-prior-v2",))
    same = h_off == h_on and not h_off.startswith("__ERROR__")
    if not same:
        n_diff += 1
        flipped = [f for f in files_on if damp_status_changed(f)]
        print(f"  {row['instance_id']:50} DIFFERS; undamped-by-v2 files in "
              f"bundle: {flipped}", flush=True)
    else:
        print(f"  {row['instance_id']:50} IDENTICAL", flush=True)

print(f"\nGate A failures: {fail_a}")
print(f"Gate B diffs (expected wherever doc-dir code files rank): {n_diff}")
sys.exit(1 if fail_a else 0)
