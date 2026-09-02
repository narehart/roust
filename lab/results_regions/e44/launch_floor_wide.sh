#!/bin/bash
# E45b: replicate the floor-0.15 lead (Rust FUNCTION 3G/0L, p=.25) on the two
# largest slices, where a real effect of that size becomes measurable.
# sg + cap 32, budget 8192; FILE must equal each slice's E37 sg32 arm.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { slice=$1; pq=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$pq" --repos-dir "$dir" \
      --symbol-graph --max-additions 32 --pack-floor 0.15 \
      --report "$OUT/${slice}_fl15.jsonl" > "$OUT/${slice}_fl15.log" 2>&1
  echo "ARM_DONE ${slice}_fl15 rc=$? $(date +%H:%M:%S)"; }
run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_v2   & sleep 8
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_private &
wait; echo E45B_DONE
