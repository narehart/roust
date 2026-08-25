"""WS3b gold-rank capture: for every trace-firing instance of a slice, run
the pinned branch binary with and without --trace-formats-v2 and report the
rank of the first gold file in the engine's ranked `files` output, plus
which resolved frames fired and whether any frame IS a gold file.

Usage:
  uv run --no-project --with pandas --with pyarrow python lab/ws3b_goldrank.py \
      <binary> <gold.parquet> <repos_dir> <v2_report.jsonl>
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

binary, parquet, repos_dir, v2_report = sys.argv[1:5]

fired = {}
for line in open(v2_report):
    r = json.loads(line)
    tb = (r.get("trace_boost") or {}).get("trace_files") or []
    if tb:
        fired[r["instance_id"]] = tb

df = pd.read_parquet(parquet)
df = df[df["instance_id"].isin(fired)].sort_values("instance_id")


def gold_files(patch):
    return sorted({m.group(2) for m in
                   re.finditer(r"^diff --git a/(\S+) b/(\S+)", patch or "", re.M)})


def ranked_files(rp, query, extra=()):
    argv = [binary, "--json", "--budget", "8192", query, str(rp), *extra]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
    if p.returncode != 0:
        return None
    obj = json.loads(p.stdout)
    return [f["path"] if isinstance(f, dict) else f for f in obj.get("files", [])]


for _, row in df.iterrows():
    slug = row["repo"].replace("/", "__")
    rp = Path(repos_dir) / slug
    subprocess.run(["git", "checkout", "-f", row["base_commit"]], cwd=rp,
                   check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, check=True, capture_output=True)
    shutil.rmtree(rp / ".roust", ignore_errors=True)
    gold = set(gold_files(row["patch"]))
    q = row["problem_statement"]
    base = ranked_files(rp, q) or []
    v2 = ranked_files(rp, q, ("--trace-formats-v2",)) or []

    def rank(files):
        for i, f in enumerate(files):
            if f in gold:
                return i + 1
        return None

    frames = fired[row["instance_id"]]
    frame_is_gold = [f for f in frames if f in gold]
    print(json.dumps({
        "instance_id": row["instance_id"],
        "gold": sorted(gold),
        "frames_fired": frames,
        "frames_that_are_gold": frame_is_gold,
        "gold_rank_base": rank(base),
        "gold_rank_v2": rank(v2),
        "n_files_base": len(base),
        "n_files_v2": len(v2),
    }), flush=True)
