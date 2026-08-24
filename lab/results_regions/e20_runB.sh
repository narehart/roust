#!/bin/zsh
# E20/E11b Lite-300 gate, runner B (private repos copy e20b):
# arm 3: E20 BM25-kNN lambda 0.7  arm 4: E11b trace-boost
set -e
cd /Users/nicholasarehart/programming-projects/bgrep
echo "runner B start: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --lexboost 0.7 --lexboost-graph knn \
  --report lab/results_regions/e20_knn07.jsonl \
  --repos-dir lab/swebench_repos_e20b
echo "runner B knn07 done: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --trace-boost \
  --report lab/results_regions/e20_traceboost.jsonl \
  --repos-dir lab/swebench_repos_e20b
echo "runner B traceboost done: $(date)"
