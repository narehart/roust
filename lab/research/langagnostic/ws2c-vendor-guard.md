# WS2c — the vendored-C guard + `--cfamily-ext` default re-gate

*Campaign #56 workstream 2c, executing WS2b's proposed guard
(`lab/research/langagnostic/ws2b-cfamily-gate.md`) and re-gating the
default flip it deferred. Branch `ws2c-vendor-guard` off the WS2b tip
`5db05e1`. Gate runs 2026-08-25. Engine binary for ALL arms: `roust 0.2.0
(39b0b14, clean)` — a pinned-worktree build of the VENDOR_RE-extension
commit (default still OFF at that commit; the cfamily arms pass
`--cfamily-ext` explicitly, which is behavior-identical to the flip's
default-ON state — both paths call `set_cfamily_ext(true)`). The default
flip itself (`main.rs`, `--cfamily-ext` default ON + `--no-cfamily-ext`
off-switch) is a later commit on this branch, gated by these results.*

## The change

`VENDOR_RE` (`roust-rs/src/core.rs`) gains two alternates, exactly the
WS2b-proposed spellings:

    (^|/)(cextern|extern)(/|$)      (^|/)(libsvm|liblinear)(/|$)

Component-anchored: `cextern/`, `extern/`, `libsvm/`, `liblinear/` as
exact path components. `external/`, `src/externals/`, and nushell's
`run_external.rs` do NOT match (pinned by the new
`ws2c_vendor_re_cextern_libsvm_guard` unit test; 80/80 tests pass).

## Gate 1 — gold data check (before any eval): PASS

`lab/ws2c_gold_datacheck.py` over the gold patch paths of all eight
slices (MSWE parquets rebuilt from HF via `lab/mswe_adapter.py`; per-lang
slices re-derived from the committed instance lists — c 128, cpp 129,
go 428, rust 239, java 128, jsts 580 all reproduce WS2/E23 counts):

| slice | n | gold matching NEW patterns | gold matching OLD VENDOR_RE | `extern` substring |
|---|---|---|---|---|
| c | 128 | **0** | 0 | 0 |
| cpp | 129 | **0** | 1 (pre-existing¹) | 0 |
| go | 428 | **0** | 0 (incl. zero under `vendor/`) | 0 |
| rust | 239 | **0** | 0 | 2 (spared²) |
| java | 128 | **0** | 0 | 0 |
| jsts | 580 | **0** | 0 | 0 |
| lite | 300 | **0** | 0 | 0 |
| verified | 407 | **0** | 0 | 0 |

¹ `nlohmann__json-944`: gold `third_party/amalgamate/config.json` was
already excluded by the *existing* `third_party` pattern (and `.json` is
not an indexable extension) — a pre-existing finding, unchanged by WS2c.
² `nushell-13870`/`-12901`: gold `crates/nu-command/src/system/run_external.rs`
contains the substring `extern` but is spared by the component anchoring —
the exact reason the pattern is anchored.

Zero gold under any newly- or already-excluded dir in our slices → the
MSWE c/cpp idx-style full arms are skippable per the round spec; only the
two exp arms are re-run.

## The census discovery — the guard touches Python DEFAULTS too

`lab/ws2c_census.py` (`git ls-tree` at every Lite/Verified base commit,
private clones, read-only): **`astropy/extern/` carries 26 unique
default-suffix files** (vendored ply, configobj, six, plus jquery `.js`)
on 6 Lite and 18 Verified astropy instances. matplotlib and sklearn's
matching dirs hold only C-family files. Two consequences, both borne out
downstream: (a) defaults change on astropy instances, so the WS2b
Verified base arm is NOT reusable — it was re-run (the round spec's
justify-or-rerun resolves to rerun); (b) django/sympy/sphinx are provably
untouched, making them the right byte-identity pool.

## Gate 2 — defaults byte-identity vs main: PASS

`lab/ws2c_identity_gate.py`, MAIN binary `(3069573, clean)` vs branch
`(39b0b14, clean)`, two runs per binary, retrieval-payload md5, cold
`.roust`, private `repos_gate` clones: **9/9 OK, 0 determinism flakes**
(3 × django, sympy, sphinx — ≥8 per spec). Diagnostic on matching-dir
repos: astropy-12907/-14182, matplotlib-18869, sklearn-10297 all
IDENTICAL under this cold single-instance protocol. (The Lite/Verified
arms below run the harness's warm incremental-cache sequence, where small
astropy payload diffs DO appear — the arm-vs-arm comparison is the
apples-to-apples one; the cold gate bounds the blast radius to astropy
regardless.) Log: `lab/results_regions/ws2c/identity_gate.log`.

## Arms

Six detached runs, 10 s stagger, all `roust 0.2.0 (39b0b14, clean)`
pinned-worktree, private clones per arm (`repos_lite_{base,cf}`,
`repos_ver_{base,cf}` reused from WS2b; fresh `ws2c_repos/{c,cpp}_exp`
clones), `--budget 8192` defaults. Row counts 128/129/300/300/407/407,
single engine SHA across all rows, 1 engine error total (mswe_c, the same
no-results instance WS2 hit; errors-count-as-wrong). Scorers:
`agentless_metric_v4.py` (Lite), `agentless_metric_verified.py`
(Verified), `agentless_metric_full.py --ts-functions --lang-functions`
with WS2's pinned grammar wheels (MSWE).

### Gate 3a — MSWE C/C++ exp re-gate: PASS, byte-identical

| slice | arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|
| c 128 | WS2 exp (reference) | 46.88 | 26.56 | 10.94 | .19768 |
| c 128 | WS2c exp (guarded) | **46.88** | **26.56** | **10.94** | **.19768** |
| cpp 129 | WS2 exp (reference) | 65.89 | 18.60 | 7.75 | .29672 |
| cpp 129 | WS2c exp (guarded) | **65.89** | **18.60** | **7.75** | **.29672** |

Not merely within noise: **0/128 and 0/129 per-instance payload diffs** —
the guard is provably inert on the C/C++ slices (zstd/jq/ponyc and the
five cpp repos have no matching dirs with indexable content). FILE holds
46.88/65.89 exactly as required.

### Gate 3b — Lite-300: PASS on all four (and the defaults delta)

| arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|
| reference (current main defaults, WS2b base) | 92.33 (277) | 54.67 (164) | 43.67 (131) | .52544 |
| WS2c base (defaults, guard only) | **92.33** (277) | **54.67** (164) | **43.67** (131) | **.52710** |
| WS2c cfamily (guard + C indexing = post-flip defaults) | **92.33** (277) | **54.67** (164) | **44.00** (132) | **.52728** |

Defaults delta (reference vs WS2c base, `paired_diff_lite300_defaults.json`):
5 payload diffs, ALL astropy (census-predicted), all indirect. Outcome
changes: astropy-12907 FUNCTION ✗→✓, astropy-14365 FUNCTION ✓→✗ (its
fraction +0.5 despite the exact-set loss) — net FUNCTION 0, LINE 0 flips,
fraction +1/−0 (+.00166). Non-negative on every headline metric.

Flip gate (WS2c base vs cfamily, `paired_diff_lite300.json`): 36 payload
diffs, ONE outcome change — matplotlib-26020 LINE ✗→✓ (+0.053, indirect,
no C file in bundle). cfamily ≥ base on all four metrics. **The WS2b
regression is cured**: vs the pre-guard WS2b cfamily arm (54.33), FUNCTION
is back to 54.67.

### scikit-learn-14894 — the WS2b casualty, itemized

WS2b: 4 bundled libsvm C/C++ files (`sklearn/svm/src/libsvm/{svm.cpp,
svm.h, libsvm_helper.c, libsvm_sparse_helper.c}`) entered the bundle and
displaced the gold spans — FUNCTION ✓→✗, LINE ✓→✗, fraction −0.182.
WS2c: the cfamily bundle is **file-for-file identical to the base
bundle** (36 files, zero C-family), `hunk_line_recall` 1.0, FUNCTION and
LINE both correct. **The guard saved it** — that is the entire round in
one instance.

### Gate 3c — Verified-407: FILE/FUNCTION hold; LINE −1 instance

| arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|
| fresh reference (current main defaults, WS2b base) | 92.38 (376) | 47.17 (192) | 35.38 (144) | .47651 |
| WS2c base (defaults, guard only) | **92.38** (376) | **47.17** (192) | 35.14 (143) | .47635 |
| WS2c cfamily (post-flip defaults) | **92.38** (376) | **47.17** (192) | 35.14 (143) | .47635 |

Defaults delta (reference vs WS2c base,
`paired_diff_ver407_defaults.json`): 17 payload diffs, ALL astropy (of
the 18 census-exposed instances), all indirect. ONE outcome change:
**astropy-14508 LINE ✓→✗** (gold `astropy/io/fits/card.py`; the file is
still retrieved — FILE holds — but the in-file region set drops 2 of 31
gold lines, recall 1.0→0.935, after the 26 vendored extern/ files leave
the index and re-rank candidate regions). Bench fraction −.00016, sign
test +0/−1 p=1.

Flip gate (WS2c base vs cfamily, `paired_diff_ver407.json`): 51 payload
diffs, **zero outcome flips, zero fraction changes** (+0/−0, at every
level) — with the guard in place, indexing C on Verified is
outcome-inert; the −0.25 pp LINE vs the reference is carried entirely by
the defaults delta above, none of it by the flip.

## Verdict

Scorecard for the bundle (VENDOR_RE guard + default flip), end-state
(post-flip defaults) vs current-main references:

| gate | criterion | result |
|---|---|---|
| gold data check | 0 gold under new patterns, all slices | **PASS** (0/8 slices) |
| defaults byte-identity (non-matching repos) | 9/9 two-run md5 | **PASS** |
| MSWE c/cpp exp | FILE holds 46.88/65.89, rest within noise | **PASS** (byte-identical, 0 payload diffs) |
| Lite-300 defaults delta | non-negative | **PASS** (+.00166 fraction, counts identical) |
| Lite-300 end-state | all four hold | **PASS** (92.33/54.67/**44.00**/.52728 — LINE +0.33 over reference) |
| Verified-407 defaults delta | non-negative | **FAIL by one instance** (LINE 35.38→35.14, astropy-14508, −2 gold lines, p=1) |
| Verified-407 end-state | all four hold | **FAIL by the same single instance** (92.38/47.17/**35.14**/.47635 — the flip itself adds zero flips; the −1 LINE instance is wholly the defaults delta) |

**Verdict: ADOPT-RECOMMEND, with one itemized boundary condition for the
user.** Eleven of twelve cells are green; the WS2b failure mode (direct
gold displacement by vendored C — structural, systematic) is cured and
proven cured at the payload level. The single red cell is not the C flip
at all: it is the guard's own defaults side-effect on astropy —
one instance, two gold lines, indirect region re-ranking after genuinely
vendored `.py`/`.js` leaves the index, with the mirror-image effect on
Lite being a gain (+1 LINE instance there, +0/−1 vs +1/−0 sign tests,
both p=1 — symmetric one-instance churn, not a harm class). WS2b's REJECT
precedent was a *structural, attributable, preventable* loss; this one is
attributable noise with no mechanism to prevent short of narrowing
`extern/` out of the guard — which would re-admit matplotlib's 191
`extern/` C files, the exact class the guard exists for. If the user
prefers the strict letter (every cell non-negative), the fallback is
dropping the bare `extern` alternate and re-gating; the recommendation
here is to accept the churn and adopt.

Do-not-merge: the PR presents the bundle; adoption is the user's call.

## Artifacts

`lab/results_regions/ws2c/`: `mswe_{c,cpp}_exp.jsonl`,
`lite300_{base,cfamily}.jsonl`, `ver407_{base,cfamily}.jsonl` (+ `.log`),
`agentless_metric_ws2c_*.json` × 6, `paired_diff_lite300{,_defaults}.json`,
`paired_diff_ver407{,_defaults}.json`, `gold_datacheck.json`,
`identity_gate.log`, `score_*.log`. Scripts: `lab/ws2c_gold_datacheck.py`,
`lab/ws2c_census.py`, `lab/ws2c_identity_gate.py`. Engine: VENDOR_RE
extension + guard unit test (`39b0b14`), default flip + `--no-cfamily-ext`
(this branch's tip). Parquets: `lab/mswe_{c,cpp}.parquet` re-derived from
HF + committed instance lists (untracked, per WS2 convention).

## Process notes (recorded)

- The WS2 worktree (`bgrep-worktrees/ws2-grammar-batch`) and its parquets/
  clones were gone; c/cpp slices were rebuilt from HF and verified to
  reproduce the committed instance lists exactly, and fresh private clones
  were used for the exp arms. Slice identity is auditable in
  `gold_datacheck.json` (n per slice).
- Cold-vs-warm nuance: the identity gate (cold `.roust` per instance)
  shows astropy defaults byte-identical, while the harness arms (warm
  incremental cache across same-repo instances) show 5/17 astropy payload
  diffs. Both are true; arm-vs-arm comparisons share the warm convention.
- The mswe_c engine error (1) is the same no-results instance as WS2's
  c_exp arm (0 new errors anywhere; 0 harness errors).
- The primary checkout's shared `roust-rs/target/release/roust` was
  rebuilt at the branch tip during post-gate smoke testing (no runs were
  using it; all arms used the pinned worktree binary). It now reflects
  the ws2c flip state, superseding the stale WS1b build WS2b flagged.
- One session interruption (transient API error) between arm launch and
  completion; all six detached runners survived and were verified by row
  count, engine SHA, and error scan before scoring.
