#!/bin/bash
# WS3d reduced-grid launcher: jsts base + guard full arms only (see
# fixture_census.log -- java/rust are structurally inert, Lite/Verified
# covered by the 31-instance python_microgate). Bash, not zsh: $UV must
# word-split (the ws3b goldrank launcher anomaly).
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/ws3d-displacement-guard
R=$P/lab/results_regions/ws3d
UV="uv run --no-project --with pandas --with pyarrow python"

nohup $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/mswe_jsts.parquet --repos-dir $P/lab/mswe_repos_e23 \
  --shard 1/1 --report $R/mswe_jsts_ws3d_base.jsonl > $R/mswe_jsts_base.log 2>&1 &
echo "jsts_base pid=$!"
sleep 10
nohup $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/mswe_jsts.parquet --repos-dir $P/lab/mswe_repos_private \
  --shard 1/1 --displacement-guard --report $R/mswe_jsts_ws3d_guard.jsonl > $R/mswe_jsts_guard.log 2>&1 &
echo "jsts_guard pid=$!"
echo JSTS_LAUNCHED
