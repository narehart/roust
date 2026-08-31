#!/bin/bash
# E36b: the edges alone REGRESS C at the shipped cap (-1.56 full slice), because
# new Guarantee-1 seats displace other candidates inside cap 16. The 3+ gains
# were measured with cap 128 + 2hop. This arm asks whether the combination is
# net positive on FULL slices at a still-sane operating point (cap 32, 2 hops).
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e36/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; parquet=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --import-edges-v2 --import-hops 2 --max-additions 32 \
      --report "$OUT/${slice}_combo.jsonl" > "$OUT/${slice}_combo.log" 2>&1
  echo "ARM_DONE ${slice}_combo rc=$? $(date +%H:%M:%S)"
}
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/ws3b_repos/c_base    &
wait
echo E36_COMBO_DONE
