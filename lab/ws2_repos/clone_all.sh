#!/bin/bash
# WS2 private clones: lab/ws2_repos/<lang>_base/<org>__<repo>
set -u
BASE=/Users/nicholasarehart/programming-projects/bgrep-worktrees/ws2-grammar-batch/lab/ws2_repos
clone() { lang=$1; org=$2; repo=$3
  d=$BASE/${lang}_base/${org}__${repo}
  [ -d "$d/.git" ] && { echo "SKIP $d"; return; }
  mkdir -p $BASE/${lang}_base
  git clone --quiet https://github.com/$org/$repo.git "$d" && echo "OK $lang $org/$repo" || echo "FAIL $lang $org/$repo"
}
clone java alibaba fastjson2; clone java apache dubbo; clone java elastic logstash
clone java fasterxml jackson-core; clone java fasterxml jackson-databind; clone java fasterxml jackson-dataformat-xml
clone java google gson; clone java googlecontainertools jib; clone java mockito mockito
clone go cli cli; clone go grpc grpc-go; clone go zeromicro go-zero
clone rust BurntSushi ripgrep; clone rust clap-rs clap; clone rust nushell nushell
clone rust rayon-rs rayon; clone rust serde-rs serde; clone rust sharkdp bat; clone rust sharkdp fd
clone rust tokio-rs bytes; clone rust tokio-rs tokio; clone rust tokio-rs tracing
clone c facebook zstd; clone c jqlang jq; clone c ponylang ponyc
clone cpp catchorg Catch2; clone cpp fmtlib fmt; clone cpp nlohmann json
clone cpp simdjson simdjson; clone cpp yhirose cpp-httplib
echo ALL_DONE
