//! roust command-line interface -- a Rust port of `src/roust/cli.py`.
//!
//!     roust [--json] [--files-only] [--budget N=8192] [--k N]
//!              [--no-cache] [--reindex]
//!              [--no-history] [--no-docs] [--no-anchors] [--no-testbridge]
//!              [--explain] QUERY PATH
//!
//! Runs the frozen-v7 retrieval pipeline (roust::core, roust::cache,
//! roust::history) against a repo and prints a token-budgeted,
//! region-packed bundle of the files most relevant to QUERY.
//!
//! Default output (stdout) is the packed bundle text. A one-line stats
//! summary always goes to stderr, never stdout, so stdout stays
//! pipeable/parseable.
//!
//! Exit codes: 0 = results found (including low-confidence matches, flagged
//! via `low_confidence` in `--json` stats and a stderr warning), 1 = no
//! results, 2 = usage error.
//!
//! "No results" (exit 1) covers BOTH empty-result cases, matching the
//! README's "1 = no results" contract: (a) literal zero-match -- no query
//! term matched anything in the indexed corpus vocabulary at all -- and (b)
//! terms matched somewhere in the vocabulary (e.g. only in docs pages, which
//! are query-able vocabulary but not packable code files) yet the packed
//! result set came out empty. Under `--json` both cases emit the same valid,
//! parseable empty-payload JSON on stdout (`files: []`, `regions: {}`,
//! `bundle: ""`, real `stats`), so `--json` callers ALWAYS get exactly one
//! JSON document on stdout regardless of outcome; the two cases remain
//! distinguishable by the stderr note and by `matched_query_terms` in stats.

use roust::cache;
use roust::core::{
    anchor_def_symbols, extract_symbol_anchors, is_low_confidence, lexboost_hubs, lexboost_import_neighbors,
    lexboost_knn_neighbors, pack_regions, query_term_coverage, query_terms, route_query, select_files, trace_frame_files,
    RoutedQuery, SelectParams,
};
use clap::Parser;
use std::collections::HashSet;
use std::path::PathBuf;
use std::time::Instant;

/// Engine provenance embedded at compile time by build.rs -- short git SHA
/// and a dirty flag scoped to `roust-rs/` paths (see build.rs). Powers
/// `roust --version` (e.g. `roust 0.2.0 (abc1234, clean)`) and the
/// `engine_sha`/`engine_dirty` fields in `--json` stats, so a stale `uv run
/// roust` wheel (doesn't rebuild on `roust-rs/src` changes) is always
/// identifiable rather than silently measured as current.
const ROUST_VERSION: &str =
    concat!(env!("CARGO_PKG_VERSION"), " (", env!("ROUST_GIT_SHA"), ", ", env!("ROUST_GIT_DIRTY"), ")");

#[derive(Parser, Debug)]
#[command(
    name = "roust",
    version = ROUST_VERSION,
    about = "Recall-first code retrieval for coding agents - one ranked, token-budgeted bundle per query, no model or API key required"
)]
struct Args {
    /// natural-language query or issue text (pass it raw -- identifiers,
    /// error strings, and other anchors are signal, don't pre-clean it)
    query: String,

    /// repo path to search (default: .)
    #[arg(default_value = ".")]
    path: String,

    /// token budget for the packed bundle (default 8192, sized for LLM
    /// context; humans reading by hand may prefer 2048)
    #[arg(long, default_value_t = 8192)]
    budget: i64,

    /// cap the number of returned files, 0 = no cap (humans reading by hand
    /// may prefer --k 8 for a tighter, scannable list)
    #[arg(long, default_value_t = 0)]
    k: i64,

    /// print ranked file paths only, one per line, instead of the packed bundle
    #[arg(long)]
    files_only: bool,

    /// machine-readable JSON output instead of the packed bundle
    #[arg(long)]
    json: bool,

    /// do not read or write the on-disk index cache (<repo>/.roust/)
    #[arg(long)]
    no_cache: bool,

    /// force a fresh index build even if a matching cache entry exists
    /// (still writes the cache afterward unless combined with --no-cache)
    #[arg(long)]
    reindex: bool,

    /// disable the git-history commit-message field + co-change frontier expansion
    #[arg(long)]
    no_history: bool,

    /// disable the docs-bridge signal (*.rst/*.txt/*.md page indexing + bridging)
    #[arg(long)]
    no_docs: bool,

    /// disable the definition-symbol anchor channel
    #[arg(long)]
    no_anchors: bool,

    /// disable the test-file lexical bridge channel
    #[arg(long)]
    no_testbridge: bool,

    /// dump the Explain diagnostic record as JSON to stderr
    #[arg(long)]
    explain: bool,

    /// E28 (per-language parity campaign): how many pool candidates may be
    /// added beyond the lexical picks (16 = shipped behaviour). All-or-
    /// nothing FILE on multi-gold-file instances rewards breadth, and the
    /// mining shows 62% of missed multi-file gold is already an eligible
    /// candidate ranked below this cut. Raising it trades precision for
    /// recall; the cost is expected to land on the region metrics.
    #[arg(long, default_value_t = 16)]
    max_additions: i64,

    /// E30 (per-language parity campaign): how many of each source file's
    /// owned pool candidates the per-source seating guarantee admits
    /// (1 = shipped behaviour). E29 showed file selection is blind to the
    /// token budget, so breadth is only reachable through admission; unlike
    /// --max-additions this spends admissions on ownership diversity rather
    /// than on the next-ranked candidate overall.
    #[arg(long, default_value_t = 1)]
    seats_per_source: i64,

    /// E32 (per-language parity campaign): how many hops of the import graph
    /// the candidate GENERATOR walks out from each source file (1 = shipped).
    /// E31 showed Java and Rust are exactly inert to the admission cap (0.00
    /// at 32 and at 128), i.e. their gold is never proposed as a candidate at
    /// any cap -- a generation limit, not an admission one.
    #[arg(long, default_value_t = 1)]
    import_hops: i64,

    /// E32 (per-language parity campaign): resolve import edges for Java
    /// (`import a.b.C;`) and the C family (`#include "foo.h"`), which the
    /// import graph never covered -- those files had NO edges at all, hence
    /// no candidate generation and no Guarantee-1 seat. Default off.
    #[arg(long)]
    import_edges_v2: bool,

    /// E33 (per-language parity campaign): pool eligibility floor as a
    /// fraction of the best candidate's score (0.15 = shipped). Applied
    /// BEFORE any admission rule, so it bounds every cap.
    #[arg(long, default_value_t = 0.15)]
    eligible_floor: f64,

    /// E34 (per-language parity campaign): how many BM25-ranked files seed
    /// the retrieval as `sources` (10 = shipped). E33 showed Java, C++ and
    /// Rust saturate under maximum candidate GENERATION, so the residue is
    /// upstream of the graph: everything is expanded outward from these
    /// seeds, and gold more than two hops from all of them is unreachable.
    #[arg(long, default_value_t = 10)]
    k_lex: usize,

    /// E37 (per-language parity campaign): generate candidates from the
    /// SYMBOL-REFERENCE graph -- a file that references a rare symbol another
    /// file defines becomes its neighbour. Language-agnostic by construction:
    /// it uses the existing definition index and term index, so it needs no
    /// per-language import syntax and subsumes the per-language import
    /// parsers rather than adding another one.
    #[arg(long)]
    symbol_graph: bool,

    /// E44: concentrate packing BUDGET on query-connected, graph-central
    /// files via personalized PageRank from the BM25 seeds (0.0 = off).
    /// Does not change which files are returned -- only how deeply each is
    /// packed -- so it attacks the depth loss that every breadth gain paid.
    #[arg(long, default_value_t = 0.0)]
    ppr_budget: f64,

    /// E44b: additive PPR budget boost (scores[f] += lambda * ppr) instead of
    /// the multiplicative squash. Raises graph-connected additions toward
    /// seed-level funding without lowering anyone.
    #[arg(long)]
    ppr_additive: bool,

    /// E45 (adopted): the packer's per-file budget floor (0.15; 0.3 restores
    /// the pre-E45 engine). Every region
    /// is weighted by (floor + file score); a high floor gives every admitted
    /// file a near-equal claim, which is why wide admission spread budget thin.
    #[arg(long, default_value_t = 0.15)]
    pack_floor: f64,

    /// E47: compact pass-1 seat (in tokens) for returned files ranked at or
    /// beyond --tail-seat-after. Every returned file otherwise gets a flat
    /// 120-token seat, which at wide admission is the whole depth tax. The
    /// file still counts as retrieved; pass 2 can re-expand it on evidence.
    /// 0 = off.
    #[arg(long, default_value_t = 0)]
    tail_seat_tokens: i64,

    /// E47: rank (0-based, in returned order) from which the compact seat
    /// applies.
    #[arg(long, default_value_t = 16)]
    tail_seat_after: usize,

    /// E39: index build files (build.gradle, Cargo.toml, CMakeLists.txt,
    /// package.json, pom.xml, go.mod, Makefile ...). Genuinely useful to
    /// return -- real changes often edit them -- and they carry gold that the
    /// corpus could not retrieve at any rank.
    #[arg(long)]
    build_files: bool,

    /// E39: index changelogs and release notes (CHANGELOG, release-notes/,
    /// VERSION-*, CREDITS-*). These are gold ONLY because the fixing PR also
    /// wrote a release note, so this raises the benchmark score without
    /// making the tool more useful. Kept separate from --build-files for
    /// exactly that reason; do not adopt silently.
    #[arg(long)]
    changelog_files: bool,

    /// E41: index the broad non-source class (.md .rst .txt .adoc .asciidoc
    /// .json .yml .yaml .toml). Needed for JS/TS, whose non-source gold is
    /// dispersed component docs and fixtures that the narrow changelog rule
    /// cannot reach. The most dilutive rule in the engine.
    #[arg(long)]
    docs_data_files: bool,

    /// pad every selected region by N lines in each direction (clamped to
    /// file bounds), merging spans that end up overlapping or adjacent
    /// (E12/span-padding experiment): default 5, adopted from the comboA
    /// campaign result (guarded padding + length norm, see #4). If padding
    /// pushes the bundle over --budget, padding is first de-escalated
    /// (shrunk back toward 0) on the lowest-gain spans before any whole span
    /// is dropped (E12b guard): a file present in the unpadded (--pad-lines
    /// 0) selection is never evicted purely because padding grew it over
    /// budget. Pass `--pad-lines 0` (together with `--len-exp 1.0`) to
    /// reproduce the pre-adoption (byte-identical pre-E12/E14) engine.
    #[arg(long, default_value_t = 5)]
    pad_lines: usize,

    /// exponent applied to the token-count denominator of pack_regions'
    /// region-selection metric (E14/issue #14 case mining): `gain /
    /// tok^len_exp` in place of the flat `gain / tok`. Default 0.85,
    /// adopted from the comboA campaign result (see #4): sub-linearly
    /// discounts region length, letting long real-fix functions compete
    /// against short lucky-match stubs instead of being crushed by the
    /// token-count division. Pass `--len-exp 1.0` (together with
    /// `--pad-lines 0`) to reproduce the pre-adoption (byte-identical
    /// pre-E12/E14) engine, where 1.0 is the original linear length penalty.
    #[arg(long, default_value_t = 0.85)]
    len_exp: f64,

    /// E19 (campaign #4 wave 5): for each packed file, also include spans of
    /// the pass-1 pick's def-name family -- same method name across sibling
    /// classes in the file, or a shared def-name prefix/suffix segment
    /// family with >= 4 members (multi-function "sweep" patches; capped at
    /// 8 members, nearest to the seed first). Default OFF: byte-identical
    /// to the engine without this flag. Added spans are budget-checked
    /// depth; they never displace a file's pass-1 span (E12b guard).
    #[arg(long)]
    family_enum: bool,

    /// E18 (campaign #4 wave 5): identifier-token-bag overlap threshold
    /// (SourcererCC-style, multiset intersection / max bag size) at or
    /// above which a same-file span counts as a sibling of the pass-1 pick
    /// and is added as budget-checked depth (top --max-siblings by
    /// overlap). 0 (default) disables: byte-identical to the engine
    /// without this flag.
    #[arg(long, default_value_t = 0.0)]
    sibling_sim: f64,

    /// max E18 similarity-siblings added per file (only meaningful with
    /// --sibling-sim > 0)
    #[arg(long, default_value_t = 3)]
    max_siblings: usize,

    /// E11 (campaign #4 wave 5): deterministic structure-aware query
    /// routing. Partitions the issue text into {traceback, code-fence,
    /// prose} channels: traceback blocks are mined for frame files /
    /// function names / exception + message (frame-named files get a
    /// rank-decayed additive FILE boost, BRTracer-style, with 0.1 import
    /// spillover) and the raw block is dropped as bulk text; fenced/REPL/
    /// indented code blocks are mined for identifiers then dropped
    /// (mine-then-discard); prose-only queries are byte-identical to the
    /// unrouted engine. Default OFF: byte-identical to the engine without
    /// this flag.
    #[arg(long)]
    route: bool,

    /// E11 conditional test/example-path downweight (Kim & Lee): multiplier
    /// applied to test/docs/example-shaped file paths ONLY when the query's
    /// fence-mined terms are a strict majority of its term list (never for
    /// prose or trace-dominated queries). Only meaningful with --route.
    #[arg(long, default_value_t = 0.85)]
    route_test_penalty: f64,

    /// E11b trace-frame FILE boost -- ADOPTED as the engine default
    /// (campaign #4 wave 5, PR #52, user-approved 2026-08-24). Files named
    /// in the issue's traceback frames (resolved into the repo) receive the
    /// rank-decayed additive FILE boost (1/rank for the top-10 frames,
    /// raise-site first; 0.1 deeper; 0.1 import spillover). The query TEXT
    /// is byte-untouched -- no term mining, no discarding. ON by default;
    /// passing this flag explicitly is accepted-but-redundant (kept for
    /// harness compatibility). Disable with --no-trace-boost. Mutually
    /// exclusive with --route, which applies its own trace handling.
    #[arg(long)]
    trace_boost: bool,

    /// disable the E11b trace-frame FILE boost (reproduces the
    /// pre-adoption engine byte-identically; also implied by --route,
    /// whose rejected-experiment pipeline supplies its own trace channel)
    #[arg(long)]
    no_trace_boost: bool,

    /// WS3b multi-format trace-frame extraction -- ADOPTED as the engine
    /// default (campaign #56, audit finding 2, PR #66, standing
    /// language-agnostic directive 2026-08-26). Adds Java (`at
    /// pkg.Cls.m(Cls.java:123)`, FQCN->path), Node (`at fn
    /// (path.js:1:2)`), Go panic locator, and Rust backtrace `at` frame
    /// parsing alongside the CPython format; frames feed the SAME
    /// rank-decayed E11b boost channel, raise-site first per format's own
    /// convention. Python parsing unchanged; query text byte-untouched;
    /// provably byte-identical on all Python slices (zero new-format
    /// matches on Lite/Verified/full). ON by default; passing this flag
    /// explicitly is accepted-but-redundant (kept for harness
    /// compatibility). Disable with --no-trace-formats-v2. No-op under
    /// --no-trace-boost / --route.
    #[arg(long)]
    trace_formats_v2: bool,

    /// disable WS3b multi-format trace-frame extraction (CPython-only
    /// frame parsing, reproducing the pre-adoption engine
    /// byte-identically)
    #[arg(long)]
    no_trace_formats_v2: bool,

    /// E20 (campaign #4 wave 5): LexBoost neighbor score smoothing lambda
    /// (arXiv:2409.05882). Final file score = lambda*S + (1-lambda)*
    /// prior*mean(neighbor S) over the graph chosen by --lexboost-graph,
    /// with top-decile-in-degree hub exclusion. 0 (default) = OFF,
    /// byte-identical to the engine without this flag; the paper's default
    /// is 0.7.
    #[arg(long, default_value_t = 0.0)]
    lexboost: f64,

    /// language-agnostic structural block extraction -- ADOPTED as the
    /// engine default (E23, campaign #4 wave 5, PR #55, user-approved
    /// 2026-08-25, language-agnostic directive; first entry of the #56
    /// campaign). Structural region candidates come from each language's
    /// parser: Python natively; .js/.jsx/.ts/.tsx (E23) and, since the
    /// WS2 grammar batch, .java/.go/.rs plus the C family
    /// (.c/.h/.cc/.cpp/.cxx/.hpp/.hh, indexed only under --cfamily-ext)
    /// via pinned tree-sitter CST walks (functions, methods, classes,
    /// impl/trait blocks, structs/enums, templates; same nested
    /// class-span + member-span shape python_blocks emits); fixed
    /// +/-30-line windows for anything else. ON by default; passing this
    /// flag explicitly is accepted-but-redundant (kept for harness
    /// compatibility; hidden alias: --ts-blocks). Disable with
    /// --no-structural-blocks.
    #[arg(long, alias = "ts-blocks")]
    structural_blocks: bool,

    /// disable structural block extraction for languages beyond Python
    /// (reproduces the pre-adoption engine byte-identically:
    /// .js/.jsx/.ts/.tsx -- and the WS2 grammar-batch languages -- fall
    /// back to fixed +/-30-line windows; Python's native structural
    /// packing is unaffected in either state; hidden alias: --no-ts-blocks)
    #[arg(long, alias = "no-ts-blocks")]
    no_structural_blocks: bool,

    /// E25 (campaign #56 follow-on): choose packing-unit headers by SHAPE
    /// (any node that binds a name to a body, per tree-sitter's own field
    /// convention) instead of the per-language node-kind allowlists. The
    /// zero-configuration path: a newly linked grammar works with no code
    /// from us. Experimental, default OFF -- byte-identical to the shipped
    /// engine when unset. Python is unaffected either way (it uses the
    /// native block scanner, not a grammar).
    #[arg(long, conflicts_with = "no_structural_blocks")]
    shape_blocks: bool,

    /// E26 (per-language parity campaign, ADOPTED default ON): index `.rb`
    /// and `.pony` sources, which the original allowlist never covered.
    /// Accepted-but-redundant; `--no-ext-v2` reverts to the pre-adoption
    /// walk (those files become invisible again, as they were before).
    #[arg(long)]
    ext_v2: bool,

    /// Escape hatch for the E26 adoption: do NOT index `.rb`/`.pony`,
    /// reproducing the pre-adoption engine byte-identically.
    #[arg(long, conflicts_with = "ext_v2")]
    no_ext_v2: bool,

    /// WS2 (campaign #56): ALSO index the C-family extensions
    /// (.c/.h/.cc/.cpp/.cxx/.hpp/.hh) in the corpus walk. ON by default
    /// since WS2c: the vendored-C VENDOR_RE guard (cextern/, extern/,
    /// libsvm/, liblinear/ path components) excludes the bundled-C class
    /// that made default-ON unsafe in the WS2b gate (vendored libsvm
    /// displacing gold on sklearn), and the WS2c re-gate held all four
    /// metrics on Lite-300 with MSWE C/C++ payload-identical. Passing this
    /// flag explicitly is accepted-but-redundant (kept for harness
    /// compatibility). Disable with --no-cfamily-ext. Either state re-keys
    /// the index cache (a flag-off cache is never served to a flag-on run,
    /// or vice versa).
    #[arg(long, default_value_t = true)]
    cfamily_ext: bool,

    /// disable C-family indexing (reproduces the pre-WS2c corpus walk:
    /// .c/.h/.cc/.cpp/.cxx/.hpp/.hh are not indexed at all)
    #[arg(long)]
    no_cfamily_ext: bool,

    /// WS3a (campaign #56, audit finding 1): recalibrated impl_prior.
    /// Doc-like path components (docs?/examples?/benchmarks?/benches)
    /// stop damping files with a code extension -- they are production
    /// dirs outside Python (21.4% of indexed JS/TS gold damped by v1;
    /// Lite 0.0%). Genuinely test-like paths (test/tests/__tests__/spec
    /// dirs, test_*/_test.*/.spec./.test. patterns) keep the 0.3 damp in
    /// every language, with _test.<ext> broadened to all extensions.
    /// Non-code files in doc-like dirs keep the damp. Also lifts the
    /// structural-expansion / testbridge / docsbridge exclusions for
    /// no-longer-damped files (all key off impl_prior), and adds the
    /// one-word `thirdparty` component to the vendor guard (the WS3a cpp
    /// arm measured nlohmann's vendored Google Benchmark displacing gold
    /// once undamped; VENDOR_RE only knew `third_party`). Re-keys the
    /// index cache (def_index is impl_prior-gated at build time). Default
    /// OFF.
    #[arg(long)]
    impl_prior_v2: bool,

    /// WS3c (campaign #56, audit findings 3+6): structural-symbol
    /// unification -- ADOPTED as the engine default (standing
    /// language-agnostic directive, 2026-08-26; PR #67). def_index symbol
    /// names are sourced from the SAME pinned tree-sitter walks that
    /// produce structural blocks (union with the legacy per-language def
    /// regexes) for every grammar-covered non-Python file -- Java/C/C++
    /// gain a def/anchor channel for the first time; JS/TS arrow
    /// functions (`const f = () => ..`), object-literal methods and class
    /// fields become def entries; Rust impl/trait/enum and Go
    /// grouped-type names are covered. Anchor-forced region seating (the
    /// query names the exact symbol -> its own structural block is
    /// force-seated) is un-gated from `.py` to all grammar-covered
    /// languages. Python's def extraction and seating are byte-identical
    /// in either state. Either state re-keys the index cache (a flag-off
    /// cache is never served to a flag-on run, or vice versa). ON by
    /// default; passing this flag explicitly is accepted-but-redundant
    /// (kept for harness compatibility). Disable with --no-symbols-v2.
    #[arg(long)]
    symbols_v2: bool,

    /// disable WS3c structural-symbol unification (reproduces the
    /// pre-adoption engine byte-identically: def_index falls back to the
    /// per-language regex scan alone, and anchor-forced region seating is
    /// `.py`-only again)
    #[arg(long)]
    no_symbols_v2: bool,

    /// WS3d anchor displacement guard -- ADOPTED as the engine default
    /// (campaign #56, PR #68, standing language-agnostic directive
    /// 2026-08-26): exclude fixture-directory-shaped files (any `*.test/`
    /// or `*.spec/` DIRECTORY component -- the jscodeshift codemod
    /// fixture convention TESTLIKE_RE's file-infix `.test.` match misses)
    /// from symbol-anchor candidacy. The WS3d fire-level mining found
    /// this the only shape rule that separates displacing anchor fires
    /// (mui-34337/34548/35178: fixture pairs defining the same rare
    /// symbol eat gold's pack budget) from the adopted anchor wins, with
    /// zero win-fire / zero gold-fire collateral across all mined fires;
    /// jsts arms LINE 13.97->14.14, fraction +0.0018, FILE/FUNCTION
    /// invariant, zero win suppression; java/rust/Lite/Verified proven
    /// inert (fixture census + 31-instance byte-identity micro-gate).
    /// Ranking-side only; fixture files stay indexed and lexically
    /// rankable. ON by default; passing this flag explicitly is
    /// accepted-but-redundant (kept for harness compatibility). Disable
    /// with --no-displacement-guard.
    #[arg(long)]
    displacement_guard: bool,

    /// disable the WS3d fixture-dir anchor displacement guard
    /// (reproduces the pre-adoption anchor channel byte-identically:
    /// fixture-dir files compete for anchors again)
    #[arg(long)]
    no_displacement_guard: bool,

    /// E20 graph substrate for --lexboost: "import" (undirected import
    /// graph, already cached per query) or "knn" (BM25 16-nearest-neighbor
    /// files by content similarity, computed from the cached index at
    /// query time).
    #[arg(long, default_value = "import")]
    lexboost_graph: String,

    /// E21 (campaign #4 wave 5): FILE-score aggregation. "accum" (default,
    /// byte-identical to the engine without this flag) = whole-file BM25F
    /// accumulation; "chunk-max" = the content channel is scored per packer
    /// chunk (python_blocks / window fallback) and aggregated per file by
    /// MAX chunk score (BRTracer segmentation, hub-attractor defense);
    /// "chunk-top2" = mean of the top-2 chunk scores. E21b decoupled
    /// modes: "chunk-rank" / "chunk-top2-rank" = the chunk aggregate
    /// decides file selection and order ONLY, while pack_regions receives
    /// the original accumulation-normalized score map for budget
    /// allocation (the E21 gate showed the chunk map's damped scores
    /// shrink central gold files' packed budgets).
    #[arg(long, default_value = "accum")]
    file_score: String,

    /// E22 (campaign #4 wave 5): static test-bridge FILE channel weight.
    /// Bridges the query to production files via lexically-matching test
    /// files' imports + call expressions (IssueExec's issue->tests->code
    /// pathway, statically approximated; capped at 5 bridged files/query),
    /// adding weight * top_score * strength to the pre-normalization file
    /// score. 0 (default) = OFF, byte-identical to the engine without this
    /// flag.
    #[arg(long, default_value_t = 0.0)]
    test_bridge: f64,
}

fn main() {
    let args = Args::parse();

    // WS2: set BEFORE any corpus/cache work -- both the corpus walk and the
    // cache manifest scan read this process-global exactly once per file.
    // WS2c: default ON; --no-cfamily-ext wins over the (redundant) on-flag.
    roust::core::set_cfamily_ext(args.cfamily_ext && !args.no_cfamily_ext);
    roust::core::set_ext_v2(!args.no_ext_v2);

    // WS3a: same contract as the cfamily global -- set BEFORE any
    // corpus/cache work (impl_prior gates def_index at build time and the
    // cache key reads this).
    roust::core::set_impl_prior_v2(args.impl_prior_v2);

    // WS3c: same contract -- set BEFORE any corpus/cache work (def_index
    // gains tree-sitter symbols at build time; the cache key reads this;
    // pack_regions reads it at pack time for anchor seating). ADOPTED
    // default ON; --no-symbols-v2 is the escape hatch and the explicit
    // on-flag is accepted-but-redundant (mutual exclusion checked below,
    // mirroring the trace-formats-v2 pattern).
    roust::core::set_symbols_v2(!args.no_symbols_v2);
    roust::core::set_import_edges_v2(args.import_edges_v2);
    roust::core::set_build_files(args.build_files);
    roust::core::set_changelog_files(args.changelog_files);
    roust::core::set_docs_data_files(args.docs_data_files);
    roust::core::set_pack_floor(args.pack_floor);
    roust::core::set_tail_seat(args.tail_seat_tokens, args.tail_seat_after);
    // WS3d displacement guard: default ON (adopted); --no-displacement-guard
    // is the escape hatch and the explicit on-flag is accepted-but-redundant
    // (mutual exclusion checked below, mirroring the symbols-v2 pattern).
    roust::core::set_displacement_guard(!args.no_displacement_guard);

    if args.budget <= 0 {
        eprintln!("roust: error: --budget must be positive");
        std::process::exit(2);
    }
    if args.k < 0 {
        eprintln!("roust: error: --k must be >= 0");
        std::process::exit(2);
    }
    if !args.len_exp.is_finite() {
        eprintln!("roust: error: --len-exp must be finite");
        std::process::exit(2);
    }
    if !args.sibling_sim.is_finite() || !(0.0..=1.0).contains(&args.sibling_sim) {
        eprintln!("roust: error: --sibling-sim must be in [0, 1]");
        std::process::exit(2);
    }
    if !args.route_test_penalty.is_finite() || !(0.0..=1.0).contains(&args.route_test_penalty) {
        eprintln!("roust: error: --route-test-penalty must be in [0, 1]");
        std::process::exit(2);
    }
    if !args.lexboost.is_finite() || !(0.0..=1.0).contains(&args.lexboost) {
        eprintln!("roust: error: --lexboost must be in [0, 1]");
        std::process::exit(2);
    }
    if args.lexboost_graph != "import" && args.lexboost_graph != "knn" {
        eprintln!("roust: error: --lexboost-graph must be 'import' or 'knn'");
        std::process::exit(2);
    }
    let file_score_mode = match args.file_score.as_str() {
        "accum" => roust::core::FileScoreMode::Accum,
        "chunk-max" => roust::core::FileScoreMode::ChunkMax,
        "chunk-top2" => roust::core::FileScoreMode::ChunkTop2,
        "chunk-rank" => roust::core::FileScoreMode::ChunkRankMax,
        "chunk-top2-rank" => roust::core::FileScoreMode::ChunkRankTop2,
        _ => {
            eprintln!("roust: error: --file-score must be 'accum', 'chunk-max', 'chunk-top2', 'chunk-rank', or 'chunk-top2-rank'");
            std::process::exit(2);
        }
    };
    if !args.test_bridge.is_finite() || !(0.0..=1.0).contains(&args.test_bridge) {
        eprintln!("roust: error: --test-bridge must be in [0, 1]");
        std::process::exit(2);
    }
    if args.route && args.trace_boost {
        eprintln!("roust: error: --route and --trace-boost are mutually exclusive (--route already applies the trace-frame boost)");
        std::process::exit(2);
    }
    if args.trace_boost && args.no_trace_boost {
        eprintln!("roust: error: --trace-boost and --no-trace-boost are mutually exclusive");
        std::process::exit(2);
    }
    if args.trace_formats_v2 && args.no_trace_formats_v2 {
        eprintln!("roust: error: --trace-formats-v2 and --no-trace-formats-v2 are mutually exclusive");
        std::process::exit(2);
    }
    if args.symbols_v2 && args.no_symbols_v2 {
        eprintln!("roust: error: --symbols-v2 and --no-symbols-v2 are mutually exclusive");
        std::process::exit(2);
    }
    if args.displacement_guard && args.no_displacement_guard {
        eprintln!("roust: error: --displacement-guard and --no-displacement-guard are mutually exclusive");
        std::process::exit(2);
    }
    if args.structural_blocks && args.no_structural_blocks {
        eprintln!("roust: error: --structural-blocks and --no-structural-blocks are mutually exclusive");
        std::process::exit(2);
    }
    // E23 structural blocks are ON by default (adopted);
    // --no-structural-blocks disables them (--ts-blocks/--no-ts-blocks are
    // hidden compat aliases).
    let block_mode = if args.shape_blocks {
        roust::core::BlockMode::Shape
    } else if args.no_structural_blocks {
        roust::core::BlockMode::Windows
    } else {
        roust::core::BlockMode::Structural
    };
    // Trace boost is ON by default (adopted); --no-trace-boost disables it,
    // and --route implies it off (route's own pipeline supplies trace_files).
    let use_trace_boost = !args.no_trace_boost && !args.route;

    let repo_path = PathBuf::from(&args.path);
    if !repo_path.is_dir() {
        eprintln!("roust: error: not a directory: {}", args.path);
        std::process::exit(2);
    }

    let with_history = !args.no_history;
    let with_docs = !args.no_docs;
    let use_anchors = !args.no_anchors;
    let use_testbridge = !args.no_testbridge;

    let t0 = Instant::now();

    let (corpus, edges, history, cache_hit) =
        cache::load_or_build(&repo_path, with_history, with_docs, !args.no_cache, args.reindex);
    let index_ms = t0.elapsed().as_secs_f64() * 1000.0;

    // E20 LexBoost graph (flag-gated; defaults build nothing): neighbor
    // lists + hub set from the chosen substrate. The import graph is free
    // (already built and cached for every query); the kNN graph is computed
    // here from the cached corpus statistics, and its cost is reported as
    // `lexboost_graph_ms` (an adoption consideration, per the latency
    // story).
    let t_graph = Instant::now();
    let lexboost_nbrs: Option<roust::core::NeighborMap> = if args.lexboost > 0.0 {
        Some(match args.lexboost_graph.as_str() {
            "knn" => lexboost_knn_neighbors(&corpus, 16),
            _ => lexboost_import_neighbors(&edges),
        })
    } else {
        None
    };
    let lexboost_hub_set = lexboost_nbrs.as_ref().map(lexboost_hubs);
    let lexboost_graph_ms = t_graph.elapsed().as_secs_f64() * 1000.0;

    let t1 = Instant::now();
    // E11 routing (--route): structure-aware query treatment. The default
    // path calls query_terms directly and never constructs a RoutedQuery,
    // keeping defaults byte-identical to the pre-E11 engine.
    let routed: Option<RoutedQuery> = if args.route { Some(route_query(&args.query, &corpus)) } else { None };
    let terms = match &routed {
        Some(rq) => rq.terms.clone(),
        None => query_terms(&args.query, &[]),
    };
    // E11b trace-frame FILE extraction (adopted default; see
    // use_trace_boost above); `terms` above is untouched (byte-identical
    // query text).
    // WS3b multi-format parsing is ON by default (adopted);
    // --no-trace-formats-v2 restores CPython-only frame extraction.
    let use_trace_formats_v2 = !args.no_trace_formats_v2;
    let boost_files: Vec<String> = if use_trace_boost {
        if use_trace_formats_v2 {
            roust::core::trace_frame_files_v2(&args.query, &corpus)
        } else {
            trace_frame_files(&args.query, &corpus)
        }
    } else {
        Vec::new()
    };
    let (matched_terms, total_terms) = query_term_coverage(&corpus, &terms);
    let zero_match = matched_terms == 0;
    let anchors = if use_anchors { Some(extract_symbol_anchors(&args.query, &corpus)) } else { None };
    let cochange = if with_history {
        history.as_ref().map(|h| &h.cochange)
    } else {
        None
    };

    let params = SelectParams {
        cochange,
        max_additions: args.max_additions,
        seats_per_source: args.seats_per_source,
        import_hops: args.import_hops,
        eligible_floor: args.eligible_floor,
        k_lex: args.k_lex,
        symbol_graph: args.symbol_graph,
        ppr_budget: args.ppr_budget,
        ppr_additive: args.ppr_additive,
        anchors: anchors.as_deref(),
        use_testbridge,
        use_docsbridge: with_docs,
        trace_files: routed
            .as_ref()
            .filter(|rq| !rq.trace_files.is_empty())
            .map(|rq| rq.trace_files.as_slice())
            .or(if use_trace_boost && !boost_files.is_empty() { Some(boost_files.as_slice()) } else { None }),
        test_penalty: match &routed {
            Some(rq) if rq.fence_dominant => args.route_test_penalty,
            _ => 1.0,
        },
        lexboost: args.lexboost,
        lexboost_nbrs: lexboost_nbrs.as_ref(),
        lexboost_hubs: lexboost_hub_set.as_ref(),
        file_score: file_score_mode,
        test_bridge: args.test_bridge,
        ..Default::default()
    };
    let (mut files, scores, explain) = select_files(&corpus, &terms, true, &params);
    if args.k > 0 {
        files.truncate(args.k as usize);
    }

    let encoder = tiktoken_rs::cl100k_base_singleton();
    let count_tokens = |text: &str| -> usize { encoder.lock().encode_ordinary(text).len() };

    let anchor_files: HashSet<String> = explain.anchor_promotions.iter().map(|(f, ..)| f.clone()).collect();
    let anchor_symbols = if anchor_files.is_empty() {
        indexmap::IndexMap::new()
    } else {
        anchor_def_symbols(&args.query, &corpus, &anchor_files)
    };
    let (spans, bundle) = pack_regions(
        &corpus,
        &files,
        &terms,
        &scores,
        args.budget,
        &count_tokens,
        Some(&anchor_symbols),
        0.0,
        args.pad_lines,
        args.len_exp,
        args.family_enum,
        args.sibling_sim,
        args.max_siblings,
        block_mode,
    );
    let query_ms = t1.elapsed().as_secs_f64() * 1000.0;

    if args.explain {
        eprintln!("{}", serde_json::to_string_pretty(&explain).unwrap());
    }

    let packed_files: Vec<String> = files.iter().filter(|f| spans.contains_key(f.as_str())).cloned().collect();
    let bundle_tokens = if !bundle.is_empty() { count_tokens(&bundle) } else { 0 };
    let cache_state = if cache_hit { "hit" } else { "miss" };
    let low_confidence = is_low_confidence(explain.top_score, matched_terms, total_terms);

    let mut stats = serde_json::json!({
        "files_indexed": corpus.n_docs,
        "index_ms": index_ms.round() as i64,
        "query_ms": query_ms.round() as i64,
        "bundle_tokens": bundle_tokens,
        "cache": cache_state,
        "top_score": explain.top_score,
        "matched_query_terms": matched_terms,
        "total_query_terms": total_terms,
        "engine_sha": env!("ROUST_GIT_SHA"),
        "engine_dirty": env!("ROUST_GIT_DIRTY") == "dirty",
    });
    if low_confidence {
        stats["low_confidence"] = serde_json::json!(true);
    }
    if let Some(rq) = &routed {
        // Present only under --route (defaults stay byte-identical): the
        // per-query class + channel term counts + resolved trace files +
        // whether the conditional test penalty fired, for the E11 gate's
        // smoke checks and class-conditional scoring.
        stats["route"] = serde_json::json!({
            "class": rq.class(),
            "fence_dominant": rq.fence_dominant,
            "test_penalty_applied": rq.fence_dominant,
            "trace_files": rq.trace_files,
            "n_prose_terms": rq.n_prose_terms,
            "n_trace_terms": rq.n_trace_terms,
            "n_fence_terms": rq.n_fence_terms,
        });
    }
    if use_trace_boost {
        // Adopted default: the resolved frame files that received the E11b
        // FILE boost, raise-site first -- consumed by the eval harness's
        // flip itemization (frame rank per flip). Absent under
        // --no-trace-boost / --route.
        stats["trace_boost"] = serde_json::json!({
            "trace_files": boost_files,
            "formats_v2": use_trace_formats_v2,
        });
    }
    if file_score_mode != roust::core::FileScoreMode::Accum {
        // Present only under --file-score chunk-* (defaults stay byte-
        // identical): the old-vs-new score anatomy `(file, chunk_score,
        // accum_score, best_chunk_content, best_chunk_start,
        // best_chunk_end)`, consumed by the E21 gate's flip itemization.
        stats["file_score"] = serde_json::json!({
            "mode": args.file_score,
            "top": &explain.file_score_top,
        });
    }
    if args.test_bridge > 0.0 {
        // Present only under --test-bridge (defaults stay byte-identical):
        // the bridged files `(file, via_test, strength, added, call_hits)`
        // + count, consumed by the E22 gate's bridge-path anatomy and the
        // flooding check.
        stats["test_bridge"] = serde_json::json!({
            "weight": args.test_bridge,
            "n_bridged": explain.test_bridge.len(),
            "bridged": &explain.test_bridge,
        });
    }
    if file_score_mode != roust::core::FileScoreMode::Accum {
        // Present only under --file-score chunk-* (defaults stay byte-
        // identical): the old-vs-new score anatomy `(file, chunk_score,
        // accum_score, best_chunk_content, best_chunk_start,
        // best_chunk_end)`, consumed by the E21 gate's flip itemization.
        stats["file_score"] = serde_json::json!({
            "mode": args.file_score,
            "top": &explain.file_score_top,
        });
    }
    if args.test_bridge > 0.0 {
        // Present only under --test-bridge (defaults stay byte-identical):
        // the bridged files `(file, via_test, strength, added, call_hits)`
        // + count, consumed by the E22 gate's bridge-path anatomy and the
        // flooding check.
        stats["test_bridge"] = serde_json::json!({
            "weight": args.test_bridge,
            "n_bridged": explain.test_bridge.len(),
            "bridged": &explain.test_bridge,
        });
    }
    if args.lexboost > 0.0 {
        // Present only under --lexboost (defaults stay byte-identical):
        // graph shape + cost + the top-of-ranking smoothing anatomy
        // `(file, smoothed, direct, neighbor_mean, is_hub)`, consumed by
        // the E20 gate's flip itemization (direct-vs-neighbor anatomy).
        stats["lexboost"] = serde_json::json!({
            "lambda": args.lexboost,
            "graph": args.lexboost_graph,
            "graph_ms": lexboost_graph_ms.round() as i64,
            "n_files_in_graph": lexboost_nbrs.as_ref().map(|m| m.len()).unwrap_or(0),
            "n_hubs": lexboost_hub_set.as_ref().map(|h| h.len()).unwrap_or(0),
            "top": &explain.lexboost_top,
        });
    }

    if !packed_files.is_empty() {
        if args.json {
            let files_json: Vec<serde_json::Value> = packed_files
                .iter()
                .enumerate()
                .map(|(i, f)| serde_json::json!({"path": f, "score_rank": i}))
                .collect();
            let regions_json: serde_json::Map<String, serde_json::Value> = packed_files
                .iter()
                .map(|f| {
                    let rs = &spans[f.as_str()];
                    let v: Vec<Vec<usize>> = rs.iter().map(|(a, b)| vec![*a, *b]).collect();
                    (f.clone(), serde_json::json!(v))
                })
                .collect();
            let payload = serde_json::json!({
                "query": args.query,
                "files": files_json,
                "regions": regions_json,
                "bundle": bundle,
                "stats": stats,
            });
            println!("{}", serde_json::to_string(&payload).unwrap());
        } else if args.files_only {
            for f in &packed_files {
                println!("{f}");
            }
        } else {
            println!("{bundle}");
        }
    } else if args.json {
        // Empty result set under --json (issue #25, hardened): emit valid,
        // parseable JSON with an empty result set rather than nothing, so
        // callers scripting against --json never have to special-case "no
        // stdout at all". This fires for ANY empty `packed_files`, not just
        // the literal zero-match case -- query terms can match the corpus
        // vocabulary (docs pages, commit messages, path components) while
        // still selecting no packable code file, and that case must honor
        // the same "--json always prints exactly one JSON document" contract.
        let payload = serde_json::json!({
            "query": args.query,
            "files": [],
            "regions": {},
            "bundle": "",
            "stats": stats,
        });
        println!("{}", serde_json::to_string(&payload).unwrap());
    }

    // zero_match gets its own dedicated stderr message instead of the
    // generic low-confidence suffix -- it's the strictly stronger "nothing
    // in the corpus vocabulary matched at all" signal, not merely a weak
    // match.
    let confidence_note = if !zero_match && low_confidence { " [low-confidence match]" } else { "" };
    eprintln!(
        "roust: {} files, {} tokens (indexed {} files, index {}ms, query {}ms, cache {}){}",
        packed_files.len(),
        bundle_tokens,
        corpus.n_docs,
        index_ms.round() as i64,
        query_ms.round() as i64,
        cache_state,
        confidence_note,
    );
    if zero_match {
        eprintln!("roust: no query term matched anything in the indexed corpus vocabulary -- no results");
    } else if packed_files.is_empty() {
        eprintln!("roust: query terms matched the corpus vocabulary but no packable file was selected -- no results");
    }

    // Exit contract (see module doc / README): 1 = no results, covering both
    // literal zero-match AND an empty packed result set with vocabulary
    // matches. Applies uniformly across output modes -- exit codes must not
    // depend on whether --json/--files-only was passed. (`zero_match` is
    // kept in the condition even though it should always imply an empty
    // result set, so the pre-hardening exit-1 guarantee can never regress.)
    if zero_match || packed_files.is_empty() {
        std::process::exit(1);
    }
}
