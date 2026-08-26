#!/bin/bash
# E25 scoring: all 12 non-Python arms via agentless_metric_full with
# --repos-dir + the tree-sitter wheels (FUNCTION spans are parsed from the
# checkouts; without the wheels + --repos-dir FUNCTION silently scores 0.00
# -- the WS3a lesson). NOT lab/agentless_metric.py, which ignores CLI args.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
R=$P/lab/results_regions/e25
cd $P
UV="uv run --no-project --with pandas --with pyarrow --with tree-sitter --with tree-sitter-javascript --with tree-sitter-typescript --with tree-sitter-java --with tree-sitter-go --with tree-sitter-rust --with tree-sitter-c --with tree-sitter-cpp python"
score() { arm=$1; gold=$2; repos=$3
  $UV lab/agentless_metric_full.py --predictions "$R/$arm.jsonl" --gold-parquet "$gold" \
    --repos-dir "$repos" --ts-functions --lang-functions --expect-n 0 \
    --out "$R/metric_$arm.json" > "$R/score_$arm.log" 2>&1 \
    && echo "scored $arm" || echo "FAILED $arm (see $R/score_$arm.log)"
}
score jsts_def   lab/mswe_jsts.parquet lab/mswe_repos_e23
score jsts_shape lab/mswe_jsts.parquet lab/mswe_repos_private
score java_def   lab/ws3b_java.parquet lab/ws3b_repos/java_base
score java_shape lab/ws3b_java.parquet lab/ws3b_repos/java_v2
score go_def     lab/mswe_go.parquet   lab/ws3b_repos/go_base
score go_shape   lab/mswe_go.parquet   lab/ws3b_repos/go_v2
score rust_def   lab/ws3a_rust.parquet lab/ws3a_repos/rust_base
score rust_shape lab/ws3a_rust.parquet lab/ws3a_repos/rust_v2
score c_def      lab/mswe_c.parquet    lab/ws3b_repos/c_base
score c_shape    lab/mswe_c.parquet    lab/e25_repos/c_shape
score cpp_def    lab/mswe_cpp.parquet  lab/ws3a_repos/cpp_base
score cpp_shape  lab/mswe_cpp.parquet  lab/e25_repos/cpp_shape
echo E25_SCORING_DONE
