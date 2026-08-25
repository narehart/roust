# WS1 — universal indexing (`--index-all`): gate REJECT, do not adopt

*Language-agnostic campaign (issue #56), workstream 1. Branch
`ws1-universal-index` off main `0d8113e`; engine commit `e41967f`, gate
binary `roust 0.2.0 (d0f0218, clean)` (interim commit touched `lab/` only;
Gate A proved retrieval identity). Gate runs 2026-08-25.*

## What shipped (flag-gated, default OFF, byte-identical)

**Engine** (`roust-rs/src/core.rs`, `cache.rs`, `main.rs`): `--index-all`
replaces the corpus walk's `CODE_EXTENSIONS` allowlist with content-based
inclusion — every file that survives the existing ignore rules (git-ls-files
enumeration, `.git/`, vendored dirs via `VENDOR_RE`, now-explicit `.roust/`
exclusion) and the existing caps (2 MB `MAX_FILE_BYTES`, 3000-char
`MAX_LINE_CHARS`, non-empty tokenization) is indexed if it sniffs as text
(no NUL byte in the first 8 KB, UTF-8-decodable head tolerating one
truncated trailing char). Allowlisted extensions are never sniffed, so the
flagged corpus is a **strict superset** of the default corpus. Cache
plumbing is flag-aware end to end: distinct cache key (`:a1` suffix only
when flagged — unflagged keys byte-unchanged), manifest covers every walked
file under the flag (stat-only pass can't sniff; coarser-is-safe), and the
incremental-update partition becomes corpus-membership-based (a `.md` can
be in both the code and docs fields) with a conservative decline-to-full-
rebuild for any modified never-indexed file (binary→text flips). `--json`
stats gain an `index_all` block (files beyond the allowlist + suffix
breakdown) only when flagged. 5 new unit/integration tests (sniff verdicts,
inclusion fixture, allowlist-never-sniffed superset guarantee, flagged
update_files, cross-flag cache isolation); 77 total pass.

**Harness**: `--index-all` passthrough in `parity/region_eval_full.py`
(EXTRA_ENGINE_FLAGS, per-row provenance), `parity/region_eval2.py` (argv
builder + `index_all_stats` per row), `parity/region_eval_verified.py`
(`index_all_stats` diagnostic).

## Pre-run proofs and measurements

- **Identity Gate A** (`lab/ws1_identity_gate.py`): defaults byte-identical
  to main `0d8113e` — 18 instances (12 Lite across 6 Python repos + 6 MSWE
  JS/TS across 3 repos), two runs per binary per instance, md5 over the
  retrieval payload: 0 mismatches, 0 determinism flakes.
- **Gate B anatomy**: defaults vs `--index-all` on 12 Lite instances — all
  12 differ, fully attributable: 42–1099 newly-admitted files per repo
  (pylint worst: `.txt`/`.rc` test fixtures; seaborn: `.ipynb`), newcomers
  (`README.rst`, `setup.cfg`, `CHANGES.rst`) enter bundles, and even
  newcomer-free bundles shift because corpus statistics (df/n_docs/avg_len)
  change. The dilution mechanism, visible before the gate.
- **Ceiling recoverability** (`lab/ws1_ceiling_analysis.py`, per-instance
  checkouts of all 135 blocked instances): **all 499 out-of-allowlist gold
  files pass the inclusion chain** — 0 blocked by vendor regex, size cap,
  sniff, or long-line filter. Gold ext breakdown: `.json` 316, `.md` 158,
  `.preview` 12, extensionless 5, `.svelte` 4, `.cts`/`.diff`/`.mjs`/
  `.yaml` 1 each. Filters kept unchanged — data-justified (nothing gold is
  minified/oversized; newly-admitted p99 size well under 2 MB everywhere).
- **node_modules**: 0 files under git control in any MSWE repo, and
  `VENDOR_RE` excludes the path unconditionally anyway.
- **Smoke** (`lab/ws1_smoke.py`, 10 blocked instances): **13/13
  out-of-allowlist gold files indexed, 10/13 returned** (misses:
  `.gitignore`, `.prettierignore`, `scripts/react-next.diff` — ranking, not
  indexing). Cost: index size +30–100 % (material-ui 38.8→51.2 MB, svelte
  7.5→14.6 MB), cold index comparable, worst warm-query delta axios
  2.2 s → 5.5 s.

## Baseline reproduction — and a stale-reference finding

MSWE-580 baseline arm reproduces the E23 reference **exactly**:
46.38 / 31.03 / 13.28 / .2582 (269/580, 180, 77; same single
`iamkun__dayjs-857` engine error).

Lite-300 baseline arm: **92.33 / 54.67 / 43.67 / .52544** — FILE and
FUNCTION equal the v12 reference to every digit; LINE (43.67 vs 43.33) and
fraction (.52544 vs .52510) do NOT. Root-caused, not a harness bug: exactly
26 instances differ from `e23_lite300_baseline.jsonl`, every one with a
`.js` file in its bundle (django admin JS, sphinx `searchtools.js`,
matplotlib `mpl.js`). Proven on `django__django-13710`: main `0d8113e`
defaults == this run's row; `0d8113e --no-structural-blocks` == the E23
row. **The published v12 LINE/fraction reference is stale post-PR#55** —
E23's "Python v12 references unchanged" claim silently excluded Lite
bundles containing JS (its identity proofs sampled pure-Python bundles).
The current-main Lite reference is 92.33 / 54.67 / **43.67** / **.52544**
(structural blocks nudge those 26 bundles, net +1 LINE instance). Both WS1
arms ran one binary, so the paired gate below is internally valid.

## MSWE-580 gate (primary): REJECT

| metric | baseline (defaults) | `--index-all` | paired |
|---|---|---|---|
| FILE (all-gold superset) | 46.38 (269/580) | **31.21 (181/580)** | **+13/−101, p=4.8e-18** |
| FUNCTION (exact) | 31.03 (180/580) | 25.52 (148/580) | — |
| LINE (all-or-nothing) | 13.28 (77/580) | 11.21 (65/580) | — |
| LINE mean fraction | .2582 | .1988 | +40/−154, p=5.6e-17 |

**Ceiling math**: of the 135 ceiling-blocked instances, **10 recovered**
(7.4 % of the theoretical 135-instance / ~23.3-point headroom; ~+1.7 FILE
points gross). Of the 13 total FILE gains, 10 are blocked-set recoveries.
Meanwhile the 445 unblocked instances collapsed **60.4 % → 38.4 %**
FILE-correct (269→171): net **−15.2 FILE points**.

**Anatomy — indexing works, ranking drowns**:
- Every out-of-allowlist gold file was indexable, but only **21/499 were
  returned**. Indexed ≠ ranked: gold configs/docs do not outrank the
  boilerplate admitted alongside them.
- Blocked-135 under the flag: 10 recovered / 24 missing only outside-gold /
  98 missing BOTH kinds / 3 missing only code gold — dilution damaged even
  the code-gold halves of the very instances the flag was meant to rescue.
- Displacers in the 101 lost bundles (top basenames): `README.md` (128
  bundle slots), `CONTRIBUTING.md` (91), `FUNDING.yml` (87),
  `PULL_REQUEST_TEMPLATE.md` (86), `config.yml`/`bug_report.yml` (82),
  `package.json` (73), plus svelte blog-post `.md`s. Missing gold in those
  bundles: `.js` ×116, `.ts` ×21. JS/TS issue text is lexically close to
  READMEs/templates/changelogs (shared product vocabulary, fenced code,
  package names), so BM25F ranks boilerplate high; dense-token newcomers
  also shrink packed mass (mean region lines 1061→877).
- `package.json` duality: gold in only 7 blocked instances, displacer in 73
  lost bundles — the newcomer class is overwhelmingly noise, occasionally
  signal, and extension-level rules cannot separate the two (`.md` is both
  the #1 displacer and 158 gold files).

## Lite-300 dilution gate: FAIL (nominal), null (statistical)

| metric | baseline (defaults) | `--index-all` | paired |
|---|---|---|---|
| FILE | 92.33 (277/300) | **92.00 (276/300)** | +2/−3, p=1.0 |
| FUNCTION (exact) | 54.67 (164/300) | 54.00 (162/300) | — |
| LINE (all-or-nothing) | 43.67 (131/300) | 43.67 (131/300) | — |
| LINE mean fraction | .52544 | .52502 | +8/−8, p=1.0 |

FILE did not hold 92.33 — the strict invariant fails by one net instance,
though every direction count is coin-flip null. The three losses are the
same displacement signature in miniature (`setup.cfg`/`tox.ini`/
`README.rst`/ISSUE_TEMPLATEs — and sphinx locale `.po` files — entering
bundles; one gold `.py` evicted each). Two django gains. Python dilution is
mild because Python issue text is less README-shaped; the verdict does not
depend on it.

## Verdict: REJECT as-is — keep `--index-all` flag-gated OFF

Primary metric moved −15.2 FILE points (p=4.8e-18) against a ceiling case
worth at most +23.3; realized recovery 7.4 % of headroom. Verified arms not
run (Lite gate did not pass; primary already decided). The flag, its cache
plumbing, and the harness passthrough stay on the branch as the vehicle for
the follow-ups below.

**Revival preconditions** (ranked, case-mined):
1. **Additive-only packing guard** (WS1b, strongest): rank with newcomers
   but guarantee the unflagged selection's packed files are never evicted —
   the E12b-padding-guard pattern lifted to file admission. All-gold-
   superset FILE is monotone in the packed set, so losses become
   structurally impossible (−101 → 0 by construction) while the +13 gains
   survive; cost is newcomers packing only into residual budget.
2. **Non-code file prior**: `impl_prior`-style down-weight for
   non-allowlisted files (the displacer class — README/templates/CI
   configs/blog posts — is near-never gold; 0.3-style multiplier, gated).
3. **Docs-field promotion** instead of code-field indexing for `.md`/
   `.rst`/`.txt`: the docs field already indexes them for bridging;
   promoting docs hits into FILE output attacks the `.md` half of the
   ceiling (158/499) without touching code-field ranking at all.
4. NOT a fix: extension deny-lists or "minified junk" filters — measured
   irrelevant (0/499 gold files filtered; displacers and gold share
   extensions).

## Process anomalies (recorded)

- Stale-reference discovery above: v12 Lite LINE/fraction references must
  be restated as 43.67/.52544 for any post-PR#55 engine comparison.
- Scoring env: `.venv-pkg` lacked the tree-sitter bindings the E23 scorer
  pins; installed `tree-sitter==0.26.0`, `tree-sitter-javascript==0.25.0`,
  `tree-sitter-typescript==0.23.2` to score MSWE.
- The E23-era identity-gate scratchpad (`wt-main-ref`, `gate_clones`) no
  longer existed; rebuilt in this session's scratchpad (main-ref worktree
  at `0d8113e` + 9 private clones). `lab/ws1_identity_gate.py` now takes
  both as CLI args instead of hardcoding session paths.
- Four concurrent detached arms (2× MSWE-580, 2× Lite-300) on disjoint
  private clone dirs, launches staggered 12 s (pgrep guard, issue #56):
  no guard trips, no cross-arm interference; both baselines reproduced
  their references on FILE/FUNCTION exactly.

## Artifacts

`lab/results_regions/`: `mswe_jsts_ws1_baseline.jsonl`(+`.log`),
`mswe_jsts_ws1_indexall.jsonl`(+`.log`), `ws1_lite300_baseline.jsonl`
(+`.log`), `ws1_lite300_indexall.jsonl`(+`.log`),
`agentless_metric_mswe_ws1_{baseline,indexall}.json`,
`agentless_metric_ws1_lite300_{baseline,indexall}.json`,
`ws1_ceiling_records.jsonl` (per-instance recoverability verdicts).
Scripts: `lab/ws1_identity_gate.py`, `lab/ws1_ceiling_analysis.py`,
`lab/ws1_smoke.py`, `lab/ws1_paired_stats.py`.
