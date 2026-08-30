#!/bin/bash
# E28 scoring. Uses agentless_metric_full.py (--repos-dir --ts-functions
# --lang-functions) for the six MSWE slices and the v4 / verified scorers for
# Python. NEVER lab/agentless_metric.py -- it ignores its CLI args.
# The AST walks are read-only `git show <base_commit>:<path>`, so they are
# commit-addressed and unaffected by a working tree's checked-out state; they
# still only run after every arm has exited.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
BASE=$R/lab/results_regions/e28
ARMS=$BASE/arms
MET=$BASE/metrics
mkdir -p "$MET"
PY="uv run --no-project --with pandas --with pyarrow --with scipy --with tree_sitter --with tree_sitter_javascript --with tree_sitter_typescript --with tree_sitter_java --with tree_sitter_go --with tree_sitter_rust --with tree_sitter_c --with tree_sitter_cpp python"

score_full() { # slice parquet reposdir n tag jsonl
  $PY $R/lab/agentless_metric_full.py --predictions "$6" --gold-parquet "$2" \
      --repos-dir "$3" --expect-n "$4" --ts-functions --lang-functions \
      --out "$MET/$5.json" > "$MET/$5.log" 2>&1
  echo "SCORED $5 rc=$?"
}

# ---- arms -----------------------------------------------------------------
for cap in 24 32; do
  score_full jsts $R/lab/mswe_jsts.parquet   $R/lab/mswe_repos_e23           580 "jsts_m$cap" "$ARMS/jsts_m$cap.jsonl" &
  sleep 3
  score_full java $R/lab/ws3b_java.parquet   $R/lab/ws3b_repos/java_base     128 "java_m$cap" "$ARMS/java_m$cap.jsonl" &
  sleep 3
  score_full go   $R/lab/mswe_go.parquet     $R/lab/ws3b_repos/go_base       428 "go_m$cap"   "$ARMS/go_m$cap.jsonl" &
  sleep 3
  score_full rust $R/lab/ws3a_rust.parquet   $R/lab/ws3a_repos/rust_base     239 "rust_m$cap" "$ARMS/rust_m$cap.jsonl" &
  sleep 3
  score_full c    $R/lab/mswe_c.parquet      $R/lab/ws3b_repos/c_base        128 "c_m$cap"    "$ARMS/c_m$cap.jsonl" &
  sleep 3
  score_full cpp  $R/lab/mswe_cpp.parquet    $R/lab/ws3a_repos/cpp_base      129 "cpp_m$cap"  "$ARMS/cpp_m$cap.jsonl" &
  sleep 3
  $PY $R/lab/agentless_metric_v4.py --predictions "$ARMS/lite_m$cap.jsonl" \
      --out "$MET/lite_m$cap.json" > "$MET/lite_m$cap.log" 2>&1 &
  sleep 3
  $PY $R/lab/agentless_metric_verified.py --predictions "$ARMS/ver_m$cap.jsonl" \
      --gold-parquet $R/lab/swebench_verified_heldout.parquet --expect-n 407 \
      --out "$MET/ver_m$cap.json" > "$MET/ver_m$cap.log" 2>&1 &
  sleep 3
done
wait
echo ALL_SCORING_DONE
