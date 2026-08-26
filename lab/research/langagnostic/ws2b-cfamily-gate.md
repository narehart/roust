# WS2b — the `--cfamily-ext` default-flip gate: Python dilution arms

*Campaign #56 workstream 2b, gating the flip of `--cfamily-ext` (WS2's new
extension flag, default OFF) to default ON. Branch `ws2b-cfamily-gate` off
main `3069573` (the WS2 merge tip). Gate runs 2026-08-25. Engine binary for
ALL arms: `roust 0.2.0 (80e9d25, clean)` — a pinned-worktree build of a
harness-only branch commit whose `roust-rs/` tree is byte-identical to main
`3069573` (empty `git diff`, plus the Gate A payload proof below). The
branch adds only the `--cfamily-ext` argparse passthrough to
`parity/region_eval2.py` / `parity/region_eval_verified.py` (the same
`EXTRA_ENGINE_FLAGS` mechanism `region_eval_full.py` got in WS2) and the two
WS2b lab scripts. MSWE C/C++ arms are NOT rerun — WS2's stand
(`lab/research/langagnostic/ws2-grammar-batch.md`): indexing is worth FILE
0→65.89 (cpp, p=5.2e-26) / 0→46.88 (c, p=1.7e-18) on MSWE-257.*

## Question

Does indexing C-family files (`.c/.h/.cc/.cpp/.cxx/.hpp/.hh`) harm the
Python benchmarks? Python repos carry C sources; if the flag is ever to be
default-ON, Lite-300 and Verified-407 must hold on current-main defaults vs
`--cfamily-ext`.

## Step 0 — what would actually enter the index (analysis before arms)

`VENDOR_RE` (`roust-rs/src/core.rs:1047`) is
`(?i)(vendor|vendored|third_party|node_modules|\.min\.(js|css)$|bundle\.js$)`,
a substring match on the rel path. **It does NOT cover the Python repos'
bundled C**, because they spell it `cextern/`, `extern/`, and
`sklearn/svm/src/` — none of which match. (numpy/pandas themselves are in
neither Lite nor Verified; both benches cover the same 12 repos, so the
"numpy vendors C" concern maps onto astropy/matplotlib/scikit-learn here.)
Census over the 12 repos (clone HEAD; VENDOR_RE + the 2 MB `MAX_FILE_BYTES`
cap applied — no file exceeds it):

| repo | entering C-family files | breakdown |
|---|---|---|
| astropy | 471 | 427 vendored-in-spirit under `cextern/` (erfa 235, cfitsio 91, expat 57, wcslib 44) + 44 first-party (`astropy/wcs` 31, `astropy/io` 6, `astropy/_erfa` 3, …) |
| matplotlib | 220 | 191 vendored-in-spirit under `extern/` (agg24-svn 186, ttconv 5) + 29 first-party `src/*.cpp` |
| scikit-learn | 16 | bundled libsvm/liblinear under `sklearn/svm/` (13) + `sklearn/utils` 2 + `sklearn/linear_model` 1 |
| sphinx | 1 | `tests/roots/` fixture (TESTLIKE_RE prior 0.3, still indexed) |
| django, sympy, seaborn, flask, requests, xarray, pylint, pytest | 0 | — |

Verdict of step 0: ~708 files enter across 4 of 12 repos, most of them
third-party code VENDOR_RE misses on spelling — **the arms are a real
dilution test, not a cheap identity confirmation**.

## Identity gates (pre-arm, `lab/ws2b_identity_gate.py`)

Binaries: main-tip build `roust 0.2.0 (3069573, clean)` vs branch build
`(80e9d25, clean)`. Clones: private copy, cold `.roust` per instance. Pool:
12 Lite instances = 2 × {astropy, matplotlib, scikit-learn, sphinx (the
C-carrying repos), django, sympy (controls)}.

- **Gate A (defaults byte-identity, two runs per binary): 12/12 OK, 0
  determinism flakes** — the branch binary is payload-identical to main on
  defaults; arms cleared.
- **Gate B (diagnostic, branch binary, flag off vs on): 6/12 DIFFER —
  exactly the 2 astropy + 2 matplotlib + 2 sklearn instances; django/
  sympy/sphinx inert.** 3 of the 6 diffs have NO C-family file in the final
  bundle (astropy-14182, both sklearn) — C entering the index shifts
  df/IDF and candidate competition without any C file being selected. Log:
  `lab/results_regions/ws2b/identity_gate.log`.

## Arms

Harness: `parity/region_eval2.py` / `parity/region_eval_verified.py`
(default invocations, `--budget 8192`), `--repos-dir` at a private per-arm
clone copy (5 copies total incl. the gate's; shared `lab/swebench_repos`
untouched), 10 s launch stagger, detached; 0 engine errors, 0 harness
errors in any arm (300/300 and 407/407 rows). Scorers:
`lab/agentless_metric_v4.py` and `lab/agentless_metric_verified.py`
(errors-count-as-wrong convention).

### Lite-300 (defaults vs `--cfamily-ext`)

| metric | base | cfamily | delta |
|---|---|---|---|
| FILE | 92.33 (277/300) | **92.33 (277/300)** | 0 flips — per-instance identical set |
| FUNCTION | 54.67 (164/300) | 54.33 (163/300) | **−0.33 (one instance)** |
| LINE | 43.67 (131/300) | **44.00 (132/300)** | +0.33 (+2/−1 flips) |
| fraction | .52544 | **.52616** | +.00072 (+3/−1, sign test p=0.625 ns) |

The baseline arm reproduces the current-main reference **exactly**
(92.33/54.67/43.67/.52544 — the post-PR-#55/#60 numbers).

### Verified-407 (defaults vs `--cfamily-ext`)

| metric | base (fresh) | cfamily | delta |
|---|---|---|---|
| FILE | 92.38 (376/407) | **92.38 (376/407)** | 0 flips — per-instance identical set |
| FUNCTION | 47.17 (192/407) | **47.17 (192/407)** | 0 flips |
| LINE | 35.38 (144/407) | **35.38 (144/407)** | 0 flips |
| fraction | .47651 | .47628 | −.00023 (+0/−1, p=1 ns) |

### Verified baseline drift (finding, derived FIRST per the round spec)

The recorded Verified reference 92.38/47.17/35.63/.47810 **is stale** — it
predates PR #55/#60. Fresh current-main baseline: **92.38 / 47.17 / 35.38 /
.47651**. FILE and FUNCTION are unchanged; structural-blocks adoption moved
Verified LINE −0.25 pp (145→144 instances) and fraction −.0016 — the same
post-adoption shift WS1b flagged on Lite (where it moved LINE the other
way, 43.33→43.67). All WS2b gating is against the fresh numbers; the fresh
baseline artifact (`agentless_metric_ws2b_ver407_base.json`) is the
current Verified reference going forward.

## Per-instance itemization (`lab/ws2b_paired_diff.py`)

Lite: 47/300 payloads changed, 4 instances changed outcome. Verified:
66/407 payloads changed, 1 instance changed (fraction only). Every changed
instance, with attribution (direct = C file in the returned bundle;
indirect = payload changed with no C file selected, i.e. the Gate-B
df/competition mechanism):

| instance | flips | Δfraction | attribution | C files involved |
|---|---|---|---|---|
| scikit-learn-14894 (Lite) | FUNCTION ✓→✗, LINE ✓→✗ | −0.182 | **direct** | `sklearn/svm/src/libsvm/{svm.cpp, svm.h, libsvm_helper.c, libsvm_sparse_helper.c}` entered the bundle |
| matplotlib-25079 (Lite) | LINE ✗→✓ | +0.125 | indirect | none in bundle |
| matplotlib-26020 (Lite) | LINE ✗→✓ | +0.053 | indirect | none in bundle |
| scikit-learn-25500 (Lite) | none | +0.222 | indirect | none in bundle |
| matplotlib-25775 (Verified) | none | −0.091 | indirect | none in bundle |

The single casualty is **vendored libsvm**: on sklearn-14894 (a
`sklearn/svm/base.py` fix) four bundled libsvm C/C++ files score into the
bundle and displace the Python spans that previously covered the gold
function/lines. FILE never flips anywhere on either bench — dilution never
knocks a gold file out of the selected set; the damage is budget
displacement inside the bundle, and it happened exactly once in 707
instances.

## Verdict — gate FAILS (narrowly); do NOT flip the default yet

Per the gate criterion (all four metrics hold on both benches), Lite
FUNCTION 54.67→54.33 is a regression: **REJECT the default flip in its
current form.** The full picture is a wash (Lite LINE and fraction up,
Verified all-zero flips, no sign-test significance anywhere), but the one
loss is structural, attributable, and *preventable*: it is exactly the
vendored-C class step 0 predicted VENDOR_RE would miss.

**Proposed guard (WS2c):** extend `VENDOR_RE` with the vendored-C
spellings before re-gating the flip — `(^|/)(cextern|extern)(/|$)` plus
the bundled-lib names `(^|/)(libsvm|liblinear)(/|$)`. This excludes all
427 astropy `cextern/` files, matplotlib's 191 `extern/` files, and
sklearn's 13 `sklearn/svm/src/libsvm|liblinear` files (the sklearn-14894
casualty), while keeping first-party native sources (astropy/wcs,
matplotlib/src) indexable — which is the point of the flag. Caveats to
gate in WS2c: (a) `extern/` exclusion must be re-gated on MSWE C/C++ (no
gold files under `extern/` in the WS2 slices is expected but unverified);
(b) VENDOR_RE is walk-global, so the change needs the usual Lite/Verified
byte-identity-or-better check on defaults too (it can only remove files
that default-indexing never saw, so defaults should be byte-identical —
cheap to confirm).

## README scoreboard plan (drafted in this PR, consistent with the verdict)

The multi-language table is promoted into README `## Scoreboard` as a
first-class subsection ("Multi-language localization") with per-cell
sources: Python Lite/Verified rows from this round's fresh artifacts
(retiring the stale README LINE 43.3 and the stale Verified 35.63/.4781),
JS/TS from E23, Java/Go/Rust/C/C++ from WS2's corrected-scorer arms. The
C/C++ rows are explicitly marked **opt-in `--cfamily-ext`** with a
one-line note that the default flip was gated here and deferred pending
the vendored-C exclusion. No cell claims default behavior that isn't.

## Artifacts

`lab/results_regions/ws2b/`: `lite300_{base,cfamily}.jsonl`,
`ver407_{base,cfamily}.jsonl`, `agentless_metric_ws2b_*.json` × 4,
`paired_diff_{lite300,ver407}.json`, `identity_gate.log`. Scripts:
`lab/ws2b_identity_gate.py`, `lab/ws2b_paired_diff.py`. Harness:
`--cfamily-ext` passthrough in `parity/region_eval2.py` /
`parity/region_eval_verified.py` (commit `80e9d25`).

## Process anomalies (recorded)

- The primary checkout's shared binary (`roust-rs/target/release/roust`)
  was found stale at `0e7e362` — a WS1b experiment-branch build, not main.
  It was never used and never rebuilt (ops rule); all runs used the pinned
  worktree build. Whoever owns the WS1b run should rebuild before their
  next defaults run.
- The committed Lite reference artifact
  (`agentless_metric_e23_lite300_baseline.json`, 43.33/.52510) predates
  structural-blocks adoption; the working reference 43.67/.52544 was
  confirmed by this round's fresh baseline arm. Same stale-reference
  pattern as the Verified drift finding above — post-adoption references
  now live in `ws2b/` artifacts.
- No runner deaths, no engine errors, no timeouts in any of the four arms
  or the identity gate.
