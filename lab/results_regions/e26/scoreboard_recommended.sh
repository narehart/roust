#!/bin/bash
# E26 goal scoreboard under the RECOMMENDED config:
#   c    -> --ext-v2 + fixture guard  (.pony is the slice's only EXT_V2 suffix)
#   java -> --ext-v2 + fixture guard  (.rb   is the slice's only EXT_V2 suffix)
#   jsts/rust/cpp/go/python -> DEFAULT (no ext-v2): jsts is measurably harmed
#   even guarded; rust/cpp/go/python have zero EXT_V2 gold.
set -u
P=/Users/nicholasarehart/programming-projects/bgrep; cd $P
R=$P/lab/results_regions/e26; R25=$P/lab/results_regions/e25
UV="uv run --no-project --with pandas --with pyarrow python"
$UV lab/e26_scoreboard.py \
  --arm "c (ext-v2+guard):$R/c_guard.jsonl:$R/metric_c_guard.json" \
  --arm "java (ext-v2+guard):$R/java_guard.jsonl:$R/metric_java_guard.json" \
  --arm "jsts (default):$R25/jsts_def.jsonl:$R25/metric_jsts_def.json" \
  --arm "rust (default):$R25/rust_def.jsonl:$R25/metric_rust_def.json" \
  --arm "cpp (default):$R25/cpp_def.jsonl:$R25/metric_cpp_def.json" \
  --arm "go (default):$R25/go_def.jsonl:$R25/metric_go_def.json" \
  --arm "python Lite:$R25/lite300_def.jsonl:$R25/metric_lite300_def.json" \
  --arm "python Verified:$R25/ver407_def.jsonl:$R25/metric_ver407_def.json" \
  --out $R/scoreboard_recommended.json
