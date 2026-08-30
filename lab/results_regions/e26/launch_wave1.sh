#!/bin/bash
# E26 wave 1: --ext-v2 arms for the five slices whose repos actually contain
# a new extension (go census: 0 repos -> provably inert, no arm run).
# The DEFAULT arm is E25's `_def` at abb96af: the abb96af..5ebd6ab engine diff
# is flag-gated only (cache-key ":e2" marker + an `||` clause in
# code_suffix_allowed + the arg wiring), so with --ext-v2 off the engine is
# byte-identical and those defaults remain valid same-engine pairs.
# Pinned worktree harness+binary at fcb2562 (= 5ebd6ab engine + parity
# passthrough only). Private repo dir per arm (issue #41). Bash, not zsh.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e26-ext-coverage
R=$P/lab/results_regions/e26
UV="uv run --no-project --with pandas --with pyarrow python"

arm() { name=$1; parquet=$2; repos=$3; shift 3
  nohup $UV $WB/parity/region_eval_full.py \
    --gold-parquet "$P/$parquet" --repos-dir "$P/$repos" \
    --shard 1/1 --ext-v2 --report "$R/$name.jsonl" > "$R/$name.log" 2>&1 &
  echo "launched $name pid=$!"
  sleep 10
}

arm jsts_ext lab/mswe_jsts.parquet lab/mswe_repos_private
arm java_ext lab/ws3b_java.parquet lab/ws3b_repos/java_v2
arm rust_ext lab/ws3a_rust.parquet lab/ws3a_repos/rust_v2
arm c_ext    lab/mswe_c.parquet    lab/e26_repos/c_ext
arm cpp_ext  lab/mswe_cpp.parquet  lab/ws3a_repos/cpp_v2

echo E26_WAVE1_LAUNCHED
