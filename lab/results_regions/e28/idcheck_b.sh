#!/bin/bash
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e28-breadth
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e28
OUT=$BASE/idcheck
PY="uv run --no-project --with pandas --with pyarrow python"
N=5
run() {
  slice=$1; harness=$2; parquet=$3; dir=$4
  case "$harness" in
    full) $PY "$WT/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" --limit $N --report "$OUT/${slice}_defB.jsonl" > "$OUT/${slice}_defB.log" 2>&1 ;;
    lite) $PY "$WT/parity/region_eval2.py" --repos-dir "$dir" --limit $N --report "$OUT/${slice}_defB.jsonl" > "$OUT/${slice}_defB.log" 2>&1 ;;
    ver)  $PY "$WT/parity/region_eval_verified.py" --gold-parquet "$parquet" --repos-dir "$dir" --limit $N --report "$OUT/${slice}_defB.jsonl" > "$OUT/${slice}_defB.log" 2>&1 ;;
  esac
  echo "doneB $slice rc=$?"
}
while IFS='|' read -r s h p a b; do
  case "$s" in \#*|"") continue ;; esac
  run "$s" "$h" "$p" "$b" &
  sleep 10
done < "$BASE/slices.env"
wait
echo ALL_IDCHECKB_DONE
