# E55: locate the remaining recall bottleneck

The objective remains language recall parity with Python at the existing
8192-token request budget, using all-gold FILE, exact FUNCTION containment,
all-gold LINE, and fractional LINE coverage. Subset results and oracle results
cannot establish parity. Engine errors stay in the denominator. Python Lite
is discovery; Verified remains a final validation gate.

## Literature motivating the next experiments

[SweRank+](https://arxiv.org/abs/2512.20482) studies multilingual issue-to-code
ranking and iterative query reformulation. This motivates testing a new learned
retrieval signal rather than more variants of lexical packing. Its top-k
function accuracy is not our all-gold token-budget metric. Model release and
training overlap must be checked before using its results as independent
evidence. The Hugging Face model search on 2026-09-07 exposed official original
SweRank models but no official SweRankEmbedMulti checkpoint.

[SWE-Explore](https://arxiv.org/abs/2606.07297) evaluates budgeted code regions
and uses oracle context to diagnose localization. This motivates isolating
file selection from within-file packing; its line budget is not interchangeable
with roust's token budget.

[Repository-level Code Search with Neural Retrieval Methods](https://arxiv.org/abs/2502.07067)
motivates complementary historical and learned ranking signals. Historical
documents must precede each evaluation base commit; no future patch leakage.

## First diagnostic, frozen before measurement

Run full Rust (239) and C++ (129), initially a two-instance wiring smoke.
Each instance runs the shipped CLI, a lab example reproducing its defaults,
and the same example with only the file list replaced by sorted old-side gold
paths. The no-override example must have identical regions and bundle hashes.
Use E51 private clones and isolated per-arm block caches. Record binary/input/
output hashes and commits; use the unchanged language-aware scorer.

The oracle preserves the original lexical file scores, anchors, packing,
and token budget. It reports requested files absent from the actual indexed
corpus instead of silently adding them. This is an observed intervention,
not a strict upper bound: ordering, source coverage, lexical scores, and the
existing packer still constrain it. Gold enters only this explicitly labeled
diagnostic, never a deployable retrieval arm.

Next decisions: if supplying files restores depth, prioritize learned file
ranking; if depth remains weak, add issue-to-region ranking and investigate
packing feasibility. Replicate promising real retrieval changes across all
discovery languages and Lite, with paired tests and token/latency accounting,
before any default adoption or Verified use.
