#!/bin/zsh
# E21b Lite-300 gate, runner A (private repos copy e20a):
# arm 1: baseline (defaults)  arm 2: E21b chunk-rank (decoupled)
set -e
export BGREP_REGION_EVAL_SKIP_DRIVER_GUARD=1  # twin-runner pgrep false positive only; verified no swebench_driver process exists (issue #41 discipline: private clone copies)
cd /Users/nicholasarehart/programming-projects/bgrep
echo "runner A start: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --report lab/results_regions/e21b_baseline.jsonl \
  --repos-dir lab/swebench_repos_e20a
echo "runner A baseline done: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --file-score chunk-rank \
  --report lab/results_regions/e21b_chunkrank.jsonl \
  --repos-dir lab/swebench_repos_e20a
echo "runner A chunk-rank done: $(date)"
