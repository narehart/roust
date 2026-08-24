#!/bin/zsh
# E20/E11b Lite-300 gate, runner A (private repos copy e20a):
# arm 1: baseline (defaults)  arm 2: E20 import-graph lambda 0.7
set -e
cd /Users/nicholasarehart/programming-projects/bgrep
echo "runner A start: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --report lab/results_regions/e20_baseline.jsonl \
  --repos-dir lab/swebench_repos_e20a
echo "runner A baseline done: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --lexboost 0.7 --lexboost-graph import \
  --report lab/results_regions/e20_import07.jsonl \
  --repos-dir lab/swebench_repos_e20a
echo "runner A import07 done: $(date)"
