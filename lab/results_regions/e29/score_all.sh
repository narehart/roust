#!/bin/bash
# E29 scoring. Uses agentless_metric_full.py (--repos-dir --ts-functions
# --lang-functions) for the six MSWE slices and agentless_metric_verified.py
# for Python Verified. NEVER lab/agentless_metric.py -- it ignores its CLI args.
#
# --expect-n is the size of each slice's >=3-gold-file stratum, not the slice
# size: every arm this round is restricted to that stratum by --instances, so
# a full-slice expect-n would fire a spurious count failure and, worse, a
# SHORT arm would pass unnoticed.
#
# The AST walks are read-only `git show <base_commit>:<path>`, so they are
# commit-addressed and unaffected by a working tree's checked-out state. They
# are still only run after every arm of every round has exited -- never score
# a clone dir a live arm is checking out.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
BASE=$R/lab/results_regions/e29
ARMS=$BASE/arms
MET=$BASE/metrics
mkdir -p "$MET"
PY="uv run --no-project --with pandas --with pyarrow --with scipy --with tree_sitter --with tree_sitter_javascript --with tree_sitter_typescript --with tree_sitter_java --with tree_sitter_go --with tree_sitter_rust --with tree_sitter_c --with tree_sitter_cpp python"

ARM_TAGS="a1_c16b8192 a2_c32b8192 a3_c32b16384 a4_c32b24576 a5_c16b24576"

score_full() { # slice parquet reposdir n tag jsonl
  $PY $R/lab/agentless_metric_full.py --predictions "$6" --gold-parquet "$2" \
      --repos-dir "$3" --expect-n "$4" --ts-functions --lang-functions \
      --out "$MET/$5.json" > "$MET/$5.log" 2>&1
  echo "SCORED $5 rc=$?"
}

for t in $ARM_TAGS; do
  score_full jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_e23       207 "jsts_$t" "$ARMS/jsts_$t.jsonl" &
  sleep 3
  score_full java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base  40 "java_$t" "$ARMS/java_$t.jsonl" &
  sleep 3
  score_full go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_base   143 "go_$t"   "$ARMS/go_$t.jsonl" &
  sleep 3
  score_full rust $R/lab/ws3a_rust.parquet $R/lab/ws3a_repos/rust_base 105 "rust_$t" "$ARMS/rust_$t.jsonl" &
  sleep 3
  score_full c    $R/lab/mswe_c.parquet    $R/lab/ws3b_repos/c_base     46 "c_$t"    "$ARMS/c_$t.jsonl" &
  sleep 3
  score_full cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_base   55 "cpp_$t"  "$ARMS/cpp_$t.jsonl" &
  sleep 3
  $PY $R/lab/agentless_metric_verified.py --predictions "$ARMS/ver_$t.jsonl" \
      --gold-parquet $R/lab/swebench_verified_heldout.parquet --expect-n 22 \
      --out "$MET/ver_$t.json" > "$MET/ver_$t.log" 2>&1 &
  sleep 3
  wait
done
echo ALL_SCORING_DONE
