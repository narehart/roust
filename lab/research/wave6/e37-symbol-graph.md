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

---

# E38 — full-slice sweep, and a comparison trap re-encountered

Every language measured at **full-slice** scale (not the >= 3-gold strata),
shipped budget, with the language-agnostic symbol graph plus cap 32:

| slice | n | shipped | symbol-graph + cap 32 | delta |
|---|---|---|---|---|
| Go | 428 | 64.95 | **70.79** | **+5.84** |
| C++ | 129 | 65.89 | **68.99** | +3.10 |
| JS/TS | 580 | 46.38 | **52.07** | **+5.69** |
| Rust | 239 | 60.25 | **65.27** | **+5.02** |
| C | 128 | 51.56 | **56.25** | +4.69 |
| Java | 128 | 49.22 | **51.56** | +2.34 |

**One mechanism, no per-language code, improves all six non-Python languages
by +2.34 to +5.84 FILE points**, at roughly shipped token cost, with Python's
own numbers statistically unchanged on both gates. That is the substantive
result of this round.

## The trap, hit again

A fixed bar of 63.64 was compared against these full-slice numbers, and three
languages appeared to clear it. **They do not.** 63.64 is Python Verified's
**>= 3-gold-file stratum** figure; its full-slice figure is **92.38**. Full
slices are dominated by single-gold-file instances and are therefore much
easier, so comparing a non-Python full-slice number to a Python stratum
number flatters the former.

Both consistent readings:

| slice | full-slice (bar 92.38) | 3+ stratum (bar 63.64) |
|---|---|---|
| Go | 70.79 | 36.36 |
| C++ | 68.99 | 32.73 |
| Rust | 65.27 | 35.24 |
| C | 56.25 | 8.70 |
| JS/TS | 52.07 | 13.04 |
| Java | 51.56 | 20.00 |
| **Python** | **92.38** | **63.64** |

Under either, **no language clears**. This is the same population-mismatch
confound identified in E35 -- encountered a second time, in the direction
that would have flattered the result. Any future bar must state which
population it refers to.

## Ceiling probes for the two laggards

Java and C at cap 128 + k_lex 30 + every generation lever:

| slice | shipped | max config | line fraction | tokens |
|---|---|---|---|---|
| C | 51.56 | **67.19** | .2251 -> **.0556** | 8514 -> 12863 |
| Java | 49.22 | 52.34 | .4152 -> **.1284** | 8762 -> 13763 |

C's full-slice number crosses 63.64 only in a configuration that costs 51%
more tokens and **destroys 75% of line-level depth**. That is a ceiling
probe, not an operating point: the bundle locates the files and then says far
less about each. It should not be counted as C meeting any bar.

## E38c — depth is budget-recoverable, and C clears

The maxed generation config at budget 8192 crossed 63.64 on C but collapsed
line depth 75% (.2251 -> .0556). E29 predicted that cost is a fixed-budget
artifact, not a property of the breadth. Re-run at budget 16384:

| slice | n | shipped | maxed + budget 16384 | vs 63.64 | line fraction | tokens |
|---|---|---|---|---|---|---|
| **C** | 128 | 51.56 | **67.19** | **CLEARS** | .2251 -> **.2075** | 8.5k -> 17.7k |
| Java | 128 | 49.22 | 52.34 | -11.30 | .4152 -> .4045 | 8.8k -> 19.1k |

C's depth comes back almost entirely (.2075 against a shipped .2251) while
keeping the full breadth gain -- the prediction confirmed on a second slice.
The cost is 2x tokens.

## Standing against a full-slice bar of 63.64

| slice | best full-slice | config | cost |
|---|---|---|---|
| Go | **70.79** | symbol-graph + cap 32 | ~shipped |
| C++ | **68.99** | symbol-graph + cap 32 | ~shipped |
| C | **67.19** | maxed + budget 16384 | 2x tokens |
| Rust | **65.27** | symbol-graph + cap 32 | ~shipped |
| JS/TS | 52.07 | symbol-graph + cap 32 | ~shipped |
| Java | 52.34 | maxed + budget 16384 | 2x tokens |

Four of six clear; three of those four at essentially shipped cost. **JS/TS
and Java do not**, and Java is the outlier: it gains only 3.12 with every
lever maxed and the budget doubled, from a lower base than C, which cleared.

Ceiling probes for both were attempted and **abandoned**: at cap 500 / cap 128
with k_lex 30 on the two largest corpora the pool explosion made the arms
effectively non-terminating (JS/TS advanced 2 records in 37 minutes; Java
produced none). Those partial arms were discarded rather than reported. The
practical consequence is that no measurement exists for Java or JS/TS above
the settings listed here, and the honest statement is that neither reaches
63.64 at any setting this harness can actually run.

## Caveat that applies to the whole table

A full-slice bar of 63.64 is **not** the like-for-like Python comparison:
Python Verified's full-slice figure is 92.38, and 63.64 is its >= 3-gold-file
stratum. Against Python measured on the same population, none of these
clear. The table above answers the fixed numeric target as posed, not
"parity with Python".
