#!/bin/bash
# E30 seats-per-source, Go smoke. Two arms, one per clone dir (issue #41).
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e30-seats
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e30
INST=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/instances
PQ=/Users/nicholasarehart/programming-projects/bgrep/lab/mswe_go.parquet
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  tag=$1; dir=$2; seats=$3
  extra=""
  if [ "$seats" != "0" ]; then extra="--seats-per-source $seats"; fi
  $PY "$WT/parity/region_eval_full.py" --gold-parquet "$PQ" --repos-dir "$dir" \
      --instances "$INST/go.txt" $extra --report "$BASE/arms/go_${tag}.jsonl" \
      > "$BASE/arms/go_${tag}.log" 2>&1
  echo "ARM_DONE go_${tag} rc=$? $(date +%H:%M:%S)"
}
run s2 /Users/nicholasarehart/programming-projects/bgrep/lab/ws3b_repos/go_base 2 & sleep 10
run s3 /Users/nicholasarehart/programming-projects/bgrep/lab/ws3b_repos/go_v2   3 &
wait
echo E30_GO_SMOKE_DONE
