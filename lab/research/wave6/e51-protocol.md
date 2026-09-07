# E51 — non-Python recall: complementary packing candidates

## Mining before implementation

Reproduce with `uv run --no-project --with pandas --with pyarrow python
lab/e51_mine.py --out lab/results_regions/e51/mining.json` (join the command
onto one line). The report hashes all gold and archived E47 prediction inputs.
Gold parsing and error handling use the existing evaluator; Python Verified
is excluded from mining. Source-only metrics are diagnostics with an explicit
extension set and a non-vacuous denominator, not a replacement scoreboard.

The archived Rust source-line deficit is 35,207 lines in retrieved files versus
5,799 in absent files; C++ is 26,980 versus 2,544. Packing accounts for 85.9%
and 91.4% of those source-line deficits respectively. Java source-only FILE
is 82.03%, versus 49.22% all-file FILE: dataset composition matters. JS/TS
and C still have substantial source-file retrieval deficits. These are line-
weighted diagnoses, not per-instance success rates or attainable ceilings.

E25 specifically left an untested union of allowlisted and shape-based block
candidates. Current pass 1 can truncate a large block from its header, leaving
query evidence deep inside a function unpacked. Test complementary candidates
rather than replacing the existing structural representation.

## Frozen hypotheses and arms

All arms use the current shipped 8192-token budget, floor 0.15, and tail seats.
No indexing extensions, gold filters, or query text are changed.

1. `shape-union`: structural candidates plus shape candidates (E25 follow-up).
2. `hit-windows`: structural candidates plus independent +/-10-line windows
   centered on query-hit lines in grammar-covered non-Python files. Keep
   overlaps as alternative candidates; deduplicate exact spans. This bounds
   individual candidates rather than merging dense hits into giant blocks.
3. `wide-hit-windows`: arm 2 plus existing `--symbol-graph --max-additions 32`.
   Tests whether complementary packing recovers the depth cost of breadth.

These are research flags, OFF by default. Do not tune radius or other constants
on observed results in this round. Candidate generation changes only for the
wide arm; FILE must remain identical for each packing-only arm.

## Evaluation and decision

- Freeze clean baseline and experimental binaries and record SHA256 and engine
  commit. Prove flag-off payload identity against main, excluding provenance
  and timing metadata, on all discovery instances.
- Use private shared-object clones; never checkout/clean the existing datasets'
  working trees. Reuse the existing region evaluator and language-aware exact
  function scorer. Record failures as wrong, including timeouts; compare exact
  instance sets, never only their intersection.
- Discovery: full Rust and C++ slices. Select at most one candidate with a
  positive exact FUNCTION or LINE result, positive mean line fraction, no
  FILE regression, and <=2% mean-token growth. Rank qualifying arms by mean
  per-slice FUNCTION improvement, then mean fraction improvement. If none
  qualifies, stop and record a null; no Verified inspection.
- Replicate the frozen candidate on full Java, Go, JS/TS, and C slices and
  Python Lite. Report every slice, exact paired McNemar tests for FILE,
  FUNCTION, and LINE, and paired bootstrap intervals for fraction/token deltas.
  Do not change parameters after replication.
- Only a candidate with nonnegative FILE/FUNCTION/LINE/fraction in each slice
  and <=2% token growth proceeds to the 407-instance Python Verified final
  gate. Apply the same non-regression criteria there. A nonsignificant loss
  does not establish safety. Report zero-function cases separately.
- A positive default adoption additionally needs statistically supported
  improvement (paired test with correction for the three candidate arms),
  relevant Rust/unit and Python CLI checks, a PR, and CI. Otherwise retain
  the measurement as a null or opt-in experiment without a default flip.

The Python comparison is the current full-slice scoreboard (92% FILE, with
FUNCTION/LINE and token cost alongside it), never the historical 63.64% value
from a 22-instance multi-file subset. No finite null proves parity impossible.
