#!/bin/bash
# E46 wide (subset): sg + cap 32 at budget B on the slices whose clone dirs
# are free right now (go_v2 / mswe_repos_private are held by the E45b floor
# arms). FILE must equal each slice's E37 sg32 arm; the question is depth.
set -uo pipefail
B=${1:?usage: <budget> <slice...>}; shift
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { slice=$1; pq=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$pq" --repos-dir "$dir" \
      --symbol-graph --max-additions 32 --budget "$B" \
      --report "$OUT/${slice}_b${B}.jsonl" > "$OUT/${slice}_b${B}.log" 2>&1
  echo "ARM_DONE ${slice}_b${B} rc=$? $(date +%H:%M:%S)"; }
for s in "$@"; do case "$s" in
  cpp)  run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_v2  & sleep 8 ;;
  java) run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_v2 & sleep 8 ;;
  c)    run c    $R/lab/mswe_c.parquet    $R/lab/e26_repos/c_ext    & sleep 8 ;;
  go)   run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_v2   & sleep 8 ;;
  jsts) run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_private & sleep 8 ;;
esac; done
wait; echo "E46_WIDE_DONE b=$B $*"
