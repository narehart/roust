#!/bin/bash
# E30 round 2, Go: does ownership diversity help when there IS room?
# Round 1 showed seats>1 at the shipped cap 16 only DISPLACES tail-fill
# candidates (guarantees run before the `additions.len() >= max_additions`
# break), so it changed composition at constant breadth. These two arms hold
# the cap at 32 -- E28's setting, Go 37.06 -- so the extra seats are additive.
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e30-seats
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e30
INST=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/instances
PQ=/Users/nicholasarehart/programming-projects/bgrep/lab/mswe_go.parquet
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  tag=$1; dir=$2; seats=$3
  $PY "$WT/parity/region_eval_full.py" --gold-parquet "$PQ" --repos-dir "$dir" \
      --instances "$INST/go.txt" --max-additions 32 --seats-per-source "$seats" \
      --report "$BASE/arms/go_${tag}.jsonl" > "$BASE/arms/go_${tag}.log" 2>&1
  echo "ARM_DONE go_${tag} rc=$? $(date +%H:%M:%S)"
}
run c32s2 /Users/nicholasarehart/programming-projects/bgrep/lab/ws3b_repos/go_base 2 & sleep 10
run c32s3 /Users/nicholasarehart/programming-projects/bgrep/lab/ws3b_repos/go_v2   3 &
wait
echo E30_GO_ROUND2_DONE
