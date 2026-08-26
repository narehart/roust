# WS1c — issue-mention-gated newcomer admission: step-0 NO-GO, hypothesis falsified by mining

*Language-agnostic campaign (issue #56), workstream 1c. Branch
`ws1c-mention-gate` off `ws1b-additive-index` (0632717). Mining runs
2026-08-25. No engine change was implemented and no 580/300-instance arms
were run — the pre-registered step-0 measurement decided the round (that is
what step 0 is for).*

## Hypothesis (from WS1b's ranked candidate #1)

`--newcomer-mention-gate`: newcomers admissible only when the issue text
mentions them — basename exact match (case-insensitive) or path-suffix
match against query tokens; carve `--newcomer-reserve` (0.10) only when a
mentioned newcomer exists, byte-identical to defaults otherwise. The
case-mined premise from WS1b: "gold newcomers are frequently NAMED in the
issue text (`readme.md` in every github-readme-stats gain), while
PULL_REQUEST_TEMPLATE.md never is."

## Step-0 result: the premise is false at scale

Canonical matching semantics implemented in
`lab/ws1c_mention_mining.py` (whitespace tokens, wrapping punctuation
trimmed, case-insensitive basename equality or '/'-aligned path-suffix
match; mentioned hits refined by the engine's text-sniff + 2 MB cap so
counts reflect actual corpus membership):

- **Ceiling: 1 of 499 out-of-allowlist gold files is mentioned** in its
  issue text (path-like token variant; the unrestricted-token variant is
  also 1). One instance of 135, `mui__material-ui-23806`, gold
  `docs/src/pages/components/use-media-query/use-media-query.md`.
- **Risk bound: the gate would fire on 48/580 MSWE and 13/300 Lite
  instances** (path-like tokens; 92/580 and 25/300 unrestricted) — rare as
  designed, but buying at most one instance.

The honest recovery ceiling is tighter still. FILE is all-gold-superset,
so a blocked instance is recoverable only if ALL its outside gold is
mentioned AND its in-allowlist gold is already fully in the default
bundle (true for only 33/135): **1/135 recoverable** under spec
semantics. Upper bound on the primary metric: 46.38 → 46.55 — exactly the
number WS1b's leftover-only additive already achieved at zero region
cost, while the mention gate would carve reserve (shrinking core spans)
on 48 MSWE and 13 Lite instances to get there. The mechanism is strictly
dominated by machinery already on the branch.

### Why the case-mined premise looked true and isn't

- `anuraghazra__github-readme-stats-88` (gold `readme.md`), full issue
  text: *"It seems redundant to display the stats title in GitHub README
  profile."* — "README" is prose (the product surface), not a file
  reference. Every github-readme-stats "mention" in WS1b's gains is this
  shape, or the repo name `github-readme-stats` inside URLs. The premise
  conflated the product name with a path mention.
- The ONE real hit, `mui__material-ui-23806`, is a PR-shaped issue that
  literally contains *"I modified these files:"* followed by the gold
  paths — an answer-key leak, not an organic signal.

### The variant grid: no operating point exists

Stronger extraction and looser matching were measured before declaring
the ceiling real (`lab/ws1c_variant_grid.py` →
`lab/results_regions/ws1c_variant_grid.json`; ceiling = recoverable
instances of 135, fire = gate-fire instances):

| variant | ceiling /135 | gold mentioned /499 | fire MSWE /580 | fire Lite /300 |
|---|---|---|---|---|
| exact tokens (spec, path-like) | 1 | 1 | 48 | 13 |
| exact, regex path-runs (links/URLs/parens) | 1 | 1 | 56 | 13 |
| exact, + bidirectional suffix (blob URLs) | 1 | 1 | 200 | 14 |
| + stem token, distinctiveness cap K=1 | 2 | 7 | 468 | 252 |
| + stem K=4 | 8 | 49 | 479 | 270 |
| + stem K=8 | 11 | 94 | 514 | 270 |
| stem restricted to issue TITLE, K=8, len>=5 | 4 | 44 | 267 | 119 |

The real signal is at the STEM level: 102/499 gold newcomers are named by
basename stem ("readme" for `readme.md`, "autocomplete"/"slider" for the
material-ui docs `.md`/`.json` class; 56/135 instances have at least one
stem-named gold, 11 fully recoverable). But stems are unboundable as a
gate: with thousands of newcomer-eligible files per repo, essentially
every issue contains SOME word that is a file stem ("main", "index",
"plugin", "django" — django locale files alone give `django.po` ×4942),
so gate-fire saturates (85–90%) even at distinctiveness cap K=1, and a
title-only restriction kills the ceiling (readme-stats issues don't put
"readme" in titles) while Lite still fires on 119/300. Reserve carving at
those rates reproduces WS1b's rejected reserve-10 cost profile
(Lite FUNCTION −3.0, MSWE fraction −1.29).

### Lite anatomy: the 13 gate-fire instances are pure downside

All 13 have pure-`.py` gold, zero mentioned gold; 11 are currently
FILE-correct. What their mentions would admit: sphinx `doc/**/index.rst`
(7 instances — issues cite doc TOC pages), django form-template
`default.html`s, `pytest.ini` fixture copies, `pyproject.toml` examples,
`cextern/wcslib/C/wcs.c`. The gate would shave core spans on 11 correct
Python instances to admit doc boilerplate — exactly the dilution the
mechanism was designed to avoid, minus any gain.

## Verdict: NO-GO — do not implement, do not run arms

- Measured ceiling of the spec'd mechanism = +1 instance (46.55), a tie
  with already-adopted-scaffolding behavior (`--index-all-additive`
  leftover-only, +1/−0 at zero region risk); every point of possible gain
  is already banked more safely. Gates 3–5 cannot produce information
  that changes this — the upper bound is arithmetic, not noise.
- Success criterion "FILE > 46.38 with regions non-negative" is
  technically reachable but strictly dominated; ADOPT-RECOMMEND is
  therefore not on the table. Nothing to flip, nothing to gate.

## What survives for the ledger (WS1c → WS1d candidates)

1. **The newcomer-ranking problem is NOT mention-solvable from the query
   side.** Gold newcomers are named by stem in 20% of gold (102/499) but
   never by path/basename (1/499, and that one is a leak); stem matching
   cannot be gated rarely enough. Any future mention feature belongs (if
   anywhere) as a small RANKING boost inside the newcomer queue, never as
   a reserve-carve trigger.
2. **WS1b candidate #2 (boilerplate-class down-weight within the
   newcomer queue) and #3 (docs-field promotion) are now the only live
   paths** to the 135-instance ceiling. The stem finding feeds #3: the
   recoverable class is component-named docs (`.md`/`.json` under
   `docs/`), which the docs field already indexes.
3. Method note: this round cost ~zero compute because step 0 was
   pre-registered ahead of implementation. The WS1b smoke expectation
   ("github-readme-stats instances, gold readme.md, mentioned — must
   recover") would have failed in implementation and only then revealed
   the premise; mining first inverted the order.

## Process notes

- Repos were read with `git ls-tree`/`git cat-file` only (no checkouts) —
  safe beside any concurrently running evals; `lab/mswe_repos_private`
  used for MSWE per the issue #56 hazard protocol.
- MSWE-580 baseline rows reused from WS1b
  (`mswe_jsts_ws1b_baseline.jsonl`) for the core-gold-present test; gold
  file sets parsed from the dataset patches (`diff --git` paths), outside
  gold from `ws1_ceiling_records.jsonl` (sums to 499 exactly).
- No engine, harness, or defaults change anywhere in this round; the
  branch adds mining scripts + results + this writeup only.

## Artifacts

- `lab/ws1c_mention_mining.py` — canonical semantics + A/B/C mining
  (ceiling-135 mentioned gold; MSWE-580 and Lite-300 gate-fire with
  sniff-refined corpus membership) →
  `lab/results_regions/ws1c_mention_mining.json`.
- `lab/ws1c_variant_grid.py` — the 11-variant trade-off grid →
  `lab/results_regions/ws1c_variant_grid.json`.
