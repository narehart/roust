#!/bin/bash
# E37: the language-agnostic symbol-reference graph (Aider repo-map relation:
# file A references a rare symbol that file B defines). No per-language import
# syntax at all -- it reads the def index and term index the engine already
# builds and caches, so it works the same in every language it can parse and
# would subsume the per-language import parsers rather than adding an eighth.
#
# FULL slices at the SHIPPED operating point. Baselines were measured on dir A
# in E36 (java 49.22, c 51.56, cpp 65.89), so these arms take dir B and no two
# live arms share a clone dir (issue #41).
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e37; mkdir -p "$OUT/arms"
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; parquet=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --symbol-graph --report "$OUT/arms/${slice}_sg.jsonl" > "$OUT/arms/${slice}_sg.log" 2>&1
  echo "ARM_DONE ${slice}_sg rc=$? $(date +%H:%M:%S)"
}
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_v2  & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/e26_repos/c_ext     & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_v2   &
wait
echo E37_SG_DONE
