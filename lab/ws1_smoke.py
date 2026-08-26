"""WS1 smoke (gate protocol step 1): 10 ceiling-blocked MSWE instances.

For each: check out base commit in the private scratchpad clone, run the new
binary with --index-all on the real problem statement, and report for every
out-of-allowlist gold file:
  indexed?  (present in the corpus files list persisted to .roust/rust-index.bin)
  returned? (present in the query's regions dict)
Also reports files_indexed baseline-vs-flagged and cold-index/query timings.
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

MAIN_REPO = Path("/Users/nicholasarehart/programming-projects/bgrep")
CLONES = Path(sys.argv[1])
RECORDS = Path(sys.argv[2])
NEW_BIN = MAIN_REPO / "roust-rs/target/release/roust"

import pandas as pd

df = pd.read_parquet(MAIN_REPO / "lab/mswe_jsts.parquet")
df["slug"] = df["repo"].str.replace("/", "__")
by_iid = {r["instance_id"]: r for _, r in df.iterrows()}

records = [json.loads(l) for l in RECORDS.read_text().splitlines()]
# 10 instances: spread across repos and gold suffixes (.svelte/.mjs/<none>/
# .preview/.yaml oddballs first, then fill with .json/.md heavy ones).
def suffix_set(rec):
    return {f.rsplit(".", 1)[-1] if "." in f.rsplit("/", 1)[-1] else "<none>"
            for f in rec["outside"]}
odd = [r for r in records if suffix_set(r) - {"json", "md"}]
common = [r for r in records if not (suffix_set(r) - {"json", "md"})]
picked, seen = [], set()
# one odd-suffix instance per slug first, then round-robin fill to 10
for r in odd:
    if r["slug"] not in seen:
        picked.append(r); seen.add(r["slug"])
for r in common + odd:
    if len(picked) >= 10:
        break
    if r not in picked:
        picked.append(r)
picked = picked[:10]

def run(query, rp, extra=()):
    t0 = time.time()
    p = subprocess.run([str(NEW_BIN), "--json", "--budget", "8192", query, str(rp), *extra],
                       capture_output=True, text=True, timeout=600)
    wall = time.time() - t0
    if p.returncode not in (0, 1):
        return None, wall, f"exit {p.returncode}: {p.stderr[:200]}"
    return json.loads(p.stdout), wall, None

n_indexed = n_returned = n_files = 0
for rec in picked:
    row = by_iid[rec["instance_id"]]
    rp = CLONES / rec["slug"]
    subprocess.run(["git", "checkout", "-f", "-q", rec["base_commit"]], cwd=rp,
                   check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, capture_output=True)
    shutil.rmtree(rp / ".roust", ignore_errors=True)

    obj_base, wall_base, err_b = run(row["problem_statement"], rp)
    base_idx_size = (rp / ".roust/rust-index.bin").stat().st_size
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    obj_flag, wall_flag, err_f = run(row["problem_statement"], rp, ("--index-all",))
    obj_flag2, wall_flag_warm, _ = run(row["problem_statement"], rp, ("--index-all",))

    cache = json.loads((rp / ".roust/rust-index.bin").read_text())
    corpus_files = set(cache["corpus"]["files"])
    regions = set((obj_flag or {}).get("regions", {}).keys())
    fi_base = (obj_base or {}).get("stats", {}).get("files_indexed")
    fi_flag = (obj_flag or {}).get("stats", {}).get("files_indexed")
    print(f"\n{rec['instance_id']} ({rec['slug']})  files_indexed {fi_base} -> {fi_flag}  "
          f"cold {wall_base:.1f}s/base {wall_flag:.1f}s/flag warm {wall_flag_warm:.1f}s"
          + (f"  ERR base={err_b} flag={err_f}" if (err_b or err_f) else ""), flush=True)
    idx_size = (rp / ".roust/rust-index.bin").stat().st_size
    print(f"  index size: {base_idx_size/1e6:.1f} -> {idx_size/1e6:.1f} MB", flush=True)
    for f in rec["outside"]:
        n_files += 1
        indexed = f in corpus_files
        returned = f in regions
        n_indexed += indexed
        n_returned += returned
        print(f"  gold {f}: indexed={indexed} returned={returned}", flush=True)

print(f"\nSMOKE TOTAL: {n_files} out-of-allowlist gold files -> "
      f"indexed {n_indexed}/{n_files}, returned {n_returned}/{n_files}")
