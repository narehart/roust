#!/bin/bash
# E48: can BREADTH become a default now that the stub refunds its depth tax?
#  (a) Python dual gate at --symbol-graph --max-additions 32 (stub is now the
#      shipped default, so no flag). E28 rejected plain cap 32 on Python for
#      region regressions; the stub may have changed that. Baselines: the
#      post-E47 Python arms (lite_ts40 / ver_ts40 = new published refs).
#  (b) JS/TS, the one holdout at cap 32 (FUNCTION -1.55 vs shipped with the
#      40-token stub): a smaller stub, 25 tokens. Baseline jsts_ts40 (cap32).
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e48/arms
PY="uv run --no-project --with pandas --with pyarrow python"
C=$R/lab/results_regions/e44/compare.py
$PY "$R/parity/region_eval2.py" --repos-dir $R/lab/swebench_repos_e20a --symbol-graph --max-additions 32 \
    --report "$OUT/lite_sg32.jsonl" > "$OUT/lite_sg32.log" 2>&1 & sleep 8
$PY "$R/parity/region_eval_verified.py" --repos-dir $R/lab/ws3a_repos/repos_ver_base --symbol-graph --max-additions 32 \
    --report "$OUT/ver_sg32.jsonl" > "$OUT/ver_sg32.log" 2>&1 & sleep 8
$PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/mswe_jsts.parquet --repos-dir $R/lab/mswe_repos_private \
    --symbol-graph --max-additions 32 --tail-seat-tokens 25 --tail-seat-after 16 \
    --report "$OUT/jsts_sg32_ts25.jsonl" > "$OUT/jsts_sg32_ts25.log" 2>&1 &
wait
uv run --no-project --with scipy python $C $R/lab/results_regions/e47/arms/lite_ts40.jsonl $OUT/lite_sg32.jsonl "LITE new-default -> +sg+cap32"
uv run --no-project --with scipy python $C $R/lab/results_regions/e47/arms/ver_ts40.jsonl $OUT/ver_sg32.jsonl "VERIFIED new-default -> +sg+cap32"
uv run --no-project --with scipy python $C $R/lab/results_regions/e47/arms/jsts_ts40.jsonl $OUT/jsts_sg32_ts25.jsonl "jsts cap32 stub40 -> stub25"
uv run --no-project --with scipy python $C $R/lab/results_regions/e37/arms/jsts_base.jsonl $OUT/jsts_sg32_ts25.jsonl "jsts SHIPPED -> cap32 stub25"
echo E48_ARMS_DONE
