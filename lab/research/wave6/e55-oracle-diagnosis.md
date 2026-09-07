# E55: file selection explains much of the depth deficit, but not parity

Full Rust (239) and C++ (129), frozen engine/example at `645170a`, original
exact language-aware scorer, 8192 requested tokens, pad 5, length exponent
0.85. All 368 no-override example payloads match the shipped CLI's regions
and bundle hashes. No engine errors. This experiment supplies gold paths;
**none of its gains is a deployable retrieval improvement**.

| Slice / arm | FILE | FUNCTION | LINE | Mean line fraction | Mean actual tokens |
|---|---:|---:|---:|---:|---:|
| Rust baseline | 60.25 | 20.92 | 7.53 | .248645 | 8464.05 |
| Rust oracle files | 72.38 | 52.72 | 31.38 | .580950 | 7133.25 |
| C++ baseline | 65.89 | 20.93 | 8.53 | .310977 | 8514.95 |
| C++ oracle files | 70.54 | 44.96 | 30.23 | .517708 | 7359.90 |

The intervention replaces the selected file list with sorted old-side gold
paths that exist in the actual corpus. It preserves lexical scores, anchors,
and packing. The output shows that removing irrelevant files and admitting
missing relevant files together can recover substantial depth at lower
actual token cost. This experiment does not isolate those two effects from
each other. It also changes ordering. Its depth scores are observations,
not mathematical upper bounds.

## A verified corpus coverage constraint

66 Rust instances and 38 C++ instances have at least one requested gold file
absent from the actual corpus. Every other instance obtains FILE correctness
under the oracle. Consequently, keeping this corpus membership imposes FILE
ceilings of 173/239 (72.38%) and 91/129 (70.54%) on these exact inputs. These
are corpus-membership ceilings, not general language or packing ceilings.

Absent occurrences in Rust include 145 `.md`, 33 `.toml`, 9 `.lock`, and
shell completions/manpages. C++ includes 64 `.md`, 44 `.txt`, build scripts,
and generator inputs. Exact paths are in the diagnosis JSON. These are
occurrence counts across tasks, not unique files. Existing broad-index flags
cover many of them; prior E41 experiments showed that unselective expansion
can seriously damage ranking, so repeating that alone is not a solution.

## What to change next

The Python Lite reference is FILE 92.33%, FUNCTION 57.67%, LINE 46.00%, and
fraction approximately .537. Even this gold-informed intervention leaves
both exact depth metrics below Python in both languages. Rust fractional
coverage exceeds Python's reference, which does not establish parity across
the metrics. Required work therefore has three parts:

1. Retrieve relevant files more selectively, using an information signal
   beyond the current lexical/graph heuristics. E56 tests a pinned local
   embedding model and fixed lexical fusion.
2. Reach relevant documentation, configuration, and other text without
   letting an expanded corpus overwhelm source retrieval. Raw all-gold FILE
   parity cannot be achieved by changing ranking over the current corpus.
3. Improve within-file localization and budget use; correct file names alone
   do not recover Python-level exact FUNCTION or LINE recall.

The [protocol](e55-protocol.md) records the arXiv motivation. Models' top-k
function metrics remain distinct from this evaluation. No default changes,
no Verified use, and no parity claim result from E55.

Reproduce with [the artifact instructions](../../results_regions/e55/README.md).
