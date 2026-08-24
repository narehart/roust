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

## Verified-407 (dual gate; all arms 407/407 ok)

| arm | FILE | FUNCTION | LINE | mean fraction |
|---|---|---|---|---|
| baseline (defaults) | 375/407 (92.14) | 47.17 | 35.38 | .47522 |
| route (0.85 = 0.7) | 376/407 (92.38) | 44.96 | 34.89 | .46644 |

Baseline reproduces the committed Verified reference
(`agentless_metric_verified_new.json`) to within one instance: LINE exact
(35.38 = 35.38), FUNCTION 192 vs 191 correct (47.17 vs 47.04), FILE 375 vs
374 (92.14 vs 91.89), fraction .47522 vs .47413 — a one-instance drift
consistent with clone-state differences vs the older artifact's run, and
immaterial to the gate: all paired deltas below are computed against THIS
round's own baseline, same harness, same session, same clones. Both route
arms again **byte-identical on all 407** — the
penalty component is inert on both datasets (0 differing outputs across all
707 routed runs). Aggregate paired deltas: FILE +0.25 (3G/2L), FUNCTION
**−2.21 [−3.93, −0.74]** (4G/13L, McNemar p=.049), LINE −0.49 (4G/6L),
fraction −.0088.

Engine provenance note: the Verified baseline arm started under binary
`2a81d78` and finished under `4c27958` (rebuilt mid-run after the Lite
artifact commit moved HEAD; `roust-rs/` diff between the two commits is
EMPTY, so the binaries are logic-identical — only the embedded sha
differs). Route arms ran wholly under `4c27958`.

### Verified class-conditional (route vs baseline)

| class | n | FILE Δ | FUNCTION Δ | LINE Δ | fraction Δ [CI95] |
|---|---|---|---|---|---|
| prose | 122 | **0.00** | **0.00** | **0.00** | **.0000 [0, 0]** (zero discordants) |
| trace | 4 | 0.00 | −25.0 (0G/1L) | −25.0 (0G/1L) | −.250 [−.75, 0] |
| fence | 244 | −0.41 (1G/2L) | −1.64 (4G/8L) | 0.00 (4G/4L) | −.0039 [−.027, +.019] |
| trace+fence | 37 | **+5.41 (2G/0L)** | **−10.81 (0G/4L) [−21.6, −2.7]** | −2.70 (0G/1L) | −.0441 [−.121, +.017] |

**Lite's region-level trace win did NOT replicate.** Lite trace-bearing
pooled: FUNCTION 5G/2L, LINE 8G/1L. Verified trace-bearing pooled: FUNCTION
0G/5L, LINE 0G/2L — a clean sign flip on held-out data, with the
trace+fence FUNCTION delta's CI excluding zero on the wrong side. The fence
class is mildly negative on BOTH datasets (FUNCTION 4G/8L on each —
identical discordant counts, a faithful out-of-sample replication of the
fence-treatment cost). Prose: zero discordant pairs out of 201 prose
instances across both datasets — the routing scope guarantee held
everywhere.

**What DID replicate: the FILE-level trace boost.** Trace-attributed FILE
flips are 2 gained / 0 lost on Lite (django-12113, astropy-14182) and 2
gained / 0 lost on Verified (pylint-8898, sympy-20438) — four FILE rescues,
zero FILE losses, on frame-resolved instances across both datasets.
trace+fence FILE +5.41 is the one positive Verified class cell.

**Loss anatomy (all 5 Verified trace-bearing FUNCTION losses):** in every
case the gold file is STILL retrieved (FILE unchanged, 1→1) but the
fraction collapses (1.00→0.00 django-12663, 1.00→0.00 sympy-19954,
0.39→0.00 matplotlib-20859, 0.46→0.00 requests-1724) — the regions moved
off the gold lines *within* a still-selected file. Two confounded
sub-mechanisms both act here: (i) mine-then-discard REPLACED the trace
block's raw text (frame context lines contain the gold function's own body
identifiers, which were feeding within-file region gain), and (ii)
boost-inserted frame files consumed bundle budget, shrinking the gold
file's span allocation (files_same=False in every loss). sympy-23824
(tf=0, no boost possible) shows mechanism (i) acting alone.

## Final verdict: package REJECT; E11b trace-only promotion WITHHELD (mixed
evidence, verdict "c")

- **The `--route` package fails the dual gate**: Lite mildly positive
  (FILE +1.0, LINE +1.67, fraction +.013), Verified negative (FUNCTION
  −2.21, p=.049; trace+fence FUNCTION −10.81 with CI excluding zero). Not
  adoptable.
- **A trace-only E11b "just drop the fence treatment" is NOT supported
  either**: the trace treatment itself is what regressed Verified's
  trace-bearing regions (0G/5L FUNCTION) — the Lite 8G/1L LINE win was
  Lite-local. Under case-mining discipline the promote recommendation is
  withheld.
- **The surviving signal for a future E11b** is narrow and specific: the
  rank-decayed FILE boost from resolved traceback frames (+4 FILE rescues,
  0 FILE losses, both datasets — never once lost a file). The clean
  follow-up is **boost-only routing**: keep the query text BYTE-UNTOUCHED
  (no mine-then-discard anywhere, no term replacement) and add ONLY the
  additive frame-file boost + import spillover to file scoring. That
  isolates the one sub-mechanism with consistent cross-dataset evidence
  from the two that hurt (term replacement; budget displacement is then the
  remaining risk to watch at region level). Needs its own full dual gate;
  expected effect is FILE-level only and small (2/300-scale), so it should
  ride along with a stronger FILE-thread experiment (wave5 #2 LexBoost)
  rather than run alone.
- **Deterministic findings worth keeping regardless**: (i) the test-path
  penalty NEVER fires effectively — fence-dominant queries do not put
  test-shaped files anywhere near the packed set in this engine (impl-prior
  and ranking already handle them); Kim & Lee's prior is already priced in.
  (ii) The classifier + per-record `route` stats are cheap, correct
  telemetry (201/201 prose no-ops) and E11b can reuse them unchanged.
  (iii) BLIZZARD's class asymmetry replicated in *shape* (ST-treatment
  strongest, PE weakest) but not in sign at region granularity — evidence
  that its Java-era gains do not transplant to an engine that already does
  corpus-wide identifier splitting + within-file region packing.

### Artifacts

- Predictions: `lab/results_regions/e11_{baseline,route085,route070}.jsonl`,
  `lab/results_regions/e11_verified_{baseline,route085,route070}.jsonl`
- Scores: `lab/results_regions/agentless_metric_e11_{baseline,route085,route070}.json`,
  `lab/results_regions/agentless_metric_e11_verified_{baseline,route085,route070}.json`
- Paired stats: `lab/stats/e11_{route085,route070}_vs_baseline.json`,
  `lab/stats/e11_verified_{route085,route070}_vs_baseline.json`
- Class-conditional + flip itemization:
  `lab/results_regions/e11_class_conditional.json`,
  `lab/results_regions/e11_verified_class_conditional.json`
  (generator: `lab/stats/class_conditional_e11.py`)
- Byte-identity proof: 12/12 sampled instances vs main-built 0e017c1 binary
  (scratchpad `byte_identity_check_e11.py`; not committed)
- Private repos copy used throughout (issue #41); `lab/swebench_repos`
  untouched by the eval loop (scorer reads are `git show` object-DB only)
