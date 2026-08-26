#!/bin/bash
# E25 wave 1: default vs --shape-blocks paired arms, jsts/java/rust/c/cpp.
# ALL arms run the PINNED worktree harness+binary at abb96af (roust 0.3.2)
# so both members of every pair sit on one engine commit -- the committed
# ws2/ws3b baselines for c/cpp/go predate WS3c and cannot be paired against
# an abb96af shape arm. Private repo dir per arm (issue #41). Bash, not zsh.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e25-shape-blocks
R=$P/lab/results_regions/e25
UV="uv run --no-project --with pandas --with pyarrow python"

launch() { name=$1; shift
  nohup "$@" > "$R/$name.log" 2>&1 &
  echo "launched $name pid=$!"
  sleep 10
}

arm() { name=$1; parquet=$2; repos=$3; shift 3
  launch "$name" $UV $WB/parity/region_eval_full.py \
    --gold-parquet "$P/$parquet" --repos-dir "$P/$repos" \
    --shard 1/1 --report "$R/$name.jsonl" "$@"
}

arm jsts_def  lab/mswe_jsts.parquet lab/mswe_repos_e23
arm jsts_shape lab/mswe_jsts.parquet lab/mswe_repos_private --shape-blocks
arm java_def  lab/ws3b_java.parquet lab/ws3b_repos/java_base
arm java_shape lab/ws3b_java.parquet lab/ws3b_repos/java_v2 --shape-blocks
arm rust_def  lab/ws3a_rust.parquet lab/ws3a_repos/rust_base
arm rust_shape lab/ws3a_rust.parquet lab/ws3a_repos/rust_v2 --shape-blocks
arm c_def     lab/mswe_c.parquet lab/ws3b_repos/c_base
arm c_shape   lab/mswe_c.parquet lab/e25_repos/c_shape --shape-blocks
arm cpp_def   lab/mswe_cpp.parquet lab/ws3a_repos/cpp_base
arm cpp_shape lab/mswe_cpp.parquet lab/e25_repos/cpp_shape --shape-blocks

echo E25_WAVE1_LAUNCHED
