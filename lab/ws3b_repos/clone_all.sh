#!/bin/bash
# WS3b private clones/copies: lab/ws3b_repos/<arm>/<org>__<repo>
# java base+v2 (9 repos x2), go micro base+v2 (2 repos x2), jsts micro
# base+v2 (4 repos x2, cp -R from the surviving mswe_repos_e23 clones),
# c base (3 repos x1, fresh thirdparty-fix baseline). cpp base reuses
# lab/ws3a_repos/cpp_base (idle since WS3a).
set -u
BASE=/Users/nicholasarehart/programming-projects/bgrep/lab/ws3b_repos
E23=/Users/nicholasarehart/programming-projects/bgrep/lab/mswe_repos_e23
clone() { arm=$1; org=$2; repo=$3
  d=$BASE/$arm/${org}__${repo}
  [ -d "$d/.git" ] && { echo "SKIP $d"; return; }
  mkdir -p $BASE/$arm
  git clone --quiet https://github.com/$org/$repo.git "$d" && echo "OK $arm $org/$repo" || echo "FAIL $arm $org/$repo"
}
copy() { arm=$1; slug=$2
  d=$BASE/$arm/$slug
  [ -d "$d/.git" ] && { echo "SKIP $d"; return; }
  mkdir -p $BASE/$arm
  cp -R "$E23/$slug" "$d" && echo "OK copy $arm $slug" || echo "FAIL copy $arm $slug"
}
for arm in java_base java_v2; do
  clone $arm alibaba fastjson2; clone $arm apache dubbo; clone $arm elastic logstash
  clone $arm fasterxml jackson-core; clone $arm fasterxml jackson-databind
  clone $arm fasterxml jackson-dataformat-xml
  clone $arm google gson; clone $arm googlecontainertools jib; clone $arm mockito mockito
done
for arm in go_base go_v2; do
  clone $arm cli cli; clone $arm grpc grpc-go
done
for arm in jsts_base jsts_v2; do
  copy $arm mui__material-ui; copy $arm vuejs__core; copy $arm iamkun__dayjs; copy $arm sveltejs__svelte
done
clone c_base facebook zstd; clone c_base jqlang jq; clone c_base ponylang ponyc
echo ALL_DONE
