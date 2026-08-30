#!/bin/bash
# E27b conditioning probes, reproduced from the instance ids E27 itself
# identified -- 3 Lite instances the seats HARMED (all n_gold=1) and 5 Go
# instances the seats HELPED. The question is whether any gate suppresses the
# former without reverting the latter.
#
# Binary: roust 0.3.2 (94be546, clean), built in its own worktree so the
# pinned E27 binary (d5263f6) is untouched. Harness runs FROM that worktree so
# the engine-provenance guard sees a matching sha. Bash, not zsh.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WB=/private/tmp/e27b-wt
R=$P/lab/results_regions/e27b
UV="uv run --no-project --with pandas --with pyarrow python"

lite() { name=$1; shift
  $UV $WB/parity/region_eval2.py --repos-dir $P/lab/ws3a_repos/repos_lite_base \
    --instances $R/lite_harms.txt --report $R/$name.jsonl "$@" > $R/$name.log 2>&1
  echo "lite $name exit=$?"
}
go() { name=$1; shift
  $UV $WB/parity/region_eval_full.py --gold-parquet $P/lab/mswe_go.parquet \
    --repos-dir $P/lab/ws3b_repos/go_base --shard 1/1 \
    --instances $R/go_wins.txt --report $R/$name.jsonl "$@" > $R/$name.log 2>&1
  echo "go $name exit=$?"
}

# --- probe 1: does the BREADTH gate suppress the Lite harms? ---
lite L_def
lite L_s2      --cochange-seats 2 --cochange-seat-min 2
lite L_s2_b2   --cochange-seats 2 --cochange-seat-min 2 --cochange-seat-breadth 2
lite L_s2_b4   --cochange-seats 2 --cochange-seat-min 2 --cochange-seat-breadth 4
lite L_s2_b8   --cochange-seats 2 --cochange-seat-min 2 --cochange-seat-breadth 8

# --- probe 2: does raising the EVIDENCE threshold suppress them, and what
# --- does it cost on the Go instances the seats helped? ---
lite L_s2_min10 --cochange-seats 2 --cochange-seat-min 10
go   G_def
go   G_s2       --cochange-seats 2 --cochange-seat-min 2
go   G_s2_min10 --cochange-seats 2 --cochange-seat-min 10

echo E27B_PROBE_DONE
