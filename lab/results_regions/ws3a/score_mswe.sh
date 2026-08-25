#!/bin/bash
# WS3a MSWE scoring: agentless_metric_full with --repos-dir (FUNCTION spans
# are parsed from the checkouts via read-only git show).
set -eu
P=/Users/nicholasarehart/programming-projects/bgrep
R=$P/lab/results_regions/ws3a
cd $P
UV="uv run --no-project --with pandas --with pyarrow --with tree-sitter --with tree-sitter-javascript --with tree-sitter-typescript --with tree-sitter-java --with tree-sitter-go --with tree-sitter-rust --with tree-sitter-c --with tree-sitter-cpp python"
score() { pred=$1; gold=$2; repos=$3; out=$4
  $UV lab/agentless_metric_full.py --predictions "$R/$pred" --gold-parquet "$gold" \
    --repos-dir "$repos" --ts-functions --lang-functions --expect-n 0 \
    --out "$R/$out" > "$R/${out%.json}.log" 2>&1
  echo "scored $out"
}
score mswe_jsts_ws3a_base.jsonl lab/mswe_jsts.parquet lab/mswe_repos_e23 agentless_metric_ws3a_jsts_base.json
score mswe_jsts_ws3a_v2.jsonl   lab/mswe_jsts.parquet lab/mswe_repos_e23 agentless_metric_ws3a_jsts_v2.json
score mswe_cpp_ws3a_base.jsonl  lab/mswe_cpp.parquet  lab/ws3a_repos/cpp_base agentless_metric_ws3a_cpp_base.json
score mswe_cpp_ws3a_v2.jsonl    lab/mswe_cpp.parquet  lab/ws3a_repos/cpp_base agentless_metric_ws3a_cpp_v2.json
score mswe_rust_ws3a_base.jsonl lab/ws3a_rust.parquet lab/ws3a_repos/rust_base agentless_metric_ws3a_rust_base.json
score mswe_rust_ws3a_v2.jsonl   lab/ws3a_rust.parquet lab/ws3a_repos/rust_base agentless_metric_ws3a_rust_v2.json
rm -f $R/agentless_metric_ws3a_ws3a_base_cpp.json $R/agentless_metric_ws3a_ws3a_v2_cpp.json
echo MSWE_RESCORING_DONE
