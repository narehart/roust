# WS3c — structural-symbol unification (#56, audit findings 3+6)

**Verdict: ADOPTED (default ON since `3984d33`, PR #67, 2026-08-26,
standing language-agnostic directive; was ADOPT-RECOMMEND).**
`--no-symbols-v2` is the escape hatch (reproduces the pre-adoption
engine byte-identically); `--symbols-v2` remains accepted-but-redundant
for harness compatibility. Round evidence: The two
slices where the def/anchor channel was absent or blind gain at every
region level with FILE positive: java FILE 47.66→49.22 (+2/−0), FUNCTION
34.38→35.16 (+2/−1), LINE 14.06→14.84 (+1/−0), fraction +0.0037; jsts
FILE 46.21→46.38 (+1/−0), FUNCTION 30.86→31.21 (+4/−2), LINE 13.45→13.97
(+4/−1), fraction +0.0021. rust is FILE-positive (+1/−0), fraction
+0.0013, LINE flat, with a FUNCTION −2 (+0/−2, p=.5) displacement cost.
Python holds exactly: all four metrics identical PER INSTANCE on
Lite-300 and Verified-407 (zero metric-field diffs; 28+51 instances
repack non-gold content only). Known cost, measured and itemized: weak
(strength-1.0) anchors on non-gold files can displace budget from gold
regions — the WS3b no-gold-frame anatomy, now in a second channel; a
strength/testlike anchor guard is the queued follow-up.

Engine: branch `ws3c-symbols` @ `10967da` vs main @ `8d86875`. All arms
pinned-worktree binaries (`roust 0.2.0 (10967da, clean)`; gate A proves
defaults == `(8d86875, clean)`), private repo dirs per arm, detached
runs, 10s stagger.

## The change (flag-gated `--symbols-v2`, default OFF)

`roust-rs/src/core.rs`:

- **def_index from the tree-sitter walks (finding 6).** For every
  grammar-covered non-Python file, `def_symbols_with` UNIONs the legacy
  per-extension def regex scan with symbol names captured from the SAME
  pinned CST walks that produce structural block spans (`sitter_def_walk`
  reuses each language's `*_header_start` allowlist + hoisting, adding
  per-family name extraction: JS/TS declaration names, declarator-bound
  arrow functions, object-literal methods/pairs, class fields; Java
  class/interface/enum/record/annotation/method/constructor names; Go
  func/method + grouped type names; Rust fn/struct/enum/trait/union/
  mod/macro + impl'd type base names; C/C++ function-definition
  declarator descent (qualified `Foo::bar` unwraps to the method name),
  typedef/struct/class/namespace/preproc-macro names). Java and the C
  family gain a def/anchor channel for the FIRST time; JS arrow
  functions stop being invisible. Union (not replace) means a parse
  failure can only miss additions, never lose regex-baseline symbols.
  Python's extraction is byte-identical by construction (never takes the
  sitter branch). `Corpus::update_files` mirrors the same set, so
  incremental cache updates agree with fresh builds. Cache key gains
  `:sv2` (def_index contents change at build time).
- **Anchor-forced seating un-gated from `.py` (finding 3).**
  `pack_regions`' seat lookup now accepts any grammar-covered file,
  taking def lines from `structural_def_entries` — the (line, name)
  pairs derive from the same hoisted header starts as the candidate
  spans, so the line==span-start match holds by construction
  (unit-proven). Flag-off, non-Python files `continue` exactly as
  before.

Harness: `--symbols-v2` passthrough in `parity/region_eval2.py`,
`region_eval_verified.py`, `region_eval_full.py`.

## Gates

**Gate 2 — unit + CLI fixtures (PASS, suite 94/94).** 7 unit tests:
arrow/object-method/class-field JS entries, Java methods+constructors,
Rust impl fns (+ the bodyless-trait-signature case the regex union still
covers), C++ inline + out-of-line `Foo::bar` methods, Python/grammarless
empty, flag-off == regex byte-equality, and def-entry lines ==
structural span starts (the seating precondition). 2 CLI-level tests
(`tests/symbols_v2.rs`, process-isolated because the flag is a CLI
process-global): a buried JS arrow definition and a buried Java method
are invisible at defaults, and under `--symbols-v2` are anchor-promoted
with the symbol's OWN block seated over an in-file decoy region that
wins on generic term density.

**Gate 1/A — defaults byte-identity vs main (PASS 17/17).**
MAIN(8d86875) vs BRANCH(10967da), two runs each, retrieval-payload md5,
cold `.roust`, on the WS3b mixed pool (6 Lite python, 4 jsts, 3 rust,
2 cpp, 2 java). 0 failures (`ws3c/identity_gate.log`).

**Gate B — flag-ON determinism (PASS 17/17) + itemization.** Two
`--symbols-v2` runs hash identically on every pool instance. 10/17
differ from defaults under the flag (informational): every differ is
non-Python def_index enrichment reshaping anchors/packs; the one Lite
differ (matplotlib-18869) is itemized below.

## MSWE arms (region_eval_full, branch binary, defaults vs flag)

Baselines reproduce the current references with every drift attributed
to the WS3b default flip adopted AFTER those references were measured:
java base = post-WS3b reference DIGIT-EXACT (47.66/34.38/14.06/.39325);
rust base = reference except fraction .24214→.24181 (the documented
adopted −0.0003 delta); jsts base 46.21/30.86/13.45/.25774 vs pre-WS3b
reference 46.38/31.03/13.28/.25820 = exactly the WS3b micro-arm flips
now in defaults (svelte-11104 FILE+FUNCTION loss, mui-32182 LINE gain),
per-instance verified against the archived e23 arm.

| slice (n) | arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|
| jsts (580) | base | 46.21 | 30.86 | 13.45 | .25774 |
| | v2 | **46.38** | **31.21** | **13.97** | **.25979** |
| java (128) | base | 47.66 | 34.38 | 14.06 | .39325 |
| | v2 | **49.22** | **35.16** | **14.84** | **.39691** |
| rust (239) | base | 59.83 | 20.50 | 7.53 | .24181 |
| | v2 | **60.25** | 19.67 | 7.53 | **.24315** |

Paired stats (`ws2_paired_stats.py`, two-sided exact sign tests):

- **jsts**: FILE +1/−0, LINE +4/−1 (p=.375), FUNCTION +4/−2 (p=.69),
  fraction mean **+0.0020** with sign +18/−34 (p=.036): the gains are
  LARGE (anchor-seated def blocks capture whole gold functions:
  mui-32713 0→1.0, clap-2161-style rescues) while the more numerous
  losses are small budget nibbles from newly-inserted anchor files.
  56/580 metric-changed, 431 repack-only.
- **java**: FILE +2/−0 (p=.5), LINE +1/−0, FUNCTION +2/−1 (p=1),
  fraction +10/−7 (mean +0.0037). 18/128 metric-changed — and ALL 18
  went from ZERO anchors at base to fired anchors under v2 (Java had no
  def channel at all): the purest new-channel slice.
- **rust**: FILE +1/−0, LINE +0/−0, FUNCTION +0/−2 (p=.5), fraction
  +16/−17 (mean +0.0013). 34/239 metric-changed; rust already had a
  def regex, so v2 mostly RESHAPES anchor membership (25/34 changed
  sets, only 1 from-empty) via impl/enum/trait names entering the
  rarity gate.

## Python hold (Lite-300 + Verified-407)

| bench | arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|
| Lite-300 | base (=ref) | 92.33 | 54.67 | 44.00 | .52728 |
| | v2 | 92.33 | 54.67 | 44.00 | .52728 |
| Verified-407 | base (=ref) | 92.38 | 47.17 | 35.14 | .47635 |
| | v2 | 92.38 | 47.17 | 35.14 | .47635 |

Both base arms reproduce the v12 references digit-exact. v2 is NOT
byte-identical (Python repos contain JS/C/C++ files whose def entries
now exist), but the four metric FIELDS are identical on every one of
the 300+407 instances: 28 Lite + 51 Verified instances change PACK
COMPOSITION only — added files are .js/.cpp/.h/.c (63 of 91 additions;
the few .py adds/removes are budget reshuffles), gold ranks and gold
line coverage untouched everywhere. FUNCTION re-scored from the changed
regions confirms the hold: 54.67 / 47.17 digit-exact, ZERO per-instance
FUNCTION flips on either bench. The hold is EMPIRICAL, not
structural: v2 anchors did evict non-gold .py files on ~50 instances
without ever hitting gold — the same displacement potential the loss
itemization below names.

**matplotlib-18869 (the one Lite gate-pool differ), exact mechanism:**
base anchors = [setupext.py 1.5-tail, style/core.py 1.0-tail]; v2 =
[setupext.py 1.5-tail, **src/qhull_wrap.cpp** 1.0-tail] — the C++ file's
new def entries let it outcompete non-gold style/core.py for the second
tail slot; qhull_wrap.cpp enters the pack, style/core.py leaves, one
artist.py span trims under E12b de-escalation (865-891→882-891). Gold
(`lib/matplotlib/__init__.py`) stays rank 1; FILE/LINE/fraction 1.0/0/0
unchanged.

## Itemization highlights (`itemize_{jsts,java,rust}.txt`, anchors from
--explain reruns on every metric-changed instance)

Gains — the query names the symbol, v2's def entry anchors the GOLD file
or seats its block:

| instance | mechanism | outcome |
|---|---|---|
| mui-32713 | gold `createMixins.js` (arrow-fn defs) was NOT in the ranked list at base (rank None); v2 def entry anchors it in at 1.5-tail | FILE 0→1, LINE 0→1, fraction 0→**1.000** |
| jackson-databind-3509 | base anchors []; v2 anchors gold `LogicalType.java` 2.5-head | FILE 0.67→1.0, fraction .125→.292 |
| mockito-3129 | v2 anchors gold `MockUtil.java` 2.5-head + `DefaultMockitoPlugins.java` head-move | FILE →1.0, FUNCTION False→True |
| clap-5015 | v2 anchors gold `parser.rs`+`derive.rs`, displacing base's test-file anchors | FILE 0.67→1.0 |
| jackson-databind-4013 | seating: gold deser block seated | LINE .29→.86, fraction .036→.893 |
| clap-2161 | respans only (seating) | LINE .5→1.0, fraction .28→.56 |

Losses — one shared anatomy (the WS3b no-gold-frame displacement, in
anchor form): a NEW anchor fires on a NON-gold file, head/tail
insertion + budget reallocation squeezes the gold file's packed spans:

| instance | mechanism | outcome |
|---|---|---|
| mui-34337 | two strength-1.0 anchors on codemod TEST-FIXTURE files (`jss-to-styled.test/first.{actual,expected}.js` — dir named `.test/` so TESTLIKE_RE misses it) | LINE 1.0→0, fraction 1.0→0 |
| jackson-databind-4219 | base anchors []; v2 anchors 3 non-gold deser files 2.5-head; gold rank 6→9 | LINE .5→0, fraction .68→0, FUNCTION True→False |
| clap-4059 | non-gold `matched_arg.rs` anchor + respans | fraction .26→0, FUNCTION True→False |
| clap-5227 | non-gold `resettable.rs` 2.5-head anchor; gold rank 15→16 | LINE .33→0, fraction .43→0, FUNCTION True→False |

**Queued follow-up (post-round case-mining seed):** an anchor
displacement guard — candidates: damp strength-1.0 (non-code-span,
lowercase) anchors when the anchored file carries no lexical mass;
extend the testlike predicate to fixture-dir shapes (`*.test/` as a
DIRECTORY component); require anchors to beat the file they evict on
fused score. mui-34337 / jackson-4219 / clap-5227 are the seed cases.
This is the same guard family WS3b queued for trace frames — one guard
may serve both channels.

## Verdict detail

Success criterion: affected slices gain FUNCTION/LINE/fraction with
FILE invariant-or-positive and Python held.

- jsts: FUNCTION +0.35, LINE +0.52, fraction +0.0021, FILE +0.17 — MET.
- java: FUNCTION +0.78, LINE +0.78, fraction +0.0037, FILE +1.56 — MET.
- rust: FILE +0.42, fraction +0.0013, LINE flat, FUNCTION −0.83 — mixed
  (2 displacement losses, 0 gains at function level).
- Python: all four metrics held per-instance on both benches — MET.

ADOPTED on the jsts+java evidence with the rust FUNCTION cost stated
(the WS2 go-caveat precedent: a mixed-positive slice does not block a
campaign-level win when itemized); the shared anchor/trace displacement
guard stays queued as the follow-up round.

## Adoption + rebaseline record (2026-08-26, `3984d33`)

- **Default flip proofs** (`lab/ws3c_adoption_gate.py`,
  `ws3c/adoption_gate.log`; retrieval-payload md5, two runs per config,
  cold `.roust`): (A) NEW(3984d33) defaults == OLD(10967da) with
  explicit `--symbols-v2` on all 19 itemized metric-changed
  jsts/java/rust instances; (B) NEW defaults == OLD defaults on 12 Lite
  Python instances (one per repo) -- rows in the known pack-only differ
  class (matplotlib-18869 expected) are re-checked as NEW defaults ==
  OLD `--symbols-v2` and reported, not failed; (C) NEW
  `--no-symbols-v2` == OLD defaults on the same 19 instances.
  **Results: 0 failures.** Proof A 19/19 OK; proof B 11/12 OK with
  matplotlib-18869 DIFFERS-AS-KNOWN (the itemized pack-only differ:
  NEW defaults == OLD `--symbols-v2` byte-identically, per-config
  determinism held); proof C 19/19 OK.
- **New references**: jsts **46.38 / 31.21 / 13.97 / .25979**
  (`agentless_metric_ws3c_jsts_v2.json`), java
  **49.22 / 35.16 / 14.84 / .39691**
  (`agentless_metric_ws3c_java_v2.json`), rust
  **60.25 / 19.67 / 7.53 / .24315**
  (`agentless_metric_ws3c_rust_v2.json`; FUNCTION carries the stated
  −2-instance displacement caveat -- clap-4059/clap-5227 -- pending the
  displacement-guard round). The post-WS3b jsts base
  (46.21/30.86/13.45/.25774) is formally SUPERSEDED, as is the pre-WS3b
  46.38/31.03/13.28/.25820 it restated. Python Lite/Verified references
  unchanged (all four metrics digit-identical per instance under the
  new default). README scoreboard + CHANGELOG updated in the adoption
  commit.
- **Tests**: `tests/symbols_v2.rs` reworked for default-ON (escape
  hatch reproduces the pre-adoption assertions; the redundant old
  spelling is asserted equal to defaults); suite 94/94.

## Anomalies / notes

- `lab/agentless_metric.py` (Lite scorer) IGNORES `--predictions`/`--out`
  (no argparse; hardcoded stored-predictions path) — it silently scored
  the wrong file on first invocation. Rescored with
  `lab/agentless_metric_v4.py` (argument-driven, the WS3a-provenance
  scorer). score_all.sh in the artifacts dir carries the correction.
- jsts FUNCTION is judged on 579/580 (one persistent engine-error
  instance, unchanged convention); the FUNCTION metric became
  meaningful for JS/TS only after the harness's multi-language
  gold-function extraction (wave5 bonus finding) — base 30.86 is
  consistent with the post-WS3b state of that harness.
- The mui-32182 LINE gain and svelte-11104 FILE/FUNCTION loss that
  WS3b's micro-arm measured under the then-flag are now BASE behavior
  (default flipped at ac0b63f); WS3c's jsts reference should be restated
  as 46.21/30.86/13.45/.25774 for future rounds.
- Anchor firing is far broader than metric movement: 431/580 jsts,
  95/128 java, 179/239 rust instances repack under v2 with zero metric
  change — def-channel churn is mostly metric-neutral budget reshuffling
  at these budgets.

## Artifacts

- arms + logs: `lab/results_regions/ws3c/`
  (`mswe_{jsts,java,rust}_ws3c_{base,v2}.jsonl`,
  `{lite300,ver407}_ws3c_{base,v2}.jsonl`, metric JSONs
  `agentless_metric_ws3c_*.json`, `launch_all.sh`, `score_all.sh`,
  `identity_gate.log`, `itemize_{jsts,java,rust,mpl18869}.txt`)
- gates: `lab/ws3c_identity_gate.py`; itemizer: `lab/ws3c_itemize.py`
- engine: `roust-rs/src/core.rs` (`sitter_def_walk`,
  `structural_def_entries`, `def_symbols_with`, seating block),
  `main.rs` (`--symbols-v2`), `cache.rs` (`:sv2` key marker);
  CLI gate tests `roust-rs/tests/symbols_v2.rs`
