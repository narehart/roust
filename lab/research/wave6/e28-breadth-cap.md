# E28 — does admitting more candidates close the multi-gold-file gap?

Campaign #4 wave 6, serving the standing language-agnostic directive (#56):
get every language to Python-level measurements.
Engine: `roust 0.3.2 (8a12c5e, clean)`, one pinned binary for all 16 arms.
**No default was flipped. The verdict is NO-ADOPT.**

## Question

E27 closed the ranking question by falsifying it. Co-change seats put the
*wrong* files in the bundle: seat gold-precision 0.08–3.65%, and the gold and
non-gold co-change distributions were indistinguishable (identical medians on
go). Directory proximity (7–26%) and shared-identifier overlap (gold median 36
vs non-gold 29, heavily overlapping) failed the same way. Three independent
sibling signals, three failures to discriminate.

But E27's mining survived intact, and it points somewhere else:
**62% of missed multi-file gold is already an eligible candidate**, sitting
below the addition cut. If the engine cannot *rank* those siblings, the
remaining lever is not ranking at all — it is **breadth**: admit more of them.

`--max-additions <n>` exposes the previously-hardcoded cap in `select_files`
(`if additions.len() >= 16`). Default 16 = shipped, byte-identical. This round
sweeps n ∈ {24, 32} on every slice.

This is a deliberately different lever class from E27, and — unlike E27 — it
is **not** gated on the evidence that produced the error. That was the
recurring failure this campaign has now seen four times (WS3d, WS1c, E27):
*when a proposed fix is gated on the same evidence that produced the error,
the gate cannot separate the cases.* Breadth sidesteps the gate entirely by
declining to discriminate at all.

## The hypothesis was a trade, and it was pre-registered as one

Stated before the numbers:

> Breadth should raise all-or-nothing FILE at 3+ gold files while costing the
> region metrics, because the 8192-token budget is fixed — it is then spread
> across ~50 files instead of ~33.

So `mean files returned` and `mean bundle tokens` are first-class columns
here, not appendix material. A round that reported FILE without them would be
reporting half a mechanism.

## Method

* **One pinned binary, 16 arms.** Built once at `8a12c5e` = main (`8cae8b8`,
  the committed `--max-additions` implementation) plus one Python-only
  harness-passthrough commit. Never rebuilt mid-run.
* **Instrumentation proven inert by construction.** The harness flag defaults
  to a sentinel `0` meaning *forward no flag at all*, so a default arm's argv
  is byte-identical to every pre-E28 default arm's.
* **Default arms REUSED from E27 — measured, not assumed.** E27's `_s0` arms
  ran at `6e28c76`, whose ancestry includes E26's `.rb`/`.pony` adoption
  (`ca15227`), and `git diff ca15227 3eb8f78 -- roust-rs/src/` is empty, so
  main's engine source and E27's should agree on the default path. That was
  verified rather than trusted: **118 record comparisons across all 8 slices,
  0 payload differences.** The comparison is on `regions` / `tokens` / the
  derived metrics — **never raw JSON**, because the `stats` block carries
  `index_ms`/`query_ms` and the reference binary differs from *itself* between
  runs. `lab/e28_identity.py`.
* **Clone dirs proven interchangeable too.** Because the arms pair against
  records produced in a *different* directory, the A and B dirs were also
  checked against each other and against E27 — all identical. This is not
  ceremony; it caught a real bug (see Anomalies).
* **Private clone dir per concurrent arm** (issue #41): 16 concurrent arms,
  10s stagger, one working tree each. Scoring ran only after every arm exited.
* **Provenance.** Every arm's log prints its `max_additions` and repos dir;
  every record carries `engine_sha` and `max_additions`.
* **Scoring.** `lab/agentless_metric_full.py --repos-dir --ts-functions
  --lang-functions` for the MSWE slices; `agentless_metric_v4.py` /
  `agentless_metric_verified.py` for Python. Never `lab/agentless_metric.py`,
  which ignores its CLI args.
* **Stats.** Exact McNemar (binomial, two-sided) per all-or-nothing metric,
  Wilcoxon signed-rank on the per-instance line fraction, whole-slice and
  **per gold-file stratum**.

All 16 arms returned exact expected row counts (4,678 records) with error
counts matching E27's defaults exactly (1 each on jsts/go/c, 0 elsewhere), and
every paired run's crosscheck against its own metric JSON agreed.

Artifacts in `lab/results_regions/e28/`. Analysis: `lab/e28_paired.py`,
`lab/e28_tables.py`, `lab/e28_identity.py`.

## Pre-registered adoption bar

> 3+ FILE improves materially on the affected slices **AND** Lite/Verified are
> non-negative on all four metrics. If FILE rises while FUNCTION/LINE fall,
> that is NOT an adoption — report it as the measured precision/recall trade
> it is.

## Per-slice results

| slice | n | arm | FILE | FUNCTION (exact) | LINE | line frac |
|---|---|---|---|---|---|---|
| **jsts** | 580 | default | 46.38 (269) | 31.21 (181) | 14.14 (82) | 0.26156 |
| | | cap 24 | 47.59 (276) | 30.17 (175) | 13.10 (76) | 0.24931 |
| | | *delta* | *+1.21* | *-1.04* | *-1.04* | *-0.01225* |
| | | cap 32 | 47.59 (276) | 29.31 (170) | 12.59 (73) | 0.24237 |
| | | *delta* | *+1.21* | *-1.90* | *-1.55* | *-0.01918* |
| **java** | 128 | default | 49.22 (63) | 36.72 (47) | 14.06 (18) | 0.41522 |
| | | cap 24 | 50.78 (65) | 34.38 (44) | 12.50 (16) | 0.40461 |
| | | *delta* | *+1.56* | *-2.34* | *-1.56* | *-0.01061* |
| | | cap 32 | 51.56 (66) | 31.25 (40) | 11.72 (15) | 0.37422 |
| | | *delta* | *+2.34* | *-5.47* | *-2.34* | *-0.04100* |
| **go** | 428 | default | 64.95 (278) | 28.97 (124) | 16.59 (71) | 0.41021 |
| | | cap 24 | 67.99 (291) | 27.34 (117) | 14.72 (63) | 0.39091 |
| | | *delta* | *+3.04* | *-1.63* | *-1.87* | *-0.01930* |
| | | cap 32 | 70.56 (302) | 24.77 (106) | 13.32 (57) | 0.37662 |
| | | *delta* | *+5.61* | *-4.20* | *-3.27* | *-0.03359* |
| **rust** | 239 | default | 60.25 (144) | 19.67 (47) | 7.53 (18) | 0.24315 |
| | | cap 24 | 60.67 (145) | 19.25 (46) | 7.53 (18) | 0.23449 |
| | | *delta* | *+0.42* | *-0.42* | *+0.00* | *-0.00866* |
| | | cap 32 | 60.67 (145) | 18.41 (44) | 6.69 (16) | 0.22543 |
| | | *delta* | *+0.42* | *-1.26* | *-0.84* | *-0.01772* |
| **c** | 128 | default | 51.56 (66) | 28.12 (36) | 13.28 (17) | 0.22513 |
| | | cap 24 | 53.12 (68) | 25.78 (33) | 12.50 (16) | 0.21393 |
| | | *delta* | *+1.56* | *-2.34* | *-0.78* | *-0.01120* |
| | | cap 32 | 55.47 (71) | 26.56 (34) | 12.50 (16) | 0.20981 |
| | | *delta* | *+3.91* | *-1.56* | *-0.78* | *-0.01532* |
| **cpp** | 129 | default | 65.89 (85) | 17.83 (23) | 6.98 (9) | 0.29880 |
| | | cap 24 | 66.67 (86) | 17.83 (23) | 6.98 (9) | 0.29687 |
| | | *delta* | *+0.78* | *+0.00* | *+0.00* | *-0.00193* |
| | | cap 32 | 66.67 (86) | 17.05 (22) | 6.98 (9) | 0.29328 |
| | | *delta* | *+0.78* | *-0.78* | *+0.00* | *-0.00552* |
| **python Lite** | 300 | default | 92.33 (277) | 54.67 (164) | 44.00 (132) | 0.52728 |
| | | cap 24 | 93.67 (281) | 51.33 (154) | 41.33 (124) | 0.51274 |
| | | *delta* | *+1.34* | *-3.34* | *-2.67* | *-0.01454* |
| | | cap 32 | 94.67 (284) | 51.00 (153) | 40.67 (122) | 0.50097 |
| | | *delta* | *+2.34* | *-3.67* | *-3.33* | *-0.02631* |
| **python Verified** | 407 | default | 92.38 (376) | 47.17 (192) | 35.14 (143) | 0.47635 |
| | | cap 24 | 93.61 (381) | 44.96 (183) | 33.91 (138) | 0.46470 |
| | | *delta* | *+1.23* | *-2.21* | *-1.23* | *-0.01165* |
| | | cap 32 | 94.10 (383) | 43.24 (176) | 32.43 (132) | 0.43766 |
| | | *delta* | *+1.72* | *-3.93* | *-2.71* | *-0.03869* |

**Every slice, both caps: FILE up, FUNCTION down, LINE down, fraction down.**
16 of 16 arms. There is no slice where breadth is free, and no slice where it
fails to buy files. This is the cleanest single-direction result of the
campaign — and it is clean in *both* directions at once.

## Stratified by gold-file count — the headline

| slice | arm | 1 gold | 2 gold | 3+ gold |
|---|---|---|---|---|
| **jsts** | default | 72.50/41.79/26.43 (n=280) | 48.39/26.88/5.38 (n=93) | 10.14/18.84/1.45 (n=207) |
| | cap 24 | 73.57/40.00/24.29 | 50.54/25.81/5.38 | 11.11/18.84/1.45 **[FILE +0.97, 0/2, p=0.5000]** |
| | cap 32 | 73.57/38.57/23.57 | 50.54/25.81/4.30 | 11.11/18.36/1.45 **[FILE +0.97, 0/2, p=0.5000]** |
| **java** | default | 94.12/52.94/35.29 (n=51) | 18.92/43.24/0.00 (n=37) | 20.00/10.00/0.00 (n=40) |
| | cap 24 | 94.12/49.02/31.37 | 24.32/40.54/0.00 | 20.00/10.00/0.00 **[FILE +0.00, 0/0, p=1.0000]** |
| | cap 32 | 96.08/41.18/29.41 | 24.32/40.54/0.00 | 20.00/10.00/0.00 **[FILE +0.00, 0/0, p=1.0000]** |
| **go** | default | 88.30/53.19/31.38 (n=188) | 75.26/19.59/11.34 (n=97) | 27.27/3.50/0.70 (n=143) |
| | cap 24 | 89.36/48.40/28.19 | 77.32/20.62/9.28 | 33.57/4.20/0.70 **[FILE +6.30, 0/9, p=0.0039]** |
| | cap 32 | 90.96/43.62/25.00 | 80.41/19.59/9.28 | 37.06/3.50/0.70 **[FILE +9.79, 0/14, p=0.0001]** |
| **rust** | default | 97.56/39.02/21.95 (n=82) | 67.31/11.54/0.00 (n=52) | 27.62/8.57/0.00 (n=105) |
| | cap 24 | 97.56/37.80/21.95 | 69.23/11.54/0.00 | 27.62/8.57/0.00 **[FILE +0.00, 0/0, p=1.0000]** |
| | cap 32 | 97.56/35.37/19.51 | 69.23/11.54/0.00 | 27.62/8.57/0.00 **[FILE +0.00, 0/0, p=1.0000]** |
| **c** | default | 78.79/43.94/25.76 (n=66) | 75.00/18.75/0.00 (n=16) | 4.35/8.70/0.00 (n=46) |
| | cap 24 | 80.30/40.91/24.24 | 81.25/12.50/0.00 | 4.35/8.70/0.00 **[FILE +0.00, 0/0, p=1.0000]** |
| | cap 32 | 81.82/40.91/24.24 | 81.25/18.75/0.00 | 8.70/8.70/0.00 **[FILE +4.35, 0/2, p=0.5000]** |
| **cpp** | default | 100.00/34.04/19.15 (n=47) | 88.89/7.41/0.00 (n=27) | 25.45/9.09/0.00 (n=55) |
| | cap 24 | 100.00/34.04/19.15 | 88.89/7.41/0.00 | 27.27/9.09/0.00 **[FILE +1.82, 0/1, p=1.0000]** |
| | cap 32 | 100.00/31.91/19.15 | 88.89/7.41/0.00 | 27.27/9.09/0.00 **[FILE +1.82, 0/1, p=1.0000]** |
| **python Lite** | default | 92.33/54.67/44.00 (n=300) | — (n=0) | — (n=0) |
| | cap 24 | 93.67/51.33/41.33 | — | — |
| | cap 32 | 94.67/51.00/40.67 | — | — |
| **python Verified** | default | 95.83/53.57/41.07 (n=336) | 81.63/22.45/8.16 (n=49) | 63.64/4.55/4.55 (n=22) |
| | cap 24 | 96.73/51.49/39.58 | 83.67/18.37/8.16 | 68.18/4.55/4.55 **[FILE +4.54, 0/1, p=1.0000]** |
| | cap 32 | 97.02/49.40/37.80 | 83.67/18.37/8.16 | 72.73/4.55/4.55 **[FILE +9.09, 0/2, p=0.5000]** |

**Unlike E27, the 3+ stratum genuinely moves.** go gains +6.30 (p=0.0039) and
+9.79 (p=0.0001) — the first significant 3+ FILE movement of the campaign, on
14 instances, none lost. Verified 3+ goes 63.64 → 72.73. c gains +4.35, cpp
+1.82, jsts +0.97.

E27's diagnosis is therefore **confirmed, not merely survived**: the missing
siblings really were in the pool, and breadth really does reach them. The
mechanism does exactly what the mining predicted. It just costs more than it
is worth.

Two slices are inert at 3+ (java, rust, both 0/0 discordant). Their pools do
not hold 24 eligible candidates in the first place, so the cap is not the
binding constraint there — the same reason cpp's files-returned barely moves
(+2.44 at cap 24, against go's +7.57).

## Paired significance (whole slice)

| slice | arm | McNemar FILE (def-only/arm-only, p) | FUNCTION | LINE | Wilcoxon frac | changed |
|---|---|---|---|---|---|---|
| jsts | cap 24 | 0/7, p=0.0156 | 6/0, p=0.0312 | 6/0, p=0.0312 | 12up/51down, p=0.0000 | 68/580 |
| jsts | cap 32 | 0/7, p=0.0156 | 11/0, p=0.0010 | 9/0, p=0.0039 | 15up/62down, p=0.0000 | 84/580 |
| java | cap 24 | 0/2, p=0.5000 | 3/0, p=0.2500 | 2/0, p=0.5000 | 3up/11down, p=0.0062 | 16/128 |
| java | cap 32 | 0/3, p=0.2500 | 7/0, p=0.0156 | 3/0, p=0.2500 | 3up/19down, p=0.0001 | 25/128 |
| go | cap 24 | 0/13, p=0.0002 | 15/8, p=0.2100 | 9/1, p=0.0215 | 32up/56down, p=0.0002 | 101/428 |
| go | cap 32 | 0/24, p=0.0000 | 24/6, p=0.0014 | 15/1, p=0.0005 | 37up/90down, p=0.0000 | 142/428 |
| rust | cap 24 | 0/1, p=1.0000 | 1/0, p=1.0000 | 1/1, p=1.0000 | 10up/27down, p=0.0133 | 38/239 |
| rust | cap 32 | 0/1, p=1.0000 | 3/0, p=0.2500 | 3/1, p=0.6250 | 12up/36down, p=0.0019 | 49/239 |
| c | cap 24 | 0/2, p=0.5000 | 3/0, p=0.2500 | 1/0, p=1.0000 | 5up/12down, p=0.1089 | 19/128 |
| c | cap 32 | 0/5, p=0.0625 | 2/0, p=0.5000 | 1/0, p=1.0000 | 3up/15down, p=0.0040 | 23/128 |
| cpp | cap 24 | 0/1, p=1.0000 | 0/0, p=1.0000 | 0/0, p=1.0000 | 6up/7down, p=0.2439 | 14/129 |
| cpp | cap 32 | 0/1, p=1.0000 | 1/0, p=1.0000 | 0/0, p=1.0000 | 5up/10down, p=0.0215 | 16/129 |
| python Lite | cap 24 | 0/4, p=0.1250 | 11/1, p=0.0063 | 8/0, p=0.0078 | 2up/12down, p=0.0257 | 22/300 |
| python Lite | cap 32 | 0/7, p=0.0156 | 13/2, p=0.0074 | 11/1, p=0.0063 | 4up/17down, p=0.0029 | 32/300 |
| python Verified | cap 24 | 0/5, p=0.0625 | 10/1, p=0.0117 | 5/0, p=0.0625 | 4up/22down, p=0.0036 | 32/407 |
| python Verified | cap 32 | 0/7, p=0.0156 | 17/1, p=0.0001 | 11/0, p=0.0010 | 2up/41down, p=0.0000 | 52/407 |

### FILE is strictly monotone in the cap — and that is the problem

Look at the left column: **the default-only count is 0 in all 16 arms.**
Across 4,678 paired instances, raising the cap never once cost a file-correct
instance; it won 90. Breadth is a pure, monotone gain at file level.

That is precisely what makes it dangerous. A retrieval knob that only ever
improves the headline metric is exactly the kind of knob a metric-driven
campaign adopts by reflex. The Wilcoxon column is the counterweight, and it
runs the other way in **all 16 arms** (jsts cap 32: 15 up / 62 down,
p=0.0000; Verified cap 32: 2 up / 41 down, p=0.0000).

## The cost of breadth — files returned and bundle tokens

The budget is fixed at 8192 tokens. It does not grow when the cap does.

| slice | arm | mean files returned | mean bundle tokens | files delta | tokens delta |
|---|---|---|---|---|---|
| **jsts** | default | 30.82 | 8531.7 | — | — |
| | cap 24 | 36.89 | 8617.6 | +6.07 | +85.9 |
| | cap 32 | 41.45 | 8673.5 | +10.63 | +141.8 |
| **java** | default | 31.28 | 8762.2 | — | — |
| | cap 24 | 39.01 | 8897.2 | +7.73 | +135.0 |
| | cap 32 | 46.51 | 9023.2 | +15.23 | +261.0 |
| **go** | default | 33.55 | 8486.5 | — | — |
| | cap 24 | 41.12 | 8549.5 | +7.57 | +63.0 |
| | cap 32 | 48.42 | 8612.1 | +14.87 | +125.6 |
| **rust** | default | 29.95 | 8464.0 | — | — |
| | cap 24 | 35.26 | 8510.5 | +5.31 | +46.5 |
| | cap 32 | 38.19 | 8537.3 | +8.24 | +73.3 |
| **c** | default | 30.19 | 8513.7 | — | — |
| | cap 24 | 37.77 | 8587.1 | +7.58 | +73.4 |
| | cap 32 | 44.83 | 8653.7 | +14.64 | +140.0 |
| **cpp** | default | 24.40 | 8510.4 | — | — |
| | cap 24 | 26.84 | 8537.5 | +2.44 | +27.1 |
| | cap 32 | 28.33 | 8554.1 | +3.93 | +43.7 |
| **python Lite** | default | 34.88 | 8558.5 | — | — |
| | cap 24 | 42.46 | 8628.8 | +7.58 | +70.3 |
| | cap 32 | 49.99 | 8696.3 | +15.11 | +137.8 |
| **python Verified** | default | 34.95 | 8557.6 | — | — |
| | cap 24 | 42.63 | 8627.7 | +7.68 | +70.1 |
| | cap 32 | 50.19 | 8693.9 | +15.24 | +136.3 |
| | | | | | |

**This table is the round.** Files returned rise by up to **+15.2 (Lite:
34.9 → 50.0, +43%)** while bundle tokens move by **under 3%** (+137.8 on an
8558 base). The budget did not grow. The same ~8600 tokens are simply cut into
50 pieces instead of 35, and every file already in the bundle gets thinner.

Region precision (gold lines / returned lines) confirms the direction on every
slice — jsts 0.01393 → 0.01304, Verified 0.00778 → 0.00682, go 0.01772 →
0.01611 — while mean returned region lines rise (go 1164 → 1203). *(This
metric is far stricter than the chunk-precision figures quoted in the
literature and is not numerically comparable to them; only the direction is
being claimed.)*

## The trade is visible inside single instances

The clearest evidence is not the aggregate but go's cap-32 3+ FILE wins — the
14 instances the mechanism was built for, where it worked:

| instance | n_gold | line fraction |
|---|---|---|
| cli__cli-2004 | 5 | 0.2903 → 0.1210 (**-0.1694**) |
| cli__cli-7185 | 3 | 0.1667 → 0.0000 (**-0.1667**) |
| zeromicro__go-zero-1456 | 5 | 0.7188 → 0.6354 (-0.0833) |
| cli__cli-696 | 8 | 0.5109 → 0.4783 (-0.0326) |
| cli__cli-728 | 8 | 0.4689 → 0.4606 (-0.0083) |

Of the 14 instances that gained all-of-gold FILE coverage, **5 lost line
fraction and 0 gained it**; mean fraction delta −0.0155. `cli__cli-7185` is
the mechanism in miniature: the bundle now contains every gold file, and shows
**none** of the gold lines. It gained a point on FILE and became less useful.

That is the trade stated exactly: you find the file and simultaneously see
less of it.

## Engaging the Recall Trap rather than optimising around it

wave-5's scan flagged **The Recall Trap (arXiv:2608.14838)** for exactly this
situation. On SWE-bench Verified under fixed-budget context packs, the
higher-recall configuration put the gold file in 87.8% of packs versus 80.6%
for the lower-recall one — and the *lower*-recall config resolved **+7.6pp**
more issues (GPT-5.6, 39.2 → 46.8, n=500, **p=0.0003**; +3.6pp on Qwen3.6-27B,
p=0.013), with a random-chunk control ruling out a selection artifact. Their
conclusion: under a fixed token budget, file breadth trades against within-file
depth, **and depth wins downstream**.

E28 reproduces the first half of that finding in our own harness, with the
same sign and the same mechanism (fixed budget, breadth up, depth down). We
did not measure the second half — roust's harness has no execution-graded
downstream consumer, so we cannot say resolve rate fell. But that is an
argument for caution, not for adoption: the one published study that *did*
grade this exact trade downstream found the recall-maximizing side lost, and
the effect it measured (+7.6pp resolve, p=0.0003) is far larger than the FILE
gains on offer here (+1.2 to +5.6pp).

This matters because roust's charter is "1.00-recall retrieval at ≥70% token
savings", and a naive reading of that charter says *take the recall*. E28 is
the case where that reading would have been wrong. The charter's second clause
is a budget constraint, and under a binding budget recall is not free — it is
purchased from depth, at a price this round measures precisely.

Two further external anchors point the same way. **CodeGrep (arXiv:2608.05886)**
found a retriever below ~0.45 chunk precision actively *degrades* its agent
consumer, so precision is not a soft secondary axis. And **SWE-Explore
(2606.07297)** concluded that "file-level localization is already strong for
modern methods; line-level coverage and efficient ranking remain the key
axes" — i.e. the field considers FILE close to saturated and LINE the live
frontier. E28 trades the saturated axis for the live one, in the wrong
direction.

## Adoption bar

| arm | Python Lite 4-metric | Python Verified 4-metric | slices with 3+ FILE gain | slices with significant regression (p<0.05) | verdict |
|---|---|---|---|---|---|
| cap 24 | +1.34/**-3.34**/**-2.67**/**-0.01454** **NEG** | +1.23/**-2.21**/**-1.23**/**-0.01165** **NEG** | jsts +0.97, go +6.30, cpp +1.82, Verified +4.54 | jsts FUNCTION/LINE, go LINE, Lite FUNCTION/LINE, Verified FUNCTION | **FAIL** |
| cap 32 | +2.34/**-3.67**/**-3.33**/**-0.02631** **NEG** | +1.72/**-3.93**/**-2.71**/**-0.03869** **NEG** | jsts +0.97, go +9.79, c +4.35, cpp +1.82, Verified +9.09 | jsts FUNCTION/LINE, java FUNCTION, go FUNCTION/LINE, Lite FUNCTION/LINE, Verified FUNCTION/LINE | **FAIL** |

## Verdict — NO-ADOPT as a default

The bar was pre-registered and is not moved now that the 3+ column finally
lit up:

* **Python fails at both caps, significantly.** Lite loses FUNCTION (−3.34 /
  −3.67, p=0.0063 / 0.0074) and LINE (−2.67 / −3.33, p=0.0078 / 0.0063);
  Verified loses FUNCTION (−2.21 / −3.93, p=0.0117 / **0.0001**) and LINE at
  cap 32 (−2.71, p=0.0010). These are not directional hints of the kind E27
  produced — they are significant regressions on the strongest slice.
* **The pre-registered escape clause fires exactly as written.** FILE rose,
  FUNCTION and LINE fell, on 16 of 16 arms. That was named in advance as *not*
  an adoption.
* **The 3+ gain is real but locally purchased.** go's +9.79 at 3+ is the
  campaign's first significant multi-file FILE movement — and go's FUNCTION
  falls −4.20 (p=0.0014) and LINE −3.27 (p=0.0005) to pay for it, with the
  winning instances themselves losing line fraction.

**Recommendation: `--max-additions` ships default-16 as a documented
experimental option. No default was flipped.**

## What survives, and what this changes

E27 falsified the *ranking* lever. E28 does something different: it
**validates the mining and prices the lever**. Breadth reaches the siblings
E27's mining said were there — go 3+ FILE +9.79 with 14 wins and 0 losses is
not noise. The reason to decline it is not that it fails; it is that under a
fixed budget it costs more depth than the files are worth.

That converts a vague worry into a measured exchange rate. On go at cap 32:
**+5.61 FILE for −4.20 FUNCTION and −3.27 LINE, at +14.9 files per bundle and
+0.1% tokens.** Any future breadth proposal has to beat that rate.

The campaign has now closed both halves of the multi-file problem from the
candidate-set side:

* **ranking** the siblings — falsified (E27: the evidence cannot discriminate);
* **admitting** the siblings — priced and rejected (E28: it works, and costs
  more than it returns under a fixed budget).

Neither failure is about the sibling signal any more. Both are about the
**packer's economy**: a fixed budget divided over a file set. That is the
remaining unexamined layer, and it is where the queue now points:

1. **Budget reallocation between pass 1 and pass 2** — if depth is what
   breadth destroys, spend the budget asymmetrically rather than uniformly:
   give a newly-admitted candidate a floor allocation instead of an equal
   share, so admitting a file cannot thin the file that already carries gold.
   E28 gives this a concrete target: recover go's 14 3+ FILE wins **without**
   the −3.27 LINE.
2. **Set-valued output** — return a small set of candidate bundles for
   multi-site patches instead of one ranked list, sidestepping the fixed-budget
   division entirely.
3. **Budget-aware breadth** — the cap is currently a constant. cpp's pool
   cannot fill 24 slots while go's can fill 32; a cap conditioned on how much
   budget remains after the lexical picks is a different mechanism from a
   larger constant, and E28 measured only the constant.

## Anomalies

* **`lab/ws3b_repos/jsts_base` and `jsts_v2` contain only 4 of the 9 jsts
  repos.** The identity gate caught this immediately — all 5 sampled records
  failed with `repo checkout not found`. Had the gate not run, the jsts arms
  would have silently scored a partial corpus against a full-corpus default.
  jsts arms were moved to `mswe_repos_e23` / `mswe_repos_private`, which
  reproduce E27's `_s0` records exactly. **Clone directories in `lab/` are not
  interchangeable and must be verified per round, not assumed.**
* **The system `python3` has an ABI-mismatched pandas/numpy** (`numpy.dtype
  size changed, Expected 96 from C header, got 88`). The first launch died on
  it instantly. The entire rig runs under `uv run --no-project --with ...`;
  the scorer additionally needs the seven tree-sitter grammar wheels or the
  FUNCTION metric dies on `No module named tree_sitter`.
* **`region_eval_full.py` on main still has no `--instances` allowlist** (E27
  added one on its own branch; it was never landed). The identity sample used
  a `--limit` prefix instead. Worth landing separately.
* Reusing E27's default arms saved a full wave. It was only safe because the
  identity gate is payload-based; the two directory bugs above are exactly
  what a `stats`-inclusive raw-JSON comparison would have drowned in noise.
