//! E8 repo-history association mining: end-to-end test against a REAL
//! constructed git repo (known commits touching known functions with known
//! message terms), asserting the mined table matches the hand-computed
//! expectation. Complements the pure-parser fixture tests in
//! `src/history.rs` (which feed canned `git log -p` text) by exercising
//! the actual `git log` invocation, hunk-header funcname generation
//! included.

use roust::core::tokenize;
use roust::history::{mine_history_assoc, HISTORY_ASSOC_COMMITS};
use std::path::{Path, PathBuf};
use std::process::Command;

fn git(repo: &Path, args: &[&str]) {
    let status = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(["-c", "user.email=e8@test.invalid", "-c", "user.name=e8", "-c", "commit.gpgsign=false"])
        .args(args)
        .status()
        .expect("failed to run git");
    assert!(status.success(), "git {args:?} failed in {repo:?}");
}

const PACK_V1: &str = concat!(
    "def alpha_sum(values):\n",
    "    total = 0\n",
    "    for v in values:\n",
    "        total += v\n",
    "    return total\n",
    "\n",
    "\n",
    "def beta_norm(values):\n",
    "    m = 1\n",
    "    result = [v / m for v in values]\n",
    "    return result\n",
);

// commit 2: one line changed INSIDE alpha_sum's body (git's funcname
// heuristic reports the nearest preceding column-0 definition line, i.e.
// `def alpha_sum(values):`, as the hunk context).
const PACK_V2: &str = concat!(
    "def alpha_sum(values):\n",
    "    total = 0\n",
    "    for v in values:\n",
    "        total = total + v\n",
    "    return total\n",
    "\n",
    "\n",
    "def beta_norm(values):\n",
    "    m = 1\n",
    "    result = [v / m for v in values]\n",
    "    return result\n",
);

// commit 3: one line changed INSIDE beta_norm's body.
const PACK_V3: &str = concat!(
    "def alpha_sum(values):\n",
    "    total = 0\n",
    "    for v in values:\n",
    "        total = total + v\n",
    "    return total\n",
    "\n",
    "\n",
    "def beta_norm(values):\n",
    "    m = 2\n",
    "    result = [v / m for v in values]\n",
    "    return result\n",
);

// conventional-commit format: the developer's environment may enforce a
// commit-msg hook globally (core.hooksPath), and fixture commits must pass
// it rather than bypass it -- same precedent as incremental.rs's
// "test: initial commit".
const MSG_ALPHA: &str = "fix: canonical summation determinism";
const MSG_BETA: &str = "perf: normalize weighting overflow guard";

fn make_fixture_repo(tag: &str) -> PathBuf {
    let repo = std::env::temp_dir().join(format!("roust_e8_assoc_{tag}_{}", std::process::id()));
    std::fs::remove_dir_all(&repo).ok();
    std::fs::create_dir_all(&repo).unwrap();
    git(&repo, &["init", "-q"]);
    std::fs::write(repo.join("pack.py"), PACK_V1).unwrap();
    git(&repo, &["add", "-A"]);
    git(&repo, &["commit", "-q", "-m", "chore: initial layout scaffolding"]);
    std::fs::write(repo.join("pack.py"), PACK_V2).unwrap();
    git(&repo, &["commit", "-q", "-am", MSG_ALPHA]);
    std::fs::write(repo.join("pack.py"), PACK_V3).unwrap();
    git(&repo, &["commit", "-q", "-am", MSG_BETA]);
    repo
}

/// Hand-computed expectation: every term of MSG_ALPHA associates
/// (pack.py, alpha_sum) with count 1 and nothing else; every term of
/// MSG_BETA associates (pack.py, beta_norm) with count 1 and nothing else;
/// the initial pure-addition commit contributes nothing (its hunks have no
/// enclosing-function context).
#[test]
fn mined_table_matches_hand_computed_fixture() {
    let repo = make_fixture_repo("hand");
    let table = mine_history_assoc(&repo, HISTORY_ASSOC_COMMITS, None);

    let alpha_terms = tokenize(MSG_ALPHA);
    let beta_terms = tokenize(MSG_BETA);
    assert!(!alpha_terms.is_empty() && !beta_terms.is_empty());
    assert!(
        !alpha_terms.iter().any(|t| beta_terms.contains(t)),
        "fixture messages must share no terms for the disjointness assertions below"
    );

    for t in &alpha_terms {
        let by_file = table.get(t).unwrap_or_else(|| panic!("alpha term {t:?} missing from table"));
        assert_eq!(by_file.len(), 1, "term {t:?} must associate exactly one file");
        let funcs = &by_file["pack.py"];
        assert_eq!(funcs.len(), 1, "term {t:?} must associate exactly one function");
        assert_eq!(funcs["alpha_sum"], 1, "term {t:?}");
    }
    for t in &beta_terms {
        let by_file = table.get(t).unwrap_or_else(|| panic!("beta term {t:?} missing from table"));
        assert_eq!(by_file.len(), 1, "term {t:?} must associate exactly one file");
        let funcs = &by_file["pack.py"];
        assert_eq!(funcs.len(), 1, "term {t:?} must associate exactly one function");
        assert_eq!(funcs["beta_norm"], 1, "term {t:?}");
    }
    // the initial commit's terms ("chore: initial layout scaffolding") appear in
    // no association: its hunk (`@@ -0,0 +1,N @@`) has no enclosing context.
    for t in tokenize("chore: initial layout scaffolding") {
        assert!(!table.contains_key(&t), "pure-addition commit term {t:?} must contribute nothing");
    }

    std::fs::remove_dir_all(&repo).ok();
}

/// Mining is a deterministic function of the repo's history: repeated runs
/// produce the identical (insertion-order-sensitive) table.
#[test]
fn mining_is_deterministic_across_runs() {
    let repo = make_fixture_repo("det");
    let first = mine_history_assoc(&repo, HISTORY_ASSOC_COMMITS, None);
    assert!(!first.is_empty());
    for _ in 0..9 {
        let again = mine_history_assoc(&repo, HISTORY_ASSOC_COMMITS, None);
        assert_eq!(first, again, "mine_history_assoc must be deterministic");
    }
    std::fs::remove_dir_all(&repo).ok();
}

/// LEAK SAFETY: mining from a detached HEAD at an ancestor commit sees only
/// that commit's ancestors -- a later ("future fix") commit on the branch
/// must contribute nothing, mirroring how the eval harness checks out an
/// instance's base_commit before invoking the engine.
#[test]
fn mining_at_detached_ancestor_sees_no_future_commits() {
    let repo = make_fixture_repo("leak");
    // detach at HEAD~1: MSG_BETA's commit is now in the future.
    git(&repo, &["checkout", "-q", "--detach", "HEAD~1"]);
    let table = mine_history_assoc(&repo, HISTORY_ASSOC_COMMITS, None);
    for t in tokenize(MSG_ALPHA) {
        assert!(table.contains_key(&t), "ancestor commit term {t:?} must still be mined");
    }
    for t in tokenize(MSG_BETA) {
        assert!(!table.contains_key(&t), "future commit term {t:?} must be invisible at base_commit");
    }
    std::fs::remove_dir_all(&repo).ok();
}
