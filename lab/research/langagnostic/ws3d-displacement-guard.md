# WS3d — anchor/trace displacement guard (#56): general guard NO-GO by mining; fixture-dir guard ADOPTED

**Verdicts:**

- **General anchor/trace displacement guard — NO-GO, by fire-level
  mining.** The WS3b/WS3c loss anatomies do NOT share a
  runtime-computable fire shape that separates them from the adopted
  wins: culprit fires and win-carrying fires are SHAPE-IDENTICAL
  (itemized below — the strongest rule catches 4/6 seeds but suppresses
  4 of the 6 anchor adoption wins). The WS3b-queued "no lexical mass"
  trace rule has an EMPTY population (every trace-firing instance has
  >=1 frame in the base pack). The displacement/win separation is
  CONSEQUENCE-side (what the fire evicts), not fire-side — the only
  clean instance-level separator is the gold-aware oracle "no fired
  frame is gold" (10 hits, both trace seeds, 0 wins), which cannot be
  computed at runtime. Mining tables are the deliverable, per the WS1c
  stop rule.
- **`--displacement-guard` (fixture-dir anchor exclusion) — ADOPTED
  (default ON, PR #68, 2026-08-26, standing language-agnostic
  directive; was ADOPT-RECOMMEND).** `--no-displacement-guard` is the
  escape hatch (reproduces the pre-adoption anchor channel
  byte-identically); the explicit `--displacement-guard` spelling
  remains accepted-but-redundant for harness compatibility. No cache
  re-key (ranking-side only). The one discriminator that separates
  cleanly IN THE DATA: the fired file living under a `*.test/` /
  `*.spec/` DIRECTORY component (jscodeshift codemod fixture
  convention; TESTLIKE_RE only matches `.test.` as a file-name INFIX,
  so these dirs are undamped and anchor-eligible). Across all 306 mined
  fires: 0 win fires matched, 0 gold fires matched anywhere. Arms: jsts
  **LINE 13.97→14.14 (+1/−0, mui-34337 0→1.0), fraction
  .25979→.26156 (+2/−1, mean +0.0018), FILE and FUNCTION identical
  (+0/−0, zero flips on the mutually-judged 579)**; base reproduces the
  post-WS3c reference digit-exact. Every other slice is held by proof,
  not by arms: java/rust structurally inert (fixture census: 0 matching
  trees in 128+239 instances), Lite/Verified inert byte-exactly on the
  entire exposed population (31/31 pytest instances IDENTICAL under the
  micro-gate). Zero adoption wins touched (verified nominally, below).

Engine: branch `ws3d-displacement-guard` @ `82c8d2f` vs main @
`e41c972`. Pinned worktree binaries (`roust 0.2.0 (82c8d2f, clean)` /
`(e41c972, clean)`), private repo copies per arm, detached runs, 10s
stagger, bash launchers (the ws3b zsh word-split trap bit once more —
see anomalies).

## Step 0 — seed anatomies (--explain, current defaults, live state)

`lab/ws3d_seed_explain.py` → `ws3d/seed_explain.{log,json}`; four
configs per seed {default, --no-trace-formats-v2, --no-symbols-v2,
both-off}.

| seed | channel | live? | anatomy under current defaults |
|---|---|---|---|
| sveltejs__svelte-11104 | trace | YES (FILE 0) | 2 non-gold frames (`internal/server/index.js` rank1 +1.0, `legacy/legacy-server.js` +0.5) — both DO carry lexical mass (present in both-off pack). Displacement is SCORE-INFLATION: boost raises `best`, the relative `floor_ratio` cut tightens, rank-31 gold falls out of the ranked list entirely (rank 31 -> None; cov 8/22 -> 0/22) |
| clap-rs__clap-2161 | trace | NO — healed | WS3c seating restored coverage: defaults cov 10/15 + 1/1 == both-off; residual is gold rank 1->2 only. Not a live loss |
| mui__material-ui-34337 | anchor | YES (LINE 0) | two strength-1.0 tail INSERTS on `jss-to-styled.test/first.{actual,expected}.js` (fixture-dir pair defining the same rare symbol); gold stays rank 1 but pass-1 seats eat its budget: cov 6/10 -> 0/10 |
| fasterxml__jackson-databind-4219 | anchor | YES (LINE 0) | 3 non-gold INSERTS (`JsonDeserializer` 2.5-head, `DeserializationConfig` 2.5-head, `DeserializerFactoryConfig` 1.0-tail), all absent from pre-anchor pack; gold rank 1 keeps rank, loses spans: cov 5/5 -> 0/5 |
| clap-rs__clap-4059 | anchor | YES (FUNC F) | non-gold `matched_arg.rs` 1.0-tail INSERT + 2.5 head moves (`action.rs`); gold cov 1/1 -> 0/1 |
| clap-rs__clap-5227 | anchor | YES (LINE 0) | non-gold `resettable.rs` 2.5-head INSERT (zero ranked lexical presence); gold rank 1, cov 2/2 -> 0/2 |

**Mechanism (from `pack_regions`):** pass 1 seats one span per ranked
file UNCONDITIONALLY; anchor-promoted files get a deep
`anchor_cap = budget/10` (~819 tok at 8192) seat. Files already ranked
in the top 10 get NO anchor benefit (promotion fires only on insert or
move-from-rank>=10) — so a rank-1 gold file gets nothing while non-gold
inserted anchors each take up to 819 tokens of pass-1 budget, and
pass-2 (where gold's deep coverage lived) starves. The wins have the
same fire shape but the anchored file IS gold (absent/deep pre-fire) —
gold-ness is the only difference, and it is not runtime-knowable.

## Step 0 — broader-class mining (306 fires / 122 instances)

`lab/ws3d_mine.py` + `lab/ws3d_firelevel.py` from the ws3c itemize
artifacts (all metric-changed instances with --explain anchors) and the
ws3b goldrank jsonls + base packs → `ws3d/mine_fires.json`.

Fire-level discriminator table. "win_supp" = the rule matches a
WIN-CARRYING fire (gold fire inside an itemized adoption win) — an
instance-level count overstates suppression, a guard damps fires:

| rule | seeds caught | wins suppressed | gold-fire collateral (all fires) | loss/gain fires matched |
|---|---|---|---|---|
| (a) test/fixture-shaped fired file | 1 | 0 | 0 | 5/1 |
| (a1) fixture-dir only | 1 (mui-34337) | **0** | **0** | 5/1 |
| (b) weak anchor (strength<2.0) | 3 | **1 (mui-32713!)** | 3 | 63/39 |
| (b2) weak AND insert | 3 | 1 | 3 | 63/39 |
| (c) trace fire w/ no frame in base pack | 0 — EMPTY population | – | – | – |
| (e) any anchor insert (no ranked presence) | 4 | **4 of 6** (3509, 3129, 5015, 32713) | 14 | 105/72 |
| (f) strong insert (>=2.0 head) | 2 | **3** | 11 | 42/33 |
| (d/oracle) no fired frame is gold | 2/2 trace | 0 | – | 10 hits: 2 loss, 8 neutral — CLEAN but gold-aware |

Shape-identity, concretely: jackson-4219's culprits
(`JsonDeserializer.java` 2.5/insert/head) vs jackson-3509's win
(`LogicalType.java` 2.5/insert/head), mockito-3129's win (`MockUtil.java`
2.5/insert/head); mui-34337's culprits (1.0/insert/tail) vs mui-32713's
win (`createMixins.js` 1.5/insert/tail, rank None -> FILE+LINE 1.0).
Any fire-shape rule that catches the former kills the latter.

The (a1) matches: mui-34337 x2 + mui-34548 (`theme-spacing.test/` x2,
FILE 0.67->0) + mui-35178 (`theme-spacing.test/large-actual.js` at
**2.0-head** — so the guard must be shape-based, not strength-based) as
losses; one gain-instance touch (mui-31172) whose gain is carried by
its non-fixture 2.5-move + 2.0-head fires. Trace channel: the only
matching fire is dubbo-7041's `ReflectUtilsTest.java` frame2 (testlike
proper, not fixture-dir; and that instance's WIN is carried by its gold
frame1) — the guard is anchor-only, trace untouched.

## The change (flag-gated `--displacement-guard`, default OFF — NOT flipped)

`roust-rs/src/core.rs`: `FIXTURE_DIR_RE` = `(?i)(^|/)[^/]+\.(test|spec)/`
(deliberately NOT merged into TESTLIKE_RE, which feeds the impl-prior
damp + testbridge — widening it would change adopted defaults);
`extract_symbol_anchors` skips matching def files under the flag,
AFTER the <=3-definers rarity gate (no new symbols become
anchor-eligible; ranking-side only — fixture files stay indexed and
lexically rankable). `main.rs`: `--displacement-guard` +
process-global setter (the symbols-v2 pattern). Harness passthrough in
`parity/region_eval{2,_verified,_full}.py`.

Tests (suite 97/97 green): `fixture_dir_path_shapes` unit (the three
mined shapes match; `.test.` infix / plain `test/` / `latest`-style
lookalikes don't); `tests/displacement_guard.rs` CLI pair
(process-isolated, the symbols-v2 convention): (1) a synthetic
mui-34337 — fixture pair anchor-promoted at defaults, excluded under
the guard, non-fixture anchor untouched; (2) byte-identity of guard-ON
vs defaults on a fixture-dir-free tree with a live non-fixture anchor.

## Gates

**Identity gate (PASS 17/17, 0 flag-differs)** —
`lab/ws3d_identity_gate.py`, `ws3d/identity_gate.log`: MAIN(e41c972)
vs BRANCH(82c8d2f) defaults byte-identity (retrieval-payload md5, two
runs each, cold `.roust`) on the WS3b 17-instance mixed pool, 0
failures; gate B guard-ON determinism 17/17 + 0 guard-differs on the
pool (informational).

**Fixture-dir tree census (`lab/ws3d_fixture_census.py`,
`ws3d/fixture_census.log`)** — the guard can only change output on an
instance whose checked-out tree contains a `*.test/`/`*.spec/` path
(otherwise `extract_symbol_anchors` is structurally identical), checked
EXACTLY per instance via read-only `git ls-tree -r <base_commit>`:

| slice | matching instances | consequence |
|---|---|---|
| java (128) | **0** | guard structurally inert — no arms needed |
| rust (239) | **0** | guard structurally inert — no arms needed |
| go (428) | **0** | ditto (census extended at adoption; go-zero via blob-less bare clone) |
| c (128) | **0** | ditto |
| cpp (129) | **0** | ditto |
| Lite (300) | 15 (all pytest, all `extra/setup-py.test/setup.py`) | 31-instance byte-compare micro-gate |
| Verified (407) | 16 (same single path) | ditto |
| jsts (580) | 174 (mui codemod fixture trees) | full base+guard arms |

**Python micro-gate (PASS 31/31 IDENTICAL, 0 determinism failures)** —
`lab/ws3d_python_microgate.py`, `ws3d/python_microgate.log`: defaults
vs `--displacement-guard`, two runs each, cold `.roust`, on every
fixture-dir-bearing Lite/Verified instance. pytest's lone
`setup-py.test/setup.py` never wins an anchor: the Python hold is
byte-exact on the entire exposed population. Combined with the census,
Lite/Verified/java/rust references stand without rerunning full arms —
the reduced grid this round ran is {jsts base, jsts guard} + census +
micro-gate.

## MSWE jsts arms (region_eval_full, 82c8d2f, defaults vs --displacement-guard)

Both arms 580/580 rows, 579 error-free (the one persistent
engine-error instance, unchanged convention). Scored by
`ws3d/score_all.sh` (agentless_metric_full + tree-sitter wheels +
--repos-dir — the WS3a FUNCTION lesson).

| slice (n) | arm | FILE | FUNCTION | LINE | fraction |
|---|---|---|---|---|---|
| jsts (580) | base | 46.38 | 31.21 | 13.97 | .25979 |
| | guard | 46.38 | 31.21 | **14.14** | **.26156** |

Base reproduces the post-WS3c jsts reference DIGIT-EXACT. Paired stats
(`ws2_paired_stats.py`): FILE +0/−0; LINE +1/−0; fraction +2/−1 (mean
+0.0018); FUNCTION +0/−0 with ZERO per-instance flips (mutually-judged
n=579). The guard is surgical: 3 metric-changed / 14 pack-only-changed
/ 563 byte-stable instances.

Itemization (`ws3d/itemize_jsts.txt`, --explain anchor reruns):

| instance | anchors removed | outcome |
|---|---|---|
| mui-34337 (SEED) | both `jss-to-styled.test/` 1.0-tails (guard anchors = []) | **LINE 0→1.0, frac 0→1.0** — full recovery, FUNC held True |
| mui-35178 | `theme-spacing.test/large-actual.js` 2.0-HEAD (legitimate `extendTheme.ts` 2.5-head kept) | **LINE .385→.538, frac .123→.162** — exact return to its pre-WS3c values |
| mui-31172 | `variant-prop.test/` 1.5-tail — slot REFILLED by next tail candidate (`Unstable_TrapFocus.js` 1.0) | frac .341→.327 — small give-back on a WS3c-gain instance whose gain is carried by its non-fixture 2.5-move/2.0-head anchors (those keep it above its pre-WS3c base at LINE) |

mui-34548, honestly: pack-only under the guard (its fixture tails ARE
removed) but no metric recovery — that loss is co-driven by two
2.5-head `makeStyles` inserts the guard correctly leaves alone (they
are win-shaped; any rule catching them kills jackson-3509/mockito-3129).
Mining "caught" ≠ "recovers" there; 2 of the 3 fixture-loss instances
recover fully.

**Win verification (nominal, per the round charter):** mui-32713 frac
1.0 HELD (pack sheds non-gold fixture files, gold coverage intact),
dayjs-1953 + mui-32182 byte-identical, svelte-11104 unchanged (trace,
out of guard scope); jackson-3509 / mockito-3129 / jackson-4013 /
jackson-4325 / jackson-4360 / dubbo-7041 (java) and clap-5015 /
clap-3212 / clap-4474 (rust) held by structural inertness (census: 0
fixture-dir trees in either slice); java's 18 zero-anchor WS3c fires
likewise. All 14 pack-only diffs are mui fixture-bearing instances,
non-gold churn only. Zero suppressed wins.

## Adoption + rebaseline record (2026-08-26)

- **Default flip** (adoption commit on this branch): main.rs sets the
  guard ON unless `--no-displacement-guard`; mutual-exclusion check;
  the core.rs library initializer stays `false` (the SYMBOLS_V2
  unit-test convention). `tests/displacement_guard.rs` reworked for
  default-ON (escape hatch reproduces the pre-adoption assertions; the
  redundant old spelling asserted byte-equal to defaults); suite 97/97.
- **Default flip proofs** (`lab/ws3d_adoption_gate.py`,
  `ws3d/adoption_gate.log`; retrieval-payload md5, two runs per config,
  cold `.roust`): (A) NEW defaults == OLD(82c8d2f) with explicit
  `--displacement-guard` on ALL 17 changed jsts instances (3 metric +
  14 pack-only — the entire changed population, not a sample);
  (B) NEW defaults == OLD defaults on 12 Lite instances (one per repo,
  pytest deliberately included: its instances are the whole Python
  fixture-dir exposure, and the micro-gate proved the guard inert on
  them, so there is NO expected differ class — any mismatch fails);
  (C) NEW `--no-displacement-guard` == OLD defaults on the same 17.
  **Results: 0 failures (A 17/17, B 12/12, C 17/17).**
- **New reference**: jsts **46.38 / 31.21 / 14.14 / .26156**
  (`agentless_metric_ws3d_jsts_guard.json`) supersedes the WS3c jsts
  reference (46.38/31.21/13.97/.25979, now the escape-hatch state).
  ALL other references stand unchanged, by proof rather than by arms:
  java (49.22/35.16/14.84/.39691) and rust (60.25/19.67/7.53/.24315)
  carry zero fixture-dir paths in any evaluated tree (census 0/128,
  0/239); Lite (92.33/54.67/44.00/.52728) and Verified
  (92.38/47.17/35.14/.47635) are byte-identical on their entire
  31-instance exposed population (micro-gate) and untouched elsewhere
  by construction; go (0/428), c (0/128) and cpp (0/129) are
  structurally inert by the same census, extended at adoption to all
  eight slices (`fixture_census.log`; the missing go-zero clone was
  restored as a blob-less bare clone for the ls-tree reads). README
  scoreboard (JS/TS row + note 6) and CHANGELOG updated in the
  adoption commit.

## Anomalies / notes

- The zsh word-splitting launcher trap (ws3b anomaly) recurred on the
  first jsts arm launch (`nohup $UV ...` under zsh passes one giant
  argv); relaunched via `ws3d/launch_jsts.sh` under bash. No data
  impact (the failed launches wrote nothing).
- clap-2161 is listed as a WS3d seed but is not a live loss: WS3c's
  seating rescue (LINE .5->1.0) already covers it; its only residual is
  gold rank 1->2 with coverage intact.
- svelte-11104's parquet gold (`transform-server.js` + changeset) differs
  from the ws3b goldrank itemization's resolved-frame gold view; the
  mining used the goldrank rows, the seed smoke the parquet — both agree
  the instance is a live FILE loss and both frames are non-gold.
- The general guard's future, if reopened: the mechanism analysis points
  CONSEQUENCE-side — e.g. floor-protection on pre-boost lex_picks
  survivors (svelte-11104's eviction), or seat-budget caps for inserted
  anchors (jackson-4219's 3x819-token seats). Both change behavior on
  Python trace/anchor instances (the E11b/anchor channels are Python
  defaults), so they need full Lite/Verified revalidation — deliberately
  out of scope for a 1-seed (trace) / 3-seed (anchor, wins-entangled)
  live population.

## Artifacts

- `lab/results_regions/ws3d/`: `seed_explain.{log,json}`,
  `seed_guard.{log,json}`, `mine_fires.json`, `identity_gate.log`,
  `fixture_census.log`, `python_microgate.log`,
  `mswe_jsts_ws3d_{base,guard}.jsonl` + logs,
  `agentless_metric_ws3d_jsts_{base,guard}.{json,log}`,
  `itemize_jsts.txt`, `launch_all.sh` (full-grid reference),
  `launch_jsts.sh` (reduced grid actually run), `score_all.{sh,log}`;
  pinned binaries `roust_{e41c972,82c8d2f}_pinned` on disk (untracked,
  per convention)
- miners/gates: `lab/ws3d_seed_explain.py`, `lab/ws3d_mine.py`,
  `lab/ws3d_firelevel.py`, `lab/ws3d_identity_gate.py`,
  `lab/ws3d_fixture_census.py`, `lab/ws3d_python_microgate.py`,
  `lab/ws3d_itemize.py`
- engine: `roust-rs/src/core.rs` (`FIXTURE_DIR_RE`, guard statics,
  anchor filter), `main.rs` (flag), `tests/displacement_guard.rs`
