#!/bin/bash
# E28 breadth-cap gate: 16 arms = 8 slices x --max-additions {24, 32}.
# One pinned binary (built at the harness-passthrough commit, never rebuilt
# mid-run). One PRIVATE clone dir per concurrent arm (issue #41): cap 24 takes
# dir A, cap 32 takes dir B, so no two live arms ever share a working tree.
# bash, not zsh -- macOS bash 3.2 trips `set -u` on empty arrays, so no arrays.
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e28-breadth
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e28
OUT=$BASE/arms
PY="uv run --no-project --with pandas --with pyarrow python"
mkdir -p "$OUT"

run_arm() {
  slice=$1; harness=$2; parquet=$3; dir=$4; cap=$5
  tag="${slice}_m${cap}"
  case "$harness" in
    full) $PY "$WT/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
            --max-additions "$cap" --report "$OUT/${tag}.jsonl" > "$OUT/${tag}.log" 2>&1 ;;
    lite) $PY "$WT/parity/region_eval2.py" --repos-dir "$dir" \
            --max-additions "$cap" --report "$OUT/${tag}.jsonl" > "$OUT/${tag}.log" 2>&1 ;;
    ver)  $PY "$WT/parity/region_eval_verified.py" --gold-parquet "$parquet" --repos-dir "$dir" \
            --max-additions "$cap" --report "$OUT/${tag}.jsonl" > "$OUT/${tag}.log" 2>&1 ;;
  esac
  echo "ARM_DONE $tag rc=$? $(date +%H:%M:%S)"
}

while IFS='|' read -r s h p a b; do
  case "$s" in \#*|"") continue ;; esac
  run_arm "$s" "$h" "$p" "$a" 24 &
  sleep 10
  run_arm "$s" "$h" "$p" "$b" 32 &
  sleep 10
done < "$BASE/slices.env"
wait
echo ALL_ARMS_DONE
