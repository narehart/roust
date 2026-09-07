# E53 — engine fixes and emitted-coverage experiment

**Adopt the tested correctness and output-preserving performance changes.
Do not adopt emitted-term coverage.** Both frozen recall arms lose mean line
coverage on full Rust/C++ discovery. No candidate advances to replication or
Python Verified. [Protocol](e53-protocol.md),
[reproduction](../../results_regions/e53/README.md).

## Engine findings and changes

1. The structural dispatch evaluated `shape_blocks_cached` before checking
   whether shape mode was enabled. Default queries paid for an unused parse
   (or cache lookup), and union mode performed a redundant lookup. Check the
   mode before invoking the shape parser.
2. Lexical tokens and token counts share a span cache, but could be computed
   separately. A count-only insertion stored an empty vector, which a later
   lexical lookup treated as computed empty coverage. Represent both states
   independently with `Option`; invalidate the ambiguous legacy format with
   version 2. Cache tests verify recomputation of the actual lexical entries,
   not only equivalent returned bundles. Invalid vocabulary references cause
   recomputation rather than an indexing panic.
3. Concurrent block-cache writers used one temporary filename. Each writer
   now owns a create-new temporary with a process/sequence suffix, publishes
   through rename, and clears the dirty state only after successful publication.
   Concurrent process tests verify complete JSON and stable returned payloads.
4. Structural spans searched later headers repeatedly for the next equal or
   shallower depth, quadratic in deeply nested source. A reverse monotone
   stack finds the same ends in linear time. Exhaustive small depth sequences
   match the original search; a 100,000-header nesting case exercises scaling.
5. Python-compatible line splitting materialized a `(byte offset, character)`
   array for the entire input. The streaming iterator keeps only the returned
   line slices. Exhaustive strings over all supported line boundaries and
   representative multibyte characters match the original implementation,
   including CRLF and trailing-boundary behavior.

The corpus index is unchanged. Existing block caches rebuild once because
format version 1 cannot distinguish a missing lexical value from an empty
one. Lost cache writes may cause recomputation; cache data is not authoritative.
This is a correctness/performance change, not a claim of improved recall.

## Recall hypothesis and result

Pass 1 previously credited all query terms in the original candidate even
when its seat cap omitted their text. `--emitted-coverage` instead credits the
text actually selected (the unpadded source span when padding reconstructs
text). The second arm adds E51 structural/shape union. No cap, file-ranking,
ranking formula, or padding guard was changed. Both flags remain default-off.

| Slice | Arm | FILE | FUNCTION | LINE | Fraction | Mean tokens |
|---|---|---:|---:|---:|---:|---:|
| rust (239) | baseline | 60.25 | 20.92 | 7.53 | 0.248645 | 8464.05 |
| rust | emitted | 60.25 | 20.50 | 8.37 | 0.244894 | 8463.48 |
| rust | emitted-shape | 60.25 | 23.01 | 7.95 | 0.240128 | 8423.95 |
| cpp (129) | baseline | 65.89 | 20.93 | 8.53 | 0.310977 | 8514.95 |
| cpp | emitted | 65.89 | 20.93 | 7.75 | 0.307876 | 8513.62 |
| cpp | emitted-shape | 65.89 | 26.36 | 10.08 | 0.303357 | 8495.81 |

All 368 discovery instances completed with zero engine errors. Fixed-engine
flag-off region/bundle payloads match baseline on 368/368 cases. Exact scores
use the existing language-aware scorer, with empty-function diagnostics and
Git-read failures reported separately. Mean fractions count errors as zero.

| Slice | Arm | FUNCTION gained/lost | Raw p | Eight-comparison p | Fraction delta [95% paired interval] |
|---|---|---:|---:|---:|---|
| rust | emitted | 0/1 | 1.000000 | 1.000000 | -0.003751 [-0.021226, +0.014406] |
| rust | emitted-shape | 10/5 | 0.301758 | 1.000000 | -0.008517 [-0.033125, +0.016836] |
| cpp | emitted | 0/0 | 1.000000 | 1.000000 | -0.003101 [-0.008846, +0.002320] |
| cpp | emitted-shape | 8/1 | 0.039062 | 0.312500 | -0.007619 [-0.030249, +0.015254] |

Intervals use 10,000 paired resamples with seed 20260907. The artifacts also
retain two-arm corrections and paired FILE/LINE and token statistics.

The point-estimate fraction failures suffice for rejection under the frozen
gate; nonsignificant differences are not proof of non-regression. The slices
have been used for earlier research and are not untouched holdouts.

## Traces explain the tradeoff, not a universal remedy

`--pack-trace` emits structured pass-1 candidate/emitted spans, omitted and
retained query terms, and pass-2 admission decisions on stderr. It does not
alter normal stdout. `traces.json` records a post-run autopsy of the largest
fractional gain/loss for each slice and verifies exact payload identity with
the archived predictions.

- `clap-rs__clap-2253`: fraction .8421→0; 13 pass-1 seats omit query terms.
- `tokio-rs__tokio-6462`: fraction 0→1; 20 seats omit query terms.
- `nlohmann__json-708`: fraction 1→.8125; six seats omit query terms.
- `simdjson__simdjson-2178`: fraction 0→.21875; 15 seats omit query terms.

Correcting coverage changes later choices. These examples establish that the
mismatch exists and that correcting it can help or hurt; they do not isolate
all interactions with truncation and final padding. Traces expose decisions
before the final guard; compare `final_regions` to see what was returned.
No parameters were tuned on these post-run examples.

## Performance and validation

The final run (`performance_quiet.json`, conditions recorded separately) ran
with all other task retrieval, scoring, builds, and tests completed. Comparing
clean main `ff0c995` with all fixes in `fddb0a0`, with retrieval experiments off:

| State | Cases | Median per-case latency ratio (fixed / baseline) | Median reduction |
|---|---:|---:|---:|
| Block cache cold, corpus warm | 14 | 0.9029 | 9.7% |
| Block cache warm, corpus warm | 14 | 0.9790 | 2.1% |

All 168 measured invocations (14 cases × two engines × two states × three
repeats), plus warmups, have identical regions and bundles. Warm ratios vary
from 0.930 to 1.044; individual cases can be slower. These are descriptive
medians without a claim of statistically established universal latency gains.
Input hashes, driver hash, binary hashes, and all raw observations are retained.

The timing sample is fourteen fixed tasks (two per non-Verified slice), with
three repeats per state and alternating binary order. It measures CLI latency
with a warm corpus and either cold or warm block cache. Every measured payload
must match baseline. It is a small descriptive sample, not a universal speedup
or a recall gate. The earlier `performance.json` overlapped other jobs and is
retained as exploratory evidence, not used for the final performance claim.
`performance_paused_with_test_overlap.json` also overlapped a targeted cache
test; it is retained separately and excluded from that claim.

Validation includes 125 Rust tests, 21 Python tests against a release binary,
cache/Unicode/header reference-equivalence tests, and four shard-integrity
tests covering valid ordering, duplicates, missing shards, and changed bytes. The exact scorer's new
bounded, content-hash parse cache reproduces all four original smoke metric
files byte-for-byte; the original scorer remains unchanged. Raw predictions,
input/binary hashes, exact metrics, paired statistics, trace records, and
reproduction commands are archived under `lab/results_regions/e53/`.
