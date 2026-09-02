#!/bin/bash
# E44 FUNCTION/LINE scoring. agentless_metric_full.py ONLY (lab/agentless_metric.py
# ignores its CLI args). --expect-n = full slice size. Usage: score.sh <slice> <tag>...
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
BASE=$R/lab/results_regions/e44; MET=$BASE/metrics; mkdir -p "$MET"
PY="uv run --no-project --with pandas --with pyarrow --with scipy --with tree_sitter --with tree_sitter_javascript --with tree_sitter_typescript --with tree_sitter_java --with tree_sitter_go --with tree_sitter_rust --with tree_sitter_c --with tree_sitter_cpp python"
slice=$1; shift
case "$slice" in
  rust) PQ=$R/lab/ws3a_rust.parquet; RD=$R/lab/ws3a_repos/rust_base; N=239 ;;
  jsts) PQ=$R/lab/mswe_jsts.parquet; RD=$R/lab/mswe_repos_e23;       N=580 ;;
  java) PQ=$R/lab/ws3b_java.parquet; RD=$R/lab/ws3b_repos/java_base; N=128 ;;
  go)   PQ=$R/lab/mswe_go.parquet;   RD=$R/lab/ws3b_repos/go_base;   N=428 ;;
  cpp)  PQ=$R/lab/mswe_cpp.parquet;  RD=$R/lab/ws3a_repos/cpp_base;  N=129 ;;
  c)    PQ=$R/lab/mswe_c.parquet;    RD=$R/lab/ws3b_repos/c_base;    N=128 ;;
esac
for spec in "$@"; do
  # spec = <jsonl path>:<metric tag>
  jl=${spec%%:*}; tag=${spec##*:}
  $PY $R/lab/agentless_metric_full.py --predictions "$jl" --gold-parquet "$PQ" --repos-dir "$RD" \
      --expect-n "$N" --ts-functions --lang-functions --out "$MET/${slice}_${tag}.json" > "$MET/${slice}_${tag}.log" 2>&1
  echo "SCORED ${slice}_${tag} rc=$?"
done
