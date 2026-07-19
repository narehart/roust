//! CLI output/exit-code contract tests, exercising the real `roust` binary
//! (`CARGO_BIN_EXE_roust`) end to end.
//!
//! The load-bearing one is the reviewer's live repro: query terms that match
//! ONLY a docs page (`.md`) are corpus vocabulary (so not a literal
//! zero-match) yet select no packable code file -- pre-fix, `--json` printed
//! NOTHING on stdout and exited 0, violating both the "--json always prints
//! exactly one JSON document" contract and the "1 = no results" exit
//! contract. Post-fix: valid empty-payload JSON on stdout + exit 1.

use std::path::{Path, PathBuf};
use std::process::Command;

fn make_repo(tag: &str) -> PathBuf {
    let repo = std::env::temp_dir().join(format!("roust_cli_{tag}_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&repo);
    std::fs::create_dir_all(&repo).unwrap();
    // One indexable code file that shares no vocabulary with the probe query.
    std::fs::write(
        repo.join("app.py"),
        "\"\"\"Application entry point.\"\"\"\n\n\ndef run_server(port):\n    return port + 1\n",
    )
    .unwrap();
    // One docs page carrying the probe terms -- vocabulary, but not packable.
    std::fs::write(repo.join("NOTES.md"), "# Notes\n\nfrobnicate the quuxify glorp subsystem carefully.\n").unwrap();
    repo
}

fn run_roust(repo: &Path, args: &[&str]) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_roust"))
        .args(args)
        .arg(repo)
        .arg("--no-cache")
        .output()
        .expect("failed to spawn roust binary")
}

/// Empty result set with vocabulary matches (docs-only match): stdout must
/// carry exactly one valid JSON document with an empty result set, and the
/// exit code must be 1 ("no results").
#[test]
fn json_empty_results_with_docs_match_emits_valid_json_and_exit_1() {
    let repo = make_repo("docsmatch");
    let out = run_roust(&repo, &["--json", "frobnicate quuxify glorp"]);

    let stdout = String::from_utf8(out.stdout).unwrap();
    let v: serde_json::Value =
        serde_json::from_str(stdout.trim()).expect("stdout must be exactly one valid JSON document");
    assert_eq!(v["files"], serde_json::json!([]), "files must be an empty array");
    assert_eq!(v["regions"], serde_json::json!({}), "regions must be an empty object");
    assert_eq!(v["bundle"], serde_json::json!(""), "bundle must be the empty string");
    assert!(
        v["stats"]["matched_query_terms"].as_i64().unwrap() > 0,
        "fixture must NOT be a literal zero-match -- the .md page carries the query terms as vocabulary (got stats: {})",
        v["stats"]
    );
    assert_eq!(out.status.code(), Some(1), "empty result set must exit 1 (no results)");

    std::fs::remove_dir_all(&repo).ok();
}

/// Literal zero-match keeps its existing contract: valid empty JSON, exit 1.
#[test]
fn json_zero_match_emits_valid_json_and_exit_1() {
    let repo = make_repo("zeromatch");
    let out = run_roust(&repo, &["--json", "zzqxv yyqkw"]);

    let stdout = String::from_utf8(out.stdout).unwrap();
    let v: serde_json::Value =
        serde_json::from_str(stdout.trim()).expect("stdout must be exactly one valid JSON document");
    assert_eq!(v["files"], serde_json::json!([]));
    assert_eq!(v["stats"]["matched_query_terms"], serde_json::json!(0));
    assert_eq!(out.status.code(), Some(1), "zero-match must exit 1");

    std::fs::remove_dir_all(&repo).ok();
}

/// Exit codes must not depend on the output mode: the docs-only-match empty
/// result set exits 1 without --json too (default bundle mode).
#[test]
fn empty_results_exit_1_without_json_mode() {
    let repo = make_repo("nojson");
    let out = run_roust(&repo, &["frobnicate quuxify glorp"]);
    assert_eq!(out.status.code(), Some(1), "empty result set must exit 1 in bundle mode too");

    std::fs::remove_dir_all(&repo).ok();
}

/// Sanity: a query with real results still exits 0 with populated JSON.
#[test]
fn json_with_results_exits_0() {
    let repo = make_repo("results");
    let out = run_roust(&repo, &["--json", "run server port"]);

    let stdout = String::from_utf8(out.stdout).unwrap();
    let v: serde_json::Value = serde_json::from_str(stdout.trim()).expect("stdout must be valid JSON");
    assert!(!v["files"].as_array().unwrap().is_empty(), "expected app.py in results, got: {v}");
    assert_eq!(out.status.code(), Some(0));

    std::fs::remove_dir_all(&repo).ok();
}
