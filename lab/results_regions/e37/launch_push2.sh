#!/bin/bash
# E38b: jsts has never been measured at full-slice scale; java and c are the
# two still short of 63.64 (-12.86 and -7.39), so they get more admission room
# (cap 128) and more BM25 seeds (k_lex 30) on top of everything else.
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
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_e23     base ""                                  & sleep 8
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_private sg32 "--symbol-graph --max-additions 32" & sleep 8
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base max "--symbol-graph --import-edges-v2 --import-hops 2 --max-additions 128 --k-lex 30" & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/ws3b_repos/c_base   max "--symbol-graph --import-edges-v2 --import-hops 2 --max-additions 128 --k-lex 30" &
wait
echo E38B_DONE
