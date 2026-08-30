#!/bin/bash
# E26 scoring: the five --ext-v2 arms, via agentless_metric_full with
# --repos-dir + the tree-sitter wheels (FUNCTION spans are parsed from the
# checkouts; without the wheels + --repos-dir FUNCTION silently scores 0.00
# -- the WS3a lesson). NOT lab/agentless_metric.py, which ignores CLI args.
# The DEFAULT arm's metric JSONs are E25's committed metric_<slice>_def.json:
# the abb96af..5ebd6ab engine diff is flag-gated only, so they are the
# same-engine default side of every pair.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
R=$P/lab/results_regions/e26
cd $P
UV="uv run --no-project --with pandas --with pyarrow --with tree-sitter --with tree-sitter-javascript --with tree-sitter-typescript --with tree-sitter-java --with tree-sitter-go --with tree-sitter-rust --with tree-sitter-c --with tree-sitter-cpp python"
score() { arm=$1; gold=$2; repos=$3
  $UV lab/agentless_metric_full.py --predictions "$R/$arm.jsonl" --gold-parquet "$gold" \
    --repos-dir "$repos" --ts-functions --lang-functions --expect-n 0 \
    --out "$R/metric_$arm.json" > "$R/score_$arm.log" 2>&1 \
    && echo "scored $arm" || echo "FAILED $arm (see $R/score_$arm.log)"
}
score jsts_ext lab/mswe_jsts.parquet lab/mswe_repos_private
score java_ext lab/ws3b_java.parquet lab/ws3b_repos/java_v2
score rust_ext lab/ws3a_rust.parquet lab/ws3a_repos/rust_v2
score c_ext    lab/mswe_c.parquet    lab/e26_repos/c_ext
score cpp_ext  lab/mswe_cpp.parquet  lab/ws3a_repos/cpp_v2
echo E26_SCORING_DONE
