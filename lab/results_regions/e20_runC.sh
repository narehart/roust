#!/bin/zsh
# E20/E11b Verified-407 dual gate, runner C (private repos copy e20a):
# verified baseline -> verified E20-knn lambda 0.7
set -e
export BGREP_REGION_EVAL_SKIP_DRIVER_GUARD=1  # no swebench_driver exists; private clone copy (issue #41)
cd /Users/nicholasarehart/programming-projects/bgrep
echo "runner C start: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval_verified.py \
  --report lab/results_regions/e20_verified_baseline.jsonl \
  --repos-dir lab/swebench_repos_e20a
echo "runner C verified baseline done: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval_verified.py \
  --lexboost 0.7 --lexboost-graph knn \
  --report lab/results_regions/e20_verified_knn07.jsonl \
  --repos-dir lab/swebench_repos_e20a
echo "runner C verified knn07 done: $(date)"
