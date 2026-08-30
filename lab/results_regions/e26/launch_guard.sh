#!/bin/bash
# E26 wave 2: --ext-v2 WITH the fixture guard (b0cf3a9), the three slices that
# have ext gold or measured displacement: jsts / java / c.
# rust and cpp are deliberately NOT re-run -- they have ZERO ext-v2 gold, their
# unguarded deltas were already ~zero, and the guard can only admit FEWER
# files, so it cannot move them away from the default they already match.
# Pinned worktree harness+binary at 11a8a2f (= the b0cf3a9 engine + parity-only
# commits). Repo dirs are FRESH copies of the *_base clones with .roust removed:
# the guard changes corpus membership WITHOUT re-keying the cache (CACHE_VERSION
# is still 4 and the key still ends ":e2"), so a guarded binary must never be
# pointed at a checkout an unguarded --ext-v2 run has cached.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e26-guard
R=$P/lab/results_regions/e26
UV="uv run --no-project --with pandas --with pyarrow python"

arm() { name=$1; parquet=$2; repos=$3
  nohup $UV $WB/parity/region_eval_full.py \
    --gold-parquet "$P/$parquet" --repos-dir "$P/$repos" \
    --shard 1/1 --ext-v2 --report "$R/$name.jsonl" > "$R/$name.log" 2>&1 &
  echo "launched $name pid=$!"
  sleep 10
}

arm jsts_guard lab/mswe_jsts.parquet lab/e26_repos/jsts_guard
arm java_guard lab/ws3b_java.parquet lab/e26_repos/java_guard
arm c_guard    lab/mswe_c.parquet    lab/e26_repos/c_guard
echo E26_GUARD_LAUNCHED
