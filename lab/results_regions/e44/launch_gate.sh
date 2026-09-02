#!/bin/bash
# E44 Python dual gate for --ppr-budget at the SHIPPED operating point, on top
# of --symbol-graph so the comparison is against E37's lite_sg / ver_sg arms
# (300 / 407, both Python-neutral on FILE). PPR does not change the file set,
# so FILE must match those arms instance-for-instance; the gate is about
# FUNCTION / LINE / fraction on Python -- the depth column.
set -uo pipefail
LAM=${1:?usage: launch_gate.sh <lambda>}
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
$PY "$R/parity/region_eval2.py" --repos-dir $R/lab/swebench_repos_e20b --symbol-graph --ppr-budget "$LAM" \
    --report "$OUT/lite_ppr.jsonl" > "$OUT/lite_ppr.log" 2>&1 & sleep 8
$PY "$R/parity/region_eval_verified.py" --repos-dir $R/lab/ws3a_repos/repos_ver_v2 --symbol-graph --ppr-budget "$LAM" \
    --report "$OUT/ver_ppr.jsonl" > "$OUT/ver_ppr.log" 2>&1 &
wait; echo E44_GATE_DONE
