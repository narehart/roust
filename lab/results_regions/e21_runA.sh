#!/bin/zsh
# E21/E22 Lite-300 gate, runner A (private repos copy e20a):
# arm 1: baseline (defaults)  arm 2: E21 chunk-max  arm 3: E22 test-bridge 0.1
set -e
export BGREP_REGION_EVAL_SKIP_DRIVER_GUARD=1  # twin-runner pgrep false positive only; verified no swebench_driver process exists (issue #41 discipline: private clone copies)
cd /Users/nicholasarehart/programming-projects/bgrep
echo "runner A start: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --report lab/results_regions/e21_baseline.jsonl \
  --repos-dir lab/swebench_repos_e20a
echo "runner A baseline done: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --file-score chunk-max \
  --report lab/results_regions/e21_chunkmax.jsonl \
  --repos-dir lab/swebench_repos_e20a
echo "runner A chunk-max done: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --test-bridge 0.1 \
  --report lab/results_regions/e22_tb01.jsonl \
  --repos-dir lab/swebench_repos_e20a
echo "runner A tb01 done: $(date)"
