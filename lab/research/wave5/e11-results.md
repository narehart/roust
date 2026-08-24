# E11 — query-type routing (BLIZZARD/BRTracer/Chaparro/Kim&Lee) — Lite-300 gate

*Campaign #4, wave 5. Branch `e11-routing`, engine commit `2a81d78`. Spec:
`wave5/file-ranking-and-routing.md` section (b) (transplant #1); motivation:
E17's measured class gap (code-block-bearing queries 30.9% gold-line capture
vs 56.3% for tracebacks — repro-snippet tokens hijack bag-of-words ranking
toward test/example-shaped code). Query-side only, per the E18/E19
packer-economy lesson: `pack_regions` is untouched.*

## Mechanism (flag-gated `--route`, defaults byte-identical)

1. **Classifier** — deterministic line-based regex partition of the issue
   text into {traceback, code-fence, prose} channels. Traceback blocks are
   claimed first (precedence per block type: a trace inside a fence is
   trace); fences = markdown ```/~~~ blocks + doctest/REPL (`>>>`) lines +
   indented (4-space/tab) code runs whose first line matches a code-starter
   pattern. Query class = {prose, trace, fence, trace+fence}.
2. **Traceback treatment** (best class, pushed further — BRTracer): frames
   (`File "X", line N, in f`) mined for function names + module basenames
   (resolved frames only) + exception name + error message; the raw block is
   dropped as bulk query text. Frame paths resolved to repo files by
   trailing-component match (>= 2 components); resolved files get a
   rank-decayed additive FILE boost on the NORMALIZED lexical score — 1/rank
   for the top-10 frames (rank 1 = raise site, Python frame order reversed),
   0.1 deeper, 0.1 spillover to files the frame files' own text imports
   (existing `file_import_targets`, directed). A frame file with zero
   lexical overlap is INSERTED into the candidate pool (E-class rescue).
3. **Code-fence treatment** (the failing class — Chaparro/BLIZZARD PE
   mine-then-discard): identifiers in code positions (def/class/import
   names, call targets, attribute accesses, assignment LHS, keyword-
   filtered) kept as query terms; fence bulk (comments, strings, output,
   prose-in-code) discarded.
4. **Conditional test-path downweight** (Kim & Lee): file score multiplied
   by `--route-test-penalty` (default 0.85) for `TESTLIKE_RE`-shaped paths
   ONLY when fence-mined terms are a strict majority of the deduped query
   term list (`fence_dominant`); never fires on prose/trace-dominated
   queries; directly trace-boosted files are exempt.

Prose-only queries return EXACTLY `query_terms(question)` — the routed path
is a no-op for them (verified: output md5-identical with/without `--route`
on prose smoke instances).

Determinism: boost insertion is canonical (frame-rank order, then sorted
spillover set), one addition per file (no float-summation order ambiguity),
`total_cmp` sorts throughout. Proofs: 60/60 Rust tests (7 new: partition,
extraction, mining, REPL, boost rescue + spillover, penalty scoping, frame
resolution); defaults byte-identical to the main-built binary (0e017c1) on
12/12 sampled Lite instances (md5 over regions+bundle, two-run cross-process
determinism folded in).

## Smoke (10 hand-picked instances, all classes)

- Frame resolution is precise: `django-12113` resolves 11 frames raise-site
  first (`django/db/backends/sqlite3/base.py` = the "database is locked"
  raise site at rank 1); `django-11583` -> `django/utils/autoreload.py`.
- `fence_dominant` fires where designed (`matplotlib-22711`: 65 fence terms
  vs 43+1 prose/trace) and nowhere else in the smoke set.
- Prose instances byte-identical under `--route` (`django-10914`).
- Known limitation (documented, accepted): IPython-format tracebacks
  (`AssertionError   Traceback (most recent call last)` header,
  `<ipython-input-...>` frames, no `File "..."` lines — e.g.
  `matplotlib-23299`) are NOT claimed by the CPython trace regexes; when
  inside a fence they fall through to fence treatment (mine-then-discard),
  which is the correct fallback.

## Gate protocol

Three arms on Lite-300 (`parity/region_eval2.py`, private repos copy per
issue #41, engine `2a81d78` clean, budget 8192): baseline (defaults) /
route(penalty 0.85) / route(penalty 0.7). Scored with
`lab/agentless_metric_v4.py`; paired deltas vs baseline via
`lab/stats/paired_tests.py` (paired bootstrap n_boot=10000 + McNemar exact).
Baseline must reproduce FUNCTION 53.33 / LINE 42.67 / fraction .51683 /
FILE 277/300 exactly. FILE is NOT an invariant tripwire for this experiment
— the trace boost and test penalty are file-level by design; FILE is a
primary metric and every FILE flip is itemized (instance, direction, active
component). Class-conditional deltas reported per query class (BLIZZARD
worsened 25% of queries; an aggregate win hiding a class regression is not
adoptable).

## Results (Lite-300, all arms 300/300 ok, engine `2a81d78` clean)

| arm | FILE | FUNCTION | LINE (all-or-nothing) | mean fraction |
|---|---|---|---|---|
| baseline (defaults) | **277/300 (92.33)** | **53.33** | **42.67** | **.51683** |
| route (penalty 0.85) | 280/300 (93.33) | 53.00 | 44.33 | .53016 |
| route (penalty 0.7) | 280/300 (93.33) | 53.00 | 44.33 | .53016 |

Baseline reproduces the adopted-engine reference EXACTLY (FUNCTION 53.33 /
LINE 42.67 / fraction .516831 / FILE 277/300) — no contamination. One
route085 record (`sympy-17022`) hit the 180s harness timeout on the original
pass; a same-config re-run completed in 6.6s with output byte-identical to
route070's record for the same instance (penalty provably inert there:
`fence_dominant=false`), so the timeout was environmental (machine load) and
the record was patched from the re-run; route070/baseline had 0 errors
unpatched.

**The penalty sweep is INERT: route(0.85) and route(0.7) are byte-identical
on all 300 instances** (md5 over regions, zero differing records). 19/300
queries are fence-dominant, so the multiplier WAS applied to their
test-shaped candidates' scores at both settings — but not one packed output
changed, and none of the 19 has a single TESTLIKE-path file in its packed
regions in ANY arm (baseline included). The E17 diagnosis ("repro tokens
drag ranking toward test/example-shaped code") does not manifest as
test-files-in-output at the FILE level on Lite — the hijack cost shows up
as wrong *production* files/regions instead. The three arms therefore
collapse to two: baseline vs routing; the test-penalty component is dead
weight at any strength.

Paired deltas vs baseline (`lab/stats/paired_tests.py`, n_boot=10000,
McNemar exact; identical for both route arms):

| metric | Δ [CI95] | McNemar p | discordant |
|---|---|---|---|
| FILE | **+1.00 [−0.33, +2.67]** | 0.375 | n01=4, n10=1 |
| FUNCTION | −0.33 [−3.33, +2.67] | 1.0 | n01=9, n10=10 |
| LINE | +1.67 [−1.00, +4.33] | 0.332 | n01=11, n10=6 |
| fraction | +.0133 [−.0125, +.0396] | — | — |

FILE moves for the first time in the campaign (+3 net, 277→280) — by
design, not contamination: the trace boost and the fence query-term change
are file-level mechanisms and every flip is itemized below.

## Class-conditional results (route vs baseline; BLIZZARD check)

| class | n | FILE Δ | FUNCTION Δ | LINE Δ | fraction Δ [CI95] |
|---|---|---|---|---|---|
| prose | 79 | **0.00** | **0.00** | **0.00** | **.0000 [0, 0]** |
| trace | 7 | +14.29 (1G/0L) | 0.00 (1G/1L) | 0.00 (1G/1L) | .0000 [−.429, +.429] |
| fence | 166 | +0.60 (2G/1L) | **−2.41** (4G/8L, p=.39) | −1.20 (3G/5L) | −.0121 [−.047, +.022] |
| trace+fence | 48 | +2.08 (1G/0L) | +6.25 (4G/1L, p=.375) | **+14.58 (7G/0L, p=.016)** | **+.1253 [+.047, +.219]** |

- **Prose is untouched — exactly 0.00 on every metric, zero discordant
  pairs across 79 instances.** The no-op guarantee held at scale.
- **The trace-bearing classes are the win**: trace+fence LINE +14.58pp with
  SEVEN gains and ZERO losses (the only McNemar-significant cell, p=.016)
  and a fraction CI excluding zero (+.125 [+.047, +.219]). Pooling
  trace-involved instances (n=55): FUNCTION 5G/2L, LINE 8G/1L.
- **The fence-only class — E11's motivating target — got WORSE**: FUNCTION
  4G/8L (−2.41pp), LINE 3G/5L, fraction −.012. Not CI-significant, but the
  sign is consistent across all three region metrics: mine-then-discard
  threw away prose-in-fence signal the bag-of-words ranking was actually
  using (comments, error-message strings, printed output inside the snippet)
  and the mined identifiers did not compensate. BLIZZARD's own asymmetry
  reproduced faithfully — its PE class was also its smallest gain — but
  here it lands slightly negative under an engine that already stems/splits
  identifiers corpus-wide.

## FILE + FUNCTION flip itemization (by component)

FILE flips (route vs baseline): 4 gained / 1 lost.

| instance | dir | class | component |
|---|---|---|---|
| django-12113 | GAIN | trace | trace boost (11 frame files; raise-site `sqlite3/base.py` pulled the whole backend family in) |
| astropy-14182 | GAIN | trace+fence | trace boost (5 frame files: `io/ascii` chain incl. gold `rst.py`) |
| sympy-13915 | GAIN | fence | fence term change (no trace files; mined identifiers re-ranked `sympy/core` files in) |
| pylint-7080 | GAIN | fence | fence term change |
| pytest-9359 | LOSS | fence | fence term change (discarded fence bulk had carried the gold file's ranking terms) |

Test-penalty-attributed flips: **zero** (component inert, see above).
FUNCTION discordants split the same way: every trace-attributed flip is
2 gains for 1 loss or better; the fence-attributed flips run 4G/8L.

## Verdict (Lite): dual-gate CONTINUE for the trace mechanism; fence
mechanism negative on its target class; penalty dead

Aggregate is net positive (FILE +1.0, LINE +1.67, fraction +.013, FUNCTION
−0.33, none individually significant at n=300) and the gains are entirely
attributable to the traceback treatment; per protocol the arms went to
Verified (below). But per the adoption rule stated up front — an aggregate
win hiding a class regression is not adoptable — `--route` AS A PACKAGE is
not adopt-recommendable from Lite evidence: its fence component is
sign-negative on the exact class it was built to fix, and its penalty
component provably does nothing. The adoptable candidate that Verified
should confirm or kill is the trace treatment (classifier + frame
extraction + FILE boost + spillover), which on Lite is 8G/1L on LINE across
its 55 trace-bearing instances and never fires on anything else.

## Verified-407 (dual gate)

TBD — arms running (`e11_verified_{baseline,route085,route070}.jsonl`);
reference baseline FUNCTION 47.0 / LINE 35.4.

### Artifacts

- Predictions: `lab/results_regions/e11_{baseline,route085,route070}.jsonl`,
  `lab/results_regions/e11_verified_{baseline,route085,route070}.jsonl`
- Scores: `lab/results_regions/agentless_metric_e11_{baseline,route085,route070}.json`
- Paired stats: `lab/stats/e11_{route085,route070}_vs_baseline.json`
- Class-conditional + flip itemization: `lab/results_regions/e11_class_conditional.json`
- Byte-identity proof: 12/12 sampled instances vs main-built 0e017c1 binary
  (scratchpad `byte_identity_check_e11.py`; not committed)
- Private repos copy used throughout (issue #41); `lab/swebench_repos`
  untouched by the eval loop (scorer reads are `git show` object-DB only)
