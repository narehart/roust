#!/bin/bash
# E40: JS/TS is the lone holdout and its gap is GENUINE -- ceiling 76.68 vs
# 52.07 measured, so there is 24.6 points of real headroom with no benchmark
# artifact involved (changelog indexing made jsts WORSE, -2.07). The one lever
# never run on the full slice is the second hop, which was jsts's single
# largest gain on the multi-gold stratum (+10.14). No --changelog-files here.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e39/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  tag=$1; dir=$2; extra=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/mswe_jsts.parquet \
      --repos-dir "$dir" --symbol-graph $extra \
      --report "$OUT/jsts_${tag}.jsonl" > "$OUT/jsts_${tag}.log" 2>&1
  echo "ARM_DONE jsts_${tag} rc=$? $(date +%H:%M:%S)"
}
run h2c32  $R/lab/mswe_repos_e23     "--import-hops 2 --max-additions 32"                  & sleep 8
run h2c64b $R/lab/mswe_repos_private "--import-hops 2 --max-additions 64 --budget 16384"   &
wait
echo E40_DONE
