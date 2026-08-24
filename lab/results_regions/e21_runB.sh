#!/bin/zsh
# E21/E22 Lite-300 gate, runner B (private repos copy e20b):
# arm 1: E21 chunk-top2  arm 2: E22 test-bridge 0.3
set -e
export BGREP_REGION_EVAL_SKIP_DRIVER_GUARD=1  # twin-runner pgrep false positive only; verified no swebench_driver process exists (issue #41 discipline: private clone copies)
cd /Users/nicholasarehart/programming-projects/bgrep
echo "runner B start: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --file-score chunk-top2 \
  --report lab/results_regions/e21_chunktop2.jsonl \
  --repos-dir lab/swebench_repos_e20b
echo "runner B chunk-top2 done: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --test-bridge 0.3 \
  --report lab/results_regions/e22_tb03.jsonl \
  --repos-dir lab/swebench_repos_e20b
echo "runner B tb03 done: $(date)"
