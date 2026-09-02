#!/bin/bash
# E45: packer budget floor on Rust, sg + cap 32, budget 8192. The floor is
# the one constant that makes wide admission spread budget evenly; lowering
# it makes allocation proportional to the LEXICAL file score -- the signal
# that already places regions -- rather than introducing a new graph signal
# (PPR, both forms, was negative). Identity gate: FILE must equal rust_sg32.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { tag=$1; dir=$2; fl=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/ws3a_rust.parquet --repos-dir "$dir" \
      --symbol-graph --max-additions 32 --pack-floor "$fl" \
      --report "$OUT/rust_${tag}.jsonl" > "$OUT/rust_${tag}.log" 2>&1
  echo "ARM_DONE rust_${tag} rc=$? $(date +%H:%M:%S)"; }
run fl15 $R/lab/ws3a_repos/rust_v2   0.15 & sleep 8
run fl05 $R/lab/ws3a_repos/rust_base 0.05 &
wait; echo E45_DONE
