#!/bin/bash
# E31 parity sweep, lean redesign. The first attempt ran 14 arms at cap 500 +
# budget 24576 concurrently and starved itself (+5 records in 15 min); it was
# killed. This round exploits E29's budget-invariance of the FILE column --
# re-confirmed at cap 500 (57.34 at both 8192 and 24576) -- so the parity
# question is answered at the SHIPPED budget, which is far cheaper to pack.
# One arm per slice, cap 128 (Go: 52.45 of the 57.34 ceiling), dir A only, so
# no two live arms share a clone dir.
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e30-seats
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e30
INST=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/instances
OUT=$BASE/arms
PY="uv run --no-project --with pandas --with pyarrow python"
mkdir -p "$OUT"
run_arm() {
  slice=$1; harness=$2; parquet=$3; dir=$4
  case "$harness" in
    full) $PY "$WT/parity/region_eval_full.py" --gold-parquet "$parquet" \
            --repos-dir "$dir" --instances "$INST/${slice}.txt" --max-additions 128 \
            --report "$OUT/${slice}_q128.jsonl" > "$OUT/${slice}_q128.log" 2>&1 ;;
    ver)  $PY "$WT/parity/region_eval_verified.py" --gold-parquet "$parquet" \
            --repos-dir "$dir" --instances "$INST/${slice}.txt" --max-additions 128 \
            --report "$OUT/${slice}_q128.jsonl" > "$OUT/${slice}_q128.log" 2>&1 ;;
  esac
  echo "ARM_DONE ${slice}_q128 rc=$? $(date +%H:%M:%S)"
}
while IFS='|' read -r s h p a b; do
  case "$s" in \#*|"") continue ;; esac
  run_arm "$s" "$h" "$p" "$a" & sleep 8
done < /Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/slices.env
wait
echo "E31_PARITY2_DONE $(date +%H:%M:%S)"
