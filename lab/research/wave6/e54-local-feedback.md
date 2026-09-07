# E54 — query-local feedback does not clear the file-recall gate

**Decision: NO ADOPT.** The C discovery slice has unchanged FILE, FUNCTION,
and LINE recall, failing the preset requirement for FILE improvement on both
slices. The complete JS/TS results are retained below. Neither replication nor
Python Verified is used to rescue the failed candidate. [Protocol](e54-protocol.md),
[reproduction](../../results_regions/e53/README.md).

## From absent-file evidence to a testable mechanism

E53's read-only mining joins the archived baseline to the same old-side gold
parser and recorded base commits. Missing source-file occurrences concentrate
in a few repositories:

| Slice | Missing source files | Largest repository contribution | Pass audited index guards |
|---|---:|---|---:|
| JS/TS | 1218 | MUI 846; Svelte 316 | 1213 |
| C | 266 | Pony compiler 252 | 266 |
| Java | 53 | Logstash 32 | 51 |

The guard audit checks suffix, vendor path, byte size, and maximum line
length. Passing these guards is not proof of actual corpus membership; it
does not model ignored/untracked files, every tokenization rule, or ranking.
The five JS/TS suffix exceptions are four `.svelte` files and one `.mjs`;
Java's two are `.sh`. These counts do not justify broadening the index.
Errors in the archived predictions remain missing, not silently excluded.

A companion-file probe proposes the first two absent same-directory
implementation/header or implementation/declaration counterparts in returned
file order. Only 4/338 JS/TS proposals and 0/254 C proposals are gold, with
zero complete FILE rescues. Even admitting every companion would rescue no
JS/TS tasks and only two C tasks (before any budget displacement). Explicit
missing-source basenames occur in just 8/1218 JS/TS and 2/266 C occurrences.
These findings reject blind companion expansion as this round's mechanism.

Inspection of `select_files` suggests a different hypothesis: feedback terms
are selected by whole-file TF×IDF from up to three top implementation files.
`--local-feedback` instead counts terms within merged +/-3-line query-hit
contexts. It keeps the original twenty-term limit, IDF formula, candidate
pool, file-seat cap, and packing defaults. A source without a text hit uses
its original full-file counts. The flag defaults off; no language parser,
source-extension list, or gold-derived term enters the engine.

## Full discovery results

| Slice | Arm | FILE | FUNCTION | LINE | Fraction (errors zero) | Mean tokens |
|---|---|---:|---:|---:|---:|---:|
| jsts (580) | baseline | 46.38 | 31.55 | 14.14 | 0.263083 | 8529.23 |
| jsts (580) | local-feedback | 46.38 | 31.38 | 14.31 | 0.263880 | 8528.83 |
| c (128) | baseline | 51.56 | 28.12 | 13.28 | 0.223155 | 8514.77 |
| c (128) | local-feedback | 51.56 | 28.12 | 13.28 | 0.223748 | 8515.93 |

Fraction uses the strict paired convention: engine errors contribute zero.
The legacy scorer excludes errors only for its fractional mean, so its C
means (.224912 baseline / .225510 treatment) differ from the table. Do not
compare one denominator convention with the other.

| Slice | Metric | Gained/lost | Raw p | Six-endpoint adjusted p |
|---|---|---:|---:|---:|
| jsts | FILE | 0/0 | 1.000000 | 1.000000 |
| jsts | FUNCTION | 0/1 | 1.000000 | 1.000000 |
| jsts | LINE | 1/0 | 1.000000 | 1.000000 |
| c | FILE | 0/0 | 1.000000 | 1.000000 |
| c | FUNCTION | 0/0 | 1.000000 | 1.000000 |
| c | LINE | 0/0 | 1.000000 | 1.000000 |

Paired fraction deltas and 95% bootstrap intervals (10,000 resamples, seed
20260907): jsts: +0.000797 [-0.000613, +0.002923]; c: +0.000593 [-0.000922, +0.002703].

Flag-off identity: jsts: 579 successful payloads plus 1 matching error record; c: 127 successful payloads plus 1 matching error record.
Error IDs and exact-function support diagnostics are included in the paired
artifacts. Costs use pairs successful in both arms (579 JS/TS, 127 C).

Small changes in fractional coverage do not satisfy a file-recall gate.
A nonsignificant loss also would not establish non-regression. These are
previously used research slices, not independent held-out evidence.

## Execution and integrity

Clean main `ff0c995` is compared with clean experimental engine `fddb0a0`.
The enabled arm uses only `--local-feedback`; emitted coverage and the older
block/budget experiments remain off. Structural caches are isolated by arm.
The original source checkouts are only read; retrieval uses private clones.

JS/TS was rerun as four deterministic index-modulo shards for throughput.
The interrupted serial prefix is archived separately in compressed form; the complete aggregate
is the scored run. The merger requires identical provenance and hashes,
nonoverlapping complete IDs, and original dataset ordering. The aggregate's
scorer reads immutable base-commit objects from the existing object stores.

All 128 completed serial-prefix cases match the aggregate in every arm
(384 record comparisons, including matching error records). Compressed inputs
and the identity/hashes report are in `lab/results_regions/e54/serial-prefix/`.
The prefix is not included twice in any score.

Exact scoring uses the unmodified language-aware scorer. Driver memoization
has a byte-identical smoke reference, and per-run artifacts record driver,
scorer, parser, and package hashes/versions. Paired outputs include complete
error lists and non-vacuous function counts; the C slice includes Pony files,
whose methods the C/C++ function scorer does not recognize. Keep FILE/LINE
and the function-support limitation alongside FUNCTION.

The result supports retaining the engine correctness and performance fixes
from E53 while leaving this relevance-feedback heuristic disabled. Better
query-to-file evidence remains an open problem; this test does not establish
that local context is generally useless or that non-Python parity is impossible.
