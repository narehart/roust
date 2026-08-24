# E20 (LexBoost neighbor smoothing) + E11b (trace-frame boost-only) — dual gate

*Campaign #4, wave 5. Branch `e20-lexboost`, engine commit `8034a57` (off main
`69aa161`, post-E11-merge). Specs: `wave5/file-ranking-and-routing.md` a1/a2
(LexBoost, arXiv:2409.05882) and b2 (BRTracer trace boost); E11b's charter is
`wave5/e11-results.md`'s final verdict — the rank-decayed trace-frame FILE
boost was E11's sole cross-dataset survivor (4 FILE rescues / 0 losses), and
the REJECT anatomy demanded a boost-only re-test with query text
byte-untouched. PRIMARY metric this round: FILE (E-class rescue);
FUNCTION/LINE/fraction are guardrails (the E11 budget-displacement lesson).*

## Mechanisms (both flag-gated, defaults byte-identical)

- **E20 `--lexboost <lambda>` + `--lexboost-graph <import|knn>`**: smooth the
  normalized channel-fused file score with the MEAN score of corpus-graph
  neighbors: `S' = lambda*S + (1-lambda)*impl_prior(f)*mean_{n in N(f)} S(n)`.
  Zero-direct-score files with scored neighbors are INSERTED (E-class
  rescue). Guards: (1) hub protection — files whose graph in-degree is
  strictly above the corpus's 90th percentile receive NO neighbor term
  (`S' = lambda*S`); (2) the neighbor term is multiplied by `impl_prior(f)`
  so test-shaped files cannot ride neighbor support past the engine's
  existing damping. Graphs: `import` = the cached undirected import graph
  (free); `knn` = deterministic BM25 16-nearest-neighbors by content
  similarity (per-file top-32 tf-idf query terms, df<=512 cost cap,
  canonical tie-breaks everywhere), built from cached corpus stats at query
  time.
- **E11b `--trace-boost`**: `trace_frame_files()` scans issue lines for
  CPython frame lines, resolves paths into the corpus
  (`resolve_frame_path`, >=2 trailing components), and feeds the resolved
  files raise-site-first into the EXISTING E11 boost channel (1/rank
  frames 1–10, 0.1 deeper, 0.1 import spillover). Query terms are
  byte-untouched (no mine-then-discard anywhere); unit test proves
  `trace_frame_files == route_query().trace_files`. Mutually exclusive with
  `--route`.

Proofs before arms: 7 new Rust tests (smoothing math to 1e-12, hub guard,
insertion rescue, lambda=1 identity, kNN determinism/sortedness/no-self,
prior damping, defaults-off identity), full suite green; defaults
byte-identity 14/14 instances (all 12 Lite repos) vs the main-built
`69aa161` binary, two branch runs each (md5 over files+regions+bundle).
Private clone copies per issue #41 (`swebench_repos_e20a/_e20b`); the
`swebench_driver_guard` raced against its own twin at simultaneous launch
(each runner's `pgrep -f swebench_driver` matched the other's pgrep), so
runs used the documented `BGREP_REGION_EVAL_SKIP_DRIVER_GUARD=1` opt-out
after confirming no driver process existed; the baseline's exact
reference reproduction (below) is the contamination backstop.

## Smoke (protocol step 1)

E20 flipped 3 of the e7b E-class miss set before any arm ran
(astropy-14182 under BOTH graphs; sympy-13146 import; django-11283 knn),
with the gold anatomy showing the paper's mechanism verbatim (rst.py:
direct .49, neighbor-mean .75 -> smoothed .57). Hub check: `sympy/core/
expr.py` and `sphinx/application.py` marked `is_hub`, neighbor term zeroed,
no hub gained anywhere. E11b fired only on trace instances — but did NOT
flip django-12113/astropy-14182 (E11's Lite FILE gains), first evidence
that those gains needed the term-surgery half of the E11 package.

## Lite-300 (all arms 300/300 ok, engine `8034a57` clean)

Baseline reproduces the adopted-engine reference EXACTLY: FILE 92.33
(277/300), FUNCTION 53.33, LINE 42.67, fraction .5168305891310305 —
float-identical to the E11-round artifact.

| arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|
| baseline | **92.33** (277/300) | **53.33** | **42.67** | **.51683** |
| E20 import λ0.7 | 92.33 (6G/6L, p=1.0) | 51.00 (6G/13L, p=.167) | 41.00 (3G/8L, p=.227) | .50571 [−.0299,+.0067] |
| E20 knn λ0.7 | 92.67 (5G/4L, p=1.0) | 53.33 (9G/9L) | 42.67 (6G/6L) | .52327 [−.0129,+.0258] |
| E11b trace-boost | 92.33 (**0 discordants**) | **54.67 (4G/0L, p=.125)** | 43.33 (3G/1L) | **.52510 [+.0000,+.0192]** |

### λ mini-sweep (knn, Lite only — dose-response)

| arm | FILE | FUNCTION | LINE | fraction Δ [CI95] |
|---|---|---|---|---|
| knn λ0.5 | 92.33 (6G/6L) | 49.33 (**−4.00**, 9G/21L, p=.043) | 38.67 (**−4.00**, 4G/16L, p=.012) | −.0349 [−.0614,−.0092] |
| knn λ0.7 | 92.67 (5G/4L) | 53.33 (9G/9L) | 42.67 (6G/6L) | +.0064 [−.0129,+.0258] |
| knn λ0.9 | 92.67 (2G/1L) | 53.33 (4G/4L) | 43.33 (3G/1L) | **+.0098 [+.0009,+.0213]** |

Clean monotone dose-response: heavier neighbor weight strictly degrades
region metrics (λ0.5 is McNemar-significantly negative on FUNCTION and
LINE). λ0.9 — the mildest smoothing — is the only E20 cell in the round
with a CI-excluding-zero positive fraction delta, and keeps the FILE +1
with far less churn (2G/1L vs 5G/4L).

### Lite FILE flip anatomy (every flip itemized)

**import07** (6G/6L): gains astropy-14182 (rst.py direct .49 / nb-mean .75),
django-15388/16229/17087, sympy-13146, sympy-21055; losses django-11797,
matplotlib-25311, pytest-7490, pytest-9359, and — the mechanism finding —
**sympy-15346 and sympy-20322 lost because their gold files
(`simplify/trigsimp.py` direct .79→.56, `core/mul.py` .77→.54) are
themselves import-graph hubs**: the hub guard zeroed their neighbor term
while every competitor kept its blend.

**knn07** (5G/4L): gains astropy-14182, django-11283 (the
`0011_update_proxy_permissions.py` E-class rescue, direct .78 / nb .46),
django-16229, django-17087, sympy-21055; losses django-11797 (lookups.py
.68→.61, displacement), matplotlib-23476/25311, sympy-15346.

**trace-boost: zero FILE flips.** E11's two Lite FILE gains
(django-12113, astropy-14182) did NOT reproduce under boost-only — those
gains required E11's mine-then-discard term surgery interacting with the
boost; attribution in `e11-results.md` ("component: trace boost") was
package-level, not ablated. The boost-only FILE effect on Lite is nil.

**trace-boost FUNCTION 4G/0L** (django-15202, matplotlib-25079,
sympy-13471, sympy-22714): in every gain the gold file sits at **frame
rank 1 (the raise site)** — the boost raises the gold file's entry in the
`scores` map, and `pack_regions` reallocates budget toward it, landing the
right function in a file that was ALREADY retrieved. LINE 3G/1L (loss:
django-13028, 1.00→0.857 partial, mild displacement). Fired on 46/300;
254 non-trace instances byte-identical.

## Verified-407 (all arms 407/407 ok; dual gate)

Baseline reproduces the Verified reference EXACTLY: FILE 92.14 (375/407),
FUNCTION 47.17, LINE 35.38, fraction .47522.

| arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|
| baseline | **92.14** (375/407) | **47.17** | **35.38** | **.47522** |
| E20 knn λ0.7 | 92.38 (7G/6L, p=1.0) | 46.68 (−0.49, 10G/12L) | 34.89 (−0.49, 6G/8L) | .47740 [−.0114,+.0160] |
| E11b trace-boost | 92.38 (**1G/0L**) | 47.17 (1G/1L) | 35.63 (**1G/0L**) | .47810 [−.0015,+.0090] |

(import λ0.7 did not advance to Verified: Lite region guardrails violated.)

### Verified flip anatomy

**knn07** (7G/6L): gains django-14011, django-16662, matplotlib-24870,
matplotlib-25775, scikit-learn-25102, sphinx-11510, sympy-20801 — all
non-hub, standard neighbor promotion. Losses: sphinx-7462, sphinx-9591,
sympy-15875, and **three hub-guard-caused gold losses** —
`django/db/models/expressions.py` (direct .72→.51), `sphinx/domains/std.py`
(.64→.44), `sphinx/util/inspect.py` (.78→.54), all `hub=True,
nb_mean=0.0`. Same failure mode as import07 on Lite, now on held-out data:
**gold files are disproportionately central files, so top-decile hub
exclusion systematically taxes exactly the files the experiment is trying
to rescue.**

**trace-boost**: FILE GAIN pylint-8898 (`pylint/utils/__init__.py` via the
0.1 import spillover, not a direct frame file) — the same instance E11's
package gained; zero FILE losses. FUNCTION 1G (django-15380, gold at frame
rank 1, LINE 0→1.0 with it) / 1L (matplotlib-20859 — the same instance in
E11's Verified loss anatomy; under E11 its fraction collapsed .39→.00 via
term replacement + displacement, under boost-only a mild within-file
displacement remains). Fired on 38/407; 369 non-trace instances
byte-identical. kNN graph cost on Verified: p50 240ms / p90 550ms / max
1487ms per query (vs ~0.6–1.8s cold index) — under the 2x cold-index
adoption blocker, but a real per-query tax at django scale.

## Verdicts (per mechanism, dual-gate evidence)

- **E20 import-graph λ0.7 — REJECT.** Lite: FILE net 0 with 6G/6L churn;
  FUNCTION −2.33 / LINE −1.67 (guardrails violated); 2 of 6 losses caused
  by the hub guard taxing central gold files. Never advanced to Verified.
- **E20 BM25-kNN λ0.7 — REJECT.** FILE "wins" are churn, not signal: net
  +1 on each dataset at p=1.0 (Lite 5G/4L, Verified 7G/6L), and Verified
  region guardrails go sign-negative (FUNCTION/LINE −0.49). The E-class
  rescue is real (astropy-14182, django-11283 flip exactly as the paper
  predicts) but symmetric displacement + hub-guard gold losses cancel it.
  **Flagged follow-up, not gated here**: λ0.9 is the only cell with a
  CI-positive Lite fraction (+.0098 [+.0009,+.0213]) and the dose-response
  is cleanly monotone toward light smoothing — a redesigned E20b (λ≈0.9,
  hub handling that does not zero gold-heavy central files, e.g.
  degree-capped mean instead of exclusion) would need its own full dual
  gate.
- **E11b trace-boost — ADOPT-RECOMMEND (weak, clean).** Passes both gates
  as specified: Lite is positive with guardrails intact (FUNCTION +1.33,
  4G/0L; LINE +0.67; fraction +.0083 with CI lower bound +.0000; FILE
  zero discordants), and Verified is non-negative in every cell with the
  same sign (FILE +0.25 1G/0L, LINE +0.25 1G/0L, fraction +.0029,
  FUNCTION 0.00 at 1G/1L). Cross-dataset totals: FILE 1G/0L, FUNCTION
  5G/1L, LINE 4G/1L. The E11 Verified trace catastrophe (FUNCTION 0G/5L)
  is cured by leaving query text untouched — confirming e11-results.md's
  diagnosis that term replacement, not the boost, did the damage. Honest
  caveats, stated plainly: effect sizes are small (~1.3pp Lite FUNCTION,
  +0.25pp Verified FILE/LINE), no single cell is McNemar-significant
  (best p=.125), and the Lite 4G/0L FUNCTION pattern attenuated to 1G/1L
  held-out. The adoption case is asymmetric risk, not effect size: zero
  measured downside beyond two mild partial-line displacements, strictly
  additive, fires on only ~10–12% of instances (trace-bearing), provably
  byte-identical elsewhere, and zero query-time cost (a regex scan).
  **Default-on change if adopted (NOT flipped in this branch):**
  `--trace-boost` default true (or fold into the engine unconditionally,
  keeping `--no-trace-boost` as the escape hatch; `--route` stays
  rejected/off and mutually exclusive). Scoreboard deltas: Lite FUNCTION
  53.33→54.67, LINE 42.67→43.33, fraction .5168→.5251, FILE unchanged
  92.33; Verified FILE 92.14→92.38, LINE 35.38→35.63, fraction
  .4752→.4781, FUNCTION unchanged 47.17.

## Campaign notes

- **The FILE thread stays hard.** Both graph substrates rescue genuine
  E-class instances, but at λ0.7 the rescue is paid for one-for-one by
  displacement and hub-guard losses. The load-bearing new fact for E20b:
  **hub exclusion and gold-file centrality collide** — 5 of the round's
  gold-file FILE losses across arms had `hub=True` anatomy. Any future hub
  defense must damp attractors without zeroing central gold files.
- **E11's attribution is now ablated**: boost-only reproduces NONE of the
  package's Lite FILE gains (0 flips vs the package's +3 net) but keeps
  its region-side benefit and its Verified FILE gain (pylint-8898). The
  surviving mechanism is "give the raise-site file budget priority", not
  "insert frame files into the pool".
- IPython-format tracebacks remain unclaimed (E11 known limitation,
  inherited unchanged by `trace_frame_files`).

## Artifacts

- Predictions: `lab/results_regions/e20_{baseline,import07,knn07,knn05,knn09,traceboost}.jsonl`,
  `lab/results_regions/e20_verified_{baseline,knn07,traceboost}.jsonl`
- Scores: `lab/results_regions/agentless_metric_e20_*.json` (same stems)
- Paired stats: `lab/stats/e20_{import07,knn07,knn05,knn09,traceboost}_vs_baseline.json`,
  `lab/stats/e20_verified_{knn07,traceboost}_vs_baseline.json`
- Runners + logs: `lab/results_regions/e20_run{A,B,C,D}.{sh,log}`
- Byte-identity + smoke + itemization scripts: session scratchpad (not
  committed, per convention); smoke results summarized above.
