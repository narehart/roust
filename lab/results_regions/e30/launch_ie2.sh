#!/bin/bash
# E32 import-edges-v2 on exactly the three slices whose import graph is EMPTY
# today (Java, C, C++). Evidence they are the right three: the second hop --
# which can only walk existing edges -- moved jsts +10.14, rust +5.71, go
# +4.90 and these three by exactly 0.00.
# Runs from the MAIN checkout (binary a36699f) so the e30-seats worktree
# binary is left alone. One slice per clone dir.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
BASE=$R/lab/results_regions/e30
INST=$R/lab/results_regions/e29/instances
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; parquet=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --instances "$INST/${slice}.txt" --max-additions 128 --import-edges-v2 \
      --report "$BASE/arms/${slice}_ie2c128.jsonl" > "$BASE/arms/${slice}_ie2c128.log" 2>&1
  echo "ARM_DONE ${slice}_ie2c128 rc=$? $(date +%H:%M:%S)"
}
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/ws3b_repos/c_base    & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_base  &
wait
echo E32_IE2_DONE
