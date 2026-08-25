# WS2 — the grammar batch (Java / Go / Rust / C / C++): five-language MSWE gates

*Campaign #56 workstream 2, replicating the E23 JS/TS template
(`lab/research/wave5/e23-results.md`) across the remaining Multi-SWE-bench
languages. Branch `ws2-grammar-batch` off main `0d8113e` (the E23 adoption
tip); engine + harness commits `fae44f3` / `96b77da` / `aa9cb15`. Gate runs
2026-08-25; baseline arms engine `roust 0.2.0 (0d8113e, clean)` (pinned
worktree build), experiment arms `roust 0.2.0 (aa9cb15, clean)`
(`aa9cb15` differs from the identity-gated `96b77da` by a lab-only commit;
the `roust-rs/` tree is identical). Data: Multi-SWE-bench
(ByteDance-Seed, HF `ByteDance-Seed/Multi-SWE-bench`, arXiv:2504.02605),
fetched per-language via `lab/mswe_adapter.py --langs {java,go,rust,c,cpp}`
— same schema and conversion as `mswe_jsts.parquet` (adapter unchanged).*

## What shipped

**Engine** (`roust-rs/`): the E23 CST walk factored out of `ts_blocks`
verbatim into `sitter_blocks(text, language, header_start)` — parametric
over (grammar, allowlist), same span contract (1-indexed inclusive spans,
leading preamble, header-to-next-same-or-lower-depth partition,
multi-granularity nesting) — plus five per-language allowlists
(`grammar_blocks`):

- **Java** (`tree-sitter-java =0.23.5`): class/interface/enum/record/
  annotation-type declarations, methods, constructors, compact (record)
  constructors, static initializers. Annotations are children of the
  declaration node in this grammar, so decorator folding comes built in.
- **Go** (`tree-sitter-go =0.25.0`): function/method declarations (receiver
  methods included), `type_declaration` (single and grouped `type (...)`).
- **Rust** (`tree-sitter-rust =0.24.2`): fn/impl/trait/struct/enum/union/
  macro-definition items + body-bearing `mod` items; contiguous preceding
  `attribute_item` siblings fold into the span start (python_blocks'
  decorator folding — attributes are siblings, not children, in this
  grammar).
- **C** (`tree-sitter-c =0.24.2`): function definitions, typedefs,
  body-bearing struct/enum/union specifiers (hoisted into wrapping
  typedef/declaration statements; one-header-per-line dedup collapses the
  typedef double-emit), function-like macros (`preproc_function_def`).
- **C++** (`tree-sitter-cpp =0.23.4`): the C set + class specifiers,
  namespaces, template declarations (definitions inside `template<..>`
  hoist to the template line, the JS `export` hoist pattern). `.h` parses
  with the C++ grammar (difftastic's convention).

All five crates are crates.io versions **pinned exactly** against the
already-pinned `tree-sitter =0.26.13` core — no parser.c vendoring needed
(same outcome as E23; the multilang report's a3 vendoring plan remains the
fallback for a future crate/core conflict). Dispatch rides the existing
adopted `--structural-blocks` default (`--no-structural-blocks` reverts
every non-Python language to ±30-line windows).

**`--cfamily-ext` (new flag, default OFF).** The batch's one scope
discovery: `.c/.h/.cc/.cpp/.cxx/.hpp/.hh` were never in `CODE_EXTENSIONS`
— C/C++ files are not indexed by the corpus walk at all, so "window
fallback" was never their baseline; *absence* was. The flag adds the seven
extensions to the walk, the cache manifest scan, and the incremental-update
filter through one shared predicate (`code_suffix_allowed`), and re-keys
the index cache (`:cf1` marker) so flag states can never serve each other's
payloads. Default OFF is forced by the byte-identity contract: Python repos
vendor C sources (numpy/pandas), so default-ON would change Python bundles.
Making it default-ON is a separate, Python-gated experiment (see verdicts).

**Harness twin** (`lab/agentless_metric_verified.py` +
`agentless_metric_full.py --lang-functions`, default OFF): tree-sitter
function-span extraction for the five languages on BOTH the gold and
predicted sides of the exact FUNCTION metric — implementations only
(Java abstract/interface signatures and Go assembly stubs excluded via
body-field checks; Rust trait signatures excluded by node kind; C++
lambdas excluded; Rust attribute folding and C++ template hoisting match
the engine). Python wheels pinned to the engine's exact grammar versions
(`tree-sitter-java==0.23.5`, `tree-sitter-go==0.25.0`,
`tree-sitter-rust==0.24.2`, `tree-sitter-c==0.24.2`,
`tree-sitter-cpp==0.23.4` — all exist on PyPI at crate-matching versions).
`parity/region_eval_full.py` gained `--cfamily-ext` /
`--no-structural-blocks` passthroughs.

## The data (scale report)

Per-language slices built from the HF dataset (all records kept — no
empty-patch skips in any slice), 30 repos, ~1.36 GB of git objects
(GitHub API pre-clone estimate), private per-arm clones under
`lab/ws2_repos/`:

| slice | n | repos (n-dominant first) |
|---|---|---|
| go | 428 | cli/cli 397, grpc-go 16, go-zero 15 |
| rust | 239 | clap 132, tokio 25, tracing 21, ripgrep 14, fd 14, nushell 14, bat 10, bytes 5, rayon 2, serde 2 |
| cpp | 129 | nlohmann/json 55, fmt 41, simdjson 20, Catch2 12, cpp-httplib 1 |
| java | 128 | jackson-databind 42, logstash 38, jackson-core 18, fastjson2 6, mockito 6, others 18 |
| c | 128 | ponyc 82, zstd 29, jq 17 |

Priority order re-verified by n: **Go > Rust > C++ > Java ≈ C** (the spec's
Java-first ordering was based on unverified counts; actual Java n=128).

## The vacuous-FUNCTION retirement, five times over

Computed from the gold patches directly: the pre-WS2 scorer (Python AST +
E23's JS/TS) has an **empty gold function set on 428/428 go, 239/239 rust,
128/128 java, 128/128 c, and 128/129 cpp instances** — any FUNCTION number
previously reported on these slices was ≥99% vacuous. Every FUNCTION
figure below is from the corrected `--lang-functions` scorer (both arms of
every pair scored identically; `--ts-functions` also on). Corrected-scorer
gold coverage: go 425/428, rust 228/239, cpp 123/129, java 125/128,
c 113/128 instances have non-empty gold function sets; empty-gold
instances count correct per Agentless's superset convention (auditable via
`n_gold_functions` in the artifacts — e.g. cpp_main's FUNCTION 4.65 is
exactly its 6 empty-gold instances).

## Results — the five-language table

MSWE-1052, engine arms as above, scorer `--ts-functions --lang-functions`,
unified errors-count-as-wrong convention. Baseline for java/go/rust =
main binary, default flags (window packing for these languages). For
C/C++ the three arms decompose the confound the extension gap forces:
`main` (main binary, defaults — the true current default: nothing
indexed), `idx` (branch, `--cfamily-ext --no-structural-blocks` — indexing
ON, windows), `exp` (branch, `--cfamily-ext` — indexing + structure).
Paired columns are gains/losses with two-sided exact sign tests
(`lab/ws2_paired_stats.py`, the E23 machinery).

### Java (n=128) — baseline arm = corrected baseline
| metric | base | exp | paired |
|---|---|---|---|
| FILE | 47.66 | **47.66** | +0/−0, p=1 — invariant, per-instance identical |
| FUNCTION | 21.88 | **33.59** | +23/−8, p=0.011 |
| LINE | 13.28 | **14.06** | +11/−10, p=1 (ns) |
| fraction | .2385 | **.3932** | +.1548, +51/−29, p=0.018 |

### Go (n=428)
| metric | base | exp | paired |
|---|---|---|---|
| FILE | 63.79 | **63.79** | +0/−0, p=1 — invariant |
| FUNCTION | 22.66 | **29.21** | +52/−24, p=1.8e-3 |
| LINE | 19.39 | 16.59 | +25/−37, p=0.162 (ns regression — see anatomy) |
| fraction | .3545 | **.4114** | +.0568, +165/−110, p=1.1e-3 |

### Rust (n=239)
| metric | base | exp | paired |
|---|---|---|---|
| FILE | 59.83 | **59.83** | +0/−0, p=1 — invariant |
| FUNCTION | 9.21 | **20.50** | +32/−5, p=7.4e-6 |
| LINE | 3.77 | **7.53** | +14/−5, p=0.064 |
| fraction | .0976 | **.2421** | +.1445, +119/−43, p=1.9e-9 |

### C++ (n=129) — three arms
| metric | main | idx | exp | indexing (main→idx) | structure (idx→exp) |
|---|---|---|---|---|---|
| FILE | 0.00 | 65.89 | **65.89** | +85/−0, p=5.2e-26 | +0/−0, p=1 — invariant |
| FUNCTION | 4.65¹ | 6.20 | **18.60** | +2/−0, p=0.5 | +17/−1, p=1.5e-4 |
| LINE | 0.00 | 1.55 | **7.75** | +2/−0, p=0.5 | +9/−1, p=0.021 |
| fraction | .0000 | .0676 | **.2967** | +.0675, p=9.1e-13 | +.2292, +82/−20, p=4.3e-10 |

¹ entirely the 6 empty-gold instances (vacuous-correct convention).

### C (n=128) — three arms
| metric | main | idx | exp | indexing (main→idx) | structure (idx→exp) |
|---|---|---|---|---|---|
| FILE | 0.00² | 46.88 | **46.88** | +60/−0, p=1.7e-18 | +0/−0, p=1 — invariant |
| FUNCTION | 3.91 | 15.62 | **26.56** | +6/−0, p=0.031 | +19/−5, p=6.6e-3 |
| LINE | 0.00 | 3.91 | **10.94** | +5/−0, p=0.063 | +13/−4, p=0.049 |
| fraction | .0000 | .0493 | **.1961** | +.0493, p=7.6e-6 | +.1468, +49/−10, p=2.7e-7 |

² the main arm threw 50 engine errors (roust exit 1, "no results" — repos
with essentially nothing indexable; counted wrong per convention). The
"current default" on C is not a weak baseline; it is a null system.

## Go LINE anatomy (the one negative cell)

All 37 LINE all-or-nothing losses are cli/cli. Losses have larger gold
patches than gains (median 28 vs 16 gold lines, both median 1 file), and
the exp bundle still captures a median 50.4% of gold lines on loss
instances (gains reach 1.0 by definition; base was 1.0 on losses). Shape:
multi-site edits inside one file, where several ±30 windows centered on
scattered hit lines happened to straddle every edit site, while structural
packing seats the best-scoring function span(s) and misses sibling sites.
This is the E17 D-class / sweep-fragmentation signature — the packing half
improved (fraction +.0568, p=1.1e-3; FUNCTION +52/−24), and the residual
is the sibling-set problem parts (b)#2/#3 of the multilang report already
own. No boundary-quality issue found in the losses inspected.

## Identity proofs

1. **Defaults byte-identity vs main** (`lab/ws2_identity_gate.py`):
   18 instances (12 Lite Python across 6 repos + 6 MSWE JS/TS across
   axios/dayjs/express), TWO runs per binary, md5 over the retrieval
   payload: **18/18 identical, 0 determinism flakes** — the batch changes
   nothing for Python or the E23 languages.
2. **`--cfamily-ext` inertness**: branch binary, flag on vs off, the 12
   pure-Python Lite instances: **12/12 byte-identical** (the flag only
   matters where C-family files exist).
3. **FILE invariance inside every same-indexing pair** (+0/−0 in all
   five): structure is a packing change; select_files untouched.
4. Unit level: 71 tests pass; the 7 new WS2 tests pin exact fixture spans
   per language (generics, receivers, impl/trait blocks, typedef dedup,
   template hoisting, attribute folding) and prove pack_regions flag
   gating leaves `.py` spans byte-equal.

## Cost

**Binary size**: 9,689,520 → 15,576,800 bytes (**+5.89 MB, +60.8%**) for
five grammars. Compiled grammar objects (per-grammar attribution, pre-link):
go 456 KB, java 840 KB, c 1.26 MB, rust 2.23 MB, cpp 6.78 MB. C++ is the
E23-scan's predicted worst case (24.66 MB parser.c) and dominates.

**Latency** (biggest repo per slice, same branch binary, structural vs
`--no-structural-blocks`, warm best-of-2, idle machine):

| repo | window | structural | delta |
|---|---|---|---|
| fastjson2 (java) | 0.80 s | 2.18 s | +1.4 s |
| cli/cli (go) | 0.78 s | 2.11 s | +1.3 s |
| nushell (rust) | 0.27 s | 1.34 s | +1.1 s |
| ponyc (c) | 0.78 s | 1.90 s | +1.1 s |
| nlohmann/json (cpp) | 0.61 s | 3.70 s | +3.1 s |

Same profile as E23's axios 2.23 s: the O(candidates²) pass-2 cost with
more/finer candidates, not a parser pathology (nlohmann's single huge
headers make cpp the stress case). Cost optimization remains follow-up (b)
of #56, unchanged in scope by this batch.

## Verdicts (per the E23 gate criteria)

- **Java: PASS, adopt-recommend.** FILE invariant; FUNCTION +11.72
  (p=0.011); fraction +.1548 (p=0.018); LINE +0.78 (ns, positive).
- **Go: PASS with recorded caveat, adopt-recommend.** FILE invariant;
  FUNCTION +6.55 (p=1.8e-3); fraction +.0568 (p=1.1e-3); LINE −2.80
  (p=0.162, ns) — fragmentation-shaped (above), the campaign's known
  sibling problem, not a boundary defect. Watch for reversal when a
  sibling mechanism lands.
- **Rust: PASS, adopt-recommend.** Strongest slice: FUNCTION +11.29
  (p=7.4e-6); LINE +3.77 (p=0.064); fraction +.1445 (p=1.9e-9).
- **C++: PASS on the structure effect, adopt-recommend conditional on
  `--cfamily-ext`.** Structure (same binary, same indexing): FUNCTION
  +12.40 (p=1.5e-4), LINE +6.20 (p=0.021), fraction +.2292 (p=4.3e-10),
  FILE invariant. Indexing itself is the bigger single lever (FILE
  0→65.89) and is a flag, not a default.
- **C: PASS on the structure effect, same conditional.** FUNCTION +10.94
  (p=6.6e-3), LINE +7.03 (p=0.049), fraction +.1468 (p=2.7e-7), FILE
  invariant.

**Adoption shape.** Merging this branch adopts structural packing for
.java/.go/.rs immediately (they ride the existing default-ON flag; the
18/18 identity gate bounds the blast radius to exactly those languages).
C/C++ additionally need `--cfamily-ext`, which stays opt-in until a
dedicated gate proves default-ON safe on Python (numpy/pandas-class repos
index vendored/native .c under it — Lite-300 + Verified no-regression
required, plus a VENDOR_RE review; proposed as WS2b).

## Artifacts

`lab/results_regions/ws2/`: `mswe_{java,go,rust}_{base,exp}.jsonl`,
`mswe_{c,cpp}_{main,idx,exp}.jsonl` (+ per-arm `.log`),
`agentless_metric_mswe_<lang>_<arm>.json` × 12, `score_*.log`,
`launch_all.sh`. Scripts: `lab/ws2_identity_gate.py`,
`lab/ws2_paired_stats.py`, `lab/ws2_repos/clone_all.sh`,
`lab/mswe_<lang>_instances.txt` × 5 (committed; parquets + raw HF jsonl
stay untracked like `mswe_jsts.parquet`, rebuildable via
`lab/mswe_adapter.py`). Engine tests: 7 WS2 fixtures in
`roust-rs/src/core.rs`.

## Process anomalies (recorded)

- The first latency attempt ran while 12 scorer processes hammered the
  same clone dirs; the c/cpp window arms returned instant-exit artifacts
  (0.00 s). Rerun clean on an idle machine; only the clean numbers are
  reported. (Same lesson as E23's runtime anomaly: co-located load
  perturbs measurements but not artifacts.)
- `agentless_metric_verified.print_table` crashed on the two vacuous main
  arms (empty file-correct subset → None mean) AFTER the JSON artifact
  write; fixed with n/a-printing. Artifacts unaffected.
- `mswe_jsts.parquet` exists only untracked in the primary checkout (never
  committed with E23); the identity gate needed it and it was copied in.
  The five new slices ship committed instance lists to avoid repeating
  this.
- c_main's 50 "engine errors" are roust's no-results exit on unindexable
  repos — expected, and itself the cleanest statement of the extension
  ceiling this batch removes.
