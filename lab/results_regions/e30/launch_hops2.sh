#!/bin/bash
# E32 second-hop generation across the remaining slices, cap 128 so newly
# generated candidates have room to be admitted. Rust: 27.62 -> 33.33.
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e30-seats
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e30
INST=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/instances
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; harness=$2; parquet=$3; dir=$4
  case "$harness" in
   full) $PY "$WT/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --instances "$INST/${slice}.txt" --max-additions 128 --import-hops 2 \
      --report "$BASE/arms/${slice}_h2c128.jsonl" > "$BASE/arms/${slice}_h2c128.log" 2>&1 ;;
   ver)  $PY "$WT/parity/region_eval_verified.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --instances "$INST/${slice}.txt" --max-additions 128 --import-hops 2 \
      --report "$BASE/arms/${slice}_h2c128.jsonl" > "$BASE/arms/${slice}_h2c128.log" 2>&1 ;;
  esac
  echo "ARM_DONE ${slice}_h2c128 rc=$? $(date +%H:%M:%S)"
}
R=/Users/nicholasarehart/programming-projects/bgrep
run jsts full $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_e23     & sleep 8
run go   full $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_base & sleep 8
run c    full $R/lab/mswe_c.parquet    $R/lab/ws3b_repos/c_base  & sleep 8
run cpp  full $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_base & sleep 8
run ver  ver  $R/lab/swebench_verified_heldout.parquet $R/lab/ws3a_repos/repos_ver_base &
wait
echo E32_HOPS2_DONE
