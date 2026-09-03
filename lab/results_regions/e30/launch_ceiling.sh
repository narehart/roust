#!/bin/bash
# E31 admission ceiling. If the multi-file gap were admission-bound, an
# effectively unbounded cap would close it. Whatever all-gold FILE plateaus
# at here is the POOL's ceiling: the residue above it is gold the candidate
# generator never proposes, which no admission or re-ranking lever can reach.
# Two arms so the ceiling is measured at both a shipped and a generous budget
# (E29: the file set is budget-invariant, so these should agree -- and if they
# do not, that falsifies E29 rather than this).
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e30-seats
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e30
INST=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/instances
PQ=/Users/nicholasarehart/programming-projects/bgrep/lab/mswe_go.parquet
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  tag=$1; dir=$2; cap=$3; bud=$4
  extra="--max-additions $cap"
  if [ "$bud" != "0" ]; then extra="$extra --budget $bud"; fi
  $PY "$WT/parity/region_eval_full.py" --gold-parquet "$PQ" --repos-dir "$dir" \
      --instances "$INST/go.txt" $extra --report "$BASE/arms/go_${tag}.jsonl" \
      > "$BASE/arms/go_${tag}.log" 2>&1
  echo "ARM_DONE go_${tag} rc=$? $(date +%H:%M:%S)"
}
run cap500       /Users/nicholasarehart/programming-projects/bgrep/lab/ws3b_repos/go_base 500 0     & sleep 10
run cap500b24576 /Users/nicholasarehart/programming-projects/bgrep/lab/ws3b_repos/go_v2   500 24576 &
wait
echo E31_CEILING_DONE
