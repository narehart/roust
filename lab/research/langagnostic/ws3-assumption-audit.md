# WS3 phase 1 — Python-assumption audit (issue #56, workstream 3)

**Status: audit only — no engine changes in this phase. Each recommended fix
gets its own flag-gated round with an MSWE first-class gate.**

Engine audited at `main` @ `9ca99e9` (post-WS2c: structural blocks, trace
boost, and `--cfamily-ext` all adopted defaults). Scope: every file of
`roust-rs/src/` (`core.rs`, `cache.rs`, `history.rs`, `main.rs`, `pyutil.rs`)
read end-to-end; no Python wrapper exists at HEAD. Two assumption-class bugs
were already caught incidentally before this sweep (the Python-AST-only
gold-function scorer, E23; the missing C-family indexing extensions, WS2) —
this is the deliberate sweep for the rest.

Evidence source: `mine_ws3_audit.py` (this directory) over the committed MSWE
parquets (`lab/mswe_jsts.parquet` 580, `lab/mswe_ws2c.parquet` 1052,
`lab/mswe_c.parquet` 128, `lab/mswe_cpp.parquet` 129) with
`lab/swebench_lite.parquet` (300) as the Python baseline; per-instance rows in
`ws3_audit_census.jsonl` (this directory). Language is assigned per instance
by majority gold-file extension; regexes are line-for-line ports of the
engine's (`TESTLIKE_RE`, `TB_FRAME_RE`, `CODE_EXTENSIONS`+`CFAMILY`).

## Census results

### 1. Trace-format census (engine boost fires ONLY on CPython format)

| slice | n | CPython TB | other-format TB | other-TB w/ gold-resolving frame |
|---|---|---|---|---|
| Lite (py) | 300 | **50 (16.7%)** | 0 | — |
| MSWE java | 124 | 0 | **15 (12.1%)** | **10 (8.1%)** |
| MSWE rust | 239 | 0 | 19 (7.9%) | 4 (1.7%) |
| MSWE go | 430 | 0 | 6 (1.4%) | 3 |
| MSWE jsts | 580 | 0 | 6 (1.0%) | 1 |
| MSWE c/cpp | 242 | 0 | 5 | 3 |

Java issues carry stack traces at ~3/4 the density Python Lite does, and 10/124
instances have a frame that resolves to a gold file — every one currently
receives zero boost (`TB_FRAME_RE` is CPython-only). Java frames carry only a
basename (`Bar.java:123`) but the FQCN in the same frame
(`com.foo.Bar.baz(...)`) determines the path suffix `com/foo/Bar.java`.

### 2. TESTLIKE damping census (0.3x `impl_prior` on gold)

| slice | % of **indexed** gold files damped | % of instances with >=1 damped indexed gold |
|---|---|---|
| Lite (py) | **0.0%** | **0.0%** |
| MSWE jsts | **21.4%** | **12.6%** |
| MSWE cpp | 15.6% | 7.7% |
| MSWE rust | 9.2% | 10.9% |
| MSWE go | 0.7% | 1.6% |
| MSWE java | 0.8% | 0.8% |
| MSWE c | 0.3% | 0.9% |

Which alternates fire on gold (all gold, indexed + not): `docs?` dominates —
jsts 1034 (mui `docs/data/...` demo components are shipped source), go 65
(cli/cli `internal/docs/man.go` — `docs` is a production package name),
cpp 102 + `benchmark` 50 (Catch2 `include/internal/benchmark/*.hpp` is
production), rust `examples?` 154 + `benches` 29 + `doc` 19 (ripgrep
`crates/core/flags/doc/*.rs` is production). The prior was calibrated on a
benchmark (SWE-bench Lite) where it hits gold exactly never; on JS/TS one in
eight instances carries a ~3.3x score handicap on a gold file, and damped
files are additionally **hard-excluded** from structural-expansion additions
(`impl_prior(c) < 1.0` filter) and testbridge/docsbridge targets.

### 3. Extension-coverage census (gold outside the indexed set; WS1 bound)

| slice | % gold files unindexed | dominant unindexed extensions |
|---|---|---|
| MSWE java | 29.8% | `.x` 42 (logstash), `.rb` 28, `.asciidoc` 14, `.gradle` 6 |
| MSWE c | 24.9% | `.pony` 64 (ponyc!), `.md` 40 |
| MSWE jsts | 24.4% | `.md` 429, `.json` 376, `.preview` 37, `.svelte` 5 |
| MSWE cpp | 22.1% | `.md` 78, `.txt` 44, `.yml` 10 |
| MSWE rust | 20.1% | `.md` 146, `.toml` 33, `.lock` 9 |
| MSWE go | 6.6% | `.json` 35, `.mod` 16, `.sum` 14 |
| Lite (py) | 0.0% | — |

Plus 16/1052 ws2c instances (and 14/128 of the c slice) whose gold is 100%
unindexed — structurally unreachable at any ranking quality. The `.pony`/
`.rb`/`.x` long tail is the strongest argument that allowlist growth does not
converge: WS1's index-all-textual (binary-sniff + size caps) is the fix, and
these are its per-language acceptance numbers.

## Ranked findings

Legend: effort XS/S/M/L; impact is measured where the census supports it,
mechanism-bounded otherwise. Ranked by impact-per-effort.

| # | finding | code site | mechanism of harm | impact evidence | fix sketch | effort |
|---|---|---|---|---|---|---|
| 1 | `TESTLIKE_RE` damps non-Python gold; never Python gold | `core.rs:1040` (`TESTLIKE_RE`), `:1056` (`impl_prior`), consumed at `:1798`, `:2822` (hard exclusion from additions), `:2443`, `:2538` | 0.3x on fused score + exclusion from expansion/bridges, driven by `docs?`/`examples?`/`benchmark?s`/`benches` path components that are production dirs in JS/Go/Rust/C++ ecosystems | census 2: jsts 21.4% of indexed gold damped (12.6% of instances), cpp 15.6%, rust 9.2%; Lite 0.0%. Headroom context: jsts FILE 46.38 vs 76.7 ceiling | soften doc/example/bench components for code-extension files (drop or 0.7) while keeping true test alternates at 0.3; flag `--impl-prior-v2` | S |
| 2 | Trace-frame FILE boost is CPython-format-only | `core.rs:310-329` (`TB_*`), `:747` (`trace_frame_files`), default-on `main.rs:365` | adopted E11b boost (proven +4 FILE rescues/0 losses on Python) never fires for Java/Node/Go/Rust/C++ trace formats | census 1: java 15/124 instances with traces, 10 with gold-resolving frames get zero boost; rust 19/239 | per-format frame regexes emitting the same raise-site-first `(path, rank)` contract; Java path derived from FQCN + basename; formats are mutually exclusive with CPython's so Lite/Verified byte-identity is provable | M |
| 3 | Anchor-forced region seating is `.py`-only | `core.rs:3988` (`!rel.ends_with(".py")` in `pack_regions`), `:3082` (`py_def_line_numbers`) | a non-Python file the anchor channel promoted never gets its named symbol's block force-seated — generic density picks the region, feeding the packing-half of the JS/TS line-recall collapse (conditional median .250 vs Python .857) | mechanism + E23 anatomy; def-line data already exists in the `sitter_blocks` walk (span starts) | seat forced blocks for all structural-grammar languages using tree-sitter header lines | S-M |
| 4 | `TESTBRIDGE_EXTS` omits `.tsx/.jsx/.java/.kt/.c/.cpp/.cs/.swift` | `core.rs:2412` | test files in those extensions can never act as bridge sources (testbridge is default-ON); `.test.tsx` is the standard React convention | mechanism; jsts is the largest slice (580) | extend list to the full indexed set | XS |
| 5 | Import graph absent for Java/Kotlin/C/C++/C#/Swift | `core.rs:2021-2145` (`file_import_targets`: py/js/rs/go only) | structural-expansion additions lose import neighbors (same-dir+cochange only), testbridge has no edges to walk, trace spillover empty, lexboost import graph empty | mechanism; java FILE 47.66 is the weakest non-C slice; `import com.foo.Bar;` and `#include "x.h"` are regex-trivial | JAVA_IMPORT_RE + package index (mirror `py_module_index`); C-family `#include "..."` relative resolution | M |
| 6 | `def_index`/anchor channel absent for Java/C/C++/Kotlin/C#/Swift; `JS_DEF_RE` misses arrow functions | `core.rs:1341-1351`, `:1520` (`def_re_for`); `JS_DEF_RE` `:1086` | `extract_symbol_anchors` (default-ON, E-class rescue) can never promote those files even when the issue names the exact class/method; `const f = () =>` components invisible in JS | mechanism; the pinned tree-sitter grammars already parse these files every query — the regex def layer is legacy | build def_index from the tree-sitter walk for all structural languages (also unlocks #3 and #8) | M |
| 7 | `CODE_EXTENSIONS` allowlist ceiling (WS1) | `core.rs:16-31` | gold files never indexed; no ranking change can recover them | census 3: 6.6-29.8% of gold mass per language; 16/1052 instances fully unreachable; `.pony/.rb/.x` long tail shows allowlists don't converge | WS1 index-all-textual (already chartered); census 3 is its per-language acceptance table | (WS1) |
| 8 | Docsbridge resolves dotted refs through a Python module index only | `core.rs:2490-2547` (`resolve_py_dotted`, `SPHINX_DIRECTIVE_RE`) | for non-Python repos the docsbridge (default-ON) is a silent no-op — forfeited signal, no active harm; `DOTTED_PATH_RE` already matches Java FQCNs, resolution just lacks a non-Python module index | mechanism | piggyback on #5's package indexes | S |
| 9 | STOP/keyword sets are Python(+partial Go/Rust/JS)-tuned | `core.rs:94-103` (`STOP`), `:362` (`ROUTE_KW`, route-only), `:4163` (E18 `kw_excl`, flag-off) | Java `public/static/final/throws`, C++ `include/define/nullptr/namespace` survive as index terms: doclen inflation + junk fence-mined query terms; second-order (idf already crushes ubiquitous terms within a repo) | mechanism; low measured urgency | extend STOP symmetrically; NOTE: changes Python tokenization too ("public" appears in Python docstrings) — full 4-metric gate, no byte-identity | S code, M gate |
| 10 | `extract_comments` non-Python branch is C-style-only | `core.rs:1095-1114` | correct for every currently-indexed language (JSDoc/godoc/rustdoc/javadoc are `//` or `/* */`); becomes wrong the day WS1 indexes `.rb`/`.pony`/`.yml` (Ruby `#` comments would be extracted as nothing) | contingent on WS1 | per-family comment syntax table keyed on suffix, shipped with WS1 | XS (with WS1) |

Non-findings (audited, no action):

- **History mining is NOT funcname-based** — `history.rs` uses
  `git log --name-only` (whole-file attribution); git's language-specific
  hunk-header funcname regexes are never consulted. Its only language bias is
  the `is_code_file` gate (`history.rs:222`) inheriting finding #7's
  allowlist: commits touching only unindexed-language files contribute no
  cochange/msg signal — fixed for free by WS1.
- **Tokenizer/identifier splitting is symmetric** — `subtokens` handles
  snake_case and camelCase (incl. `HTTPResponse` acronym runs) identically for
  all languages; kebab-case never forms an identifier in the indexed set.
  `IDENT_RE` drops `$`-sigils and Unicode identifiers (rare; noted, unranked).
- **`resolve_frame_path` is language-neutral** (trailing-component match) —
  reusable as-is by finding #2.
- **Route pipeline** (`INDENT_CODE_START_RE`, `MINE_*`, `.py`-strip at
  `core.rs:667`) is Python-shaped throughout, but `--route` is a rejected,
  flag-OFF experiment — not worth a round unless routing is revived.
- **`cache.rs` manifest scan** shares `code_suffix_allowed` with the corpus
  walk by construction — no independent assumption.
- **`.kt/.cs/.swift`** are indexed but have no grammar (window fallback) and
  no def/import support; absent from MSWE, so unmeasurable today — revisit if
  a bench slice appears.

## Recommended fix rounds (each its own PR + gate)

**Round WS3a — impl_prior recalibration (finding 1).**
Flag `--impl-prior-v2`: `docs?`/`doc`/`examples?`/`benchmark?s`/`benches`
components stop damping files with code extensions (or damp 0.7); true test
alternates (`tests?`, `__tests__`, `.spec.`, `.test.`, `_test.*`, `test_`,
`conftest`, `spec/s`) keep 0.3. Gate: MSWE jsts + cpp + rust FILE/fraction
primary (expect FILE gains — the only mechanism-level FILE lever found by
this audit), java/go/c no-regression, Lite-300 + Verified-407 all-four
invariant with paired diff (byte-identity NOT expected: Python repos contain
damped non-gold files whose rank can shift; the gate is the 4-metric hold).

**Round WS3b — multi-format trace-frame boost (finding 2).**
Java (`at pkg.Cls.m(Cls.java:123)` with FQCN->path), Node
(`at fn (path:1:2)`), Go (goroutine frame-locator lines), Rust
(`panicked at` + backtrace `at path.rs:1:2`) frame extraction feeding the
existing `trace_frame_files` contract. Gate: MSWE java FILE primary (10/124
direct gold pointers currently ignored), rust/go/jsts secondary; Lite-300 +
Verified-407 byte-identity gate (the new formats are disjoint from CPython's
frame syntax — identity is provable, same as E23's flag-off proof).

**Round WS3c — structural-symbol unification (findings 3 + 6, feeds 8).**
Build `def_index` and def-line numbers from the already-pinned tree-sitter
walks for all structural languages; drop the `.py`-only guard in
`pack_regions`' anchor seating; extend `JS_DEF_RE` duties to the CST
(arrow functions). Gate: MSWE per-language FUNCTION/LINE/fraction primary
with FILE expected-invariant per slice, Lite-300 + Verified-407
byte-identity for Python (its def path is untouched).

Follow-ups after the rounds: finding 4 (`TESTBRIDGE_EXTS`, XS micro-gate),
finding 5 (import graphs — measure after WS3a/b to avoid confounding the
FILE movement), finding 9 (STOP symmetrization, low urgency).
