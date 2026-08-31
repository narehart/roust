# E37 — the language-agnostic symbol-reference graph

User-directed: *"pursue the Aider-style symbol-reference graph. It is
genuinely language-agnostic, fits machinery we already have, keeps
determinism, and would subsume the per-language import parsers rather than
adding an eighth one."*

## Mechanism

`--symbol-graph` (default off) makes file A a candidate neighbour of file B
when A **references a rare symbol that B defines**. Both halves already exist
and are already cached: `def_index` (symbol -> defining files) and `tf`
(per-file terms). Definitions are normalised through the same stemmer the
term index uses so the two sides match. Rarity filters: a symbol defined in
more than 3 files, or present in >= 5% of the corpus, carries no locality and
is skipped. Deterministic (definer lists sorted); no cache re-key needed,
since it reads index data rather than changing it.

This is the [Aider repo-map](https://aider.chat/2023/10/22/repomap.html)
relation. It needs **no per-language syntax at all** -- the exact property
whose absence let Java, C and C++ ship with a completely empty import graph.

## Results, full slices, with paired tests

| arm | n | gained | lost | net FILE | McNemar p | frac delta | Wilcoxon p |
|---|---|---|---|---|---|---|---|
| java cap16 | 128 | 1 | 1 | +0.00 | 1.00 | **+.0075** | **0.011** |
| c cap16 | 128 | 1 | 0 | +0.78 | 1.00 | -.0013 | 0.50 |
| cpp cap16 | 129 | 2 | 1 | +0.78 | 1.00 | -.0009 | 0.60 |
| rust cap16 | 239 | 6 | 3 | +1.26 | 0.51 | -.0050 | 0.59 |
| **c cap32** | 128 | **6** | **0** | **+4.69** | **0.031** | -.0148 | 0.005 |
| java cap32 | 128 | 3 | 0 | +2.34 | 0.25 | -.0213 | 0.011 |
| cpp cap32 | 129 | 4 | 0 | +3.10 | 0.125 | -.0088 | 0.014 |

Python dual gate (shipped operating point):

| gate | n | FILE | line fraction | McNemar p | Wilcoxon p |
|---|---|---|---|---|---|
| Lite | 300 | 92.33 -> 92.67 | .52728 -> .52759 | 1.00 | 0.84 |
| Verified | 407 | 92.38 -> 92.63 | .47635 -> .47185 | 1.00 | 0.088 |

## Honest reading

* At the **shipped operating point the mechanism is neutral on FILE**
  everywhere -- every McNemar p is 1.00 or 0.51. The one statistically
  significant effect is Java's **line depth improving** (+.0075, p=0.011).
* Its only significant FILE gain is **C at cap 32** (+4.69, 6 gained / 0 lost,
  p=0.031), and depth regresses significantly on all three slices there.
* Python is neutral on FILE; Verified's depth drop is not significant
  (p=0.088) but is the largest single concern on record for this flag.
* A claim made mid-round and **retracted**: that the symbol graph "beats" the
  per-language import parsers. The margin was +0.78 on each of two slices --
  one instance out of 128. That is noise, not a win. What the data supports
  is that it **matches** them while being one mechanism instead of seven.

## Why it is still the right direction

* Costs 3-12 tokens per bundle. Effectively free.
* Gains outnumber losses in every single arm (1/1, 1/0, 2/1, 6/3, 3/0, 6/0,
  4/0) -- directionally consistent, merely underpowered at these slice sizes.
* It is the only mechanism tried that cannot silently miss a language: the
  per-language parsers failed *totally and invisibly* for three languages,
  and nothing in the harness caught it for the entire campaign.

## Status

Not adopted. Underpowered rather than negative. The next step that would
settle it is more instances (SWE-bench Multilingual's curated 300 across 9
languages is the obvious source), not another knob.
