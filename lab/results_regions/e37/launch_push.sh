#!/bin/bash
# E38: push every language toward the fixed 63.64 bar on FULL slices.
# Standing at shipped defaults: cpp 65.89 (clears), rust 60.25, c 51.56,
# java 49.22; go and jsts never measured at full-slice scale at all.
# Best mechanism so far = symbol graph + cap 32; java/c additionally get the
# import edges + 2 hops, which is where their combo gains came from.
# One arm per clone dir (issue #41).
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e37/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; parquet=$2; dir=$3; tag=$4; extra=$5
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      $extra --report "$OUT/${slice}_${tag}.jsonl" > "$OUT/${slice}_${tag}.log" 2>&1
  echo "ARM_DONE ${slice}_${tag} rc=$? $(date +%H:%M:%S)"
}
run rust $R/lab/ws3a_rust.parquet $R/lab/ws3a_repos/rust_base sg32 "--symbol-graph --max-additions 32" & sleep 8
run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_base   base ""                                   & sleep 8
run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_v2     sg32 "--symbol-graph --max-additions 32"  & sleep 8
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_v2   all  "--symbol-graph --import-edges-v2 --import-hops 2 --max-additions 32" & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/e26_repos/c_ext      all  "--symbol-graph --import-edges-v2 --import-hops 2 --max-additions 32" &
wait
echo E38_PUSH_DONE
