#!/bin/bash
# WS2 gate launcher: 12 arms, 12s stagger (e23 guard lesson), all detached.
set -u
B=/Users/nicholasarehart/programming-projects/bgrep-worktrees/ws2-grammar-batch
M=/Users/nicholasarehart/programming-projects/bgrep-worktrees/ws2-main-baseline
R=$B/lab/results_regions/ws2
launch() { wt=$1; lang=$2; arm=$3; repos=$4; shift 4
  nohup uv run --with pandas --with pyarrow python $wt/parity/region_eval_full.py \
    --gold-parquet $B/lab/mswe_$lang.parquet \
    --repos-dir $B/lab/ws2_repos/$repos \
    --report $R/mswe_${lang}_${arm}.jsonl "$@" \
    > $R/mswe_${lang}_${arm}.log 2>&1 &
  echo "launched ${lang}_${arm} pid $!"
  sleep 12
}
launch $M go   base go_base
launch $B go   exp  go_exp
launch $M rust base rust_base
launch $B rust exp  rust_exp
launch $M java base java_base
launch $B java exp  java_exp
launch $M cpp  main cpp_base
launch $B cpp  idx  cpp_idx --cfamily-ext --no-structural-blocks
launch $B cpp  exp  cpp_exp --cfamily-ext
launch $M c    main c_base
launch $B c    idx  c_idx --cfamily-ext --no-structural-blocks
launch $B c    exp  c_exp --cfamily-ext
echo LAUNCHES_DONE
