#!/bin/bash
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
BASE=$R/lab/results_regions/e30
INST=$R/lab/results_regions/e29/instances
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; parquet=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --instances "$INST/${slice}.txt" --max-additions 500 --import-hops 2 \
      --import-edges-v2 --eligible-floor 0.02 \
      --report "$BASE/arms/${slice}_max.jsonl" > "$BASE/arms/${slice}_max.log" 2>&1
  echo "ARM_DONE ${slice}_max rc=$? $(date +%H:%M:%S)"
}
run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_base  & sleep 8
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_e23      &
wait
echo E33_MAX2_DONE
