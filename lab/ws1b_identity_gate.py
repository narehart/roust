"""WS1b (--index-all-additive, campaign #56) byte-identity + invariant gates.

Gate A: defaults byte-identity vs the main (0d8113e) reference binary --
        two runs per binary per instance (determinism + identity), 12 Lite
        instances across 6 Python repos + 6 MSWE JS/TS instances across 3
        repos (mixed, same pool as WS1's gate A).
Gate B: flag-on invariant, new binary, all 18 instances -- the
        --index-all-additive output MUST be the defaults output plus zero
        or more APPENDED newcomer files: defaults file list is a byte-
        identical prefix of the flagged list, every defaults file's spans
        are byte-unchanged, the flagged bundle starts with the defaults
        bundle, every appended file is non-allowlisted, and bundle tokens
        stay within budget. Any violation fails the gate.

Usage: python lab/ws1b_identity_gate.py <ref_bin> <clones_dir>
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


def has_allowlisted_suffix(rel: str) -> bool:
    # mirrors roust::core::has_allowlisted_suffix for the gate's newcomer
    # check (last dotted component against the engine allowlist)
    return rel.endswith(CODE_EXTS)


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


def run_obj(binary: Path, query: str, repo: Path, extra=()):
    argv = [str(binary), "--json", "--budget", "8192", query, str(repo), *extra]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    if p.returncode not in (0, 1):
        return None, f"exit {p.returncode}: {p.stderr[:200]}"
    return json.loads(p.stdout), None


def payload_hash(obj) -> str:
    payload = {k: obj.get(k) for k in ("query", "files", "regions", "bundle")}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def run_hash(binary: Path, query: str, repo: Path, extra=()) -> str:
    obj, err = run_obj(binary, query, repo, extra)
    if err:
        return f"__ERROR__ {err}"
    return payload_hash(obj)


gate = list(pool_from("lab/swebench_lite.parquet", LITE_REPOS, 2).iterrows()) \
     + list(pool_from("lab/mswe_jsts.parquet", MSWE_REPOS, 2).iterrows())

fail = 0
print(f"=== Gate A: defaults identity, ref({REF_BIN}) vs new({NEW_BIN}), two "
      f"runs each, {len(gate)} instances (12 Lite + 6 MSWE) ===", flush=True)
for _, row in gate:
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    h = [run_hash(REF_BIN, q, rp), run_hash(REF_BIN, q, rp),
         run_hash(NEW_BIN, q, rp), run_hash(NEW_BIN, q, rp)]
    ok = len(set(h)) == 1 and not h[0].startswith("__ERROR__")
    if not ok:
        fail += 1
    print(f"  {row['instance_id']:45} {'OK' if ok else 'MISMATCH ' + str(h)}", flush=True)

print(f"=== Gate B: --index-all-additive invariant, new binary, {len(gate)} "
      f"instances ===", flush=True)
for _, row in gate:
    rp = checkout(row["slug"], row["base_commit"])
    q = row["problem_statement"]
    base, err_b = run_obj(NEW_BIN, q, rp)
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    add, err_a = run_obj(NEW_BIN, q, rp, extra=("--index-all-additive",))
    problems = []
    if err_b or err_a:
        problems.append(f"error base={err_b} add={err_a}")
    else:
        bf = [f["path"] for f in base["files"]]
        af = [f["path"] for f in add["files"]]
        if af[:len(bf)] != bf:
            problems.append("defaults file list is NOT a prefix of the flagged list")
        for f in af[len(bf):]:
            if has_allowlisted_suffix(f):
                problems.append(f"appended allowlisted file {f}")
        for f in bf:
            if add["regions"].get(f) != base["regions"].get(f):
                problems.append(f"core spans changed for {f}")
        if not add["bundle"].startswith(base["bundle"]):
            problems.append("flagged bundle does not start with defaults bundle")
        if add["stats"]["bundle_tokens"] > 8192:
            problems.append(f"bundle_tokens {add['stats']['bundle_tokens']} > budget")
        st = add["stats"].get("index_all_additive") or {}
        n_admitted = st.get("n_newcomers_admitted", 0)
        if n_admitted != len(af) - len(bf):
            problems.append(f"stats n_newcomers_admitted={n_admitted} != appended {len(af)-len(bf)}")
    ok = not problems
    if not ok:
        fail += 1
    extra = "" if err_b or err_a or not ok else \
        f"+{len(af) - len(bf)} newcomers, {st.get('newcomer_tokens', 0)} tok of {st.get('leftover_tokens', 0)} leftover"
    print(f"  {row['instance_id']:45} {'OK ' + extra if ok else 'VIOLATION ' + '; '.join(problems)}",
          flush=True)

print(f"=== {'GATE PASS' if fail == 0 else f'GATE FAIL ({fail} failures)'} ===", flush=True)
sys.exit(0 if fail == 0 else 1)
