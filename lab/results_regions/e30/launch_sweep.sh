#!/bin/bash
# E31 cap sweep on Go's >=3-gold-file stratum. FILE is budget-invariant
# (E29, re-confirmed at cap 500: 57.34 at both 8192 and 24576), so the sweep
# runs at the shipped budget and reads the FILE column only.
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e30-seats
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e30
INST=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/instances
PQ=/Users/nicholasarehart/programming-projects/bgrep/lab/mswe_go.parquet
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  cap=$1; dir=$2
  $PY "$WT/parity/region_eval_full.py" --gold-parquet "$PQ" --repos-dir "$dir" \
      --instances "$INST/go.txt" --max-additions "$cap" \
      --report "$BASE/arms/go_cap${cap}.jsonl" > "$BASE/arms/go_cap${cap}.log" 2>&1
  echo "ARM_DONE go_cap${cap} rc=$? $(date +%H:%M:%S)"
}
run "$1" /Users/nicholasarehart/programming-projects/bgrep/lab/ws3b_repos/go_base & sleep 10
run "$2" /Users/nicholasarehart/programming-projects/bgrep/lab/ws3b_repos/go_v2   &
wait
echo "E31_SWEEP_DONE $1 $2"
