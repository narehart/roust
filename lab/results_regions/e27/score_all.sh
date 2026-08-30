#!/bin/bash
# E27 scoring: metric JSON per arm, then paired stats + seat anatomy per
# (slice, seats) pair against that slice's own same-binary default arm.
#
# Scoring uses lab/agentless_metric_full.py with --repos-dir --ts-functions
# --lang-functions for the MSWE slices (never lab/agentless_metric.py, which
# ignores its CLI args), and the v4 / verified scorers for Python.
# Bash, not zsh.
# Re-runnable: every arm is guarded on its EXPECTED row count, so an arm that
# is still in flight is skipped with a loud INCOMPLETE line instead of being
# scored on a partial JSONL. Run it again when the stragglers land.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
R=$P/lab/results_regions/e27
UVP="uv run --no-project --with pandas --with pyarrow python"
# The FUNCTION-exact metric parses gold+predicted files with tree-sitter, so
# the MSWE scorer needs every grammar the --lang-functions batch covers.
# Without these it dies on `No module named tree_sitter` (E25/E26 dep set).
UVT="uv run --no-project --with pandas --with pyarrow --with tree-sitter \
  --with tree-sitter-javascript --with tree-sitter-typescript --with tree-sitter-java \
  --with tree-sitter-go --with tree-sitter-rust --with tree-sitter-c --with tree-sitter-cpp python"
UVS="uv run --no-project --with pandas --with pyarrow --with scipy python"

# slice parquet repos_dir expect_n
mswe_meta() {
  case $1 in
    # NOT mswe_repos_e23 / mswe_repos_private: those two carry the live jsts
    # arms and are being checked out under us. Scoring only does read-only
    # `git show` walks, but issue #41 discipline is that a dir with a live
    # arm in it is off limits, so scoring reads the third (idle) jsts clone.
    jsts) echo "lab/mswe_jsts.parquet lab/e26_repos/jsts_guard 580";;
    go)   echo "lab/mswe_go.parquet lab/ws3b_repos/go_base 428";;
    rust) echo "lab/ws3a_rust.parquet lab/ws3a_repos/rust_base 239";;
    cpp)  echo "lab/mswe_cpp.parquet lab/ws3a_repos/cpp_base 129";;
    java) echo "lab/ws3b_java.parquet lab/ws3b_repos/java_base 128";;
    c)    echo "lab/mswe_c.parquet lab/ws3b_repos/c_base 128";;
  esac
}

# scored <metric_json> <arm_jsonl> -- true when a VALID metric JSON already
# exists and is newer than the arm it scores. Makes stage 1 idempotent so a
# re-run only computes what is genuinely missing (the AST walks are the
# expensive part of this round).
scored_already() {
  [ -s "$1" ] || return 1
  [ "$1" -nt "$2" ] || return 1
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d['all_instances']['function']['detail'] is not None else 1)" "$1" 2>/dev/null
}

# complete <jsonl> <expected_rows>
complete() {
  [ -s "$1" ] || return 1
  local got
  got=$(wc -l < "$1" | tr -d " ")
  [ "$got" = "$2" ]
}

echo "=== stage 1: metric JSON per arm ==="
for s in jsts go rust cpp java c; do
  set -- $(mswe_meta $s); parquet=$1; repos=$2; n=$3
  for arm in s0 s2 s3 s4; do
    if scored_already "$R/metric_${s}_${arm}.json" "$R/${s}_${arm}.jsonl"; then
      echo "cached ${s}_${arm}"
    elif complete "$R/${s}_${arm}.jsonl" "$n"; then
      $UVT $P/lab/agentless_metric_full.py \
        --predictions "$R/${s}_${arm}.jsonl" --gold-parquet "$P/$parquet" \
        --repos-dir "$P/$repos" --expect-n "$n" --ts-functions --lang-functions \
        --out "$R/metric_${s}_${arm}.json" > "$R/metric_${s}_${arm}.log" 2>&1
      echo "scored ${s}_${arm} exit=$?"
    else
      echo "INCOMPLETE ${s}_${arm}.jsonl ($(wc -l < "$R/${s}_${arm}.jsonl" 2>/dev/null | tr -d ' ')/$n) -- skipped"
    fi
  done
done
for arm in s0 s2 s3 s4; do
  if scored_already "$R/metric_lite_${arm}.json" "$R/lite_${arm}.jsonl"; then
    echo "cached lite_${arm}"
  elif complete "$R/lite_${arm}.jsonl" 300; then
    $UVT $P/lab/agentless_metric_v4.py --predictions "$R/lite_${arm}.jsonl" \
      --out "$R/metric_lite_${arm}.json" > "$R/metric_lite_${arm}.log" 2>&1
    echo "scored lite_${arm} exit=$?"
  else
    echo "INCOMPLETE lite_${arm}.jsonl -- skipped"
  fi
  if scored_already "$R/metric_ver_${arm}.json" "$R/ver_${arm}.jsonl"; then
    echo "cached ver_${arm}"
  elif complete "$R/ver_${arm}.jsonl" 407; then
    $UVT $P/lab/agentless_metric_verified.py --predictions "$R/ver_${arm}.jsonl" \
      --gold-parquet "$P/lab/swebench_verified_heldout.parquet" --expect-n 407 \
      --out "$R/metric_ver_${arm}.json" > "$R/metric_ver_${arm}.log" 2>&1
    echo "scored ver_${arm} exit=$?"
  else
    echo "INCOMPLETE ver_${arm}.jsonl -- skipped"
  fi
done

echo "=== stage 2: paired stats + seat anatomy ==="
pair() {
  local s=$1 arm=$2 parquet=$3
  if [ ! -s "$R/metric_${s}_${arm}.json" ] || [ ! -s "$R/metric_${s}_s0.json" ]; then
    echo "SKIP pair ${s}_${arm} (metric missing)"; return
  fi
  $UVS $P/lab/e27_paired.py --label "${s}_${arm}" \
    --def-jsonl "$R/${s}_s0.jsonl" --arm-jsonl "$R/${s}_${arm}.jsonl" \
    --def-metric "$R/metric_${s}_s0.json" --arm-metric "$R/metric_${s}_${arm}.json" \
    --out-prefix "$R/${s}_${arm}" > "$R/paired_${s}_${arm}.txt" 2>&1
  echo "paired ${s}_${arm} exit=$?"
  $UVP $P/lab/e27_seats.py --label "${s}_${arm}" \
    --trace "$R/trace_${s}_${arm}.jsonl" \
    --def-jsonl "$R/${s}_s0.jsonl" --arm-jsonl "$R/${s}_${arm}.jsonl" \
    --gold-parquet "$P/$parquet" --out "$R/seats_${s}_${arm}.json" \
    > "$R/seats_${s}_${arm}.txt" 2>&1
  echo "seats ${s}_${arm} exit=$?"
}

for s in jsts go rust cpp java c; do
  set -- $(mswe_meta $s); parquet=$1
  for arm in s2 s3 s4; do pair "$s" "$arm" "$parquet"; done
done
for arm in s2 s3 s4; do
  pair lite "$arm" lab/swebench_lite.parquet
  pair ver  "$arm" lab/swebench_verified_heldout.parquet
done

echo E27_SCORING_DONE
