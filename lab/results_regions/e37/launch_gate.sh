#!/bin/bash
# E37 Python dual gate for --symbol-graph, at the SHIPPED operating point.
# This gate is essential in a way E36's was not: --import-edges-v2 only fires
# on .java/.c/.cpp/.h and proved Python-identical, but the symbol graph is
# language-agnostic BY CONSTRUCTION and therefore acts on Python too. Baselines
# already measured in E36 (lite 92.33/.52728, ver 92.38/.47635, both matching
# the published references), so only the treatment arms run here.
# Rust full-slice base+treatment runs alongside on its own clone dirs.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e37/arms
PY="uv run --no-project --with pandas --with pyarrow python"
$PY "$R/parity/region_eval2.py" --repos-dir $R/lab/swebench_repos_e20b --symbol-graph \
    --report "$OUT/lite_sg.jsonl" > "$OUT/lite_sg.log" 2>&1 & sleep 8
$PY "$R/parity/region_eval_verified.py" --repos-dir $R/lab/ws3a_repos/repos_ver_v2 --symbol-graph \
    --report "$OUT/ver_sg.jsonl" > "$OUT/ver_sg.log" 2>&1 & sleep 8
$PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/ws3a_rust.parquet \
    --repos-dir $R/lab/ws3a_repos/rust_base \
    --report "$OUT/rust_base.jsonl" > "$OUT/rust_base.log" 2>&1 & sleep 8
$PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/ws3a_rust.parquet \
    --repos-dir $R/lab/ws3a_repos/rust_v2 --symbol-graph \
    --report "$OUT/rust_sg.jsonl" > "$OUT/rust_sg.log" 2>&1 &
wait
echo E37_GATE_DONE
