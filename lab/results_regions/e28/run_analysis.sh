#!/bin/bash
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
BASE=$R/lab/results_regions/e28
E27=$R/lab/results_regions/e27
PY="uv run --no-project --with scipy python"
"$BASE/score_all.sh" 2>&1 | tee "$BASE/scoring.out"
echo "--- paired analysis ---"
while IFS='|' read -r s h p a b; do
  case "$s" in \#*|"") continue ;; esac
  for cap in 24 32; do
    tag="${s}_m${cap}"
    $PY $R/lab/e28_paired.py --label "$tag" \
        --def-jsonl "$E27/${s}_s0.jsonl" --arm-jsonl "$BASE/arms/${tag}.jsonl" \
        --def-metric "$E27/metric_${s}_s0.json" --arm-metric "$BASE/metrics/${tag}.json" \
        --out-prefix "$BASE/${tag}" > "$BASE/paired_${tag}.txt" 2>&1
    echo "PAIRED $tag rc=$?"
  done
done < "$BASE/slices.env"
uv run --no-project python $R/lab/e28_tables.py --dir "$BASE" > "$BASE/tables.md" 2>&1
echo "TABLES rc=$?"
echo ALL_ANALYSIS_DONE
