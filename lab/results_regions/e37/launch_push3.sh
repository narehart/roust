#!/bin/bash
# E38c: the three slices still under a full-slice 63.64 -- c 56.25, jsts 52.07,
# java 51.56. C already reached 67.19 at cap128+k30 but with a 75% line-depth
# collapse, so its arm adds budget 16384: E29 showed the FILE set is budget-
# invariant while depth is fully budget-recoverable, so this should keep the
# breadth and buy the depth back. jsts and java get the same maxed generation.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e37/arms
PY="uv run --no-project --with pandas --with pyarrow python"
MAX="--symbol-graph --import-edges-v2 --import-hops 2 --max-additions 128 --k-lex 30"
run() {
  slice=$1; parquet=$2; dir=$3; tag=$4; extra=$5
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      $extra --report "$OUT/${slice}_${tag}.jsonl" > "$OUT/${slice}_${tag}.log" 2>&1
  echo "ARM_DONE ${slice}_${tag} rc=$? $(date +%H:%M:%S)"
}
run c    $R/lab/mswe_c.parquet    $R/lab/e26_repos/c_ext      maxb "$MAX --budget 16384" & sleep 8
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_e23       maxb "$MAX --budget 16384" & sleep 8
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_v2   maxb "$MAX --budget 16384" &
wait
echo E38C_DONE
