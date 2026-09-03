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

## E40 — the JS/TS holdout, genuine mechanisms only

JS/TS is the one slice whose gap is entirely genuine: changelog indexing made
it *worse* (-2.07), because its non-source gold is dispersed component docs
and fixtures rather than a handful of changelogs. So this arm used only the
symbol graph and second-hop generation.

| config | n | FILE | line fraction | tokens |
|---|---|---|---|---|
| shipped | 580 | 46.38 | .2616 | 8.5k |
| symbol-graph + cap 32 | 580 | 52.07 | .2276 | 8.8k |
| + 2 hops | 580 | 54.48 | .2271 | 8.8k |
| + cap 64, budget 16384 | 580 | **59.31** | **.3108** | 17.2k |

**+12.75 over shipped with line depth ABOVE shipped** (.3130 vs .2616) -- the
E29 pattern once more: the breadth was never paid for out of depth, only out
of a fixed budget. 4.33 short of 63.64, against a 76.68 ceiling.

A seed-count arm (k_lex 30 on top of the above) was also launched and
**abandoned**: k_lex multiplies the seeds and each seed drives a 2-hop walk,
so the pool explodes on this slice -- it advanced 2 records in 37 minutes.
That is the third ceiling probe on the two largest corpora to die the same
way, and it bounds what this harness can measure, not what the engine can do.

A further arm at cap 128 / budget 24576 was launched and **abandoned**: it
advanced ~5 records per several minutes on the 580-instance slice (the same
pool-explosion behaviour that killed the E33 and E38 ceiling probes) and would
have taken hours without being able to change the conclusion. Not reported.

## Final standing against a full-slice bar of 63.64

| slice | best GENUINE | clears? | with changelog artifact |
|---|---|---|---|
| Go | **70.79** | yes | 70.56 |
| C++ | **68.99** | yes | 69.77 |
| C | **67.19** | yes (2x tokens) | -- |
| Rust | **65.27** | yes | 69.87 |
| JS/TS | 59.31 | no (-4.33) | 50.00 (worse) |
| Java | 51.56 | **impossible** (ceiling 57.03) | 75.00 |

Four of six clear on genuine retrieval improvements. **Java cannot clear
honestly at all** -- its ceiling with current indexing is below the bar --
and the only route over it is indexing release notes, which is why
`--changelog-files` exists, stays default-off, and is recommended against.
