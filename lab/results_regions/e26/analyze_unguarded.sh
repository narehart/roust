#!/bin/bash
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
R=$P/lab/results_regions/e26
R25=$P/lab/results_regions/e25
cd $P
UV="uv run --no-project --with pandas --with pyarrow --with scipy python"
pq() { case $1 in jsts) echo lab/mswe_jsts.parquet;; java) echo lab/ws3b_java.parquet;;
  rust) echo lab/ws3a_rust.parquet;; c) echo lab/mswe_c.parquet;; cpp) echo lab/mswe_cpp.parquet;; esac; }
for s in jsts java rust c cpp; do
  $UV lab/e26_paired.py --label $s --parquet "$(pq $s)" \
    --def-jsonl $R25/${s}_def.jsonl --ext-jsonl $R/${s}_ext.jsonl \
    --def-metric $R25/metric_${s}_def.json --ext-metric $R/metric_${s}_ext.json \
    --out-prefix $R/${s}_ext > $R/paired_${s}_ext.txt 2>&1
  echo "=== $s exit=$?"
done
echo E26_UNGUARDED_ANALYSIS_DONE
