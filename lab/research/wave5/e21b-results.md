# E21b (chunk-max file RANKING decoupled from packer budgets) — Lite gate

*Campaign #4, wave 5. Branch `e21b-decoupled`, engine commit `a9d6cd0` (off
main `3f0c77b` + the E21 machinery `d1279e8..69020a7`, fast-forwarded). This
round is the revival precondition stated verbatim in
`wave5/e21-e22-results.md`: E21 proved chunk-max fixes FILE ranking (hub
demotion on merit, both hub-gold guards improved, zero gold taxes in any FILE
flip) but fails through the score-map coupling — the damped chunk-normalized
`scores` flow into `pack_regions` and shrink central gold files' packed
budgets (8/9 no-FILE-flip FUNCTION losses had shrunken gold budgets). E21b:
use the chunk aggregate ONLY for file selection/order; hand the packer the
ORIGINAL accumulation-normalized score map. Prediction: keeps chunk-max's 5
FILE gains, eliminates the budget-shrinkage FUNCTION losses.*

**Verdict up front: both arms REJECT at the Lite gate; no arm advanced to
Verified.** The decoupling mechanism WORKED as designed — all 5 FILE gains
held, and every budget-shrinkage loss whose packed budget was actually
restored (5 of 9) got its FUNCTION back, cutting the region tax from −2.67
(CI excluding zero) to −1.00 (CI [−3.33, +1.00], p=.55) — but the residual
FUNCTION/fraction signs are still negative, so the adoption guardrail
("FUNCTION/LINE/fraction non-negative") is not met. Flag-gated only; defaults
remain byte-identical to v12.

## Mechanism

`--file-score chunk-rank` (ChunkRankMax) and `chunk-top2-rank`
(ChunkRankTop2): the chunk-aggregated fused map (`Corpus::bm25_chunk`,
machinery reused wholesale from E21 `d1279e8`) drives `lex_picks`, the
structural-expansion sources, and the ranked output — exactly as coupled
chunk-max does — while an accum map (`Corpus::bm25`) rides alongside,
receives the SAME post-normalization channel mutations (test-bridge
additions, lexboost smoothing, trace-boost insertions, test-path penalty,
each mirrored value-for-value), and becomes the `scores` map handed to
`pack_regions`. Contract: on any query whose selected file list does not
change, the packer input is bit-identical to the Accum baseline's. E22
test-bridge paths were not exercised in any arm (flag inert at 0.0).

Proofs before arms: 4 new Rust tests (selection == ChunkMax's while the
budget map is bit-identical to Accum's, on both the lex-only and full-PPR
paths; top2-rank semantics; determinism), 65 lib tests green. Defaults
byte-identity 14/14 instances (one per repo ×12 + django-12113 +
astropy-14182), five md5s each over files+regions+bundle (main `3f0c77b`
binary ×2 runs, branch binary ×2 runs, explicit `--file-score accum`) — all
identical; engine provenance clean (`a9d6cd0, clean`, guard enforced).
Private clone copies (`swebench_repos_e20a`/`_e20b`, issue #41); documented
`BGREP_REGION_EVAL_SKIP_DRIVER_GUARD=1` twin-runner opt-out used after
confirming no `swebench_driver` process existed.

## Smoke (protocol step 1)

- **All 5 E21 FILE-gain instances still gain** under chunk-rank
  (astropy-14182 `rst.py`, django-16229 `boundfield.py`, matplotlib-23314
  `axes3d.py`, django-11815 `serializer.py`, sympy-13915 `mul.py`) — gold
  present in regions, absent at baseline.
- **Budget restoration is real but conditional on the selected list**: gold
  packed lines EXACTLY restored where the headline anatomy lived
  (django-11620 `views/debug.py` 75→136=baseline, django-11905
  `models/lookups.py` 129→205=baseline), near-restored on sympy-20154
  `utilities/iterables.py` (213→462 vs 481) and sphinx-8721 `viewcode.py`
  (124→139 vs 144), but NOT restored where chunk-selection changed the
  packing competition even with accum budgets: django-11910 `autodetector.py`
  158→127(cmax)→105(crank), sphinx-8801 `importer.py` and
  scikit-learn-25638 `multiclass.py` stuck at the chunk-max level. This
  smoke split predicted the FUNCTION flips exactly (below).
- query_ms: chunk-rank costs the same as chunk-max (+8–58% per query, worst
  5.6→8.8s django-16910; both chunk modes also pay a second accum pass for
  diagnostics/budgets). Full-run wall-clock was checkout-dominated
  (1671s vs baseline 1672s per 300). Amortization via indexed chunk stats
  remains the precondition for any adoption conversation (unchanged from
  E21); not attempted here per protocol.

## Lite-300 (all arms 300/300 ok, engine `a9d6cd0` clean)

Baseline reproduces the v12 reference EXACTLY: FILE 92.33 (277/300),
FUNCTION 54.67, LINE 43.33, fraction 0.52510439865484 — float-identical,
zero per-instance `hunk_line_recall` mismatches vs `e21_baseline.jsonl`
(contamination backstop clean).

| arm | FILE | FUNCTION | LINE | fraction Δ [CI95] |
|---|---|---|---|---|
| baseline (v12) | **92.33** (277/300) | **54.67** | **43.33** | .52510 |
| E21 chunk-max (coupled, prior round) | 92.67 (+0.33, 5G/4L, p=1.0) | 52.00 (−2.67, 3G/11L, p=.057) | 42.33 (−1.00) | −.0080 [−.0283,+.0128] |
| **E21b chunk-rank** | 92.67 (+0.33, 5G/4L, p=1.0) | 53.67 (−1.00, 4G/7L, p=.549) | 44.00 (+0.67, 4G/2L, p=.688) | −.0038 [−.0196,+.0119] |
| **E21b chunk-top2-rank** | 92.33 (0.00, 4G/4L, p=1.0) | 54.33 (−0.33, 8G/9L, p=1.0) | 43.67 (+0.33, 6G/5L, p=1.0) | +.0021 [−.0155,+.0198] |

## Flip anatomy

**The decisive question — did the 8 budget-shrinkage losses come back?
5 of 9 no-FILE-flip FUNCTION losses RESTORED, and the split is exactly the
smoke's budget split.** Restored: django-11620, django-11905, sphinx-8721,
sympy-15011, sympy-20154 — precisely the instances whose gold packed budget
the decoupling actually restored (exact or near). Still lost: django-11910,
django-16910, sphinx-8801, scikit-learn-25638 — precisely the four whose
gold budget stayed shrunken because the chunk-selected file LIST (not the
score map) changed the packing competition: with accum budgets, other
high-accum files in the chunk-chosen list soak up budget that baseline's
list gave to the gold file (11910's `autodetector.py` even dropped below its
coupled-chunk-max budget, 127→105). The E20 central-gold tax has a THIRD
face: after ranking (E20) and budget scores (E21), it survives in list
composition.

**chunk-rank FILE (5G/4L) is E21 chunk-max's flip set verbatim** — gains
astropy-14182, django-11815, django-16229, matplotlib-23314, sympy-13915;
losses django-11630, django-15498, matplotlib-18869, pytest-9359. Expected:
ranking is chunk-max's by construction; budgets don't feed back into FILE
selection. Symmetric churn (p=1.0), every gain with the hub-demotion
anatomy, every loss a pool reshuffle.

**chunk-rank FUNCTION (4G/7L) fully decomposed:** gains astropy-14182 (the
FILE gain converting to function level — the E-class rescue paying off
downstream), django-11019, scikit-learn-25747, sympy-18835 (packing
reshuffles in unchanged files). Losses: 2 are FILE-flip collateral
(django-11630, django-15498 — the file itself left the set), 4 are the
unrestored budget cases above, 1 is NEW (pydata__xarray-4094, no FILE flip —
residual list-composition reshuffle). LINE +0.67 and the top2 variant's
FUNCTION −0.33 / LINE +0.33 / fraction +.0021 show the same story milder:
decoupling recovered most of the coupled arms' region damage but not to
non-negative on FUNCTION.

## Verdicts (Lite gate)

- **E21b chunk-rank — REJECT.** FILE +0.33 remains churn (5G/4L, p=1.0), and
  though the decoupling did exactly what it was designed to do (FUNCTION
  −2.67→−1.00, CI now spans zero; LINE flips positive +0.67), FUNCTION
  −1.00 and fraction −.0038 are sign-negative: the "guardrails intact"
  bar for advancing to Verified is not met. The FILE gain never rose above
  churn in either round, so there is no positive signal to trade against.
- **E21b chunk-top2-rank — REJECT.** Closest to harmless (FUNCTION −0.33,
  LINE +0.33, fraction +.0021, all p=1.0) but FILE is net 0.00 — a
  guardrail-cleaner variant of a mechanism with nothing left to buy.

## Campaign notes

- **The budget-coupling hypothesis is confirmed and now fully closed**: the
  E21 FUNCTION damage was two-thirds budget-map coupling (fixed by E21b,
  5/9 restored, tax CI no longer excludes zero) and one-third
  list-composition effects that no score-map handoff can fix — packing
  competition depends on WHICH files are selected, and chunk-selection
  changes that set/order by design. A further decoupling ("chunk ranking
  for file order, baseline accum selection for the packed set") would
  forfeit the FILE gains (they ARE selection changes) — the mechanism
  space here is exhausted.
- **Chunk-max FILE ranking itself remains churn-positive-at-best** (5G/4L
  both rounds, p=1.0, identical flip sets): the hub-demotion gains are
  real and anatomically exactly as specified, but pool reshuffles pay for
  them one-for-one on Lite. Chunk aggregation is not a free FILE win; it
  is a different point on the same tradeoff curve.
- D-class remains the pool; the ledger's pattern holds — case-mining beats
  mechanism priors (this round's 5-restored/4-lost split was predicted
  instance-by-instance by the smoke's packed-line comparison, not by the
  aggregate hypothesis).

## Artifacts

- Predictions: `lab/results_regions/e21b_{baseline,chunkrank,chunktop2rank}.jsonl`
- Scores: `lab/results_regions/agentless_metric_e21b_{baseline,chunkrank,chunktop2rank}.json`
- Paired stats: `lab/stats/e21b_{chunkrank,chunktop2rank}_vs_baseline.json`
- Runners + logs: `lab/results_regions/e21b_run{A,B}.{sh,log}`
- Byte-identity + smoke scripts and raw smoke JSON: session scratchpad (not
  committed, per convention); results summarized above.
