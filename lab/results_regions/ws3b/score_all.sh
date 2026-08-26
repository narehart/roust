#!/bin/bash
# WS3b scoring: agentless_metric_full with --repos-dir + tree-sitter wheels
# (FUNCTION spans parsed from the checkouts via read-only git show; the
# WS3a lesson -- without the wheels + --repos-dir, FUNCTION silently
# scores 0.00).
set -eu
P=/Users/nicholasarehart/programming-projects/bgrep
R=$P/lab/results_regions/ws3b
cd $P
UV="uv run --no-project --with pandas --with pyarrow --with tree-sitter --with tree-sitter-javascript --with tree-sitter-typescript --with tree-sitter-java --with tree-sitter-go --with tree-sitter-rust --with tree-sitter-c --with tree-sitter-cpp python"
score() { pred=$1; gold=$2; repos=$3; out=$4
  $UV lab/agentless_metric_full.py --predictions "$R/$pred" --gold-parquet "$gold" \
    --repos-dir "$repos" --ts-functions --lang-functions --expect-n 0 \
    --out "$R/$out" > "$R/${out%.json}.log" 2>&1
  echo "scored $out"
}
score mswe_java_ws3b_base.jsonl lab/ws3b_java.parquet lab/ws3b_repos/java_base agentless_metric_ws3b_java_base.json
score mswe_java_ws3b_v2.jsonl   lab/ws3b_java.parquet lab/ws3b_repos/java_base agentless_metric_ws3b_java_v2.json
score mswe_rust_ws3b_base.jsonl lab/ws3a_rust.parquet lab/ws3a_repos/rust_base agentless_metric_ws3b_rust_base.json
score mswe_rust_ws3b_v2.jsonl   lab/ws3a_rust.parquet lab/ws3a_repos/rust_base agentless_metric_ws3b_rust_v2.json
score mswe_cpp_ws3b_base.jsonl  lab/mswe_cpp.parquet  lab/ws3a_repos/cpp_base agentless_metric_ws3b_cpp_base.json
score mswe_c_ws3b_base.jsonl    lab/mswe_c.parquet    lab/ws3b_repos/c_base agentless_metric_ws3b_c_base.json
score mswe_go_micro_ws3b_base.jsonl lab/ws3b_go_micro.parquet lab/ws3b_repos/go_base agentless_metric_ws3b_go_micro_base.json
score mswe_go_micro_ws3b_v2.jsonl   lab/ws3b_go_micro.parquet lab/ws3b_repos/go_base agentless_metric_ws3b_go_micro_v2.json
score mswe_jsts_micro_ws3b_base.jsonl lab/ws3b_jsts_micro.parquet lab/ws3b_repos/jsts_base agentless_metric_ws3b_jsts_micro_base.json
score mswe_jsts_micro_ws3b_v2.jsonl   lab/ws3b_jsts_micro.parquet lab/ws3b_repos/jsts_base agentless_metric_ws3b_jsts_micro_v2.json
echo WS3B_SCORING_DONE
