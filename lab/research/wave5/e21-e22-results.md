# E21 (chunk-max FILE scoring) + E22 (static test-bridge channel) — Lite gate

*Campaign #4, wave 5. Branch `e21-chunkmax`, engine commit `d1279e8` (off main
`3f0c77b`, post-v12-rebaseline). Specs: `wave5/file-ranking-and-routing.md` a4
(BRTracer ICSME 2014 segmentation + cAST arXiv:2506.15655) and
`wave5/fresh-sota-scan.md` (IssueExec arXiv:2607.17286, static test-bridge).
Motivating context from `wave5/e20-e11b-results.md`: gold files are
disproportionately graph-central, so any hub-style *exclusion* heuristic is
known-harmful — chunk-max was attractive precisely because it defends against
accumulation WITHOUT an exclusion list. PRIMARY metric: FILE (hub-attractor
demotion / E-class rescue); FUNCTION/LINE/fraction are guardrails.*

**Verdict up front: all four arms REJECT at the Lite gate; no arm advanced to
Verified.** Flag-gated only — defaults remain byte-identical to v12; do not
merge as adoption.

## Mechanisms (both flag-gated, defaults byte-identical)

- **E21 `--file-score <accum|chunk-max|chunk-top2>`** (default `accum` =
  pre-E21 code path): the CONTENT channel of the fused BM25F file score is
  scored per packer chunk (`python_blocks` for .py — the packer's own nested
  spans; `window_blocks` over `hit_lines` radius 30 otherwise, with a
  whole-file coverage guard when the stemmed term is substring-invisible)
  and aggregated per file by MAX chunk score (or mean of top-2). Each chunk
  is scored with the same Okapi formula and corpus statistics (idf from
  file-level df, length norm against corpus `avg_len`), so chunk scores are
  mutually comparable across files. Path bonus, comment channel, and
  impl_prior are byte-identical to accum. The whole fused map is swapped —
  lex_picks, the `scores` budget map, and the legacy testbridge promotions
  all coherently consume the chunk aggregate.
- **E22 `--test-bridge <w>`** (default 0 = off): static approximation of
  IssueExec's issue→tests→code pathway. Top-3 positive-scoring test-like
  files by their own pristine fused score → directed `file_import_targets`
  filtered to production files → call-expression evidence
  (`\b([A-Za-z_]\w*)\s*\(` identifiers defined per `def_index`). Strength
  `sum_t (s_t/s_top)·(1+min(call_hits,3))`, capped at the TOP 5 bridged
  files per query (the ledger's flooding lesson), added PRE-normalization as
  `w·top_score·(raw/raw_max)` — a bridged file absent from the lexical pool
  is INSERTED (E-class rescue path). Weights swept {0.1, 0.3}.

Proofs before arms: 9 new Rust tests (chunk math vs hand formula to 1e-12,
per-line-tokenize == file tf invariant, non-py fallback == accum equality,
hub-demotion mechanism end-to-end on a toy corpus, top2 semantics, bridge
path + zero-direct-score insertion, flooding cap, determinism of both
channels, defaults-off identity), full suite green (61 lib + integration).
Defaults byte-identity 14/14 instances (one per repo ×12 + django-12113 +
astropy-14182) vs the main-built `3f0c77b` binary — md5 over
files+regions+bundle, two runs per config, plus explicit `--file-score
accum`: all five hashes identical per instance. Private clone copies
(`swebench_repos_e20a`/`_e20b`, issue #41); the documented
`BGREP_REGION_EVAL_SKIP_DRIVER_GUARD=1` twin-runner opt-out was used after
confirming no `swebench_driver` process existed.

## Smoke (protocol step 1, e7b hub/E-class set + hub-gold guards)

- **E21 met its smoke criterion**: astropy-14182 — gold `rst.py` (absent at
  baseline, lost to the `ascii/core.py` attractor) inserted under BOTH chunk
  arms; and the two hub-gold guard instances from the E20 loss anatomy
  IMPROVED rather than losing (sympy-15346 gold `trigsimp.py` rank 11→1,
  sympy-20322 gold `mul.py` 25→11) — chunk-max helps central gold files,
  the anti-E20-hub-guard property the round was designed around.
- **E22**: cap held at exactly 5 bridged files on every firing query (no
  flooding); call evidence populated; but no gold file bridged on the smoke
  set, and tb0.1 LOST sympy-15346's gold via insertion displacement (tb0.3
  did not) — a warning that replicated exactly in the full run (below).
- Chunk arms cost +15–40% query_ms at sympy/django scale (e.g. 8.6→9.8s
  worst smoke instance; ~2.8→3.7s astropy).

## Lite-300 (all arms 300/300 ok, engine `d1279e8` clean)

Baseline reproduces the v12 adopted-engine reference EXACTLY: FILE 92.33
(277/300), FUNCTION 54.67, LINE 43.33, fraction 0.52510439865484 —
float-identical to `agentless_metric_e20_traceboost.json`, zero per-instance
`hunk_line_recall` mismatches vs `e20_traceboost.jsonl` (contamination
backstop clean).

| arm | FILE | FUNCTION | LINE | fraction Δ [CI95] |
|---|---|---|---|---|
| baseline (v12) | **92.33** (277/300) | **54.67** | **43.33** | .52510 |
| E21 chunk-max | 92.67 (+0.33, 5G/4L, p=1.0) | 52.00 (**−2.67**, 3G/11L, p=.057) | 42.33 (−1.00, 5G/8L, p=.581) | −.0080 [−.0283,+.0128] |
| E21 chunk-top2 | 92.33 (0.00, 4G/4L, p=1.0) | 53.33 (−1.33, 7G/11L, p=.481) | 42.33 (−1.00, 7G/10L, p=.629) | −.0079 [−.0304,+.0140] |
| E22 w=0.1 | 92.00 (−0.33, 0G/1L, p=1.0) | 54.00 (−0.67, 1G/3L, p=.625) | 43.33 (0.00, 2G/2L, p=1.0) | −.0030 [−.0109,+.0016] |
| E22 w=0.3 | 92.67 (+0.33, 1G/0L, p=1.0) | 53.67 (−1.00, 2G/5L, p=.453) | 43.67 (+0.33, 3G/2L, p=1.0) | +.0039 [−.0010,+.0098] |

## Flip anatomy

**E21 chunk-max FILE (5G/4L).** Gains: astropy-14182 (gold `rst.py` in;
`ascii/core.py`'s accumulated 118.45 collapses to a 66.32 best-chunk under
top2's diagnostics — the hub-demotion anatomy verbatim), django-11815 (gold
`migrations/serializer.py`), django-16229 (gold `forms/boundfield.py`;
`forms/models.py` 109.11→83.09, `forms/fields.py` 107.09→85.17 — big
accumulators damped), matplotlib-23314 (gold `mplot3d/axes3d.py`;
`pyplot.py` 54.86→41.44), sympy-13915 (gold `core/mul.py`). Losses:
django-11630, django-15498, matplotlib-18869 (gold `axes3d.py` — the same
file the 23314 gain rescued; its own accumulation 84.05→83.70 survived but
competitors reshuffled the pool), pytest-9359 (`config/__init__.py`
102.50→94.17 — displacement, the gold was riding the old pool shape). The
FILE churn is symmetric (p=1.0): every gain has the predicted anatomy, but
equal-and-opposite pool reshuffles pay for it.

**E21 region guardrail violation is the headline.** FUNCTION −2.67 (3G/11L,
p=.057, CI [−5.33,−0.33] excludes zero) and it is mostly NOT a file-flip
side-effect: 9 of the 11 FUNCTION losses (django-11620/-11905/-11910/-16910,
sphinx-8721/-8801, sympy-15011/-20154, scikit-learn-25638) had NO FILE flip —
the chunk-based normalized `scores` map feeds `pack_regions`' budget
allocation, and flattening whole-file accumulation reshapes per-file budget
shares inside an unchanged file list. Quantified: in 8 of those 9 losses the
GOLD file's packed line budget shrank under chunk-max (`views/debug.py`
136→75 lines, `models/lookups.py` 205→129, `utilities/iterables.py` 481→213,
`migrations/autodetector.py` 158→127, ...) — gold files are often the large
central files (the E20 postmortem's finding), and chunk-max damps exactly
their normalized score relative to small dense competitors, so the E20
"central-gold tax" reappears one stage down, at budget allocation instead of
ranking. The FILE-stage mechanism works as specified; the damage is
collateral, through the score-map coupling. chunk-top2 shows the same
signature milder (FUNCTION −1.33, LINE −1.00) with FILE net zero.

**E22 w=0.1 FILE (0G/1L).** The sole flip is the smoke warning confirmed:
sympy-15346 gold `trigsimp.py` (baseline rank 11) evicted by five bridged
insertions (`utilities/pytest.py`, `exceptions.py`, `core/basic.py`,
`core/function.py`, `core/numbers.py` — none gold). Pure displacement loss.

**E22 w=0.3 FILE (1G/0L).** Gain sympy-21055 (gold `assumptions/refine.py`)
— but the gold was NOT among the bridged files (bridge inserted
`core/expr.py` add=19.44, `meijerint.py`, `complexes.py`, `integrals.py`,
`piecewise.py`): the gain is an INDIRECT pool reshuffle, not the designed
issue→test→gold pathway. Across all 300 instances at both weights, **no
bridged file was ever a missing gold file** — the two-hop static bridge
lands on prominent production files near the tests, which are largely files
the lexical ranking already found (247/300 queries bridge at the full cap of
5; mean 4.19; the cap is load-bearing). tb0.1 vs tb0.3 non-monotonicity on
sympy-15346 (0.1 loses gold, 0.3 keeps it at rank 30) is a k-boundary
artifact: small additions evict the tail, larger ones reorder the head.
tb0.3's LINE +0.33 / FUNCTION churn is likewise bridge-induced budget
reshuffle, not the designed pathway: in every region-flip gain instance
(django-13220/-13590/-13710, xarray-3364) the bridged non-gold files
entered the packed set and redistributed budget; FUNCTION −1.00 has CI
[−2.67, +0.67] (not bounded away from zero, unlike chunk-max's).

## Verdicts (per mechanism, Lite gate)

- **E21 chunk-max — REJECT.** FILE +0.33 is churn (5G/4L, p=1.0) and the
  region guardrails are violated: FUNCTION −2.67 with a CI excluding zero
  (3G/11L, p=.057), LINE −1.00, fraction −.0080. Did not advance to
  Verified (e20-import07 precedent: Lite guardrail violation stops the arm).
- **E21 chunk-top2 — REJECT.** FILE net 0.00 (4G/4L churn) with the same
  region degradation signature milder (FUNCTION −1.33, LINE −1.00). The
  softer aggregate halves the collateral damage but also halves the FILE
  effect to zero.
- **E22 w=0.1 — REJECT.** Strictly harmful: FILE −0.33 via the predicted
  displacement loss (the ledger's additive-channel failure mode, now
  reproduced even with pre-normalization integration and a hard cap),
  FUNCTION −0.67, fraction −.0030.
- **E22 w=0.3 — REJECT.** FILE +0.33 (1G/0L) but the gain is indirect (gold
  never bridged), FUNCTION guardrail sign-negative (−1.00, 2G/5L), and the
  designed pathway produced zero direct gold rescues in 300 instances.
  Positive fraction (+.0039) has a CI spanning zero. Does not meet
  "Lite-positive with guardrails intact".

## Campaign notes

- **The load-bearing new fact for E21b**: chunk-max's FILE-stage behavior is
  exactly as the spec predicted (hub attractors demoted on merit, central
  gold files HELPED at the ranking stage — no E20-style hub-guard tax in any
  FILE flip), but swapping the fused map wholesale couples the ranking
  change into `pack_regions`' budget allocator, and THAT is where the losses
  live: 9/11 FUNCTION losses had no FILE flip, and in 8 of those 9 the gold
  file's packed budget shrank — the central-gold tax reappearing at the
  budget stage. Revival precondition, concrete: **chunk-max for file RANKING
  only** — select/order files by the chunk aggregate but hand pack_regions
  the accum-normalized `scores` map. Decouples the validated FILE mechanism
  from the damaged region stage.
- **E22's premise is falsified in its static form**: tests bridge to
  prominent already-retrieved production files, not to the lexically-flat
  gold (IssueExec's 97% test-coverage-of-gold stat does not survive the
  "top-3 lexically-matching tests, imports+calls only" approximation — the
  RIGHT test is rarely in the lexical top-3, and when it is, its imports
  name the popular neighbors, not the fix site). A deeper bridge (test
  selection beyond lexical top-3, or transitive import hops) would fight
  the same displacement economics with weaker signal; not recommended.
- Chunk scoring costs +15–40% query_ms (per-query re-tokenization of
  matched files' lines); would need amortization (indexed chunk stats)
  before any adoption conversation.
- IndexMap iteration-order note: both new channels are deterministic by
  construction (files-order iteration, terms-order summation, sorted
  import-target iteration, canonical tie-breaks); determinism unit-tested.

## Artifacts

- Predictions: `lab/results_regions/{e21_baseline,e21_chunkmax,e21_chunktop2,e22_tb01,e22_tb03}.jsonl`
- Scores: `lab/results_regions/agentless_metric_{e21_baseline,e21_chunkmax,e21_chunktop2,e22_tb01,e22_tb03}.json`
- Paired stats: `lab/stats/{e21_chunkmax,e21_chunktop2,e22_tb01,e22_tb03}_vs_baseline.json`
- Runners + logs: `lab/results_regions/e21_run{A,B}.{sh,log}`
- Byte-identity + smoke scripts and raw smoke JSON: session scratchpad (not
  committed, per convention); smoke results summarized above.
