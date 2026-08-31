#!/bin/bash
# E37b head-to-head, both mechanisms given the SAME room (cap 32):
#   * per-language import parsers : --import-edges-v2 --import-hops 2  (E36 combo)
#   * language-agnostic           : --symbol-graph
# Full slices, shipped budget. E36 combo reference: java 50.78, c 55.47.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e37/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; parquet=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --symbol-graph --max-additions 32 \
      --report "$OUT/${slice}_sg32.jsonl" > "$OUT/${slice}_sg32.log" 2>&1
  echo "ARM_DONE ${slice}_sg32 rc=$? $(date +%H:%M:%S)"
}
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/ws3b_repos/c_base    & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_base  &
wait
echo E37B_DONE
