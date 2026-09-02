# E44 — personalized PageRank as a BUDGET lever (depth without giving up breadth)

## Why this, grounded in what is already proven

Every breadth gain in E28-E42 paid in depth. The mechanism is in
`pack_regions`: the pass-2 marginal score is proportional to
`(0.3 + scores[file])`, and admitted additions enter `scores` at
`0.3 + 0.5*fb_n` -- so the per-file multiplier spans only ~0.6-1.3 and a
wide admitted set gets nearly even budget. Two facts on record say the
`scores` map is the right lever and centrality the right signal:

* **E11b**: raising a gold file's `scores` entry pulled budget toward it and
  lifted FUNCTION 4G/0L on Lite -- the map IS the depth lever.
* **E20**: gold files are disproportionately graph-central; excluding hubs
  taxed exactly the files being rescued.

The literature scan ([LocAgent](https://arxiv.org/abs/2503.09089),
[ARISE](https://arxiv.org/html/2605.03117v1), the
[repo-level survey list](https://github.com/YerbaPage/Awesome-Repo-Level-Code-Generation))
converges on the same reading: file-level localization is well served by
lexical signals; **function/line level is the bottleneck**. That is the
column this campaign has been spending.

## Mechanism

`--ppr-budget <lambda>`: random walk with restart (alpha .15, 25 iters,
same-directory edges at .35 -- the Python reference's dead-code defaults)
from the BM25 seeds over the import graph, plus symbol-reference edges among
the returned set when `--symbol-graph` is on. Normalised over the returned
set and applied to the budget map AFTER selection, so the FILE SET cannot
change -- that is a built-in identity gate, and any FUNCTION/LINE/fraction
movement at fixed cap and budget is a pure depth effect. Language-agnostic,
deterministic, O(edges x 25) per query (tokens +/-3).

## Rust, cap 32, budget 8192, full slice (n=239)

| arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|
| shipped | 60.25 | 19.67 | 7.53 | .2431 |
| symbol-graph + cap 32 | **65.27** | 17.57 | 6.28 | .2103 |
| + PPR multiplicative 0.5 | 65.27 (0 flips) | 16.32 | 5.86 | .1936 |
| + PPR multiplicative 0.8 | 65.27 (0 flips) | 17.15 | 5.86 | .2023 |

**Identity gate passes** (FILE 65.27 -> 65.27, zero per-instance flips at
both strengths): the change is provably budget-only.

**The multiplicative form is NEGATIVE on depth.** Fraction -.0167 (20 gains /
29 losses, Wilcoxon p=.12) at 0.5 and -.0080 (32/36, p=.57) at 0.8;
FUNCTION -1.25 / -0.42; LINE -0.42 at both. Not significant, but the sign is
consistent across every column and both doses, and it is dose-monotone.

Reading: the seeds already sit near score 1.0, so `scores *= (1-l) + l*ppr`
mostly SQUASHES the additions -- and the multi-file gold lives in the
additions. Concentrating on the seeds is concentrating on the wrong files.

## E44b — additive form: also negative

`--ppr-additive`: `scores[f] += lambda * ppr_n[f]`. Raises graph-connected
files toward seed-level funding without lowering anyone -- the E11b pattern,
and E20's one positive mechanism (rescue by insertion, not smoothing).

| arm | FILE | FUNCTION | LINE | fraction | frac gain/loss | Wilcoxon |
|---|---|---|---|---|---|---|
| symbol-graph + cap 32 | 65.27 | 17.57 | 6.28 | .2103 | -- | -- |
| + PPR mult 0.5 | 65.27 (0 flips) | 16.32 | 5.86 | .1936 | 20/29 | p=.12 |
| + PPR mult 0.8 | 65.27 (0 flips) | 17.15 | 5.86 | .2023 | 32/36 | p=.57 |
| + PPR add 0.3 | 65.27 (0 flips) | 17.15 | 6.28 | .2057 | 23/22 | p=.45 |
| + PPR add 0.6 | 65.27 (0 flips) | 16.74 | 5.86 | .1929 | 20/27 | **p=.038** |

**Falsified in both forms.** Every PPR arm is at or below the baseline on
FUNCTION, LINE and fraction; the additive 0.6 arm is significantly negative.
The identity gate held on all four (FILE 65.27 -> 65.27, zero per-instance
flips), so this is a clean result about the SIGNAL, not a bug in the plumbing.

Reading: E20's "gold files are graph-central" is a statement about which
FILES are gold relative to the non-gold pool. It does not carry over to
where the gold LINES are among the files already returned -- there, the
lexical marginal (query-term coverage) is already the better allocator, and
any graph reweighting on top of it is noise or worse. The `scores` map IS
the depth lever (E11b), but PageRank is the wrong thing to put in it.

## E45 — the packer's budget floor: NULL

`--pack-floor` (default 0.3, byte-identical) lowers every file's baseline
claim so allocation follows the lexical score more steeply.

| arm | FILE | fraction delta | gain/loss | Wilcoxon |
|---|---|---|---|---|
| floor 0.15 | 65.27 (0 flips) | +.0051 | 14/11 | p=.77 |
| floor 0.05 | 65.27 (0 flips) | -.0026 | 24/23 | p=.72 |

On the fraction proxy nothing moves. The exact metrics, scored:

| arm | FILE | FUNCTION | LINE | fraction | FUNCTION gain/loss vs sg32 | McNemar |
|---|---|---|---|---|---|---|
| symbol-graph + cap 32 | 65.27 | 17.57 | 6.28 | .2103 | -- | -- |
| floor 0.15 | 65.27 (0 flips) | **18.83** | **6.69** | .2154 | **3 / 0** | p=.25 |
| floor 0.05 | 65.27 (0 flips) | 17.99 | 5.86 | .2077 | 3 / 2 | p=1.0 |
| PPR mult 0.5 | 65.27 | 16.32 | 5.86 | .1936 | 0 / 3 | p=.25 |
| PPR mult 0.8 | 65.27 | 17.15 | 5.86 | .2023 | 2 / 3 | p=1.0 |
| PPR add 0.3 | 65.27 | 17.15 | 6.28 | .2057 | 0 / 1 | p=1.0 |
| PPR add 0.6 | 65.27 | 16.74 | 5.86 | .1929 | 0 / 2 | p=.50 |

Floor 0.15 is the **first depth-only arm in this sequence to move FUNCTION
up at fixed FILE** -- +1.26 (3 gained, 0 lost) with LINE +0.41 -- but three
instances on a 239-slice is not evidence (p=.25), and the dose-response is
non-monotone (0.05 is worse than 0.15 on LINE), which is what noise looks
like. Recorded as a lead, not a result: it needs the two largest slices
(Go 428, JS/TS 580) before it can be believed either way. Every PPR arm is
at or below baseline on FUNCTION; none gains an instance it did not lose.

Taking the floor from 0.3 to 0.05 -- a 6x change in the one constant the
diagnosis blamed -- moves a handful of spans either way.

## Why: the tax is the seat COUNT, measured from the bundles

| Rust arm | files/bundle | spans/bundle | spans/file | files with exactly 1 span | tokens |
|---|---|---|---|---|---|
| shipped (cap 16) | 29.9 | 55.3 | 1.85 | 75% | 8464 |
| symbol-graph + cap 32 | 42.5 | 65.7 | 1.55 | 81% | 8577 |
| + floor 0.05 | 42.5 | 64.1 | 1.51 | 84% | 8569 |

* The harness counts a file as retrieved only if it has **>= 1 span**
  (`files_in_regions = set(regions.keys())`), so every returned file needs a
  pass-1 seat. Cap 32 returns 12.6 more files; spans rise only 10.4; the
  extra seats come straight out of pass-2 depth (spans/file 1.85 -> 1.55).
* The seats are already small -- median first span is **11 lines** in the
  top-16 files and **10 lines** in the tail -- so shrinking them ("stub
  seats") has almost no headroom, and the tail holds 58% of first-span lines
  only because there are more tail files.
* Neither PPR (a new per-file signal) nor the floor (steeper use of the
  existing signal) can help, because pass-2 allocation is not the problem:
  pass-1's mandatory one-seat-per-file is, and it is what makes FILE count.

**Conclusion, measured rather than argued: at a fixed token budget, breadth
and depth are coupled through the mandatory seat count, and redistributing
budget among the returned files cannot uncouple them.** The lever that does
-- proven in E29 (FILE budget-invariant, depth fully budget-recoverable) --
is budget. E46 therefore measures the smallest budget at which sg + cap 32
restores shipped FUNCTION/LINE on Rust while keeping its +5.02 FILE.

## E46 — the depth-neutral budget, Rust, sg + cap 32 (FILE identical by construction)

| budget | FILE | fraction | frac gain/loss | Wilcoxon | tokens | premium |
|---|---|---|---|---|---|---|
| shipped, cap 16 | 60.25 | .2431 | -- | -- | 8464 | -- |
| 8192, cap 32 | 65.27 | .2103 | -- | -- | 8577 | +1% |
| **9216**, cap 32 | 65.27 (0 flips) | **.2397** | 51 / 7 | **p < 1e-4** | 9597 | **+13%** |
| **10240**, cap 32 | 65.27 (0 flips) | **.2553** | 67 / 3 | **p < 1e-4** | 10620 | +25% |

Budget does exactly what E29 predicted and what no redistribution could:
at 9216 the fraction is back to the shipped .2431 within .003; at 10240 it
is ABOVE shipped. Both are significant beyond doubt (51/7 and 67/3
instance-level gains/losses), and the file set is provably unchanged.

So on Rust the genuine operating point is: **+5.02 FILE with shipped-level
depth for ~13% more tokens**, or **+5.02 FILE with depth above shipped for
~25%**. FUNCTION/LINE at these budgets are being scored to confirm on the
exact metrics.

