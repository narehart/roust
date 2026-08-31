#!/bin/bash
# E36 dual gate for --import-edges-v2: SWE-bench Lite 300 + Verified 407, at
# the shipped operating point. This gate is LOAD-BEARING rather than a
# formality: the new resolution fires on .c/.cpp/.h, and Python repos DO
# contain those under the adopted --cfamily-ext default (numpy, pandas), so
# the flag can move Python numbers even though no .py branch changed.
# Private clone dirs per arm (issue #41): never lab/swebench_repos itself.
set -uo pipefail
R=/Users/nicholasarehart/programming-projects/bgrep
OUT=$R/lab/results_regions/e36/arms
PY="uv run --no-project --with pandas --with pyarrow python"
lite() {
  tag=$1; dir=$2; extra=$3
  $PY "$R/parity/region_eval2.py" --repos-dir "$dir" $extra \
      --report "$OUT/lite_${tag}.jsonl" > "$OUT/lite_${tag}.log" 2>&1
  echo "ARM_DONE lite_${tag} rc=$? $(date +%H:%M:%S)"
}
ver() {
  tag=$1; dir=$2; extra=$3
  $PY "$R/parity/region_eval_verified.py" --repos-dir "$dir" $extra \
      --report "$OUT/ver_${tag}.jsonl" > "$OUT/ver_${tag}.log" 2>&1
  echo "ARM_DONE ver_${tag} rc=$? $(date +%H:%M:%S)"
}
lite base $R/lab/swebench_repos_e20a ""                  & sleep 8
lite ie2  $R/lab/swebench_repos_e20b "--import-edges-v2" & sleep 8
ver  base $R/lab/ws3a_repos/repos_ver_base ""                  & sleep 8
ver  ie2  $R/lab/ws3a_repos/repos_ver_v2   "--import-edges-v2" &
wait
echo E36_GATE_DONE
