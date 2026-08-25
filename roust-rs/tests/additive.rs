//! WS1b `--index-all-additive` invariant tests, exercising the real `roust`
//! binary (`CARGO_BIN_EXE_roust`) end to end.
//!
//! The load-bearing contract (campaign #56, WS1b): the flagged run's output
//! must be the unflagged run's output PLUS zero or more appended newcomer
//! files -- the unflagged file set is always a subset, every unflagged
//! file's spans are byte-unchanged, the bundle starts with the unflagged
//! bundle, and when no leftover budget exists the two outputs are
//! identical. Newcomer admission can consume only budget the unflagged
//! engine left unused.

use std::path::{Path, PathBuf};
use std::process::Command;

fn make_repo(tag: &str) -> PathBuf {
    let repo = std::env::temp_dir().join(format!("roust_ws1b_{tag}_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&repo);
    std::fs::create_dir_all(repo.join("pkg")).unwrap();
    // Allowlisted code files: the core selection.
    std::fs::write(
        repo.join("pkg/widgets.py"),
        "\"\"\"Widget pricing validation.\"\"\"\n\n\ndef validate_widget_pricing(widget, rules):\n    \"\"\"Validate widget pricing against the configured rules.\"\"\"\n    for rule in rules:\n        if not rule.check(widget):\n            return False\n    return True\n",
    )
    .unwrap();
    std::fs::write(
        repo.join("pkg/server.py"),
        "\"\"\"HTTP entry point.\"\"\"\n\n\ndef run_server(port):\n    return port + 1\n",
    )
    .unwrap();
    // Non-allowlisted newcomer carrying the query vocabulary: only
    // indexable under --index-all / --index-all-additive.
    std::fs::write(
        repo.join("pkg/widget_rules.json"),
        "{\n  \"widget\": \"pricing validation rules\",\n  \"rules\": [\"widget pricing must validate\"]\n}\n",
    )
    .unwrap();
    repo
}

fn run_json(repo: &Path, extra: &[&str], query: &str) -> serde_json::Value {
    let out = Command::new(env!("CARGO_BIN_EXE_roust"))
        .arg("--json")
        .args(extra)
        .arg(query)
        .arg(repo)
        .arg("--no-cache")
        .output()
        .expect("failed to spawn roust binary");
    let stdout = String::from_utf8(out.stdout).unwrap();
    serde_json::from_str(stdout.trim()).expect("stdout must be exactly one valid JSON document")
}

fn file_paths(v: &serde_json::Value) -> Vec<String> {
    v["files"].as_array().unwrap().iter().map(|f| f["path"].as_str().unwrap().to_string()).collect()
}

/// Core invariant: flagged output == unflagged output + appended newcomers.
/// The unflagged files keep their positions AND their exact spans; the
/// bundle is prefix-identical; the admitted newcomer is a non-allowlisted
/// file with spans of its own; total bundle tokens stay within --budget.
#[test]
fn additive_appends_newcomers_without_touching_core() {
    let repo = make_repo("invariant");
    let query = "widget pricing validation rules";
    let base = run_json(&repo, &[], query);
    let add = run_json(&repo, &["--index-all-additive"], query);

    let base_files = file_paths(&base);
    let add_files = file_paths(&add);
    assert!(!base_files.is_empty(), "fixture must produce a non-empty core selection");
    assert!(
        add_files.len() > base_files.len(),
        "expected at least one admitted newcomer (leftover budget is ample), got {add_files:?}"
    );
    // Superset with core order preserved: flagged list starts with the
    // unflagged list, newcomers strictly appended.
    assert_eq!(
        &add_files[..base_files.len()],
        base_files.as_slice(),
        "core selection must be a byte-identical prefix of the flagged selection"
    );
    for f in &add_files[base_files.len()..] {
        assert!(
            !roust::core::has_allowlisted_suffix(f),
            "appended file {f} is allowlisted -- only newcomers may be appended"
        );
    }
    // Core spans byte-unchanged.
    for f in &base_files {
        assert_eq!(
            add["regions"][f], base["regions"][f],
            "core file {f} spans changed under --index-all-additive"
        );
    }
    // Newcomers have spans of their own.
    for f in &add_files[base_files.len()..] {
        assert!(
            add["regions"][f].as_array().is_some_and(|a| !a.is_empty()),
            "admitted newcomer {f} has no spans"
        );
    }
    // Bundle prefix-identical: the flagged bundle is core bundle + "\n\n" +
    // newcomer sections.
    let base_bundle = base["bundle"].as_str().unwrap();
    let add_bundle = add["bundle"].as_str().unwrap();
    assert!(
        add_bundle.starts_with(base_bundle),
        "flagged bundle must start with the unflagged bundle"
    );
    // Budget guard: newcomers consumed only leftover budget (default 8192).
    assert!(add["stats"]["bundle_tokens"].as_i64().unwrap() <= 8192);
    // Stats anatomy present and consistent.
    let st = &add["stats"]["index_all_additive"];
    assert!(st["n_files_beyond_allowlist"].as_i64().unwrap() >= 1);
    assert_eq!(
        st["n_newcomers_admitted"].as_u64().unwrap() as usize,
        add_files.len() - base_files.len()
    );
    assert!(st["newcomer_tokens"].as_i64().unwrap() > 0);

    std::fs::remove_dir_all(&repo).ok();
}

/// No leftover budget => no admissions: with a budget the core bundle
/// already exhausts, the flagged output is identical to the unflagged one
/// (files, regions, bundle) -- regression to the core is structurally
/// impossible, not just unlikely.
#[test]
fn additive_with_no_leftover_budget_is_identical_to_defaults() {
    let repo = make_repo("noleftover");
    let query = "widget pricing validation rules";
    // Tiny budget: pass-1 seats the core unconditionally and leaves nothing.
    let base = run_json(&repo, &["--budget", "60"], query);
    let add = run_json(&repo, &["--budget", "60", "--index-all-additive"], query);

    assert_eq!(add["files"], base["files"], "file set must be identical when no budget is left");
    assert_eq!(add["regions"], base["regions"], "regions must be identical when no budget is left");
    assert_eq!(add["bundle"], base["bundle"], "bundle must be identical when no budget is left");
    assert_eq!(add["stats"]["index_all_additive"]["n_newcomers_admitted"], serde_json::json!(0));

    std::fs::remove_dir_all(&repo).ok();
}

/// WS1b reserve variant: --newcomer-reserve shrinks the CORE pack budget
/// (never the core file set -- pass 1 seats every selected file
/// unconditionally) to guarantee newcomer headroom. Contract: the
/// unflagged packed file LIST is still a byte-identical prefix of the
/// flagged list (set + order), newcomers are appended, and the total
/// stays within the full budget whenever a newcomer was admitted. Core
/// spans MAY differ from the unflagged run (that is the trade), so no
/// span equality is asserted for the reserve variant.
#[test]
fn reserve_preserves_core_file_set_and_appends_newcomers() {
    let repo = make_repo("reserve");
    let query = "widget pricing validation rules";
    let base = run_json(&repo, &[], query);
    let add = run_json(&repo, &["--index-all-additive", "--newcomer-reserve", "0.10"], query);

    let base_files = file_paths(&base);
    let add_files = file_paths(&add);
    assert_eq!(
        &add_files[..base_files.len()],
        base_files.as_slice(),
        "core packed file list must be a byte-identical prefix under --newcomer-reserve"
    );
    for f in &add_files[base_files.len()..] {
        assert!(!roust::core::has_allowlisted_suffix(f), "appended file {f} is allowlisted");
    }
    let st = &add["stats"]["index_all_additive"];
    assert_eq!(st["core_budget"].as_i64().unwrap(), 8192 - 819, "core budget must be budget*(1-0.10)");
    if st["n_newcomers_admitted"].as_u64().unwrap() > 0 {
        assert!(add["stats"]["bundle_tokens"].as_i64().unwrap() <= 8192);
    }

    std::fs::remove_dir_all(&repo).ok();
}

/// --newcomer-reserve without --index-all-additive is a usage error.
#[test]
fn reserve_requires_additive_flag() {
    let repo = make_repo("reserve_req");
    let out = Command::new(env!("CARGO_BIN_EXE_roust"))
        .args(["--newcomer-reserve", "0.10", "widget"])
        .arg(&repo)
        .arg("--no-cache")
        .output()
        .expect("failed to spawn roust binary");
    assert_eq!(out.status.code(), Some(2), "reserve without additive must be a usage error");

    std::fs::remove_dir_all(&repo).ok();
}

/// --index-all and --index-all-additive are mutually exclusive (usage
/// error, exit 2): one re-ranks everything, the other guards the core --
/// silently combining them has no coherent meaning.
#[test]
fn additive_conflicts_with_index_all() {
    let repo = make_repo("conflict");
    let out = Command::new(env!("CARGO_BIN_EXE_roust"))
        .args(["--index-all", "--index-all-additive", "widget", ])
        .arg(&repo)
        .arg("--no-cache")
        .output()
        .expect("failed to spawn roust binary");
    assert_eq!(out.status.code(), Some(2), "conflicting flags must be a usage error");

    std::fs::remove_dir_all(&repo).ok();
}
