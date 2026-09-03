#!/bin/bash
# E47 Python dual gate at SHIPPED settings (cap 16, budget 8192, no symbol
# graph). At the shipped cap the bundle still carries ~30 files, so files at
# rank >= 16 exist and the stub fires -- this gate decides whether the tiered
# seat can be a default. Baselines: E36 lite_base / ver_base (= published).
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e47/arms
PY="uv run --no-project --with pandas --with pyarrow python"
$PY "$R/parity/region_eval2.py" --repos-dir $R/lab/swebench_repos_e20a --tail-seat-tokens 40 --tail-seat-after 16 \
    --report "$OUT/lite_ts40.jsonl" > "$OUT/lite_ts40.log" 2>&1 & sleep 8
$PY "$R/parity/region_eval_verified.py" --repos-dir $R/lab/ws3a_repos/repos_ver_base --tail-seat-tokens 40 --tail-seat-after 16 \
    --report "$OUT/ver_ts40.jsonl" > "$OUT/ver_ts40.log" 2>&1 &
wait
uv run --no-project --with scipy python $R/lab/results_regions/e44/compare.py $R/lab/results_regions/e36/arms/lite_base.jsonl $OUT/lite_ts40.jsonl "LITE shipped -> tail seat 40"
uv run --no-project --with scipy python $R/lab/results_regions/e44/compare.py $R/lab/results_regions/e36/arms/ver_base.jsonl $OUT/ver_ts40.jsonl "VERIFIED shipped -> tail seat 40"
M=$R/lab/results_regions/e44/metrics
uv run --no-project --with pandas --with pyarrow python $R/lab/agentless_metric_v4.py --predictions $OUT/lite_ts40.jsonl --out $M/lite_ts40.json > $M/lite_ts40.log 2>&1; echo "scored lite_ts40 rc=$?"
uv run --no-project --with pandas --with pyarrow python $R/lab/agentless_metric_verified.py --predictions $OUT/ver_ts40.jsonl --expect-n 0 --out $M/ver_ts40.json > $M/ver_ts40.log 2>&1; echo "scored ver_ts40 rc=$?"
echo E47_GATE_DONE
