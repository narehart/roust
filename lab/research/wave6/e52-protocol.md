# E52 — charge the union of overlapping spans

E51's completed discovery arms all fail the positive mean-fraction criterion:
shape union changes Rust by +.000798 and C++ by -.005560; hit windows lose
.034008 and .031071. No E51 candidate proceeds to replication or Verified.
Exact scoring is still being completed for the full report; it cannot reverse
that prespecified fraction failure. Defaults remain unchanged.

The hit-window output uses only 7,820 tokens on Rust versus 8,464 baseline.
Code inspection finds that pass 2 charges every selected candidate in full,
even when its text overlaps earlier spans; the padded output subsequently
merges those spans. This motivates a separate budget-accounting experiment.

`--unique-span-budget` charges the change in the token count of the union of
unpadded spans for the selected file. Fully contained candidates are skipped;
the ranking formula, candidate definitions, file selection, and final padding
guard stay unchanged. It is inactive with `--pad-lines 0`, whose output does
not merge overlaps. The flag defaults OFF. This is not a claim of monotone
recall: a changed selection prefix can interact with the final padding guard.

Two frozen arms: the flag alone, and the flag plus existing `--symbol-graph
--max-additions 32`. No E51 block-representation flags are used. Radius and
other tuning constants are unchanged. The baseline remains main `ad13f2f`.

Use the same discovery (full Rust/C++), exact scorer, private clones, identity
proof, costs, and non-regression criteria as E51. Select at most one candidate
with positive FUNCTION or LINE and positive fraction on both discovery slices,
no FILE regression, and <=2% token growth. Rank qualifiers by mean per-slice
FUNCTION gain, then fraction. Account for two arms in paired-test correction.
Only a qualifying frozen candidate replicates on Java/Go/JS-TS/C/Lite; only
a nonnegative result in every metric and slice reaches Python Verified.
No parameter tuning uses replication or Verified. If this also fails, record
the bounded null and the remaining bottlenecks; do not declare parity impossible.
