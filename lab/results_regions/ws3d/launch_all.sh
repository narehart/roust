#!/bin/bash
# WS3d arm launcher (campaign #56 round WS3d): 10 detached arms, 10s stagger.
# ALL arms run the pinned BRANCH worktree (82c8d2f) harness+binary -- base
# arms on defaults (gate A proves defaults == main e41c972 byte-identically
# on the 17-instance mixed pool), guard arms add --displacement-guard.
# Private repo dirs per arm (issue #41), reusing the ws3a/ws3b round dirs
# (idle since those rounds closed). DO NOT run concurrently with
# lab/ws3d_identity_gate.py (shares mswe_repos_e23 + ws3a/ws3b dirs).
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/ws3d-displacement-guard
R=$P/lab/results_regions/ws3d

launch() { name=$1; shift
  nohup "$@" > "$R/$name.log" 2>&1 &
  echo "launched $name pid=$!"
  sleep 10
}

UV="uv run --no-project --with pandas --with pyarrow python"

# --- primary gate: jsts 580 + java 128 + rust 239, base vs guard ---
launch mswe_jsts_base $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/mswe_jsts.parquet --repos-dir $P/lab/mswe_repos_e23 \
  --shard 1/1 --report $R/mswe_jsts_ws3d_base.jsonl
launch mswe_jsts_guard $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/mswe_jsts.parquet --repos-dir $P/lab/mswe_repos_private \
  --shard 1/1 --displacement-guard --report $R/mswe_jsts_ws3d_guard.jsonl
launch mswe_java_base $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3b_java.parquet --repos-dir $P/lab/ws3b_repos/java_base \
  --shard 1/1 --report $R/mswe_java_ws3d_base.jsonl
launch mswe_java_guard $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3b_java.parquet --repos-dir $P/lab/ws3b_repos/java_v2 \
  --shard 1/1 --displacement-guard --report $R/mswe_java_ws3d_guard.jsonl
launch mswe_rust_base $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3a_rust.parquet --repos-dir $P/lab/ws3a_repos/rust_base \
  --shard 1/1 --report $R/mswe_rust_ws3d_base.jsonl
launch mswe_rust_guard $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3a_rust.parquet --repos-dir $P/lab/ws3a_repos/rust_v2 \
  --shard 1/1 --displacement-guard --report $R/mswe_rust_ws3d_guard.jsonl

# --- Python hold arms ---
launch lite300_base $UV $WB/parity/region_eval2.py \
  --repos-dir $P/lab/ws3a_repos/repos_lite_base --report $R/lite300_ws3d_base.jsonl
launch lite300_guard $UV $WB/parity/region_eval2.py \
  --repos-dir $P/lab/ws3a_repos/repos_lite_v2 --displacement-guard \
  --report $R/lite300_ws3d_guard.jsonl
launch ver407_base $UV $WB/parity/region_eval_verified.py \
  --repos-dir $P/lab/ws3a_repos/repos_ver_base --report $R/ver407_ws3d_base.jsonl
launch ver407_guard $UV $WB/parity/region_eval_verified.py \
  --repos-dir $P/lab/ws3a_repos/repos_ver_v2 --displacement-guard \
  --report $R/ver407_ws3d_guard.jsonl

echo ALL_LAUNCHED
