#!/bin/bash
# E25 Python scoring. Python gold is pure-Python, so FUNCTION spans come from
# the stdlib ast walk inside these scorers -- --repos-dir/--lang-functions are
# the non-Python (tree-sitter) path and do not apply here. These are the same
# two scorers the committed ws2c Lite/Verified baselines were produced with.
# NOT lab/agentless_metric.py (it ignores CLI args). Bash, not zsh.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
R=$P/lab/results_regions/e25
cd $P
UV="uv run --no-project --with pandas --with pyarrow python"
$UV lab/agentless_metric_v4.py --predictions $R/lite300_def.jsonl \
  --out $R/metric_lite300_def.json > $R/score_lite300_def.log 2>&1 && echo "scored lite300_def"
$UV lab/agentless_metric_v4.py --predictions $R/lite300_shape.jsonl \
  --out $R/metric_lite300_shape.json > $R/score_lite300_shape.log 2>&1 && echo "scored lite300_shape"
$UV lab/agentless_metric_verified.py --predictions $R/ver407_def.jsonl --expect-n 0 \
  --out $R/metric_ver407_def.json > $R/score_ver407_def.log 2>&1 && echo "scored ver407_def"
$UV lab/agentless_metric_verified.py --predictions $R/ver407_shape.jsonl --expect-n 0 \
  --out $R/metric_ver407_shape.json > $R/score_ver407_shape.log 2>&1 && echo "scored ver407_shape"
echo E25_PYTHON_SCORING_DONE
