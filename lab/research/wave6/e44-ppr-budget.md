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

## E45 — the direct knob: the packer's budget floor (running)

The diagnosis still stands: wide admission spreads budget because every
admitted file has a baseline claim of `PACK_FLOOR = 0.3` against a top file's
~1.3. Rather than a new signal, lower the floor so allocation follows the
lexical score that already places regions. `--pack-floor` (default 0.3,
byte-identical). Rust at 0.15 and 0.05, same identity gate.
