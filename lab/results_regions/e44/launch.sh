#!/bin/bash
# E44 smoke: PPR budget concentration on Rust (239, the fastest full slice).
# Same file set as rust_sg32 by construction (PPR runs AFTER selection), so
# FILE must come out IDENTICAL -- that is the built-in identity gate -- and
# any FUNCTION/LINE/fraction movement is a pure depth effect at fixed cap 32
# and fixed budget 8192. Two lambdas for dose-response.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { tag=$1; dir=$2; lam=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/ws3a_rust.parquet --repos-dir "$dir" \
      --symbol-graph --max-additions 32 --ppr-budget "$lam" \
      --report "$OUT/rust_${tag}.jsonl" > "$OUT/rust_${tag}.log" 2>&1
  echo "ARM_DONE rust_${tag} rc=$? $(date +%H:%M:%S)"; }
run ppr05 $R/lab/ws3a_repos/rust_v2   0.5 & sleep 8
run ppr08 $R/lab/ws3a_repos/rust_base 0.8 &
wait; echo E44_SMOKE_DONE
