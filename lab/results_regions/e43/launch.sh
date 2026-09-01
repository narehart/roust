#!/bin/bash
# E43: the Python dual gate that decides whether any of this can ship.
# --docs-data-files has NEVER been gated and is the most dilutive rule in the
# engine (up to +39% corpus). Python repos carry plenty of .md/.json/.yml, so
# this can move Lite/Verified even though no .py logic changed.
# Baselines from E36 on the same binary lineage: lite 92.33 / .52728,
# ver 92.38 / .47635 (both equal to the published references).
#   *_sg  = --symbol-graph alone            (already known FILE-neutral)
#   *_all = + --changelog-files --docs-data-files  (the untested part)
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e43; mkdir -p "$OUT/arms"
PY="uv run --no-project --with pandas --with pyarrow python"
$PY "$R/parity/region_eval2.py" --repos-dir $R/lab/swebench_repos_e20a \
    --symbol-graph --changelog-files --docs-data-files \
    --report "$OUT/arms/lite_all.jsonl" > "$OUT/arms/lite_all.log" 2>&1 & sleep 8
$PY "$R/parity/region_eval_verified.py" --repos-dir $R/lab/ws3a_repos/repos_ver_base \
    --symbol-graph --changelog-files --docs-data-files \
    --report "$OUT/arms/ver_all.jsonl" > "$OUT/arms/ver_all.log" 2>&1 &
wait
echo E43_DONE
