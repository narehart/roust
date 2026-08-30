# E31 / E32 — the admission ceiling, and the missing import graph

These two rounds **overturn** the conclusion E30 closed on. E30 reported that
the multi-file gap was "not reachable by re-ranking or re-composing the
existing candidate pool". The first half of that is right and still holds.
The second half — the implied claim that *breadth* could not help — was an
overgeneralisation from a single one-step negative (E28 raised the admission
cap 16 -> 32 and lost on the region metrics), and it is wrong.

## E31 — admission was never exhausted

Nobody had swept the cap. Go's >= 3-gold-file stratum, n = 143:

| cap | 16 (shipped) | 32 (E28) | 64 | 128 | 500 |
|---|---|---|---|---|---|
| all-gold FILE % | 27.27 | 37.06 | 44.06 | 52.45 | **57.34** |

Monotone, and cap 500 vs cap 32 **gains 29 instances and loses 0**. The
engine admits well under half the gold its own candidate pool already holds.

cap 500 measures **57.34 at budget 8192 and 57.34 at budget 24576**, which
independently re-confirms E29's budget-invariance of the FILE column at a
completely different cap. At the larger budget the line fraction is .4018
against the shipped default's .2498 — strictly better on breadth *and* depth,
for ~3x the tokens.

### The cross-language split

Every slice, >= 3 gold files, cap 16 -> cap 128:

| slice | FILE @16 | FILE @128 | delta |
|---|---|---|---|
| Go | 27.27 | 52.45 | **+25.17** |
| Python Verified | 63.64 | 86.36 | **+22.73** |
| C | 4.35 | 10.87 | +6.52 |
| JS/TS | 10.14 | 12.56 | +2.42 |
| C++ | 25.45 | 27.27 | +1.82 |
| Java | 20.00 | 20.00 | **0.00** |
| Rust | 27.62 | 27.62 | **0.00** |

Two different failure modes, not one:

* **admission-bound** (Go, Python) — the pool holds the gold, the engine
  would not admit it;
* **generation-bound** (Java and Rust at *exactly* 0.00 across caps 16, 32
  and 128; also JS/TS, C++, C) — no cap helps because the gold is never
  proposed as a candidate at all.

Note what this does to the goal as literally posed: Python gains more than
every language except Go, so measured at the same setting the bar moves from
63.64 to 86.36 and the spread *widens*. Admission alone cannot produce parity.

## E32 — the candidate generator, and a language-agnostic hole

Candidate generation is `edges` (import graph) + same-directory + co-change.
Two levers, both flag-gated and default-off.

### `--import-hops 2` (second-hop closure)

| slice | cap128 | cap128 + 2hop | delta |
|---|---|---|---|
| JS/TS | 12.56 | **22.71** | **+10.14** |
| Rust | 27.62 | **33.33** | **+5.71** |
| Go | 52.45 | **57.34** | **+4.90** |
| Java | 20.00 | 20.00 | 0.00 |
| C | 10.87 | 10.87 | 0.00 |
| C++ | 27.27 | 27.27 | 0.00 |
| Python Verified | 86.36 | 86.36 | 0.00 |

It moves **every language that has an import graph** and **nothing** that
does not. Rust had been inert to every admission lever ever tried; the
generation lever breaks it.

### `--import-edges-v2` (the hole)

`file_import_targets` handled `.py`, `.js/.ts/.jsx/.tsx`, `.rs` and `.go` —
and nothing else. **Java, C and C++ files had an entirely empty import
graph**: no candidate generation, no Guarantee-1 seat. That is why Java is
inert at every cap, why a second hop over its graph was a *byte-identical*
no-op (no edges to walk), and a large part of why C sits at 4.35.

The language-agnostic campaign made *indexing* (extensions) and *structural
parsing* (tree-sitter) language-agnostic. The import graph — a core retrieval
signal — was never audited and stayed Python/JS/Rust/Go only.

Resolving `import a.b.C;` to a path ending `a/b/C.java`, and `#include
"foo/bar.h"` relative-then-suffix:

| slice | cap128 | + ie2 | delta |
|---|---|---|---|
| Java | 20.00 | **22.50** | **+2.50** |
| C | 10.87 | **13.04** | **+2.17** |
| C++ | 27.27 | 27.27 | 0.00 |

Java's first non-zero movement of the entire campaign.

### The two generation levers combined

Once Java/C/C++ finally *have* edges, the second hop has something to walk:

| slice | default (cap 16) | cap128 | + ie2 | + ie2 + 2hop |
|---|---|---|---|---|
| **C** | 4.35 | 10.87 | 13.04 | **21.74** |
| **C++** | 25.45 | 27.27 | 27.27 | **29.09** |
| Java | 20.00 | 20.00 | **22.50** | 20.00 |

C ends at **5x its shipped default**. Java is the exception: the second hop
*costs* it the 2.50 that the edges won, so its best configuration is edges
without hops — a per-language interaction, not a uniform win, and one reason
none of this is adoptable as a single global default without a further round.

### Best measured configuration per slice (>= 3 gold files)

| slice | shipped default | best measured | config |
|---|---|---|---|
| Python Verified | 63.64 | **86.36** | cap 128 |
| Go | 27.27 | **57.34** | cap 128 + 2hop |
| Rust | 27.62 | **33.33** | cap 128 + 2hop |
| C++ | 25.45 | **29.09** | cap 128 + ie2 + 2hop |
| JS/TS | 10.14 | **22.71** | cap 128 + 2hop |
| Java | 20.00 | **22.50** | cap 128 + ie2 |
| C | 4.35 | **21.74** | cap 128 + ie2 + 2hop |

Every slice improves, several by a lot. The *goal* is still unmet, because
Python improves too (63.64 -> 86.36) and remains clearly ahead.

## Status and honest limits

* **No default is flipped.** All three flags (`--max-additions` is already
  exposed, `--import-hops`, `--import-edges-v2`) default to shipped
  behaviour, and Python is untouched by construction.
* Every high-cap number above costs tokens: cap 128 runs ~8.9-12.0k against
  the shipped ~8.5k, and the line fraction *drops* at a fixed budget. E29
  says that depth is budget-recoverable, but these rows are **not**
  comparable to the published 8192 scoreboard and must not be quoted as if
  they were.
* FUNCTION/LINE were not re-scored for the E31/E32 arms; FILE and the
  in-record line fraction are what these rounds measured.
* The parity goal is **still not met**: at each slice's best measured
  configuration the ordering is Python 86.36, Go 57.34, Rust 33.33,
  C++ 29.09, JS/TS 22.71, Java 22.50, C 21.74.
* The best configuration is **not the same for every language** (Java is hurt
  by the second hop that helps everyone else), so there is no single global
  default here yet — picking one is a further round's work.

## Process note

A one-step negative was generalised into an architectural impossibility claim
and stated as terminal. The correct discipline is to **sweep a knob to its
ceiling before concluding it cannot help** — the sweep here cost two arms and
reversed the conclusion.

## Provenance

Pinned binaries: `roust 0.3.2 (7c8f6bb)` for the E31 sweep and the 2-hop
arms (isolated worktree, never rebuilt mid-run), `roust 0.3.2 (f1e8eff)` for
the import-edges arms (main checkout, so the worktree binary was left alone
while its arms were live). E29's >= 3-gold-file instance lists throughout, so
every arm is directly comparable to E29's and to each other. `--import-edges-v2`
re-keys the cache (`:ie2`) because the import graph is part of the cache
payload; without that a cache written flag-off would be served to a flag-on
run and the new edges would silently never appear.

One implementation defect found and fixed mid-round: the first cut resolved
Java/C imports with a full corpus scan per import statement, which was
O(imports x files) per file and made a Java slice effectively unrunnable
(3 records in 5 minutes). A basename index built once per corpus restored it
to ~45x that throughput.

---

# E33 — the maximum-generation ceiling

Everything the campaign has found that can add candidates, on at once:
cap 500, `--import-hops 2`, `--import-edges-v2`, and the pool eligibility
floor dropped 0.15 -> 0.02 via the new `--eligible-floor` (that cut runs
BEFORE any admission rule, so it bounds every cap and no admission lever can
reach past it). A **ceiling probe**, not a proposal.

| slice | n | shipped default | best staged config | **ceiling** |
|---|---|---|---|---|
| **Python Verified** | 22 | 63.64 | 86.36 | **100.00** |
| Rust | 105 | 27.62 | 33.33 | **33.33** (saturated) |
| C++ | 55 | 25.45 | 29.09 | **29.09** (saturated) |
| C | 46 | 4.35 | 21.74 | **28.26** |
| Java | 40 | 20.00 | 22.50 | **22.50** (saturated) |

Go and JS/TS could not be measured at this setting: on the two largest
corpora the probe's pool explosion made the arms effectively non-terminating
(Go stalled at 75/143, JS/TS at 62/207 after ~40 minutes) and they were
killed. Their best *staged* numbers stand as lower bounds on their ceilings:
Go >= 57.34 (cap 500 + 2hop), JS/TS >= 22.71 (cap 128 + 2hop).

## What this settles

**Python retrieves every gold file on every instance of its multi-gold
stratum.** Three of the five measured non-Python slices are *saturated*:
Java, C++ and Rust gain **exactly nothing** from maximum generation over
their best staged configuration. Their gold is not merely unadmitted and not
merely ungenerated — it is unreachable by every candidate-generation and
admission mechanism this engine has.

So the goal as literally posed — every language at Python's measurements — is
**not attainable by tuning this engine**, and this time that claim rests on a
measured ceiling with every knob at maximum rather than on an inference from
one negative arm. The residual gap is in the *lexical/BM25 substrate* that
produces `sources` and scores candidates in the first place, not in the graph
walked outward from it.

## Caveats that materially limit these numbers

* **Python Verified is n = 22.** A 100.00 on 22 instances is a small-sample
  result and should not be read as a general Python property.
* The ceiling costs 15k-26k tokens per bundle against a shipped ~8.5k, and
  the line fraction *collapses* (Python .0723 against its .2473 default).
  Breadth at this setting is bought with depth that E29 says only a much
  larger budget restores.
* Nothing here is adoptable as-is: the best configuration differs per
  language, and the ceiling config is far past any sensible operating point.

---

# E34 — the seed count, and a correction to E33

E33 called Java, C++ and Rust "saturated". **That was wrong in the same way
E30's conclusion was wrong**: it was a ceiling of the *graph-expansion*
machinery measured at a fixed number of BM25 seeds (`k_lex = 10`), not a
ceiling of the engine. Everything is expanded outward from those seeds, so
the seed count is a strictly upstream knob that E33 held constant.

Exposed as `--k-lex` (default 10 unchanged), at cap 128 + 2hop + ie2:

| slice | k10 (shipped) | k10 + generation | k30 | k50 |
|---|---|---|---|---|
| Rust | 27.62 | 33.33 | 37.14 | **38.10** |
| C++ | 25.45 | 29.09 | **32.73** | 32.73 |
| Java | 20.00 | 22.50 | 20.00 | 22.50 |

Two of the three "saturated" slices move past E33's ceiling. Returns
diminish by k=50 (Rust +0.96, C++ flat), so the seed dimension plateaus too.
Java is non-monotone across k (22.50 / 20.00 / 22.50) and is n=40 — that
column is noise, not signal.

## Four dimensions, each swept to a plateau

| dimension | knob | swept | outcome |
|---|---|---|---|
| admission | `--max-additions` | 16 -> 500 | plateaus (~57 on Go) |
| generation breadth | `--import-hops` | 1 -> 2 | +10.14 jsts, +5.71 rust, 0.00 without a graph |
| generation coverage | `--import-edges-v2` | off -> on | unfreezes Java/C/C++ |
| pool floor | `--eligible-floor` | 0.15 -> 0.02 | +6.52 C, else ~0 |
| seeds | `--k-lex` | 10 -> 50 | +4.77 rust, +3.64 cpp, plateaus |

**Best measured, per slice, anywhere in this space (>= 3 gold files):**

| slice | shipped | best measured |
|---|---|---|
| Python Verified | 63.64 | **100.00** |
| Go | 27.27 | **>= 57.34** |
| Rust | 27.62 | **38.10** |
| C++ | 25.45 | **32.73** |
| C | 4.35 | **28.26** |
| JS/TS | 10.14 | **>= 22.71** |
| Java | 20.00 | **22.50** |

## Conclusion, stated with the scope it has earned

Across every knob this campaign has exposed -- admission, generation breadth,
generation coverage, the pool floor, and the seed count -- each swept until
returns plateau, the non-Python slices plateau far below Python, and Python
itself rises to 100.00 under the same treatment. Per-language parity is not
reachable by configuring this engine.

That is a claim about **this five-dimensional configuration space**, swept.
It is not a proof that no retrieval design could close the gap.

## A process failure worth recording twice

I declared a terminal ceiling twice from a subset of knobs, and was wrong
both times: E30 ("admission cannot help" -- refuted by sweeping the cap) and
E33 ("Java/C++/Rust are saturated" -- refuted by raising the seed count). The
discipline that would have prevented both: **before calling anything a
ceiling, enumerate the knobs upstream of the one being swept, and either
sweep them or scope the claim to the ones held fixed.**

---

# E35 — the comparison itself was confounded

Before spending another arm, I checked whether the slices being compared are
comparable. They are not. The ">= 3 gold files" stratum has a very different
*difficulty* in each language, and the metric is all-or-nothing over EVERY
gold file:

| slice | n | mean gold files | median | instances with > 6 |
|---|---|---|---|---|
| **Python Verified** | 22 | **4.32** | 3.0 | 1 |
| Java | 40 | 4.88 | 3.0 | 6 |
| Go | 143 | 7.95 | 4.0 | 32 |
| Rust | 105 | 8.87 | 6.0 | 42 |
| C | 46 | 9.17 | 5.0 | 16 |
| C++ | 55 | 10.00 | 5.0 | 24 |
| **JS/TS** | 207 | **10.99** | 5.0 | 84 |

Python's stratum is the easiest in the set -- 13 of its 22 instances have
exactly three gold files and only one exceeds six -- while JS/TS averages
eleven files per instance. Requiring all of eleven files is enormously harder
than requiring all of three, so every cross-slice "3+ FILE" comparison in
this campaign, including the ones framing the goal, compared unlike things.

## Like-for-like: exactly 3 gold files

Shipped defaults:

| slice | ver | rust | cpp | go | java | jsts | c |
|---|---|---|---|---|---|---|---|
| FILE % | 69.23 | 54.55 | 50.00 | 42.62 | 33.33 | 16.33 | 0.00 |
| n | 13 | 22 | 16 | 61 | 21 | 49 | 7 |

At a common improved config (cap 128):

| slice | ver | go | rust | cpp | java | jsts | c |
|---|---|---|---|---|---|---|---|
| FILE % | 92.31 | 62.30 | 54.55 | 50.00 | 33.33 | 24.49 | 14.29 |

**Roughly half the apparent language gap was the confound.** At shipped
defaults the Python-to-Rust gap is 14.7pp, not the 36.0pp that the raw
stratum comparison (63.64 vs 27.62) reported. Python still leads at matched
difficulty and matched config, so the gap is real -- it is just about half
the size the goal was framed around.

## The bar rests on 13 instances

Python Verified contributes **13 instances** at exactly three gold files and
22 in the whole 3+ stratum. Every "Python level" number in this campaign --
63.64, 86.36, 100.00 -- is computed on that sample. A 100.00 is 22 of 22; a
92.31 is 12 of 13. These are not a defensible basis for a cross-language
parity target, and no amount of engine work changes that.

## Recommendation

Retire "all languages to Python-level measurements" as posed. It compares
strata of unequal difficulty against a 13-22 instance reference. The
defensible successor questions:

1. **Matched-difficulty parity**: at exactly k gold files, how far behind
   Python is each language? (Answer today: ~15pp for Rust at k=3, default.)
2. **The adoptable subset**: `--import-edges-v2` closes a real
   language-agnostic hole (Java/C/C++ had NO import graph); C goes 4.35 ->
   28.26 on the 3+ stratum, 0.00 -> 28.57 at exactly 3. That deserves a
   dual-gate round at a sane operating point on its own merits.

## E35b — direct standardization: the goal, measured like-for-like

Standardizing every slice to Python Verified's gold-count mix (the weights
are 3:0.591, 4:0.273, 5:0.045, 6+:0.091), so each language is scored as if
its instances had Python's difficulty:

**Shipped defaults**

| slice | crude | standardized |
|---|---|---|
| Python Verified | 63.64 | 63.64 |
| Rust | 27.62 | **46.45** |
| C++ | 25.45 | **45.00** |
| Go | 27.27 | **35.52** |
| Java | 20.00 | 21.00 |
| JS/TS | 10.14 | 16.88 |
| C | 4.35 | 3.64 |

**Best configuration per slice**

| slice | crude | standardized |
|---|---|---|
| Python Verified | 86.36 | 86.36 |
| **Go** | 57.34 | **64.21** |
| Rust | 38.10 | **57.61** |
| C++ | 32.73 | **53.65** |
| JS/TS | 22.71 | 35.53 |
| Java | 22.50 | 24.03 |
| C | 21.74 | 20.31 |

**Go at its best configuration reaches 64.21 standardized, above the 63.64
Python-Verified baseline the goal was originally framed on.** Rust (57.61)
and C++ (53.65) come close. That result was invisible while the difficulty
confound sat in the comparison: crude Go is 57.34 against a Python that has
itself moved to 86.36.

### What this does and does not establish

It does **not** establish parity. Against Python measured *at the same
config*, every language is still behind (86.36 vs Go's 64.21), and Java, C
and JS/TS remain far behind on any reading.

It does establish that a substantial part of the headline gap was an artifact
of comparing strata of unequal difficulty, and that on a like-for-like
measurement one language now clears the original bar.

### Load-bearing caveats

* The standardization weights come from **22 Python instances**, and two of
  the four weight cells are n=1 and n=2 (Python scores 0% in both at default,
  50% in the 6+ cell at best config). Those cells are noise; the weights
  carry that noise into every standardized figure.
* "Best configuration" differs per slice and costs 9-15k tokens against the
  shipped ~8.5k, with line fraction well below default. These are not
  operating points, and not comparable to the published 8192 scoreboard.
* FUNCTION and LINE were never re-scored across E31-E35. Everything here is
  the FILE column.
