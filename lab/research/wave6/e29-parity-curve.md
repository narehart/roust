# E29 — what does multi-file localization cost, per language?

Campaign #4 wave 6, closing round of the standing language-agnostic directive
(#56): get every language to Python-level measurements.
Engine: `roust 0.3.2 (5696ad6, clean)`, one pinned binary for all 35 arms.
**No default was flipped. This round is a MEASUREMENT, not an adoption.**

## Question

E28 rejected the breadth cap on a clean, single-direction result: at the fixed
8192-token budget, FILE rose on 16/16 arms while FUNCTION/LINE fell on 16/16.
Breadth cannibalised depth. The pre-registered escape clause fired exactly as
written, and the round closed NO-ADOPT.

But E28's design could not distinguish two very different explanations for
that trade:

1. **breadth and depth are genuinely coupled** — admitting a file necessarily
   costs you depth in the files you already had; or
2. **the budget was binding** — the same ~8600 tokens were cut into 50 pieces
   instead of 35, and the trade is an artifact of the constant, not the knob.

A 12-instance Go smoke suggested (2): at cap 32, mean gold-line fraction went
23.8% → 36.6% → 46.4% as the budget went 8192 → 16384 → 24576. If that held at
scale, the honest deliverable was never an adoption but a **cost-of-parity
curve**: how many tokens it takes each language to reach Python-level
multi-file localization, and whether depth survives the trip.

That is the round this document reports. Its answer is not the one the design
anticipated, and the reason is worth more than the curve would have been.

## Design

Restricted to the stratum where the question exists: **instances with >= 3
gold files**. E26's reframe is why — SWE-bench Lite is 300/300
single-gold-file, so its 92.33 was never an aggregate, and at 1 gold file cpp
(100), rust (97.6), java (94.1) and py-Verified (95.8) already beat it.
Everything, Python included, collapses at 3+. **Lite is absent from this round
entirely: its 3+ stratum is empty.** That is a fact about the benchmark, not
an omission.

Stratum sizes, derived from the stored default records and matching E28's
table exactly: jsts 207, go 143, rust 105, cpp 55, c 46, java 40, Verified 22
— **618 instances**.

Five arms, not the four originally specified:

| arm | cap | budget | role |
|---|---|---|---|
| a1 | 16 | 8192 | the shipped default — baseline for every delta |
| a2 | 32 | 8192 | E28's rejected arm, replicated on this stratum |
| a3 | 32 | 16384 | |
| a4 | 32 | 24576 | |
| **a5** | **16** | **24576** | **decomposition — added, not in the original design** |

a5 exists because a3 and a4 move the cap and the budget *together*. Without an
arm that moves only the budget, the round could not say which of the two knobs
bought any observed gain, and its central claim would have been confounded.
It cost 618 extra instance-runs. It turned out to carry the result.

## Method

* **One pinned binary, 35 arms.** Built once at `5696ad6` = main (`8cae8b8`)
  plus a single Python-only harness-passthrough commit; `git diff 8cae8b8 HEAD
  -- roust-rs/` is empty, so the engine is byte-identical to main. Never
  rebuilt mid-run. sha256 `cbc68bb5…`.
* **Three flags ported, none of them new engine behaviour.** Main's
  `region_eval_full.py` had none of `--max-additions` (E28's branch),
  `--instances` (E27's branch), or `--budget` (new here). `--budget` rebinds
  the module-level `BUDGET` rather than riding `EXTRA_ENGINE_FLAGS`, because
  the harness already passes `--budget` positionally and appending it would
  forward the flag twice.
* **Instrumentation inert by construction.** Both new harness flags default to
  a sentinel `0` meaning *forward no flag at all*, so a1's argv is
  byte-identical to every pre-E28 default arm's, and a2's to E28's `_m32`.
* **Arm-identity gate on the WHOLE stratum.** a1 and a2 are re-runs of stored
  arms, so they must reproduce them. **1,236 of 1,236 records payload-identical,
  0 differences** (E28's comparable gate sampled 118). The comparison is on
  `regions` / `tokens` / the derived metrics — **never raw JSON**, because the
  `stats` block carries `index_ms`/`query_ms` and a reference binary differs
  from *itself* between runs. `lab/e29_identity.py`.
  This one gate establishes three things the round depends on: that
  `--instances` does not perturb the instances it selects, that `--budget`'s
  sentinel is genuinely inert, and that this round's clone directories hold
  the same corpus E27/E28 used — the check that caught E28's silently-partial
  jsts directory.
* **Private clone dir per concurrent arm** (issue #41), rounds of at most two
  arms per slice so no two live arms ever share a working tree, 10s stagger.
  Scoring ran only after every arm of every round had exited.
* **Scoring.** `lab/agentless_metric_full.py --repos-dir --ts-functions
  --lang-functions` for the six MSWE slices, `agentless_metric_verified.py`
  for Python. Never `lab/agentless_metric.py`, which ignores its CLI args.
  `--expect-n` is the *stratum* size, not the slice size, so a short arm
  cannot pass unnoticed. All 35 metric JSONs crosschecked against recomputed
  headline values: **0 mismatches**.
* **Stats.** Exact McNemar (binomial, two-sided) on the all-or-nothing
  metrics, Wilcoxon signed-rank on per-instance line fraction.

All 35 arms returned exact expected row counts (3,090 records) with **0 errors**.

Artifacts in `lab/results_regions/e29/`. Analysis: `lab/e29_curve.py`,
`lab/e29_residual.py`, `lab/e29_identity.py`.

## The controlling fact: the budget does not buy files

Before any curve can be drawn, one thing has to be true — that spending more
tokens changes *which* files come back. It does not.

`regions` is the returned file → spans map, so its key set is exactly the
bundle's file set. Holding the cap at 32 and tripling the budget:

| slice | n | cap32: 8192 vs 16384 | cap32: 8192 vs 24576 | cap16 vs cap32 @ 24576 |
|---|---|---|---|---|
| JS/TS | 207 | 207/207 | 207/207 | 36/207 |
| Java | 40 | 40/40 | 40/40 | 0/40 |
| Go | 143 | 143/143 | 143/143 | 0/143 |
| Rust | 105 | 105/105 | 105/105 | 13/105 |
| C | 46 | 46/46 | 46/46 | 0/46 |
| C++ | 55 | 55/55 | 55/55 | 20/55 |
| Python Verified | 22 | 22/22 | 22/22 | 0/22 |
| **TOTAL** | **618** | **618/618** | **618/618** | **69/618** |

**The file set is byte-identical on 618 of 618 instances across a 3x budget
range.** The same holds at cap 16 (a1 vs a5): 618/618 identical, FILE% equal
to two decimals in every language. Meanwhile the *cap* changes the set on
549/618.

The mechanism is not subtle in hindsight. File selection happens in
`select_files`, governed by the cap and blind to the budget; the budget only
decides how much of each already-selected file gets packed. **Breadth and
depth are orthogonal knobs.** Tokens buy depth. Only the cap buys files.

The 12-instance smoke that motivated this round already contained this signal
and it was misread: its all-gold column was 7/12 at cap 32 for 8192, 16384
*and* 24576. The FILE column never moved. Only the fraction did.

## Per-slice, per-arm results (>= 3 gold files)

| slice | n | arm | FILE | FUNCTION | LINE | line frac | mean tokens | mean files |
|---|---|---|---|---|---|---|---|---|
| **JS/TS** | 207 | cap16 @ 8192 | 10.14 (21) | 18.84 (39) | 1.45 (3) | 0.19411 | 8536 | 30.57 |
| | | cap32 @ 8192 | 11.11 (23) | 18.36 (38) | 1.45 (3) | 0.18639 | 8663 | 40.46 |
| | | cap32 @ 16384 | 11.11 (23) | 24.15 (50) | 2.42 (5) | 0.27448 | 16319 | 40.46 |
| | | cap32 @ 24576 | 11.11 (23) | 26.09 (54) | 4.35 (9) | 0.33393 | 23383 | 40.46 |
| | | cap16 @ 24576 | 10.14 (21) | 26.57 (55) | 4.83 (10) | 0.33339 | 22999 | 30.57 |
| **Java** | 40 | cap16 @ 8192 | 20.00 (8) | 10.00 (4) | 0.00 (0) | 0.22247 | 8741 | 31.38 |
| | | cap32 @ 8192 | 20.00 (8) | 10.00 (4) | 0.00 (0) | 0.21658 | 8994 | 46.58 |
| | | cap32 @ 16384 | 20.00 (8) | 15.00 (6) | 2.50 (1) | 0.28281 | 17208 | 46.58 |
| | | cap32 @ 24576 | 20.00 (8) | 30.00 (12) | 2.50 (1) | 0.35957 | 25415 | 46.58 |
| | | cap16 @ 24576 | 20.00 (8) | 32.50 (13) | 2.50 (1) | 0.37946 | 25076 | 31.38 |
| **Go** | 143 | cap16 @ 8192 | 27.27 (39) | 3.50 (5) | 0.70 (1) | 0.24980 | 8488 | 33.64 |
| | | cap32 @ 8192 | **37.06 (53)** | 3.50 (5) | 0.70 (1) | 0.23433 | 8618 | 48.79 |
| | | cap32 @ 16384 | **37.06 (53)** | 9.09 (13) | 0.70 (1) | 0.38111 | 16832 | 48.79 |
| | | cap32 @ 24576 | **37.06 (53)** | 18.18 (26) | 5.59 (8) | 0.48932 | 24996 | 48.79 |
| | | cap16 @ 24576 | 27.27 (39) | 20.28 (29) | 6.99 (10) | 0.49284 | 24784 | 33.64 |
| **Rust** | 105 | cap16 @ 8192 | 27.62 (29) | 8.57 (9) | 0.00 (0) | 0.16529 | 8456 | 29.61 |
| | | cap32 @ 8192 | 27.62 (29) | 8.57 (9) | 0.00 (0) | 0.15690 | 8530 | 37.85 |
| | | cap32 @ 16384 | 27.62 (29) | 14.29 (15) | 0.00 (0) | 0.25849 | 16683 | 37.85 |
| | | cap32 @ 24576 | 27.62 (29) | 18.10 (19) | 1.90 (2) | 0.33597 | 24654 | 37.85 |
| | | cap16 @ 24576 | 27.62 (29) | 17.14 (18) | 1.90 (2) | 0.33537 | 24568 | 29.61 |
| **C** | 46 | cap16 @ 8192 | 4.35 (2) | 8.70 (4) | 0.00 (0) | 0.09635 | 8512 | 30.07 |
| | | cap32 @ 8192 | 8.70 (4) | 8.70 (4) | 0.00 (0) | 0.08088 | 8659 | 45.06 |
| | | cap32 @ 16384 | 8.70 (4) | 8.70 (4) | 0.00 (0) | 0.14555 | 16882 | 45.06 |
| | | cap32 @ 24576 | 8.70 (4) | 13.04 (6) | 0.00 (0) | 0.19860 | 25052 | 45.06 |
| | | cap16 @ 24576 | 4.35 (2) | 13.04 (6) | 0.00 (0) | 0.19389 | 24872 | 30.07 |
| **C++** | 55 | cap16 @ 8192 | 25.45 (14) | 9.09 (5) | 0.00 (0) | 0.11175 | 8573 | 27.73 |
| | | cap32 @ 8192 | 27.27 (15) | 9.09 (5) | 0.00 (0) | 0.10788 | 8646 | 34.27 |
| | | cap32 @ 16384 | 27.27 (15) | 10.91 (6) | 0.00 (0) | 0.17319 | 16894 | 34.27 |
| | | cap32 @ 24576 | 27.27 (15) | 21.82 (12) | 0.00 (0) | 0.22808 | 25122 | 34.27 |
| | | cap16 @ 24576 | 25.45 (14) | 21.82 (12) | 0.00 (0) | 0.22838 | 25047 | 27.73 |
| **Python Ver** | 22 | cap16 @ 8192 | 63.64 (14) | 4.55 (1) | 4.55 (1) | 0.24733 | 8564 | 35.36 |
| | | cap32 @ 8192 | 72.73 (16) | 4.55 (1) | 4.55 (1) | 0.21452 | 8702 | 50.91 |
| | | cap32 @ 16384 | 72.73 (16) | 9.09 (2) | 9.09 (2) | 0.31870 | 16940 | 50.91 |
| | | cap32 @ 24576 | 72.73 (16) | 9.09 (2) | 9.09 (2) | 0.43055 | 25129 | 50.91 |
| | | cap16 @ 24576 | 63.64 (14) | 9.09 (2) | 9.09 (2) | 0.47354 | 24872 | 35.36 |

Read the FILE column down each slice: it takes exactly two values, one per cap
setting, and the budget never moves it. Read the FUNCTION and frac columns and
they climb monotonically with budget in every slice.

## The cost-of-parity curve

3+ FILE / mean gold-line fraction against budget.

| slice | 8192 cap16 | 8192 cap32 | 16384 cap32 | 24576 cap32 | 24576 cap16 |
|---|---|---|---|---|---|
| JS/TS | 10.14 / .1941 | 11.11 / .1864 | 11.11 / .2745 | 11.11 / .3339 | 10.14 / .3334 |
| Java | 20.00 / .2225 | 20.00 / .2166 | 20.00 / .2828 | 20.00 / .3596 | 20.00 / .3795 |
| Go | 27.27 / .2498 | 37.06 / .2343 | 37.06 / .3811 | 37.06 / .4893 | 27.27 / .4928 |
| Rust | 27.62 / .1653 | 27.62 / .1569 | 27.62 / .2585 | 27.62 / .3360 | 27.62 / .3354 |
| C | 4.35 / .0963 | 8.70 / .0809 | 8.70 / .1455 | 8.70 / .1986 | 4.35 / .1939 |
| C++ | 25.45 / .1117 | 27.27 / .1079 | 27.27 / .1732 | 27.27 / .2281 | 25.45 / .2284 |
| Python Ver | 63.64 / .2473 | 72.73 / .2145 | 72.73 / .3187 | 72.73 / .4305 | 63.64 / .4735 |

**The FILE half of the curve is a flat line. The depth half is a steep one.**

### Budget to parity: undefined

The requested number — the budget at which each language's 3+ stratum reaches
Python-Verified's default 3+ FILE of 63.64 — **does not exist for any of the
six non-Python slices**:

| slice | 3+ FILE at 8192 | at 16384 | at 24576 | budget to parity |
|---|---|---|---|---|
| JS/TS | 11.11 | 11.11 | 11.11 | **unreachable** |
| Java | 20.00 | 20.00 | 20.00 | **unreachable** |
| Go | 37.06 | 37.06 | 37.06 | **unreachable** |
| Rust | 27.62 | 27.62 | 27.62 | **unreachable** |
| C | 8.70 | 8.70 | 8.70 | **unreachable** |
| C++ | 27.27 | 27.27 | 27.27 | **unreachable** |
| Python Ver | 72.73 | 72.73 | 72.73 | already above |

Not "expensive". Unreachable *at any price*, because the quantity being
spent does not purchase the quantity being measured. Go sits at 37.06 whether
you spend 8k or 24k. **The per-language multi-file gap is a SELECTION gap, not
a budget gap** — and that is a considerably more useful finding than a price
list, because it says where the remaining work has to happen.

## What tokens actually buy: depth, significantly, everywhere

Paired against the default arm (a1), the budget arms are a monotone gain on
the region metrics — and note the McNemar columns: **zero default-only wins
anywhere**.

| slice | arm | McNemar FILE | FUNCTION | LINE | Wilcoxon frac |
|---|---|---|---|---|---|
| JS/TS | cap32 @ 16384 | 0/2, p=0.5000 | 0/11, p=0.0010 | 0/2, p=0.5000 | 119up/2down, p=0.0000 |
| JS/TS | cap32 @ 24576 | 0/2, p=0.5000 | 0/15, p=0.0001 | 0/6, p=0.0312 | 141up/0down, p=0.0000 |
| Java | cap32 @ 24576 | 0/0, p=1.0000 | 0/8, p=0.0078 | 0/1, p=1.0000 | 23up/0down, p=0.0000 |
| Go | cap32 @ 8192 (E28) | **0/14, p=0.0001** | 0/0, p=1.0000 | 0/0, p=1.0000 | 23up/41down, p=0.0078 |
| Go | cap32 @ 16384 | **0/14, p=0.0001** | 0/8, p=0.0078 | 0/0, p=1.0000 | 102up/2down, p=0.0000 |
| Go | cap32 @ 24576 | **0/14, p=0.0001** | 0/21, p=0.0000 | 0/7, p=0.0156 | 124up/1down, p=0.0000 |
| Go | cap16 @ 24576 | 0/0, p=1.0000 | 0/24, p=0.0000 | 0/9, p=0.0039 | 125up/0down, p=0.0000 |
| Rust | cap32 @ 24576 | 0/0, p=1.0000 | 0/10, p=0.0020 | 0/2, p=0.5000 | 87up/1down, p=0.0000 |
| C | cap32 @ 24576 | 0/2, p=0.5000 | 0/2, p=0.5000 | 0/0, p=1.0000 | 28up/0down, p=0.0000 |
| C++ | cap32 @ 24576 | 0/1, p=1.0000 | 0/7, p=0.0156 | 0/0, p=1.0000 | 41up/0down, p=0.0000 |
| Python Ver | cap32 @ 24576 | 0/2, p=0.5000 | 0/1, p=1.0000 | 0/1, p=1.0000 | 16up/1down, p=0.0011 |

Go's FILE column is the cleanest illustration in the round: **0/14 at every
one of the three cap-32 budgets, and 0/0 for cap 16 at 24576.** The same
fourteen instances, won by the cap, unmoved by the budget.

## Two prices worth naming

### The depth-neutral budget — what E28's breadth actually costs

If the budget cannot buy files, the parity bar is not the right thing to
price. The meaningful price is: how many tokens does it take for the cap-32
arm to stop being *shallower* than the shipped default? That is E28's cost,
paid in budget instead of in depth.

| slice | default frac | cap32 @ 8192 | cap32 @ 16384 | est. depth-neutral budget | premium | FILE bought |
|---|---|---|---|---|---|---|
| JS/TS | 0.19411 | 0.18639 | 0.27448 | ~8910 | +718 (9%) | +0.97 |
| Java | 0.22247 | 0.21658 | 0.28281 | ~8920 | +728 (9%) | +0.00 |
| **Go** | 0.24980 | 0.23433 | 0.38111 | **~9055** | **+863 (11%)** | **+9.79** |
| Rust | 0.16529 | 0.15690 | 0.25849 | ~8869 | +677 (8%) | +0.00 |
| C | 0.09635 | 0.08088 | 0.14555 | ~10152 | +1960 (24%) | +4.35 |
| C++ | 0.11175 | 0.10788 | 0.17319 | ~8678 | +486 (6%) | +1.82 |
| Python Ver | 0.24733 | 0.21452 | 0.31870 | ~10772 | +2580 (31%) | +9.09 |

These are interpolations between two measured points, not measurements.
**Go's is the number to quote: roughly 9,055 tokens — an 11% premium — buys
E28's +9.79 3+ FILE at no net depth cost.** Python Verified's 31% is the most
expensive, and Java's and Rust's premiums buy nothing at all (+0.00 FILE).

### The residual cost of breadth when the budget is not binding

Pairing a4 against a5 holds the budget at 24576 and moves only the cap — the
comparison E28 could not make.

| slice | dFILE | McNemar FILE | dFUNCTION | dfrac | Wilcoxon frac |
|---|---|---|---|---|---|
| JS/TS | +0.97 | 0/2, p=0.5000 | -0.48 | +0.00054 | p=0.8666 |
| Java | +0.00 | 0/0, p=1.0000 | -2.50 | **-0.01989** | **p=0.0078** |
| Go | **+9.79** | **0/14, p=0.0001** | -2.10 | -0.00351 | p=0.2503 |
| Rust | +0.00 | 0/0, p=1.0000 | +0.96 | +0.00059 | p=0.6721 |
| C | +4.35 | 0/2, p=0.5000 | +0.00 | +0.00470 | p=0.7148 |
| C++ | +1.82 | 0/1, p=1.0000 | +0.00 | -0.00030 | p=0.6250 |
| Python Ver | +9.09 | 0/2, p=0.5000 | +0.00 | -0.04299 | p=0.1250 |

**On 6 of 7 slices the depth cost of breadth is statistically indistinguishable
from zero once the budget is not binding** — Go keeps its +9.79 FILE at
p=0.0001 while its fraction moves −0.0035 (p=0.25, n.s.). Java is the
exception and moves the wrong way (−0.0199, p=0.0078).

So E28's diagnosis stands but its *attribution* was half wrong. The depth cost
E28 measured was real and is genuinely a fixed-budget artifact — it largely
dissolves when the budget is relaxed. The FILE gain, however, was never
budget-related in either direction, so the two halves of E28's "trade" were
never actually coupled by a shared mechanism. They were two independent
effects that happened to be observed together because only one knob was moved.

## Engaging the Recall Trap honestly

**The Recall Trap (arXiv:2608.14838)** found that under *fixed-budget* context
packs on SWE-bench Verified, the higher-recall configuration put the gold file
in 87.8% of packs vs 80.6%, and the *lower*-recall config resolved +7.6pp more
issues (GPT-5.6, 39.2 → 46.8, n=500, p=0.0003). E28 reproduced the first half
in-harness.

Varying the budget tests a materially different claim, and it is worth being
explicit about why that is legitimate rather than a way around E28's negative:

* The Recall Trap's result is **conditional on a fixed budget** — that is the
  premise of its design, stated in its own framing. Asking what happens when
  the budget moves is not a re-run of a lost experiment under friendlier
  conditions; it is a question the original design excluded by construction.
* E29 does not contradict it. It **localizes** it. The trade the paper
  identifies is real at fixed budget and E29 shows it relaxing as the budget
  relaxes — exactly what a budget-division mechanism predicts.
* And E29 gives the trap a sharper edge for this engine: since tokens cannot
  buy files here, **there is no version of "spend more to get more recall"
  available at all.** The only way to raise recall is the cap, which is
  precisely the lever the trap warns about. That is a stronger reason for
  caution than E28 had, not a weaker one.

What E29 emphatically does **not** show is that a bigger budget is better
downstream. roust's harness has no execution-graded consumer. FUNCTION and
LINE rising with budget is a retrieval-metric statement; the Recall Trap's
finding was that *depth* wins downstream, and depth is what rises here, so the
direction is at least consistent — but "consistent with" is not "demonstrated".

## Verdict — measurement, no adoption

**Nothing is adopted and no default is flipped.** `--max-additions` stays at
16 and `--budget` stays at 8192.

The framing discipline this round was commissioned under holds, and two points
must be stated plainly:

* **Cross-budget rows are NOT comparable to the published 8192 scoreboard.**
  Every number in the 16384 and 24576 columns describes a product that does
  not exist. The scoreboard remains the 8192 figures.
* **A larger budget is not a free win.** 8192 is a product choice matched to
  agent context windows. A 24,576-token bundle is 3x the cost, and it is
  charged to the consumer's context — the very context the tool exists to
  conserve. roust's charter is "1.00-recall retrieval at >= 70% token savings";
  tripling the bundle attacks the second clause directly.
* **Is depth preserved or merely restored?** Restored, then exceeded — but by
  spending, not by design. At the depth-neutral budget it is exactly restored;
  beyond that it is bought.

## What this changes

E27 falsified sibling **ranking**. E28 priced sibling **admission** and
declined it. E29 removes a whole class of proposed remedy from the table:

> **The multi-file gap cannot be bought with tokens.** File selection is
> budget-invariant on 618/618 instances. Any future proposal of the form
> "give the packer more room" is answered in advance.

That leaves the candidate-set and selection layers as the only place the gap
can move, which is exactly where the campaign's META-FINDING says the signal
is exhausted (E20 hubs, WS3d fires, E27 seats: gold and non-gold pool
candidates are indistinguishable on co-change, directory proximity, and shared
identifiers). The two findings together are a sharp statement of where this
line of work stands: **the files are reachable (E28's mining), the budget is
not the obstacle (E29), and the available signals cannot tell which to pick
(E20/E27).**

The queue that survives:

1. **Budget reallocation between pass 1 and pass 2** — still live, and now
   better targeted. E29 shows a newly-admitted file costs the pack ~nothing at
   a large budget; a floor allocation would aim to reproduce that at 8192.
2. **Set-valued output** — return several candidate bundles for multi-site
   patches, sidestepping the single-division problem entirely. Untouched by
   this round's negative, since it does not spend more tokens per bundle.
3. **A better selector, not a bigger one.** E29 says the packer is not the
   bottleneck. Anything that moves 3+ FILE has to change *which* files
   `select_files` ranks into the top 16 — a discrimination problem, and the
   one the campaign has repeatedly failed to solve with existing signals.

## Anomalies

* **Java pays more depth for breadth at 24576 than at 8192** (−0.0199,
  p=0.0078) — the only slice where relaxing the budget makes the trade *worse*.
  Python Verified directionally does the same (−0.0430) but at n=22 and
  p=0.1250 it is not significant. Unexplained; flagged rather than smoothed.
* **Java and Rust are inert to the cap at every budget** (+0.00 FILE on all
  arms, 0/0 discordant). E28 saw the same and attributed it to pools that do
  not hold 24 eligible candidates. E29 confirms it is not a budget effect.
* **C's FUNCTION is flat from 8192 to 16384** (8.70 at both) then jumps to
  13.04 at 24576 — the only slice with a dead zone in the middle of the range.
* **`--budget` must not ride `EXTRA_ENGINE_FLAGS`.** The harness already passes
  `--budget` positionally in `run_roust`; appending it would forward the flag
  twice. It rebinds the module-global instead. A launcher written in zsh also
  silently breaks the flag: zsh does not word-split unquoted parameters, so
  `$extra` arrives as one argument and argparse rejects `--budget 24576` as an
  unrecognized token. The launchers are `#!/bin/bash` for this reason.
* **`--instances` still is not on main.** E27 added it on its branch, E29
  re-ported it here alongside `--max-additions` and `--budget`. Three
  measurement flags have now been ported twice each. Worth landing.
