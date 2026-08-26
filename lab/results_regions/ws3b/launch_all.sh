#!/bin/bash
# WS3b arm launcher (campaign #56 round WS3b): 10 detached arms, 10s stagger.
# ALL arms run the pinned BRANCH worktree (0c0fc79) harness+binary -- base
# arms on defaults (gate A proves defaults == main de96114 byte-identically
# on thirdparty-free trees), v2 arms add --trace-formats-v2. Private repo
# dirs per arm (issue #41); cpp/c base arms are the fresh thirdparty-fix
# baselines (no v2 arm: census shows zero c/cpp trace-bearing instances).
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/ws3b-trace-formats
R=$P/lab/results_regions/ws3b

launch() { name=$1; shift
  nohup "$@" > "$R/$name.log" 2>&1 &
  echo "launched $name pid=$!"
  sleep 10
}

UV="uv run --no-project --with pandas --with pyarrow python"

# --- primary gate: java 128 + rust 239, base vs v2 ---
launch mswe_java_base $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3b_java.parquet --repos-dir $P/lab/ws3b_repos/java_base \
  --shard 1/1 --report $R/mswe_java_ws3b_base.jsonl
launch mswe_java_v2 $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3b_java.parquet --repos-dir $P/lab/ws3b_repos/java_v2 \
  --shard 1/1 --trace-formats-v2 --report $R/mswe_java_ws3b_v2.jsonl
launch mswe_rust_base $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3a_rust.parquet --repos-dir $P/lab/ws3a_repos/rust_base \
  --shard 1/1 --report $R/mswe_rust_ws3b_base.jsonl
launch mswe_rust_v2 $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3a_rust.parquet --repos-dir $P/lab/ws3a_repos/rust_v2 \
  --shard 1/1 --trace-formats-v2 --report $R/mswe_rust_ws3b_v2.jsonl

# --- fresh thirdparty-fix baselines (defaults; compare vs WS3a/WS2 refs) ---
launch mswe_cpp_base $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/mswe_cpp.parquet --repos-dir $P/lab/ws3a_repos/cpp_base \
  --shard 1/1 --report $R/mswe_cpp_ws3b_base.jsonl
launch mswe_c_base $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/mswe_c.parquet --repos-dir $P/lab/ws3b_repos/c_base \
  --shard 1/1 --report $R/mswe_c_ws3b_base.jsonl

# --- go/jsts targeted micro-arms (census: trace incidence too low for
#     full arms -- 6/430 go, 6/580 jsts; these give frame-fire evidence) ---
launch mswe_go_micro_base $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3b_go_micro.parquet --repos-dir $P/lab/ws3b_repos/go_base \
  --shard 1/1 --report $R/mswe_go_micro_ws3b_base.jsonl
launch mswe_go_micro_v2 $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3b_go_micro.parquet --repos-dir $P/lab/ws3b_repos/go_v2 \
  --shard 1/1 --trace-formats-v2 --report $R/mswe_go_micro_ws3b_v2.jsonl
launch mswe_jsts_micro_base $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3b_jsts_micro.parquet --repos-dir $P/lab/ws3b_repos/jsts_base \
  --shard 1/1 --report $R/mswe_jsts_micro_ws3b_base.jsonl
launch mswe_jsts_micro_v2 $UV $WB/parity/region_eval_full.py \
  --gold-parquet $P/lab/ws3b_jsts_micro.parquet --repos-dir $P/lab/ws3b_repos/jsts_v2 \
  --shard 1/1 --trace-formats-v2 --report $R/mswe_jsts_micro_ws3b_v2.jsonl

echo ALL_LAUNCHED
