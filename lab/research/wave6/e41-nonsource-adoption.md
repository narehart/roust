# E41 — user-directed: index the non-source gold classes

The user reviewed the recommendation against indexing benchmark-artifact
files and directed "do it". Implemented and measured in full.

## What was added

* `--build-files` -- build.gradle, Cargo.toml, CMakeLists.txt, package.json,
  pom.xml, go.mod, Makefile. Genuinely useful; measured **+0.00** everywhere.
* `--changelog-files` -- CHANGELOG, release-notes/, VERSION-*, CREDITS-*.
* `--docs-data-files` -- the broad class: .md .rst .txt .adoc .asciidoc
  .json .yml .yaml .toml. Added because JS/TS's non-source gold is dispersed
  (top-6 basenames cover only 14%) and the narrow changelog rule cannot reach
  it. Raises the jsts *ceiling* from 76.68% to 97.58%.

All three re-key the cache (`:bf`, `:cl`, `:dd`) because they change corpus
membership. All three default OFF.

## Result: five of six clear, JS/TS collapses

| slice | best | config | vs 63.64 |
|---|---|---|---|
| Java | **72.66** | sg + cap32 + changelog + docs-data | **CLEARS** |
| Go | **70.79** | sg + cap32 (genuine) | **CLEARS** |
| Rust | **69.87** | sg + cap32 + changelog | **CLEARS** |
| C++ | **69.77** | sg + cap32 + changelog | **CLEARS** |
| C | **64.84** | sg + edges + 2hop + cap64 + b16384 + nonsource | **CLEARS** |
| **JS/TS** | 59.31 | sg + 2hop + cap64 + b16384 (**genuine**) | **-4.33** |

C is worth noting: it clears at 64.84 with line fraction **.2615, ABOVE its
shipped .2251** -- breadth and depth both improved, at 2x tokens.

## JS/TS: the indexing route makes it worse, not better

| jsts config | FILE |
|---|---|
| genuine (sg + 2hop + cap64 + b16384) | **59.31** |
| + changelog files | 50.00 |
| + broad docs/data class | **37.87** |

A 21-point collapse. Raising the *ceiling* from 76.68% to 97.58% does not
help when reaching it means flooding the corpus: every `package.json` and
every doc page enters the index, and the dilution overwhelms the ranking.
JS/TS's dispersed gold cannot be captured without dragging in thousands of
irrelevant files. **This is the one slice where the artifact route is not
merely distasteful but actively counterproductive.**

## Status

Five of six clear 63.64; JS/TS cannot by any measured route, and its best
result remains the fully genuine one. The flags stay default-off pending a
Python dual gate, which has not been run for `--docs-data-files` and must be
before any default moves: it is by far the most dilutive rule in the engine.

---

# E42 — JS/TS clears, genuinely

I said JS/TS "cannot" reach the bar. That was wrong, and the error was mine
rather than the engine's: I read **compute failures as capability limits**.

The cap-128 arm I abandoned as "non-terminating" was slow only because I had
paired it with budget 24576. E29 proved the returned FILE SET is
**budget-invariant** (618/618 instances byte-identical from 8192 to 24576),
so budget cannot change the FILE score at all -- that arm was paying a 3x
packing cost for a number the budget could not move. Re-run at the shipped
budget it completes in minutes. The same mistake had killed the k_lex arm.

## The admission curve, measured cheaply

| cap | 32 | 64 | 128 | 256 |
|---|---|---|---|---|
| FILE | 54.48 | 59.31 | 62.07 | trending down |

Admission plateaus at ~62, leaving 1.57 to the bar. The seed count -- which
gave rust +3.81 and cpp +3.64 and had never been runnable here -- closes it:

| cap 128 + | k_lex 10 | k_lex 20 | k_lex 30 |
|---|---|---|---|
| FILE | 62.07 | **64.14** | **65.69** |

**No changelog indexing, no non-source files. Purely the symbol graph, the
second hop, admission and seeds.**

## Final standing, all six slices vs 63.64

| slice | n | FILE | line frac | tokens | kind | config |
|---|---|---|---|---|---|---|
| Go | 428 | **70.79** | .3740 | 8.6k | genuine | sg + cap32 |
| Java | 128 | **72.66** | .4116 | 9.0k | **artifact** | sg+cap32+changelog+docs |
| C++ | 129 | **68.99** | .2900 | 8.6k | genuine | sg + cap32 |
| C | 128 | **67.19** | .2075 | 17.7k | genuine | sg+edges+2hop+cap128+k30+b16384 |
| JS/TS | 580 | **65.69** | .1359 | 13.7k | genuine | sg+2hop+cap128+k30 |
| Rust | 239 | **65.27** | .2103 | 8.6k | genuine | sg + cap32 |

**All six clear. Five of the six do so on genuine retrieval improvements**
with no benchmark-artifact indexing; only Java requires it, because its
ceiling without it (57.03%) is below the bar.

## Costs that must travel with these numbers

* Three slices run at 1.5-2x the shipped token budget (C 17.7k, JS/TS 13.7k,
  Java 9.0k against a shipped ~8.5k).
* Line depth is **down** on the wide configs -- JS/TS .1359 against a shipped
  .2616, C .2075 against .2251. These configs find more files and say less
  about each; E29 says the depth is budget-recoverable, at further token cost.
* No Python dual gate has been run for `--docs-data-files`, and Java's
  configuration depends on it. Nothing should be defaulted on before that.
* `--build-files`, the one non-source class with genuine user value, measured
  **+0.00** everywhere.
