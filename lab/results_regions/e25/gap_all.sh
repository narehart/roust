#!/bin/bash
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
R=$P/lab/results_regions/e25
cd $P
UV="uv run --no-project --with pandas --with pyarrow --with tree-sitter --with tree-sitter-javascript --with tree-sitter-typescript --with tree-sitter-java --with tree-sitter-go --with tree-sitter-rust --with tree-sitter-c --with tree-sitter-cpp python"
gap() { label=$1; pq=$2; repos=$3
  $UV lab/e25_shape_gap.py --parquet $pq --repos-dir $repos --label $label \
    --out $R/gap_$label.json 2>&1 | tail -32
}
gap jsts lab/mswe_jsts.parquet lab/mswe_repos_e23
gap java lab/ws3b_java.parquet lab/ws3b_repos/java_base
gap go   lab/mswe_go.parquet   lab/ws3b_repos/go_base
gap rust lab/ws3a_rust.parquet lab/ws3a_repos/rust_base
gap c    lab/mswe_c.parquet    lab/ws3b_repos/c_base
gap cpp  lab/mswe_cpp.parquet  lab/ws3a_repos/cpp_base
echo E25_GAP_DONE
