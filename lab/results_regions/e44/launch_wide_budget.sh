#!/bin/bash
# E46 wide: sg + cap 32 at the depth-neutral budget B found on Rust, on every
# other slice. FILE is budget-invariant (E29), so each arm's FILE must equal
# its E37 sg32 arm instance-for-instance; the question is whether FUNCTION/
# LINE return to shipped at this B on each language, and the token premium.
# Baselines: E36/E37 *_base (shipped) and E37 *_sg32 (cap 32 @ 8192).
set -uo pipefail
B=${1:?usage: launch_wide_budget.sh <budget>}
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { slice=$1; pq=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$pq" --repos-dir "$dir" \
      --symbol-graph --max-additions 32 --budget "$B" \
      --report "$OUT/${slice}_b${B}.jsonl" > "$OUT/${slice}_b${B}.log" 2>&1
  echo "ARM_DONE ${slice}_b${B} rc=$? $(date +%H:%M:%S)"; }
run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_v2    & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_v2   & sleep 8
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_v2  & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/e26_repos/c_ext     & sleep 8
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_private  &
wait; echo E46_WIDE_DONE
