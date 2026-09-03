#!/bin/bash
# E34 seed-count probe on the three slices E33 proved SATURATED under maximum
# candidate generation (Java 22.50, C++ 29.09, Rust 33.33 -- max generation
# added exactly nothing). Everything is expanded outward from the BM25 seeds,
# so if the residue is upstream of the graph, more seeds is the lever that
# moves it. Held at cap 128 + 2hop + ie2 so any newly seeded subgraph has room
# to be generated AND admitted; k_lex 10 -> 30.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
BASE=$R/lab/results_regions/e30
INST=$R/lab/results_regions/e29/instances
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; parquet=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --instances "$INST/${slice}.txt" --max-additions 128 --import-hops 2 \
      --import-edges-v2 --k-lex 50 \
      --report "$BASE/arms/${slice}_k50.jsonl" > "$BASE/arms/${slice}_k50.log" 2>&1
  echo "ARM_DONE ${slice}_k50 rc=$? $(date +%H:%M:%S)"
}
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base & sleep 8
run rust $R/lab/ws3a_rust.parquet $R/lab/ws3a_repos/rust_base & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_base  &
wait
echo E34_K50_DONE
