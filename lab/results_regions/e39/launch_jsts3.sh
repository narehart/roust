#!/bin/bash
# E40c: last genuine lever for the last genuinely-reachable slice. jsts is
# 59.13 (cap64 + budget 16384), 4.51 under 63.64, ceiling 76.68. The seed
# count is the one lever never applied here and it gave rust +3.81 and cpp
# +3.64. Cap stays at 64 -- cap 128 on this slice is what made the previous
# arm non-terminating. No changelog indexing: this must be a genuine result.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e39/arms
PY="uv run --no-project --with pandas --with pyarrow python"
$PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/mswe_jsts.parquet \
    --repos-dir $R/lab/mswe_repos_e23 --symbol-graph --import-hops 2 \
    --max-additions 64 --budget 16384 --k-lex 30 \
    --report "$OUT/jsts_k30.jsonl" > "$OUT/jsts_k30.log" 2>&1
echo "ARM_DONE jsts_k30 rc=$? $(date +%H:%M:%S)"
echo E40C_DONE
