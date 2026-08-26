#!/bin/bash
# WS3a arm launcher (campaign #56 round WS3a): 10 detached arms, 10s stagger.
# Baseline arms run the pinned MAIN worktree (3cb92d9) binary+harness with
# defaults; v2 arms run the pinned BRANCH worktree (499ec29) with
# --impl-prior-v2. Every arm gets a PRIVATE repos dir (issue #41).
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WM=/Users/nicholasarehart/programming-projects/bgrep-worktrees/ws3a-main-baseline
WB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/ws3a-impl-prior
R=$P/lab/results_regions/ws3a

launch() { name=$1; shift
  nohup "$@" > "$R/$name.log" 2>&1 &
  echo "launched $name pid=$!"
  sleep 10
}

UV="uv run --no-project --with pandas --with pyarrow python"

# --- MSWE arms (primary gate) ---
launch mswe_jsts_base $UV $WM/parity/region_eval_full.py \
  --gold-parquet $P/lab/mswe_jsts.parquet --repos-dir $P/lab/mswe_repos_e23 \
  --shard 1/1 --report $R/mswe_jsts_ws3a_base.jsonl
launch mswe_jsts_v2 $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/mswe_jsts.parquet --repos-dir $P/lab/mswe_repos_private \
  --shard 1/1 --impl-prior-v2 --report $R/mswe_jsts_ws3a_v2.jsonl
launch mswe_cpp_base $UV $WM/parity/region_eval_full.py \
  --gold-parquet $P/lab/mswe_cpp.parquet --repos-dir $P/lab/ws3a_repos/cpp_base \
  --shard 1/1 --report $R/mswe_cpp_ws3a_base.jsonl
launch mswe_cpp_v2 $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/mswe_cpp.parquet --repos-dir $P/lab/ws3a_repos/cpp_v2 \
  --shard 1/1 --impl-prior-v2 --report $R/mswe_cpp_ws3a_v2.jsonl
launch mswe_rust_base $UV $WM/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3a_rust.parquet --repos-dir $P/lab/ws3a_repos/rust_base \
  --shard 1/1 --report $R/mswe_rust_ws3a_base.jsonl
launch mswe_rust_v2 $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3a_rust.parquet --repos-dir $P/lab/ws3a_repos/rust_v2 \
  --shard 1/1 --impl-prior-v2 --report $R/mswe_rust_ws3a_v2.jsonl

# --- Python invariance arms ---
launch lite300_base $UV $WM/parity/region_eval2.py \
  --repos-dir $P/lab/ws3a_repos/repos_lite_base --report $R/lite300_ws3a_base.jsonl
launch lite300_v2 $UV $WB/parity/region_eval2.py \
  --repos-dir $P/lab/ws3a_repos/repos_lite_v2 --impl-prior-v2 \
  --report $R/lite300_ws3a_v2.jsonl
launch ver407_base $UV $WM/parity/region_eval_verified.py \
  --repos-dir $P/lab/ws3a_repos/repos_ver_base --report $R/ver407_ws3a_base.jsonl
launch ver407_v2 $UV $WB/parity/region_eval_verified.py \
  --repos-dir $P/lab/ws3a_repos/repos_ver_v2 --impl-prior-v2 \
  --report $R/ver407_ws3a_v2.jsonl

echo ALL_LAUNCHED
