#!/bin/zsh
# E20/E11b runner D (private repos copy e20b):
# verified E11b trace-boost -> Lite knn lambda mini-sweep (0.5, 0.9)
set -e
export BGREP_REGION_EVAL_SKIP_DRIVER_GUARD=1  # no swebench_driver exists; private clone copy (issue #41)
cd /Users/nicholasarehart/programming-projects/bgrep
echo "runner D start: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval_verified.py \
  --trace-boost \
  --report lab/results_regions/e20_verified_traceboost.jsonl \
  --repos-dir lab/swebench_repos_e20b
echo "runner D verified traceboost done: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --lexboost 0.5 --lexboost-graph knn \
  --report lab/results_regions/e20_knn05.jsonl \
  --repos-dir lab/swebench_repos_e20b
echo "runner D lite knn05 done: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --lexboost 0.9 --lexboost-graph knn \
  --report lab/results_regions/e20_knn09.jsonl \
  --repos-dir lab/swebench_repos_e20b
echo "runner D lite knn09 done: $(date)"
