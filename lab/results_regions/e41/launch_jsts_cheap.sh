#!/bin/bash
# E42: jsts at cap 128 measured CHEAPLY. E29 proved the returned FILE SET is
# budget-invariant (618/618 instances byte-identical from 8192 to 24576), so
# the FILE score at cap 128 is the same at the shipped budget as at 24576 --
# and the shipped budget packs far less, which is why the earlier cap128 arm
# at budget 24576 ran for hours and this one should not.
# Trend: cap32 54.48 -> cap64 59.31 (+4.83/doubling) -> cap128 projects ~64,
# against a bar of 63.64 and a ceiling of 76.68. NO non-source indexing:
# this must be a genuine result.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e41/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  tag=$1; dir=$2; cap=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/mswe_jsts.parquet \
      --repos-dir "$dir" --symbol-graph --import-hops 2 --max-additions "$cap" \
      --report "$OUT/jsts_${tag}.jsonl" > "$OUT/jsts_${tag}.log" 2>&1
  echo "ARM_DONE jsts_${tag} rc=$? $(date +%H:%M:%S)"
}
run c128cheap $R/lab/mswe_repos_e23     128 & sleep 8
run c256cheap $R/lab/mswe_repos_private 256 &
wait
echo E42_DONE
