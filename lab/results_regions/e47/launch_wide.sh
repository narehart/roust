#!/bin/bash
# E47 wide: sg + cap 32 @ shipped budget with tiered seats (T from the Rust
# smoke, $1) on the other five slices. FILE must equal each slice's E37
# sg32 arm; compare chained per arm. One arm per clone dir.
set -uo pipefail
T=${1:?usage: launch_wide.sh <tail-seat-tokens>}
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e47/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { slice=$1; pq=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$pq" --repos-dir "$dir" \
      --symbol-graph --max-additions 32 --tail-seat-tokens "$T" --tail-seat-after 16 \
      --report "$OUT/${slice}_ts${T}.jsonl" > "$OUT/${slice}_ts${T}.log" 2>&1
  echo "ARM_DONE ${slice}_ts${T} rc=$? $(date +%H:%M:%S)"
  uv run --no-project --with scipy python $R/lab/results_regions/e44/compare.py $R/lab/results_regions/e37/arms/${slice}_sg32.jsonl $OUT/${slice}_ts${T}.jsonl "$slice sg32 -> tail seat $T"; }
run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_v2    & sleep 8
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_private  & sleep 8
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_v2  & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/e26_repos/c_ext     & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_v2   &
wait; echo "E47_WIDE_DONE T=$T"
