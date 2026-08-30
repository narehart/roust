#!/bin/bash
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e28-breadth
OUT=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e28/idcheck
PY="uv run --no-project --with pandas --with pyarrow python"
mkdir -p "$OUT"
N=5
run() {
  slice=$1; harness=$2; parquet=$3; dir=$4
  case "$harness" in
    full) $PY "$WT/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
            --limit $N --report "$OUT/${slice}_def.jsonl" > "$OUT/${slice}_def.log" 2>&1 ;;
    lite) $PY "$WT/parity/region_eval2.py" --repos-dir "$dir" \
            --limit $N --report "$OUT/${slice}_def.jsonl" > "$OUT/${slice}_def.log" 2>&1 ;;
    ver)  $PY "$WT/parity/region_eval_verified.py" --gold-parquet "$parquet" --repos-dir "$dir" \
            --limit $N --report "$OUT/${slice}_def.jsonl" > "$OUT/${slice}_def.log" 2>&1 ;;
  esac
  echo "done $slice rc=$?"
}
grep -v '^#' /Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e28/slices.env | while IFS='|' read -r s h p a b; do
  run "$s" "$h" "$p" "$a" &
  sleep 10
done
wait
echo ALL_IDCHECK_DONE
