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
