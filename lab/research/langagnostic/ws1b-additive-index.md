# WS1b — additive-only universal indexing: safe and proven, but the ceiling is a RANKING problem

*Language-agnostic campaign (issue #56), workstream 1b. Branch
`ws1b-additive-index` off `ws1-universal-index` (72ff41c); engine commits
`269882f` (additive) + `0e7e362` (reserve variant); merge-base reference
main `0d8113e`. Gate runs 2026-08-25.*

## Hypothesis (from WS1's revival precondition 1)

WS1 proved indexing recovers all 499 out-of-allowlist gold files but naive
re-ranking loses 101 MSWE bundles to boilerplate displacement (−15.2 FILE
points). WS1b lifts the E12b guard pattern to file admission:
`--index-all-additive` runs the ENTIRE unflagged pipeline first — core
selection byte-identical by construction — then admits newcomer files
(content-sniffed text beyond the extension allowlist) strictly into
leftover budget, appended after the core. Losses become structurally
impossible; the +13 WS1 gains were hoped to survive.

## What shipped (flag-gated, default OFF, byte-identical)

**Engine** (`roust-rs/src/main.rs`, `cache.rs`):
- `--index-all-additive` (conflicts with `--index-all`): loads BOTH corpora
  — the default corpus for the untouched core pipeline (its own
  df/n_docs/avg_len; WS1 showed superset statistics perturb every core
  score, so a filter on one flagged corpus cannot work) and the
  `--index-all` superset corpus for newcomer ranking. Newcomer candidates =
  the superset corpus's own full selection (`select_files`) filtered to
  non-allowlisted files, admitted greedily in that rank order: each packed
  alone (`pack_regions`) against the remaining budget, accepted only if the
  concatenated bundle stays within `--budget`, skipped otherwise. Core
  files/spans/bundle are append-only; admission stops at `--k` or exhausted
  budget; zero-match queries skip admission (exit contract unchanged).
- `--newcomer-reserve FRAC` (requires additive; built after leftover-only
  measured inert, per the pre-registered plan): core packs against
  `budget*(1-frac)` so a reserve slice survives for newcomers. The core
  FILE SET is unchanged (pass 1 seats every selected file unconditionally);
  core SPANS may shrink — that is the measured trade.
- Cache: the superset corpus now lives in its OWN file
  (`.roust/rust-index-a1.bin`) in addition to its `:a1` key — an additive
  run loads both corpora without evicting either cache, and flagged runs
  can never clobber the default cache file. Cross-flag test strengthened
  accordingly (`incremental.rs`: switch-back is now a clean hit of the
  untouched default cache, not a rebuild).
- 5 new integration tests (`roust-rs/tests/additive.rs`): superset +
  core-spans-unchanged + bundle-prefix invariant, no-leftover identity,
  flag conflict, reserve file-set preservation, reserve-requires-additive.
  82 total pass.

**Harness**: `--index-all-additive` + `--newcomer-reserve` passthrough in
`parity/region_eval2.py` and `parity/region_eval_full.py`;
`index_all_additive_stats` per-row capture in both plus
`parity/region_eval_verified.py`. Gate scripts `lab/ws1b_identity_gate.py`
(identity + flag-on invariant), `lab/ws1b_smoke.py` (WS1's 10 ceiling
instances, additive).

## Gate 1 — identity + invariant: PASS

- **Gate A** (defaults byte-identity vs main `0d8113e` ref binary): 18
  instances (12 Lite / 6 Python repos + 6 MSWE / 3 JS repos), two runs per
  binary per instance, md5 over the retrieval payload: 18/18 identical, 0
  determinism flakes.
- **Gate B** (flag-on invariant, same 18): 18/18 OK — defaults file list is
  a byte-identical prefix of the flagged list, core spans unchanged,
  flagged bundle starts with the defaults bundle, newcomers fit the budget
  or the output equals defaults exactly. Anatomy preview: leftover was 0 on
  15/18 instances; one admission total (express-3695: +1 newcomer, 127 of
  130 leftover tokens).

## Gate 2 — smoke (WS1's 10 ceiling instances): invariant holds, recovery ~0

0/10 invariant violations. **0/13 out-of-allowlist gold files returned**
(WS1's full re-ranking returned 10/13 by displacing the core). Cause is
structural: cores pack 8.1–8.6k tokens of the 8192 budget (pass-1 seats
unconditionally and overshoots), leftover was 0 on 8/10 instances; the two
admissions that fit (~50–200 leftover tokens) were `CONTRIBUTING.md` and
`themes/README.md` — boilerplate, not gold. This is the pre-registered
"leftover-only shows zero gains" branch → the reserve variant was built.

## Baseline reproductions: exact

- MSWE-580 baseline: **46.38 / 31.03 / 13.28 / .2582** (269/580, 180, 77;
  same single `iamkun__dayjs-857` error) — equals the E23/WS1 reference on
  every digit.
- Lite-300 baseline: **92.33 / 54.67 / 43.67 / .52544** (277, 164, 131) —
  equals WS1's restated post-#55 reference on every digit.

## Arm 1 — leftover-only additive: SAFE, +1/−0, INERT

| bench | metric | baseline | `--index-all-additive` | paired |
|---|---|---|---|---|
| MSWE-580 | FILE (all-gold superset) | 46.38 (269/580) | **46.55 (270/580)** | **+1/−0** (losses structurally impossible; 0 observed) |
| MSWE-580 | FUNCTION (exact) | 31.03 (180) | 31.03 (180) | 0 flips |
| MSWE-580 | LINE / fraction | 13.28 (77) / .2582 | 13.28 (77) / .2582 | fraction float-exact equal; 0 flips |
| Lite-300 | FILE | 92.33 (277/300) | **92.33 (277/300)** | +0/−0, bit-identical rows |
| Lite-300 | FUNCTION | 54.67 (164) | 54.67 (164) | 0 flips |
| Lite-300 | LINE / fraction | 43.67 (131) / .52544 | 43.67 (131) / .52544 | 0 flips |

**Anatomy**: leftover budget existed on only **32/579** MSWE instances and
**0/300** Lite instances — the default packer exhausts (usually overshoots)
the 8192 budget essentially always, so the admission channel is starved by
construction. 28 MSWE instances admitted 60 newcomers (13.2k tokens
total): README.md ×9, CONTRIBUTING.md ×8, PULL_REQUEST_TEMPLATE.md ×8,
CHANGELOG.md ×7 — WS1's displacer class, now harmless but also not gold.
1/499 gold newcomers returned; blocked-135 recovery = 1
(`anuraghazra__github-readme-stats-88`, gold `readme.md`). Per-row
invariant verified across all 880 paired rows: 0 core-span changes, file
sets always supersets. Cost: one extra (superset) index build/load per
query (`additive_ms` ~0.3–8s cold on gate repos, cached thereafter in the
separate `-a1` cache file).

## Arm 2 — `--newcomer-reserve 0.10`: REJECT (Lite dilution gate fails on regions)

| bench | metric | baseline | reserve 0.10 | paired |
|---|---|---|---|---|
| MSWE-580 | FILE | 46.38 (269/580) | **47.59 (276/580)** | **+7/−0**, sign-test p=.016 |
| MSWE-580 | FUNCTION | 31.03 (180) | 30.34 (176) | +1/−5 |
| MSWE-580 | LINE / fraction | 13.28 (77) / .2582 | 12.59 (73) / .24532 | fraction +13/−59 |
| Lite-300 | FILE | 92.33 (277/300) | **92.33 (277/300)** | +0/−0 (identical correct set) |
| Lite-300 | FUNCTION | 54.67 (164) | **51.67 (155)** | net −9 |
| Lite-300 | LINE / fraction | 43.67 (131) / .52544 | **41.67 (125)** / .50607 | fraction +1/−9 |

**Anatomy**: the FILE-set guard held everywhere (0 superset violations on
both benches — FILE cannot regress, and didn't). But the ~819-token
reserve is consumed by boilerplate almost universally: MSWE admitted 1492
newcomers on 572/579 instances (PULL_REQUEST_TEMPLATE.md ×356,
bug_report.yml ×199, CONTRIBUTING.md ×141, FUNDING.yml ×139…); Lite
admitted 229 on 115/300 (CHANGES ×16, CONTRIBUTING.rst ×16, README.rst
×12, sphinx locale `.po`s…). All 7 MSWE FILE gains are blocked-135
recoveries (5.2% of the 135) — 6 of 7 are `anuraghazra__github-readme-stats`
instances whose gold IS `readme.md`, i.e. the one repo family where
boilerplate-first ranking coincides with gold. 9/499 gold newcomers
returned. Meanwhile the shaved core spans cost real region mass on BOTH
benches (MSWE fraction −1.29pt, Lite FUNCTION −3.0pt) — paying ~10% of
every core bundle to buy PR templates.

## Verdicts

1. **Leftover-only `--index-all-additive`: gate-positive but inert — keep
   flag-gated OFF, do not flip defaults.** It meets the letter of the
   success criterion (MSWE FILE strictly above baseline at +1/−0 with the
   Lite invariant holding exactly) and its safety story is now proven at
   scale (880 paired rows, 0 violations; losses structurally impossible).
   But +1 instance against a 135-instance ceiling is noise-level benefit
   for a 2× index-cost flag. Its real value is as **groundwork**: the
   guard machinery (two-corpus loading, split cache, append-only
   admission, invariant tests) is exactly the safe substrate any future
   newcomer-ranking fix will run on — adopt-the-scaffolding,
   not-the-default.
2. **`--newcomer-reserve 0.10`: REJECT.** The Lite dilution gate is
   decisive: FILE held only because the guard makes losses impossible,
   while FUNCTION/LINE/fraction all regressed on both benches to fund
   boilerplate admissions. Do not pursue larger reserves; the bottleneck
   is not headroom.

## The ceiling problem is now isolated: NEWCOMER RANKING

Three experiments triangulate it. WS1 (full re-ranking): gold newcomers
indexable but drowned by boilerplate — and the boilerplate also destroyed
the core. WS1b leftover-only: core protected, but no budget for newcomers
at all. WS1b reserve: budget manufactured, core protected — and the
admission queue STILL spends it on PR templates (9/499 gold returned).
Indexing is solved; admission budget is solvable; **the newcomer scoring
function itself is the entire remaining problem**. The admitted-basename
tables above are effectively a training set for it.

**WS1c candidates (ranked)**:
1. **Issue-mention promotion for newcomers** (new, case-mined from this
   run): gold newcomers are frequently NAMED in the issue text
   (`readme.md` in every github-readme-stats gain; config filenames in
   WS1's `.json` gold class), while PULL_REQUEST_TEMPLATE.md never is. An
   E11b-style path/basename-mention boost applied to the newcomer queue —
   or hard-gating admission on path-mention — attacks exactly the
   boilerplate-first ordering, costs nothing on Python (no newcomers
   admitted at leftover=0), and composes with the additive guard.
2. **Boilerplate-class down-weight inside the newcomer queue** (WS1
   precondition 2, refined): a uniform non-code `impl_prior` multiplier is
   a no-op under additive (it cannot reorder newcomers among themselves) —
   the down-weight must discriminate WITHIN the class:
   community-health/CI-template paths (`.github/`, `CONTRIBUTING*`,
   `FUNDING*`, `*_TEMPLATE*`, changelogs) vs everything else.
3. **Docs-field promotion** (WS1 precondition 3, untouched): route
   `.md`/`.rst` docs hits into FILE output via the already-indexed docs
   field — attacks the 158/499 `.md` gold slice without the code-field
   queue at all.
4. NOT worth pursuing: bigger reserves, uniform newcomer priors,
   extension deny-lists (re-confirmed: `.md` is both top displacer and top
   gold class).

Verified arms were not run this round: per the coordinator's close-out
directive, and because the Lite mechanism result makes the outcome
derivable — leftover was 0 on 300/300 Python instances, so leftover-only
additive is a provable no-op on Verified's Python instances too (reserve
was already rejected on Lite). Flagged as an open checkbox if
belt-and-braces confirmation is wanted before any future default flip.

## Process anomalies (recorded)

- **Engine-sha mix in MSWE rows**: `269882f clean` (early rows), `6f752c2
  dirty` (6 baseline + 4 additive rows during the reserve-variant build
  window), `0e7e362 clean` (remainder + resumed rows + both reserve arms).
  All three binaries are retrieval-identical for the flags in use:
  defaults untouched by any commit in the window (Gate A), additive path
  untouched by the reserve commit (`reserve=0.0` keeps
  `core_budget == budget`; only two stats fields were added). Lesson
  re-learned: don't rebuild the shared binary while arms are running —
  future arms should copy the binary to a private path first (the pinned
  worktree used for the Lite arms is the right pattern).
- **MSWE additive runner died silently at 484/580** (no traceback, log
  ends cleanly mid-svelte; external kill/OOM suspected). Partial file
  verified clean (484 valid unique rows), missing 96 = exactly the
  contiguous sorted-order tail; resumed via `lab/ws1b_mswe_resume.py`
  (provenance-identical rows to `..._resume.jsonl`), concatenated to
  `..._additive_full.jsonl` and verified: 580 unique, baseline order,
  single known dayjs-857 error.
- **Lite arms initially refused by the provenance guard**: a lab-only
  commit landed between launch staggers, moving HEAD past the binary's
  embedded sha. Relaunched from a scratchpad worktree pinned at `269882f`
  with the binary copied in — guard satisfied without `--allow-stale-engine`.
- **Gate script fix**: the first Gate B run flagged `bundle_tokens >
  budget` as a violation; that's legal pass-1 core overshoot (defaults
  behavior). Corrected to the real invariant (newcomers admitted ⇒ total
  fits budget; none admitted ⇒ output equals defaults) and rerun clean.
- Four concurrent detached arms + gate chain on disjoint private
  clone dirs (issue #56 hazard protocol), 10s staggers: no interference.

## Artifacts

`lab/results_regions/`: `mswe_jsts_ws1b_baseline.{jsonl,log}`,
`mswe_jsts_ws1b_additive_full.jsonl` (+ partial-run `.log`, resume
`.jsonl`/`.log`), `mswe_jsts_ws1b_reserve10.{jsonl,log}`,
`ws1b_lite300_{baseline,additive,reserve10}.{jsonl,log}`,
`agentless_metric_mswe_ws1b_{baseline,additive,reserve10}.json`,
`agentless_metric_ws1b_lite300_{baseline,additive,reserve10}.json`,
`ws1b_gate.log`, `ws1b_smoke.log`.
Scripts: `lab/ws1b_identity_gate.py`, `lab/ws1b_smoke.py`,
`lab/ws1b_mswe_resume.py`.
