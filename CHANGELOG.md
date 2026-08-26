# Changelog

All notable changes to `roust` are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.3.0] - 2026-08-26 - Language-agnostic engine (first published release)

First published release (0.1.0 and 0.2.0 were development milestones, never
published). Distributed through three channels — **npm** (`npm i -g roust` /
`npx roust`, with the platform binary delivered as an `optionalDependencies`
package, the esbuild/Biome model), **crates.io** (`cargo install roust`, and
the build-from-source path for platforms without a prebuilt binary), and
**GitHub Releases** (raw per-platform binaries with `.sha256` checksums). Headline: roust stopped being a
Python-shaped tool. Structural region packing now covers eight languages
via pinned tree-sitter grammars, C-family sources are indexed at all, and
stack traces from four ecosystems feed the file-boost channel -- each
change gated per-language on Multi-SWE-bench slices with the Python
benchmarks proven byte-identical or measured non-negative (campaign issue
#56; per-round evidence in `lab/research/langagnostic/`).

Measured effect, Multi-SWE-bench (corrected tree-sitter scorer; the
pre-campaign FUNCTION figures on non-Python slices were vacuous, produced
by a Python-AST-only gold extractor, and are retired):

| slice | FUNCTION | LINE | fraction |
|---|---|---|---|
| JS/TS (580) | 21.21 -> 31.21 | 9.31 -> 14.14 | .1805 -> .26156 |
| Java (128) | 21.88 -> 35.16 | 13.28 -> 14.84 | .2385 -> .39691 |
| Go (428) | 22.66 -> 29.21 | 19.39 -> 16.59 | .3545 -> .4114 |
| Rust (239) | 9.21 -> 19.67 | 3.77 -> 7.53 | .0976 -> .24315 |
| C (128) | not indexed -> 26.56 | -> 10.94 | -> .1961 |
| C++ (129) | not indexed -> 18.60 | -> 7.75 | -> .29672 |

Python references moved only where an adoption measured a gain: SWE-bench
Lite 92.33 FILE / 54.67 FUNCTION / 44.00 LINE / .52728 fraction, Verified
92.38 / 47.17 / 35.14 / .47635.


- **Behavior change - fixture-dir anchor displacement guard on by
  default** (issue #56 campaign, WS3d, PR #68, adopted 2026-08-26 under
  the standing language-agnostic directive): files under a `*.test/` or
  `*.spec/` DIRECTORY component (the jscodeshift codemod fixture
  convention -- e.g. mui's `jss-to-styled.test/first.actual.js` --
  which the testlike damp's file-infix `.test.` match misses) are
  excluded from symbol-anchor candidacy. Fire-level mining over the
  WS3b/WS3c loss anatomies found this the only rule separating
  displacing anchor fires from the adopted wins (0 win fires, 0 gold
  fires matched across all 306 mined fires). Measured (Multi-SWE JS/TS
  580): LINE 13.97 -> 14.14 (+1/-0: mui-34337 recovers 0 -> 1.0),
  fraction .25979 -> .26156, FILE and FUNCTION invariant with zero
  per-instance flips; base reproduced the WS3c reference digit-exact.
  All other slices proven untouched: java/rust carry zero fixture-dir
  paths in any evaluated tree (per-instance-sha `git ls-tree` census);
  the entire Python exposure (31 pytest Lite/Verified instances, all
  the single path `extra/setup-py.test/setup.py`) is byte-identical
  under the guard. Ranking-side only (fixture files stay indexed and
  lexically rankable; no cache re-key needed). `--displacement-guard`
  is now accepted-but-redundant; `--no-displacement-guard` reproduces
  the pre-adoption anchor channel byte-identically. The WS3c-queued
  GENERAL anchor/trace displacement guard was investigated and closed
  NO-GO: culprit fires are shape-identical to the adoption wins' gold
  fires (mining tables in
  `lab/research/langagnostic/ws3d-displacement-guard.md`).

- **Behavior change - structural-symbol unification on by default**
  (issue #56 campaign, WS3c, PR #67, adopted 2026-08-26 under the
  standing language-agnostic directive): definition-symbol names for the
  def/anchor channel are now sourced from the same pinned tree-sitter
  walks that produce structural blocks, for every grammar-covered
  language (union with the legacy per-language def regexes), and
  anchor-forced region seating is un-gated from `.py`. Java and the C
  family gain a def/anchor channel for the first time; JS/TS arrow
  functions, object-literal methods and class fields become def
  entries; Rust impl/trait/enum and Go grouped-type names are covered.
  Measured (Multi-SWE): Java 47.66/34.38/14.06/.393 ->
  49.22/35.16/14.84/.397 (all four up); JS/TS 46.21/30.86/13.45/.258 ->
  46.38/31.21/13.97/.260 (all four up); Rust FILE 59.83 -> 60.25 and
  fraction +.0013 with a FUNCTION 20.50 -> 19.67 displacement cost
  (+0/-2, itemized in `lab/research/langagnostic/ws3c-symbols.md`).
  Python is held exactly: Lite-300 and Verified-407 all four metrics
  digit-identical per instance (zero FUNCTION flips). `--symbols-v2` is
  now accepted-but-redundant; `--no-symbols-v2` reproduces the
  pre-adoption engine byte-identically. Either state re-keys the index
  cache (`:sv2` marker), so pre-adoption caches rebuild automatically.
  Known anatomy shared with WS3b's trace boost (queued follow-up
  guard): a weak anchor on a non-gold file can displace gold-region
  budget (mui-34337, jackson-databind-4219, clap-4059/5227).

- **Behavior change - multi-format trace-frame boost on by default**
  (issue #56 campaign, WS3b, PR #66, adopted 2026-08-26 under the
  standing language-agnostic directive): the E11b trace-frame FILE boost
  now parses Java (`at pkg.Cls.m(Cls.java:123)`, FQCN->path), Node/V8,
  Go panic locator, and Rust backtrace frames alongside CPython
  tracebacks. Measured: Multi-SWE Java FUNCTION 33.59 -> 34.38 (+1/-0)
  with zero losses on any java metric; rust headline-flat; Python
  provably byte-identical (zero new-format regex matches across
  Lite/Verified/full; 91/91 trace-bearing instances byte-identical in
  both flag states, two runs each). `--trace-formats-v2` is now
  accepted-but-redundant; `--no-trace-formats-v2` reproduces
  CPython-only parsing byte-identically. Known micro-scale anatomy
  (queued follow-up guard): traces that resolve to non-gold files can
  displace gold (svelte-11104, clap-2161).
- **Behavior change - one-word `thirdparty` path component joins the
  vendor guard unconditionally** (WS3b, PR #66; promoted from WS3a's
  flag-gate after zero gold matches across all 8 benchmark slices and
  zero thirdparty paths in every evaluated tree outside nlohmann/json):
  files under a `thirdparty/` component are no longer indexed. Index
  cache format version 3 -> 4 (stale caches rebuild automatically).
  Fresh references: MSWE C++ 65.12/17.83/6.98/.295 (was
  65.89/18.60/7.75/.297; confined to nlohmann, itemized in
  `lab/research/langagnostic/ws3b-trace-formats.md`), MSWE C unchanged
  digit-exact.
- **Behavior change - tree-sitter JS/TS structural blocks on by default**
  (issue #4 campaign, E23, PR #55, user-approved adoption 2026-08-25; step
  one of the language-agnostic campaign, issue #56): .js/.jsx/.ts/.tsx
  files now get tree-sitter CST structural block candidates (functions,
  methods, classes, declarator-bound arrow functions - the same nested
  span shape `python_blocks` emits) in place of fixed +/-30-line windows.
  Measured on the 580-instance Multi-SWE-bench JS/TS slice: FUNCTION
  21.21 -> 31.03 (+68/-11, p=3.5e-11; the previously published 99.83 was
  a vacuous Python-only-scorer artifact, now retired), LINE 9.31 -> 13.28,
  mean fraction .1805 -> .2582, FILE invariant (per-instance identical).
  Python bundles are provably untouched (Lite-300 reproduces the v12
  reference exactly; byte-identity proven per instance in both flag
  states). The flag is named for the mechanism's scope, not one language:
  `--structural-blocks` (ON by default, accepted-but-redundant) /
  `--no-structural-blocks` (escape hatch, reproduces the pre-adoption
  engine byte-identically); `--ts-blocks` / `--no-ts-blocks` remain as
  hidden compat aliases for existing harness scripts and artifact
  provenance. Cost: binary +3.39 MB (three exactly-pinned grammars);
  warm JS/TS structural queries ~2.2 s on axios-scale repos (the packer's
  known structural-candidate cost profile, shared with the Python path).
- **Behavior change - trace-frame FILE boost on by default** (issue #4
  campaign, E11b, PR #52, user-approved adoption): files named in a
  traceback in the query receive a rank-decayed additive file-score boost
  (1/rank for the top-10 frames, raise-site first; 0.1 deeper; 0.1 import
  spillover). Query text is untouched; queries without resolvable frames
  are byte-identical to the previous engine (proven 14/14 instances, plus
  `--no-trace-boost` reproduces the pre-adoption engine byte-for-byte).
  Measured on SWE-bench Lite: FUNCTION 53.3 -> 54.7 (4 gains / 0 losses),
  LINE 42.7 -> 43.3, fraction .5168 -> .5251, File@10 82.7 -> 83.3; on
  held-out Verified: FILE 92.14 -> 92.38, LINE 35.38 -> 35.63, no cell
  regressed. New flags: `--no-trace-boost` (escape hatch), flag-gated
  `--lexboost`/`--lexboost-graph` (E20 experiment, default off, gate
  REJECT - not a default).
- Release infrastructure: tag-triggered npm + crates.io + GitHub Releases
  (`.github/workflows/release.yml`, `npm/`, `RELEASE.md`).

## [0.2.0] - UNRELEASED (development milestone, never published) - Single Rust engine

- `pip install roust` (from a source checkout) now delivers the Rust binary
  directly (maturin `bindings = "bin"`), replacing the parallel Python
  implementation.
- **Behavior change - new region-packing defaults** (issue #4 campaign,
  PR #40): guarded span padding `--pad-lines` (default 5) and sub-linear
  length normalization `--len-exp` (default 0.85) are now the shipped
  defaults. Measured on SWE-bench Lite: FUNCTION 41.0 -> 53.3, LINE 35.7 ->
  42.7, FILE invariant (277/300); replicated on the 407-instance held-out
  SWE-bench Verified set. `--pad-lines 0 --len-exp 1.0` reproduces the
  pre-adoption packing byte-for-byte.
- **Low-confidence / exit-code contract**: `--json` `stats` now includes
  `top_score`, `matched_query_terms`/`total_query_terms`, and a calibrated
  `low_confidence: true` flag (also appended as `[low-confidence match]` to
  the stderr summary). Exit codes: `0` = results found (low-confidence
  matches included - roust still returns its best guess), `1` = no query
  term matched anything in the indexed corpus vocabulary, `2` = usage
  error.
- **Determinism fix** (issue #14): canonical (sorted) IDF summation in
  `pack_regions`' weight() - region packing is cross-process deterministic
  (`HashSet` iteration order previously leaked into region tie-breaks; see
  `roust-rs/PARITY_NOTES.md` item 15).
