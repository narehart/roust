#!/bin/bash
# E44 wide: PPR budget concentration on every remaining slice at the best
# lambda from the Rust smoke ($1), same fixed cap 32 / budget 8192 as the
# E37 sg32 baselines, so FILE is identical by construction and the whole
# effect is depth. One arm per clone dir (issue #41).
set -uo pipefail
LAM=${1:?usage: launch_wide.sh <lambda>}
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { slice=$1; pq=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$pq" --repos-dir "$dir" \
      --symbol-graph --max-additions 32 --ppr-budget "$LAM" \
      --report "$OUT/${slice}_ppr.jsonl" > "$OUT/${slice}_ppr.log" 2>&1
  echo "ARM_DONE ${slice}_ppr rc=$? $(date +%H:%M:%S)"; }
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_e23      & sleep 8
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_v2  & sleep 8
run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_v2    & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_v2   & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/e26_repos/c_ext     &
wait; echo E44_WIDE_DONE
