#!/bin/bash
# E25 wave 2: go default vs --shape-blocks, pinned abb96af harness+binary.
# Bash, not zsh -- $UV must word-split (the recurring launcher trap).
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e25-shape-blocks
R=$P/lab/results_regions/e25
UV="uv run --no-project --with pandas --with pyarrow python"

nohup $UV $WB/parity/region_eval_full.py --gold-parquet $P/lab/mswe_go.parquet \
  --repos-dir $P/lab/ws3b_repos/go_base --shard 1/1 \
  --report $R/go_def.jsonl > $R/go_def.log 2>&1 &
echo "go_def pid=$!"
sleep 10
nohup $UV $WB/parity/region_eval_full.py --gold-parquet $P/lab/mswe_go.parquet \
  --repos-dir $P/lab/ws3b_repos/go_v2 --shard 1/1 --shape-blocks \
  --report $R/go_shape.jsonl > $R/go_shape.log 2>&1 &
echo "go_shape pid=$!"
echo E25_GO_LAUNCHED
