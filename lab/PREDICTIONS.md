# Pre-registered predictions: SWE-bench Verified, frozen v7 config

Committed while the Verified run is in progress and before any Verified result
has been observed. Config frozen at commit 80a6706 (v7: BM25F + graph frontier
+ monotone history additions + tiered def-symbol anchors + tail-only test/docs
bridges). Headline metric: "Verified MINUS Lite overlap" subset (Lite served as
dev set for five tuning iterations and is contaminated).

## Point predictions (held-out subset)

| metric | prediction | interval |
|---|---|---|
| File@1 | .45 | .41-.49 |
| File@5 | .72 | .69-.75 |
| File@10 | .80 | .77-.83 |
| File@all | .90 | .87-.93 |

## Reasoning

1. The BASE pipeline (v1) was never tuned on SWE-bench at all (archex-tuned)
   and transferred at .890 @all — expected robust.
2. The incremental Lite gains (.890 -> .923 @all, .803 -> .827 @10) came from
   five Lite-informed iterations; standard dev-set optimism suggests roughly
   half of the incremental gain is artifact. Channels ranked by expected
   generalization: hygiene fixes (fully principled) > symbol anchors
   (rarity-gated, principled) > history additions > test/docs bridges
   (cap values tuned on Lite; converted only 1 of 7 ceiling instances even
   on the dev set).
3. Verified issues are human-screened for specification quality; published
   localization numbers run slightly HIGHER on Verified than Lite (e.g.
   CoSIL File@5 86.4 vs 83.7). This pushes our lexical/anchor channels up,
   partially offsetting dev-set shrinkage.

## Falsification criteria (stated in advance)

- Held-out @all >= .92: full generalization; Lite tuning was not overfit.
- Held-out @all in .87-.92: expected outcome; incremental channels partially
  artifact, core claim stands.
- Held-out @all < .87: the post-v1 campaigns were substantially dev-set
  artifacts; report as such and restrict claims to the v1+hygiene config.
- Channel-level check: if bridges/anchors show near-zero net contribution
  held-out (measurable later by ablation), they get demoted from the paper's
  contribution list to its negative-results list regardless of aggregate.

## Results (graded 2026-07-11, run completed after predictions were committed)

Held-out subset (Verified minus Lite overlap, n=407, zero errors):

| metric | predicted | actual | verdict |
|---|---|---|---|
| File@1 | .45 (.41-.49) | .354 | MISS, below interval |
| File@5 | .72 (.69-.75) | .649 | MISS, below interval |
| File@10 | .80 (.77-.83) | .794 | HIT |
| File@all | .90 (.87-.93) | .921 | HIT, >= .92 full-generalization line |

Full Verified (n=500): @1 .382 / @5 .672 / @10 .798 / @all .920.
Lite-overlap subset (n=93): @1 .505 / @5 .774 / @10 .817 / @all .914.

Reading: RECALL generalizes perfectly (.921 held-out vs .923 dev) — the
recall-first architecture and monotone channels transfer. HEAD PRECISION does
not: the 15pp @1 gap between Lite-overlap and held-out mixes two inseparable
effects (Lite instances were selected to be simpler; five tuning iterations
touched the ranking head). Per the pre-registered channel-level criterion, any
paper must report @1/@5 as non-transferring and lead with @10/@all.
