# Changelog

All notable changes to `roust` are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
- Release infrastructure: tag-triggered PyPI (trusted publishing) + crates.io
  + GitHub Releases (`.github/workflows/release.yml`, `RELEASE.md`).

## [0.2.0] - UNRELEASED (not yet published to PyPI or crates.io) - Single Rust engine

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
