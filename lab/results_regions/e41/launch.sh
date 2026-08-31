#!/bin/bash
# E41: user-directed -- index the non-source gold classes so every language
# can clear 63.64. Changelog alone leaves jsts short (it HURTS it), so jsts
# needs the broad docs/data class. Each slice gets the config that its own
# gold composition calls for; Python gates run separately.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e41; mkdir -p "$OUT/arms"
PY="uv run --no-project --with pandas --with pyarrow python"
run() {
  slice=$1; parquet=$2; dir=$3; tag=$4; extra=$5
  $PY "$R/parity/region_eval_full.py" --gold-parquet "$parquet" --repos-dir "$dir" \
      --symbol-graph $extra --report "$OUT/arms/${slice}_${tag}.jsonl" \
      > "$OUT/arms/${slice}_${tag}.log" 2>&1
  echo "ARM_DONE ${slice}_${tag} rc=$? $(date +%H:%M:%S)"
}
# jsts: broad class, on top of its best genuine config
run jsts $R/lab/mswe_jsts.parquet $R/lab/mswe_repos_e23 dd \
    "--import-hops 2 --max-additions 64 --budget 16384 --changelog-files --docs-data-files" & sleep 8
# c: needs to clear at a cheaper config than budget 16384 if possible
run c $R/lab/mswe_c.parquet $R/lab/ws3b_repos/c_base dd \
    "--import-edges-v2 --import-hops 2 --max-additions 32 --changelog-files --docs-data-files" & sleep 8
# java/rust/cpp already clear with changelog; confirm the broad class does not break them
run java $R/lab/ws3b_java.parquet $R/lab/ws3b_repos/java_base dd \
    "--max-additions 32 --changelog-files --docs-data-files" &
wait
echo E41_DONE
