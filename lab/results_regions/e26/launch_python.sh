#!/bin/bash
# E26 python inertness check. NOT a full 707-instance arm: the census shows
# sympy is the ONLY Python-bench repo that contains an EXT_V2 file at all
# (bin/test_pyodide.mjs, 1 file, present in just 5/74 Lite and 6/53 Verified
# base commits), and ZERO Python gold files carry an EXT_V2 suffix. So the
# check runs every sympy instance (77 Lite / 53 Verified) plus 11 non-sympy
# controls each, flag OFF and flag ON, TWICE per arm -- the repeat run is the
# determinism control that makes "payload hashes match" mean something.
# Pinned worktree harness+binary at fcb2562 (= the 5ebd6ab engine).
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
WB=/Users/nicholasarehart/programming-projects/bgrep-worktrees/e26-ext-coverage
R=$P/lab/results_regions/e26
UV="uv run --no-project --with pandas --with pyarrow python"

run_lite() { # $1=tag $2=extra flags
  $UV $WB/parity/region_eval2.py --repos-dir $P/lab/ws3a_repos/repos_lite_v2 \
    --instances $R/py_lite_instances.txt $2 --report $R/py_lite_$1.jsonl \
    > $R/py_lite_$1.log 2>&1
  echo "py_lite_$1 exit=$?"
}
run_ver() {
  $UV $WB/parity/region_eval_verified.py --repos-dir $P/lab/ws3a_repos/repos_ver_v2 \
    --instances $R/py_ver_instances.txt $2 --report $R/py_ver_$1.jsonl \
    > $R/py_ver_$1.log 2>&1
  echo "py_ver_$1 exit=$?"
}

( run_lite off_a ""; run_lite off_b ""; run_lite on_a "--ext-v2"; run_lite on_b "--ext-v2"
  echo E26_PY_LITE_DONE ) > $R/py_lite_wave.log 2>&1 &
echo "lite wave pid=$!"
sleep 10
( run_ver off_a ""; run_ver off_b ""; run_ver on_a "--ext-v2"; run_ver on_b "--ext-v2"
  echo E26_PY_VER_DONE ) > $R/py_ver_wave.log 2>&1 &
echo "ver wave pid=$!"
echo E26_PYTHON_LAUNCHED
