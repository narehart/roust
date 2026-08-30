#!/bin/bash
# E27 gate: --cochange-seats {2,3,4} at --cochange-seat-min 2, every slice,
# against FRESH same-binary default arms.
#
# Why fresh defaults everywhere instead of reusing E25's `_def` arms: E25 ran
# at abb96af, and ca15227 (E26's .rb/.pony adoption) has since MOVED the
# default engine. That invalidates the pairing on c and java for certain, and
# leaves jsts/go/rust/cpp resting on a census argument rather than a
# measurement. Default arms are the cheap half of this round, so every slice
# gets its own same-binary default side and the E25 numbers become a drift
# audit instead of a load-bearing baseline.
#
# ONE pinned binary for every arm: roust 0.3.2 (d5263f6, clean), built once in
# the e27-seats worktree and never rebuilt while these run. d5263f6 =
# 6e28c76 + harness passthrough + an env-gated seat trace, proven
# payload-identical to 6e28c76 on 8/8 repos at defaults AND at
# --cochange-seats 1 (scratchpad/cmp_payload.py).
#
# Private repo dir per CONCURRENT arm (issue #41). 16 chains run at once, two
# arms each, sequential within a chain, so no two live arms share a clone dir.
# Bash, not zsh.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e27-seats
R=$P/lab/results_regions/e27
UV="uv run --no-project --with pandas --with pyarrow python"
SEAT_MIN=2
mkdir -p "$R"

# One arm. Clears the clone dir's caches first so every corpus is cold and no
# arm can inherit another's index.
run_arm() {
  local name=$1 script=$2 parquet=$3 repos=$4 seats=$5
  find "$P/$repos" -maxdepth 2 -name .roust -type d -exec rm -rf {} + 2>/dev/null
  # macOS ships bash 3.2, where "${arr[@]}" on an EMPTY array trips `set -u`.
  # So the seat flags are carried as a plain word-split string: a default arm
  # sets it empty and passes no flag at all, which is the point -- its argv
  # then matches every pre-E27 default arm's byte for byte.
  local extra=""
  if [ "$seats" -gt 0 ]; then
    extra="--cochange-seats $seats --cochange-seat-min $SEAT_MIN"
  fi
  export ROUST_E27_SEAT_TRACE="$R/trace_$name.jsonl"
  rm -f "$ROUST_E27_SEAT_TRACE"
  if [ "$script" = "full" ]; then
    $UV "$WB/parity/region_eval_full.py" \
      --gold-parquet "$P/$parquet" --repos-dir "$P/$repos" \
      --shard 1/1 --report "$R/$name.jsonl" $extra >> "$R/$name.log" 2>&1
  elif [ "$script" = "lite" ]; then
    $UV "$WB/parity/region_eval2.py" \
      --repos-dir "$P/$repos" --report "$R/$name.jsonl" $extra >> "$R/$name.log" 2>&1
  else
    $UV "$WB/parity/region_eval_verified.py" \
      --repos-dir "$P/$repos" --report "$R/$name.jsonl" $extra >> "$R/$name.log" 2>&1
  fi
  echo "ARM_DONE $name exit=$?" >> "$R/progress.txt"
  unset ROUST_E27_SEAT_TRACE
}

# A chain of two arms sharing one clone dir, run sequentially in background.
chain() {
  local slice=$1 script=$2 parquet=$3 repos=$4 a=$5 b=$6
  (
    run_arm "${slice}_${a}" "$script" "$parquet" "$repos" "${a#s}"
    run_arm "${slice}_${b}" "$script" "$parquet" "$repos" "${b#s}"
    echo "CHAIN_DONE $slice/$repos" >> "$R/progress.txt"
  ) &
  echo "launched chain $slice [$a,$b] on $repos pid=$!"
  sleep 10
}

# `s0` names the default arm: run_arm forwards no seat flags at 0, so its argv
# is byte-identical to every pre-E27 default arm's.
chain jsts full lab/mswe_jsts.parquet  lab/mswe_repos_e23              s0 s3
chain jsts full lab/mswe_jsts.parquet  lab/mswe_repos_private          s2 s4
chain go   full lab/mswe_go.parquet    lab/ws3b_repos/go_base          s0 s3
chain go   full lab/mswe_go.parquet    lab/ws3b_repos/go_v2            s2 s4
chain rust full lab/ws3a_rust.parquet  lab/ws3a_repos/rust_base        s0 s3
chain rust full lab/ws3a_rust.parquet  lab/ws3a_repos/rust_v2          s2 s4
chain cpp  full lab/mswe_cpp.parquet   lab/ws3a_repos/cpp_base         s0 s3
chain cpp  full lab/mswe_cpp.parquet   lab/ws3a_repos/cpp_v2           s2 s4
chain java full lab/ws3b_java.parquet  lab/ws3b_repos/java_base        s0 s3
chain java full lab/ws3b_java.parquet  lab/ws3b_repos/java_v2          s2 s4
chain c    full lab/mswe_c.parquet     lab/ws3b_repos/c_base           s0 s3
chain c    full lab/mswe_c.parquet     lab/e26_repos/c_ext             s2 s4
chain lite lite -                      lab/ws3a_repos/repos_lite_base  s0 s3
chain lite lite -                      lab/ws3a_repos/repos_lite_v2    s2 s4
chain ver  ver  -                      lab/ws3a_repos/repos_ver_base   s0 s3
chain ver  ver  -                      lab/ws3a_repos/repos_ver_v2     s2 s4

wait
echo E27_ALL_ARMS_DONE >> "$R/progress.txt"
echo E27_ALL_ARMS_DONE
