# E26 — does widening the indexed extension set recover gold roust cannot reach at any rank?

Campaign #56 follow-on (language-agnostic directive), campaign #4 wave 6.
Engines: `roust 0.3.2 (fcb2562)` unguarded and `roust 0.3.2 (11a8a2f)` guarded.
**No default was flipped.**

## Question

Python's gold files are ~100% indexable (Lite 0.0% unindexed, Verified 0.2%).
Every other slice has gold roust cannot retrieve at ANY rank, because the file
type is never indexed. Most of that mass is docs/config, which WS1 already
measured as net-harmful to index (FILE 46.4 → 31.2). What remains is real
source code in languages the allowlist never covered. `--ext-v2` (default OFF)
adds `.rb .pony .svelte .mjs .cjs .cts .mts .vue .scala .php`.

Two questions, and the second turned out to matter more than the first:

1. How much of the unreachable-gold ceiling does indexing those suffixes close?
2. What does admitting them **cost** in displacement, on slices that have no
   such gold to gain?

## Method

* **Same-commit pairing.** Every comparison is against E25's `_def` arms at
  `abb96af`. That reuse is licensed, not assumed: the `abb96af..5ebd6ab`
  engine diff is *flag-gated only* — a `:e2` cache marker, one `||` clause in
  `code_suffix_allowed`, and the arg wiring — so with the flag off the engine
  is byte-identical and those defaults are a valid same-engine default side.
* **Pinned binaries, private clones.** Unguarded arms on `fcb2562`, guarded on
  `11a8a2f`, each built once in its own worktree, one private repo dir per arm
  (issue #41). The guarded arms got FRESH copies of the `_base` clones with
  `.roust` removed — see Anomalies for why that was necessary.
* **Provenance.** Every unguarded arm was captured carrying `--ext-v2` in live
  process argv (`argv_raw.txt`); every record in every arm carries
  `engine_sha` and `ext_v2` (`fcb2562`/`11a8a2f`, `True`). The Python arms print
  `EXTRA_ENGINE_FLAGS`. Without this, "no change" and "flag never passed" are
  indistinguishable — the E25 lesson.
* **Scoring.** `lab/agentless_metric_full.py --repos-dir --ts-functions
  --lang-functions` for the non-Python slices; `agentless_metric_v4.py` /
  `agentless_metric_verified.py` for Python. Never `lab/agentless_metric.py`,
  which ignores CLI args.
* **Stats.** Exact McNemar (binomial, two-sided) per all-or-nothing metric;
  Wilcoxon signed-rank on the per-instance line fraction.

Artifacts in `lab/results_regions/e26/`. Analysis: `lab/e26_census.py`,
`lab/e26_paired.py`, `lab/e26_scoreboard.py`, `lab/e26_tables.py`.

## Scoping census — measured, not assumed

Arms were scoped from a census of gold-file suffixes and of what each base
commit actually contains (`lab/e26_census.py`), which corrected the brief twice.

| slice | gold files | EXT_V2 gold | by suffix | base commits containing any EXT_V2 file |
|---|---|---|---|---|
| c | 584 | **109** (18.7%) | `.pony` 109 | ponyc 81/81 |
| java | 379 | **32** (8.4%) | `.rb` 32 | logstash 38/38 |
| jsts | 3511 | **7** (0.2%) | `.svelte` 5, `.mjs` 1, `.cts` 1 | svelte 242/242, vue 44/44, axios 4/4, mui 82/166 |
| rust | 1165 | **0** | — | ripgrep 14/14, bat 10/10 |
| cpp | 723 | **0** | — | simdjson 20/20 |
| go | 1646 | **0** | — | **0 of 367** |
| python Lite / Verified | 300 / 530 | **0 / 0** | — | sympy only, 5/74 and 6/53 |

**go was not run, and the census is the proof.** Not merely "no repo currently
contains one": zero EXT_V2 files exist in the tree at *any* of the 367 distinct
base commits covering all 428 instances. (One `.mjs` exists in cli/cli's history
under `.github/`, absent from every base commit.) The flag cannot change a byte.

**rust and cpp have zero EXT_V2 gold**, so they cannot gain FILE at all. That
makes them the round's most valuable arms, not its least: they measure pure
displacement cost, with no upside to mask it.

## Result — the three-column table

| slice | n | arm | FILE | FUNCTION (exact) | LINE | line frac |
|---|---|---|---|---|---|---|
| **jsts** | 580 | default | 46.38 (269) | 31.21 (181) | 14.14 (82) | 0.26156 |
| | | --ext-v2 | 41.21 (239) | 31.55 (183) | 13.97 (81) | 0.25970 |
| | | *delta* | *-5.17* | *+0.34* | *-0.17* | *-0.00186* |
| | | **+guard** | 43.62 (253) | 31.03 (180) | 13.97 (81) | 0.25874 |
| | | ***delta*** | ***-2.76*** | ***-0.18*** | ***-0.17*** | ***-0.00282*** |
| **java** | 128 | default | 49.22 (63) | 35.16 (45) | 14.84 (19) | 0.39691 |
| | | --ext-v2 | 49.22 (63) | 36.72 (47) | 14.06 (18) | 0.41843 |
| | | *delta* | *+0.00* | *+1.56* | *-0.78* | *+0.02151* |
| | | **+guard** | 49.22 (63) | 36.72 (47) | 14.06 (18) | 0.41522 |
| | | ***delta*** | ***+0.00*** | ***+1.56*** | ***-0.78*** | ***+0.01831*** |
| **c** | 128 | default | 46.88 (60) | 28.12 (36) | 10.94 (14) | 0.20217 |
| | | --ext-v2 | 51.56 (66) | 28.12 (36) | 13.28 (17) | 0.22576 |
| | | *delta* | *+4.68* | *+0.00* | *+2.34* | *+0.02359* |
| | | **+guard** | **51.56 (66)** | 28.12 (36) | **13.28 (17)** | 0.22513 |
| | | ***delta*** | ***+4.68*** | ***+0.00*** | ***+2.34*** | ***+0.02297*** |
| **rust** | 239 | default | 60.25 (144) | 19.67 (47) | 7.53 (18) | 0.24315 |
| | | --ext-v2 | 60.25 (144) | 19.67 (47) | 7.53 (18) | 0.24287 |
| | | *delta* | *+0.00* | *+0.00* | *+0.00* | *-0.00028* |
| **cpp** | 129 | default | 65.89 (85) | 17.83 (23) | 6.98 (9) | 0.29866 |
| | | --ext-v2 | 65.89 (85) | 17.83 (23) | 6.98 (9) | 0.29880 |
| | | *delta* | *+0.00* | *+0.00* | *+0.00* | *+0.00014* |

| slice | arm | McNemar (def-only/arm-only, p) and Wilcoxon | changed |
|---|---|---|---|
| jsts | --ext-v2 | FILE 33/3, **p=0.0000** · FUNC 3/5, p=0.7266 · LINE 3/2, p=1.0000 · frac 25up/28down, p=0.2269 | 84/580 |
| jsts | +guard | FILE 17/1, **p=0.0001** · FUNC 3/2, p=1.0000 · LINE 2/1, p=1.0000 · frac 9up/22down, **p=0.0071** | 43/580 |
| java | --ext-v2 | FILE 0/0, p=1.0000 · FUNC 1/3, p=0.6250 · LINE 1/0, p=1.0000 · frac 12up/7down, p=0.0533 | 19/128 |
| java | +guard | FILE 0/0, p=1.0000 · FUNC 1/3, p=0.6250 · LINE 1/0, p=1.0000 · frac 8up/9down, p=0.3317 | 17/128 |
| c | --ext-v2 | FILE 2/8, p=0.1094 · FUNC 2/2, p=1.0000 · LINE 0/3, p=0.2500 · frac 15up/5down, **p=0.0124** | 27/128 |
| c | +guard | FILE 2/8, p=0.1094 · FUNC 2/2, p=1.0000 · LINE 0/3, p=0.2500 · frac 14up/7down, **p=0.0190** | 28/128 |
| rust | --ext-v2 | all p=1.0000; frac 1up/1down | 2/239 |
| cpp | --ext-v2 | all p=1.0000; frac 1up/0down | 1/129 |

## Ceiling recovery and displacement

**The premise is confirmed exactly: the default arm retrieved 0 of all 148
EXT_V2 gold files.** They were unreachable at any rank.

| slice | arm | EXT_V2 gold | default got | arm got | ceiling closed | non-ext gold lost | gained |
|---|---|---|---|---|---|---|---|
| jsts | --ext-v2 | 7 | 0 | 1 | 14.3% | 88 | 27 |
| jsts | +guard | 7 | 0 | 1 | 14.3% | 46 | 3 |
| java | --ext-v2 | 32 | 0 | 13 | 40.6% | 3 | 0 |
| java | **+guard** | 32 | 0 | **17** | **53.1%** | 3 | 0 |
| c | --ext-v2 | 109 | 0 | 21 | 19.3% | 10 | 9 |
| c | **+guard** | 109 | 0 | **22** | **20.2%** | 14 | 5 |
| rust / cpp | --ext-v2 | 0 | 0 | 0 | n/a | 0 | 0 |

The guard does not merely reduce cost — on java it **raises** recovery, 13 → 17
of 32 (40.6% → 53.1%). Excluding fixture `.rb` stops fixtures from crowding
real `.rb` gold out of the budget. c gains 21 → 22.

**Attribution is unambiguous.** Every FILE regression, guarded and unguarded,
is one repo:

| arm | non-ext gold lost, by repo | FILE 1→0 | FILE 0→1 |
|---|---|---|---|
| jsts --ext-v2 | svelte 87, axios 1 | svelte 33 | svelte 2, vue 1 |
| jsts +guard | svelte 45, axios 1 | **svelte 17** | vue 1 |
| c +guard | ponyc 14 | ponyc 2 | **ponyc 8** |
| java +guard | logstash 3 | none | none |

The guard halves svelte's damage (88 → 46 gold lost, 33 → 17 FILE regressions)
but does not cure it: jsts FILE is still −2.76 at **p=0.0001**, and the guarded
line fraction is now significantly *negative* (p=0.0071, 9 up / 22 down).
sveltejs/svelte ships 2,927 `.svelte` files for 5 gold ones; the guard removes
the ~2,617 under test/fixture paths (code corpus 4,951 → 2,334, measured
independently from the cache manifest), and the ~300 that remain are still
enough to lose 17 files that the default arm retrieved.

## Python — provably untouched

Not asserted from the census, measured. sympy is the only Python-bench repo
containing an EXT_V2 file (`bin/test_pyodide.mjs`, 1 file, present in 5/74 Lite
and 6/53 Verified base commits), and zero Python gold carries an EXT_V2 suffix.
The check ran **every** sympy instance (77 Lite, 53 Verified) plus 11 non-sympy
controls each, flag OFF and ON, **twice per arm** — the repeat being the
determinism control that makes payload identity mean something.

**All 6 pairwise comparisons are payload-identical: Lite 88/88, Verified 64/64.**
That includes off_a/off_b and on_a/on_b (determinism) and every off-vs-on pair.
Flag provenance: ON logs print `EXTRA_ENGINE_FLAGS=['--ext-v2']`, OFF print `[]`.

## Goal scoreboard — stratified by gold-file count

**SWE-bench Lite is 300/300 single-gold-file instances.** Its headline 92.33 was
therefore never an aggregate over a mixed workload, and comparing another
slice's aggregate to it has been comparing different problems. The honest
comparison is stratum to stratum. Config: c and java under `--ext-v2` + guard,
everything else default.

| slice | arm | all | 1 gold | 2 gold | 3+ gold |
|---|---|---|---|---|---|
| | | FILE/FUNC/LINE | FILE/FUNC/LINE | FILE/FUNC/LINE | FILE/FUNC/LINE |
| **python Lite** | default | 92.33/54.67/44.00 (n=300) | **92.33/54.67/44.00** (n=300) | — (n=0) | — (n=0) |
| **python Verified** | default | 92.38/47.17/35.14 (n=407) | **95.83/53.57/41.07** (n=336) | 81.63/22.45/8.16 (n=49) | **63.64**/4.55/4.55 (n=22) |
| cpp | default | 65.89/17.83/6.98 | **100.00**/34.04/19.15 (n=47) | 88.89/7.41/0.00 (n=27) | 25.45/9.09/0.00 (n=55) |
| rust | default | 60.25/19.67/7.53 | **97.56**/39.02/21.95 (n=82) | 67.31/11.54/0.00 (n=52) | 27.62/8.57/0.00 (n=105) |
| java | ext-v2+guard | 49.22/36.72/14.06 | **94.12**/52.94/35.29 (n=51) | 18.92/43.24/0.00 (n=37) | 20.00/10.00/0.00 (n=40) |
| go | default | 64.95/28.97/16.59 | 88.30/53.19/31.38 (n=188) | 75.26/19.59/11.34 (n=97) | 27.27/3.50/0.70 (n=143) |
| c | ext-v2+guard | 51.56/28.12/13.28 | **78.79**/43.94/25.76 (n=66) | 75.00/18.75/0.00 (n=16) | 4.35/8.70/0.00 (n=46) |
| jsts | default | 46.38/31.21/14.14 | 72.50/41.79/26.43 (n=280) | 48.39/26.88/5.38 (n=93) | 10.14/18.84/1.45 (n=207) |

Read stratum 1 and the "language gap" largely disappears: **cpp 100.0, rust
97.6, python-Verified 95.8 and java 94.1 all beat python-Lite's 92.3**, with go
88.3 close behind. c is the round's biggest single move here, 69.70 → **78.79**
(+9.09) — the coverage hole closing.

Read stratum 3+ and the real gap appears, and it is not coverage:
python-Verified 63.64 against 27.62 (rust), 27.27 (go), 25.45 (cpp), 20.00
(java), 10.14 (jsts), 4.35 (c). Every non-Python slice collapses on multi-file
instances while Python degrades gently. **The remaining distance to
"Python-level" is a ranking and budget problem on multi-gold-file instances,
not an indexing-coverage problem** — everywhere coverage has been fixed.

## Verdict — per extension, not per flag

The flag is one switch over ten suffixes, but the evidence separates cleanly,
because each slice's EXT_V2 mass is a single suffix: java's is *only* `.rb`
(580 files, logstash), c's is *only* `.pony` (165, ponyc). The java and c arms
therefore already **are** the `.rb`-only and `.pony`-only measurements.

* **`.pony` — SHIP, with the guard.** FILE **+4.68** (46.88 → 51.56), LINE
  **+2.34**, line fraction +0.02297 (Wilcoxon **p=0.0190**), FUNCTION flat.
  22 of 109 unreachable gold files recovered; FILE +8/−2 within ponyc.
* **`.rb` — SHIP, with the guard.** FILE invariant (no risk taken), FUNCTION
  **+1.56**, fraction +0.01831. Ceiling recovery 53.1% — the best of the round,
  and it *improves* under the guard. Cost is 3 gold files, zero FILE flips.
* **`.svelte` — DROP.** The only significant harm in the round, and it survives
  the guard: FILE −2.76 at **p=0.0001**, fraction significantly negative
  (p=0.0071), for 1 of 7 gold files recovered. All 17 FILE regressions are
  sveltejs/svelte.
* **`.mjs .cjs .cts .mts .vue .scala .php` — DROP for now, as unmeasured.**
  Their only gold is 2 files in jsts (1 `.mjs`, 1 `.cts`), neither recovered.
  rust/cpp show them inert (2 and 1 changed instances, zero gold displaced), so
  there is no evidence of harm — but equally none of benefit. Shipping them
  would be adding surface with no measurement behind it.

Recommendation: narrow `EXT_V2_EXTENSIONS` to `.rb` + `.pony`, keep the fixture
guard, keep the flag default OFF pending a Python + Lite/Verified revalidation
of the narrowed set. **No default flipped in this round.**

## Anomalies and lessons

1. **A membership-changing flag must re-key the cache.** `--ext-v2` and its
   guarded successor both wrote the key marker `:e2` while indexing *different*
   corpora, so a guarded binary could serve itself an unguarded corpus. Found by
   reading `cache_key`, not by observing a failure. Fixed on main as `:e2g`
   (00649b9). WS2c's `:cf1` is the precedent that got it right.
2. **The corpus walk and the manifest scan must use the SAME predicate.** Two
   bugs, both found from the cache manifest (`manifest_census.txt`):
   the manifest's `exts` set never included the EXT_V2 suffixes (0 of svelte's
   2,927 `.svelte` files listed, though the corpus ranked over them); and
   b0cf3a9's guard hook evicted all 428 docs entries (427 `.md`, 1 `.txt`)
   because `path_indexable` answers "is this code" and knows nothing of
   `DOCS_EXTENSIONS`. Both fixed on main (c338745).
3. **The signature of that divergence is warm-vs-cold nondeterminism, not an
   error.** A warm cache written by an affected build returns different
   retrieval output than a cold rebuild, silently — astropy and pytest
   disagreed between binaries until `.roust` was wiped. That is the concrete
   user-facing cost, and it is why this class of bug must be caught by reading
   the predicates rather than by waiting for a failure.
4. **None of this affects the round's numbers.** The harness runs
   `git checkout -f` + `git clean -fdq` per instance and `.roust` is not
   gitignored (both verified), so every corpus was built cold and the manifest
   is only consulted on a warm cache. The guard was separately shown not to
   disturb docs in the *corpus*: `docs_avg_len` (286.62060889929745) and
   `docs_df` (9,916 terms) are identical between arms.
5. **Binary vs main.** The guarded arms ran `11a8a2f`, which differs from main
   only in carrying the `:e2` marker rather than `:e2g`, and predates c338745's
   manifest fixes. Same admission rule, same retrieval, cold corpora — not a
   provenance mismatch.
6. **Reproduce a surprising red result two ways before believing OR dismissing
   it.** A "0/N defaults identity" scare had two distinct causes at different
   times: first a broken shell conditional (`A && B || C` in an identity loop —
   use explicit if/else), later the genuine stale-cache effect above. The real
   bug was nearly dismissed as the shell artifact already seen.
7. **Scope arms from a census, not from a list of languages that exist.** The
   census killed the go arms outright (provably inert across 367 base commits),
   replaced a 707-instance Python arm with a 152-instance targeted identity
   check, and predicted in advance that rust and cpp could only measure cost.
