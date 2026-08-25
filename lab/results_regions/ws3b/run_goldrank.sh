#!/bin/bash
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
NB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/ws3b-trace-formats/roust-rs/target/release/roust
R=$P/lab/results_regions/ws3b
cd $P
run() { name=$1; gold=$2; repos=$3; rep=$4
  uv run --no-project --with pandas --with pyarrow python lab/ws3b_goldrank.py \
    "$NB" "$gold" "$repos" "$R/$rep" > "$R/goldrank_$name.jsonl" 2> "$R/goldrank_$name.err"
  echo "done $name $(wc -l < $R/goldrank_$name.jsonl)"
}
run java lab/ws3b_java.parquet lab/ws3b_repos/java_v2 mswe_java_ws3b_v2.jsonl
run rust lab/ws3a_rust.parquet lab/ws3a_repos/rust_v2 mswe_rust_ws3b_v2.jsonl
run go lab/ws3b_go_micro.parquet lab/ws3b_repos/go_v2 mswe_go_micro_ws3b_v2.jsonl
run jsts lab/ws3b_jsts_micro.parquet lab/ws3b_repos/jsts_v2 mswe_jsts_micro_ws3b_v2.jsonl
echo GOLDRANK_ALL_DONE
