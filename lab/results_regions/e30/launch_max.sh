#!/bin/bash
# E33 maximum-generation ceiling. Everything the campaign has found that can
# add candidates, all on at once: cap 500, 2-hop generation, Java/C-family
# import edges, and the pool eligibility floor dropped 0.15 -> 0.02 (the cut
# runs BEFORE admission, so it bounds every cap and no admission lever can
# reach past it). This is a CEILING probe, not a proposal: it is the number
# that says whether per-language parity is attainable at any setting.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
BASE=$R/lab/results_regions/e30
INST=$R/lab/results_regions/e29/instances
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; harness=$2; parquet=$3; dir=$4
  case "$harness" in
   full) $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --instances "$INST/${slice}.txt" --max-additions 500 --import-hops 2 \
      --import-edges-v2 --eligible-floor 0.02 \
      --report "$BASE/arms/${slice}_max.jsonl" > "$BASE/arms/${slice}_max.log" 2>&1 ;;
   ver)  $PY "$R/parity/region_eval_verified.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --instances "$INST/${slice}.txt" --max-additions 500 --import-hops 2 \
      --import-edges-v2 --eligible-floor 0.02 \
      --report "$BASE/arms/${slice}_max.jsonl" > "$BASE/arms/${slice}_max.log" 2>&1 ;;
  esac
  echo "ARM_DONE ${slice}_max rc=$? $(date +%H:%M:%S)"
}
run java full $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base & sleep 8
run c    full $R/lab/mswe_c.parquet    $R/lab/ws3b_repos/c_base    & sleep 8
run cpp  full $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_base  & sleep 8
run rust full $R/lab/ws3a_rust.parquet $R/lab/ws3a_repos/rust_base & sleep 8
run ver  ver  $R/lab/swebench_verified_heldout.parquet $R/lab/ws3a_repos/repos_ver_base &
wait
echo E33_MAX_DONE
