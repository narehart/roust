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
