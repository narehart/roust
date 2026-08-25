#!/bin/bash
# WS3a private clones: lab/ws3a_repos/<lang>_base/<org>__<repo>
# cpp + rust only (jsts arms reuse the surviving mswe_repos_e23 /
# mswe_repos_private copies). Same repo set as WS2's clone_all.sh.
set -u
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/ws3a_repos
clone() { lang=$1; org=$2; repo=$3
  d=$BASE/${lang}_base/${org}__${repo}
  [ -d "$d/.git" ] && { echo "SKIP $d"; return; }
  mkdir -p $BASE/${lang}_base
  git clone --quiet https://github.com/$org/$repo.git "$d" && echo "OK $lang $org/$repo" || echo "FAIL $lang $org/$repo"
}
clone rust BurntSushi ripgrep; clone rust clap-rs clap; clone rust nushell nushell
clone rust rayon-rs rayon; clone rust serde-rs serde; clone rust sharkdp bat; clone rust sharkdp fd
clone rust tokio-rs bytes; clone rust tokio-rs tokio; clone rust tokio-rs tracing
clone cpp catchorg Catch2; clone cpp fmtlib fmt; clone cpp nlohmann json
clone cpp simdjson simdjson; clone cpp yhirose cpp-httplib
echo ALL_DONE
