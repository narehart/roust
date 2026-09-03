#!/bin/bash
# E47 smoke, Rust: sg + cap 32 @ shipped budget 8192 with tiered seats. FILE
# must equal rust_sg32 (65.27) -- every file still gets >= 1 span. Depth
# should recover toward shipped (19.67 FUNC / .2431) at ZERO extra tokens.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e47/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { tag=$1; dir=$2; tok=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet $R/lab/ws3a_rust.parquet --repos-dir "$dir" \
      --symbol-graph --max-additions 32 --tail-seat-tokens "$tok" --tail-seat-after 16 \
      --report "$OUT/rust_${tag}.jsonl" > "$OUT/rust_${tag}.log" 2>&1
  echo "ARM_DONE rust_${tag} rc=$? $(date +%H:%M:%S)"
  uv run --no-project --with scipy python $R/lab/results_regions/e44/compare.py $R/lab/results_regions/e37/arms/rust_sg32.jsonl $OUT/rust_${tag}.jsonl "rust sg32 -> tail seat $tok"; }
run ts40 $R/lab/ws3a_repos/rust_v2   40 & sleep 8
run ts60 $R/lab/ws3a_repos/rust_base 60 &
wait; echo E47_SMOKE_DONE
