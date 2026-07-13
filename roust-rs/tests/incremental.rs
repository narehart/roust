//! Incremental index-update tests for `roust::cache` -- a Rust port of
//! `tests/test_incremental.py`'s property test.
//!
//! Core acceptance bar (see `cache.rs`'s module docstring): an
//! incrementally-patched Corpus must be OBSERVATIONALLY IDENTICAL to a
//! fresh-built Corpus over the same on-disk content -- same `select_files()`
//! output (files AND scores) for any query. These tests build a synthetic
//! repo, apply a scripted sequence of content-only edits, and after EACH
//! edit compare the cache's `load_or_build_ex()` result against an
//! independently fresh-built Corpus, while also asserting which update path
//! (`"unchanged"` / `"incremental"` / `"full"`) was actually taken.

use roust::cache;
use roust::core::{self, extract_symbol_anchors, query_terms, select_files, Corpus, SelectParams};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::Command;

const QUERIES: &[&str] = &[
    "how does the router dispatch requests to handlers",
    "how are widgets validated before creation",
    "how is application configuration loaded",
];

const INIT: &str = "\"\"\"Widget package: models, validation, handlers, routing, and config.\"\"\"\n";

const MODELS: &str = concat!(
    "\"\"\"Domain models for widgets.\"\"\"\n\n\n",
    "class Widget:\n",
    "    \"\"\"A widget resource with a name and a price.\"\"\"\n\n",
    "    def __init__(self, name, price):\n",
    "        self.name = name\n",
    "        self.price = price\n\n",
    "    def describe(self):\n",
    "        return f\"{self.name}: {self.price}\"\n",
);

const VALIDATORS_V1: &str = concat!(
    "\"\"\"Validation helpers for widget models.\"\"\"\n\n",
    "from pkg.models import Widget\n\n\n",
    "def validate_widget(widget):\n",
    "    \"\"\"Validate that a widget has a positive price.\"\"\"\n",
    "    if widget.price <= 0:\n",
    "        raise ValueError(\"widget price must be positive\")\n",
    "    return True\n",
);

const VALIDATORS_V2: &str = concat!(
    "\"\"\"Validation helpers for widget models.\"\"\"\n\n",
    "from pkg.models import Widget\n\n\n",
    "def validate_widget(widget):\n",
    "    \"\"\"Validate that a widget has a positive price and a name.\"\"\"\n",
    "    if widget.price <= 0:\n",
    "        raise ValueError(\"widget price must be positive\")\n",
    "    if not widget.name:\n",
    "        raise ValueError(\"widget name must not be empty\")\n",
    "    return True\n",
);

const UTILS_V1: &str = concat!(
    "\"\"\"Shared string utility helpers.\"\"\"\n\n\n",
    "def normalize_name(name):\n",
    "    return name.strip().lower()\n",
);

const UTILS_V2: &str = concat!(
    "\"\"\"Shared string utility helpers.\"\"\"\n\n\n",
    "def normalize_name(name):\n",
    "    return name.strip().lower()\n\n\n",
    "def slugify(name):\n",
    "    \"\"\"Convert a name into a url-safe slug.\"\"\"\n",
    "    return normalize_name(name).replace(\" \", \"-\")\n",
);

const CONFIG: &str = concat!(
    "\"\"\"Static configuration loading.\"\"\"\n\n",
    "DEFAULT_TIMEOUT = 30\n\n\n",
    "def load_config():\n",
    "    return {\"timeout\": DEFAULT_TIMEOUT}\n",
);

const HANDLERS_V1: &str = concat!(
    "\"\"\"Request handlers for widget operations.\"\"\"\n\n",
    "from pkg.models import Widget\n",
    "from pkg.validators import validate_widget\n\n\n",
    "def handle_create_widget(request):\n",
    "    widget = Widget(request[\"name\"], request[\"price\"])\n",
    "    validate_widget(widget)\n",
    "    return widget.describe()\n",
);

const HANDLERS_V2: &str = concat!(
    "\"\"\"Request handlers for widget operations.\"\"\"\n\n",
    "from pkg.models import Widget\n",
    "from pkg.validators import validate_widget\n",
    "from pkg.utils import normalize_name\n\n\n",
    "def handle_create_widget(request):\n",
    "    widget = Widget(normalize_name(request[\"name\"]), request[\"price\"])\n",
    "    validate_widget(widget)\n",
    "    return widget.describe()\n",
);

const ROUTER_V1: &str = concat!(
    "\"\"\"Routing logic: maps incoming requests to handlers.\"\"\"\n\n",
    "from pkg.handlers import handle_create_widget\n\n\n",
    "class Router:\n",
    "    \"\"\"Dispatches incoming requests to the correct registered handler.\"\"\"\n\n",
    "    def __init__(self):\n",
    "        self.routes = {\"create_widget\": handle_create_widget}\n\n",
    "    def dispatch(self, path, request):\n",
    "        handler = self.routes.get(path)\n",
    "        return handler(request)\n",
);

const ROUTER_V2: &str = concat!(
    "\"\"\"Routing logic: maps incoming requests to handlers.\"\"\"\n\n",
    "from pkg.handlers import handle_create_widget\n\n\n",
    "class Router:\n",
    "    \"\"\"Dispatches incoming requests to the correct registered handler.\"\"\"\n\n",
    "    def __init__(self):\n",
    "        self.routes = {\"create_widget\": handle_create_widget}\n\n",
    "    def add_route(self, path, handler):\n",
    "        self.routes[path] = handler\n\n",
    "    def dispatch(self, path, request):\n",
    "        handler = self.routes.get(path)\n",
    "        if handler is None:\n",
    "            raise KeyError(f\"no handler registered for {path}\")\n",
    "        return handler(request)\n",
);

const SERVICE_V1: &str = concat!(
    "\"\"\"Top-level service wiring router and config together.\"\"\"\n\n",
    "from pkg.router import Router\n",
    "from pkg.config import load_config\n\n\n",
    "class Service:\n",
    "    \"\"\"Application service entry point.\"\"\"\n\n",
    "    def __init__(self):\n",
    "        self.router = Router()\n",
    "        self.config = load_config()\n\n",
    "    def handle(self, path, request):\n",
    "        return self.router.dispatch(path, request)\n",
);

const SERVICE_V2: &str = concat!(
    "\"\"\"Top-level service wiring router and config together.\"\"\"\n\n",
    "from pkg.router import Router\n",
    "from pkg.config import load_config\n\n\n",
    "class Service:\n",
    "    \"\"\"Application service entry point.\"\"\"\n\n",
    "    def __init__(self):\n",
    "        self.router = Router()\n",
    "        self.config = load_config()\n\n",
    "    def handle(self, path, request):\n",
    "        return self.router.dispatch(path, request)\n\n",
    "    def timeout(self):\n",
    "        return self.config[\"timeout\"]\n",
);

fn files_v1() -> Vec<(&'static str, &'static str)> {
    vec![
        ("pkg/__init__.py", INIT),
        ("pkg/models.py", MODELS),
        ("pkg/validators.py", VALIDATORS_V1),
        ("pkg/utils.py", UTILS_V1),
        ("pkg/config.py", CONFIG),
        ("pkg/handlers.py", HANDLERS_V1),
        ("pkg/router.py", ROUTER_V1),
        ("pkg/service.py", SERVICE_V1),
    ]
}

fn make_repo(base: &Path, tag: &str) -> PathBuf {
    let repo = base.join(format!("repo_{tag}_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&repo);
    std::fs::create_dir_all(repo.join("pkg")).unwrap();
    for (rel, text) in files_v1() {
        std::fs::write(repo.join(rel), text).unwrap();
    }
    repo
}

/// Write new content, then explicitly bump mtime forward so filesystems
/// with coarse mtime resolution still observe a change (mirrors
/// `test_incremental.py`'s `_write`).
fn write_bumped(repo: &Path, rel: &str, text: &str) {
    let p = repo.join(rel);
    std::fs::write(&p, text).unwrap();
    bump_mtime(&p);
}

fn touch_bumped(repo: &Path, rel: &str) {
    bump_mtime(&repo.join(rel));
}

fn bump_mtime(p: &Path) {
    let meta = std::fs::metadata(p).unwrap();
    let mtime = filetime::FileTime::from_last_modification_time(&meta);
    let bumped = filetime::FileTime::from_unix_time(mtime.seconds() + 10, mtime.nanoseconds());
    filetime::set_file_mtime(p, bumped).unwrap();
}

fn select(corpus: &Corpus, query: &str) -> (Vec<String>, indexmap::IndexMap<String, f64>) {
    let terms = query_terms(query, &[]);
    let anchors = extract_symbol_anchors(query, corpus);
    let params = SelectParams { anchors: Some(&anchors), use_testbridge: true, use_docsbridge: false, ..Default::default() };
    let (files, scores, _explain) = select_files(corpus, &terms, true, &params);
    (files, scores)
}

fn rounded_scores(scores: &indexmap::IndexMap<String, f64>) -> BTreeMap<String, String> {
    scores.iter().map(|(k, v)| (k.clone(), format!("{v:.9}"))).collect()
}

fn assert_matches_fresh_build(repo: &Path, cached_corpus: &Corpus) {
    let fresh = Corpus::build(repo, None, false, false);
    assert_eq!(cached_corpus.files, fresh.files, "file list diverged");
    for &query in QUERIES {
        let (c_files, c_scores) = select(cached_corpus, query);
        let (f_files, f_scores) = select(&fresh, query);
        assert_eq!(c_files, f_files, "file list diverged for query: {query:?}");
        assert_eq!(rounded_scores(&c_scores), rounded_scores(&f_scores), "scores diverged for query: {query:?}");
    }
}

#[test]
fn incremental_property() {
    let base = std::env::temp_dir();
    let repo = make_repo(&base, "prop");
    let router_v1 = ROUTER_V1;

    // Seed the cache with an initial full build.
    let (corpus, _edges, _history, cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "full");
    assert!(!cache_hit);
    assert_matches_fresh_build(&repo, &corpus);

    // Step 1: modify a function body (validators.py) -- no import/def change.
    write_bumped(&repo, "pkg/validators.py", VALIDATORS_V2);
    let (corpus, _edges, _history, cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "incremental", "step 1 (modify function body) should patch, not rebuild");
    assert!(cache_hit);
    assert_matches_fresh_build(&repo, &corpus);

    // Step 2: modify imports in a file (handlers.py starts importing utils).
    write_bumped(&repo, "pkg/handlers.py", HANDLERS_V2);
    let (corpus, edges, _history, _cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "incremental", "step 2 (modify imports) should patch, not rebuild");
    assert!(
        edges.get("pkg/handlers.py").map(|s| s.contains("pkg/utils.py")).unwrap_or(false),
        "new import edge missing"
    );
    assert_matches_fresh_build(&repo, &corpus);

    // Step 3: modify a file to add a new def (utils.py gains slugify()).
    write_bumped(&repo, "pkg/utils.py", UTILS_V2);
    let (corpus, _edges, _history, _cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "incremental", "step 3 (add a def) should patch, not rebuild");
    assert_eq!(corpus.def_index.get("slugify"), Some(&vec!["pkg/utils.py".to_string()]));
    assert_matches_fresh_build(&repo, &corpus);

    // Step 4: touch a file without content change (config.py).
    touch_bumped(&repo, "pkg/config.py");
    let (corpus, _edges, _history, _cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "incremental", "step 4 (mtime-only touch) should patch, not rebuild");
    assert_matches_fresh_build(&repo, &corpus);

    // Step 5: modify two files at once (router.py and service.py).
    write_bumped(&repo, "pkg/router.py", ROUTER_V2);
    write_bumped(&repo, "pkg/service.py", SERVICE_V2);
    let (corpus, _edges, _history, _cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "incremental", "step 5 (two files at once) should patch, not rebuild");
    assert_matches_fresh_build(&repo, &corpus);

    // Step 6: revert a file (router.py back to its original content).
    write_bumped(&repo, "pkg/router.py", router_v1);
    let (corpus, _edges, _history, _cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "incremental", "step 6 (revert) should patch, not rebuild");
    assert!(!corpus.text["pkg/router.py"].contains("add_route"));
    assert_matches_fresh_build(&repo, &corpus);

    std::fs::remove_dir_all(&repo).ok();
}

#[test]
fn add_file_triggers_full_rebuild() {
    let base = std::env::temp_dir();
    let repo = make_repo(&base, "add");
    cache::load_or_build_ex(&repo, false, false, true, false);

    std::fs::write(
        repo.join("pkg/extra.py"),
        "\"\"\"A brand new module.\"\"\"\n\n\ndef extra_fn():\n    return 1\n",
    )
    .unwrap();
    let (corpus, _edges, _history, cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "full", "adding a file must force a full rebuild");
    assert!(!cache_hit);
    assert!(corpus.files.contains(&"pkg/extra.py".to_string()));
    assert_matches_fresh_build(&repo, &corpus);

    std::fs::remove_dir_all(&repo).ok();
}

#[test]
fn remove_file_triggers_full_rebuild() {
    let base = std::env::temp_dir();
    let repo = make_repo(&base, "rm");
    cache::load_or_build_ex(&repo, false, false, true, false);

    std::fs::remove_file(repo.join("pkg/utils.py")).unwrap();
    let (corpus, _edges, _history, cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "full", "removing a file must force a full rebuild");
    assert!(!cache_hit);
    assert!(!corpus.files.contains(&"pkg/utils.py".to_string()));
    assert_matches_fresh_build(&repo, &corpus);

    std::fs::remove_dir_all(&repo).ok();
}

#[test]
fn unchanged_repo_is_pure_cache_hit() {
    let base = std::env::temp_dir();
    let repo = make_repo(&base, "unchanged");
    cache::load_or_build_ex(&repo, false, false, true, false);
    let (_corpus, _edges, _history, cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "unchanged");
    assert!(cache_hit);

    std::fs::remove_dir_all(&repo).ok();
}

#[test]
fn docs_field_incremental_update() {
    let base = std::env::temp_dir();
    let repo = make_repo(&base, "docs");
    std::fs::create_dir_all(repo.join("docs")).unwrap();
    std::fs::write(repo.join("docs/guide.md"), "# Guide\n\nSee pkg.router.Router for dispatch details.\n").unwrap();
    cache::load_or_build_ex(&repo, false, true, true, false);

    write_bumped(&repo, "docs/guide.md", "# Guide\n\nSee pkg.service.Service for the entry point.\n");
    let (corpus, _edges, _history, _cache_hit, kind) = cache::load_or_build_ex(&repo, false, true, true, false);
    assert_eq!(kind, "incremental", "docs-only content edit should patch, not rebuild");
    assert!(corpus.docs_text["docs/guide.md"].contains("service"));
    let fresh = Corpus::build(&repo, None, false, true);
    assert_eq!(corpus.docs_tf, fresh.docs_tf);
    assert_eq!(corpus.docs_df, fresh.docs_df);

    std::fs::remove_dir_all(&repo).ok();
}

/// The tricky case in `update_import_graph_for_files`: A and B import each
/// other; A is edited to stop importing B, but B (unchanged) still imports
/// A. The (A, B) edge must survive since B independently still authors it.
/// A subsequent edit removing B's import too must then fully remove it.
#[test]
fn reverse_import_edge_preserved_when_only_one_side_still_imports() {
    let base = std::env::temp_dir();
    let repo = base.join(format!("repo_reverse_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&repo);
    std::fs::create_dir_all(repo.join("pkg")).unwrap();
    std::fs::write(repo.join("pkg/__init__.py"), "\"\"\"pkg.\"\"\"\n").unwrap();
    let a_v1 = "\"\"\"Module A.\"\"\"\n\nfrom pkg.b import helper_b\n\n\ndef helper_a():\n    return helper_b() + 1\n";
    let b_v1 = "\"\"\"Module B.\"\"\"\n\nfrom pkg.a import helper_a\n\n\ndef helper_b():\n    return 1\n\n\ndef other_b():\n    return helper_a() + 2\n";
    std::fs::write(repo.join("pkg/a.py"), a_v1).unwrap();
    std::fs::write(repo.join("pkg/b.py"), b_v1).unwrap();

    let mut corpus = Corpus::build(&repo, None, false, false);
    let mut edges = core::build_import_graph(&corpus);
    assert!(edges["pkg/a.py"].contains("pkg/b.py"));
    assert!(edges["pkg/b.py"].contains("pkg/a.py"));

    // A drops the import of B; B is untouched and still imports A.
    let a_v2 = "\"\"\"Module A, standalone now.\"\"\"\n\n\ndef helper_a():\n    return 42\n";
    let old_text: std::collections::HashMap<String, String> =
        [("pkg/a.py".to_string(), corpus.text["pkg/a.py"].clone())].into_iter().collect();
    std::fs::write(repo.join("pkg/a.py"), a_v2).unwrap();
    assert!(corpus.update_files(&["pkg/a.py".to_string()]));
    core::update_import_graph_for_files(&corpus, &mut edges, &old_text);

    assert!(edges.get("pkg/b.py").map(|s| s.contains("pkg/a.py")).unwrap_or(false), "B's own import of A must survive");
    assert!(edges.get("pkg/a.py").map(|s| s.contains("pkg/b.py")).unwrap_or(false), "edge must stay symmetric");

    let fresh1 = Corpus::build(&repo, None, false, false);
    let fresh_edges1 = core::build_import_graph(&fresh1);
    assert_eq!(edges, fresh_edges1);

    // Now B also drops its import of A -- the edge must fully disappear.
    let b_v2 =
        "\"\"\"Module B, standalone now.\"\"\"\n\n\ndef helper_b():\n    return 1\n\n\ndef other_b():\n    return 2\n";
    let old_text2: std::collections::HashMap<String, String> =
        [("pkg/b.py".to_string(), corpus.text["pkg/b.py"].clone())].into_iter().collect();
    std::fs::write(repo.join("pkg/b.py"), b_v2).unwrap();
    assert!(corpus.update_files(&["pkg/b.py".to_string()]));
    core::update_import_graph_for_files(&corpus, &mut edges, &old_text2);

    assert!(!edges.get("pkg/a.py").map(|s| s.contains("pkg/b.py")).unwrap_or(false));
    assert!(!edges.get("pkg/b.py").map(|s| s.contains("pkg/a.py")).unwrap_or(false));

    let fresh2 = Corpus::build(&repo, None, false, false);
    let fresh_edges2 = core::build_import_graph(&fresh2);
    assert_eq!(edges, fresh_edges2);

    std::fs::remove_dir_all(&repo).ok();
}

fn git(repo: &Path, args: &[&str]) {
    let status = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(args)
        .status()
        .expect("failed to run git");
    assert!(status.success(), "git {args:?} failed in {repo:?}");
}

/// Like `make_repo`, but a real git repo (init + commit) so
/// `cache::scan_manifest`'s git-ls-files-first candidate enumeration is
/// exercised rather than the raw-walk fallback the other tests in this file
/// hit (their repos are never git-initialized). Ported from
/// `tests/test_incremental.py`'s `_make_git_repo`.
fn make_git_repo(base: &Path, tag: &str) -> PathBuf {
    let repo = make_repo(base, tag);
    git(&repo, &["init", "-q"]);
    git(&repo, &["-c", "user.email=test@test.invalid", "-c", "user.name=test", "add", "-A"]);
    git(
        &repo,
        &["-c", "user.email=test@test.invalid", "-c", "user.name=test", "commit", "-q", "-m", "test: initial commit"],
    );
    repo
}

/// A .gitignore'd file appearing on disk (e.g. a build artifact, or -- the
/// motivating case -- a .venv/ package file) must never flip the cache
/// verdict away from "unchanged": `scan_manifest` enumerates candidates via
/// the same git-ls-files-first source `Corpus` itself indexes, so an ignored
/// file was never a manifest entry to begin with. A subsequent edit to an
/// actually-tracked file must still be detected and patched incrementally.
/// Ported from `tests/test_incremental.py::test_gitignored_file_creation_does_not_trigger_rebuild`.
#[test]
fn gitignored_file_creation_does_not_trigger_rebuild() {
    let base = std::env::temp_dir();
    let repo = make_git_repo(&base, "gitignore");

    let (corpus, _edges, _history, _cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "full");
    assert!(corpus.files.contains(&"pkg/router.py".to_string()));

    std::fs::write(repo.join(".gitignore"), "ignored_pkg/\n").unwrap();
    std::fs::create_dir_all(repo.join("ignored_pkg")).unwrap();
    std::fs::write(
        repo.join("ignored_pkg/junk.py"),
        "\"\"\"Should never be indexed -- lives under a gitignored directory.\"\"\"\n\n\ndef junk_fn():\n    return 0\n",
    )
    .unwrap();

    let (corpus, _edges, _history, cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "unchanged", "an ignored file appearing on disk must not trigger a rebuild");
    assert!(cache_hit);
    assert!(!corpus.files.contains(&"ignored_pkg/junk.py".to_string()));

    // A tracked-file edit must still be detected and incrementally patched.
    write_bumped(&repo, "pkg/validators.py", VALIDATORS_V2);
    let (corpus, _edges, _history, cache_hit, kind) = cache::load_or_build_ex(&repo, false, false, true, false);
    assert_eq!(kind, "incremental", "a tracked-file edit must still be detected");
    assert!(cache_hit);
    assert!(!corpus.files.contains(&"ignored_pkg/junk.py".to_string()));
    assert_matches_fresh_build(&repo, &corpus);

    std::fs::remove_dir_all(&repo).ok();
}
