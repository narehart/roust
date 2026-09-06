# Evaluation record

<!-- site:sub The complete technical record behind every published roust number: comparisons, caveats, re-measurements, and the artifact each one came from. -->

This page is for readers who want the whole story. The short version is on
[Benchmarks](BENCHMARKS.md); how the numbers are produced is on
[Research](RESEARCH.md). Everything here is reproduced from a committed
artifact in the repository, and every correction or retraction made along the
way is kept rather than erased.

Conventions used throughout:

- **FILE** is all-or-nothing: an instance counts only if *every* gold file is
  in the returned set. **FUNCTION** requires the gold function spans to be a
  subset of the packed spans (exact containment). **LINE** is all-or-nothing
  over gold lines; **fraction** is the mean share of gold lines covered.
- Engine errors count as wrong at every level and stay in the denominator.
- Python numbers are SWE-bench Lite (300, the tuning set) and SWE-bench
  Verified (407, held out: no adoption decision was ever made on it). Other
  languages are Multi-SWE-bench slices.

## Agent-loop outcomes <!-- note: does better retrieval change what an agent achieves -->

Given the same task and the same agent (tokenbench v2, live Sonnet 4.5), roust
solves **93.3%** of tasks, grep **26.7%**, embedding-RAG **80.0%** (9-trial
mean). n=15, a partial run stopped at a spend cap (see protocol below). The grep
and roust arms get their method as the agent's only *search* tool, the
embedding-RAG arm gets rag_search **plus grep**, and every arm has a read_file
tool.

| System | Solves | Median turns | Tokens / attempt | $ / attempt | $ / successful run |
|---|---|---|---|---|---|
| **roust** | 93.3% | 9 | 308,184 | $0.95 | $0.93 |
| grep | 26.7% | 30 | 239,600 | $0.76 | $0.53 |
| embedding-RAG | 80.0% (9-trial mean ± 4.4pp) | 20.5 | 695,833 | $2.14 | $1.80 |
| roust + grep (both) | 57.1% | 27.5 | 595,234 | $1.83 | $1.60 |
| grep + stopping prompt | 20.0% | — | 52,576 | $0.17 | $0.18 |
| roust + stopping prompt | 66.7% | — | 241,027 | $0.74 | $0.63 |

What the table does and does not say:

- roust costs more per attempt than grep (308k vs 240k tokens) and wins on
  solve rate anyway. grep is cheap because it gives up: 73.3% of its runs hit
  the turn cap and produce nothing.
- Giving the agent grep *alongside* roust makes it worse (93.3% → 57.1%):
  replace grep, don't supplement it
  ([#5](https://github.com/narehart/roust/issues/5)).
- `$ / successful run` is a lower bound on cost-to-answer for a single
  attempt. The repeat-run campaign (#16, `results_repeats.jsonl`) measured the
  rest: for roust and grep, failures are **stable across trials** (p≈0; roust's
  one miss failed 10/10), while embedding-RAG's failures are genuinely
  stochastic. Its per-instance expected cost to first success, computed as
  (1−p̂)/p̂ × mean failed-attempt cost + mean successful-attempt cost with p̂
  over the 10 trials (trial 0 + 9 repeats), aggregates over its solvable set
  (all 15 instances, per-instance p̂ 0.10–1.00) to a **median of $2.42** per
  instance; the **mean is $4.90**, dominated by django-16400 (p̂ = 0.10, E ≈
  $31). An earlier revision stated "$2.50" here without naming the
  aggregation; the stated-convention numbers replace it.
- embedding-RAG's **Solves** cell is a 9-trial mean
  (`lab/tokenbench/results_repeats.jsonl`); its other columns are the trial-0
  measurement (`lab/tokenbench/results.jsonl`).
- The two `+ stopping prompt` rows are the forced-stopping steelman arms
  (`grep_forced`/`roust_forced`, hard stopping directive + 12-turn cap):
  `lab/tokenbench/results_forced.jsonl`.
- Outcome volatility across 9 identical repeats: embedding-RAG bounces
  73.3–86.7% (mean 80.0% ± 4.4pp); roust reproduced 93.3% exactly with 0
  outcome flips, and its single failure (django-16400) failed 10/10 trials, a
  capability gap rather than variance (p < 0.30 at 95%, rule of three). grep's
  failures were stable across both its trials.

Protocol: our agent-loop harness, live Sonnet 4.5, measured to task
completion. A partial run: 58 of 120 planned pairs, stopped at an $80 spend
cap, so n=15 (14 for embedding-RAG). The research log, including the retracted
"95% fewer tokens than grep" claim (from a v1 one-shot protocol that does not
hold in the agent loop, [#6](https://github.com/narehart/roust/issues/6)), is
in `lab/README.md`.

## Localization accuracy vs published systems <!-- note: where roust sits against trained retrievers -->

roust is **not** the most accurate retriever available: trained retrievers
score higher on published localization benchmarks. What roust offers is the
best result you can get for free, with no model, no embeddings, no API key,
and no training.

| System | File-level | Metric | Free? | Source |
|---|---|---|---|---|
| SweRankEmbed-Large + LLM rerank | 96.0 | Acc@10 | no (trained + LLM) | arXiv:2505.07849 |
| SweRankEmbed-Large | 94.2 | Acc@10 | no (trained) | arXiv:2505.07849 |
| LocAgent | 94.16 | file acc | no (LLM) | arXiv:2503.09089 |
| **roust** | 83.3 (File@10) · 92.3 (all-gold retrieved, ~35 files returned) | File@10 / Agentless-metric FILE | yes | `lab/README.md` ablation + trace-boost remeasure (`lab/research/wave5/e20-e11b-results.md`) / `lab/results_regions/agentless_metric_e20_traceboost.json` |
| SweRankEmbed-Small | 90.9 | Acc@10 | no (trained) | arXiv:2505.07849 |
| OrcaLoca | 83.33 | file-match | no (LLM) | arXiv:2502.00350 |
| Agentless GPT-4o | 69.7 | Agentless-metric FILE | no (LLM) | arXiv:2407.01489 |
| BM25 | 61.7 | Acc@10 | yes | arXiv:2505.07849 |
| CoSIL | 60.7 | Top-1 | no (LLM) | arXiv:2503.22424 |
| archex (BM25 default) | 56.0 | Agentless-metric FILE | yes (local index; embeddings optional) | `lab/results_regions/agentless_metric_archex_bm25.json` |
| archex (vector/hybrid) | 57.3 | Agentless-metric FILE | yes (local index + FastEmbed/ONNX) | `lab/results_regions/agentless_metric_archex_vector.json` |
| **roust** (Multi-SWE JS/TS, 580 inst.) | 46.4 | Agentless-metric FILE | yes | `lab/results_regions/agentless_metric_mswe_e23_tsblocks.json` |

Published rows are each system's own paper on its own harness, a different
protocol from the agent-loop table above. archex has two rows: its default
retrieval mode (BM25+graph, no embeddings) and its optional vector/hybrid mode
(FastEmbed/ONNX + graph), both measured by us
([#1](https://github.com/narehart/roust/issues/1)).

### Reading the File-level column

- The column mixes several metrics (Acc@10 / Top-1 / file-match /
  Agentless-metric FILE) and is **not** comparable straight down; each row
  names its own.
- roust's two numbers differ in both directions. Acc@10 counts an instance
  correct if *any* gold file appears in the top 10. Agentless-metric FILE
  counts it correct only if *all* gold files appear anywhere in the returned
  set (~35 files for roust, range 22–38, measured from
  `lab/results_regions/full300_v11.jsonl`): stricter on completeness, looser
  on depth, so neither subsumes the other.
- **File@10 83.3** (all gold files within the top 10) is the depth-aligned
  number to rank roust against the Acc@10 rows. The frozen v7 ablation row of
  `lab/README.md` measured 82.7 = 248/300; the adopted trace-frame boost adds
  +2 gains / 0 losses over the 46 trace-bearing instances
  (`lab/research/wave5/e20-e11b-results.md`); all other instances are
  byte-identical. On that aligned metric roust sits *below* the trained
  retrievers, including SweRankEmbed-Small's 90.9, and the comparison is
  conservative, since File@10 demands all gold files in the top 10 where
  Acc@10 needs one.

### Function and line level against Agentless and archex

The 92.3 all-gold figure is the one whose FUNCTION/LINE companions follow.
At the time of the trace-boost adoption, roust's Agentless-metric scores on
Lite were FILE 92.3% / FUNCTION 54.7% (exact) / LINE 43.3%
(`lab/results_regions/agentless_metric_e20_traceboost.json`); the current
shipped engine is higher still (see the eight-language table below).

- Training-free roust exceeds Agentless GPT-4o at function level (54.7 vs
  52.0) and line level (43.3 vs 35.3). Agentless GPT-4o is 69.7 / 52.0 / 35.3.
- archex (BM25 default) is 56.0 / 38.3 / 25.7
  (`lab/results_regions/agentless_metric_archex_bm25.json`). 2 of 300
  instances timed out; they count as wrong at FILE and LINE but are
  **excluded from the FUNCTION denominator** in that artifact, a
  baseline-favorable convention (38.3 = 114/298; counting them wrong would
  give 38.0).
- archex (vector/hybrid) is 57.3 / 40.7 / 27.7
  (`lab/results_regions/agentless_metric_archex_vector.json`, same 2 timeouts
  and convention, plus one git-show exclusion at FUNCTION): a single-digit
  gain over BM25 that leaves the ~35-point FILE gap to roust unchanged.
- LINE mean-fraction-covered (a continuity metric, distinct from the strict
  all-or-nothing LINE % above) rose 0.4564 → 0.5168 → 0.5251 across the same
  changes.
- Region precision (gold lines returned / total lines returned, i.e. how much
  of the packed context is actually the fix) rose from 0.4486% to 0.5522%
  mean (+23% relative). roust still trades precision for recall by design,
  packing ~1,123 lines of surrounding context per instance under the
  8192-token budget (down slightly from ~1,150 pre-adoption).
- These gains are the additive stack of three measured changes from the #4
  campaign, now the shipped defaults: guarded span padding (`--pad-lines`,
  default 5), sub-linear length normalization (`--len-exp`, default 0.85), and
  the trace-frame FILE boost (E11b, PR #52: files named in a traceback in the
  query get a rank-decayed file-score boost, raise-site first, query text
  untouched; Verified held-out confirmed non-negative in every cell, FILE
  92.14→92.38, LINE 35.38→35.63; `--no-trace-boost` disables). `roust --help`
  lists the flags that reproduce the pre-adoption engine; see
  [#4](https://github.com/narehart/roust/issues/4).

### The first non-Python row

The Multi-SWE JS/TS row was roust's first non-Python scoreboard entry: on the
580-instance Multi-SWE-bench JS/TS slice, FILE 46.4 (269/580) / FUNCTION 31.0
(exact) / LINE 13.3 / fraction .258
(`lab/results_regions/agentless_metric_mswe_e23_tsblocks.json`), measured with
the now-default tree-sitter structural blocks for .js/.jsx/.ts/.tsx (E23, PR
[#55](https://github.com/narehart/roust/pull/55), step one of the
language-agnostic campaign, [#56](https://github.com/narehart/roust/issues/56)).
Two corrections against prior reporting:

1. The previously published MSWE FUNCTION **99.83 is retired as vacuous**. The
   gold-function scorer was Python-AST-only, so every JS/TS instance had
   `n_gold_functions: 0` and passed the subset condition vacuously. With the
   fixed tree-sitter scorer the true pre-adoption baseline is **21.2**
   (`lab/results_regions/agentless_metric_mswe_e23_baseline.json`), lifted to
   **31.0** by the structural blocks (+68/−11 paired, p=3.5e-11).
2. FILE 46.4 sits under a measured **~76.7 ceiling**: 135/580 instances have
   at least one gold file outside the indexed extension set (.json, 316 gold
   files; .md, 158; .svelte, .mjs, ...), so no ranking change can lift FILE
   past ~76.7 on this corpus walk.

## Eight-language scoreboard <!-- note: the shipped defaults on every benchmarked slice -->

All rows are the shipped engine defaults, measured on one engine commit.
Every FUNCTION number is from the corrected language-aware scorer.

| language (n) | FILE | FUNCTION (exact) | LINE | LINE mean-fraction | engine config | source |
|---|---|---|---|---|---|---|
| Python — Lite 300 | 92.33 | 57.67 | 46.00 | .537 | defaults | `lab/results_regions/e44/metrics/lite_ts40.json` |
| Python — Verified 407 (held-out) | 92.38 | 48.89 | 37.84 | .494 | defaults | `lab/results_regions/e44/metrics/ver_ts40.json` |
| JS/TS — MSWE 580 | 46.38 | 31.55 | 14.14 | .264 | defaults | `lab/results_regions/e44/metrics/jsts_ts40ship.json` |
| Java — MSWE 128 | 49.22 | 39.84 | 14.84 | .433 | defaults | `lab/results_regions/e44/metrics/java_ts40ship.json` |
| Go — MSWE 428 | 64.95 | 32.94 | 18.46 | .423 | defaults | `lab/results_regions/e44/metrics/go_ts40ship.json` |
| Rust — MSWE 239 | 60.25 | 20.92 | 7.53 | .249 | defaults | `lab/results_regions/e44/metrics/rust_ts40ship.json` |
| C — MSWE 128 | 51.56 | 28.12 | 13.28 | .225 | defaults | `lab/results_regions/e44/metrics/c_ts40ship.json` |
| C++ — MSWE 129 | 65.89 | 20.93 | 8.53 | .311 | defaults | `lab/results_regions/e44/metrics/cpp_ts40ship.json` |

Cross-language FILE differences are dominated by corpus shape (JS/TS's ~76.7
extension ceiling above; Go's single-repo skew, cli/cli being 397 of 428
instances). Compare within a row's own slice, not down the column. A later
analysis (E35, `lab/research/wave6/e31-e32-generation-gap.md`) found a second
confound: the "3+ gold files" instances differ sharply in difficulty per
language (mean gold files per instance from 4.3 for Python-Verified to 11.0
for JS/TS), so roughly half of the apparent Python-to-Rust gap on that stratum
was the mix, not the engine.

### How this table got here

Each adoption below moved specific rows. The writeups hold the per-instance
itemization; the moves are summarized here in order.

1. **Python rows, C-family indexing (WS2c,
   `lab/research/langagnostic/ws2c-vendor-guard.md`).** `.c/.h/.cc/.cpp/.cxx/.hpp/.hh`
   are indexed by default behind a vendored-C guard (`VENDOR_RE`: `cextern/`,
   `extern/`, `libsvm/`, `liblinear/` path components); `--no-cfamily-ext`
   reverts, at which point the C and C++ rows become FILE 0 since nothing is
   indexable. The WS2b gate had deferred the flip after vendored libsvm
   displaced gold on one Lite instance; the guard cured exactly that instance
   and left the MSWE C/C++ arms payload-identical (0/257 diffs). Relative to
   the WS2b references the Python rows moved by exactly two single instances:
   Lite LINE 43.67→44.00 (one gain) and Verified LINE 35.38→35.14 (one loss,
   two gold lines on astropy-14508, from the guard excluding astropy's
   vendored `extern/` Python, not from C indexing; both sign tests p=1).
2. **Multi-format trace parsing (WS3b,
   `lab/research/langagnostic/ws3b-trace-formats.md`, PR
   [#66](https://github.com/narehart/roust/pull/66)).** Java FUNCTION
   33.59→34.38 (+1/−0) from the now-default Java/Node/Go/Rust frame parsing;
   Python byte-identical, 91/91 proven. The C++ row moved to a fresh baseline
   under the unconditional `thirdparty` vendor guard (65.89/18.60/7.75/.297 →
   65.12/17.83/6.98/.295); all 54 changed instances are nlohmann, whose
   checkouts vendor Google Benchmark under `benchmarks/thirdparty/`. No
   thirdparty file was ever packed by either engine; the shift is BM25
   index-statistics reshuffle. The C row reproduced digit-exact.
3. **Structural symbols (WS3c, `lab/research/langagnostic/ws3c-symbols.md`,
   PR [#67](https://github.com/narehart/roust/pull/67), adopted 2026-08-26).**
   The def/anchor channel became structural for every grammar-covered language
   (tree-sitter-sourced `def_index` + anchor-forced region seating un-gated
   from `.py`). JS/TS, Java, and Rust rows moved; the superseded post-WS3b
   jsts base was 46.21/30.86/13.45/.258 (a restatement of the pre-WS3b
   46.38/31.03/13.28/.258 reference after two documented instance moves).
   Rust caveat: FILE/fraction gain (+1/−0 FILE) but FUNCTION 20.50→19.67
   (+0/−2, two displacement losses where a new non-gold anchor squeezed the
   gold region's budget). Python rows unchanged: all four metrics
   digit-identical per instance on Lite and Verified (zero FUNCTION flips; 79
   instances repack non-gold content only).
4. **Fixture-dir displacement guard (WS3d,
   `lab/research/langagnostic/ws3d-displacement-guard.md`, PR
   [#68](https://github.com/narehart/roust/pull/68)).** JS/TS LINE/fraction
   13.97→14.14, .260→.262 (FILE/FUNCTION invariant, zero flips): files under
   `*.test/` or `*.spec/` *directory* components (the jscodeshift codemod
   fixture convention) no longer compete for symbol anchors;
   `--no-displacement-guard` reverts. Every other row proven untouched:
   java/rust have zero fixture-dir paths in any evaluated tree (per-instance
   `git ls-tree` census), and the entire Lite/Verified exposure (31 pytest
   instances, all carrying `extra/setup-py.test/setup.py`) is byte-identical.
   The general anchor/trace displacement guard was investigated and closed
   NO-GO by fire-level mining (culprit fires are shape-identical to the
   adoption wins' gold fires); the rust FUNCTION caveat and the
   svelte-11104/jackson-4219-class losses remain live.
5. **Single-commit re-measurement (E25 gate, 2026-08-26, commit `abb96af`,
   `lab/research/wave6/e25-shape-blocks.md`).** All eight rows re-run on one
   engine commit. Three moved because their previous artifacts predated
   adoptions that changed their own slices, pure engine drift in roust's
   favour: Go FILE 63.79→64.95, C FUNCTION 26.56→28.12, C++ FILE 65.12→65.89.
   JS/TS, Java, Rust, and both Python rows reproduced to the digit, which is
   what makes the drift attributable rather than noise.
6. **Extension coverage (E26, `lab/research/wave6/e26-ext-coverage.md`,
   adopted 2026-08-27, commit `ca15227`).** `.rb` and `.pony` are indexed by
   default behind a fixture-path guard, after the gate measured that the
   pre-adoption engine retrieved **0 of 148** gold files in those extensions:
   unreachable at any rank, because the file type was never indexed. C moves
   FILE 46.88→51.56 and LINE 10.94→13.28 (ponylang/ponyc's `.pony` sources);
   Java moves FUNCTION 35.16→36.72 (elastic/logstash's Ruby core), recovering
   53% of its unindexed-gold ceiling. `.svelte` was measured and REJECTED:
   2,927 files for 5 gold, JS/TS FILE −5.17 unguarded and still significantly
   negative with the guard. The other rows are unchanged by construction, not
   by assumption: a census across every slice's clones found zero `.rb`/`.pony`
   files in those repos. `--no-ext-v2` reverts; Python byte-identity re-proven
   7/7 on cold caches.
7. **Packer budget floor 0.15 (E45, `lab/research/wave6/e44-ppr-budget.md`,
   adopted 2026-09-03).** Was 0.3; `--pack-floor 0.3` restores. The floor runs
   after file selection, so FILE is pinned on every row by construction (0
   flips on all 2,339 instances) and tokens are unchanged; only the split of
   packing budget across returned files moves. Exact FUNCTION vs the prior
   rows: Java 36.72→39.06 (+3/−0), C++ 17.83→19.38 (+2/−0), Rust 19.67→20.50
   (+2/−0), Go 28.97→29.44 (+4/−2), Verified 47.17→47.67 (+3/−1), Lite
   54.67→54.67 (+2/−2), JS/TS 31.21→30.86 (+1/−3), C 28.12→27.34 (+0/−1);
   LINE up on Go, C++, Lite (44.00→44.33) and Verified (35.14→36.86),
   otherwise unchanged except one JS/TS instance. No cell significantly
   negative; Java fraction (p=.0098) and Go at cap 32 (FUNCTION p=.039)
   significantly positive. Both Python baselines reproduced the previous
   published references to the last digit before the flip.
8. **Tiered pass-1 seats (E47, `lab/research/wave6/e47-tail-seats.md`,
   adopted 2026-09-03).** Returned files at rank 16+ get a 40-token first seat
   instead of the flat 120 (`--tail-seat-tokens 0` restores). The file still
   carries a span, so FILE is pinned (0 flips, 2,339 instances) and tokens are
   unchanged; the freed budget goes to pass-2 depth. Exact FUNCTION vs the
   E45 rows: Go 29.44→32.94 (+20/−3, p<.001), Java 39.06→39.84, C++
   19.38→20.93, Rust 20.50→20.92, JS/TS 30.86→31.55, C 27.34→28.12, Lite
   54.67→57.67 (+11/−2, p=.022), Verified 47.67→48.89 (+8/−1, p=.039); LINE
   up on Go, Java, C++, Lite (44.33→46.00) and Verified (36.86→37.84). Pooled
   FUNCTION +54/−8; no cell below the prior row. Largest Lite FUNCTION move
   since PR #40.

## Held-out replication of the region gains <!-- note: the tuning-set gains reproduced on Verified -->

The region-packing changes from the #4 campaign (guarded padding +
sub-linear length normalization) were adopted on Lite and then replicated on
the 407 held-out SWE-bench Verified instances, never used for any tuning
decision (commit 2f7d324,
`lab/results_regions/agentless_metric_verified_{old,new}.json`,
`parity/region_eval_verified.py`):

- FUNCTION rose 34.2%→47.0% (+12.9pp) and LINE 26.3%→35.4% (+9.1pp,
  mean-fraction-covered +0.053). FILE essentially unchanged (92.14%→91.89%,
  one 180s engine timeout counted as wrong in the new arm).
- The absolute numbers are lower than Lite's at the time (FUNCTION 53.3%,
  LINE 42.7%) because held-out Verified is a harder set (lower baseline FILE
  accuracy, more gold hunks per instance). What needed to replicate was the
  *delta*, and it did: 104% of the Lite FUNCTION delta, 130% of the Lite LINE
  delta, 88% of the Lite fraction delta.
- File selection is untouched by padding/length-normalization, which only
  reshape spans within already-selected files; the 300/300 file-level parity
  gate (`parity/rust_gate_300_v5.json`) confirms file ranking is unchanged.
  The held-out FILE numbers (79.4 File@10 / 92.1 all-gold, `lab/README.md`'s
  held-out validation section) are therefore unaffected.
- Top-1 file accuracy on held-out Verified is .354. If you need "the one
  file", read further down the ranked list rather than trusting rank 1.

## Latency <!-- note: index build and query time, before and after the 0.4.0 speedups -->

Methodology (`lab/latency/bench_latency.py`,
[#15](https://github.com/narehart/roust/issues/15)): cold index (median of 3,
`.roust/` removed each time), warm index (median of 5, cache hit), and query
time (p50/p95 of 20 queries cycling 10 problem-statement-like phrases, warm
cache). `index_ms`/`query_ms` come from `--json`; wall time is the end-to-end
subprocess time an agent actually experiences. Apple M3 Max (arm64).

### Current engine vs the previous one (`lab/latency/latency_v2.json`)

Seven disposable repo copies (three non-Python), engine `roust 0.3.2
(c72dbbc, clean)` vs the pre-E49 engine `a1db4f6`
(`lab/latency/latency_v2_pre_e49.json`), same machine, back to back. The E49
padding-guard memo and the E50 per-file block/token cache change no output
(byte-identical bundles proven on 128/128 full-slice instances and five
hand-checked repos) and only cut time:

| Repo | Files | Cold index wall (pre / now) | Warm index wall (pre / now) | Query p50 `query_ms` (pre / now) | Query p95 `query_ms` (pre / now) | Query wall p50 (pre / now) |
|---|---|---|---|---|---|---|
| requests | 122 | 580 / 203 ms | 533 / 78 ms | 1006 / 61 ms | 1981 / 76 ms | 1033 / 90 ms |
| flask | 77 | 1536 / 232 ms | 1473 / 89 ms | 1057 / 65 ms | 1389 / 69 ms | 1086 / 94 ms |
| django | 2,214 | 2512 / 1663 ms | 1315 / 339 ms | 2212 / 126 ms | 6159 / 164 ms | 2439 / 342 ms |
| clap-rs/clap (Rust) | 98 | 2258 / 470 ms | 2117 / 103 ms | 1187 / 69 ms | 2060 / 84 ms | 1215 / 96 ms |
| nlohmann/json (C++) | 192 | 1735 / 825 ms | 1470 / 114 ms | 2026 / 85 ms | 3553 / 147 ms | 2072 / 122 ms |
| cli/cli (Go) | 711 | 1783 / 1486 ms | 893 / 529 ms | 1696 / 495 ms | 1975 / 552 ms | 1769 / 566 ms |
| roust working tree (incl. docs/lab) | 3,902 | 7150 / 3954 ms | 4123 / 571 ms | 2432 / 194 ms | 3708 / 325 ms | 2820 / 570 ms |

Query time on a warm repo is 7-25x lower than the previous engine on six of
seven repos; cli/cli, whose time is dominated by candidate generation over a
711-file corpus rather than by packing, improves 3.4x. "Cold index" and "warm
index" include one query, which is why they move too. The E50 cache lives at
`<repo>/.roust/blocks.json` (140-400 KB after a query) and is skipped under
`--no-cache`. The released 0.3.2 binary measured the same as `a1db4f6`
(requests 1563 ms, django 2099 ms per query), so 0.4.0 is an 8-23x query
speedup for users of the published packages.

### The original measurement (`lab/latency/latency_v1.json`)

Engine `roust 0.2.0 (418212b, clean)`, kept as the historical baseline:

| Repo | Files indexed | Cold index (index / wall) | Warm index (index / wall) | Query index p50 / p95 | Query wall p50 / p95 |
|---|---|---|---|---|---|
| roust (this repo) | 66 | 145ms / 302ms | 24ms / 181ms | 109ms / 148ms | 140ms / 180ms |
| requests | 122 | 128ms / 244ms | 23ms / 144ms | 81ms / 111ms | 114ms / 144ms |
| flask | 77 | 184ms / 300ms | 25ms / 142ms | 97ms / 107ms | 129ms / 142ms |
| django | 2,131 | 1538ms / 1756ms | 195ms / 412ms | 158ms / 246ms | 363ms / 451ms |

Roughly a third of the wall-clock time at this repo size is fixed subprocess
startup overhead, visible as the gap between `index_ms`/`query_ms` and the
wall-time column. Query time regressed between 0.2.0 and 0.3.2 (requests 81
ms → 1.56 s per query); E49 and E50 traced the cost to the padding guard's
repeated rebuilds and to per-query re-tokenization of returned files, and the
v2 table above is the repair.

### Competitor latency

archex (BM25 default mode) query wall time on the SWE-bench Lite corpora,
`lab/results_regions/archex300_bm25_v1.jsonl`: index mean 5.69s, query median
9.68s (2 of 300 queries hit the 300s timeout). archex (vector/hybrid mode),
`lab/results_regions/archex300_vector_v1.jsonl`: index mean 0.92s, query
median 12.98s (same 2 timeouts), worse than BM25 despite the faster index.
roust's wall time on comparable repos is in the tables above
([#1](https://github.com/narehart/roust/issues/1)).

*Historical note:* an earlier claim, never backed by a committed artifact,
compared the now-deleted Python engine against the Rust port directly ("Rust
3.6–4.2× faster than Python engine (httpx 145ms vs 522ms, django 1.8s vs
7.6s)"). The Python engine was removed in #12, so that comparison is no longer
reproducible; it is kept only as a historical data point, not a current claim.

## ContextBench <!-- note: human-annotated gold context, scored by their evaluator -->

[ContextBench](https://github.com/EuniAI/ContextBench) (arXiv:2602.05892)
scores retrieved context against human-annotated "necessary context" line
regions. roust was run one-shot (`--json --budget 8192`, single call, no
model) on the **Python subset of their curated 500-instance Verified benchmark
(266 tasks, 19 repos, 266/266 evaluated, 0 skipped)** and scored with
ContextBench's own evaluator, unmodified
([#3](https://github.com/narehart/roust/issues/3)):

| Granularity | roust recall | roust precision | Claude Sonnet 4.5 agent recall | precision |
|---|---|---|---|---|
| file | **0.679** | 0.060 | 0.720 | 0.665 |
| block | 0.346 | 0.040 | 0.449 | 0.420 |
| line | 0.274 | 0.053 | 0.374 | 0.344 |

Protocols differ and the comparison is not apples-to-apples: the published
baselines are **multi-turn LLM agents** (read, navigate, then select context)
on the full 500-task 8-language set; roust is a **single sub-2-second call
with no model, no API key, and no training**, on the Python 266. Read it as:
one free one-shot call recovers ~94% of the file-level recall of the best
agent, and its precision is ~10x lower because roust deliberately packs a
full 8192-token recall-first bundle rather than a minimal answer, the same
recall-over-precision trade documented in
[#4](https://github.com/narehart/roust/issues/4). ContextBench's efficiency
metrics (AUC-Coverage/Redundancy) are N/A for a one-step trajectory. Adapter
and protocol: `lab/contextbench/`; aggregate:
`lab/contextbench/results_python.json`.

## Questions that were open, and how they closed <!-- note: the former "what still needs work" list -->

- **Exact function and line metrics.** Early reporting used a proxy
  (line-level 35.7%, function-level 44.3%). Measured exactly
  (`lab/results_regions/agentless_metric_v2.json`): FUNCTION 39.7% and LINE
  29.3% from a fresh 300-instance run. A `w_name` sweep on the exact harness
  ([#4](https://github.com/narehart/roust/issues/4)) showed the symbol-name
  weighting itself caused the LINE drop; reverting it (w_name=0.0) restored
  FUNCTION 41.0% and LINE 35.7% (`lab/results_regions/agentless_metric_v3.json`).
  The campaign's miss autopsy then found the padding/length-normalization
  mechanism, adopted as `--pad-lines 5 --len-exp 0.85`, raising FUNCTION
  41.0→53.3% and LINE 35.7→42.7% (fraction 0.4564→0.5168,
  `lab/results_regions/agentless_metric_v5.json`), past Agentless GPT-4o at
  both levels, and replicated held-out as described above.
- **archex had never been measured by us.** Both modes now are
  ([#1](https://github.com/narehart/roust/issues/1)): archex 0.19.2 BM25
  default FILE 56.0 / FUNCTION 38.3 / LINE 25.7; vector/hybrid 57.3 / 40.7 /
  27.7, a single-digit gain with worse latency (12.98s vs 9.68s query median)
  that leaves the ~35-point FILE gap unchanged. The tokenbench agent-loop arm
  for archex is not justified at current quality.
- **True cost per success.** Measured via repeat runs
  ([#16](https://github.com/narehart/roust/issues/16)): roust solves 14/15
  deterministically at ~$1/answer with one real capability gap (django-16400,
  0/10); embedding-RAG reaches everything eventually at a median $2.42 (mean
  $4.90) per first success.
- **Latency had no committed artifact.** Measured
  ([#15](https://github.com/narehart/roust/issues/15)): `latency_v1.json`
  across four repo sizes, then `latency_v2*.json` across seven.

## Engine provenance <!-- note: the Rust port and its parity gate -->

`roust-rs/` is the only engine. It was brought to feature parity with the
now-deleted Python v0.2 engine (channel-aware packing, on-disk cache with
incremental updates, deterministic seed) and passed a bundle-level parity gate
**300/300 exact** on SWE-bench Lite before the Python engine was removed
(`parity/bundle_parity_300.json`: 300 EXACT, 0 region-level differences;
`parity/rust_gate_300_v3.json` is the file-ranking-only gate). `lab/` is a
frozen Python research sandbox (including `lab/lanes2.py`, the oracle the
parity gates were built against); it is never the source of truth for shipped
behavior.

Every evaluation harness refuses to run against a binary whose embedded git
SHA does not match the engine tree under test (`roust --version` embeds the
SHA and a dirty flag), so a stale build cannot silently score.
