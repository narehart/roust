#!/bin/bash
# WS3d scoring: jsts base + guard arms via agentless_metric_full with
# --repos-dir + tree-sitter wheels (FUNCTION spans parsed from the
# checkouts via read-only git show; without the wheels + --repos-dir
# FUNCTION silently scores 0.00 -- the WS3a lesson). The reduced grid
# (fixture_census.log + python_microgate.log) means there are no
# java/rust/Lite/Verified arms to score this round.
set -eu
P=/Users/nicholasarehart/programming-projects/bgrep
R=$P/lab/results_regions/ws3d
cd $P
UV="uv run --no-project --with pandas --with pyarrow --with tree-sitter --with tree-sitter-javascript --with tree-sitter-typescript --with tree-sitter-java --with tree-sitter-go --with tree-sitter-rust --with tree-sitter-c --with tree-sitter-cpp python"
score() { pred=$1; gold=$2; repos=$3; out=$4
  $UV lab/agentless_metric_full.py --predictions "$R/$pred" --gold-parquet "$gold" \
    --repos-dir "$repos" --ts-functions --lang-functions --expect-n 0 \
    --out "$R/$out" > "$R/${out%.json}.log" 2>&1
  echo "scored $out"
}
score mswe_jsts_ws3d_base.jsonl  lab/mswe_jsts.parquet lab/mswe_repos_e23 agentless_metric_ws3d_jsts_base.json
score mswe_jsts_ws3d_guard.jsonl lab/mswe_jsts.parquet lab/mswe_repos_e23 agentless_metric_ws3d_jsts_guard.json
echo WS3D_SCORING_DONE
