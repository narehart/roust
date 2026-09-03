#!/bin/bash
# E45c: Python dual gate for --pack-floor 0.15 ALONE at the SHIPPED operating
# point (cap 16, budget 8192, no symbol graph). This is the adoption gate:
# the floor is budget-neutral and identity-gated (FILE cannot change), so if
# it does not regress Lite/Verified FUNCTION/LINE it can become a DEFAULT.
# Baselines: E36 lite_base (92.33 / 54.67 / 44.00 / .52728) and ver_base
# (92.38 / 47.17 / 35.14 / .47635), both equal to the published references.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
$PY "$R/parity/region_eval2.py" --repos-dir $R/lab/swebench_repos_e20a --pack-floor 0.15 \
    --report "$OUT/lite_fl15.jsonl" > "$OUT/lite_fl15.log" 2>&1 & sleep 8
$PY "$R/parity/region_eval_verified.py" --repos-dir $R/lab/ws3a_repos/repos_ver_base --pack-floor 0.15 \
    --report "$OUT/ver_fl15.jsonl" > "$OUT/ver_fl15.log" 2>&1 &
wait; echo E45C_GATE_DONE
