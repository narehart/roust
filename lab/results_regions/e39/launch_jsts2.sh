#!/bin/bash
# E40b: JS/TS final push. Trajectory on genuine mechanisms is 46.38 -> 52.07
# -> 54.48 -> 59.13, with line depth ABOVE shipped at the wider budget. 4.51
# short of 63.64 against a 76.68 ceiling; the cap32->cap64 step gave +4.65, so
# cap 128 at budget 24576 is the next step on the same curve.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e39/arms
PY="uv run --no-project --with pandas --with pyarrow python"
$PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/mswe_jsts.parquet \
    --repos-dir $R/lab/mswe_repos_e23 --symbol-graph --import-hops 2 \
    --max-additions 128 --budget 24576 \
    --report "$OUT/jsts_h2c128b.jsonl" > "$OUT/jsts_h2c128b.log" 2>&1
echo "ARM_DONE jsts_h2c128b rc=$? $(date +%H:%M:%S)"
echo E40B_DONE
