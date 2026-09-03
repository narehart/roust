#!/bin/bash
# E47 adoption numbers: tail seat 40/16 ALONE at SHIPPED settings (cap 16,
# budget 8192, no symbol graph) on the six MSWE slices -- what the README
# rows become if the default flips. Baselines: E36/E37 *_base. Compare and
# FUNCTION/LINE scoring chained per slice. Free *_base clone dirs.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e47/arms
PY="uv run --no-project --with pandas --with pyarrow python"
run() { slice=$1; pq=$2; dir=$3
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$pq" --repos-dir "$dir" --tail-seat-tokens 40 --tail-seat-after 16 \
      --report "$OUT/${slice}_ts40ship.jsonl" > "$OUT/${slice}_ts40ship.log" 2>&1
  echo "ARM_DONE ${slice}_ts40ship rc=$? $(date +%H:%M:%S)"
  b=$R/lab/results_regions/e37/arms/${slice}_base.jsonl; [ -f $b ] || b=$R/lab/results_regions/e36/arms/${slice}_base.jsonl
  uv run --no-project --with scipy python $R/lab/results_regions/e44/compare.py $b $OUT/${slice}_ts40ship.jsonl "$slice shipped -> tail seat 40 @cap16"; }
run go   $R/lab/mswe_go.parquet   $R/lab/ws3b_repos/go_base   & sleep 8
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_e23      & sleep 8
run rust $R/lab/ws3a_rust.parquet $R/lab/ws3a_repos/rust_base & sleep 8
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base & sleep 8
run c    $R/lab/mswe_c.parquet    $R/lab/ws3b_repos/c_base    & sleep 8
run cpp  $R/lab/mswe_cpp.parquet  $R/lab/ws3a_repos/cpp_base  &
wait; echo E47_SHIP_ARMS_DONE
for s in go jsts rust java c cpp; do bash $R/lab/results_regions/e44/score.sh $s $OUT/${s}_ts40ship.jsonl:ts40ship; done
echo E47_SHIP_SCORED
