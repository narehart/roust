"""WS1b smoke (gate protocol step 2): the 10 WS1 ceiling-smoke instances.

For each: check out the base commit in a private clone, run the new binary
on the real problem statement twice -- defaults, then --index-all-additive
-- and report for every out-of-allowlist gold file whether the additive run
returned it, WITHOUT the old selection changing (invariant asserted per
instance: defaults file list is a prefix of the flagged list, core spans
byte-unchanged, flagged bundle starts with the defaults bundle). Also
reports newcomer admissions and leftover-budget consumption.

Instance selection is byte-copied from lab/ws1_smoke.py so the 10 instances
match WS1's smoke exactly.

Usage: python lab/ws1b_smoke.py <clones_dir> <ceiling_records_jsonl>
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

MAIN_REPO = Path(__file__).resolve().parent.parent
CLONES = Path(sys.argv[1])
RECORDS = Path(sys.argv[2])
NEW_BIN = MAIN_REPO / "roust-rs/target/release/roust"

import pandas as pd

df = pd.read_parquet(MAIN_REPO / "lab/mswe_jsts.parquet")
df["slug"] = df["repo"].str.replace("/", "__")
by_iid = {r["instance_id"]: r for _, r in df.iterrows()}

records = [json.loads(l) for l in RECORDS.read_text().splitlines()]


# --- identical selection to lab/ws1_smoke.py ---
def suffix_set(rec):
    return {f.rsplit(".", 1)[-1] if "." in f.rsplit("/", 1)[-1] else "<none>"
            for f in rec["outside"]}


odd = [r for r in records if suffix_set(r) - {"json", "md"}]
common = [r for r in records if not (suffix_set(r) - {"json", "md"})]
picked, seen = [], set()
for r in odd:
    if r["slug"] not in seen:
        picked.append(r); seen.add(r["slug"])
for r in common + odd:
    if len(picked) >= 10:
        break
    if r not in picked:
        picked.append(r)
picked = picked[:10]
# --- end identical selection ---


def run(query, rp, extra=()):
    t0 = time.time()
    p = subprocess.run([str(NEW_BIN), "--json", "--budget", "8192", query, str(rp), *extra],
                       capture_output=True, text=True, timeout=600)
    wall = time.time() - t0
    if p.returncode not in (0, 1):
        return None, wall, f"exit {p.returncode}: {p.stderr[:200]}"
    return json.loads(p.stdout), wall, None


n_files = n_returned = 0
n_invariant_violations = 0
for rec in picked:
    row = by_iid[rec["instance_id"]]
    rp = CLONES / rec["slug"]
    subprocess.run(["git", "checkout", "-f", "-q", rec["base_commit"]], cwd=rp,
                   check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, capture_output=True)
    shutil.rmtree(rp / ".roust", ignore_errors=True)

    obj_base, wall_base, err_b = run(row["problem_statement"], rp)
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    obj_add, wall_add, err_a = run(row["problem_statement"], rp, ("--index-all-additive",))
    if err_b or err_a:
        print(f"\n{rec['instance_id']} ({rec['slug']})  ERR base={err_b} add={err_a}", flush=True)
        n_invariant_violations += 1
        continue

    bf = [f["path"] for f in obj_base["files"]]
    af = [f["path"] for f in obj_add["files"]]
    problems = []
    if af[:len(bf)] != bf:
        problems.append("defaults file list not a prefix of flagged list")
    for f in bf:
        if obj_add["regions"].get(f) != obj_base["regions"].get(f):
            problems.append(f"core spans changed for {f}")
    if not obj_add["bundle"].startswith(obj_base["bundle"]):
        problems.append("bundle not prefix-identical")
    if problems:
        n_invariant_violations += 1

    st = obj_add["stats"].get("index_all_additive") or {}
    regions = set(obj_add.get("regions", {}).keys())
    print(f"\n{rec['instance_id']} ({rec['slug']})  cold {wall_base:.1f}s/base "
          f"{wall_add:.1f}s/add  newcomers admitted {st.get('n_newcomers_admitted')} "
          f"of {st.get('n_newcomer_candidates')} candidates, "
          f"{st.get('newcomer_tokens')} tok of {st.get('leftover_tokens')} leftover "
          f"(core {st.get('core_bundle_tokens')} tok)"
          + (f"  INVARIANT VIOLATION: {'; '.join(problems)}" if problems else ""), flush=True)
    if st.get("newcomers_admitted"):
        print(f"  admitted: {st['newcomers_admitted']}", flush=True)
    for f in rec["outside"]:
        n_files += 1
        returned = f in regions
        n_returned += returned
        print(f"  gold {f}: returned={returned}", flush=True)

print(f"\nSMOKE TOTAL: {n_files} out-of-allowlist gold files -> returned "
      f"{n_returned}/{n_files}; invariant violations {n_invariant_violations}/10")
