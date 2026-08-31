#!/bin/bash
# E38d: Java is the outlier -- 52.34 even with every generation lever maxed
# and the budget doubled, still 11.30 under a full-slice 63.64 while C cleared
# from a lower start. This probes its ceiling (cap 500, k_lex 50, budget
# 24576) to establish whether Java is reachable at ANY setting.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e37/arms
PY="uv run --no-project --with pandas --with pyarrow python"
$PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/ws3b_java.parquet \
    --repos-dir $R/lab/ws3b_repos/java_base \
    --symbol-graph --import-edges-v2 --import-hops 2 \
    --max-additions 500 --k-lex 50 --budget 24576 \
    --report "$OUT/java_ceiling.jsonl" > "$OUT/java_ceiling.log" 2>&1
echo "ARM_DONE java_ceiling rc=$? $(date +%H:%M:%S)"
echo E38D_DONE
