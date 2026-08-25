#!/bin/bash
# WS3a rigor check: prove no evaluated base_commit tree contains a
# `thirdparty` path component in the jsts/rust/Lite/Verified v2 arm repo
# sets (the working-tree scan only covers the last checkout). Any hit
# would mean the vendor-fix rebuild invalidates that arm too.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
cd $P
uv run --no-project --with pandas --with pyarrow python - <<'EOF'
import subprocess
from pathlib import Path
import pandas as pd

P = Path("/Users/nicholasarehart/programming-projects/bgrep")
sets = [
    ("jsts", P/"lab/mswe_jsts.parquet", P/"lab/mswe_repos_private"),
    ("rust", P/"lab/ws3a_rust.parquet", P/"lab/ws3a_repos/rust_v2"),
    ("lite", P/"lab/swebench_lite.parquet", P/"lab/ws3a_repos/repos_lite_v2"),
    ("ver", P/"lab/swebench_verified_heldout.parquet", P/"lab/ws3a_repos/repos_ver_v2"),
]
total_hits = 0
for name, pq, repos in sets:
    df = pd.read_parquet(pq)
    pairs = df[["repo", "base_commit"]].drop_duplicates()
    hits = 0
    n = 0
    for _, row in pairs.iterrows():
        rp = repos / row["repo"].replace("/", "__")
        if not rp.is_dir():
            print(f"{name}: MISSING repo {rp}")
            continue
        n += 1
        out = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", row["base_commit"]],
            cwd=rp, capture_output=True, text=True)
        for line in out.stdout.splitlines():
            low = line.lower()
            if low.startswith("thirdparty/") or "/thirdparty/" in low:
                hits += 1
                print(f"{name}: HIT {row['repo']}@{row['base_commit'][:10]}: {line}")
                break
    print(f"{name}: {n} unique base_commits checked, {hits} with thirdparty paths")
    total_hits += hits
print(f"TOTAL_HITS={total_hits}")
EOF
