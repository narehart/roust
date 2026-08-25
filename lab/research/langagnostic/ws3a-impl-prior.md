# WS3a — impl_prior v2: stop damping non-Python production code (#56)

**Verdict: DO NOT ADOPT (negative result; flag stays default-OFF).**
The census mechanism was real — v1's `docs?`/`examples?`/`benchmark?s`/
`benches` damping hit 21.4% of indexed JS/TS gold, 15.6% C++, 9.2% Rust,
0.0% Python — and `--impl-prior-v2` collapses those numbers as designed.
But the ranking effect is net NEGATIVE on every affected MSWE slice:
undamping the doc-dir gold also undamps the (much larger) doc-dir noise
population, and the noise wins the budget. Python holds (Lite exact on
FILE/FUNCTION/LINE; Verified within noise, LINE actually +3/−0).

Engine: branch `ws3a-impl-prior` @ `b80cae1` vs main @ `3cb92d9`. All
arms pinned-worktree binaries, private repo copies, detached runs.

## The change (flag `--impl-prior-v2`, default OFF)

`roust-rs/src/core.rs`:

- `TESTLIKE_V2_RE` — v1's alternates minus the four doc-like dir
  components, with `_test\.(py|go|rs|ts|js)$` broadened to
  `_test\.<any ext>$` (Google-style C++ `foo_test.cc` etc.). Damps 0.3x
  in every language.
- `DOCLIKE_V2_RE` (`docs?|examples?|benchmarks?|benches`) — damps ONLY
  non-code files; code-extension files in those dirs get prior 1.0.
- The engine-wide predicate is unified as `testlike_path(rel) =
  impl_prior(rel) < 1.0`, so the structural-expansion hard-exclusion,
  testbridge sources/targets, docsbridge targets, def_index gating, and
  the fence-dominant downweight all shift together (the audit's
  finding-1 exclusion list).
- `VENDOR_V2_RE` (`thirdparty`, one word) joins the vendor guard under
  the flag only — see "VENDOR_RE gap" below.
- `--impl-prior-v2` re-keys the index cache (`:ipv2` marker):
  def_index construction is impl_prior-gated at build time.
- history.rs cochange mining still uses v1 `TESTLIKE_RE` (not implicated
  by the audit; deliberately out of scope this round).

Harness: `--impl-prior-v2` passthrough added to `parity/region_eval2.py`,
`region_eval_verified.py`, `region_eval_full.py`.

## Gate 1 — defaults byte-identity vs main (PASS)

`lab/ws3a_identity_gate.py`, 16 mixed instances (6 Lite Python, 4 jsts,
3 rust, 3 cpp), retrieval-payload md5, two runs per binary, cold `.roust`:
Gate A **0/16 mismatches** for MAIN(3cb92d9) vs BRANCH binary on defaults
— run twice, once at `499ec29` and again at the shipped `b80cae1`
(`lab/results_regions/ws3a/identity_gate.log`, `identity_gate_b80cae1.log`).
Gate B (diagnostic, defaults vs flag): 9/16 differ, every diff attributed
to doc-dir code files entering the bundle (mui `docs/src/pages/...`,
matplotlib `examples/`, tokio `examples/tinyhttp.rs`, Catch2 `examples/`).

## Gate 2 — census re-check (PASS)

`lab/research/langagnostic/ws3a_census_v2.py` (v1 columns reproduce the
audit exactly):

| slice | v1 damped-gold % | v2 damped-gold % | v1 inst % | v2 inst % |
|---|---|---|---|---|
| Lite (py) | 0.0 | **0.0** | 0.0 | 0.0 |
| MSWE jsts | 21.4 | **2.3** | 12.6 | 6.7 |
| MSWE cpp | 15.6 | **0.0** | 7.8 | 0.0 |
| MSWE rust | 9.2 | **0.0** | 10.9 | 0.0 |
| MSWE go | 0.7 | 0.1 | 1.6 | 0.5 |
| MSWE java | 0.8 | 0.8 | 0.8 | 0.8 |
| MSWE c | 0.3 | 0.0 | 0.9 | 0.0 |

jsts residual 2.3% = genuine `.test./.spec./__tests__` files; java's 0.8%
= real `src/test/java` tests (correctly still damped). Repo-tree
spot-check (django/sympy/matplotlib/mui/ripgrep/Catch2): every v1→v2 flip
is a code file under a doc-like dir; every test-convention path still
damps (django 1916→1914 damped; the 2 flips are `docs/conf.py`-class).

## Gate 3 — MSWE arms (FAIL: net negative on all three slices)

Baselines reproduce references digit-exact: jsts 46.38/31.03/13.28/.25820
(= `agentless_metric_mswe_e23_tsblocks.json`), rust 59.83/20.50/7.53/.24214
(= WS2 exp), cpp 65.89/18.60/7.75/.29672 — the WS2 `--cfamily-ext` exp arm
digits, now produced by pure defaults (cfamily default-ON since WS2c), i.e.
the fresh post-cfamily baseline.

| slice (n) | arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|
| jsts (580) | base | 46.38 | 31.03 | 13.28 | .25820 |
| | v2 | 45.17 | 30.86 | 12.41 | .24734 |
| cpp (129) | base | 65.89 | 18.60 | 7.75 | .29672 |
| | v2 (vendor-fixed) | 64.34 | 18.60 | 6.98 | .29090 |
| rust (239) | base | 59.83 | 20.50 | 7.53 | .24214 |
| | v2 | 57.74 | 20.50 | 7.95 | .23884 |

Paired stats (`lab/ws2_paired_stats.py`; two-sided exact sign tests):

- **jsts**: FILE +2/−9 (p=.065), LINE +3/−8 (p=.227), fraction −0.0108
  (+24/−39, p=.077), FUNCTION +6/−7 (p=1). 68/580 changed.
- **cpp**: FILE +0/−2 (p=.5), LINE +0/−1, fraction −0.0058 (+11/−15,
  p=.557), FUNCTION +0/−0. 27/129 changed.
- **rust**: FILE +1/−6 (p=.125), LINE +1/−0, fraction −0.0033 (+16/−18,
  p=.864), FUNCTION +1/−1. 38/239 changed.

Itemized mechanism (`itemize_mswe_*.txt`, one row per changed instance):
both tails are real. Gains where gold IS doc-dir code, now ranked: mui
`docs/src/pages` demo gold (mui-25784 frac +0.747, mui-24794 +0.468),
clap-2253 LINE 0→1 via `benches/`. Losses where the undamped doc-dir
noise displaces: express-3695 LINE 1→0 (examples/ apps flood the bundle),
clap-1710 FILE 1→0, simdjson-958 FILE 1→0 (`benchmark/*.cpp`). The noise
population is an order of magnitude larger than the gold population
(mui alone: 4,032 files undamped, ~30 of them ever gold), so the budget
competition nets negative even though damped-gold coverage collapsed.

## Gate 4 — Python invariance (PASS)

| bench | arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|
| Lite-300 | base (=ref) | 92.33 | 54.67 | 44.00 | .52728 |
| | v2 | 92.33 | 54.67 | 44.00 | .52658 |
| Verified-407 | base (=ref) | 92.38 | 47.17 | 35.14 | .47635 |
| | v2 | 92.38 | 46.68 | 35.87 | .47912 |

Not byte-identity — proven "near": Python repos DO contain v1-damped
doc-dir code (matplotlib `galleries/examples` 521 files, sympy 71,
django 2), so flag-ON reshuffles non-gold ranks. Lite: **zero flips** on
FILE/FUNCTION/LINE; fraction −0.0007 from 2/300 instances (sign p=.5).
Verified: FILE +1/−1, LINE **+3/−0** (django-14539, sphinx-9320,
sympy-18763 all 0→1), fraction +0.0028 (+10/−8), FUNCTION +1/−3
(p=.625). All four metrics hold on both.

## VENDOR_RE gap found and fixed (in this PR, flag-gated)

Identity-gate attribution caught nlohmann/json's
`benchmarks/thirdparty/benchmark/*` (vendored Google Benchmark) entering
v2 bundles: `VENDOR_RE` knows `third_party` but not one-word
`thirdparty`, and v1 masked the gap by damping `benchmarks?/` 0.3x. The
first cpp v2 arm measured it DISPLACING GOLD on nlohmann-944/-969, so
`thirdparty` joined the vendor guard under the flag (`VENDOR_V2_RE`,
commit `b80cae1`), the cpp v2 arm was re-run on the fixed binary
(`mswe_cpp_ws3a_v2fix.jsonl`; zero thirdparty paths in any bundle;
nlohmann-944 no longer changed), and the identity gate was re-proven at
`b80cae1`. The other v2 arms are unaffected — verified by walking all
1,468 unique evaluated base_commit trees (jsts 531, rust 234, Lite 297,
Verified 406): zero contain a `thirdparty` path
(`check_thirdparty_commits.log`). Follow-up for main's default engine:
adding `thirdparty` to `VENDOR_RE` unconditionally is a candidate
micro-round (needs its own byte-identity gate; under v1 damping the
practical harm is bounded, which is why it survived this long).

## Why the audit's expectation missed (ledger note)

The audit predicted FILE gains ("the only mechanism-level FILE lever the
audit found"). The census measured gold-side damping but not the
noise-side population being freed alongside it. In mui, undamping turns
~4,000 demo files loose against ~30 damped-gold files; BM25 length/idf
does not separate a `docs/src/pages` demo from the component source it
imports, and expansion/bridges (now open to those files) amplify the
effect. Damping-side fixes need a noise-side counterweight (e.g. keep
doc-dir files OUT of expansion additions while undamping their direct
score, or a per-dir population prior) — that's a different round, with
this round's itemization as its case-mining seed.

## Artifacts

- arms + logs + itemizations: `lab/results_regions/ws3a/` (10 arms:
  `{mswe_{jsts,cpp,rust},lite300,ver407}_ws3a_{base,v2}.jsonl` +
  `mswe_cpp_ws3a_v2fix.jsonl`, metric JSONs
  `agentless_metric_ws3a_*.json`, `itemize_*.txt`, identity-gate logs)
- census: `lab/research/langagnostic/ws3a_census_v2.py`
- identity gate: `lab/ws3a_identity_gate.py`
- rust gold parquet: `lab/ws3a_rust.parquet` (mswe_ws2c filtered, 239)
