# WS3b — multi-format trace-frame boost + unconditional `thirdparty` vendor guard (#56)

**Verdicts:**

- **`--trace-formats-v2` — ADOPTED (default ON since `ac0b63f`, PR #66,
  2026-08-26, standing language-agnostic directive; was
  ADOPT-RECOMMEND).** `--no-trace-formats-v2` is the escape hatch
  (reproduces CPython-only parsing byte-identically);
  `--trace-formats-v2` remains accepted-but-redundant for harness
  compatibility. Adoption evidence: java gains FUNCTION +0.79pp (+1/−0,
  jackson-databind-4325) with ZERO losses on any java metric; rust is
  headline-flat (FILE/FUNCTION/LINE zero discordants, fraction −0.0003 at
  +1/−1 churn); Python is untouched by construction AND by measurement
  (census: zero new-format regex matches across Lite-300 / Verified-407 /
  full-2294; gate: 91/91 CPython-trace-bearing instances byte-identical
  flag-on vs flag-off, two runs each). Known risk, measured at micro
  scale: traces that do NOT resolve to gold can displace it
  (svelte-11104 FILE loss, clap-2161 fraction loss) — the census's
  "gold-resolving" column predicts every gain/loss sign in the round.
- **`thirdparty` VENDOR_RE alternate — SHIPPED UNCONDITIONALLY; the fresh
  c/cpp baselines below are the adoption record.** Zero gold matches
  across all 8 slice parquets; zero thirdparty paths in every evaluated
  tree outside nlohmann (java 127, go 352, c 126 walked this round; jsts
  531, rust 234, Lite 297, Verified 406 walked in WS3a). Defaults are
  byte-identical everywhere except nlohmann (gate A 17/17); all 54
  changed cpp instances are nlohmann; cpp shifts FILE −0.77 / FUNCTION
  −0.78 / LINE −0.78 / fraction −0.0020 (reshuffle from index-statistics
  changes, both tails present, no thirdparty file was ever packed by
  either binary); c reproduces its reference digit-exact.

Engine: branch `ws3b-trace-formats` @ `0c0fc79` vs main @ `de96114`. All
arms pinned-worktree binaries (`roust 0.2.0 (0c0fc79, clean)` /
`(de96114, clean)`), private repo copies per arm, detached runs, 10s
stagger.

## The change

`roust-rs/src/core.rs`:

- **Flag-gated (`--trace-formats-v2`, default OFF):** per-format
  trace-frame parsers feeding the SAME `trace_frame_files` contract the
  adopted E11b boost consumes (rank-ordered resolved files, raise-site
  first, 1/rank boost frames 1–10, 0.1 deeper, 0.1 import spillover;
  query text byte-untouched):
  - Java/JVM `at com.foo.Bar.baz(Bar.java:123)` — FQCN→path derivation
    (`java_frame_path`: package dirs + basename, inner-class `$` and
    Java-9 module prefixes handled), resolved by the existing
    language-neutral `resolve_frame_path` component matching;
  - Node/V8 `at fn (path.js:10:15)` / `at /path.js:1:2` (two trailing
    numbers — syntactically disjoint from Java's one);
  - Go panic locator lines `\tpkg/file.go:123 +0x39` (indented non-first
    line required, so prose `file.go:12` mentions never count);
  - Rust backtrace `at src/main.rs:12:34` lines (`at ` prefix required).
  Regexes are line-for-line ports of the WS3 census miner, so the census
  populations are exactly what the parsers see. CPython parsing is
  unchanged; per-line classification tries CPython first. CPython frames
  keep v1's reversed order (raise site last→first); the new formats all
  print the throw site first, so they keep document order. On
  Python-only text `trace_frame_files_v2 == trace_frame_files` exactly
  (unit-proven).
- **Unconditional:** the one-word `thirdparty` path component joins
  `VENDOR_RE` (promoted from WS3a's flag-gated `VENDOR_V2_RE`);
  `CACHE_VERSION` 3→4 (default-index contents change for
  thirdparty-bearing repos, pre-WS3b caches must never be served).

Harness: `--trace-formats-v2` passthrough in `parity/region_eval2.py`,
`region_eval_verified.py`, `region_eval_full.py`; `formats_v2` field in
the engine's `trace_boost` stats. 4 new Rust tests (FQCN→path shapes,
per-format extraction + prose negatives, Python v1==v2 identity +
regex disjointness both directions, unconditional thirdparty guard);
suite 85/85 green.

## Census (`ws3b_census.py` / `ws3b_census.jsonl`, committed)

| slice | n | CPython TB | v2 TB | v2→gold | per-format (inst/→gold) |
|---|---|---|---|---|---|
| lite | 300 | 50 | **0** | 0 | — |
| verified | 407 | 41 | **0** | 0 | — |
| full | 2294 | 283 | **0** | 0 | — |
| mswe_jsts | 580 | 0 | 6 | 1 | node 6/1 |
| mswe_ws2c | 1052 | 0 | 29 | 17 | java 15/10, node 6/4, go 6/3, rust 2/0 |
| mswe_c | 128 | 0 | 0 | 0 | — |
| mswe_cpp | 129 | 0 | 0 | 0 | — |
| ws3a_rust | 239 | 0 | 8 | 4 | node 6/4, rust 2/0 |

Thirdparty gold data-check: **0 matches across all 8 parquets.**

**go/jsts full-arm decision: SKIPPED, micro-arms run instead.** go has
6/430 trace-bearing (1.4%, 3 gold-resolving → max +0.7pp FILE if all
flip); jsts 6/580 (1.0%, 1 gold-resolving → max +0.2pp). Neither can
show slice-level movement; the 6-instance micro-arms below supply the
frame-fire evidence at a fraction of the cost.

## Gates

**Gate A — defaults byte-identity vs main (PASS 17/17).** MAIN(de96114)
vs BRANCH(0c0fc79), two runs each, retrieval-payload md5, cold `.roust`,
on a thirdparty-free mixed pool (6 Lite python, 4 jsts, 3 rust, 2 cpp
[Catch2/fmt], 2 java); every checkout verified `tp_files=0`. 0 failures
(`ws3b/identity_gate_A.log`).

**Gate B — thirdparty itemization (54/55 nlohmann DIFFER, mechanism
exact).** MAIN vs BRANCH defaults on all 55 nlohmann instances: the 54
whose checkouts carry `benchmarks/thirdparty/` (214–242 files) differ;
the ONE identical instance (json-18) is a pre-vendoring checkout with
`tp_files_in_tree=0`. No thirdparty file appears in ANY bundle under
either binary — the damped-0.3x files never packed under main; the diffs
are BM25 df/avgdl ripples from removing them from the corpus
(`ws3b/identity_gate_BC.log`).

**Gate C — Python disjointness (PASS 91/91).** BRANCH binary, defaults
vs `--trace-formats-v2`, two runs each, on EVERY CPython-trace-bearing
Lite (50) and Verified (41) instance: all byte-identical. Argument: the
census shows zero Lite/Verified/full instances match any new-format
regex, and the new regexes are syntactically disjoint from
`TB_FRAME_RE` (unit-proven both directions), so flag-ON output equals
flag-OFF on every Python instance; gate C is the empirical confirmation.
The v12 Lite/Verified references stand unchanged.

## MSWE arms (region_eval_full, branch binary, defaults vs flag)

Baselines reproduce references: rust base = WS3a base digit-exact
(59.83/20.50/7.53/.24214); java base = WS2 exp digit-exact
(47.66/33.59/14.06/.39325); c base = WS2 c exp digit-exact
(46.88/26.56/10.94/.19768 — c is untouched by the thirdparty fix).

| slice (n) | arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|
| java (128) | base | 47.66 | 33.59 | 14.06 | .39325 |
| | v2 | 47.66 | **34.38** | 14.06 | .39325 |
| rust (239) | base | 59.83 | 20.50 | 7.53 | .24214 |
| | v2 | 59.83 | 20.50 | 7.53 | .24181 |
| go micro (6) | base | 100.0 | 66.67 | 50.00 | .50000 |
| | v2 | 100.0 | 66.67 | 50.00 | .50000 |
| jsts micro (6) | base | 50.00 | 50.00 | 0.00 | .22317 |
| | v2 | 33.33 | 33.33 | 16.67 | .17829 |

Paired stats (`ws2_paired_stats.py`):

- **java**: FILE +0/−0, LINE +0/−0, fraction +0/−0 (mean +0.0000),
  FUNCTION **+1/−0** (43→44; jackson-databind-4325 False→True). The
  boost fired on 14/128; regions changed on 13; the other 114 instances
  are payload-identical.
- **rust**: FILE +0/−0, LINE +0/−0, FUNCTION +0/−0, fraction +1/−1
  (mean −0.0003, p=1): clap-3212 .2733→.4759 (gold-resolving node
  frames) vs clap-2161 .56→.28 (non-gold rust frames displace budget).
  Fired on 5/239.
- **go micro**: fired 6/6, regions reshuffle, ZERO metric changes.
- **jsts micro**: fired 3/6 (dayjs/vuejs frames don't resolve into the
  corpus); mui-32182 fraction .769→**1.000** (LINE 0→1 flip); 
  svelte-11104 FILE 1→0 + FUNCTION True→False (fraction .5→0).

## Frame-fire itemization (which traces fired, gold rank before/after)

`goldrank_{java,rust,go,jsts}.jsonl`: rank = first gold file's position
in the engine's ranked `files` output; `g/f` = frames that ARE gold /
frames fired.

| instance | rank base→v2 | g/f | outcome |
|---|---|---|---|
| alibaba__fastjson2-1245 | 1→1 | 1/2 | — |
| apache__dubbo-11781 | –→– | 0/7 | gold never in list |
| apache__dubbo-7041 | 2→1 | 1/2 | promoted |
| elastic__logstash-16681 | 1→1 | 1/4 | — |
| fasterxml__jackson-core-370 | 2→3 | 1/3 | non-gold frames above |
| fasterxml__jackson-databind-1923 | 1→1 | 1/7 | — |
| fasterxml__jackson-databind-3716 | 14→24 | 0/10 | non-gold trace pushes gold down |
| fasterxml__jackson-databind-4159 | 1→4 | 1/5 | — (FILE still held) |
| fasterxml__jackson-databind-4189 | 1→3 | 1/7 | — |
| fasterxml__jackson-databind-4311 | 7→8 | 0/3 | — |
| fasterxml__jackson-databind-4325 | 2→3 | 1/6 | **FUNCTION 0→1** (budget reallocation) |
| fasterxml__jackson-databind-4360 | 18→4 | 1/8 | promoted |
| googlecontainertools__jib-2542 | 1→2 | 0/1 | — |
| googlecontainertools__jib-2688 | 1→1 | 1/1 | — |
| clap-rs__clap-2161 | 1→2 | 0/1 | fraction .56→.28 (loss) |
| clap-rs__clap-3212 | 2→1 | 2/3 | fraction .27→.48 (gain) |
| clap-rs__clap-3670 | 2→2 | 1/3 | — |
| clap-rs__clap-4474 | 7→1 | 1/2 | promoted |
| clap-rs__clap-5873 | 1→2 | 1/3 | — |
| cli__cli-402 | 5→5 | 0/3 | — |
| cli__cli-405 | 1→2 | 2/4 | — |
| cli__cli-495 | 1→1 | 1/3 | — |
| cli__cli-8893 | 8→8 | 0/4 | — |
| cli__cli-9307 | 28→24 | 0/4 | — |
| grpc__grpc-go-2371 | 1→2 | 1/3 | — |
| mui__material-ui-32182 | 7→1 | 1/1 | **LINE 0→1** (fraction .77→1.0) |
| sveltejs__svelte-10187 | 3→5 | 0/2 | — |
| sveltejs__svelte-11104 | 31→out | 0/2 | **FILE 1→0** (displaced) |

Census-ceiling accounting: of java's 10 gold-resolving traces, 10 fired
with gold among the frames (`g/f ≥ 1`... 10 of the 14 fired), but 9 of
those gold files were ALREADY retrieved at base (rank ≤ 18, inside the
~29-file pack) — the java FILE ceiling was an illusion of the census:
gold-resolving traces overwhelmingly point at files the lexical channel
already ranks. The boost's real java effect is E11b's exact Lite
pattern: FUNCTION-level budget reallocation (+1), zero FILE movement.

## Fresh c/cpp baselines (thirdparty fix in; adoption record)

| slice (n) | reference (pre-fix) | fresh (post-fix) | paired detail |
|---|---|---|---|
| cpp (129) | 65.89 / 18.60 / 7.75 / .29672 | **65.12 / 17.83 / 6.98 / .29476** | FILE +0/−1 (json-1138), FUNCTION +0/−1, LINE +0/−1 (json-708 1.0→.8125), fraction +4/−11 (−.0020, p=.12); all 54 changed = nlohmann |
| c (128) | 46.88 / 26.56 / 10.94 / .19768 | **46.88 / 26.56 / 10.94 / .19768** | digit-exact, zero thirdparty trees |

The cpp shift is a small net negative confined to nlohmann: removing
214–242 never-packed vendored files changes idf/avgdl and reshuffles
close calls (16 instances move fraction, both directions). The fix's
case is structural, per the WS3a charter: vendored Google Benchmark
sources measurably displaced gold when reachable, zero gold is ever
under a thirdparty path, and index hygiene should not depend on a
damping coincidence. These fresh numbers supersede the WS2/WS3a cpp
reference for future rounds.

## Adoption + rebaseline record (2026-08-26, `ac0b63f`)

- **Default flip proofs** (`lab/ws3b_adoption_gate.py`,
  `ws3b/adoption_gate.log`; retrieval-payload md5, two runs per config,
  cold `.roust`): (A) NEW(ac0b63f) defaults == OLD(0c0fc79) with
  explicit `--trace-formats-v2` on all 19 trace-firing java/rust
  instances; (B) NEW defaults == OLD defaults on 12 Lite Python
  instances (one per repo); (C) NEW `--no-trace-formats-v2` == OLD
  defaults on the same 19 trace-firing instances. 0 failures.
- **New references**: java **47.66 / 34.38 / 14.06 / .39325**
  (`agentless_metric_ws3b_java_v2.json`) supersedes the WS2 exp row.
  rust reference UNCHANGED (59.83/20.50/7.53/.24214): the flag is
  neutral at every headline metric; the −0.0003 fraction mean (+1/−1,
  p=1) is within the adopted delta and the base numbers remain the
  citable reference. cpp/c references are the fresh thirdparty-fixed
  baselines stated above (their change is the unconditional vendor
  guard, not this flag). Python Lite/Verified references unchanged
  (byte-identity proven). README scoreboard + CHANGELOG updated in the
  adoption commit.

## Anomalies / notes

- Census counted java 15 trace-bearing; 14 fired (one instance's frames
  resolve to nothing in-corpus). jsts: 6 counted, 3 fired (dayjs/vuejs
  frames are node_modules/dist paths that don't resolve). The census
  regex-match column is an upper bound on firing.
- Rust `at path.rs:line:col` lines are claimed by the Node regex (two
  trailing numbers) before the Rust regex — extracted path is identical,
  so classification order is cosmetic; noted for census bookkeeping
  (clap "node" fires are Rust-ecosystem issues quoting panics).
- The jsts micro FILE loss (svelte-11104) and rust fraction loss
  (clap-2161) share one anatomy: NO frame resolves to gold, and the
  boosted non-gold frame files displace gold from budget/pack. **QUEUED
  FOLLOW-UP (post-adoption): a no-gold-frame displacement guard** (e.g.
  damp the boost when no frame file also carries lexical mass) — the
  svelte-11104/clap-2161 itemizations above are its case-mining seed.
- ponyc-2950 carries the standard "pure file creation" error row (c
  slice n=128 includes it as wrong at all levels, unchanged convention).
- zsh word-splitting ate one goldrank launcher attempt; rerun as a bash
  script (`run_goldrank.sh`). No data impact.

## Artifacts

- arms + logs: `lab/results_regions/ws3b/` (`mswe_{java,rust}_ws3b_{base,v2}.jsonl`,
  `mswe_{cpp,c}_ws3b_base.jsonl`, `mswe_{go,jsts}_micro_ws3b_{base,v2}.jsonl`,
  metric JSONs `agentless_metric_ws3b_*.json`, `launch_all.sh`,
  `score_all.sh`, `run_goldrank.sh`, `goldrank_*.jsonl`,
  `identity_gate_{A,BC}.log`)
- census: `lab/research/langagnostic/ws3b_census.{py,jsonl}`
- gates: `lab/ws3b_identity_gate.py`; itemizer: `lab/ws3b_itemize.py`;
  rank capture: `lab/ws3b_goldrank.py`
- slice parquets: `lab/ws3b_java.parquet` (128),
  `lab/ws3b_go_micro.parquet` (6), `lab/ws3b_jsts_micro.parquet` (6)
