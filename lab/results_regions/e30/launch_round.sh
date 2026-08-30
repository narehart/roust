#!/bin/bash
# E30 seats-per-source, full gate. Same discipline as E29:
#   * at most 2 live arms per slice, arm-A on repos_dir_A and arm-B on
#     repos_dir_B, so no two live arms ever share a clone dir (issue #41);
#   * one pinned binary, built once in the e30-seats worktree, never rebuilt
#     mid-run (provenance = binary SHA vs that worktree's HEAD);
#   * bash, not zsh -- macOS bash 3.2 trips `set -u` on empty arrays, and zsh
#     does not word-split unquoted $extra, which silently drops the flag.
#
#   round 1 : b1 = seats 1 (identity gate vs E29 a1)  [dir A]
#             b2 = seats 2                            [dir B]
#   round 2 : b3 = seats 3                            [dir A]
#
# seats=0 is the harness sentinel meaning "forward no flag at all", so b1's
# argv is byte-identical to every pre-E30 default arm's.
set -uo pipefail
WT=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e30-seats
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e30
INST=/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/instances
OUT=$BASE/arms
PY="uv run --no-project --with pandas --with pyarrow python"
ROUND=${1:?usage: launch_round.sh <1|2>}
mkdir -p "$OUT"

run_arm() {
  slice=$1; harness=$2; parquet=$3; dir=$4; tag=$5; seats=$6
  extra=""
  if [ "$seats" != "0" ]; then extra="--seats-per-source $seats"; fi
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
    run_arm "$s" "$h" "$p" "$a" b1_s1 0 & sleep 10
    run_arm "$s" "$h" "$p" "$b" b2_s2 2 & sleep 10
  else
    run_arm "$s" "$h" "$p" "$a" b3_s3 3 & sleep 10
  fi
done < "/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions/e29/slices.env"
wait
echo "ALL_ARMS_DONE round=$ROUND $(date +%H:%M:%S)"
