#!/bin/bash
# E46: the depth-neutral budget for sg + cap 32 on Rust. Diagnosis from E44/E45:
# reallocating budget AMONG returned files (PPR x2, floor x2) does not recover
# the depth tax, because the tax is the COUNT of mandatory pass-1 seats (one
# per returned file; FILE counts a file only if it has >=1 span). At cap 32 the
# bundle carries 42.5 files vs 29.9 at cap 16, seats are already ~10 lines,
# so the only proven lever left is budget (E29: FILE budget-invariant, depth
# fully budget-recoverable). Find the smallest budget that restores shipped
# FUNCTION/LINE while keeping the +5.02 FILE. FILE must equal rust_sg32.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { tag=$1; dir=$2; b=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/ws3a_rust.parquet --repos-dir "$dir" \
      --symbol-graph --max-additions 32 --budget "$b" \
      --report "$OUT/rust_${tag}.jsonl" > "$OUT/rust_${tag}.log" 2>&1
  echo "ARM_DONE rust_${tag} rc=$? $(date +%H:%M:%S)"; }
run b9216  $R/lab/ws3a_repos/rust_v2   9216  & sleep 8
run b10240 $R/lab/ws3a_repos/rust_base 10240 &
wait; echo E46_DONE
