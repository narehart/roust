//! Git-history mining for the semantic retrieval layer -- a faithful port of
//! `lab/history.py`. Single `git log` pass over the checked-out repo's recent
//! non-merge commit history, producing `msgs` (per-file commit message
//! field), `cochange` (per-file co-committed partner counts, plus derived
//! test-bridge edges), and `meta` (per-file commit/author summary, not
//! consumed by any scoring path -- kept for parity with the Python return
//! shape only).
//!
//! ORDERING NOTE: unlike select_files() in core.rs (which has exactly one
//! raw-`set`-iteration nondeterminism -- see PARITY_NOTES.md), history.py's
//! own logic never iterates a raw Python `set` in an order-sensitive way:
//! every dict here is insertion-ordered (deterministic, driven by git log's
//! own -- deterministic -- commit order), and the one spot combinations()
//! runs over a set (`combinations(sorted(set(code_files)), 2)`) is
//! explicitly pre-sorted first. So `IndexMap`, used throughout below to
//! mirror Python dict/Counter insertion order, gives byte-for-byte parity
//! with no caveats.

use crate::core::{is_code_file, TESTLIKE_RE};
use indexmap::IndexMap;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::path::Path;
use std::process::Command;
use std::sync::LazyLock;

const SENTINEL: &str = "__C__";
const MAX_MSG_CHARS: usize = 40_000;
const MAX_MSGS_PER_FILE: usize = 25;
const BULK_COMMIT_FILE_LIMIT: usize = 20;
/// E8: how many commits the association miner (`mine_history_assoc`) walks
/// with `-p`. Deliberately much smaller than `mine_history`'s 5000-commit
/// `--name-only` walk: `-p` output is orders of magnitude larger per commit,
/// and recent fixes carry most of the description->location signal anyway.
pub const HISTORY_ASSOC_COMMITS: usize = 500;
const MAX_ASSOC_TERMS_PER_COMMIT: usize = 64;
const MAX_ASSOC_PAIRS_PER_COMMIT: usize = 50;
const MIN_COCHANGE_COUNT: i64 = 3;
const MAX_COCHANGE_PARTNERS: usize = 10;
const MAX_BRIDGE_CANDIDATES: usize = 50;
const MAX_AUTHORS_PER_FILE: usize = 5;

/// Insertion-ordered multiset, mirroring `collections.Counter`'s dict
/// semantics (first-seen order preserved for ties in `most_common()`).
pub type OrderedCounter = IndexMap<String, i64>;

fn counter_incr(c: &mut OrderedCounter, k: &str, by: i64) {
    *c.entry(k.to_string()).or_insert(0) += by;
}

/// `Counter.most_common()`: stable sort by count descending, ties broken by
/// the counter's insertion order (Rust's `sort_by` is stable, and the
/// intermediate Vec is built by iterating the IndexMap in insertion order,
/// so this matches exactly).
fn most_common(c: &OrderedCounter) -> Vec<(String, i64)> {
    let mut v: Vec<(String, i64)> = c.iter().map(|(k, n)| (k.clone(), *n)).collect();
    v.sort_by(|a, b| b.1.cmp(&a.1));
    v
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct FileMeta {
    pub n_commits: i64,
    pub last_ts: i64,
    pub authors: IndexMap<String, i64>,
}

/// E8 repo-history association table: `term -> file -> enclosing-function
/// name -> count` -- how many mined commits whose message contains `term`
/// touched a hunk whose git hunk-header context names that function in that
/// file. Insertion-ordered at every level (driven by git log's own
/// deterministic commit order), mirroring this module's IndexMap-everywhere
/// determinism discipline. Nested maps (rather than a `(file, func)` tuple
/// key) so the JSON cache serialization stays a plain string-keyed object
/// and query time can do a single per-file lookup.
pub type AssocTable = IndexMap<String, IndexMap<String, IndexMap<String, i64>>>;

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct HistoryData {
    pub msgs: IndexMap<String, String>,
    pub cochange: IndexMap<String, IndexMap<String, i64>>,
    pub meta: IndexMap<String, FileMeta>,
    /// E8 association table (see `AssocTable`). `serde(default)` so a
    /// payload written without the field deserializes to an empty table
    /// rather than failing -- belt-and-braces on top of the CACHE_VERSION
    /// bump that already invalidates pre-E8 caches.
    #[serde(default)]
    pub assoc: AssocTable,
}

fn looks_like_path(ln: &str) -> bool {
    let s = ln.trim();
    if s.is_empty() || s.contains(' ') || s.contains('\t') {
        return false;
    }
    s.contains('/') || (s.contains('.') && !s.starts_with('.'))
}

/// Split a list of lines into blank-line-delimited blocks (blanks dropped,
/// empty leading/trailing blocks dropped).
fn split_blocks<'a>(lines: &[&'a str]) -> Vec<Vec<&'a str>> {
    let mut blocks = Vec::new();
    let mut cur: Vec<&str> = Vec::new();
    for &ln in lines {
        if ln.trim().is_empty() {
            if !cur.is_empty() {
                blocks.push(std::mem::take(&mut cur));
            }
        } else {
            cur.push(ln);
        }
    }
    if !cur.is_empty() {
        blocks.push(cur);
    }
    blocks
}

/// `rest` = every raw line after the header line, up to (excluding) the next
/// commit's sentinel line. Returns (message, files).
fn parse_commit(subject: &str, rest: &[&str]) -> (String, Vec<String>) {
    let blocks = split_blocks(rest);
    if blocks.is_empty() {
        return (subject.to_string(), Vec::new());
    }
    let last = blocks.last().unwrap();
    let (files, body_blocks): (Vec<String>, &[Vec<&str>]) = if last.iter().all(|ln| looks_like_path(ln)) {
        (
            last.iter().map(|ln| ln.trim().to_string()).collect(),
            &blocks[..blocks.len() - 1],
        )
    } else {
        (Vec::new(), &blocks[..])
    };
    let body = body_blocks
        .iter()
        .map(|b| b.join("\n"))
        .collect::<Vec<_>>()
        .join("\n\n");
    let message = if body.is_empty() {
        subject.to_string()
    } else {
        format!("{subject}\n{body}")
    };
    (message, files)
}

/// Derive production<->production "bridge" edges via a shared test-like
/// co-change partner (see history.py's `_bridge_cochange` docstring for the
/// full rationale).
fn bridge_cochange(cochange_counts: &IndexMap<String, OrderedCounter>) -> IndexMap<String, OrderedCounter> {
    let mut bridges: IndexMap<String, OrderedCounter> = IndexMap::new();
    for (t, partners) in cochange_counts {
        if !TESTLIKE_RE.is_match(t) {
            continue;
        }
        let mut qualifying: Vec<(String, i64)> = partners
            .iter()
            .filter(|(f, c)| **c >= MIN_COCHANGE_COUNT && !TESTLIKE_RE.is_match(f))
            .map(|(f, c)| (f.clone(), *c))
            .collect();
        qualifying.sort_by(|a, b| b.1.cmp(&a.1));
        qualifying.truncate(MAX_BRIDGE_CANDIDATES);

        for i in 0..qualifying.len() {
            for j in (i + 1)..qualifying.len() {
                let (a, ca) = &qualifying[i];
                let (b, cb) = &qualifying[j];
                let bridge = ca.min(cb) / 2;
                if bridge < 2 {
                    continue;
                }
                let cur_ab = bridges.entry(a.clone()).or_default().get(b).copied().unwrap_or(0);
                if bridge > cur_ab {
                    bridges.entry(a.clone()).or_default().insert(b.clone(), bridge);
                }
                let cur_ba = bridges.entry(b.clone()).or_default().get(a).copied().unwrap_or(0);
                if bridge > cur_ba {
                    bridges.entry(b.clone()).or_default().insert(a.clone(), bridge);
                }
            }
        }
    }
    bridges
}

/// Mine the last `max_commits` non-merge commits reachable from HEAD.
pub fn mine_history(
    repo_path: &Path,
    max_commits: usize,
    current_files: Option<&HashSet<String>>,
) -> HistoryData {
    if !repo_path.exists() {
        return HistoryData::default();
    }

    let pretty = format!("--pretty=format:{SENTINEL}%at%x00%an%x00%s%n%b");
    let output = Command::new("git")
        .args([
            "log",
            "--no-merges",
            "-n",
            &max_commits.to_string(),
            &pretty,
            "--name-only",
        ])
        .current_dir(repo_path)
        .output();
    let output = match output {
        Ok(o) if o.status.success() => o,
        _ => return HistoryData::default(),
    };
    let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
    if stdout.is_empty() {
        return HistoryData::default();
    }

    let lines: Vec<&str> = crate::pyutil::py_splitlines(&stdout);
    let headers: Vec<usize> = lines
        .iter()
        .enumerate()
        .filter(|(_, ln)| ln.starts_with(SENTINEL))
        .map(|(i, _)| i)
        .collect();

    let mut msgs: IndexMap<String, Vec<String>> = IndexMap::new();
    let mut cochange_counts: IndexMap<String, OrderedCounter> = IndexMap::new();
    let mut n_commits: OrderedCounter = IndexMap::new();
    let mut last_ts: IndexMap<String, i64> = IndexMap::new();
    let mut authors: IndexMap<String, OrderedCounter> = IndexMap::new();

    for (idx, &start) in headers.iter().enumerate() {
        let end = headers.get(idx + 1).copied().unwrap_or(lines.len());
        let header = &lines[start][SENTINEL.len()..];
        let mut parts = header.splitn(3, '\u{0}');
        let ts_str = parts.next().unwrap_or("");
        let author = parts.next().unwrap_or("");
        let subject = parts.next().unwrap_or("");
        let ts: i64 = ts_str.parse().unwrap_or(0);

        let (_msg, mut files) = parse_commit(subject, &lines[start + 1..end]);
        if let Some(fs) = current_files {
            files.retain(|f| fs.contains(f));
        }
        let n_files_total = files.len(); // pre-code-filter count, matches Python's `len(files)`
        let code_files: Vec<String> = files.into_iter().filter(|f| is_code_file(f)).collect();
        if code_files.is_empty() {
            continue;
        }
        for f in &code_files {
            counter_incr(&mut n_commits, f, 1);
            last_ts.entry(f.clone()).or_insert(ts);
            counter_incr(authors.entry(f.clone()).or_default(), author, 1);
            let list = msgs.entry(f.clone()).or_default();
            if list.len() < MAX_MSGS_PER_FILE {
                list.push(_msg.clone());
            }
        }
        if n_files_total <= BULK_COMMIT_FILE_LIMIT {
            let mut uniq: Vec<&String> = code_files.iter().collect::<HashSet<_>>().into_iter().collect();
            uniq.sort();
            if uniq.len() >= 2 {
                for i in 0..uniq.len() {
                    for j in (i + 1)..uniq.len() {
                        let a = uniq[i].clone();
                        let b = uniq[j].clone();
                        counter_incr(cochange_counts.entry(a.clone()).or_default(), &b, 1);
                        counter_incr(cochange_counts.entry(b).or_default(), &a, 1);
                    }
                }
            }
        }
    }

    let mut out_msgs: IndexMap<String, String> = IndexMap::new();
    for (f, parts) in &msgs {
        let text = parts.join("\n");
        let truncated: String = text.chars().take(MAX_MSG_CHARS).collect();
        out_msgs.insert(f.clone(), truncated);
    }

    let mut out_cochange: IndexMap<String, IndexMap<String, i64>> = IndexMap::new();
    for (f, counter) in &cochange_counts {
        let top: Vec<(String, i64)> = most_common(counter)
            .into_iter()
            .filter(|(_, n)| *n >= MIN_COCHANGE_COUNT)
            .take(MAX_COCHANGE_PARTNERS)
            .collect();
        if !top.is_empty() {
            let m: IndexMap<String, i64> = top.into_iter().collect();
            out_cochange.insert(f.clone(), m);
        }
    }

    let bridges = bridge_cochange(&cochange_counts);
    for (f, bcounter) in &bridges {
        let mut top_bridge_v = most_common(bcounter);
        top_bridge_v.truncate(MAX_COCHANGE_PARTNERS);
        if top_bridge_v.is_empty() {
            continue;
        }
        let top_bridge: IndexMap<String, i64> = top_bridge_v.into_iter().collect();
        let mut merged: IndexMap<String, i64> = out_cochange.get(f).cloned().unwrap_or_default();
        for (o, c) in &top_bridge {
            let cur = merged.get(o).copied().unwrap_or(0);
            merged.insert(o.clone(), cur.max(*c));
        }
        let mut merged_v: Vec<(String, i64)> = merged.into_iter().collect();
        merged_v.sort_by(|a, b| b.1.cmp(&a.1));
        merged_v.truncate(MAX_COCHANGE_PARTNERS);
        out_cochange.insert(f.clone(), merged_v.into_iter().collect());
    }

    let mut out_meta: IndexMap<String, FileMeta> = IndexMap::new();
    for (f, &n) in &n_commits {
        let mut auth_v = most_common(authors.get(f).unwrap());
        auth_v.truncate(MAX_AUTHORS_PER_FILE);
        out_meta.insert(
            f.clone(),
            FileMeta {
                n_commits: n,
                last_ts: *last_ts.get(f).unwrap_or(&0),
                authors: auth_v.into_iter().collect(),
            },
        );
    }

    HistoryData {
        msgs: out_msgs,
        cochange: out_cochange,
        meta: out_meta,
        // E8: the association table is mined by a SEPARATE walk
        // (`mine_history_assoc`) and attached by the caller (cache.rs's
        // build_fresh) -- mine_history itself stays a faithful port of
        // lab/history.py and never populates it.
        assoc: AssocTable::new(),
    }
}

// ---------------------------------------------------------------- E8: repo-history association mining
//
// The repo's own past fixes are (description -> location) training pairs:
// a commit message describes a problem in issue-adjacent vocabulary, and
// the commit's hunks say exactly which (file, enclosing function) the fix
// landed in. Mine those pairs at index time; at query time the issue's
// terms vote for the functions their ancestor-fixes touched (see
// core::pack_regions' `history_boost`). Function locations come from git's
// HUNK HEADERS (`@@ -a,b +c,d @@ <context>` -- git puts the enclosing
// def/class context there for free), which is drift-immune: no line-number
// mapping from old commits to the current checkout is ever needed, the
// function NAME is the join key and is resolved against the current
// checkout's own def lines at query time.

/// Matches the defining keyword + identifier inside a hunk-header context
/// string. Covers Python (`def`/`async def`/`class`), Rust (`fn`, `impl`),
/// Go (`func`, incl. `func (r *T) Name` receivers via the optional
/// parenthesized group). The context line git emits is whatever its
/// funcname heuristic picked (typically the nearest preceding
/// column-0-adjacent definition), so for a hunk inside a method this may
/// name the enclosing CLASS rather than the method -- that still joins
/// correctly at query time because `python_blocks` emits whole-class spans
/// too, whose `region_symbol` is the class name.
static HUNK_FUNC_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\b(?:def|class|fn|func|impl)\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)").unwrap());

/// The enclosing-definition name from one `@@ ... @@ <context>` hunk-header
/// line, if the context names one. `None` for no-context hunks (e.g. pure
/// file additions, `@@ -0,0 +1,N @@`) and contexts that aren't definitions.
pub fn parse_hunk_funcname(hunk_line: &str) -> Option<String> {
    let rest = hunk_line.strip_prefix("@@")?;
    let close = rest.find("@@")?;
    let ctx = rest[close + 2..].trim();
    if ctx.is_empty() {
        return None;
    }
    HUNK_FUNC_RE.captures(ctx).map(|c| c[1].to_string())
}

/// Pure parser from `git log --pretty=format:__C__%s%x00%b -p --unified=0`
/// output text to the association table -- separated from the git
/// invocation (`mine_history_assoc`) so fixture log text can be fed
/// directly in tests. Per commit: message terms are the engine tokenizer's
/// output over subject+body, deduped in first-seen order, capped at
/// `MAX_ASSOC_TERMS_PER_COMMIT` (idf FILTERING is deliberately deferred to
/// query time, where the corpus df is available -- generic terms get
/// near-zero idf weight there, so storing them costs table size but never
/// distorts scores); (file, func) pairs are deduped in first-seen order and
/// capped at `MAX_ASSOC_PAIRS_PER_COMMIT`. Commits touching more than
/// `BULK_COMMIT_FILE_LIMIT` files contribute nothing (bulk
/// refactors/vendoring are location noise -- same guard `mine_history`
/// applies to co-change).
pub fn build_assoc_table(log_text: &str, current_files: Option<&HashSet<String>>) -> AssocTable {
    let mut table: AssocTable = IndexMap::new();

    fn flush(table: &mut AssocTable, msg: &str, pairs: &[(String, String)], n_files: usize) {
        if pairs.is_empty() || n_files > BULK_COMMIT_FILE_LIMIT {
            return;
        }
        let mut term_seen: HashSet<String> = HashSet::new();
        let mut terms: Vec<String> = Vec::new();
        for t in crate::core::tokenize(msg) {
            if term_seen.insert(t.clone()) {
                terms.push(t);
                if terms.len() >= MAX_ASSOC_TERMS_PER_COMMIT {
                    break;
                }
            }
        }
        let mut pair_seen: HashSet<(String, String)> = HashSet::new();
        let mut upairs: Vec<&(String, String)> = Vec::new();
        for p in pairs {
            if pair_seen.insert(p.clone()) {
                upairs.push(p);
                if upairs.len() >= MAX_ASSOC_PAIRS_PER_COMMIT {
                    break;
                }
            }
        }
        for t in &terms {
            let by_file = table.entry(t.clone()).or_default();
            for (f, func) in &upairs {
                *by_file.entry(f.clone()).or_default().entry(func.clone()).or_insert(0) += 1;
            }
        }
    }

    let mut msg = String::new();
    let mut in_commit = false;
    let mut in_diff = false;
    let mut current_file: Option<String> = None;
    let mut pairs: Vec<(String, String)> = Vec::new();
    let mut files_touched: HashSet<String> = HashSet::new();

    for ln in crate::pyutil::py_splitlines(log_text) {
        if let Some(rest) = ln.strip_prefix(SENTINEL) {
            flush(&mut table, &msg, &pairs, files_touched.len());
            msg = rest.replace('\u{0}', "\n");
            in_commit = true;
            in_diff = false;
            current_file = None;
            pairs.clear();
            files_touched.clear();
        } else if !in_commit {
            continue;
        } else if ln.starts_with("diff --git ") {
            in_diff = true;
            current_file = None;
        } else if !in_diff {
            // body continuation line (message bodies precede the first
            // `diff --git` of a commit in `-p` output).
            msg.push('\n');
            msg.push_str(ln);
        } else if let Some(path) = ln.strip_prefix("+++ b/") {
            let p = path.trim();
            // bulk-commit detection counts EVERY post-image path (pre-
            // code-filter), matching mine_history's `len(files)` semantics.
            files_touched.insert(p.to_string());
            // `current_files` filter (same semantics as mine_history's):
            // a path that no longer exists in the checkout (deleted, or a
            // pre-rename directory layout -- e.g. this repo's bgrep-rs/ ->
            // roust-rs/ rename) can never match a candidate file at query
            // time, so mining it would only bloat the cached table.
            let keep = is_code_file(p) && current_files.is_none_or(|fs| fs.contains(p));
            current_file = if keep { Some(p.to_string()) } else { None };
        } else if ln.starts_with("+++ ") {
            current_file = None; // `+++ /dev/null` (deletion) or unusual path
        } else if ln.starts_with("@@") {
            if let (Some(f), Some(func)) = (&current_file, parse_hunk_funcname(ln)) {
                pairs.push((f.clone(), func));
            }
        }
    }
    flush(&mut table, &msg, &pairs, files_touched.len());
    table
}

/// Mine the E8 association table from the last `max_commits` non-merge
/// commits reachable from HEAD.
///
/// LEAK SAFETY: this runs plain `git log` (no `--all`, no `--branches`, no
/// `--reflog`) in the repo as checked out, so it walks ONLY ancestors of
/// the current HEAD. The eval harnesses (parity/region_eval2.py,
/// region_eval_verified.py) check out each instance's `base_commit` before
/// invoking the engine, which detaches HEAD at that commit -- mining
/// therefore sees only history strictly before the gold fix; the fix
/// commit itself and anything later are unreachable by construction.
pub fn mine_history_assoc(
    repo_path: &Path,
    max_commits: usize,
    current_files: Option<&HashSet<String>>,
) -> AssocTable {
    if !repo_path.exists() {
        return AssocTable::new();
    }
    let pretty = format!("--pretty=format:{SENTINEL}%s%x00%b");
    let output = Command::new("git")
        .args([
            "log",
            "--no-merges",
            "--no-ext-diff",
            "--no-color",
            "-n",
            &max_commits.to_string(),
            &pretty,
            "-p",
            "--unified=0",
        ])
        .current_dir(repo_path)
        .output();
    match output {
        Ok(o) if o.status.success() => build_assoc_table(&String::from_utf8_lossy(&o.stdout), current_files),
        _ => AssocTable::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn looks_like_path_cases() {
        assert!(looks_like_path("a/b.py"));
        assert!(looks_like_path("foo.py"));
        assert!(!looks_like_path(".hidden"));
        assert!(!looks_like_path("has space"));
        assert!(!looks_like_path(""));
        assert!(!looks_like_path("plainword"));
    }

    #[test]
    fn parse_commit_splits_file_list() {
        let rest = vec!["body line 1", "", "a/b.py", "c/d.py"];
        let (msg, files) = parse_commit("subject", &rest);
        assert_eq!(msg, "subject\nbody line 1");
        assert_eq!(files, vec!["a/b.py", "c/d.py"]);
    }

    #[test]
    fn parse_commit_no_file_list_block() {
        // last block doesn't parse as bare paths -> treated as body
        let rest = vec!["not a path list here"];
        let (msg, files) = parse_commit("subject", &rest);
        assert_eq!(msg, "subject\nnot a path list here");
        assert!(files.is_empty());
    }

    // ------------------------------------------------------------ E8 hunk-header parsing

    #[test]
    fn hunk_funcname_plain_def() {
        assert_eq!(parse_hunk_funcname("@@ -10,7 +10,8 @@ def frobnicate(x, y):"), Some("frobnicate".to_string()));
    }

    #[test]
    fn hunk_funcname_async_def_and_indented_method() {
        assert_eq!(
            parse_hunk_funcname("@@ -3,2 +3,3 @@     async def handle_request(self):"),
            Some("handle_request".to_string())
        );
    }

    #[test]
    fn hunk_funcname_class_context() {
        // git's funcname heuristic often reports the enclosing CLASS for a
        // hunk inside a method -- the class name must be captured (it joins
        // against python_blocks' whole-class span at query time).
        assert_eq!(parse_hunk_funcname("@@ -52,6 +52,7 @@ class RegionPacker(BasePacker):"), Some("RegionPacker".to_string()));
    }

    #[test]
    fn hunk_funcname_rust_and_go() {
        assert_eq!(parse_hunk_funcname("@@ -1,2 +1,2 @@ pub fn pack_regions("), Some("pack_regions".to_string()));
        assert_eq!(parse_hunk_funcname("@@ -1,2 +1,2 @@ func (s *Server) Listen() error {"), Some("Listen".to_string()));
    }

    #[test]
    fn hunk_funcname_no_context() {
        // pure-addition hunks (`@@ -0,0 +1,N @@`) and non-definition
        // contexts must not fabricate a function name.
        assert_eq!(parse_hunk_funcname("@@ -0,0 +1,42 @@"), None);
        assert_eq!(parse_hunk_funcname("@@ -7,3 +7,4 @@ x = compute(1, 2)"), None);
        assert_eq!(parse_hunk_funcname("not a hunk line"), None);
    }

    // ------------------------------------------------------------ E8 association-table build

    /// Two commits in fixture `git log -p -U0` format. Commit 1 ("fix
    /// canonical summation determinism") touches pack.py::weight and
    /// pack.py::PackerClass; commit 2 ("summation overflow") touches
    /// pack.py::weight again and util.py::helper. Hand-computed table:
    /// every commit-1 term maps {pack.py: {weight: 1, PackerClass: 1}};
    /// the shared term ("summat") accumulates weight -> 2 plus commit 2's
    /// {util.py: {helper: 1}}.
    #[test]
    fn build_assoc_table_hand_computed() {
        let log = "\
__C__fix canonical summation determinism\u{0}
diff --git a/pack.py b/pack.py
--- a/pack.py
+++ b/pack.py
@@ -12,1 +12,1 @@ def weight(terms):
-    old
+    new
@@ -40,1 +40,1 @@ class PackerClass:
-    old2
+    new2
__C__summation overflow guard\u{0}
diff --git a/pack.py b/pack.py
--- a/pack.py
+++ b/pack.py
@@ -12,1 +12,1 @@ def weight(terms):
-    a
+    b
diff --git a/util.py b/util.py
--- a/util.py
+++ b/util.py
@@ -3,1 +3,1 @@ def helper(x):
-    c
+    d
";
        let table = build_assoc_table(log, None);

        // Term keys are exactly the engine tokenizer's output over each
        // message (deduped) -- derive them with the same tokenizer rather
        // than hardcoding stems, then assert the hand-computed structure.
        let t1: Vec<String> = crate::core::tokenize("fix canonical summation determinism");
        let t2: Vec<String> = crate::core::tokenize("summation overflow guard");
        assert!(!t1.is_empty() && !t2.is_empty());
        let shared: Vec<&String> = t1.iter().filter(|t| t2.contains(t)).collect();
        assert_eq!(shared.len(), 1, "fixture expects exactly one shared term (summation)");
        let shared = shared[0];

        for t in &t1 {
            let by_file = table.get(t).unwrap_or_else(|| panic!("term {t:?} missing"));
            let pack = &by_file["pack.py"];
            let expected_weight = if t == shared { 2 } else { 1 };
            assert_eq!(pack["weight"], expected_weight, "term {t:?}");
            assert_eq!(pack["PackerClass"], 1, "term {t:?}");
        }
        for t in &t2 {
            let by_file = table.get(t).unwrap_or_else(|| panic!("term {t:?} missing"));
            assert_eq!(by_file["util.py"]["helper"], 1, "term {t:?}");
            assert_eq!(by_file["pack.py"]["weight"], if t == shared { 2 } else { 1 }, "term {t:?}");
            if t != shared {
                assert!(!by_file["pack.py"].contains_key("PackerClass"), "term {t:?} must not reach commit 1's pairs");
            }
        }
        // no term maps a file it never co-occurred with
        for t in &t1 {
            if t != shared {
                assert!(!table[t].contains_key("util.py"), "term {t:?}");
            }
        }
    }

    #[test]
    fn build_assoc_table_skips_deletions_and_non_code() {
        let log = "\
__C__remove dead code and notes\u{0}
diff --git a/dead.py b/dead.py
--- a/dead.py
+++ /dev/null
@@ -1,10 +0,0 @@ def gone(x):
-    body
diff --git a/notes.md b/notes.md
--- a/notes.md
+++ b/notes.md
@@ -1,1 +1,1 @@ def looks_like_code():
-    a
+    b
";
        let table = build_assoc_table(log, None);
        assert!(table.is_empty(), "deleted files and non-code files must contribute no associations");
    }

    #[test]
    fn build_assoc_table_no_context_hunks_only() {
        let log = "\
__C__add brand new module\u{0}
diff --git a/newmod.py b/newmod.py
--- /dev/null
+++ b/newmod.py
@@ -0,0 +1,3 @@
+def fresh():
+    pass
";
        let table = build_assoc_table(log, None);
        assert!(table.is_empty(), "no-context hunks carry no enclosing-function evidence");
    }
}
