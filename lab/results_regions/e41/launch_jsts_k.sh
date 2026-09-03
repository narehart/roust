#!/bin/bash
# E42b: last genuine lever for jsts. Admission has plateaued (cap32 54.48 ->
# cap64 59.31 -> cap128 62.07 -> cap256 trending DOWN), leaving 1.57 to the
# bar. The seed count is untried here at a runnable cost: it gave rust +3.81
# and cpp +3.64, and the earlier jsts k30 attempt stalled only because it was
# paired with budget 16384. FILE is budget-invariant, so the shipped budget
# gives the same FILE far more cheaply. No non-source indexing.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e41/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { tag=$1; dir=$2; k=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/mswe_jsts.parquet \
      --repos-dir "$dir" --symbol-graph --import-hops 2 --max-additions 128 --k-lex "$k" \
      --report "$OUT/jsts_${tag}.jsonl" > "$OUT/jsts_${tag}.log" 2>&1
  echo "ARM_DONE jsts_${tag} rc=$? $(date +%H:%M:%S)"; }
run k20 $R/lab/mswe_repos_e23     20 & sleep 8
run k30 $R/lab/mswe_repos_private 30 &
wait
echo E42B_DONE
