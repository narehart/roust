# E27 — can evidence-gated co-change seats close the multi-gold-file gap?

Campaign #4 wave 6, serving the standing language-agnostic directive (#56):
get every language to Python-level measurements.
Engine: `roust 0.3.2 (d5263f6, clean)`, one pinned binary for all 32 arms.
**No default was flipped. The verdict is NO-ADOPT.**

## Question

E26 closed the coverage question and, in closing it, relocated the problem.
Stratifying every slice by gold-file count showed the remaining gap is neither
coverage nor budget:

* At **1 gold file** cpp 100.0, rust 97.6, py-Verified 95.8 and java 94.1 all
  meet or beat SWE-bench Lite's 92.33. Lite is 300/300 single-gold-file, so
  its headline was never an aggregate over a mixed workload.
* At **3+ gold files** everything collapses — jsts 10.1, c 4.3, java 20.0,
  go 27.3, rust 27.6, cpp 25.5 — and **Python-Verified itself drops to 63.6**.
  The weakness is shared with Python, not specific to any language.
* Bundles return ~30 files while multi-file instances need 3–6, so budget is
  not binding.
* **62% of missed multi-file gold is already in the candidate pool.** It loses
  the ranking, not the retrieval.
* **72–89% of missed gold co-changed historically with a gold file the engine
  DID select** (go 28/39, rust 59/66).

Reading `select_files`, co-change partners enter the pool unconditionally and
`cochange_strong` gates only a secondary list (sweeping it 5→2→1 changes
nothing — verified empirically). The real limiter is **Guarantee 2: each
source seats exactly ONE neighbour**, after which everything else must win on
`add_score`, which is dominated by lexical score — precisely what sibling gold
files lack.

`--cochange-seats <n>` (default 1 = shipped behaviour) widens that guarantee
to up to n neighbours per source, but extra seats go ONLY to candidates with
co-change evidence (`--cochange-seat-min <k>`, default 2), strongest first,
deterministic on ties. This round sweeps n ∈ {2, 3, 4} at k = 2 on every
slice.

## Method

* **One pinned binary, 32 arms.** `d5263f6` = the committed E27 implementation
  (`6e28c76`) plus two measurement-only commits: harness flag passthrough, and
  an env-gated seat trace. Built once, never rebuilt mid-run.
* **Instrumentation proven inert.** The trace is read from
  `ROUST_E27_SEAT_TRACE` and nothing downstream branches on it. Proven, not
  asserted: against a reference build of `6e28c76`, payloads are **identical
  on 8/8 repos at defaults and 8/8 at `--cochange-seats 1`**, across all six
  MSWE languages plus Python. Raw JSON is not a valid identity test here — the
  `stats` block carries `index_ms`/`query_ms`, so the reference binary differs
  from *itself* run to run; the comparison is on `bundle`/`files`/`regions`/
  `query`. At `--cochange-seats 3`, 4/8 repos change **including django**, so
  the mechanism is demonstrably live on Python, not census-inert the way E26
  was.
* **Fresh default arms on every slice**, rather than reusing E25's `_def`
  arms. E25 ran at `abb96af`, and `ca15227` (E26's `.rb`/`.pony` adoption) has
  since moved the default engine — which breaks the pairing outright on c and
  java and leaves jsts/go/rust/cpp resting on a census argument rather than a
  measurement. Default arms are the cheap half of this round, so every slice
  got its own same-binary default side. The E25/E26 numbers then become a
  drift audit instead of a load-bearing baseline (see below — all 32 cells
  reproduce).
* **Private clone dir per concurrent arm** (issue #41): 16 concurrent chains
  of two sequential arms, 10s stagger, caches cleared per arm. Scoring reads
  a third, idle jsts clone so no metric walk touches a dir with a live arm.
* **Provenance.** Every arm's log prints its `EXTRA_ENGINE_FLAGS`; default
  arms print `[]` and forward no seat flag at all, so their argv is
  byte-identical to every pre-E27 default arm's. Every record carries
  `engine_sha`, `cochange_seats`, `cochange_seat_min`.
* **Scoring.** `lab/agentless_metric_full.py --repos-dir --ts-functions
  --lang-functions` for the MSWE slices; `agentless_metric_v4.py` /
  `agentless_metric_verified.py` for Python. Never `lab/agentless_metric.py`,
  which ignores its CLI args.
* **Stats.** Exact McNemar (binomial, two-sided) per all-or-nothing metric,
  Wilcoxon signed-rank on the per-instance line fraction, both for the whole
  slice and **per gold-file stratum**.

Artifacts in `lab/results_regions/e27/`. Analysis: `lab/e27_paired.py`,
`lab/e27_seats.py`, `lab/e27_tables.py`, `lab/e27_mine.py`.

## Pre-registered adoption bar

Stated before the numbers, and not moved after them:

> 3+ stratum improves materially on the affected slices, **Lite AND Verified
> non-negative on all four metrics**, and no slice regresses significantly.


## Drift audit — fresh E27 default arms vs the committed README scoreboard

| slice | metric | README | E27 fresh default | match |
|---|---|---|---|---|
| jsts | FILE | 46.38 | 46.38 | yes |
|  | FUNCTION | 31.21 | 31.21 | yes |
|  | LINE | 14.14 | 14.14 | yes |
|  | frac | 0.262 | 0.262 | yes |
| java | FILE | 49.22 | 49.22 | yes |
|  | FUNCTION | 36.72 | 36.72 | yes |
|  | LINE | 14.06 | 14.06 | yes |
|  | frac | 0.415 | 0.415 | yes |
| go | FILE | 64.95 | 64.95 | yes |
|  | FUNCTION | 28.97 | 28.97 | yes |
|  | LINE | 16.59 | 16.59 | yes |
|  | frac | 0.41 | 0.41 | yes |
| rust | FILE | 60.25 | 60.25 | yes |
|  | FUNCTION | 19.67 | 19.67 | yes |
|  | LINE | 7.53 | 7.53 | yes |
|  | frac | 0.243 | 0.243 | yes |
| c | FILE | 51.56 | 51.56 | yes |
|  | FUNCTION | 28.12 | 28.12 | yes |
|  | LINE | 13.28 | 13.28 | yes |
|  | frac | 0.225 | 0.225 | yes |
| cpp | FILE | 65.89 | 65.89 | yes |
|  | FUNCTION | 17.83 | 17.83 | yes |
|  | LINE | 6.98 | 6.98 | yes |
|  | frac | 0.299 | 0.299 | yes |
| python Lite | FILE | 92.33 | 92.33 | yes |
|  | FUNCTION | 54.67 | 54.67 | yes |
|  | LINE | 44.0 | 44.0 | yes |
|  | frac | 0.527 | 0.527 | yes |
| python Verified | FILE | 92.38 | 92.38 | yes |
|  | FUNCTION | 47.17 | 47.17 | yes |
|  | LINE | 35.14 | 35.14 | yes |
|  | frac | 0.476 | 0.476 | yes |

**All 32 cells reproduce: True**

Re-running defaults instead of reusing E25's cost one wave and bought a
32-cell reproducibility proof: the whole rig reproduces on a different engine
commit, with fresh clones, to the last digit. The pairing in this round is
sound, and the published scoreboard is confirmed rather than assumed.

## Per-slice results

| slice | n | arm | FILE | FUNCTION (exact) | LINE | line frac |
|---|---|---|---|---|---|---|
| **jsts** | 580 | default | 46.38 (269) | 31.21 (181) | 14.14 (82) | 0.26156 |
| | | seats 2 | 46.55 (270) | 31.03 (180) | 14.14 (82) | 0.26172 |
| | | *delta* | *+0.17* | *-0.18* | *+0.00* | *+0.00016* |
| | | seats 3 | 46.55 (270) | 31.03 (180) | 13.97 (81) | 0.26133 |
| | | *delta* | *+0.17* | *-0.18* | *-0.17* | *-0.00023* |
| | | seats 4 | 46.21 (268) | 30.86 (179) | 13.79 (80) | 0.25958 |
| | | *delta* | *-0.17* | *-0.35* | *-0.35* | *-0.00198* |
| **java** | 128 | default | 49.22 (63) | 36.72 (47) | 14.06 (18) | 0.41522 |
| | | seats 2 | 49.22 (63) | 37.50 (48) | 14.06 (18) | 0.41678 |
| | | *delta* | *+0.00* | *+0.78* | *+0.00* | *+0.00156* |
| | | seats 3 | 50.00 (64) | 37.50 (48) | 14.06 (18) | 0.41940 |
| | | *delta* | *+0.78* | *+0.78* | *+0.00* | *+0.00418* |
| | | seats 4 | 50.78 (65) | 37.50 (48) | 14.06 (18) | 0.41792 |
| | | *delta* | *+1.56* | *+0.78* | *+0.00* | *+0.00270* |
| **go** | 428 | default | 64.95 (278) | 28.97 (124) | 16.59 (71) | 0.41021 |
| | | seats 2 | 65.42 (280) | 32.01 (137) | 17.29 (74) | 0.42184 |
| | | *delta* | *+0.47* | *+3.04* | *+0.70* | *+0.01164* |
| | | seats 3 | 65.42 (280) | 30.37 (130) | 16.82 (72) | 0.41567 |
| | | *delta* | *+0.47* | *+1.40* | *+0.23* | *+0.00546* |
| | | seats 4 | 65.65 (281) | 29.67 (127) | 16.82 (72) | 0.41286 |
| | | *delta* | *+0.70* | *+0.70* | *+0.23* | *+0.00266* |
| **rust** | 239 | default | 60.25 (144) | 19.67 (47) | 7.53 (18) | 0.24315 |
| | | seats 2 | 60.67 (145) | 19.67 (47) | 7.53 (18) | 0.24342 |
| | | *delta* | *+0.42* | *+0.00* | *+0.00* | *+0.00027* |
| | | seats 3 | 60.67 (145) | 19.25 (46) | 7.53 (18) | 0.24264 |
| | | *delta* | *+0.42* | *-0.42* | *+0.00* | *-0.00050* |
| | | seats 4 | 60.67 (145) | 18.83 (45) | 7.53 (18) | 0.24248 |
| | | *delta* | *+0.42* | *-0.84* | *+0.00* | *-0.00067* |
| **c** | 128 | default | 51.56 (66) | 28.12 (36) | 13.28 (17) | 0.22513 |
| | | seats 2 | 51.56 (66) | 27.34 (35) | 13.28 (17) | 0.22276 |
| | | *delta* | *+0.00* | *-0.78* | *+0.00* | *-0.00237* |
| | | seats 3 | 50.78 (65) | 27.34 (35) | 13.28 (17) | 0.22240 |
| | | *delta* | *-0.78* | *-0.78* | *+0.00* | *-0.00273* |
| | | seats 4 | 50.00 (64) | 28.12 (36) | 13.28 (17) | 0.22320 |
| | | *delta* | *-1.56* | *+0.00* | *+0.00* | *-0.00193* |
| **cpp** | 129 | default | 65.89 (85) | 17.83 (23) | 6.98 (9) | 0.29880 |
| | | seats 2 | 65.89 (85) | 17.83 (23) | 6.98 (9) | 0.29911 |
| | | *delta* | *+0.00* | *+0.00* | *+0.00* | *+0.00031* |
| | | seats 3 | 66.67 (86) | 17.83 (23) | 6.98 (9) | 0.29883 |
| | | *delta* | *+0.78* | *+0.00* | *+0.00* | *+0.00003* |
| | | seats 4 | 66.67 (86) | 17.83 (23) | 6.98 (9) | 0.29883 |
| | | *delta* | *+0.78* | *+0.00* | *+0.00* | *+0.00003* |
| **python Lite** | 300 | default | 92.33 (277) | 54.67 (164) | 44.00 (132) | 0.52728 |
| | | seats 2 | 92.33 (277) | 54.00 (162) | 43.67 (131) | 0.52180 |
| | | *delta* | *+0.00* | *-0.67* | *-0.33* | *-0.00548* |
| | | seats 3 | 92.33 (277) | 54.00 (162) | 43.33 (130) | 0.52199 |
| | | *delta* | *+0.00* | *-0.67* | *-0.67* | *-0.00528* |
| | | seats 4 | 92.33 (277) | 54.00 (162) | 43.33 (130) | 0.52088 |
| | | *delta* | *+0.00* | *-0.67* | *-0.67* | *-0.00640* |
| **python Verified** | 407 | default | 92.38 (376) | 47.17 (192) | 35.14 (143) | 0.47635 |
| | | seats 2 | 92.38 (376) | 46.68 (190) | 35.14 (143) | 0.47491 |
| | | *delta* | *+0.00* | *-0.49* | *+0.00* | *-0.00144* |
| | | seats 3 | 92.14 (375) | 45.70 (186) | 35.14 (143) | 0.47247 |
| | | *delta* | *-0.24* | *-1.47* | *+0.00* | *-0.00387* |
| | | seats 4 | 92.14 (375) | 45.95 (187) | 34.89 (142) | 0.47199 |
| | | *delta* | *-0.24* | *-1.22* | *-0.25* | *-0.00435* |

## Stratified by gold-file count — the headline

FILE / FUNCTION / LINE per stratum. The 3+ column is the target.

| slice | arm | 1 gold | 2 gold | 3+ gold |
|---|---|---|---|---|
| **jsts** | default | 72.50/41.79/26.43 (n=280) | 48.39/26.88/5.38 (n=93) | 10.14/18.84/1.45 (n=207) |
| | seats 2 | 72.86/41.79/26.43 (n=280) | 48.39/25.81/5.38 (n=93) | 10.14/18.84/1.45 (n=207) **[FILE +0.00, 0/0, p=1.0000]** |
| | seats 3 | 72.86/41.79/26.07 (n=280) | 48.39/25.81/5.38 (n=93) | 10.14/18.84/1.45 (n=207) **[FILE +0.00, 0/0, p=1.0000]** |
| | seats 4 | 72.86/41.43/25.71 (n=280) | 48.39/25.81/5.38 (n=93) | 9.18/18.84/1.45 (n=207) **[FILE -0.96, 2/0, p=0.5000]** |
| **java** | default | 94.12/52.94/35.29 (n=51) | 18.92/43.24/0.00 (n=37) | 20.00/10.00/0.00 (n=40) |
| | seats 2 | 94.12/52.94/35.29 (n=51) | 18.92/45.95/0.00 (n=37) | 20.00/10.00/0.00 (n=40) **[FILE +0.00, 0/0, p=1.0000]** |
| | seats 3 | 94.12/52.94/35.29 (n=51) | 21.62/45.95/0.00 (n=37) | 20.00/10.00/0.00 (n=40) **[FILE +0.00, 0/0, p=1.0000]** |
| | seats 4 | 96.08/52.94/35.29 (n=51) | 21.62/45.95/0.00 (n=37) | 20.00/10.00/0.00 (n=40) **[FILE +0.00, 0/0, p=1.0000]** |
| **go** | default | 88.30/53.19/31.38 (n=188) | 75.26/19.59/11.34 (n=97) | 27.27/3.50/0.70 (n=143) |
| | seats 2 | 88.83/59.57/32.98 (n=188) | 75.26/20.62/11.34 (n=97) | 27.97/3.50/0.70 (n=143) **[FILE +0.70, 0/1, p=1.0000]** |
| | seats 3 | 88.83/55.85/31.91 (n=188) | 74.23/20.62/11.34 (n=97) | 28.67/3.50/0.70 (n=143) **[FILE +1.40, 0/2, p=0.5000]** |
| | seats 4 | 88.83/54.79/31.91 (n=188) | 75.26/20.62/11.34 (n=97) | 28.67/2.80/0.70 (n=143) **[FILE +1.40, 0/2, p=0.5000]** |
| **rust** | default | 97.56/39.02/21.95 (n=82) | 67.31/11.54/0.00 (n=52) | 27.62/8.57/0.00 (n=105) |
| | seats 2 | 97.56/39.02/21.95 (n=82) | 69.23/11.54/0.00 (n=52) | 27.62/8.57/0.00 (n=105) **[FILE +0.00, 0/0, p=1.0000]** |
| | seats 3 | 97.56/37.80/21.95 (n=82) | 69.23/11.54/0.00 (n=52) | 27.62/8.57/0.00 (n=105) **[FILE +0.00, 0/0, p=1.0000]** |
| | seats 4 | 97.56/36.59/21.95 (n=82) | 69.23/11.54/0.00 (n=52) | 27.62/8.57/0.00 (n=105) **[FILE +0.00, 0/0, p=1.0000]** |
| **c** | default | 78.79/43.94/25.76 (n=66) | 75.00/18.75/0.00 (n=16) | 4.35/8.70/0.00 (n=46) |
| | seats 2 | 78.79/42.42/25.76 (n=66) | 75.00/18.75/0.00 (n=16) | 4.35/8.70/0.00 (n=46) **[FILE +0.00, 0/0, p=1.0000]** |
| | seats 3 | 78.79/42.42/25.76 (n=66) | 68.75/18.75/0.00 (n=16) | 4.35/8.70/0.00 (n=46) **[FILE +0.00, 0/0, p=1.0000]** |
| | seats 4 | 78.79/43.94/25.76 (n=66) | 62.50/18.75/0.00 (n=16) | 4.35/8.70/0.00 (n=46) **[FILE +0.00, 0/0, p=1.0000]** |
| **cpp** | default | 100.00/34.04/19.15 (n=47) | 88.89/7.41/0.00 (n=27) | 25.45/9.09/0.00 (n=55) |
| | seats 2 | 100.00/34.04/19.15 (n=47) | 88.89/7.41/0.00 (n=27) | 25.45/9.09/0.00 (n=55) **[FILE +0.00, 0/0, p=1.0000]** |
| | seats 3 | 100.00/34.04/19.15 (n=47) | 88.89/7.41/0.00 (n=27) | 27.27/9.09/0.00 (n=55) **[FILE +1.82, 0/1, p=1.0000]** |
| | seats 4 | 100.00/34.04/19.15 (n=47) | 88.89/7.41/0.00 (n=27) | 27.27/9.09/0.00 (n=55) **[FILE +1.82, 0/1, p=1.0000]** |
| **python Lite** | default | 92.33/54.67/44.00 (n=300) | — (n=0) | — (n=0) |
| | seats 2 | 92.33/54.00/43.67 (n=300) | — (n=0) | — (n=0) |
| | seats 3 | 92.33/54.00/43.33 (n=300) | — (n=0) | — (n=0) |
| | seats 4 | 92.33/54.00/43.33 (n=300) | — (n=0) | — (n=0) |
| **python Verified** | default | 95.83/53.57/41.07 (n=336) | 81.63/22.45/8.16 (n=49) | 63.64/4.55/4.55 (n=22) |
| | seats 2 | 95.54/52.98/40.77 (n=336) | 81.63/22.45/10.20 (n=49) | 68.18/4.55/4.55 (n=22) **[FILE +4.54, 1/2, p=1.0000]** |
| | seats 3 | 95.24/52.08/41.07 (n=336) | 81.63/20.41/8.16 (n=49) | 68.18/4.55/4.55 (n=22) **[FILE +4.54, 1/2, p=1.0000]** |
| | seats 4 | 95.54/52.38/40.77 (n=336) | 81.63/20.41/8.16 (n=49) | 63.64/4.55/4.55 (n=22) **[FILE +0.00, 2/2, p=1.0000]** |

**Read the 3+ column: the mechanism does not do what it was built to do.**
It was designed for multi-gold-file instances, and in that stratum it is
inert almost everywhere — jsts, java, rust and c show FILE +0.00 with **zero
discordant pairs at every dose**, and the two slices that move (go +0.70/+1.40,
cpp +1.82) do so on 1–2 instances at p≥0.5. Nothing here is significant.

Meanwhile **go's one real gain is entirely in stratum 1**: FUNCTION 53.19 →
59.57 (+6.38) at 1 gold file, +1.03 at 2 gold, and **exactly 0.00 at 3+**.
The slice-level +3.04 that makes go look like a success is a single-gold-file
effect. A mechanism justified by "a patch that edits five files needs more
than one seat" delivers its entire measured benefit where there is only one
file to find.

## Paired significance (whole slice)

| slice | arm | McNemar FILE (def-only/arm-only, p) | FUNCTION | LINE | Wilcoxon frac | changed |
|---|---|---|---|---|---|---|
| jsts | seats 2 | 0/1, p=1.0000 | 1/0, p=1.0000 | 0/0, p=1.0000 | 3up/4down, p=1.0000 | 8/580 |
| jsts | seats 3 | 0/1, p=1.0000 | 1/0, p=1.0000 | 1/0, p=1.0000 | 5up/7down, p=0.4697 | 13/580 |
| jsts | seats 4 | 2/1, p=1.0000 | 2/0, p=0.5000 | 2/0, p=0.5000 | 6up/9down, p=0.3303 | 17/580 |
| java | seats 2 | 1/1, p=1.0000 | 0/1, p=1.0000 | 0/0, p=1.0000 | 4up/1down, p=0.1875 | 7/128 |
| java | seats 3 | 1/2, p=1.0000 | 0/1, p=1.0000 | 0/0, p=1.0000 | 8up/0down, p=0.0078 | 10/128 |
| java | seats 4 | 0/2, p=0.5000 | 0/1, p=1.0000 | 0/0, p=1.0000 | 7up/2down, p=0.0977 | 10/128 |
| go | seats 2 | 1/3, p=0.6250 | 2/15, p=0.0023 | 1/4, p=0.3750 | 27up/23down, p=0.0566 | 60/428 |
| go | seats 3 | 2/4, p=0.6875 | 5/11, p=0.2101 | 1/2, p=1.0000 | 30up/26down, p=0.2434 | 67/428 |
| go | seats 4 | 2/5, p=0.4531 | 6/9, p=0.6072 | 1/2, p=1.0000 | 27up/33down, p=0.8946 | 71/428 |
| rust | seats 2 | 0/1, p=1.0000 | 0/0, p=1.0000 | 0/0, p=1.0000 | 8up/5down, p=0.5417 | 14/239 |
| rust | seats 3 | 0/1, p=1.0000 | 1/0, p=1.0000 | 0/0, p=1.0000 | 8up/5down, p=0.8926 | 14/239 |
| rust | seats 4 | 0/1, p=1.0000 | 2/0, p=0.5000 | 0/0, p=1.0000 | 10up/7down, p=0.9265 | 19/239 |
| c | seats 2 | 0/0, p=1.0000 | 1/0, p=1.0000 | 0/0, p=1.0000 | 1up/2down, p=0.5000 | 3/128 |
| c | seats 3 | 1/0, p=1.0000 | 1/0, p=1.0000 | 0/0, p=1.0000 | 5up/5down, p=0.4922 | 11/128 |
| c | seats 4 | 2/0, p=0.5000 | 0/0, p=1.0000 | 0/0, p=1.0000 | 6up/5down, p=0.7002 | 13/128 |
| cpp | seats 2 | 0/0, p=1.0000 | 0/0, p=1.0000 | 0/0, p=1.0000 | 2up/0down, p=0.5000 | 2/129 |
| cpp | seats 3 | 0/1, p=1.0000 | 0/0, p=1.0000 | 0/0, p=1.0000 | 2up/1down, p=0.7500 | 4/129 |
| cpp | seats 4 | 0/1, p=1.0000 | 0/0, p=1.0000 | 0/0, p=1.0000 | 2up/1down, p=0.7500 | 4/129 |
| python Lite | seats 2 | 0/0, p=1.0000 | 2/0, p=0.5000 | 1/0, p=1.0000 | 0up/3down, p=0.2500 | 4/300 |
| python Lite | seats 3 | 0/0, p=1.0000 | 2/0, p=0.5000 | 2/0, p=0.5000 | 1up/4down, p=0.3125 | 6/300 |
| python Lite | seats 4 | 0/0, p=1.0000 | 2/0, p=0.5000 | 2/0, p=0.5000 | 1up/6down, p=0.0781 | 8/300 |
| python Verified | seats 2 | 2/2, p=1.0000 | 4/2, p=0.6875 | 2/2, p=1.0000 | 6up/9down, p=0.6387 | 18/407 |
| python Verified | seats 3 | 3/2, p=1.0000 | 7/1, p=0.0703 | 1/1, p=1.0000 | 5up/12down, p=0.1298 | 20/407 |
| python Verified | seats 4 | 4/3, p=1.0000 | 7/2, p=0.1797 | 2/1, p=1.0000 | 7up/14down, p=0.0763 | 25/407 |

go seats 2 FUNCTION is the round's only significant movement (2/15 discordant,
**p=0.0023**), and java seats 3 carries a significant fraction gain (8 up / 0
down, **p=0.0078**). No slice regresses significantly at any dose — the Python
losses are consistently signed but individually non-significant (Lite FUNCTION
2/0 at every dose, p=0.5; Verified seats 3 FUNCTION 7/1, p=0.0703). Consistent
direction across six independent Python arms is what makes them credible, not
any single p-value.

## Seat-fire anatomy

| slice | arm | instances fired | extra seats | mean where fired | seated file was gold | gold the default LACKED | bundles changed | files +/- (gold) | net gold |
|---|---|---|---|---|---|---|---|---|---|
| jsts | seats 2 | 283/579 (48.88%) | 461 | 1.629 | 9 (1.95%) | 2 | 141 (24.31%) | +245 (2) / -233 (1) | +1 |
| jsts | seats 3 | 283/579 (48.88%) | 800 | 2.827 | 14 (1.75%) | 3 | 176 (30.34%) | +443 (4) / -322 (2) | +2 |
| jsts | seats 4 | 283/579 (48.88%) | 1058 | 3.739 | 16 (1.51%) | 3 | 183 (31.55%) | +612 (4) / -353 (5) | -1 |
| java | seats 2 | 105/128 (82.03%) | 329 | 3.133 | 5 (1.52%) | 3 | 92 (71.88%) | +245 (3) / -226 (1) | +2 |
| java | seats 3 | 105/128 (82.03%) | 562 | 5.352 | 6 (1.07%) | 4 | 97 (75.78%) | +423 (4) / -304 (2) | +2 |
| java | seats 4 | 105/128 (82.03%) | 733 | 6.981 | 7 (0.95%) | 4 | 97 (75.78%) | +555 (4) / -325 (1) | +3 |
| go | seats 2 | 406/427 (95.08%) | 1234 | 3.039 | 16 (1.3%) | 9 | 371 (86.68%) | +979 (9) / -910 (18) | -9 |
| go | seats 3 | 406/427 (95.08%) | 2149 | 5.293 | 23 (1.07%) | 15 | 387 (90.42%) | +1749 (15) / -1123 (22) | -7 |
| go | seats 4 | 406/427 (95.08%) | 2778 | 6.842 | 29 (1.04%) | 18 | 388 (90.65%) | +2286 (19) / -1120 (25) | -6 |
| rust | seats 2 | 229/239 (95.82%) | 485 | 2.118 | 13 (2.68%) | 3 | 116 (48.54%) | +181 (4) / -174 (4) | +0 |
| rust | seats 3 | 229/239 (95.82%) | 785 | 3.428 | 27 (3.44%) | 6 | 120 (50.21%) | +303 (6) / -237 (7) | -1 |
| rust | seats 4 | 229/239 (95.82%) | 977 | 4.266 | 30 (3.07%) | 7 | 128 (53.56%) | +402 (7) / -261 (9) | -2 |
| c | seats 2 | 106/127 (83.46%) | 290 | 2.736 | 10 (3.45%) | 4 | 88 (68.75%) | +161 (4) / -159 (2) | +2 |
| c | seats 3 | 106/127 (83.46%) | 501 | 4.726 | 14 (2.79%) | 5 | 99 (77.34%) | +300 (6) / -227 (5) | +1 |
| c | seats 4 | 106/127 (83.46%) | 677 | 6.387 | 17 (2.51%) | 6 | 101 (78.91%) | +424 (7) / -254 (7) | +0 |
| cpp | seats 2 | 93/122 (76.23%) | 137 | 1.473 | 5 (3.65%) | 1 | 23 (17.83%) | +46 (1) / -45 (1) | +0 |
| cpp | seats 3 | 93/122 (76.23%) | 229 | 2.462 | 8 (3.49%) | 2 | 26 (20.16%) | +86 (2) / -79 (2) | +0 |
| cpp | seats 4 | 93/122 (76.23%) | 284 | 3.054 | 10 (3.52%) | 2 | 26 (20.16%) | +105 (2) / -77 (2) | +0 |
| python Lite | seats 2 | 270/300 (90.0%) | 613 | 2.27 | 1 (0.16%) | 0 | 232 (77.33%) | +437 (0) / -400 (0) | +0 |
| python Lite | seats 3 | 270/300 (90.0%) | 984 | 3.644 | 1 (0.1%) | 0 | 245 (81.67%) | +709 (0) / -573 (0) | +0 |
| python Lite | seats 4 | 270/300 (90.0%) | 1193 | 4.419 | 1 (0.08%) | 0 | 249 (83.0%) | +863 (0) / -623 (0) | +0 |
| python Verified | seats 2 | 380/407 (93.37%) | 897 | 2.361 | 3 (0.33%) | 2 | 342 (84.03%) | +660 (2) / -630 (2) | +0 |
| python Verified | seats 3 | 380/407 (93.37%) | 1435 | 3.776 | 3 (0.21%) | 2 | 356 (87.47%) | +1051 (2) / -859 (3) | -1 |
| python Verified | seats 4 | 380/407 (93.37%) | 1765 | 4.645 | 6 (0.34%) | 3 | 364 (89.43%) | +1295 (3) / -921 (4) | -1 |

This table is the round's most useful artifact, and it is unflattering.

* **Seats fire almost everywhere** — 48.9% of jsts instances, 82.0% of java,
  90.0% of Lite, 95.1% of go. This is not a rare targeted intervention.
* **Seated files are almost never gold**: 0.08%–3.65% precision. A bundle of
  ~30 files containing 1–6 gold is 3–20% gold, so **an extra seat is a worse
  bet than an average bundle slot**. The co-change evidence gate is not
  selecting for gold at all.
* **On Python Lite the mechanism is pure noise by construction**: 613 extra
  seats bought **1** gold file, and **0** gold the default lacked. Lite is
  300/300 single-gold-file — there is no sibling to find — yet seats fire on
  90% of instances and churn 77% of bundles.
* **Go's net gold is negative at every dose** (−9, −7, −6) despite the
  FUNCTION gain. The gain is therefore *not* from seating gold; it is a
  repacking side-effect, which is exactly what the stratum-1 localisation
  above independently says.

### Why: co-change count measures centrality, not relevance

Itemizing the losses names the culprit immediately. The files seats admit are
repo hubs — `pkg/cmd/root/root.go`, `pkg/cmd/auth/auth.go`,
`packages/svelte/src/compiler/index.js`, `sympy/printing/str.py` — files that
co-change with everything *because they are central*, not because they relate
to this fix. They displace real gold:

| instance | gold lost | seated instead (co-change) |
|---|---|---|
| cli__cli-7311 (n_gold=9) | `pkg/cmd/issue/list/list.go`, `pkg/cmd/pr/shared/params.go` | `pkg/cmd/root/root.go` (7), `pkg/cmd/pr/review/review.go` (6) |
| cli__cli-9037 (n_gold=5) | `pkg/cmd/pr/shared/editable_http.go`, `.../params.go` | `api/queries_issue.go` (10), `pkg/cmd/root/root.go` (8) |
| sympy__sympy-20916 (n_gold=1) | `sympy/printing/conventions.py` | `sympy/printing/str.py` (14) |
| sveltejs__svelte-12047 (n_gold=4) | `.../client/reactivity/sources.js` | `.../compiler/index.js` (4) |

"Strongest evidence first" is therefore "most central first". This is the
mirror image of E20's LexBoost finding (gold files are graph-central, so hub
*exclusion* taxes rescue targets): here hub *inclusion* taxes gold.

### The evidence cannot separate the two populations

If helpful and harmful seats differed in co-change strength, a threshold would
fix this. They do not — measured over every seat in each arm:

| slice (seats 2) | gold seats | median co-change | non-gold seats | median co-change | ranges overlap |
|---|---|---|---|---|---|
| go | 16 | **6.0** | 1218 | **6.0** | yes — gold [3,13] inside non-gold [2,89] |
| jsts | 9 | 3.0 | 452 | 4.0 | yes — gold [3,5] inside non-gold [2,37] |
| rust | 13 | 7.0 | 472 | 9.0 | yes — gold [3,43] inside non-gold [2,219] |
| ver | 3 | 7.0 | 894 | 5.0 | yes — gold [3,11] inside non-gold [2,38] |
| lite | 1 | 8.0 | 612 | 4.0 | yes — gold [8,8] inside non-gold [2,40] |

On go the two medians are **identical**. No threshold on the evidence the
mechanism already uses can separate a helpful seat from a harmful one.

## Changed-instance anatomy, by gold-file stratum

`better`/`worse` are by per-instance line fraction; `flips` counts all-or-nothing metric transitions (FILE/FUNCTION/LINE).

| slice | arm | changed | stratum 1 | stratum 2 | stratum 3+ | better | worse | FILE flips +/- | FUNC flips +/- | LINE flips +/- |
|---|---|---|---|---|---|---|---|---|---|---|
| jsts | seats 2 | 8 | 2 | 2 | 4 | 3 | 4 | +1/-0 | +0/-1 | +0/-0 |
| jsts | seats 3 | 13 | 3 | 3 | 7 | 5 | 7 | +1/-0 | +0/-1 | +0/-1 |
| jsts | seats 4 | 17 | 5 | 3 | 9 | 6 | 9 | +1/-2 | +0/-2 | +0/-2 |
| java | seats 2 | 7 | 2 | 2 | 3 | 4 | 1 | +1/-1 | +1/-0 | +0/-0 |
| java | seats 3 | 10 | 3 | 3 | 4 | 8 | 0 | +2/-1 | +1/-0 | +0/-0 |
| java | seats 4 | 10 | 2 | 4 | 4 | 7 | 2 | +2/-0 | +1/-0 | +0/-0 |
| go | seats 2 | 60 | 23 | 9 | 28 | 27 | 23 | +3/-1 | +15/-2 | +4/-1 |
| go | seats 3 | 67 | 21 | 13 | 33 | 30 | 26 | +4/-2 | +11/-5 | +2/-1 |
| go | seats 4 | 71 | 19 | 19 | 33 | 27 | 33 | +5/-2 | +9/-6 | +2/-1 |
| rust | seats 2 | 14 | 2 | 2 | 10 | 8 | 5 | +1/-0 | +0/-0 | +0/-0 |
| rust | seats 3 | 14 | 3 | 2 | 9 | 8 | 5 | +1/-0 | +0/-1 | +0/-0 |
| rust | seats 4 | 19 | 4 | 2 | 13 | 10 | 7 | +1/-0 | +0/-2 | +0/-0 |
| c | seats 2 | 3 | 1 | 0 | 2 | 1 | 2 | +0/-0 | +0/-1 | +0/-0 |
| c | seats 3 | 11 | 1 | 1 | 9 | 5 | 5 | +0/-1 | +0/-1 | +0/-0 |
| c | seats 4 | 13 | 1 | 3 | 9 | 6 | 5 | +0/-2 | +0/-0 | +0/-0 |
| cpp | seats 2 | 2 | 0 | 0 | 2 | 2 | 0 | +0/-0 | +0/-0 | +0/-0 |
| cpp | seats 3 | 4 | 0 | 0 | 4 | 2 | 1 | +1/-0 | +0/-0 | +0/-0 |
| cpp | seats 4 | 4 | 0 | 0 | 4 | 2 | 1 | +1/-0 | +0/-0 | +0/-0 |
| python Lite | seats 2 | 4 | 4 | 0 | 0 | 0 | 3 | +0/-0 | +0/-2 | +0/-1 |
| python Lite | seats 3 | 6 | 6 | 0 | 0 | 1 | 4 | +0/-0 | +0/-2 | +0/-2 |
| python Lite | seats 4 | 8 | 8 | 0 | 0 | 1 | 6 | +0/-0 | +0/-2 | +0/-2 |
| python Verified | seats 2 | 18 | 7 | 5 | 6 | 6 | 9 | +2/-2 | +2/-4 | +2/-2 |
| python Verified | seats 3 | 20 | 9 | 5 | 6 | 5 | 12 | +2/-3 | +1/-7 | +1/-1 |
| python Verified | seats 4 | 25 | 13 | 5 | 7 | 7 | 14 | +3/-4 | +2/-7 | +1/-2 |

Every Lite instance the mechanism touches, at every dose, is stratum 1 — the
population where a seat cannot possibly help. seats 2 changes 4 instances,
0 better / 3 worse by fraction.

### Python changed instances, itemized


**python Lite, seats 2** — 4 changed

| instance | gold files | stratum | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|---|
| pydata__xarray-4094 | 1 | 1 | = | 1->0 | 1->0 | 1.0000->0.0000 (-1.0000) |
| sympy__sympy-15609 | 1 | 1 | = | = | = | 0.5714->0.0000 (-0.5714) |
| sympy__sympy-12419 | 1 | 1 | = | = | = | 0.0714->0.0000 (-0.0714) |
| scikit-learn__scikit-learn-25638 | 1 | 1 | = | 1->0 | = | = (+0.0000) |

**python Lite, seats 3** — 6 changed

| instance | gold files | stratum | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|---|
| pydata__xarray-4094 | 1 | 1 | = | 1->0 | 1->0 | 1.0000->0.0000 (-1.0000) |
| sympy__sympy-15609 | 1 | 1 | = | = | = | 0.5714->0.0000 (-0.5714) |
| scikit-learn__scikit-learn-14894 | 1 | 1 | = | = | 1->0 | 1.0000->0.9091 (-0.0909) |
| sympy__sympy-12419 | 1 | 1 | = | = | = | 0.0714->0.0000 (-0.0714) |
| scikit-learn__scikit-learn-25638 | 1 | 1 | = | 1->0 | = | = (+0.0000) |
| sympy__sympy-23117 | 1 | 1 | = | = | = | 0.6667->0.8148 (+0.1481) |

**python Lite, seats 4** — 8 changed

| instance | gold files | stratum | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|---|
| pydata__xarray-4094 | 1 | 1 | = | 1->0 | 1->0 | 1.0000->0.0000 (-1.0000) |
| sympy__sympy-15609 | 1 | 1 | = | = | = | 0.5714->0.0000 (-0.5714) |
| django__django-16046 | 1 | 1 | = | = | = | 0.1667->0.0000 (-0.1667) |
| sphinx-doc__sphinx-8721 | 1 | 1 | = | = | = | 0.6667->0.5000 (-0.1667) |
| scikit-learn__scikit-learn-14894 | 1 | 1 | = | = | 1->0 | 1.0000->0.9091 (-0.0909) |
| sympy__sympy-12419 | 1 | 1 | = | = | = | 0.0714->0.0000 (-0.0714) |
| scikit-learn__scikit-learn-25638 | 1 | 1 | = | 1->0 | = | = (+0.0000) |
| sympy__sympy-23117 | 1 | 1 | = | = | = | 0.6667->0.8148 (+0.1481) |

**python Verified, seats 2** — 18 changed

| instance | gold files | stratum | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|---|
| astropy__astropy-13977 | 1 | 1 | = | 1->0 | 1->0 | 1.0000->0.0000 (-1.0000) |
| sympy__sympy-15809 | 1 | 1 | = | = | 1->0 | 1.0000->0.7500 (-0.2500) |
| django__django-16502 | 1 | 1 | = | 1->0 | = | 0.9091->0.7273 (-0.1818) |
| django__django-16938 | 2 | 2 | = | = | = | 0.5000->0.3571 (-0.1429) |
| pytest-dev__pytest-5840 | 2 | 2 | = | = | = | 0.3231->0.2154 (-0.1077) |
| django__django-11400 | 3 | 3+ | = | = | = | 0.7188->0.6250 (-0.0938) |
| matplotlib__matplotlib-25775 | 3 | 3+ | 0->1 | = | = | 0.6364->0.5455 (-0.0909) |
| sympy__sympy-20916 | 1 | 1 | 1->0 | 1->0 | = | 0.0714->0.0000 (-0.0714) |
| django__django-11138 | 4 | 3+ | = | = | = | 0.1122->0.1020 (-0.0102) |
| django__django-11734 | 3 | 3+ | 1->0 | = | = | = (+0.0000) |
| django__django-16631 | 2 | 2 | = | 1->0 | = | = (+0.0000) |
| sympy__sympy-14248 | 3 | 3+ | 0->1 | = | = | = (+0.0000) |
| django__django-13121 | 4 | 3+ | = | = | = | 0.4369->0.4660 (+0.0291) |
| sympy__sympy-12489 | 1 | 1 | = | = | = | 0.3288->0.3694 (+0.0405) |
| sympy__sympy-18763 | 1 | 1 | = | 0->1 | 0->1 | 0.8571->1.0000 (+0.1429) |
| django__django-11087 | 1 | 1 | = | = | = | 0.0000->0.1481 (+0.1481) |
| django__django-14376 | 2 | 2 | = | = | = | 0.0000->0.3913 (+0.3913) |
| sphinx-doc__sphinx-7462 | 2 | 2 | = | 0->1 | 0->1 | 0.3889->1.0000 (+0.6111) |

**python Verified, seats 3** — 20 changed

| instance | gold files | stratum | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|---|
| astropy__astropy-13977 | 1 | 1 | = | 1->0 | 1->0 | 1.0000->0.0000 (-1.0000) |
| django__django-13569 | 1 | 1 | 1->0 | 1->0 | = | 0.6667->0.0000 (-0.6667) |
| psf__requests-1724 | 1 | 1 | = | 1->0 | = | 0.4615->0.0000 (-0.4615) |
| django__django-14539 | 1 | 1 | = | 1->0 | = | 0.2500->0.0000 (-0.2500) |
| django__django-16502 | 1 | 1 | = | 1->0 | = | 0.9091->0.7273 (-0.1818) |
| django__django-16938 | 2 | 2 | = | = | = | 0.5000->0.3571 (-0.1429) |
| django__django-12155 | 2 | 2 | = | = | = | 0.8409->0.7273 (-0.1136) |
| pytest-dev__pytest-5840 | 2 | 2 | = | = | = | 0.3231->0.2154 (-0.1077) |
| django__django-11400 | 3 | 3+ | = | = | = | 0.7188->0.6250 (-0.0938) |
| matplotlib__matplotlib-25775 | 3 | 3+ | 0->1 | = | = | 0.6364->0.5455 (-0.0909) |
| sympy__sympy-20916 | 1 | 1 | 1->0 | 1->0 | = | 0.0714->0.0000 (-0.0714) |
| django__django-11138 | 4 | 3+ | = | = | = | 0.1122->0.1020 (-0.0102) |
| django__django-11734 | 3 | 3+ | 1->0 | = | = | = (+0.0000) |
| django__django-16631 | 2 | 2 | = | 1->0 | = | = (+0.0000) |
| sympy__sympy-14248 | 3 | 3+ | 0->1 | = | = | = (+0.0000) |
| django__django-13121 | 4 | 3+ | = | = | = | 0.4369->0.4660 (+0.0291) |
| sympy__sympy-12489 | 1 | 1 | = | = | = | 0.3288->0.3739 (+0.0450) |
| django__django-11087 | 1 | 1 | = | = | = | 0.0000->0.1481 (+0.1481) |
| django__django-14376 | 2 | 2 | = | = | = | 0.0000->0.3913 (+0.3913) |
| sympy__sympy-12096 | 1 | 1 | = | 0->1 | 0->1 | 0.0000->1.0000 (+1.0000) |

**python Verified, seats 4** — 25 changed

| instance | gold files | stratum | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|---|
| astropy__astropy-13977 | 1 | 1 | = | 1->0 | 1->0 | 1.0000->0.0000 (-1.0000) |
| django__django-13569 | 1 | 1 | 1->0 | 1->0 | = | 0.6667->0.0000 (-0.6667) |
| psf__requests-1724 | 1 | 1 | = | 1->0 | = | 0.4615->0.0000 (-0.4615) |
| django__django-14539 | 1 | 1 | = | 1->0 | = | 0.2500->0.0000 (-0.2500) |
| django__django-16502 | 1 | 1 | = | 1->0 | = | 0.9091->0.7273 (-0.1818) |
| pylint-dev__pylint-8898 | 3 | 3+ | 1->0 | = | = | 0.3750->0.2188 (-0.1562) |
| django__django-16938 | 2 | 2 | = | = | = | 0.5000->0.3571 (-0.1429) |
| django__django-12155 | 2 | 2 | = | = | = | 0.8409->0.7273 (-0.1136) |
| pytest-dev__pytest-5840 | 2 | 2 | = | = | = | 0.3231->0.2154 (-0.1077) |
| django__django-15278 | 1 | 1 | = | = | 1->0 | 1.0000->0.9000 (-0.1000) |
| django__django-11400 | 3 | 3+ | = | = | = | 0.7188->0.6250 (-0.0938) |
| matplotlib__matplotlib-25775 | 3 | 3+ | 0->1 | = | = | 0.6364->0.5455 (-0.0909) |
| sympy__sympy-20916 | 1 | 1 | 1->0 | 1->0 | = | 0.0714->0.0000 (-0.0714) |
| django__django-11138 | 4 | 3+ | = | = | = | 0.1122->0.1020 (-0.0102) |
| django__django-11734 | 3 | 3+ | 1->0 | = | = | = (+0.0000) |
| django__django-16631 | 2 | 2 | = | 1->0 | = | = (+0.0000) |
| sympy__sympy-14248 | 3 | 3+ | 0->1 | = | = | = (+0.0000) |
| sympy__sympy-18211 | 1 | 1 | 0->1 | = | = | = (+0.0000) |
| sympy__sympy-12489 | 1 | 1 | = | = | = | 0.3288->0.3468 (+0.0180) |
| sphinx-doc__sphinx-8035 | 1 | 1 | = | 0->1 | = | 0.4182->0.4364 (+0.0182) |
| django__django-13121 | 4 | 3+ | = | = | = | 0.4369->0.4660 (+0.0291) |
| django__django-11276 | 1 | 1 | = | = | = | 0.3158->0.3860 (+0.0702) |
| django__django-11087 | 1 | 1 | = | = | = | 0.0000->0.1481 (+0.1481) |
| django__django-14376 | 2 | 2 | = | = | = | 0.0000->0.3913 (+0.3913) |
| sympy__sympy-12096 | 1 | 1 | = | 0->1 | 0->1 | 0.0000->1.0000 (+1.0000) |

## Adoption bar

Bar: 3+ stratum improves materially on affected slices, Lite AND Verified non-negative on ALL FOUR metrics, no slice regresses significantly.

| arm | Python Lite 4-metric | Python Verified 4-metric | slices with 3+ FILE gain | slices with significant regression (p<0.05) | verdict |
|---|---|---|---|---|---|
| seats 2 | +0.00/-0.67/-0.33/-0.00548 **NEG** | +0.00/-0.49/+0.00/-0.00144 **NEG** | go +0.70, python Verified +4.54 | none | **FAIL** |
| seats 3 | +0.00/-0.67/-0.67/-0.00528 **NEG** | -0.24/-1.47/+0.00/-0.00387 **NEG** | go +1.40, cpp +1.82, python Verified +4.54 | none | **FAIL** |
| seats 4 | +0.00/-0.67/-0.67/-0.00640 **NEG** | -0.24/-1.22/-0.25/-0.00435 **NEG** | go +1.40, cpp +1.82 | none | **FAIL** |

## E27b — can the mechanism be conditioned into safety?

Two gates were built and smoke-tested against the instances E27 itself
identified: the 3 Lite instances seats **harmed** (all n_gold=1) and 5 Go
instances seats **helped**. No full arms were spent; a gate that cannot pass a
smoke test does not deserve one.

**Probe 1 — breadth gate** (`--cochange-seat-breadth N`: extra seats fire only
when N files carry ≥50% of the top lexical score). The premise is that a
concentrated query is a single-site fix, where a "sibling" cannot exist.

| instance | default | seats 2 | +breadth 2 | +breadth 4 | +breadth 8 |
|---|---|---|---|---|---|
| pydata__xarray-4094 | 1.000 | 0.000 | 0.000 | **1.000** | **1.000** |
| sympy__sympy-12419 | 0.071 | 0.000 | 0.000 | 0.000 | 0.000 |
| sympy__sympy-15609 | 0.571 | 0.000 | 0.000 | 0.000 | 0.000 |

Breadth 8 restores **1 of 3**. Both sympy harms survive every setting tested:
sympy is a large repo with diffuse lexical mass, so a single-site fix still
looks "broad" by this measure. The signal the gate needs is not in the query.

**Probe 2 — evidence gate** (`--cochange-seat-min 10`). It does suppress the
two sympy harms (xarray-4094 is *not* restored, 2 of 3) — and on the five Go
instances seats improved:

| instance | default | seats 2 | seats 2 + min 10 |
|---|---|---|---|
| cli__cli-2108 | 0.145 | 0.194 | 0.145 (reverted) |
| cli__cli-2250 | 0.625 | 0.854 | 0.625 (reverted) |
| cli__cli-2671 | 0.000 | 1.000 | 0.000 (reverted) |
| cli__cli-3924 | 0.184 | 0.306 | 0.184 (reverted) |
| cli__cli-4005 | 0.470 | 0.542 | 0.470 (reverted) |

**5 of 5 gains revert.** The harms and the gains go together, exactly as the
distribution table predicts: they are the same population.

Both gates are falsified at smoke cost. The distinguishing variable is the
gold patch's *shape* — single-site vs multi-site — which is not knowable at
query time from the corpus or the query.

## Verdict — NO-ADOPT as a default

The bar was pre-registered and is not moved now that go looks good:

* **Python fails the bar at every dose.** Lite is negative on FUNCTION
  (−0.67), LINE (−0.33/−0.67) and fraction at all three doses and never gains
  a metric; Verified is negative on FUNCTION at all three doses and loses FILE
  at seats 3 and 4. **No dose is safe** — seats 2 is the mildest and still
  goes 0 better / 3 worse on Lite.
* **The 3+ stratum, the whole point of the round, does not move.** Zero
  discordant pairs on four of six MSWE slices; nothing significant anywhere.
* **The one significant gain (go FUNCTION +3.04, p=0.0023) is stratum-1 and
  is not a retrieval gain at all** — go's net gold is −9.

Parity bought by damaging the strongest slice is not progress toward
"Python-level measurements everywhere". **Recommendation: `--cochange-seats`
ships default-OFF as a documented experimental option. No default was
flipped.**

## What survives

The mining that motivated the round is untouched and still correct: 62% of
missed multi-file gold is already in the candidate pool, and 72–89% of it
co-changed with gold the engine selected. That diagnosis stands. What E27
falsifies is the *lever*: co-change count cannot rank those siblings, because
it is a centrality measure, and centrality is what the packer already
over-weights.

This is the **third independent sighting** of the same pattern in this
campaign — WS3d (culprit fires shape-identical to win fires), WS1c (mention
signal absent at step-0 mining), now E27 (helpful and harmful seats drawn from
one distribution, medians identical). The recurring lesson: **when a proposed
fix is gated on the same evidence that produced the error, the gate cannot
separate the cases.**

Queued next, deliberately a different lever class rather than better seat
gating:

1. **Set-valued output** — let the engine return a small set of candidate
   bundles for multi-site patches instead of one ranked list.
2. **Budget reallocation between pass 1 and pass 2** — the packer's economy,
   not the candidate ranking, is what decides which gold survives.

Both attack the multi-file gap without asking co-change to carry a signal it
demonstrably does not carry.

## Anomalies

* **The E27b flag was not committed anywhere.** It existed only as
  uncommitted working-tree edits in the main checkout (main is at `c338745`,
  behind even the E27 implementation commit `6e28c76`). It is committed here
  as `94be546` so the probe evidence cites code that exists.
* **Raw JSON is not a valid identity test for this engine.** The `stats` block
  carries `index_ms`/`query_ms`, so the reference binary differs from *itself*
  between runs. Payload identity must exclude `stats`; an earlier byte-compare
  produced a false "DIFFER" on ponyc before this was found.
* **macOS bash 3.2 trips `set -u` on empty arrays.** The first launch lost
  every default arm instantly to `extra[@]: unbound variable`; seat flags are
  now carried as a word-split string. All arms were relaunched from clean.
* **`region_eval_full.py` had no `--instances` allowlist** (the two Python
  harnesses did). Added for the E27b probes.
* The scorer needs the full tree-sitter grammar dep set; without it the
  FUNCTION metric dies on `No module named tree_sitter`.
* Two background jobs were killed mid-run by external tooling; the detached
  `nohup` eval run survived both, and no arm was lost.
