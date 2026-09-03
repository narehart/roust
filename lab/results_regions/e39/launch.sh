#!/bin/bash
# E39: index the non-source gold classes, measured SEPARATELY because they
# differ in real-world value. Non-source share of gold: Python 0.2%, Java
# 25.3%, JS/TS 28.7% -- SWE-bench Verified was curated to pure source changes,
# Multi-SWE-bench was not, and Java's ceiling (57.03%) sits BELOW the 63.64
# bar purely because of it.
#   *_bf = --build-files      (genuinely useful to return)
#   *_cl = + --changelog-files (benchmark artifact; must not adopt silently)
# On top of the best sane config found so far: symbol-graph + cap 32.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e39; mkdir -p "$OUT/arms"
PY="uv run --no-project --with pandas --with pyarrow python"
SG="--symbol-graph --max-additions 32"
run() {
  slice=$1; parquet=$2; dir=$3; tag=$4; extra=$5
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      $SG $extra --report "$OUT/arms/${slice}_${tag}.jsonl" > "$OUT/arms/${slice}_${tag}.log" 2>&1
  echo "ARM_DONE ${slice}_${tag} rc=$? $(date +%H:%M:%S)"
}
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base bf "--build-files"                    & sleep 8
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_v2   cl "--build-files --changelog-files"  & sleep 8
run rust $R/lab/ws3a_rust.parquet $R/lab/ws3a_repos/rust_base bf "--build-files"                    & sleep 8
run rust $R/lab/ws3a_rust.parquet $R/lab/ws3a_repos/rust_v2   cl "--build-files --changelog-files"  & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_base  cl "--build-files --changelog-files"  &
wait
echo E39_DONE
