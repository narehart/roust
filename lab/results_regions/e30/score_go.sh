#!/bin/bash
# E30 Go scoring. agentless_metric_full.py only (never lab/agentless_metric.py).
# --expect-n 143 = the Go >=3-gold-file stratum (E29's instance list), not the
# 428-instance slice: a short arm must fail loudly, not pass quietly.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
BASE=$R/lab/results_regions/e30
MET=$BASE/metrics; mkdir -p "$MET"
PY="uv run --no-project --with pandas --with pyarrow --with scipy --with tree_sitter --with tree_sitter_go python"
for t in "$@"; do
  $PY $R/lab/agentless_metric_full.py --predictions "$BASE/arms/go_$t.jsonl" \
      --gold-parquet $R/lab/mswe_go.parquet --repos-dir $R/lab/ws3b_repos/go_base \
      --expect-n 143 --ts-functions --lang-functions --out "$MET/go_$t.json" \
      > "$MET/go_$t.log" 2>&1
  echo "SCORED go_$t rc=$?"
done
