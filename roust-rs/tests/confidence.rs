//! CLI-level tests for the low-confidence signal + zero-match exit-1
//! contract (issue #25): runs the real compiled `roust` binary (not the
//! library directly) since exit codes and `--json` stats assembly live in
//! `main.rs`, not `roust::core`. Uses this crate's own source tree
//! (`CARGO_MANIFEST_DIR`, i.e. `roust-rs/`) as a realistic-size fixture
//! corpus -- the calibrated thresholds (`core::LOW_CONFIDENCE_TOP_SCORE` /
//! `LOW_CONFIDENCE_MATCH_FRACTION`) were tuned against real, non-toy
//! repositories, and a handful of synthetic files is too small a corpus for
//! raw BM25F scores to clear them even on a genuinely on-topic query.

use serde_json::Value;
use std::path::PathBuf;
use std::process::Command;

/// `roust-rs/src` (NOT the whole crate root): a real, decent-size fixture
/// corpus without also indexing THIS test file -- if the crate root were
/// used, the gibberish query strings below would literally appear verbatim
/// in the indexed corpus (this very file), self-polluting the vocabulary and
/// making every "gibberish" query trivially match itself.
fn roust_repo() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src")
}

struct RunResult {
    code: i32,
    stdout_json: Option<Value>,
    stderr: String,
}

fn run_json(query: &str) -> RunResult {
    let out = Command::new(env!("CARGO_BIN_EXE_roust"))
        .arg("--json")
        .arg(query)
        .arg(roust_repo())
        .arg("--no-cache")
        .output()
        .expect("failed to run roust binary");
    let stdout = String::from_utf8_lossy(&out.stdout).into_owned();
    let stderr = String::from_utf8_lossy(&out.stderr).into_owned();
    let stdout_json = if stdout.trim().is_empty() { None } else { Some(serde_json::from_str(&stdout).expect("stdout must be valid JSON")) };
    RunResult { code: out.status.code().unwrap_or(-1), stdout_json, stderr }
}

#[test]
fn matching_query_has_no_low_confidence_flag() {
    // Strongly on-topic against this crate's own source (real select_files
    // vocabulary): should clear both calibrated thresholds comfortably.
    let r = run_json("how does select_files rank candidate files by bm25 score and pool structural expansion");
    assert_eq!(r.code, 0, "stderr: {}", r.stderr);
    let payload = r.stdout_json.expect("expected JSON on stdout");
    let stats = &payload["stats"];
    assert!(stats["top_score"].as_f64().unwrap() > 0.0);
    assert!(stats["matched_query_terms"].as_u64().unwrap() > 0);
    assert!(stats.get("low_confidence").is_none(), "unexpected low_confidence flag in stats: {stats}");
    assert!(!r.stderr.contains("[low-confidence match]"), "unexpected low-confidence stderr note: {}", r.stderr);
}

#[test]
fn gibberish_query_trips_low_confidence() {
    // Nonsense terms plus one real corpus word ("score") -> a nonzero but
    // coincidental match: low match-fraction trips the flag regardless of
    // the absolute raw score.
    let r = run_json("zzzqqqxyzzy flumbargle wibblewonk nizzlepop trundlewax score");
    assert_eq!(r.code, 0, "stderr: {}", r.stderr);
    let payload = r.stdout_json.expect("expected JSON on stdout");
    let stats = &payload["stats"];
    assert_eq!(stats["matched_query_terms"].as_u64().unwrap(), 1);
    assert_eq!(stats["low_confidence"], Value::Bool(true));
    assert!(r.stderr.contains("[low-confidence match]"), "stderr: {}", r.stderr);
}

#[test]
fn zero_match_query_exits_1_with_valid_empty_json() {
    // No term here exists anywhere in roust-rs's own vocabulary.
    let r = run_json("zzzqqqxyzzy flumbargle wibblewonk nizzlepop trundlewax");
    assert_eq!(r.code, 1, "stderr: {}", r.stderr);
    let payload = r.stdout_json.expect("expected valid JSON on stdout even for the zero-match case");
    assert_eq!(payload["files"], serde_json::json!([]));
    assert_eq!(payload["stats"]["matched_query_terms"], serde_json::json!(0));
    assert!(payload["stats"]["total_query_terms"].as_u64().unwrap() > 0);
    assert!(
        r.stderr.contains("no query term matched anything in the indexed corpus vocabulary"),
        "stderr: {}",
        r.stderr
    );
}
