#!/bin/bash
set -u
P=/Users/nicholasarehart/programming-projects/bgrep
R=$P/lab/results_regions/e26
UV="uv run --no-project --with pandas --with pyarrow python"
c() { $UV $P/lab/e26_census.py --slice "$1" --parquet "$P/$2" --repos-dir "$P/$3" \
        --out "$R/census_$1.json" > /dev/null 2>&1; echo "census_$1 exit=$?"; }
c jsts        lab/mswe_jsts.parquet              lab/mswe_repos_e23
c java        lab/ws3b_java.parquet              lab/ws3b_repos/java_base
c rust        lab/ws3a_rust.parquet              lab/ws3a_repos/rust_base
c c           lab/mswe_c.parquet                 lab/ws3b_repos/c_base
c cpp         lab/mswe_cpp.parquet               lab/ws3a_repos/cpp_base
c python_lite lab/swebench_lite.parquet          lab/ws3a_repos/repos_lite_base
c python_ver  lab/swebench_verified_heldout.parquet lab/ws3a_repos/repos_ver_base
echo E26_CENSUS_DONE
