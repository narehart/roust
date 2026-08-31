# E39 — the gap was never mostly retrieval: it is which files count as answers

## The diagnostic that should have come first

Instead of turning another knob, classify the misses. For each slice, what
fraction of gold files is in an extension the corpus **never indexes** -- i.e.
unretrievable at any rank, under any configuration? Because FILE is
all-or-nothing, a single such file fails the whole instance.

Hard ceiling per slice (harness gold definition: file exists at base commit,
>= 1 hunk with old-side lines):

| slice | ceiling as shipped | ceiling if non-source gold excluded | non-source share of gold |
|---|---|---|---|
| **Java** | **57.03%** | 96.88% | **25.3%** |
| JS/TS | 76.68% | 98.27% | **28.7%** |
| C++ | 70.54% | 90.70% | 23.3% |
| Rust | 72.38% | 94.56% | 18.5% |
| C | 77.17% | 87.40% | 4.2% |
| Go | 92.29% | 98.83% | 4.7% |
| **Python Verified** | **99.75%** | 100.00% | **0.2%** |

**Java's ceiling (57.03%) is BELOW the 63.64 bar.** Every configuration in
E30-E38 was chasing a target above Java's maximum attainable score, and its
52.34 was already 92% of what was reachable. C++ at 68.99 sits 1.6 points
under its own ceiling. This is why those two looked immovable: they were.

And the asymmetry that explains the whole campaign: **Python's gold is 0.2%
non-source; Java's is 25.3% and JS/TS's 28.7%.** SWE-bench Verified was
hand-curated to pure source changes. Multi-SWE-bench was not -- its gold
patches include changelogs, release notes, docs and lockfiles. Java's single
largest unindexed gold group is `release-notes/VERSION-2.x` (36 files) and
`release-notes/CREDITS-2.x` (6) in the Jackson repos: files that are "correct
answers" only because the fixing PR also wrote a release note.

## Two classes, deliberately measured apart

`--build-files` (build.gradle, Cargo.toml, CMakeLists.txt, package.json ...)
is **genuinely useful** -- real changes edit them. `--changelog-files`
(CHANGELOG, release-notes/, VERSION-*, CREDITS-*) is a **benchmark
artifact**: no user wants CREDITS-2.x back from a bug query.

| slice | sg + cap32 | + build files | + changelogs |
|---|---|---|---|
| Java | 51.56 | 51.56 (**+0.00**) | **75.00** (+23.44) |
| Rust | 65.27 | 65.27 (**+0.00**) | **69.87** (+4.60) |
| C++ | 68.99 | -- | 69.77 (+0.78) |
| Go | 70.79 | -- | 70.56 (-0.23) |
| JS/TS | 52.07 | -- | **50.00 (-2.07)** |

**The useful class contributes exactly zero. Every point comes from the
artifact class.** Java's 23-point jump is entirely the ability to return
release notes. Go is flat (4.7% non-source gold) and JS/TS gets *worse*: its
non-source gold is dispersed component docs and fixtures (top-6 basenames
cover only 14%), so the rule adds corpus without capturing the gold.

## Standing against a full-slice bar of 63.64

| slice | best | config | honest note |
|---|---|---|---|
| Java | **75.00** | sg+cap32+changelogs | +23.44 is ALL artifact |
| Go | **70.79** | sg + cap32 | genuine |
| Rust | **69.87** | sg+cap32+changelogs | +4.60 artifact |
| C++ | **69.77** | sg+cap32+changelogs | +0.78 artifact |
| C | **67.19** | maxed + budget 16384 | genuine, 2x tokens |
| JS/TS | 52.07 | sg + cap32 | does not clear |

Five of six clear -- but three of those five only by indexing changelogs.

## Recommendation

Do **not** adopt `--changelog-files`. It buys benchmark score and no user
value, and adopting it would make the scoreboard actively misleading. Adopt
nothing here yet; `--build-files` is defensible on principle but measured
+0.00, so it needs a reason other than score.

The real conclusion is about measurement, not the engine: **a large part of
the cross-language gap this campaign has chased is that Multi-SWE-bench and
SWE-bench Verified disagree about what a correct answer is.** Any future
cross-language claim should either exclude non-source gold or state that it
does not.
