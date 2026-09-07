# E52 — overlap-budget accounting does not improve recall

**Decision: NO ADOPT.** Both frozen arms lose mean line coverage on both
full discovery slices and lose exact FUNCTION recall. Neither qualifies for
replication or Python Verified under [the protocol](e52-protocol.md). Defaults
remain unchanged. Together with E51, this round tested five configurations;
none establishes non-Python recall parity with Python.

## Experiment and integrity

The baseline is clean main `ad13f2f`; the experimental engine is clean
`11cef25`. `--unique-span-budget` charges only the incremental token cost of
unioned, unpadded spans in packing pass 2. It skips contained candidates and
is inactive without padding. The wide arm also enables the existing
`--symbol-graph --max-additions 32`. Both use structural blocks, 8,192 target
tokens, padding 5, and length exponent .85. No E51 candidate flags are enabled.
The ranking formula and final padding guard are unchanged.

All 239 Rust and 129 C++ instances completed in every arm with zero engine
errors. Experimental flag-off regions and bundle payloads match baseline on
368/368 instances. Baseline exact scores were reused only after complete
control identity checks against E51, including input and engine provenance;
reuse is recorded in the metric metadata. The original exact scorer reports
zero Git-read failures. Eleven Rust and six C++ cases have no gold functions;
non-vacuous results are recorded separately without changing published scores.

## Full-slice results

FILE, FUNCTION, and LINE are exact all-gold percentages. Fraction is mean
old-side line coverage. Tokens are measured output tokens, so the target is
not a hard bound on the final formatted bundle.

| Slice | Arm | FILE | FUNCTION | LINE | Fraction | Mean tokens |
|---|---|---:|---:|---:|---:|---:|
| Rust (239) | baseline | 60.25 | 20.92 | 7.53 | .248645 | 8464.05 |
| Rust | unique budget | 60.25 | 18.41 | 7.53 | .246903 | 8471.49 |
| Rust | wide unique budget | 65.27 | 17.57 | 7.11 | .230600 | 8586.23 |
| C++ (129) | baseline | 65.89 | 20.93 | 8.53 | .310977 | 8514.95 |
| C++ | unique budget | 65.89 | 19.38 | 6.20 | .299647 | 8519.85 |
| C++ | wide unique budget | 68.99 | 18.60 | 6.20 | .295024 | 8611.24 |

The narrow arm preserves FILE instance by instance. The wide arm gains
12 Rust and four C++ FILE successes, with no losses, but loses depth. Since
it includes an existing breadth mechanism, those FILE gains cannot be
attributed to overlap accounting alone.

## Paired uncertainty

FUNCTION gains/losses and exact two-sided McNemar p-values:

| Slice | Arm | Gained / lost | Raw p | Two-arm adjusted p |
|---|---|---:|---:|---:|
| Rust | unique budget | 0 / 6 | .03125 | .06250 |
| Rust | wide unique budget | 0 / 8 | .00781 | .01563 |
| C++ | unique budget | 0 / 2 | .50000 | 1.00000 |
| C++ | wide unique budget | 0 / 3 | .25000 | .50000 |

The broader eight-comparison correction (two arms × two slices × two depth
endpoints) gives .25 and .0625 for the two Rust FUNCTION comparisons. These
are exploratory results on previously used discovery slices, not fresh
held-out evidence. Rejection follows the preset point-estimate gate and
does not require declaring each loss statistically significant.

Paired 10,000-resample bootstrap intervals, seed 20260907, for fraction deltas:

| Slice | Arm | Mean delta | 95% interval |
|---|---|---:|---|
| Rust | unique budget | -.001741 | [-.009026, +.007908] |
| Rust | wide unique budget | -.018044 | [-.030887, -.008236] |
| C++ | unique budget | -.011330 | [-.021158, -.002717] |
| C++ | wide unique budget | -.015952 | [-.027056, -.006591] |

Measured token growth is below the 2% cap in each arm, but passing cost does
not compensate for failing recall. The artifacts include paired token
intervals and per-instance coverage wins and losses.

## What the two rounds establish

[E51](e51-complementary-packing.md) identifies a useful tradeoff: keeping
structural and shape candidates raises exact FUNCTION by 5.02 percentage
points on Rust and 4.65 on C++, but loses C++ mean line coverage. E52 shows
that removing duplicate span charges alone does not solve that tradeoff.
This does not isolate the cause of each loss: changed selection order,
utility assigned to overlapping text, and the final padding guard can
interact. Candidate-level emitted-span traces would be needed to distinguish
those explanations. No claim of a recall ceiling follows from these nulls.

The next hypotheses should follow the measured failure populations:

- **Rust/C++: emitted-span utility.** About 86%/91% of missing source lines
  are in already retrieved files. Test marginal utility of newly emitted
  text with traces explaining displacement and truncation; simply adding
  windows or correcting overlap cost failed here.
- **JS/TS and C: source-file discovery.** Only about 45%/39% of missing
  source lines are in retrieved files. Mine absent-file cases for concrete
  query-to-path or symbol evidence before proposing another expansion rule.
- **Java and multi-file tasks: completion across file types.** Java's
  source-only FILE score is 82.03% versus 49.22% all-file. Investigate which
  missing non-source files can be admitted without displacing source depth;
  prior broad indexing failures rule out assuming more indexing is enough.

These are untested priorities, not improvements proved by this round.
Python Lite's single-gold-file composition and smaller gold-function context
sizes also make raw cross-language percentages an imperfect matched target.
Retain the original scoreboard while reporting file-count, source-only, and
context-size strata; do not redefine success to manufacture parity.

## Artifacts and validation

Full predictions, manifests, hashes, exact metrics, scoring provenance, and
paired results are in `lab/results_regions/e52/discovery/`. Input snapshots,
mining, and gold-context diagnostics are in `lab/results_regions/e51/`.
See [reproduction instructions](../../results_regions/e51/README.md).

Validation: 118 Rust tests and 21 Python tests pass; targeted checks cover
span union/containment and token boundaries, disabled behavior, incompatible
block flags, and padding-zero identity. Both rounds prove full-discovery
flag-off payload identity. Cached scoring was checked byte-for-byte against
the original scorer on all four smoke arms. Input restoration verifies all
seven non-Verified slices' canonical evaluation rows. No Python Verified
run was used to select, tune, or rescue these candidates.
