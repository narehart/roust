#!/bin/bash
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e41/arms
PY="uv run --no-project --with pandas --with pyarrow python"
$PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/mswe_c.parquet \
    --repos-dir $R/lab/e26_repos/c_ext --symbol-graph --import-edges-v2 --import-hops 2 \
    --max-additions 64 --budget 16384 --changelog-files --docs-data-files \
    --report "$OUT/c_mid.jsonl" > "$OUT/c_mid.log" 2>&1
echo "ARM_DONE c_mid rc=$? $(date +%H:%M:%S)"
echo E41C_DONE
