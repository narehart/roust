#!/bin/bash
# E36 adoption round for --import-edges-v2, at the SHIPPED operating point
# (cap 16, budget 8192) -- not the ceiling config. Baseline and treatment run
# on the SAME pinned binary, so the comparison carries no cross-commit drift
# (the published per-language references were measured on older engines).
# FULL slices, not the >=3-gold-file strata: adoption has to hold everywhere.
# One arm per clone dir (issue #41).
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
BASE=$R/lab/results_regions/e36
OUT=$BASE/arms; mkdir -p "$OUT"
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; parquet=$2; dir=$3; tag=$4; extra=$5
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      $extra --report "$OUT/${slice}_${tag}.jsonl" > "$OUT/${slice}_${tag}.log" 2>&1
  echo "ARM_DONE ${slice}_${tag} rc=$? $(date +%H:%M:%S)"
}
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base base ""                   & sleep 8
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_v2   ie2  "--import-edges-v2"  & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/ws3b_repos/c_base    base ""                   & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/e26_repos/c_ext      ie2  "--import-edges-v2"  & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_base  base ""                   & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_v2    ie2  "--import-edges-v2"  &
wait
echo E36_LANG_DONE
