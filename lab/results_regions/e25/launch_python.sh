#!/bin/bash
# E25 wave 3: Lite-300 + Verified-407, default vs --shape-blocks.
# NOT a formality: the identity gate found 6/60 Python-bench instances
# DIFFER under shape (all matplotlib/sphinx -- repos that bundle .js/.cpp,
# which DO reach the shape branch even though .py never does). So the
# Python rows must be measured on full arms, not asserted inert.
# Pinned abb96af harness+binary; private repo dir per arm. Bash, not zsh.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e25-shape-blocks
R=$P/lab/results_regions/e25
UV="uv run --no-project --with pandas --with pyarrow python"

launch() { name=$1; shift
  nohup "$@" > "$R/$name.log" 2>&1 &
  echo "launched $name pid=$!"
  sleep 10
}

launch lite300_def   $UV $WB/parity/region_eval2.py \
  --repos-dir $P/lab/ws3a_repos/repos_lite_base --report $R/lite300_def.jsonl
launch lite300_shape $UV $WB/parity/region_eval2.py \
  --repos-dir $P/lab/ws3a_repos/repos_lite_v2 --shape-blocks --report $R/lite300_shape.jsonl
launch ver407_def    $UV $WB/parity/region_eval_verified.py \
  --repos-dir $P/lab/ws3a_repos/repos_ver_base --report $R/ver407_def.jsonl
launch ver407_shape  $UV $WB/parity/region_eval_verified.py \
  --repos-dir $P/lab/ws3a_repos/repos_ver_v2 --shape-blocks --report $R/ver407_shape.jsonl
echo E25_PYTHON_LAUNCHED
