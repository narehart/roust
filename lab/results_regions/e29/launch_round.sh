#!/bin/bash
# E29 cost-of-parity curve. Arms are launched in ROUNDS of at most 2 per slice
# so that no two live arms ever share a clone directory (issue #41): within a
# round, arm-A takes repos_dir_A and arm-B takes repos_dir_B.
#
#   round 1 : a1 = default (cap 16, budget 8192)   [dir A]
#             a2 = cap 32, budget 8192   (= E28)   [dir B]
#   round 2 : a3 = cap 32, budget 16384            [dir A]
#             a4 = cap 32, budget 24576            [dir B]
#   round 3 : a5 = cap 16, budget 24576  (decomp)  [dir A]
#
# a1 and a2 forward argv byte-identical to E27 `_s0` / E28 `_m32` respectively
# (the harness sentinels mean "forward no flag at all"), so both are gated for
# payload identity against those records before any new arm is believed.
#
# One pinned binary at 5696ad6, built once, never rebuilt mid-run.
# bash, not zsh -- macOS bash 3.2 trips `set -u` on empty arrays, so no arrays.
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e29-parity
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29
OUT=$BASE/arms
INST=$BASE/instances
PY="uv run --no-project --with pandas --with pyarrow python"
ROUND=${1:?usage: launch_round.sh <1|2|3>}
mkdir -p "$OUT"

# run_arm <slice> <harness> <parquet> <dir> <tag> <cap> <budget>
# cap/budget of 0 = pass the flag not at all (harness sentinel).
run_arm() {
  slice=$1; harness=$2; parquet=$3; dir=$4; tag=$5; cap=$6; bud=$7
  extra=""
  if [ "$cap" != "0" ]; then extra="$extra --max-additions $cap"; fi
  if [ "$bud" != "0" ]; then extra="$extra --budget $bud"; fi
  case "$harness" in
    full) $PY "$WT/parity/region_eval_full.py" --gold-parquet "$parquet" \
            --repos-dir "$dir" --instances "$INST/${slice}.txt" $extra \
            --report "$OUT/${slice}_${tag}.jsonl" > "$OUT/${slice}_${tag}.log" 2>&1 ;;
    ver)  $PY "$WT/parity/region_eval_verified.py" --gold-parquet "$parquet" \
            --repos-dir "$dir" --instances "$INST/${slice}.txt" $extra \
            --report "$OUT/${slice}_${tag}.jsonl" > "$OUT/${slice}_${tag}.log" 2>&1 ;;
  esac
  echo "ARM_DONE ${slice}_${tag} rc=$? $(date +%H:%M:%S)"
}

while IFS='|' read -r s h p a b; do
  case "$s" in \#*|"") continue ;; esac
  if [ "$ROUND" = "1" ]; then
    run_arm "$s" "$h" "$p" "$a" a1_c16b8192  0  0     & sleep 10
    run_arm "$s" "$h" "$p" "$b" a2_c32b8192  32 0     & sleep 10
  elif [ "$ROUND" = "2" ]; then
    run_arm "$s" "$h" "$p" "$a" a3_c32b16384 32 16384 & sleep 10
    run_arm "$s" "$h" "$p" "$b" a4_c32b24576 32 24576 & sleep 10
  else
    run_arm "$s" "$h" "$p" "$a" a5_c16b24576 0  24576 & sleep 10
  fi
done < "$BASE/slices.env"
wait
echo "ALL_ARMS_DONE round=$ROUND $(date +%H:%M:%S)"
