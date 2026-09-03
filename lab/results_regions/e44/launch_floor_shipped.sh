#!/bin/bash
# E45d: --pack-floor 0.15 ALONE at SHIPPED settings (cap 16, budget 8192, no
# symbol graph) on every non-Python slice. This is what an adopted default
# would ship, and what the README scoreboard rows would become. Python gate
# already clear (Lite neutral; Verified FUNC +0.49 / LINE +1.72 / frac +.0076,
# FILE pinned). Baselines: E36/E37 *_base. Free clone dirs only
# (mswe_repos_private is held by the jsts 10752 arm).
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e44/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { slice=$1; pq=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$pq" --repos-dir "$dir" --pack-floor 0.15 \
      --report "$OUT/${slice}_fl15ship.jsonl" > "$OUT/${slice}_fl15ship.log" 2>&1
  echo "ARM_DONE ${slice}_fl15ship rc=$? $(date +%H:%M:%S)"; }
run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_base   & sleep 8
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_e23      & sleep 8
run rust $R/lab/ws3a_rust.parquet $R/lab/ws3a_repos/rust_base & sleep 8
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/ws3b_repos/c_base    & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_base  &
wait; echo E45D_DONE
