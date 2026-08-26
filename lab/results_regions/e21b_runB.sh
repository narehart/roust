#!/bin/zsh
# E21b Lite-300 gate, runner B (private repos copy e20b):
# arm 3: E21b chunk-top2-rank (decoupled, top2 aggregate)
set -e
export BGREP_REGION_EVAL_SKIP_DRIVER_GUARD=1  # twin-runner pgrep false positive only; verified no swebench_driver process exists (issue #41 discipline: private clone copies)
cd /Users/nicholasarehart/programming-projects/bgrep
echo "runner B start: $(date)"
uv run --with pandas --with pyarrow python parity/region_eval2.py \
  --file-score chunk-top2-rank \
  --report lab/results_regions/e21b_chunktop2rank.jsonl \
  --repos-dir lab/swebench_repos_e20b
echo "runner B chunk-top2-rank done: $(date)"
