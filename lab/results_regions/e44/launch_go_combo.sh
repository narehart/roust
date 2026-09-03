#!/bin/bash
# E46c: do floor 0.15 and budget 9216 COMPOSE on Go? They act on different
# things (how the budget is split across returned files vs how much budget
# there is), so their depth gains should stack. sg + cap 32; FILE must equal
# go_sg32 (70.79). go_v2 is free (the floor arm on it has finished).
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
$PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/mswe_go.parquet --repos-dir $R/lab/ws3b_repos/go_v2 \
    --symbol-graph --max-additions 32 --pack-floor 0.15 --budget 9216 \
    --report "$OUT/go_fl15b9216.jsonl" > "$OUT/go_fl15b9216.log" 2>&1
echo "ARM_DONE go_fl15b9216 rc=$? $(date +%H:%M:%S)"; echo E46C_DONE
