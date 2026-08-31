#!/bin/bash
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e39/arms
PY="uv run --no-project --with pandas --with pyarrow python"
SG="--symbol-graph --max-additions 32 --build-files --changelog-files"
run() {
  slice=$1; parquet=$2; dir=$3; extra=$4
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      $SG $extra --report "$OUT/${slice}_cl.jsonl" > "$OUT/${slice}_cl.log" 2>&1
  echo "ARM_DONE ${slice}_cl rc=$? $(date +%H:%M:%S)"
}
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_e23   ""                                       & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/ws3b_repos/c_base "--import-edges-v2 --import-hops 2"     & sleep 8
run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_base ""                                     &
wait
echo E39B_DONE
