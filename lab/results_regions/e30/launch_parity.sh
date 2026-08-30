#!/bin/bash
# E31 parity sweep: every slice at a high admission cap, with the budget
# raised so depth is not paid out of breadth (E29: FILE is budget-invariant,
# depth is fully budget-recoverable). Python Verified is measured in the SAME
# arm, so the "Python level" bar is a like-for-like number rather than a
# cross-config comparison.
#   round A : cap 128 @ 24576  [dir A]   cap 500 @ 24576  [dir B]
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e30-seats
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e30
INST=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/instances
OUT=$BASE/arms
PY="uv run --no-project --with pandas --with pyarrow python"
mkdir -p "$OUT"
run_arm() {
  slice=$1; harness=$2; parquet=$3; dir=$4; cap=$5
  tag="p${cap}b24576"
  case "$harness" in
    full) $PY "$WT/parity/region_eval_full.py" --gold-parquet "$parquet" \
            --repos-dir "$dir" --instances "$INST/${slice}.txt" \
            --max-additions "$cap" --budget 24576 \
            --report "$OUT/${slice}_${tag}.jsonl" > "$OUT/${slice}_${tag}.log" 2>&1 ;;
    ver)  $PY "$WT/parity/region_eval_verified.py" --gold-parquet "$parquet" \
            --repos-dir "$dir" --instances "$INST/${slice}.txt" \
            --max-additions "$cap" --budget 24576 \
            --report "$OUT/${slice}_${tag}.jsonl" > "$OUT/${slice}_${tag}.log" 2>&1 ;;
  esac
  echo "ARM_DONE ${slice}_${tag} rc=$? $(date +%H:%M:%S)"
}
while IFS='|' read -r s h p a b; do
  case "$s" in \#*|"") continue ;; esac
  run_arm "$s" "$h" "$p" "$a" 128 & sleep 10
  run_arm "$s" "$h" "$p" "$b" 500 & sleep 10
done < /Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/slices.env
wait
echo "E31_PARITY_DONE $(date +%H:%M:%S)"
