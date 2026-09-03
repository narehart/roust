#!/bin/bash
# E46d: JS/TS's depth-neutral budget. 9216 recovered only .015 of its .034
# fraction tax (largest of any slice; its cap-32 bundles carry the most
# files). The rust/go dose-response predicts ~10.5-11k. sg + cap 32 @ 10752;
# FILE must equal jsts_sg32 (52.07); compare + score chained on completion.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
$PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/mswe_jsts.parquet --repos-dir $R/lab/mswe_repos_private \
    --symbol-graph --max-additions 32 --budget 10752 \
    --report "$OUT/jsts_b10752.jsonl" > "$OUT/jsts_b10752.log" 2>&1
echo "ARM_DONE jsts_b10752 rc=$? $(date +%H:%M:%S)"
uv run --no-project --with scipy python $R/lab/results_regions/e44/compare.py $R/lab/results_regions/e37/arms/jsts_sg32.jsonl $OUT/jsts_b10752.jsonl "jsts sg32@8192 -> @10752"
uv run --no-project --with scipy python $R/lab/results_regions/e44/compare.py $R/lab/results_regions/e37/arms/jsts_base.jsonl $OUT/jsts_b10752.jsonl "jsts SHIPPED -> sg32@10752"
bash $R/lab/results_regions/e44/score.sh jsts $OUT/jsts_b10752.jsonl:b10752
echo E46D_DONE
