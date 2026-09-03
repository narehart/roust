#!/bin/bash
# E46 wide, last two slices, on the clone dirs NOT held by the floor arms
# (go_base, mswe_repos_e23). Same config: sg + cap 32 @ 9216.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { slice=$1; pq=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$pq" --repos-dir "$dir" \
      --symbol-graph --max-additions 32 --budget 9216 \
      --report "$OUT/${slice}_b9216.jsonl" > "$OUT/${slice}_b9216.log" 2>&1
  echo "ARM_DONE ${slice}_b9216 rc=$? $(date +%H:%M:%S)"; }
run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_base & sleep 8
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_e23     &
wait; echo E46_GOJSTS_DONE
