#!/bin/bash
# E44b: additive PPR budget boost on Rust. Identity gate as before (FILE must
# equal rust_sg32 instance-for-instance); the multiplicative cut moved the
# fraction the wrong way (-.0167 / -.0080), hypothesis: it starved the
# additions where the multi-file gold lives. Additive raises connected files
# without lowering anyone. Two lambdas for dose-response.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { tag=$1; dir=$2; lam=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/ws3a_rust.parquet --repos-dir "$dir" \
      --symbol-graph --max-additions 32 --ppr-budget "$lam" --ppr-additive \
      --report "$OUT/rust_${tag}.jsonl" > "$OUT/rust_${tag}.log" 2>&1
  echo "ARM_DONE rust_${tag} rc=$? $(date +%H:%M:%S)"; }
run add03 $R/lab/ws3a_repos/rust_v2   0.3 & sleep 8
run add06 $R/lab/ws3a_repos/rust_base 0.6 &
wait; echo E44B_DONE
