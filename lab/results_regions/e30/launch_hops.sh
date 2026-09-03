#!/bin/bash
# E32 second-hop candidate generation, tested where E31 proved the admission
# cap is INERT: Java and Rust move exactly 0.00 from cap 16 to cap 32 to cap
# 128, so their gold is not in the pool at any cap. Both arms hold cap 128 so
# that any newly GENERATED candidate has room to be admitted -- otherwise a
# generation win would be invisible behind the shipped cap of 16.
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e30-seats
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e30
INST=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/instances
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; parquet=$2; dir=$3
  $PY "$WT/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --instances "$INST/${slice}.txt" --max-additions 128 --import-hops 2 \
      --report "$BASE/arms/${slice}_h2c128.jsonl" > "$BASE/arms/${slice}_h2c128.log" 2>&1
  echo "ARM_DONE ${slice}_h2c128 rc=$? $(date +%H:%M:%S)"
}
run java /Users/nicholasarehart/programming-projects/bgrep/lab/ws3b_java.parquet \
         /Users/nicholasarehart/programming-projects/bgrep/lab/ws3b_repos/java_base & sleep 8
run rust /Users/nicholasarehart/programming-projects/bgrep/lab/ws3a_rust.parquet \
         /Users/nicholasarehart/programming-projects/bgrep/lab/ws3a_repos/rust_base &
wait
echo E32_HOPS_DONE
