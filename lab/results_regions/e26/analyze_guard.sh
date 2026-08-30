#!/bin/bash
# E26 wave-2 analysis: default vs GUARDED --ext-v2, same pairing as wave 1.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
R=$P/lab/results_regions/e26; R25=$P/lab/results_regions/e25
cd $P
UV="uv run --no-project --with pandas --with pyarrow --with tree-sitter --with tree-sitter-javascript --with tree-sitter-typescript --with tree-sitter-java --with tree-sitter-go --with tree-sitter-rust --with tree-sitter-c --with tree-sitter-cpp python"
UVS="uv run --no-project --with pandas --with pyarrow --with scipy python"
pq() { case $1 in jsts) echo lab/mswe_jsts.parquet;; java) echo lab/ws3b_java.parquet;; c) echo lab/mswe_c.parquet;; esac; }
repos() { case $1 in jsts) echo lab/e26_repos/jsts_guard;; java) echo lab/e26_repos/java_guard;; c) echo lab/e26_repos/c_guard;; esac; }
for s in jsts java c; do
  $UV lab/agentless_metric_full.py --predictions "$R/${s}_guard.jsonl" \
     --gold-parquet "$(pq $s)" --repos-dir "$(repos $s)" --ts-functions --lang-functions \
     --expect-n 0 --out "$R/metric_${s}_guard.json" > "$R/score_${s}_guard.log" 2>&1 \
     && echo "scored ${s}_guard" || echo "FAILED ${s}_guard"
done
for s in jsts java c; do
  $UVS lab/e26_paired.py --label "${s}_guarded" --parquet "$(pq $s)" \
    --def-jsonl $R25/${s}_def.jsonl --ext-jsonl $R/${s}_guard.jsonl \
    --def-metric $R25/metric_${s}_def.json --ext-metric $R/metric_${s}_guard.json \
    --out-prefix $R/${s}_guard > $R/paired_${s}_guard.txt 2>&1
  echo "=== paired ${s}_guard exit=$?"
done
echo E26_GUARD_ANALYSIS_DONE
