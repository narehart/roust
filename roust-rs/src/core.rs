//! roust retrieval core -- a Rust port of `lab/lanes2.py` (frozen v7
//! pipeline). Must stay retrieval-logic-identical to lanes2.py; see
//! PARITY_NOTES.md for every place Python runtime semantics (dict/set
//! ordering, `Path` comparison, `str.splitlines()`, hash randomization)
//! required a deliberate, documented translation choice rather than a
//! literal one.

use crate::pyutil::{normpath_join, path_join_simple, path_sort_key, py_lower, py_parent, py_parent_name, py_splitlines};
use indexmap::IndexMap;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::LazyLock;

pub const CODE_EXTENSIONS: &[&str] = &[
    ".py", ".ts", ".js", ".go", ".rs", ".java", ".kt", ".cs", ".swift", ".tsx", ".jsx",
];
pub const MAX_FILE_BYTES: u64 = 2_000_000;

pub fn is_code_file(rel: &str) -> bool {
    CODE_EXTENSIONS.iter().any(|ext| rel.ends_with(ext))
}

fn has_code_suffix(rel: &str) -> bool {
    // Matches Python's `p.suffix in CODE_EXTENSIONS` (last dotted component
    // only, NOT `endswith`) used by the Corpus file walk. Delegates to
    // `suffix_of` -- the SAME predicate `cache.rs`'s manifest scan uses --
    // so the corpus walk and the cache's change detection can never
    // disagree about which files are code. (The previous hand-rolled
    // version also searched the last '.' across the WHOLE rel path and
    // accepted extension-only hidden names like `a/.py`, which Python's
    // `Path.suffix` -- and `suffix_of` -- correctly reject.)
    CODE_EXTENSIONS.contains(&suffix_of(rel))
}

pub(crate) fn suffix_of(rel: &str) -> &str {
    // Python `Path(rel).suffix`: the last dotted component of the *final
    // path component* (a leading-dot-only filename like ".gitignore" has no
    // suffix). Good enough here since it's only ever applied to plain
    // filenames without directory separators mixed in oddly.
    let name = match rel.rfind('/') {
        Some(idx) => &rel[idx + 1..],
        None => rel,
    };
    match name.rfind('.') {
        Some(idx) if idx > 0 => &name[idx..],
        _ => "",
    }
}

// ---------------------------------------------------------------- tokenization

static IDENT_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[A-Za-z_][A-Za-z0-9_]*").unwrap());

static STOP: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    [
        "the", "and", "for", "with", "that", "this", "from", "import", "return", "self", "def",
        "class", "not", "none", "true", "false", "let", "const", "var", "function", "func",
        "type", "struct", "impl", "use", "pub", "new", "int", "str", "string", "bool", "void",
        "null", "nil", "err", "error",
    ]
    .into_iter()
    .collect()
});

/// Conservative Porter-style suffix stripping. Length gates count Unicode
/// characters (Python `len(t)`), not bytes; all matched suffixes are ASCII
/// so byte-slicing off the matched suffix is safe once the char-count gate
/// passes. See lanes2.py's `stem()` docstring for the design rationale.
pub fn stem(t: &str) -> String {
    let clen = t.chars().count();
    let mut t = t.to_string();
    let mut clen = clen;

    if t.ends_with("ies") && clen > 4 {
        t = format!("{}i", &t[..t.len() - 3]);
        clen = clen - 3 + 1;
    } else if t.ends_with("sses") {
        t = t[..t.len() - 2].to_string();
        clen -= 2;
    } else if t.ends_with('s') && !t.ends_with("ss") && clen > 3 {
        t = t[..t.len() - 1].to_string();
        clen -= 1;
    }

    if t.ends_with("ing") && clen > 5 {
        t = t[..t.len() - 3].to_string();
        clen -= 3;
    } else if t.ends_with("ed") && clen > 4 {
        t = t[..t.len() - 2].to_string();
        clen -= 2;
    }

    if t.ends_with("er") && clen > 5 {
        t = t[..t.len() - 2].to_string();
        clen -= 2;
    } else if t.ends_with("or") && clen > 6 {
        t = t[..t.len() - 2].to_string();
        clen -= 2;
    }

    if t.ends_with('y') && clen > 4 {
        t = format!("{}i", &t[..t.len() - 1]);
    } else if t.ends_with('e') && clen > 4 {
        t = t[..t.len() - 1].to_string();
    }

    t
}

/// Hand-rolled equivalent of `_CAMEL_RE = r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+"`
/// (regex lookahead isn't supported by the `regex` crate). Operates on
/// Unicode scalar values but only ever recognizes ASCII upper/lower/digit
/// characters, exactly like the explicit `[A-Z]`/`[a-z]`/`[0-9]` classes in
/// the original -- any other character is simply skipped (matches
/// `re.finditer` never producing a match there).
fn camel_matches(chunk: &str) -> Vec<String> {
    let chars: Vec<char> = chunk.chars().collect();
    let n = chars.len();
    let mut out = Vec::new();
    let mut i = 0;
    while i < n {
        let c = chars[i];
        if c.is_ascii_uppercase() {
            let mut run_end = i + 1;
            while run_end < n && chars[run_end].is_ascii_uppercase() {
                run_end += 1;
            }
            let run_len = run_end - i;

            let mut matched_len: Option<usize> = None;
            if run_len >= 2 {
                let mut k = run_len - 1;
                loop {
                    let look_pos = i + k + 1;
                    if look_pos < n && chars[look_pos].is_ascii_lowercase() {
                        matched_len = Some(k);
                        break;
                    }
                    if k == 1 {
                        break;
                    }
                    k -= 1;
                }
            }
            if let Some(k) = matched_len {
                out.push(chars[i..i + k].iter().collect());
                i += k;
                continue;
            }
            if i + 1 < n && chars[i + 1].is_ascii_lowercase() {
                let mut end = i + 1;
                while end < n && chars[end].is_ascii_lowercase() {
                    end += 1;
                }
                out.push(chars[i..end].iter().collect());
                i = end;
                continue;
            }
            out.push(chars[i..run_end].iter().collect());
            i = run_end;
        } else if c.is_ascii_lowercase() {
            let mut end = i + 1;
            while end < n && chars[end].is_ascii_lowercase() {
                end += 1;
            }
            out.push(chars[i..end].iter().collect());
            i = end;
        } else if c.is_ascii_digit() {
            let mut end = i + 1;
            while end < n && chars[end].is_ascii_digit() {
                end += 1;
            }
            out.push(chars[i..end].iter().collect());
            i = end;
        } else {
            i += 1;
        }
    }
    out
}

/// Split an identifier into lowercase subtokens (snake_case + camelCase).
pub fn subtokens(word: &str) -> Vec<String> {
    let mut parts: Vec<String> = Vec::new();
    for chunk in word.split('_') {
        if chunk.is_empty() {
            continue;
        }
        for m in camel_matches(chunk) {
            parts.push(py_lower(&m));
        }
    }
    parts
        .into_iter()
        .filter(|p| p.chars().count() > 2 && !STOP.contains(p.as_str()))
        .map(|p| stem(&p))
        .collect()
}

pub fn tokenize(text: &str) -> Vec<String> {
    let mut out = Vec::new();
    for m in IDENT_RE.find_iter(text) {
        let w = m.as_str();
        let low = py_lower(w);
        if low.chars().count() > 2 && !STOP.contains(low.as_str()) {
            out.push(stem(&low));
        }
        let subs = subtokens(w);
        if subs.len() > 1 || (!subs.is_empty() && subs[0] != stem(&low)) {
            out.extend(subs);
        }
    }
    out
}

/// Query = question tokens + task keywords, subtoken-expanded, deduped.
pub fn query_terms(question: &str, keywords: &[String]) -> Vec<String> {
    let mut seen: HashSet<String> = HashSet::new();
    let mut terms: Vec<String> = Vec::new();
    let mut candidates: Vec<String> = tokenize(question);
    for k in keywords {
        let lowk = py_lower(k);
        candidates.push(stem(&lowk));
        candidates.extend(subtokens(k));
    }
    for t in candidates {
        if !seen.contains(&t) && t.chars().count() > 2 && !STOP.contains(t.as_str()) {
            seen.insert(t.clone());
            terms.push(t);
        }
    }
    terms
}

/// How many of `terms` exist ANYWHERE in `corpus`'s vocabulary (body,
/// comment/NL, docs-page, commit-message, or path-token fields) -- i.e. the
/// full set of fields `Corpus::bm25`/`docs_bm25`/`msg_bm25` ever look a term
/// up in, not just the primary body `df`. Returns `(matched, total)`, `total`
/// always equal to `terms.len()`. Purely diagnostic (feeds `--json`'s
/// `matched_query_terms`/`total_query_terms` stats and the zero-match exit-1
/// gate in `main.rs`) -- never consulted by `select_files`, so it cannot
/// itself change ranking.
pub fn query_term_coverage(corpus: &Corpus, terms: &[String]) -> (usize, usize) {
    let mut path_vocab: HashSet<&str> = HashSet::new();
    for toks in corpus.ptoks.values() {
        for t in toks {
            path_vocab.insert(t.as_str());
        }
    }
    let matched = terms
        .iter()
        .filter(|t| {
            corpus.df.contains_key(t.as_str())
                || corpus.com_df.contains_key(t.as_str())
                || corpus.docs_df.contains_key(t.as_str())
                || corpus.msg_df.contains_key(t.as_str())
                || path_vocab.contains(t.as_str())
        })
        .count();
    (matched, terms.len())
}

// ---------------------------------------------------------------- E11 query routing

// Traceback channel (BLIZZARD BR_ST / BRTracer, campaign #4 E11): the block
// classifier is line-based and purely regex-driven -- no heuristics that
// depend on surrounding markdown. Python tracebacks only (the SWE-bench
// corpus is Python; other languages fall through to prose, today's
// treatment).
static TB_HEADER_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^\s*Traceback \(most recent call last\):\s*$").unwrap());
static TB_CHAIN_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"^\s*(?:During handling of the above exception, another exception occurred:|The above exception was the direct cause of the following exception:)\s*$",
    )
    .unwrap()
});
static TB_FRAME_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r#"^\s*File "([^"]+)", line \d+(?:, in (\S.*))?\s*$"#).unwrap());
// Exception line: `Name: message`, `pkg.mod.Name: message`, or a bare
// exception name. Anchored on the conventional exception-class suffixes plus
// the stdlib's suffix-less builtins, so ordinary prose ("Note: ..." etc.)
// never matches.
static TB_EXC_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"^\s*(?:[A-Za-z_][\w.]*\.)?([A-Za-z_]\w*(?:Error|Exception|Warning)|KeyboardInterrupt|SystemExit|StopIteration|StopAsyncIteration|GeneratorExit)\b:?\s*(.*)$",
    )
    .unwrap()
});

// Code-fence channel (Chaparro part-selection / BLIZZARD BR_PE): markdown
// fences, doctest/REPL lines, and 4-space/tab-indented code runs.
static FENCE_DELIM_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^\s*(?:```|~~~)").unwrap());
static REPL_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^\s*>>>").unwrap());
static REPL_CONT_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^\s*\.\.\.(?:\s|$)").unwrap());
static INDENT_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^(?:\t| {4,})").unwrap());
// First line of an indented run must look like code, not an indented quote /
// list continuation, before the run is claimed for the fence channel.
static INDENT_CODE_START_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r#"^\s*(?:from\s+\S+\s+import\s|import\s+\w|(?:async\s+)?def\s+\w|class\s+\w|@\w|[A-Za-z_][\w.\[\]'"]*\s*=[^=]|[A-Za-z_][\w.]*\(|with\s+\w|for\s+\w|if\s+\w|try\s*:|while\s+\w|return\s|raise\s|print\()"#,
    )
    .unwrap()
});

// Identifier mining inside structured blocks (mine-then-discard): only
// tokens in code-identifier POSITIONS survive -- def/class/import names,
// call targets, attribute accesses, assignment LHS. Bulk fence text
// (comments, string literals, output values, plain words) is dropped.
static MINE_DEF_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?:^|\s)(?:async\s+def|def|class)\s+([A-Za-z_]\w*)").unwrap());
static MINE_IMPORT_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?:^|\s)(?:from|import)\s+([A-Za-z_][\w.]*)").unwrap());
static MINE_CALL_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"([A-Za-z_]\w*)\s*\(").unwrap());
static MINE_ATTR_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\.([A-Za-z_]\w*)").unwrap());
static MINE_ASSIGN_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?:^|[\s,(])([A-Za-z_]\w*)\s*=[^=]").unwrap());

/// Python keywords + ubiquitous builtins excluded from mined identifiers
/// (raw, pre-tokenize names -- distinct from the stemmed STOP set, which
/// still applies downstream via `tokenize`).
static ROUTE_KW: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    [
        "and", "or", "not", "if", "else", "elif", "for", "while", "def", "class", "return",
        "import", "from", "with", "as", "try", "except", "finally", "raise", "lambda", "pass",
        "break", "continue", "global", "nonlocal", "assert", "yield", "del", "in", "is", "None",
        "True", "False", "self", "cls", "print", "len", "range", "isinstance", "super", "object",
        "async", "await",
    ]
    .into_iter()
    .collect()
});

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Chan {
    Prose,
    Trace,
    Fence,
}

/// E11 routed query: per-class query treatment plus the trace-frame file
/// channel. Produced only under `--route`; the default pipeline never calls
/// this.
#[derive(Debug, Default)]
pub struct RoutedQuery {
    /// Deduped query terms, assembled prose-first, then trace-mined, then
    /// fence-mined (provenance = first channel that contributed the term).
    pub terms: Vec<String>,
    /// Repo-relative files resolved from traceback frames, deduped, best
    /// rank first (rank 1 = the raise site, i.e. Python's LAST frame --
    /// BRTracer's top-of-stack semantics transposed to Python frame order).
    pub trace_files: Vec<String>,
    pub trace_bearing: bool,
    pub fence_bearing: bool,
    /// Kim & Lee conditional: fence-mined terms are a strict majority of the
    /// deduped query-term list. Gates the test-path penalty in
    /// `select_files`; never true for prose-only or trace-dominated queries.
    pub fence_dominant: bool,
    pub n_prose_terms: usize,
    pub n_trace_terms: usize,
    pub n_fence_terms: usize,
}

impl RoutedQuery {
    pub fn class(&self) -> &'static str {
        match (self.trace_bearing, self.fence_bearing) {
            (true, true) => "trace+fence",
            (true, false) => "trace",
            (false, true) => "fence",
            (false, false) => "prose",
        }
    }
}

/// Line-channel partition: traceback blocks claimed first (precedence per
/// block type -- a traceback inside a fence is treated as trace), then
/// fenced blocks / REPL lines / indented code runs.
fn partition_channels(lines: &[&str]) -> Vec<Chan> {
    let n = lines.len();
    let mut chan = vec![Chan::Prose; n];

    // Pass 1: traceback blocks.
    let mut i = 0;
    while i < n {
        if !(TB_HEADER_RE.is_match(&lines[i]) || TB_FRAME_RE.is_match(&lines[i])) {
            i += 1;
            continue;
        }
        chan[i] = Chan::Trace;
        let mut context_left = if TB_FRAME_RE.is_match(&lines[i]) { 2usize } else { 0 };
        let mut j = i + 1;
        while j < n {
            let lj = &lines[j];
            if TB_FRAME_RE.is_match(lj) {
                chan[j] = Chan::Trace;
                context_left = 2;
                j += 1;
                continue;
            }
            if TB_HEADER_RE.is_match(lj) || TB_CHAIN_RE.is_match(lj) {
                chan[j] = Chan::Trace;
                context_left = 0;
                j += 1;
                continue;
            }
            if lj.trim().is_empty() {
                // Blank lines separate chained tracebacks; consume them only
                // when the next non-blank line continues the trace.
                let mut k = j;
                while k < n && lines[k].trim().is_empty() {
                    k += 1;
                }
                if k < n && (TB_HEADER_RE.is_match(&lines[k]) || TB_CHAIN_RE.is_match(&lines[k])) {
                    for m in j..k {
                        chan[m] = Chan::Trace;
                    }
                    context_left = 0;
                    j = k;
                    continue;
                }
                break;
            }
            if TB_EXC_RE.is_match(lj) && !lj.starts_with(' ') && !lj.starts_with('\t') {
                // Exception line at the block's own indentation ends it.
                chan[j] = Chan::Trace;
                j += 1;
                break;
            }
            if context_left > 0 && (lj.starts_with(' ') || lj.starts_with('\t')) {
                // Source-context line under a frame (plus a possible py3.11+
                // `~~~^^^` marker line); bounded so a partial frame paste
                // can't swallow a following code block.
                chan[j] = Chan::Trace;
                context_left -= 1;
                j += 1;
                continue;
            }
            break;
        }
        i = j;
    }

    // Pass 2: fenced blocks (toggle), REPL lines, indented code runs.
    let mut in_fence = false;
    let mut prev_repl = false;
    let mut i = 0;
    while i < n {
        if chan[i] == Chan::Trace {
            // A trace block inside a fence: the fence stays open across it.
            prev_repl = false;
            i += 1;
            continue;
        }
        let l = &lines[i];
        if FENCE_DELIM_RE.is_match(l) {
            chan[i] = Chan::Fence;
            in_fence = !in_fence;
            prev_repl = false;
            i += 1;
            continue;
        }
        if in_fence {
            chan[i] = Chan::Fence;
            i += 1;
            continue;
        }
        if REPL_RE.is_match(l) || (prev_repl && REPL_CONT_RE.is_match(l)) {
            chan[i] = Chan::Fence;
            prev_repl = true;
            i += 1;
            continue;
        }
        prev_repl = false;
        if INDENT_RE.is_match(l) && INDENT_CODE_START_RE.is_match(l.trim_start()) {
            // Indented code run: claim while lines stay indented (interior
            // blank lines allowed when followed by another indented line).
            chan[i] = Chan::Fence;
            let mut j = i + 1;
            while j < n && chan[j] != Chan::Trace {
                if INDENT_RE.is_match(&lines[j]) {
                    chan[j] = Chan::Fence;
                    j += 1;
                } else if lines[j].trim().is_empty()
                    && j + 1 < n
                    && chan[j + 1] != Chan::Trace
                    && INDENT_RE.is_match(&lines[j + 1])
                {
                    chan[j] = Chan::Fence;
                    j += 1;
                } else {
                    break;
                }
            }
            i = j;
            continue;
        }
        i += 1;
    }

    chan
}

/// Mine code identifiers from structured-block text, in document order,
/// deduped, keyword-filtered. The bulk text is then DISCARDED as query
/// material (Chaparro/BLIZZARD mine-then-discard).
fn mine_code_identifiers(text: &str) -> Vec<String> {
    let mut seen: HashSet<String> = HashSet::new();
    let mut out: Vec<String> = Vec::new();
    let push = |name: &str, seen: &mut HashSet<String>, out: &mut Vec<String>| {
        if name.is_empty() || ROUTE_KW.contains(name) {
            return;
        }
        if seen.insert(name.to_string()) {
            out.push(name.to_string());
        }
    };
    for line in py_splitlines(text) {
        for cap in MINE_DEF_RE.captures_iter(&line) {
            push(cap.get(1).unwrap().as_str(), &mut seen, &mut out);
        }
        for cap in MINE_IMPORT_RE.captures_iter(&line) {
            push(cap.get(1).unwrap().as_str(), &mut seen, &mut out);
        }
        for cap in MINE_CALL_RE.captures_iter(&line) {
            push(cap.get(1).unwrap().as_str(), &mut seen, &mut out);
        }
        for cap in MINE_ATTR_RE.captures_iter(&line) {
            push(cap.get(1).unwrap().as_str(), &mut seen, &mut out);
        }
        for cap in MINE_ASSIGN_RE.captures_iter(&line) {
            push(cap.get(1).unwrap().as_str(), &mut seen, &mut out);
        }
    }
    out
}

/// Resolve a traceback frame path to a repo-relative corpus file by longest
/// trailing-path-component match (>= 2 shared components, or an exact
/// relative-path match). Ties broken by longest rel, then lexicographically
/// smallest. Returns None for paths outside the repo (user repro scripts,
/// stdlib frames).
fn resolve_frame_path(frame_path: &str, corpus: &Corpus) -> Option<String> {
    let norm = frame_path.replace('\\', "/");
    let fparts: Vec<&str> = norm.split('/').filter(|p| !p.is_empty()).collect();
    if fparts.is_empty() {
        return None;
    }
    let mut best: Option<(usize, &String)> = None; // (shared components, rel)
    for rel in &corpus.files {
        let rparts: Vec<&str> = rel.split('/').collect();
        let mut shared = 0usize;
        while shared < rparts.len()
            && shared < fparts.len()
            && rparts[rparts.len() - 1 - shared] == fparts[fparts.len() - 1 - shared]
        {
            shared += 1;
        }
        let full_rel_match = shared == rparts.len();
        if !(full_rel_match || shared >= 2) {
            continue;
        }
        let better = match best {
            None => true,
            Some((bs, brel)) => {
                shared > bs
                    || (shared == bs
                        && (rel.len() > brel.len() || (rel.len() == brel.len() && rel < brel)))
            }
        };
        if better {
            best = Some((shared, rel));
        }
    }
    best.map(|(_, rel)| rel.clone())
}

/// E11 (campaign #4): deterministic structure-aware query routing.
/// Partitions the issue text into {traceback, code-fence, prose} channels,
/// applies per-class treatment (trace: extract frame identifiers +
/// exception + message, resolve frame files for the FILE boost, discard the
/// block as bulk text; fence: mine identifiers, discard the body; prose:
/// byte-identical to `query_terms`). A query with neither structured
/// channel returns EXACTLY `query_terms(question, &[])`.
pub fn route_query(question: &str, corpus: &Corpus) -> RoutedQuery {
    let lines = py_splitlines(question);
    let chan = partition_channels(&lines);
    let trace_bearing = chan.iter().any(|c| *c == Chan::Trace);
    let fence_bearing = chan.iter().any(|c| *c == Chan::Fence);

    if !trace_bearing && !fence_bearing {
        let terms = query_terms(question, &[]);
        let n = terms.len();
        return RoutedQuery {
            terms,
            n_prose_terms: n,
            ..Default::default()
        };
    }

    // Channel texts.
    let mut prose_lines: Vec<&str> = Vec::new();
    let mut trace_lines: Vec<&str> = Vec::new();
    let mut fence_lines: Vec<&str> = Vec::new();
    for (i, l) in lines.iter().enumerate() {
        match chan[i] {
            Chan::Prose => prose_lines.push(*l),
            Chan::Trace => trace_lines.push(*l),
            Chan::Fence => fence_lines.push(*l),
        }
    }
    let prose_text = prose_lines.join("\n");
    let fence_text = fence_lines.join("\n");

    // Trace treatment: frames in document order; extracted query material =
    // frame function names + frame module basenames + exception names +
    // error messages. The raw trace body is otherwise dropped.
    let mut frame_paths: Vec<String> = Vec::new();
    let mut trace_material: Vec<String> = Vec::new();
    for l in &trace_lines {
        if let Some(cap) = TB_FRAME_RE.captures(l) {
            let path = cap.get(1).unwrap().as_str().to_string();
            // Module-basename terms only for frames that resolve INTO the
            // repo -- unresolved frames (user repro scripts, stdlib) would
            // contribute junk tokens ("repro", "tmp", ...).
            if resolve_frame_path(&path, corpus).is_some() {
                if let Some(base) = path.replace('\\', "/").rsplit('/').next() {
                    let stem_name = base.strip_suffix(".py").unwrap_or(base);
                    trace_material.push(stem_name.to_string());
                }
            }
            if let Some(func) = cap.get(2) {
                let f = func.as_str().trim();
                if f != "<module>" {
                    trace_material.push(f.to_string());
                }
            }
            frame_paths.push(path);
        } else if let Some(cap) = TB_EXC_RE.captures(l) {
            trace_material.push(cap.get(1).unwrap().as_str().to_string());
            let msg = cap.get(2).map(|m| m.as_str()).unwrap_or("");
            if !msg.is_empty() {
                trace_material.push(msg.to_string());
            }
        }
    }
    let trace_text = trace_material.join(" ");

    // Frame-file resolution, raise-site-first (reversed document order),
    // deduped keeping best (earliest post-reversal) rank.
    let mut trace_files: Vec<String> = Vec::new();
    let mut seen_files: HashSet<String> = HashSet::new();
    for path in frame_paths.iter().rev() {
        if let Some(rel) = resolve_frame_path(path, corpus) {
            if seen_files.insert(rel.clone()) {
                trace_files.push(rel);
            }
        }
    }

    // Fence treatment: mine-then-discard.
    let mined = mine_code_identifiers(&fence_text);
    let mined_text = mined.join(" ");

    // Term assembly: prose first, then trace, then fence; dedupe with
    // first-channel provenance; same length/STOP gates as `query_terms`.
    let mut seen: HashSet<String> = HashSet::new();
    let mut terms: Vec<String> = Vec::new();
    let mut counts = [0usize; 3];
    for (ci, text) in [(0usize, prose_text.as_str()), (1, trace_text.as_str()), (2, mined_text.as_str())] {
        for t in tokenize(text) {
            if !seen.contains(&t) && t.chars().count() > 2 && !STOP.contains(t.as_str()) {
                seen.insert(t.clone());
                terms.push(t);
                counts[ci] += 1;
            }
        }
    }
    let total = counts[0] + counts[1] + counts[2];
    let fence_dominant = fence_bearing && total > 0 && counts[2] * 2 > total;

    RoutedQuery {
        terms,
        trace_files,
        trace_bearing,
        fence_bearing,
        fence_dominant,
        n_prose_terms: counts[0],
        n_trace_terms: counts[1],
        n_fence_terms: counts[2],
    }
}

/// E11b (campaign #4 wave 5): trace-frame FILE extraction ONLY -- the one
/// E11 sub-mechanism that survived the dual gate (4 FILE rescues / 0 losses
/// across Lite + Verified). Unlike `route_query`, this touches NOTHING about
/// the query text: it scans every line for CPython traceback frame lines
/// (`File "X", line N, in f`), resolves the frame paths into the corpus
/// (`resolve_frame_path`, >= 2 trailing components), and returns the
/// resolved repo-relative files raise-site-first (Python's LAST frame =
/// rank 1, BRTracer top-of-stack semantics), deduped keeping best rank.
///
/// Equivalence note: this produces EXACTLY `route_query(q, corpus)
/// .trace_files` -- `partition_channels` pass 1 claims every
/// `TB_FRAME_RE`-matching line as trace-channel (a traceback inside a
/// markdown fence included), so scanning all lines directly is the same
/// frame set in the same order (proven by `trace_frame_files_matches_route_query`).
pub fn trace_frame_files(question: &str, corpus: &Corpus) -> Vec<String> {
    let lines = py_splitlines(question);
    let mut frame_paths: Vec<String> = Vec::new();
    for l in &lines {
        if let Some(cap) = TB_FRAME_RE.captures(l) {
            frame_paths.push(cap.get(1).unwrap().as_str().to_string());
        }
    }
    let mut out: Vec<String> = Vec::new();
    let mut seen: HashSet<String> = HashSet::new();
    for path in frame_paths.iter().rev() {
        if let Some(rel) = resolve_frame_path(path, corpus) {
            if seen.insert(rel.clone()) {
                out.push(rel);
            }
        }
    }
    out
}

// ---------------------------------------------------------------- E20 LexBoost
//
// LexBoost (Kulkarni et al., DocEng 2024, arXiv:2409.05882), campaign #4
// wave 5 transplant #2: smooth each file's channel-fused lexical score with
// the MEAN score of its corpus-graph neighbors --
//
//     S'(f) = lambda * S(f) + (1 - lambda) * impl_prior(f) * mean_{n in N(f)} S(n)
//
// so a gold file with weak direct overlap is promoted when its neighborhood
// scores well (the E-class "gold file never returned" shape). Two graph
// substrates, both deterministic and model-free (the paper's own graphs are
// dense-encoder-built; the fully lexical variant is roust's experiment):
//   - import: the existing undirected import graph (`build_import_graph`,
//     free -- it is already built and cached for every query);
//   - knn: BM25 k-nearest-neighbor files (K=16, the paper's construction),
//     computed from the cached corpus statistics at query time.
// MEAN aggregation (not sum) is load-bearing per the paper -- a hub with
// many weak neighbors must not accumulate. Two roust-specific guards on
// top: (1) hub protection -- files whose graph IN-degree (how many files
// list them as a neighbor) is in the corpus's top decile receive NO
// neighbor term (their smoothed score is `lambda * S(f)`, the same as a
// file whose neighbors all score zero -- NOT their raw score, which would
// hand hubs a relative advantage over every smoothed file); (2) the
// neighbor term is multiplied by `impl_prior(f)`, so a test/example-shaped
// file cannot ride neighbor support past the damping its direct score
// already receives (the paper has no document priors; without this a test
// file adjacent to hot production files would be inserted un-damped).
//
// A file with S(f) = 0 but a positive neighbor term is INSERTED into the
// candidate map -- like the E11 trace boost, this is an E-class rescue
// mechanism, able to surface files with zero direct lexical presence.

/// Neighbor lists for LexBoost smoothing: `{file: sorted neighbor files}`.
/// `BTreeMap` + sorted `Vec` values = fully canonical iteration and
/// summation order everywhere downstream.
pub type NeighborMap = BTreeMap<String, Vec<String>>;

/// Import-graph neighbor lists: each file's undirected import adjacency
/// (`build_import_graph` edges), sorted. Files with no import edges are
/// absent (no neighbors -> no smoothing term).
pub fn lexboost_import_neighbors(edges: &EdgeMap) -> NeighborMap {
    let mut out: NeighborMap = BTreeMap::new();
    for (f, adj) in edges {
        if !adj.is_empty() {
            out.insert(f.clone(), adj.iter().cloned().collect());
        }
    }
    out
}

/// BM25-kNN neighbor lists (the LexBoost paper's construction, K nearest
/// files by BM25 similarity of file content, lexical variant): each file's
/// top-`k` most-similar OTHER files, where similarity = Okapi BM25
/// (k1=1.2, b=0.75, content field only -- no path/comment channels, no
/// impl_prior: this is doc-doc similarity, not query relevance) of the
/// candidate against the source file's top-`KNN_QUERY_TERMS` tf-idf terms.
///
/// Determinism: query-term selection sorts by (weight desc, term asc);
/// per-candidate accumulation follows that canonical term order; the final
/// top-k sorts by (score desc via total_cmp, path asc); the returned
/// neighbor list is re-sorted by path (the mean is order-insensitive
/// mathematically, path order makes the summation canonical too).
/// Cost guard: terms with df > KNN_MAX_DF are skipped as query terms
/// (their idf makes them near-useless for similarity anyway), bounding the
/// posting-scan cost on large corpora.
pub const KNN_QUERY_TERMS: usize = 32;
pub const KNN_MAX_DF: u32 = 512;

pub fn lexboost_knn_neighbors(corpus: &Corpus, k: usize) -> NeighborMap {
    let n = corpus.files.len();
    if n < 2 || k == 0 {
        return BTreeMap::new();
    }
    let n_docs = corpus.n_docs as f64;
    let idf_of = |dfv: u32| -> f64 { (1.0 + (n_docs - dfv as f64 + 0.5) / (dfv as f64 + 0.5)).ln() };

    // Per-file top query terms by tf*idf (canonical order).
    let mut file_qterms: Vec<Vec<String>> = Vec::with_capacity(n);
    let mut term_union: BTreeSet<String> = BTreeSet::new();
    for rel in &corpus.files {
        let mut weighted: Vec<(String, f64)> = Vec::new();
        if let Some(tf_map) = corpus.tf.get(rel) {
            for (t, &tfv) in tf_map {
                let dfv = *corpus.df.get(t).unwrap_or(&1);
                if dfv > KNN_MAX_DF {
                    continue;
                }
                weighted.push((t.clone(), tfv as f64 * idf_of(dfv)));
            }
        }
        weighted.sort_by(|a, b| b.1.total_cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
        let qterms: Vec<String> = weighted.into_iter().take(KNN_QUERY_TERMS).map(|(t, _)| t).collect();
        term_union.extend(qterms.iter().cloned());
        file_qterms.push(qterms);
    }

    // Postings for the selected-term union, in corpus.files order.
    let mut postings: HashMap<&str, Vec<(u32, u32)>> = HashMap::new(); // term -> [(file idx, tf)]
    for (i, rel) in corpus.files.iter().enumerate() {
        if let Some(tf_map) = corpus.tf.get(rel) {
            for (t, &tfv) in tf_map {
                if let Some(t_key) = term_union.get(t.as_str()) {
                    postings.entry(t_key.as_str()).or_default().push((i as u32, tfv));
                }
            }
        }
    }

    let (k1, b) = (1.2_f64, 0.75_f64);
    let mut out: NeighborMap = BTreeMap::new();
    for (i, rel) in corpus.files.iter().enumerate() {
        let mut acc: HashMap<u32, f64> = HashMap::new();
        for t in &file_qterms[i] {
            let dfv = *corpus.df.get(t).unwrap_or(&1);
            let idf = idf_of(dfv);
            if let Some(plist) = postings.get(t.as_str()) {
                for &(j, tfv) in plist {
                    if j as usize == i {
                        continue;
                    }
                    let dl = *corpus.doclen.get(&corpus.files[j as usize]).unwrap_or(&0) as f64;
                    let tfv = tfv as f64;
                    let denom = tfv + k1 * (1.0 - b + b * dl / corpus.avg_len);
                    *acc.entry(j).or_insert(0.0) += idf * (tfv * (k1 + 1.0) / denom);
                }
            }
        }
        if acc.is_empty() {
            continue;
        }
        let mut cands: Vec<(u32, f64)> = acc.into_iter().collect();
        cands.sort_by(|a, b| {
            b.1.total_cmp(&a.1).then_with(|| corpus.files[a.0 as usize].cmp(&corpus.files[b.0 as usize]))
        });
        let mut nbrs: Vec<String> =
            cands.into_iter().take(k).map(|(j, _)| corpus.files[j as usize].clone()).collect();
        nbrs.sort();
        out.insert(rel.clone(), nbrs);
    }
    out
}

/// Hub set for the LexBoost high-degree guard: files whose IN-degree under
/// the neighbor relation (the number of OTHER files listing them as a
/// neighbor) is STRICTLY ABOVE the 90th-percentile in-degree of all files
/// with in-degree >= 1. Strict `>` (not `>=`) so a corpus where every
/// in-degree ties (tiny repos, uniform graphs) marks NO hubs rather than
/// all files. For the undirected import graph, in-degree equals adjacency
/// size; for the kNN graph it is the "how many files consider me near"
/// count -- exactly the sense in which `sympy/core/expr.py`-style
/// attractors are hubs.
pub fn lexboost_hubs(nbrs: &NeighborMap) -> HashSet<String> {
    let mut indeg: BTreeMap<&str, usize> = BTreeMap::new();
    for (f, nb) in nbrs {
        for x in nb {
            if x != f {
                *indeg.entry(x.as_str()).or_insert(0) += 1;
            }
        }
    }
    if indeg.is_empty() {
        return HashSet::new();
    }
    let mut degs: Vec<usize> = indeg.values().copied().collect();
    degs.sort_unstable();
    let thr = degs[(degs.len() - 1) * 9 / 10];
    indeg.into_iter().filter(|(_, d)| *d > thr).map(|(f, _)| f.to_string()).collect()
}

/// Apply LexBoost smoothing to the normalized fused file-score map. Returns
/// the smoothed map plus a bounded diagnostic dump (top entries by smoothed
/// score: `(file, smoothed, direct, neighbor_mean, is_hub)`) for the
/// experiment harness's flip anatomy. See the section comment above for the
/// formula and guards. Map order: existing `bm_n` entries first (original
/// order, values updated in place), then inserted files in `corpus.files`
/// order -- canonical, and minimally perturbing relative to the unsmoothed
/// map (downstream tie-breaks on equal scores follow map insertion order).
fn apply_lexboost(
    bm_n: &IndexMap<String, f64>,
    corpus: &Corpus,
    nbrs: &NeighborMap,
    hubs: &HashSet<String>,
    lambda: f64,
) -> (IndexMap<String, f64>, Vec<(String, f64, f64, f64, bool)>) {
    let nb_mean = |f: &str| -> f64 {
        match nbrs.get(f) {
            Some(nb) if !nb.is_empty() => {
                let mut sum = 0.0;
                for x in nb {
                    sum += bm_n.get(x).copied().unwrap_or(0.0);
                }
                sum / nb.len() as f64
            }
            _ => 0.0,
        }
    };

    let mut smoothed: IndexMap<String, f64> = IndexMap::with_capacity(bm_n.len());
    let mut diag: Vec<(String, f64, f64, f64, bool)> = Vec::new();
    for (f, &direct) in bm_n {
        let hub = hubs.contains(f);
        let mean = if hub { 0.0 } else { nb_mean(f) };
        let val = lambda * direct + (1.0 - lambda) * impl_prior(f) * mean;
        smoothed.insert(f.clone(), val);
        diag.push((f.clone(), val, direct, mean, hub));
    }
    // Insertion pass (E-class rescue): files absent from bm_n whose
    // neighbor term alone is positive.
    if lambda < 1.0 {
        for f in &corpus.files {
            if bm_n.contains_key(f) || hubs.contains(f) {
                continue;
            }
            let mean = nb_mean(f);
            if mean > 0.0 {
                let val = (1.0 - lambda) * impl_prior(f) * mean;
                smoothed.insert(f.clone(), val);
                diag.push((f.clone(), val, 0.0, mean, false));
            }
        }
    }
    diag.sort_by(|a, b| b.1.total_cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    diag.truncate(30);
    (smoothed, diag)
}

/// Calibrated low-confidence gate (issue #25). `top_score` is the raw,
/// pre-normalization top pooled BM25F score (`Explain::top_score`);
/// `matched_terms`/`total_terms` come from `query_term_coverage`. Trips when
/// EITHER the strongest candidate's raw score is below
/// `LOW_CONFIDENCE_TOP_SCORE`, OR fewer than
/// `LOW_CONFIDENCE_MATCH_FRACTION` of the query's terms exist anywhere in the
/// corpus vocabulary -- either one, on its own, is evidence the match is
/// coincidental rather than substantive.
///
/// Calibrated empirically (issue #25), not guessed:
///   - Real population: all 300 SWE-bench Lite (query, repo) pairs.
///     top_score min/p5/p25/median/p75/max = 12.04/37.44/63.07/89.98/139.18/361.99.
///     matched-fraction min/p5/p25/median/p75/max = 0.460/0.865/0.938/0.965/1.0/1.0.
///   - Gibberish population: 30 queries (15 random-ASCII, 10 shuffled-identifier
///     soup, 5 plausible-but-wrong feature descriptions) x 3 repos (django,
///     this repo, matplotlib) = 90 runs; 70/90 were literal zero-match (caught
///     by the exit-1 gate below, not this flag). Of the remaining 20
///     (nonzero-match) runs: top_score min/p5/p25/median/p75/max =
///     1.26/1.44/2.66/8.48/11.94/24.75; matched-fraction min/max = 0.20/0.875.
///
/// The two top_score distributions OVERLAP (gibberish max 24.75 > real min
/// 12.04) -- there is no threshold with full separation. Per the hard
/// constraint (zero false trips on the 300 real queries), thresholds are set
/// just under the observed real-query minima: 12.0 (vs. real min 12.04) and
/// 0.45 (vs. real min match-fraction 0.460). At these thresholds: 0/300 real
/// queries trip; 16/20 (80%) of the nonzero-match gibberish runs trip (all
/// with top_score < 12.0) -- combined with the 70 caught by exit-1, 86/90
/// (95.6%) of the full gibberish population is flagged one way or the other.
/// The 4 gibberish queries that slip through untripped are the deliberately
/// hardest case: plausible-but-wrong feature descriptions (e.g. "OAuth2
/// device code flow refresh token rotation", "GraphQL subscription resolver
/// batching") that happen to share enough real vocabulary with the target
/// repo (auth/token/schema-adjacent terms) to score above both thresholds --
/// an accepted, reported trade-off per the calibration spec, not a bug.
pub const LOW_CONFIDENCE_TOP_SCORE: f64 = 12.0;
pub const LOW_CONFIDENCE_MATCH_FRACTION: f64 = 0.45;

pub fn is_low_confidence(top_score: f64, matched_terms: usize, total_terms: usize) -> bool {
    if total_terms == 0 {
        return true;
    }
    let match_fraction = matched_terms as f64 / total_terms as f64;
    top_score < LOW_CONFIDENCE_TOP_SCORE || match_fraction < LOW_CONFIDENCE_MATCH_FRACTION
}

// ---------------------------------------------------------------- corpus + BM25

pub static TESTLIKE_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"(?i)(^|/)(tests?|testing|spec|specs|benches|benchmarks?|examples?|fixtures?|mocks?|docs?|__tests__|e2e|docs_src|tutorials?|samples?|demos?|playground|scripts?|integration|t)(/|$)|(^|/)(test_|conftest)|_test\.(py|go|rs|ts|js)$|\.test\.|\.spec\.",
    )
    .unwrap()
});

static VENDOR_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)(vendor|vendored|third_party|node_modules|\.min\.(js|css)$|bundle\.js$)").unwrap());

const MAX_LINE_CHARS: usize = 3000;

pub fn impl_prior(rel: &str) -> f64 {
    if TESTLIKE_RE.is_match(rel) {
        0.3
    } else {
        1.0
    }
}

static PATH_SPLIT_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[/\\.\-]").unwrap());

pub fn path_tokens(rel: &str) -> HashSet<String> {
    let mut toks = HashSet::new();
    for part in PATH_SPLIT_RE.split(rel) {
        let low = py_lower(part);
        if low.chars().count() > 2 && !STOP.contains(low.as_str()) {
            toks.insert(stem(&low));
        }
        for s in subtokens(part) {
            toks.insert(s);
        }
    }
    toks
}

// ---------------------------------------------------------------- NL/comment extraction

static PY_DEF_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?m)^\s*(?:class|def)\s+(\w+)").unwrap());
static GO_DEF_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?m)^func\s+(?:\([^)]*\)\s*)?(\w+)").unwrap());
static RS_DEF_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^\s*(?:pub\s+)?fn\s+(\w+)|^\s*(?:pub\s+)?struct\s+(\w+)").unwrap());
static JS_DEF_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^\s*(?:export\s+)?(?:function|class)\s+(\w+)").unwrap());

static PY_DOCSTRING_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r#"(?s)"""(.*?)"""|'''(.*?)'''"#).unwrap());
static PY_COMMENT_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?m)#(.*)$").unwrap());
static C_BLOCK_COMMENT_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?s)/\*(.*?)\*/").unwrap());
static C_LINE_COMMENT_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?m)//(.*)$").unwrap());

pub fn extract_comments(rel: &str, text: &str) -> String {
    let mut parts: Vec<String> = Vec::new();
    if rel.ends_with(".py") {
        for cap in PY_DOCSTRING_RE.captures_iter(text) {
            let g = cap.get(1).or_else(|| cap.get(2)).map(|m| m.as_str()).unwrap_or("");
            parts.push(g.to_string());
        }
        for cap in PY_COMMENT_RE.captures_iter(text) {
            parts.push(cap.get(1).map(|m| m.as_str()).unwrap_or("").to_string());
        }
    } else {
        for cap in C_BLOCK_COMMENT_RE.captures_iter(text) {
            parts.push(cap.get(1).map(|m| m.as_str()).unwrap_or("").to_string());
        }
        for cap in C_LINE_COMMENT_RE.captures_iter(text) {
            parts.push(cap.get(1).map(|m| m.as_str()).unwrap_or("").to_string());
        }
    }
    parts.join("\n")
}

// ---------------------------------------------------------------- docs field constants

pub const DOCS_EXTENSIONS: &[&str] = &[".rst", ".txt", ".md"];
static DOCS_EXCLUDE_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)(^|/)(tests?|testing|__tests__)(/|$)").unwrap());
pub(crate) const MAX_DOCS_FILE_BYTES: u64 = 500_000;
const MAX_DOCS_FILES: usize = 4000;

// ---------------------------------------------------------------- filesystem walk

/// Enumerate candidate files via `git ls-files` (tracked + untracked-but-
/// not-ignored), inheriting .gitignore/.git/info/exclude/global excludes --
/// exactly ripgrep's file-discovery semantics. Returns `None` if
/// `repo_path` isn't inside a git work tree, or if the git invocation fails
/// for ANY reason -- callers must fall back to a raw filesystem walk rather
/// than hard-fail indexing.
pub(crate) fn git_ls_files(repo_path: &Path) -> Option<Vec<String>> {
    let check = std::process::Command::new("git")
        .args(["rev-parse", "--is-inside-work-tree"])
        .current_dir(repo_path)
        .output()
        .ok()?;
    if !check.status.success() || String::from_utf8_lossy(&check.stdout).trim() != "true" {
        return None;
    }
    let output = std::process::Command::new("git")
        .args(["ls-files", "-z", "--cached", "--others", "--exclude-standard"])
        .current_dir(repo_path)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    Some(
        output
            .stdout
            .split(|&b| b == 0)
            .filter(|s| !s.is_empty())
            .map(|s| String::from_utf8_lossy(s).into_owned())
            .collect(),
    )
}

/// Order paths the way `sorted(repo_path.rglob("*"))` does: full component-
/// wise (parts-tuple) comparison, computed once over ALL files then used to
/// sort; directories are never yielded (Python's loop `continue`s on
/// `not p.is_file()` immediately, so their traversal order is irrelevant to
/// the surviving files' relative order).
///
/// Prefers `git_ls_files` when `repo_path` is inside a git work tree (see
/// above), falling back to a raw filesystem walk otherwise -- or if the git
/// invocation fails for any reason. Falling back to the raw walk means
/// entries here are not guaranteed to be plain files in the git-list case
/// (e.g. a submodule gitlink); callers must still verify via `is_file`
/// metadata before reading.
///
/// `pub(crate)` so `cache.rs` can enumerate the SAME candidate set for its
/// manifest / history current-files scans (rather than re-walking with its
/// own logic) -- the manifest must cover exactly the files `Corpus::build`
/// indexes, or add/remove change detection would desync from what actually
/// gets (re)indexed.
pub(crate) fn walk_all_files(repo_path: &Path) -> Vec<String> {
    if let Some(mut rels) = git_ls_files(repo_path) {
        rels.sort_by(|a, b| path_sort_key(a).cmp(&path_sort_key(b)));
        return rels;
    }
    let mut out: Vec<String> = Vec::new();
    fn recurse(dir: &Path, base: &Path, out: &mut Vec<String>) {
        let entries = match std::fs::read_dir(dir) {
            Ok(e) => e,
            Err(_) => return,
        };
        let mut items: Vec<std::fs::DirEntry> = entries.flatten().collect();
        items.sort_by_key(|e| e.file_name());
        for entry in items {
            let path = entry.path();
            let file_type = match entry.file_type() {
                Ok(t) => t,
                Err(_) => continue,
            };
            if file_type.is_dir() {
                recurse(&path, base, out);
            } else {
                let is_file = if file_type.is_symlink() {
                    std::fs::metadata(&path).map(|m| m.is_file()).unwrap_or(false)
                } else {
                    file_type.is_file()
                };
                if is_file {
                    if let Ok(rel) = path.strip_prefix(base) {
                        if let Some(relstr) = rel.to_str() {
                            out.push(relstr.replace('\\', "/"));
                        }
                    }
                }
            }
        }
    }
    recurse(repo_path, repo_path, &mut out);
    out.sort_by(|a, b| path_sort_key(a).cmp(&path_sort_key(b)));
    out
}

fn read_text_lossy(path: &Path) -> Option<String> {
    let bytes = std::fs::read(path).ok()?;
    Some(String::from_utf8_lossy(&bytes).into_owned())
}

fn counter_from_tokens(tokens: &[String]) -> IndexMap<String, u32> {
    let mut m = IndexMap::new();
    for t in tokens {
        *m.entry(t.clone()).or_insert(0) += 1;
    }
    m
}

// ---------------------------------------------------------------- Corpus

#[derive(Serialize, Deserialize)]
pub struct Corpus {
    pub repo_path: PathBuf,
    pub files: Vec<String>,
    pub text: HashMap<String, String>,
    pub ptoks: HashMap<String, HashSet<String>>,
    pub tf: HashMap<String, IndexMap<String, u32>>,
    pub doclen: HashMap<String, u32>,
    pub df: HashMap<String, u32>,
    pub use_comments: bool,
    pub com_tf: HashMap<String, IndexMap<String, u32>>,
    pub com_df: HashMap<String, u32>,
    pub def_index: HashMap<String, Vec<String>>,
    pub n_docs: usize,
    pub avg_len: f64,
    pub n_com_docs: usize,

    pub msg_tf: HashMap<String, IndexMap<String, u32>>,
    pub msg_df: HashMap<String, u32>,
    pub msg_doclen: HashMap<String, u32>,
    pub n_msg_docs: usize,
    pub msg_avg_len: f64,

    pub docs_files: Vec<String>,
    pub docs_text: HashMap<String, String>,
    pub docs_tf: HashMap<String, IndexMap<String, u32>>,
    pub docs_df: HashMap<String, u32>,
    pub docs_len: HashMap<String, u32>,
    pub n_docs_files: usize,
    pub docs_avg_len: f64,
}

impl Corpus {
    pub fn build(
        repo_path: &Path,
        history_msgs: Option<&IndexMap<String, String>>,
        use_comments: bool,
        build_docs: bool,
    ) -> Corpus {
        let mut files = Vec::new();
        let mut text: HashMap<String, String> = HashMap::new();
        let mut ptoks: HashMap<String, HashSet<String>> = HashMap::new();
        let mut tf: HashMap<String, IndexMap<String, u32>> = HashMap::new();
        let mut doclen: HashMap<String, u32> = HashMap::new();
        let mut df: HashMap<String, u32> = HashMap::new();
        let mut com_tf: HashMap<String, IndexMap<String, u32>> = HashMap::new();
        let mut com_df: HashMap<String, u32> = HashMap::new();
        let mut def_index: HashMap<String, Vec<String>> = HashMap::new();

        let all_files = walk_all_files(repo_path);
        for rel in &all_files {
            if rel.starts_with(".git/") || rel.contains("/.git/") {
                continue;
            }
            if !has_code_suffix(rel) {
                continue;
            }
            if VENDOR_RE.is_match(rel) {
                continue;
            }
            let full = repo_path.join(rel);
            let meta = match std::fs::metadata(&full) {
                Ok(m) => m,
                Err(_) => continue,
            };
            if !meta.is_file() {
                continue;
            }
            if meta.len() > MAX_FILE_BYTES {
                continue;
            }
            let txt = match read_text_lossy(&full) {
                Some(t) => t,
                None => continue,
            };
            let text_lines = py_splitlines(&txt);
            if let Some(maxlen) = text_lines.iter().map(|l| l.chars().count()).max() {
                if maxlen > MAX_LINE_CHARS {
                    continue;
                }
            }
            let toks = tokenize(&txt);
            if toks.is_empty() {
                continue;
            }
            files.push(rel.clone());
            ptoks.insert(rel.clone(), path_tokens(rel));
            let counts = counter_from_tokens(&toks);
            for term in counts.keys() {
                *df.entry(term.clone()).or_insert(0) += 1;
            }
            doclen.insert(rel.clone(), toks.len() as u32);
            tf.insert(rel.clone(), counts);

            if use_comments {
                let com_text = extract_comments(rel, &txt);
                let com_toks = tokenize(&com_text);
                if !com_toks.is_empty() {
                    let ctf = counter_from_tokens(&com_toks);
                    for term in ctf.keys() {
                        *com_df.entry(term.clone()).or_insert(0) += 1;
                    }
                    com_tf.insert(rel.clone(), ctf);
                }
            }

            if impl_prior(rel) == 1.0 {
                let def_re: Option<&LazyLock<Regex>> = if rel.ends_with(".py") {
                    Some(&PY_DEF_RE)
                } else if rel.ends_with(".go") {
                    Some(&GO_DEF_RE)
                } else if rel.ends_with(".rs") {
                    Some(&RS_DEF_RE)
                } else if rel.ends_with(".js") || rel.ends_with(".ts") || rel.ends_with(".jsx") || rel.ends_with(".tsx") {
                    Some(&JS_DEF_RE)
                } else {
                    None
                };
                if let Some(re) = def_re {
                    let mut syms: HashSet<String> = HashSet::new();
                    for cap in re.captures_iter(&txt) {
                        for gi in 1..cap.len() {
                            if let Some(g) = cap.get(gi) {
                                syms.insert(g.as_str().to_string());
                            }
                        }
                    }
                    for sym in syms {
                        def_index.entry(sym).or_default().push(rel.clone());
                    }
                }
            }

            text.insert(rel.clone(), txt);
        }

        let n_docs = files.len();
        let avg_len = if n_docs > 0 {
            doclen.values().map(|&v| v as f64).sum::<f64>() / n_docs as f64
        } else {
            1.0
        };
        let n_com_docs = com_tf.len();

        // commit-message field
        let mut msg_tf: HashMap<String, IndexMap<String, u32>> = HashMap::new();
        let mut msg_df: HashMap<String, u32> = HashMap::new();
        let mut msg_doclen: HashMap<String, u32> = HashMap::new();
        if let Some(hm) = history_msgs {
            if !hm.is_empty() {
                for rel in &files {
                    let msg = match hm.get(rel) {
                        Some(m) if !m.is_empty() => m,
                        _ => continue,
                    };
                    let mtoks = tokenize(msg);
                    if mtoks.is_empty() {
                        continue;
                    }
                    let mtf = counter_from_tokens(&mtoks);
                    for term in mtf.keys() {
                        *msg_df.entry(term.clone()).or_insert(0) += 1;
                    }
                    msg_doclen.insert(rel.clone(), mtoks.len() as u32);
                    msg_tf.insert(rel.clone(), mtf);
                }
            }
        }
        let n_msg_docs = msg_tf.len();
        let msg_avg_len = if n_msg_docs > 0 {
            msg_doclen.values().map(|&v| v as f64).sum::<f64>() / n_msg_docs as f64
        } else {
            1.0
        };

        // docs field
        let mut docs_files: Vec<String> = Vec::new();
        let mut docs_text: HashMap<String, String> = HashMap::new();
        let mut docs_tf: HashMap<String, IndexMap<String, u32>> = HashMap::new();
        let mut docs_df: HashMap<String, u32> = HashMap::new();
        let mut docs_len: HashMap<String, u32> = HashMap::new();
        if build_docs {
            let mut doc_paths: Vec<String> = Vec::new();
            for rel in &all_files {
                if rel.starts_with(".git/") || rel.contains("/.git/") {
                    continue;
                }
                let suf = suffix_of(rel);
                if !DOCS_EXTENSIONS.contains(&suf) {
                    continue;
                }
                if DOCS_EXCLUDE_RE.is_match(rel) {
                    continue;
                }
                doc_paths.push(rel.clone());
            }
            for rel in doc_paths.into_iter().take(MAX_DOCS_FILES) {
                let full = repo_path.join(&rel);
                let meta = match std::fs::metadata(&full) {
                    Ok(m) => m,
                    Err(_) => continue,
                };
                if !meta.is_file() {
                    continue;
                }
                if meta.len() > MAX_DOCS_FILE_BYTES {
                    continue;
                }
                let txt = match read_text_lossy(&full) {
                    Some(t) => t,
                    None => continue,
                };
                let dtoks = tokenize(&txt);
                if dtoks.is_empty() {
                    continue;
                }
                let dcounts = counter_from_tokens(&dtoks);
                for term in dcounts.keys() {
                    *docs_df.entry(term.clone()).or_insert(0) += 1;
                }
                docs_len.insert(rel.clone(), dtoks.len() as u32);
                docs_tf.insert(rel.clone(), dcounts);
                docs_text.insert(rel.clone(), txt);
                docs_files.push(rel);
            }
        }
        let n_docs_files = docs_files.len();
        let docs_avg_len = if n_docs_files > 0 {
            docs_len.values().map(|&v| v as f64).sum::<f64>() / n_docs_files as f64
        } else {
            1.0
        };

        Corpus {
            repo_path: repo_path.to_path_buf(),
            files,
            text,
            ptoks,
            tf,
            doclen,
            df,
            use_comments,
            com_tf,
            com_df,
            def_index,
            n_docs,
            avg_len,
            n_com_docs,
            msg_tf,
            msg_df,
            msg_doclen,
            n_msg_docs,
            msg_avg_len,
            docs_files,
            docs_text,
            docs_tf,
            docs_df,
            docs_len,
            n_docs_files,
            docs_avg_len,
        }
    }

    // -------------------------------------------------------- incremental update
    //
    // Ports of `roust.core.Corpus.update_files` / `update_docs_files` (see
    // `cache.py`'s module docstring for the design). Both exist for
    // `crate::cache`'s incremental-update path (the common agent edit-loop
    // case: a file's CONTENT changed but its relpath set did not). Each
    // re-derives a modified file's contribution to the corpus from scratch
    // (subtract old, add new) using the identical per-file logic `build`
    // uses, so a successfully patched Corpus is observationally identical to
    // a fresh build over the same on-disk content. Neither method touches
    // `ptoks` (unchanged by a content-only edit) or the `msg_*` fields
    // (commit history is keyed on git HEAD, which incremental updates
    // require to be unchanged -- see `cache.rs`).
    //
    // Both are all-or-nothing: every file is pre-checked against `build`'s
    // own inclusion criteria BEFORE any mutation happens, so a `false`
    // return leaves the Corpus completely unmodified and the caller is free
    // to discard it and fall back to a full rebuild.

    /// Which definition-symbol regex (if any) applies to `rel`, by
    /// extension -- factored out of `build`'s per-file if/elif chain so
    /// `update_files` can reuse the identical mapping when
    /// subtracting/re-adding a modified file's `def_index` contributions.
    fn def_re_for(rel: &str) -> Option<&'static Regex> {
        if rel.ends_with(".py") {
            Some(&PY_DEF_RE)
        } else if rel.ends_with(".go") {
            Some(&GO_DEF_RE)
        } else if rel.ends_with(".rs") {
            Some(&RS_DEF_RE)
        } else if rel.ends_with(".js") || rel.ends_with(".ts") || rel.ends_with(".jsx") || rel.ends_with(".tsx") {
            Some(&JS_DEF_RE)
        } else {
            None
        }
    }

    fn def_syms(def_re: &Regex, text: &str) -> HashSet<String> {
        let mut syms = HashSet::new();
        for cap in def_re.captures_iter(text) {
            for gi in 1..cap.len() {
                if let Some(g) = cap.get(gi) {
                    syms.insert(g.as_str().to_string());
                }
            }
        }
        syms
    }

    /// Patch this Corpus in place for `rels` -- files already present in
    /// `self.files` whose on-disk content has changed. Re-reads each file
    /// directly from `self.repo_path` and applies exactly `build`'s per-file
    /// inclusion criteria (`MAX_FILE_BYTES`, `MAX_LINE_CHARS`, non-empty
    /// tokenization); if any file's new content fails a criterion (or can no
    /// longer be read), this is shaped like an add/remove and this method
    /// makes NO changes and returns `false` -- callers must fall back to a
    /// full rebuild. Returns `true`, having refreshed
    /// df/tf/doclen/text/def_index (and com_tf/com_df if use_comments) plus
    /// avg_len/n_com_docs, on full success.
    pub fn update_files(&mut self, rels: &[String]) -> bool {
        let mut new_text: HashMap<String, String> = HashMap::new();
        let mut new_toks: HashMap<String, Vec<String>> = HashMap::new();
        for rel in rels {
            let p = self.repo_path.join(rel);
            let meta = match std::fs::metadata(&p) {
                Ok(m) => m,
                Err(_) => return false,
            };
            if meta.len() > MAX_FILE_BYTES {
                return false;
            }
            let text = match read_text_lossy(&p) {
                Some(t) => t,
                None => return false,
            };
            let lines = py_splitlines(&text);
            if let Some(maxlen) = lines.iter().map(|l| l.chars().count()).max() {
                if maxlen > MAX_LINE_CHARS {
                    return false;
                }
            }
            let toks = tokenize(&text);
            if toks.is_empty() {
                return false;
            }
            new_text.insert(rel.clone(), text);
            new_toks.insert(rel.clone(), toks);
        }

        // Corpus-order position of every indexed file. `build` fills each
        // `def_index` symbol's definer list by pushing files in
        // `self.files` walk order, so an incremental re-add must re-insert
        // the updated file at its files-order slot -- NOT push it to the
        // end, which would leave a multi-definer symbol's list permuted
        // versus a fresh `--reindex` build (and anchor resolution consumes
        // `def_index[s]` in list order, so the permutation is observable).
        let file_pos: HashMap<String, usize> = self.files.iter().enumerate().map(|(i, f)| (f.clone(), i)).collect();

        for rel in rels {
            // --- subtract old contributions (self.text[rel] is still old here)
            if let Some(old_tf) = self.tf.get(rel) {
                for term in old_tf.keys() {
                    if let Some(c) = self.df.get_mut(term) {
                        *c -= 1;
                        if *c == 0 {
                            self.df.remove(term);
                        }
                    }
                }
            }
            self.tf.remove(rel);
            self.doclen.remove(rel);
            if self.use_comments {
                if let Some(old_ctf) = self.com_tf.remove(rel) {
                    for term in old_ctf.keys() {
                        if let Some(c) = self.com_df.get_mut(term) {
                            *c -= 1;
                            if *c == 0 {
                                self.com_df.remove(term);
                            }
                        }
                    }
                }
            }
            let def_re = if impl_prior(rel) == 1.0 { Self::def_re_for(rel) } else { None };
            if let Some(re) = def_re {
                for sym in Self::def_syms(re, &self.text[rel]) {
                    if let Some(lst) = self.def_index.get_mut(&sym) {
                        lst.retain(|f| f != rel);
                    }
                }
            }

            // --- add new contributions
            let toks = &new_toks[rel];
            let counts = counter_from_tokens(toks);
            for term in counts.keys() {
                *self.df.entry(term.clone()).or_insert(0) += 1;
            }
            self.doclen.insert(rel.clone(), toks.len() as u32);
            self.tf.insert(rel.clone(), counts);
            self.text.insert(rel.clone(), new_text[rel].clone());
            if self.use_comments {
                let com_text = extract_comments(rel, &new_text[rel]);
                let com_toks = tokenize(&com_text);
                if !com_toks.is_empty() {
                    let ctf = counter_from_tokens(&com_toks);
                    for term in ctf.keys() {
                        *self.com_df.entry(term.clone()).or_insert(0) += 1;
                    }
                    self.com_tf.insert(rel.clone(), ctf);
                }
            }
            if let Some(re) = def_re {
                // Ordered re-insert (see `file_pos` above): place `rel`
                // before the first already-listed definer that comes AFTER
                // it in corpus order, keeping every list byte-identical to
                // what a fresh `build` would produce. The removal pass
                // above already `retain`ed `rel` out, and `def_syms`
                // returns a de-duplicated set, so no duplicate check is
                // needed here.
                let rp = file_pos.get(rel).copied().unwrap_or(usize::MAX);
                for sym in Self::def_syms(re, &new_text[rel]) {
                    let lst = self.def_index.entry(sym).or_default();
                    let ins = lst
                        .iter()
                        .position(|f| file_pos.get(f).copied().unwrap_or(usize::MAX) > rp)
                        .unwrap_or(lst.len());
                    lst.insert(ins, rel.clone());
                }
            }
        }

        self.n_com_docs = self.com_tf.len();
        self.avg_len = if self.n_docs > 0 {
            self.doclen.values().map(|&v| v as f64).sum::<f64>() / self.n_docs as f64
        } else {
            1.0
        };
        true
    }

    /// Analogous to `update_files` but for the docs field (`*.rst`/`*.txt`/
    /// `*.md` pages collected when this Corpus was built with
    /// `build_docs=true`). Every rel must already be a member of
    /// `self.docs_files`. Returns `false` (no changes) if any file's new
    /// content would flip its `build` inclusion verdict (now oversized, or
    /// now tokenizes to nothing) or can no longer be read -- callers must
    /// fall back to a full rebuild.
    pub fn update_docs_files(&mut self, rels: &[String]) -> bool {
        let mut new_text: HashMap<String, String> = HashMap::new();
        let mut new_toks: HashMap<String, Vec<String>> = HashMap::new();
        for rel in rels {
            let p = self.repo_path.join(rel);
            let meta = match std::fs::metadata(&p) {
                Ok(m) => m,
                Err(_) => return false,
            };
            if meta.len() > MAX_DOCS_FILE_BYTES {
                return false;
            }
            let text = match read_text_lossy(&p) {
                Some(t) => t,
                None => return false,
            };
            let toks = tokenize(&text);
            if toks.is_empty() {
                return false;
            }
            new_text.insert(rel.clone(), text);
            new_toks.insert(rel.clone(), toks);
        }

        for rel in rels {
            if let Some(old_tf) = self.docs_tf.get(rel) {
                for term in old_tf.keys() {
                    if let Some(c) = self.docs_df.get_mut(term) {
                        *c -= 1;
                        if *c == 0 {
                            self.docs_df.remove(term);
                        }
                    }
                }
            }
            let toks = &new_toks[rel];
            let counts = counter_from_tokens(toks);
            for term in counts.keys() {
                *self.docs_df.entry(term.clone()).or_insert(0) += 1;
            }
            self.docs_len.insert(rel.clone(), toks.len() as u32);
            self.docs_tf.insert(rel.clone(), counts);
            self.docs_text.insert(rel.clone(), new_text[rel].clone());
        }

        self.docs_avg_len = if self.n_docs_files > 0 {
            self.docs_len.values().map(|&v| v as f64).sum::<f64>() / self.n_docs_files as f64
        } else {
            1.0
        };
        true
    }

    /// BM25F-style: body field (Okapi) + path field (binary match, weighted),
    /// multiplied by the implementation-file document prior, plus an
    /// optional comment/NL field term. See lanes2.py's `Corpus.bm25`
    /// docstring. The returned map's *insertion order* is load-bearing: it
    /// is later fed through `_normalize` and a stable `sorted()` whose
    /// tie-break is this order, so it must match Python's dict-insertion
    /// order exactly (see PARITY_NOTES.md).
    pub fn bm25(&self, terms: &[String]) -> IndexMap<String, f64> {
        self.bm25_params(terms, 1.2, 0.75, 2.5, true, 0.5)
    }

    pub fn bm25_params(
        &self,
        terms: &[String],
        k1: f64,
        b: f64,
        path_weight: f64,
        use_prior: bool,
        comment_weight: f64,
    ) -> IndexMap<String, f64> {
        let mut scores: IndexMap<String, f64> = IndexMap::new();
        for term in terms {
            if let Some(&dfv) = self.df.get(term) {
                let idf = (1.0 + (self.n_docs as f64 - dfv as f64 + 0.5) / (dfv as f64 + 0.5)).ln();
                for rel in &self.files {
                    if let Some(tfv) = self.tf.get(rel).and_then(|m| m.get(term)) {
                        let tfv = *tfv as f64;
                        let doclen = *self.doclen.get(rel).unwrap_or(&0) as f64;
                        let denom = tfv + k1 * (1.0 - b + b * doclen / self.avg_len);
                        *scores.entry(rel.clone()).or_insert(0.0) += idf * (tfv * (k1 + 1.0) / denom);
                    }
                }
                for rel in &self.files {
                    if self.ptoks.get(rel).map(|s| s.contains(term)).unwrap_or(false) {
                        *scores.entry(rel.clone()).or_insert(0.0) += path_weight * idf;
                    }
                }
            }
            if self.use_comments && !self.com_tf.is_empty() && self.n_com_docs > 0 {
                if let Some(&cdf) = self.com_df.get(term) {
                    let idf_com = (1.0 + (self.n_com_docs as f64 - cdf as f64 + 0.5) / (cdf as f64 + 0.5)).ln();
                    // Drive iteration via corpus.files (not com_tf.items()
                    // directly) -- com_tf's insertion order is a subset of
                    // corpus.files order anyway (built in the same
                    // per-file loop), so this reproduces Python's direct
                    // `self.com_tf.items()` iteration order exactly.
                    for rel in &self.files {
                        if let Some(ctf_counter) = self.com_tf.get(rel) {
                            if let Some(&ctf) = ctf_counter.get(term) {
                                let ctf = ctf as f64;
                                *scores.entry(rel.clone()).or_insert(0.0) +=
                                    comment_weight * idf_com * (ctf * (k1 + 1.0) / (ctf + k1));
                            }
                        }
                    }
                }
            }
        }
        if use_prior {
            scores.into_iter().map(|(rel, s)| (rel.clone(), s * impl_prior(&rel))).collect()
        } else {
            scores
        }
    }

    /// Standalone Okapi BM25 over the commit-message field only.
    pub fn msg_bm25(&self, terms: &[String]) -> IndexMap<String, f64> {
        self.msg_bm25_params(terms, 1.2, 0.5, true)
    }

    pub fn msg_bm25_params(&self, terms: &[String], k1: f64, b: f64, use_prior: bool) -> IndexMap<String, f64> {
        if self.msg_tf.is_empty() || self.n_msg_docs == 0 {
            return IndexMap::new();
        }
        let mut scores: IndexMap<String, f64> = IndexMap::new();
        for term in terms {
            let mdf = match self.msg_df.get(term) {
                Some(&v) => v,
                None => continue,
            };
            let idf = (1.0 + (self.n_msg_docs as f64 - mdf as f64 + 0.5) / (mdf as f64 + 0.5)).ln();
            for rel in &self.files {
                if let Some(mtf_counter) = self.msg_tf.get(rel) {
                    if let Some(&mtf) = mtf_counter.get(term) {
                        let mtf = mtf as f64;
                        let doclen = *self.msg_doclen.get(rel).unwrap_or(&0) as f64;
                        let denom = mtf + k1 * (1.0 - b + b * doclen / self.msg_avg_len);
                        *scores.entry(rel.clone()).or_insert(0.0) += idf * (mtf * (k1 + 1.0) / denom);
                    }
                }
            }
        }
        if use_prior {
            scores.into_iter().map(|(rel, s)| (rel.clone(), s * impl_prior(&rel))).collect()
        } else {
            scores
        }
    }

    /// Standard Okapi BM25 over the docs field.
    pub fn docs_bm25(&self, terms: &[String]) -> IndexMap<String, f64> {
        if self.docs_tf.is_empty() || self.n_docs_files == 0 {
            return IndexMap::new();
        }
        let (k1, b) = (1.2, 0.75);
        let mut scores: IndexMap<String, f64> = IndexMap::new();
        for term in terms {
            let ddf = match self.docs_df.get(term) {
                Some(&v) => v,
                None => continue,
            };
            let idf = (1.0 + (self.n_docs_files as f64 - ddf as f64 + 0.5) / (ddf as f64 + 0.5)).ln();
            for rel in &self.docs_files {
                if let Some(dtf_counter) = self.docs_tf.get(rel) {
                    if let Some(&dtf) = dtf_counter.get(term) {
                        let dtf = dtf as f64;
                        let doclen = *self.docs_len.get(rel).unwrap_or(&0) as f64;
                        let denom = dtf + k1 * (1.0 - b + b * doclen / self.docs_avg_len);
                        *scores.entry(rel.clone()).or_insert(0.0) += idf * (dtf * (k1 + 1.0) / denom);
                    }
                }
            }
        }
        scores
    }
}

// ---------------------------------------------------------------- definition-symbol anchors

static ANCHOR_IDENT_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[A-Za-z_][A-Za-z0-9_]{3,}").unwrap());
static CODE_SPAN_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?s)```.*?```|`[^`\n]+`").unwrap());

/// Definition-symbol anchor channel. See lanes2.py's `extract_symbol_anchors`
/// docstring. Fully deterministic (no raw-`set`-iteration hazard): `order`
/// is regex-match order over the question text, and `corpus.def_index[s]`
/// preserves corpus.files traversal order (each file contributes at most
/// one append per symbol, regardless of the per-file symbol dedup set's
/// internal order).
pub fn extract_symbol_anchors(question: &str, corpus: &Corpus) -> Vec<(String, f64)> {
    let code_spans: Vec<(usize, usize)> = CODE_SPAN_RE.find_iter(question).map(|m| (m.start(), m.end())).collect();
    let in_code = |pos: usize| code_spans.iter().any(|&(a, b)| a <= pos && pos < b);

    let mut occurrences: IndexMap<String, Vec<usize>> = IndexMap::new();
    for m in ANCHOR_IDENT_RE.find_iter(question) {
        occurrences.entry(m.as_str().to_string()).or_default().push(m.start());
    }
    let order: Vec<String> = occurrences.keys().cloned().collect();

    let mut best: IndexMap<String, f64> = IndexMap::new();
    let mut def_counts: HashMap<String, usize> = HashMap::new();
    for s in &order {
        // Python: `if s.lower() in _STOP: continue`
        if STOP.contains(py_lower(s).as_str()) {
            continue;
        }
        let files = match corpus.def_index.get(s) {
            Some(f) if f.len() <= 3 => f,
            _ => continue,
        };
        let occ = occurrences.get(s).unwrap();
        let strength_base = if occ.iter().any(|&p| in_code(p)) { 2.0 } else { 1.0 };
        let strength = if *s != py_lower(s) || s.contains('_') {
            strength_base + 0.5
        } else {
            strength_base
        };
        for f in files {
            let cur = best.get(f).copied().unwrap_or(-1.0);
            if strength > cur {
                best.insert(f.clone(), strength);
                def_counts.insert(f.clone(), files.len());
            }
        }
    }
    let mut result: Vec<(String, f64)> = best.into_iter().collect();
    // sorted(key=(strength, -def_count), reverse=True); stable sort, ties
    // broken by `best`'s insertion order (preserved since `result` is built
    // by iterating `best` in insertion order).
    result.sort_by(|a, b| {
        let ka = (a.1, -(*def_counts.get(&a.0).unwrap() as i64));
        let kb = (b.1, -(*def_counts.get(&b.0).unwrap() as i64));
        // f64::total_cmp rather than partial_cmp().unwrap(): never panics
        // regardless of NaN/inf, and agrees with partial_cmp on every
        // finite, non-NaN input (all `strength` values here are one of
        // 1.0/1.5/2.0/2.5, so this is a pure hardening, not a ranking
        // change). See `pack_regions`' pass-2 `marginal`-based sort, which
        // gets the same total_cmp hardening for the same reason: a caller
        // can pass an already-NaN score into either function (e.g. via a
        // drifted idf input upstream), and partial_cmp().unwrap() panics
        // the instant that NaN is compared against anything.
        kb.0.total_cmp(&ka.0).then_with(|| kb.1.cmp(&ka.1))
    });
    result
}

/// Best-effort recovery of WHICH rarity-gated definition symbol(s) (see
/// `extract_symbol_anchors` above) anchored each of `files` into the ranked
/// file list, for `pack_regions`' channel-aware packing: an anchor-selected
/// file's packed regions should include the anchored symbol's own
/// definition block, not just whatever region wins on generic term
/// density.
///
/// Deliberately a separate, independent pass over the question text rather
/// than a refactor of `extract_symbol_anchors` -- that function's return
/// value is parity-pinned. This helper may return MULTIPLE symbols per
/// file (in question-regex-match order, which `pack_regions` consumes
/// first-match-wins) and is never consumed by `select_files`, so nothing
/// here can affect the ranked file list. Applies the identical rarity gate
/// (<=3 defining files) so it only ever surfaces symbols that
/// `extract_symbol_anchors` itself would have considered.
pub fn anchor_def_symbols(
    question: &str,
    corpus: &Corpus,
    files: &HashSet<String>,
) -> IndexMap<String, Vec<String>> {
    let mut out: IndexMap<String, Vec<String>> = IndexMap::new();
    if files.is_empty() {
        return out;
    }
    for m in ANCHOR_IDENT_RE.find_iter(question) {
        let s = m.as_str();
        if STOP.contains(py_lower(s).as_str()) {
            continue;
        }
        let def_files = match corpus.def_index.get(s) {
            Some(f) if !f.is_empty() && f.len() <= 3 => f,
            _ => continue,
        };
        for f in def_files {
            if files.contains(f) {
                let entry = out.entry(f.clone()).or_default();
                if !entry.iter().any(|x| x == s) {
                    entry.push(s.to_string());
                }
            }
        }
    }
    out
}

// ---------------------------------------------------------------- import graph

static PY_FROM_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^\s*from\s+([\w.]+)\s+import\s+(\([^)]*\)|[^\n]+)").unwrap());
static PY_PLAIN_IMPORT_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?m)^\s*import\s+([\w., ]+)").unwrap());
static JS_IMPORT_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#"(?:from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)|import\s*\(\s*['"]([^'"]+)['"])"#).unwrap()
});
static RS_MOD_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?m)^\s*(?:pub\s+)?mod\s+(\w+)\s*;").unwrap());
static RS_USE_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^\s*(?:pub\s+)?use\s+(?:crate|super|self)::([\w:]+)").unwrap());
static GO_IMPORT_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r#""([\w./\-]+)""#).unwrap());

fn py_module_index(files: &[String]) -> HashMap<String, String> {
    let mut idx = HashMap::new();
    for rel in files {
        if !rel.ends_with(".py") {
            continue;
        }
        let mod_name = rel[..rel.len() - 3].replace('/', ".");
        idx.insert(mod_name.clone(), rel.clone());
        if let Some(stripped) = mod_name.strip_suffix(".__init__") {
            idx.insert(stripped.to_string(), rel.clone());
        }
    }
    idx
}

/// Undirected import graph. Adjacency sets use `BTreeSet` (sorted
/// iteration) as the deliberate, documented deterministic stand-in for
/// Python's raw `set[str]` (see PARITY_NOTES.md item 7: `edges[s]`'s
/// iteration order is the one genuinely hash-randomization-exposed spot in
/// the whole pipeline).
pub type EdgeMap = HashMap<String, BTreeSet<String>>;

/// The set of files that `rel`'s OWN text authors an import edge to
/// (pre-symmetrization) -- i.e. the per-file body of `build_import_graph`'s
/// main loop, factored out so `crate::cache`'s incremental-update path
/// (`update_import_graph_for_files`) can recompute a single changed file's
/// authored edges without re-parsing the whole corpus. Must stay exactly in
/// sync with `build_import_graph`'s loop body -- best-effort per language,
/// unresolved imports ignored.
fn file_import_targets(
    rel: &str,
    text: &str,
    pyidx: &HashMap<String, String>,
    fileset: &HashSet<&String>,
) -> HashSet<String> {
    let mut targets: HashSet<String> = HashSet::new();

    let resolve_py_module = |module: &str| -> String {
        if !module.starts_with('.') {
            return module.to_string();
        }
        let level = module.len() - module.trim_start_matches('.').len();
        let rest = module.trim_start_matches('.');
        let parent = py_parent(rel);
        let mut pkg_parts: Vec<&str> = if parent == "." { Vec::new() } else { parent.split('/').collect() };
        if level > 1 {
            let keep = pkg_parts.len().saturating_sub(level - 1);
            pkg_parts.truncate(keep);
        }
        let mut all: Vec<&str> = pkg_parts;
        if !rest.is_empty() {
            all.extend(rest.split('.'));
        }
        all.join(".")
    };

    let add_module = |targets: &mut HashSet<String>, module: &str| {
        let parts: Vec<&str> = module.split('.').filter(|p| !p.is_empty()).collect();
        for i in (1..=parts.len()).rev() {
            let key = parts[..i].join(".");
            if let Some(hit) = pyidx.get(&key) {
                if hit != rel {
                    targets.insert(hit.clone());
                }
                return;
            }
        }
    };

    if rel.ends_with(".py") {
        for cap in PY_FROM_RE.captures_iter(text) {
            let module_spec = cap.get(1).unwrap().as_str();
            let module = resolve_py_module(module_spec);
            add_module(&mut targets, &module);
            let names_blob = cap.get(2).unwrap().as_str();
            let trimmed = names_blob.trim_matches(|c| c == '(' || c == ')');
            for name_raw in trimmed.replace('\n', " ").split(',') {
                let name = name_raw.trim();
                let name = name.split(" as ").next().unwrap_or(name).trim();
                let name = name.trim_matches(|c: char| c == '*' || c == '#' || c == ' ' || c == '\t');
                if !name.is_empty() && !name.contains('.') {
                    let sub_key = format!("{module}.{name}");
                    if let Some(sub) = pyidx.get(&sub_key) {
                        if sub != rel {
                            targets.insert(sub.clone());
                        }
                    }
                }
            }
        }
        for cap in PY_PLAIN_IMPORT_RE.captures_iter(text) {
            let spec_list = cap.get(1).unwrap().as_str();
            for spec in spec_list.split(',') {
                let module = spec.trim().split(" as ").next().unwrap_or("").trim();
                if !module.is_empty() {
                    add_module(&mut targets, module);
                }
            }
        }
    } else if rel.ends_with(".js") || rel.ends_with(".ts") || rel.ends_with(".jsx") || rel.ends_with(".tsx") {
        let base = py_parent(rel);
        for cap in JS_IMPORT_RE.captures_iter(text) {
            let spec = (1..=3).find_map(|i| cap.get(i)).map(|m| m.as_str()).unwrap_or("");
            if !spec.starts_with('.') {
                continue;
            }
            let cand = normpath_join(base, spec);
            let suffixes = ["", ".js", ".ts", ".jsx", ".tsx", "/index.js", "/index.ts"];
            for suffix in suffixes {
                let candidate = format!("{cand}{suffix}");
                if fileset.contains(&candidate) {
                    if candidate != rel {
                        targets.insert(candidate);
                    }
                    break;
                }
            }
        }
    } else if rel.ends_with(".rs") {
        let base = py_parent(rel);
        for cap in RS_MOD_RE.captures_iter(text) {
            let name = cap.get(1).unwrap().as_str();
            for cand in [path_join_simple(base, &format!("{name}.rs")), path_join_simple(base, &format!("{name}/mod.rs"))] {
                if fileset.contains(&cand) && cand != rel {
                    targets.insert(cand);
                }
            }
        }
        for cap in RS_USE_RE.captures_iter(text) {
            let head = cap.get(1).unwrap().as_str().split("::").next().unwrap_or("");
            for cand in [
                path_join_simple(base, &format!("{head}.rs")),
                path_join_simple(base, &format!("{head}/mod.rs")),
                format!("src/{head}.rs"),
                format!("src/{head}/mod.rs"),
            ] {
                if fileset.contains(&cand) && cand != rel {
                    targets.insert(cand);
                }
            }
        }
    } else if rel.ends_with(".go") {
        for cap in GO_IMPORT_RE.captures_iter(text) {
            let pkg = cap.get(1).unwrap().as_str();
            let tail = pkg.rsplit('/').next().unwrap_or(pkg);
            for other in fileset {
                if other.as_str() != rel && other.ends_with(".go") && py_parent_name(other) == tail {
                    targets.insert((*other).clone());
                }
            }
        }
    }
    targets
}

pub fn build_import_graph(corpus: &Corpus) -> EdgeMap {
    let mut edges: EdgeMap = HashMap::new();
    let pyidx = py_module_index(&corpus.files);
    let fileset: HashSet<&String> = corpus.files.iter().collect();

    for rel in &corpus.files {
        let text = &corpus.text[rel];
        let targets = file_import_targets(rel, text, &pyidx, &fileset);
        for t in targets {
            edges.entry(rel.clone()).or_default().insert(t.clone());
            edges.entry(t).or_default().insert(rel.clone());
        }
    }
    edges
}

/// Incrementally patch `edges` (mutated in place) for a batch of files whose
/// content changed but whose relpath set is unchanged -- see
/// `crate::cache`'s incremental-update path. `old_text` is `{rel: text}`
/// holding each changed file's PRE-edit text; `corpus.text[rel]` must
/// already hold the POST-edit text for every rel in `old_text` by the time
/// this is called (see `Corpus::update_files`, which must run first).
///
/// Recomputes each changed file's own authored-edge set
/// (`file_import_targets`) from both its old and new text. An edge
/// `(rel, t)` is removed only if `rel` was its SOLE author -- `t`'s own
/// current text, re-checked on demand, doesn't independently author it
/// back -- so an edge created by an UNCHANGED file Y importing a changed
/// file `rel` is left untouched even though `rel`'s content changed, since
/// Y's text (the sole source of that edge) didn't.
pub fn update_import_graph_for_files(corpus: &Corpus, edges: &mut EdgeMap, old_text: &HashMap<String, String>) {
    let fileset: HashSet<&String> = corpus.files.iter().collect();
    let pyidx = py_module_index(&corpus.files);

    let authored = |rel: &str, text: &str| -> HashSet<String> { file_import_targets(rel, text, &pyidx, &fileset) };

    let mut new_authored: HashMap<String, HashSet<String>> = HashMap::new();
    let mut old_authored: HashMap<String, HashSet<String>> = HashMap::new();
    for rel in old_text.keys() {
        if let Some(text) = corpus.text.get(rel) {
            new_authored.insert(rel.clone(), authored(rel, text));
        }
    }
    for (rel, text) in old_text {
        old_authored.insert(rel.clone(), authored(rel, text));
    }

    let other_authors = |t: &str, rel: &str| -> bool {
        if old_text.contains_key(t) {
            new_authored.get(t).map(|s| s.contains(rel)).unwrap_or(false)
        } else {
            match corpus.text.get(t) {
                Some(text) => authored(t, text).contains(rel),
                None => false,
            }
        }
    };

    let mut touched: HashSet<String> = old_text.keys().cloned().collect();
    for rel in old_text.keys() {
        let empty = HashSet::new();
        let old_set = old_authored.get(rel).unwrap_or(&empty);
        let new_set = new_authored.get(rel).unwrap_or(&empty);
        let removed: Vec<String> = old_set.difference(new_set).cloned().collect();
        let added: Vec<String> = new_set.difference(old_set).cloned().collect();
        touched.extend(removed.iter().cloned());
        touched.extend(added.iter().cloned());
        for t in &removed {
            if !other_authors(t, rel) {
                if let Some(s) = edges.get_mut(rel) {
                    s.remove(t);
                }
                if let Some(s) = edges.get_mut(t) {
                    s.remove(rel);
                }
            }
        }
        for t in &added {
            edges.entry(rel.clone()).or_default().insert(t.clone());
            edges.entry(t.clone()).or_default().insert(rel.clone());
        }
    }

    for k in &touched {
        if edges.get(k).map(|s| s.is_empty()).unwrap_or(false) {
            edges.remove(k);
        }
    }
}

/// Random walk with restart -- present for structural parity with
/// lanes2.py's `personalized_pagerank`, but note it is DEAD CODE relative
/// to the actual CLI/driver wiring: `select_files(use_ppr=True)` never
/// calls it (its own "structural expansion" block reimplements a different
/// additive scheme directly). Kept for completeness only, never invoked.
#[allow(dead_code)]
pub fn personalized_pagerank(
    seeds: &IndexMap<String, f64>,
    edges: &EdgeMap,
    same_dir: &HashMap<String, Vec<String>>,
    alpha: f64,
    iters: usize,
    same_dir_weight: f64,
) -> IndexMap<String, f64> {
    let total: f64 = seeds.values().sum();
    if total <= 0.0 {
        return IndexMap::new();
    }
    let restart: IndexMap<String, f64> = seeds.iter().map(|(k, v)| (k.clone(), v / total)).collect();
    let mut rank: IndexMap<String, f64> = restart.clone();
    for _ in 0..iters {
        let mut nxt: IndexMap<String, f64> = IndexMap::new();
        for (node, &mass) in &rank {
            if mass <= 1e-12 {
                continue;
            }
            let empty_set = BTreeSet::new();
            let nbrs = edges.get(node).unwrap_or(&empty_set);
            let empty_vec = Vec::new();
            let dir_nbrs = same_dir.get(py_parent(node)).unwrap_or(&empty_vec);
            let mut weights: Vec<(String, f64)> = nbrs.iter().map(|n| (n.clone(), 1.0)).collect();
            for n in dir_nbrs {
                if n != node && !nbrs.contains(n) {
                    weights.push((n.clone(), same_dir_weight));
                }
            }
            let wsum: f64 = weights.iter().map(|(_, w)| w).sum();
            if wsum <= 0.0 {
                *nxt.entry(node.clone()).or_insert(0.0) += (1.0 - alpha) * mass;
            } else {
                for (n, w) in weights {
                    *nxt.entry(n).or_insert(0.0) += (1.0 - alpha) * mass * (w / wsum);
                }
            }
        }
        for (k, v) in &restart {
            *nxt.entry(k.clone()).or_insert(0.0) += alpha * v;
        }
        rank = nxt;
    }
    rank
}

// ---------------------------------------------------------------- selection

#[derive(Debug, Default, Clone, serde::Serialize)]
pub struct Explain {
    pub lex_picks: Vec<String>,
    pub sources: Vec<String>,
    pub pool: Vec<(String, f64, f64)>,
    pub additions: Vec<String>,
    pub cochange_additions: Vec<String>,
    pub msg_additions: Vec<String>,
    pub anchor_promotions: Vec<(String, f64, String, String)>,
    pub testbridge: Vec<(String, String, String)>,
    pub docsbridge: Vec<(String, String, i64)>,
    /// Raw (pre-normalization) top pooled BM25F candidate score for this
    /// query -- i.e. `max(corpus.bm25(terms).values())`, computed before
    /// `normalize()` divides every score down to a [0,1] range and before
    /// `pack_regions` does any budget-driven packing. Unlike the
    /// normalized/packed scores exposed elsewhere, this is comparable
    /// query-to-query and corpus-to-corpus, which is exactly what makes it
    /// usable as a low-confidence calibration signal (see `main.rs`'s
    /// `low_confidence` gate): a genuinely weak/coincidental match still
    /// normalizes its best candidate to 1.0, but its raw top score stays
    /// small. Zero (the `Default` value) in the true no-match case, where
    /// `select_files` returns `Explain::default()` before this field would
    /// otherwise be set.
    pub top_score: f64,
    /// E20 LexBoost diagnostics: top files by smoothed score as
    /// `(file, smoothed, direct, neighbor_mean, is_hub)`. Empty (the
    /// default) whenever smoothing is off -- populated only under
    /// `--lexboost`, for the experiment harness's flip anatomy.
    pub lexboost_top: Vec<(String, f64, f64, f64, bool)>,
}

fn normalize(scores: &IndexMap<String, f64>) -> IndexMap<String, f64> {
    if scores.is_empty() {
        return IndexMap::new();
    }
    let mx = scores.values().cloned().fold(f64::MIN, f64::max);
    if mx > 0.0 {
        scores.iter().map(|(k, v)| (k.clone(), v / mx)).collect()
    } else {
        scores.clone()
    }
}

/// Python `round()` (banker's rounding / round-half-to-even), used only in
/// Explain diagnostics.
fn py_round(x: f64, ndigits: i32) -> f64 {
    let factor = 10f64.powi(ndigits);
    let scaled = x * factor;
    let floor = scaled.floor();
    let diff = scaled - floor;
    let rounded = if (diff - 0.5).abs() < 1e-9 {
        if (floor as i64) % 2 == 0 {
            floor
        } else {
            floor + 1.0
        }
    } else {
        scaled.round()
    };
    rounded / factor
}

fn apply_anchor_promotions(
    out: Vec<String>,
    anchors: Option<&[(String, f64)]>,
) -> (Vec<String>, Vec<(String, f64, String, String)>) {
    let anchors = match anchors {
        Some(a) if !a.is_empty() => a,
        _ => return (out, Vec::new()),
    };
    let mut promotions: Vec<(String, f64, String, String)> = Vec::new();
    let mut out = out;

    let mut head_files: Vec<String> = Vec::new();
    let mut to_remove: HashSet<String> = HashSet::new();
    for (f, strength) in anchors {
        if *strength < 2.0 || head_files.len() >= 2 || head_files.contains(f) {
            continue;
        }
        if let Some(idx) = out.iter().position(|x| x == f) {
            if idx >= 10 {
                head_files.push(f.clone());
                to_remove.insert(f.clone());
                promotions.push((f.clone(), *strength, "move".into(), "head".into()));
            }
        } else {
            head_files.push(f.clone());
            promotions.push((f.clone(), *strength, "insert".into(), "head".into()));
        }
    }
    if !head_files.is_empty() {
        let remaining: Vec<String> = out.into_iter().filter(|f| !to_remove.contains(f)).collect();
        let split = remaining.len().min(7);
        let mut new_out = remaining[..split].to_vec();
        new_out.extend(head_files.iter().cloned());
        new_out.extend(remaining[split..].to_vec());
        out = new_out;
    }

    let mut tail_files: Vec<String> = Vec::new();
    for (f, strength) in anchors {
        if *strength >= 2.0 || tail_files.len() >= 2 || tail_files.contains(f) || head_files.contains(f) {
            continue;
        }
        if !out.contains(f) {
            tail_files.push(f.clone());
            promotions.push((f.clone(), *strength, "insert".into(), "tail".into()));
        }
    }
    for f in &tail_files {
        let pos = out.len().min(12);
        out.insert(pos, f.clone());
    }

    if head_files.is_empty() && tail_files.is_empty() {
        return (out, Vec::new());
    }
    (out, promotions)
}

const TESTBRIDGE_EXTS: &[&str] = &[".py", ".go", ".rs", ".js", ".ts"];

fn apply_testbridge_promotions(
    out: Vec<String>,
    corpus: &Corpus,
    bm: &IndexMap<String, f64>,
    edges: &EdgeMap,
) -> (Vec<String>, Vec<(String, String, String)>) {
    let testlike: Vec<String> = corpus
        .files
        .iter()
        .filter(|f| TESTLIKE_RE.is_match(f) && TESTBRIDGE_EXTS.contains(&suffix_of(f)))
        .cloned()
        .collect();
    let testlike_set: HashSet<String> = testlike.iter().cloned().collect();

    let mut ranked_tests: Vec<(String, f64)> = testlike.iter().map(|f| (f.clone(), bm.get(f).copied().unwrap_or(0.0))).collect();
    ranked_tests.sort_by(|a, b| b.1.total_cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    let top_tests: Vec<(String, f64)> = ranked_tests.into_iter().filter(|(_, s)| *s > 0.0).take(3).collect();
    if top_tests.is_empty() {
        return (out, Vec::new());
    }
    let top_score = top_tests[0].1;
    if top_score <= 0.0 {
        return (out, Vec::new());
    }

    let mut candidates: IndexMap<String, (f64, String)> = IndexMap::new();
    let empty = BTreeSet::new();
    for (test, tscore) in &top_tests {
        for nbr in edges.get(test).unwrap_or(&empty) {
            if impl_prior(nbr) != 1.0 {
                continue;
            }
            let strength = tscore / top_score;
            let replace = match candidates.get(nbr) {
                None => true,
                Some((cur, _)) => strength > *cur,
            };
            if replace {
                candidates.insert(nbr.clone(), (strength, test.clone()));
            }
        }
    }

    let specificity = |f: &str| -> f64 {
        let strength = candidates.get(f).unwrap().0;
        let n_test_importers = edges
            .get(f)
            .map(|s| s.iter().filter(|x| testlike_set.contains(x.as_str())).count())
            .unwrap_or(0);
        strength / (2.0 + n_test_importers as f64).ln()
    };

    let mut tail_pool: Vec<String> = candidates.keys().cloned().collect();
    tail_pool.sort_by(|a, b| specificity(b).total_cmp(&specificity(a)).then_with(|| a.cmp(b)));

    let mut records: Vec<(String, String, String)> = Vec::new();
    let mut tail_files: Vec<String> = Vec::new();
    let mut out = out;
    for f in &tail_pool {
        if tail_files.len() >= 3 {
            break;
        }
        if out.contains(f) {
            continue;
        }
        tail_files.push(f.clone());
        records.push((f.clone(), "tail".into(), candidates.get(f).unwrap().1.clone()));
    }
    for f in &tail_files {
        let pos = out.len().min(14);
        out.insert(pos, f.clone());
    }

    (out, records)
}

static DOTTED_PATH_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\b[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*){2,}\b").unwrap());
static SPHINX_DIRECTIVE_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?:automodule|currentmodule|module|autoclass|autofunction)::\s*([\w.]+)").unwrap());

fn resolve_py_dotted(dotted: &str, pyidx: &HashMap<String, String>) -> Option<String> {
    let parts: Vec<&str> = dotted.split('.').filter(|p| !p.is_empty()).collect();
    for i in (1..=parts.len()).rev() {
        let key = parts[..i].join(".");
        if let Some(hit) = pyidx.get(&key) {
            return Some(hit.clone());
        }
    }
    None
}

fn apply_docsbridge_promotions(
    out: Vec<String>,
    corpus: &Corpus,
    terms: &[String],
) -> (Vec<String>, Vec<(String, String, i64)>) {
    if corpus.docs_tf.is_empty() {
        return (out, Vec::new());
    }
    let doc_scores = corpus.docs_bm25(terms);
    if doc_scores.is_empty() {
        return (out, Vec::new());
    }
    let mut ranked_pages: Vec<(String, f64)> = doc_scores.into_iter().collect();
    ranked_pages.sort_by(|a, b| b.1.total_cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    let top_pages: Vec<(String, f64)> = ranked_pages.into_iter().filter(|(_, s)| *s > 0.0).take(3).collect();
    if top_pages.is_empty() {
        return (out, Vec::new());
    }

    let pyidx = py_module_index(&corpus.files);
    let mut candidates: IndexMap<String, (i64, i64)> = IndexMap::new(); // (n_pages, best_rank)
    for (rank, (page, _score)) in top_pages.iter().enumerate() {
        let text = &corpus.docs_text[page];
        let mut refs: HashSet<String> = HashSet::new();
        for m in DOTTED_PATH_RE.find_iter(text) {
            refs.insert(m.as_str().to_string());
        }
        for cap in SPHINX_DIRECTIVE_RE.captures_iter(text) {
            refs.insert(cap.get(1).unwrap().as_str().to_string());
        }
        let mut resolved: HashSet<String> = HashSet::new();
        for r in &refs {
            if let Some(hit) = resolve_py_dotted(r, &pyidx) {
                if impl_prior(&hit) == 1.0 {
                    resolved.insert(hit);
                }
            }
        }
        for f in resolved {
            let entry = candidates.entry(f).or_insert((0, rank as i64));
            entry.0 += 1;
            entry.1 = entry.1.min(rank as i64);
        }
    }

    let mut tail_pool: Vec<String> = candidates.keys().cloned().collect();
    tail_pool.sort_by(|a, b| {
        let ca = candidates.get(a).unwrap();
        let cb = candidates.get(b).unwrap();
        cb.0.cmp(&ca.0).then(ca.1.cmp(&cb.1)).then(a.cmp(b))
    });

    let mut records: Vec<(String, String, i64)> = Vec::new();
    let mut tail_files: Vec<String> = Vec::new();
    let mut out = out;
    for f in &tail_pool {
        if tail_files.len() >= 2 {
            break;
        }
        if out.contains(f) {
            continue;
        }
        tail_files.push(f.clone());
        records.push((f.clone(), "tail".into(), candidates.get(f).unwrap().0));
    }
    for f in &tail_files {
        let pos = out.len().min(16);
        out.insert(pos, f.clone());
    }

    (out, records)
}

pub struct SelectParams<'a> {
    pub k_lex: usize,
    pub floor_ratio: f64,
    pub cochange: Option<&'a IndexMap<String, IndexMap<String, i64>>>,
    pub cochange_strong: i64,
    pub anchors: Option<&'a [(String, f64)]>,
    pub use_testbridge: bool,
    pub use_docsbridge: bool,
    /// E11 trace-frame FILE channel: repo-relative files resolved from
    /// traceback frames, best rank first (see `RoutedQuery::trace_files`).
    /// None (default) = channel absent, byte-identical to pre-E11 ranking.
    pub trace_files: Option<&'a [String]>,
    /// E11 conditional test/example-path downweight (Kim & Lee): multiplies
    /// the fused file score of TESTLIKE_RE-matching paths. 1.0 (default) =
    /// off; the caller sets it < 1.0 ONLY for fence-dominant queries.
    pub test_penalty: f64,
    /// E20 LexBoost lambda: blend weight on the DIRECT score in
    /// `S' = lambda*S + (1-lambda)*prior*mean(neighbors)`. 0.0 (default) =
    /// off, byte-identical to the pre-E20 engine; the paper's default is
    /// 0.7. Only meaningful together with `lexboost_nbrs`.
    pub lexboost: f64,
    /// E20 LexBoost neighbor lists (import-graph or BM25-kNN; see
    /// `lexboost_import_neighbors` / `lexboost_knn_neighbors`). None
    /// (default) = smoothing off regardless of `lexboost`.
    pub lexboost_nbrs: Option<&'a NeighborMap>,
    /// E20 hub-guard set (`lexboost_hubs`): files excluded from RECEIVING
    /// the neighbor term. None = no hub exclusion.
    pub lexboost_hubs: Option<&'a HashSet<String>>,
}

impl<'a> Default for SelectParams<'a> {
    fn default() -> Self {
        SelectParams {
            k_lex: 10,
            floor_ratio: 0.05,
            cochange: None,
            cochange_strong: 5,
            anchors: None,
            use_testbridge: false,
            use_docsbridge: false,
            trace_files: None,
            test_penalty: 1.0,
            lexboost: 0.0,
            lexboost_nbrs: None,
            lexboost_hubs: None,
        }
    }
}

/// Return candidate files: top BM25F picks, UNIONed with structural-
/// expansion additions when `use_ppr` is true. See lanes2.py's
/// `select_files` docstring for the full design rationale -- this is a
/// direct translation; the one deliberate behavioral choice (not a
/// deviation, a documented tie-break for an underlying Python
/// nondeterminism) is noted at the `edges.get(s)` call below. See
/// PARITY_NOTES.md item 7.
pub fn select_files(
    corpus: &Corpus,
    terms: &[String],
    use_ppr: bool,
    params: &SelectParams,
) -> (Vec<String>, IndexMap<String, f64>, Explain) {
    let bm = corpus.bm25(terms);
    if bm.is_empty() {
        return (Vec::new(), IndexMap::new(), Explain::default());
    }
    let top_score = bm.values().cloned().fold(0.0_f64, f64::max);
    let mut bm_n = normalize(&bm);

    // E20 LexBoost neighbor smoothing -- applied to the normalized fused
    // score BEFORE the E11 trace boost (smoothing reshapes the lexical
    // channel itself; the trace boost is an additive channel on top of it).
    // Flag-gated: lexboost == 0.0 or no neighbor map = this block is dead
    // code and bm_n is byte-identical to the pre-E20 engine.
    let mut lexboost_top: Vec<(String, f64, f64, f64, bool)> = Vec::new();
    if params.lexboost > 0.0 {
        if let Some(nbrs) = params.lexboost_nbrs {
            static NO_HUBS: LazyLock<HashSet<String>> = LazyLock::new(HashSet::new);
            let hubs = params.lexboost_hubs.unwrap_or(&NO_HUBS);
            let (sm, diag) = apply_lexboost(&bm_n, corpus, nbrs, hubs, params.lexboost);
            bm_n = sm;
            lexboost_top = diag;
        }
    }

    // E11 trace-frame FILE boost (BRTracer): rank-decayed additive channel
    // on the NORMALIZED lexical score -- 1/rank for the top-10 frame files
    // (rank 1 = raise site), 0.1 deeper, 0.1 spillover to files the frame
    // files' own text imports (`file_import_targets`, directed). A frame
    // file absent from the BM25 pool is INSERTED (score = boost alone):
    // this is the one mechanism here that can rescue files with zero
    // initial lexical presence. Iteration/insertion order is canonical
    // (frame rank order, then sorted spillover set), and each file receives
    // exactly one addition, so no float-summation order ambiguity exists.
    if let Some(tfs) = params.trace_files {
        if !tfs.is_empty() {
            let pyidx = py_module_index(&corpus.files);
            let fileset: HashSet<&String> = corpus.files.iter().collect();
            let direct: HashSet<&str> = tfs.iter().map(|s| s.as_str()).collect();
            let mut spill: BTreeSet<String> = BTreeSet::new();
            for f in tfs.iter() {
                if let Some(text) = corpus.text.get(f) {
                    for t in file_import_targets(f, text, &pyidx, &fileset) {
                        if !direct.contains(t.as_str()) {
                            spill.insert(t);
                        }
                    }
                }
            }
            for (i, f) in tfs.iter().enumerate() {
                let b = if i < 10 { 1.0 / (i as f64 + 1.0) } else { 0.1 };
                *bm_n.entry(f.clone()).or_insert(0.0) += b;
            }
            for f in spill {
                *bm_n.entry(f).or_insert(0.0) += 0.1;
            }
        }
    }

    // E11 conditional test/example-path downweight (Kim & Lee): fires only
    // when the caller set test_penalty < 1.0 (fence-dominant queries).
    // Directly trace-boosted files are exempt -- the trace channel names
    // them explicitly, which outranks the path-shape prior.
    if params.test_penalty < 1.0 {
        let direct: HashSet<&str> =
            params.trace_files.map(|tfs| tfs.iter().map(|s| s.as_str()).collect()).unwrap_or_default();
        for (f, v) in bm_n.iter_mut() {
            if TESTLIKE_RE.is_match(f) && !direct.contains(f.as_str()) {
                *v *= params.test_penalty;
            }
        }
    }

    let mut ranked: Vec<(String, f64)> = bm_n.iter().map(|(k, v)| (k.clone(), *v)).collect();
    ranked.sort_by(|a, b| b.1.total_cmp(&a.1));
    let best = ranked[0].1;
    let lex_picks: Vec<String> = ranked
        .iter()
        .take(params.k_lex)
        .enumerate()
        .filter(|(i, (_, s))| *i < 3 || *s >= params.floor_ratio * best)
        .map(|(_, (f, _))| f.clone())
        .collect();

    let mut scores: IndexMap<String, f64> = bm_n.clone();

    if !use_ppr {
        let (lex_out, promotions) = apply_anchor_promotions(lex_picks.clone(), params.anchors);
        let mut lex_out = lex_out;
        let mut tb_records = Vec::new();
        if params.use_testbridge {
            let edges = build_import_graph(corpus);
            let (o, r) = apply_testbridge_promotions(lex_out, corpus, &bm, &edges);
            lex_out = o;
            tb_records = r;
        }
        let mut db_records = Vec::new();
        if params.use_docsbridge {
            let (o, r) = apply_docsbridge_promotions(lex_out, corpus, terms);
            lex_out = o;
            db_records = r;
        }
        let explain = Explain {
            lex_picks,
            anchor_promotions: promotions,
            testbridge: tb_records,
            docsbridge: db_records,
            top_score,
            lexboost_top,
            ..Default::default()
        };
        return (lex_out, scores, explain);
    }

    // --- structural expansion
    let edges = build_import_graph(corpus);
    let mut same_dir: HashMap<String, Vec<String>> = HashMap::new();
    for rel in &corpus.files {
        same_dir.entry(py_parent(rel).to_string()).or_default().push(rel.clone());
    }

    let sources: Vec<String> = lex_picks.iter().take(6).cloned().collect();

    let qset: HashSet<String> = terms.iter().cloned().collect();
    let mut fb_terms: HashSet<String> = HashSet::new();
    let impl_sources: Vec<&String> = sources.iter().filter(|f| impl_prior(f) == 1.0).take(3).collect();
    for s in impl_sources {
        let tf_map = corpus.tf.get(s);
        if let Some(tf_map) = tf_map {
            let mut weighted: Vec<(String, f64)> = tf_map
                .iter()
                .filter(|(t, _)| !qset.contains(t.as_str()))
                .map(|(t, &tfv)| {
                    let dfv = *corpus.df.get(t).unwrap_or(&1) as f64;
                    let w = tfv as f64 * (1.0 + corpus.n_docs as f64 / (1.0 + dfv)).ln();
                    (t.clone(), w)
                })
                .collect();
            weighted.sort_by(|a, b| b.1.total_cmp(&a.1));
            for (t, _) in weighted.into_iter().take(20) {
                fb_terms.insert(t);
            }
        }
    }
    let mut fb_sorted: Vec<String> = fb_terms.into_iter().collect();
    fb_sorted.sort();
    let bm_fb = if !fb_sorted.is_empty() { corpus.bm25(&fb_sorted) } else { IndexMap::new() };
    let fb_n = normalize(&bm_fb);

    let mut pool: IndexMap<String, f64> = IndexMap::new();
    let mut owner: HashMap<String, String> = HashMap::new();
    let mut import_nbrs: HashMap<String, Vec<String>> = HashMap::new();
    let mut cochange_origin: HashSet<String> = HashSet::new();
    let fileset: HashSet<&String> = corpus.files.iter().collect();
    let lex_picks_set: HashSet<&String> = lex_picks.iter().collect();

    for s in &sources {
        let w = bm_n.get(s).copied().unwrap_or(0.0);
        let mut imp: Vec<String> = Vec::new();
        let co_partners: Option<&IndexMap<String, i64>> = params.cochange.and_then(|c| c.get(s));

        let mut neighbors: Vec<String> = Vec::new();
        // NOTE (PARITY_NOTES.md item 7): `edges.get(s)` is a Python `set`
        // in the reference; CPython's default hash randomization makes its
        // iteration order (and thus tie-breaks fed by it, downstream) not
        // reproducibly deterministic even between two runs of the *Python*
        // reference. We use sorted (alphabetical) iteration here as the
        // canonical, deterministic choice -- `BTreeSet` already iterates
        // that way.
        if let Some(adj) = edges.get(s) {
            neighbors.extend(adj.iter().cloned());
        }
        if let Some(sd) = same_dir.get(py_parent(s)) {
            neighbors.extend(sd.iter().cloned());
        }
        if let Some(cop) = co_partners {
            for c in cop.keys() {
                if fileset.contains(c) && !neighbors.contains(c) {
                    neighbors.push(c.clone());
                }
            }
        }

        for c in &neighbors {
            if lex_picks_set.contains(c) || c == s || impl_prior(c) < 1.0 {
                continue;
            }
            let is_import_edge = edges.get(s).map(|adj| adj.contains(c)).unwrap_or(false);
            if is_import_edge {
                imp.push(c.clone());
            } else if let Some(cop) = co_partners {
                if cop.get(c).copied().unwrap_or(0) >= params.cochange_strong {
                    imp.push(c.clone());
                }
            }
            if let Some(cop) = co_partners {
                if cop.contains_key(c) {
                    cochange_origin.insert(c.clone());
                }
            }
            if w > pool.get(c).copied().unwrap_or(0.0) {
                pool.insert(c.clone(), w);
                owner.insert(c.clone(), s.clone());
            }
        }
        import_nbrs.insert(s.clone(), imp);
    }

    let add_score = |c: &str, pool: &IndexMap<String, f64>| -> f64 {
        (0.15 + bm_n.get(c).copied().unwrap_or(0.0) + 0.8 * fb_n.get(c).copied().unwrap_or(0.0))
            * (0.5 + 0.5 * pool.get(c).copied().unwrap_or(0.0))
    };

    let mut ranked_pool: Vec<String> = pool.keys().cloned().collect();
    ranked_pool.sort_by(|a, b| add_score(b, &pool).total_cmp(&add_score(a, &pool)));

    let mut additions: Vec<String> = Vec::new();
    if !ranked_pool.is_empty() {
        let pmax = add_score(&ranked_pool[0], &pool);
        let eligible: Vec<String> = ranked_pool.iter().filter(|c| add_score(c, &pool) >= 0.15 * pmax).cloned().collect();
        let eligible_set: HashSet<&String> = eligible.iter().collect();

        let n = corpus.files.len().max(1) as f64;
        let qpath: HashSet<String> = terms
            .iter()
            .filter(|t| {
                if t.chars().count() <= 3 {
                    return false;
                }
                let cnt = corpus.files.iter().filter(|f| corpus.ptoks.get(*f).map(|s| s.contains(t.as_str())).unwrap_or(false)).count();
                (cnt as f64) / n < 0.10
            })
            .cloned()
            .collect();

        let path_hits: Vec<String> = eligible
            .iter()
            .filter(|c| {
                corpus
                    .ptoks
                    .get(*c)
                    .map(|pt| pt.iter().any(|t| qpath.contains(t)))
                    .unwrap_or(false)
            })
            .cloned()
            .collect();
        let mut path_hits_sorted = path_hits.clone();
        path_hits_sorted.sort_by(|a, b| add_score(b, &pool).total_cmp(&add_score(a, &pool)));
        for c in path_hits_sorted.into_iter().take(6) {
            if !additions.contains(&c) {
                additions.push(c);
            }
        }

        // Guarantee 1: each source's best direct-import neighbor.
        for s in &sources {
            let imp: Vec<String> = import_nbrs
                .get(s)
                .map(|v| v.iter().filter(|c| eligible_set.contains(c)).cloned().collect())
                .unwrap_or_default();
            if !imp.is_empty() {
                let mut best_c = imp[0].clone();
                let mut best_score = add_score(&best_c, &pool);
                for c in &imp[1..] {
                    let sc = add_score(c, &pool);
                    if sc > best_score {
                        best_score = sc;
                        best_c = c.clone();
                    }
                }
                if !additions.contains(&best_c) {
                    additions.push(best_c);
                }
            }
        }

        // Guarantee 2: each source's best neighbor overall.
        let mut groups: IndexMap<String, Vec<String>> = IndexMap::new();
        for c in &eligible {
            groups.entry(owner.get(c).cloned().unwrap_or_default()).or_default().push(c.clone());
        }
        for s in &sources {
            if let Some(grp) = groups.get(s) {
                if let Some(first) = grp.first() {
                    if !additions.contains(first) {
                        additions.push(first.clone());
                    }
                }
            }
        }
        for c in &eligible {
            if additions.len() >= 16 {
                break;
            }
            if !additions.contains(c) {
                additions.push(c.clone());
            }
        }
    }

    // History top-up
    let mut msg_additions: Vec<String> = Vec::new();
    if !corpus.msg_tf.is_empty() {
        let msg_scores = corpus.msg_bm25(terms);
        if !msg_scores.is_empty() {
            let msg_max = msg_scores.values().cloned().fold(f64::MIN, f64::max);
            if msg_max > 0.0 {
                let already: HashSet<String> = lex_picks.iter().chain(additions.iter()).cloned().collect();
                let mut msg_ranked: Vec<(String, f64)> = msg_scores.into_iter().collect();
                msg_ranked.sort_by(|a, b| b.1.total_cmp(&a.1));
                for (f, s) in msg_ranked {
                    if msg_additions.len() >= 3 {
                        break;
                    }
                    if already.contains(&f) || s < 0.35 * msg_max || impl_prior(&f) != 1.0 {
                        continue;
                    }
                    msg_additions.push(f);
                }
            }
        }
        additions.extend(msg_additions.iter().cloned());
    }

    let mut out: Vec<String> = lex_picks.clone();
    out.extend(additions.iter().cloned());
    for f in &additions {
        let v = 0.3 + 0.5 * fb_n.get(f).copied().unwrap_or(0.0);
        let cur = scores.get(f).copied().unwrap_or(0.0);
        scores.insert(f.clone(), cur.max(v));
    }

    let (out2, anchor_promotions) = apply_anchor_promotions(out, params.anchors);
    let mut out = out2;
    let mut tb_records = Vec::new();
    if params.use_testbridge {
        let (o, r) = apply_testbridge_promotions(out, corpus, &bm, &edges);
        out = o;
        tb_records = r;
    }
    let mut db_records = Vec::new();
    if params.use_docsbridge {
        let (o, r) = apply_docsbridge_promotions(out, corpus, terms);
        out = o;
        db_records = r;
    }

    let cochange_additions: Vec<String> = additions.iter().filter(|c| cochange_origin.contains(*c)).cloned().collect();
    let pool_explain: Vec<(String, f64, f64)> = ranked_pool
        .iter()
        .map(|c| (c.clone(), py_round(add_score(c, &pool), 4), py_round(pool.get(c).copied().unwrap_or(0.0), 2)))
        .collect();

    let explain = Explain {
        sources,
        lex_picks,
        pool: pool_explain,
        additions,
        cochange_additions,
        msg_additions,
        anchor_promotions,
        testbridge: tb_records,
        docsbridge: db_records,
        top_score,
        lexboost_top,
    };

    (out, scores, explain)
}

// ---------------------------------------------------------------- region packing

// v2: matched per-line via `.captures()` (not `.find_iter()` over the whole
// text), so no `(?m)` flag is needed -- mirrors lanes2.py's
// `_PY_BLOCK_RE.match(ln)` per-line loop.
static PY_BLOCK_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^([ \t]*)(async def |def |class |@)").unwrap());

/// Signature-plus-body block spans (1-indexed, inclusive), split at EVERY
/// def/class/decorator header regardless of indentation -- not just
/// column-0, as a prior version did. Column-0-only splitting made an entire
/// class (every one of its methods) a single multi-hundred-line block, so
/// `pack_regions`' per-file token cap trimmed from that block's START and
/// any gold hunk past the class's first method was silently dropped.
///
/// Blocks now nest: a class's own span still covers its header through its
/// last method (so "class X: <giant body>" remains a valid whole-class
/// candidate for `pack_regions`' greedy packing, same as before), but each
/// direct child header (a method, or a nested function) ALSO gets its own,
/// tighter span from its header line to the next sibling header at the
/// same-or-lower indentation. This hands `pack_regions` candidates at
/// multiple granularities, so a hit deep inside a large class can be
/// represented by its own small method-level block instead of only ever
/// appearing as an early fragment of the whole class.
fn python_blocks(text: &str) -> Vec<(usize, usize)> {
    let lines = py_splitlines(text);
    let n = lines.len();
    // (0-indexed line, indent width)
    let mut headers: Vec<(usize, usize)> = Vec::new();
    for (i, ln) in lines.iter().enumerate() {
        if let Some(caps) = PY_BLOCK_RE.captures(ln) {
            let indent = caps.get(1).unwrap().as_str().chars().count();
            headers.push((i, indent));
        }
    }
    if headers.is_empty() {
        return vec![(1, n)];
    }

    let mut spans: Vec<(usize, usize)> = Vec::new();
    if headers[0].0 > 0 {
        spans.push((1, headers[0].0)); // leading preamble (imports, module docstring)
    }

    for (idx, &(i, indent)) in headers.iter().enumerate() {
        if lines[i].trim_start().starts_with('@') {
            continue; // standalone decorator: folded into the following def/class's span below
        }
        let mut start = i;
        let mut k = i as isize - 1;
        while k >= 0 && lines[k as usize].trim_start().starts_with('@') {
            start = k as usize;
            k -= 1;
        }
        let mut end = n;
        for &(j, ind2) in &headers[idx + 1..] {
            if ind2 <= indent {
                end = j;
                break;
            }
        }
        spans.push((start + 1, end));
    }
    spans.into_iter().filter(|&(a, b)| b >= a).collect()
}

static PY_DEF_LINE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^[ \t]*(?:async def|def|class)\s+(\w+)").unwrap());

/// 1-indexed line number of each class/def header's FIRST occurrence in
/// `text` (Python only, any indentation), keyed by symbol name -- used to
/// seat an anchor-channel symbol's own signature+body block among
/// `python_blocks`' spans (a span with that exact start line is that
/// symbol's def block). First occurrence wins: a symbol name can recur
/// (overload-by-decorator, reassignment) but `pack_regions` only needs A
/// definition site to anchor the forced block at, not every one.
fn py_def_line_numbers(text: &str) -> HashMap<String, usize> {
    let mut out: HashMap<String, usize> = HashMap::new();
    for (i, ln) in py_splitlines(text).iter().enumerate() {
        if let Some(caps) = PY_DEF_LINE_RE.captures(ln) {
            let name = caps.get(1).unwrap().as_str().to_string();
            out.entry(name).or_insert(i + 1);
        }
    }
    out
}

fn window_blocks(text: &str, hit_lines: &[usize], radius: usize) -> Vec<(usize, usize)> {
    let n = py_splitlines(text).len();
    if hit_lines.is_empty() {
        return vec![(1, n.min(2 * radius))];
    }
    let mut sorted_hits = hit_lines.to_vec();
    sorted_hits.sort();
    let mut spans: Vec<(usize, usize)> = Vec::new();
    for &h in &sorted_hits {
        let a = if h > radius { h - radius } else { 1 };
        let b = (h + radius).min(n);
        if let Some(last) = spans.last_mut() {
            if a <= last.1 + 5 {
                last.1 = b;
                continue;
            }
        }
        spans.push((a, b));
    }
    spans
}

// ------------------------------------------------------------- E23 ts_blocks
//
// tree-sitter structural blocks for the JS/TS family (campaign #4 wave 5,
// lab/research/wave5/multilang-and-sweeps.md Part (a)). Flag-gated behind
// --ts-blocks (default OFF: byte-identical engine). Mechanism per the field
// consensus (cAST / SweRank+ / Sweep / Continue / LlamaIndex): walk the CST
// with a ~10-entry node-type ALLOWLIST -- not queries/tags.scm, whose
// per-grammar files are of "varying sophistication" and which cannot be
// version-pinned alongside the grammar crates -- and emit spans in the EXACT
// shape `python_blocks` produces, so the packer, padding (E12b), length
// norm (E14), and anchor seating apply unchanged:
//
//   - spans are 1-indexed inclusive (start, end);
//   - a leading preamble span (1, first_header_line-1) covers imports;
//   - each header's span runs to the next header at same-or-lower nesting
//     depth (CST depth plays the role python_blocks gives indentation), so
//     top-level spans PARTITION the file after the preamble and trailing
//     module-level code is swallowed by the preceding block -- the packer's
//     adjacency expectations hold;
//   - class-like spans cover header..end-of-partition, and each member
//     (method, arrow-function class field) ALSO gets its own tighter span,
//     the same multi-granularity nesting python_blocks emits.
//
// Line numbers: tree-sitter's byte offsets are mapped onto py_splitlines'
// OWN line starts (binary search over slice offsets) rather than trusting
// tree-sitter row numbers -- py_splitlines splits on the full Unicode
// boundary set (\u{2028}, \x0b, ...) while tree-sitter rows count only
// \n/\r\n, and the packer slices `py_splitlines` output by these numbers,
// so the mapping must be exact even on files where the two disagree.
//
// Parse failures degrade to the whole-file span (1, n) -- python_blocks'
// own no-headers behavior -- never to an error: tree-sitter returns a tree
// with ERROR nodes for malformed input, so this path fires only on
// parser-init failure or the (documented, cancellation-only) None parse.

/// True for the extensions `ts_blocks` can parse. Deliberately the exact
/// four extensions of the E23 scope (.js/.jsx/.ts/.tsx) -- not every
/// JS-family extension in CODE_EXTENSIONS' universe (.mjs/.cjs are not
/// indexed by the corpus walk anyway, see CODE_EXTENSIONS).
pub(crate) fn is_ts_family(rel: &str) -> bool {
    rel.ends_with(".js") || rel.ends_with(".jsx") || rel.ends_with(".ts") || rel.ends_with(".tsx")
}

/// Kinds that make a bare expression node "a function" when bound to a
/// declarator / object-literal pair / class field. `function_expression`
/// is the current tree-sitter-javascript kind; `function` was its pre-0.20
/// name, kept for grammar-bump resilience (matching a never-produced kind
/// is harmless).
fn ts_is_function_value_kind(kind: &str) -> bool {
    matches!(kind, "arrow_function" | "function_expression" | "function" | "generator_function")
}

/// If `node` is a block header per the E23 allowlist, returns the byte
/// offset its span starts at (hoisted to the enclosing declaration
/// statement for declarator-bound functions, and to a wrapping
/// `export_statement` / `ambient_declaration` in both cases -- the
/// JS analogue of python_blocks folding decorator lines into a def's span).
fn ts_header_start(node: &tree_sitter::Node) -> Option<usize> {
    let kind = node.kind();
    let declaration_like = matches!(
        kind,
        // functions & classes (async variants are the same kinds with an
        // `async` token child; generator declarations are their own kind)
        "function_declaration" | "generator_function_declaration"
            | "class_declaration" | "abstract_class_declaration"
            // class-body and object-literal methods
            | "method_definition"
            // TS-only declaration kinds (trivial to include: kind match only)
            | "interface_declaration" | "enum_declaration"
            | "module" | "internal_module"
    );
    if declaration_like {
        let mut start = node.start_byte();
        if let Some(parent) = node.parent() {
            if matches!(parent.kind(), "export_statement" | "ambient_declaration") {
                start = parent.start_byte();
            }
        }
        return Some(start);
    }
    // Expression-level functions -- the shapes a header-regex port
    // structurally cannot see (the a4 null): `const f = () => ..`,
    // `{ key: function() .. }`, `handleClick = () => ..` class fields.
    let bound_function = match kind {
        "variable_declarator" | "pair" | "field_definition" | "public_field_definition" => node
            .child_by_field_name("value")
            .is_some_and(|v| ts_is_function_value_kind(v.kind())),
        _ => false,
    };
    if !bound_function {
        return None;
    }
    let mut start = node.start_byte();
    let mut cur = *node;
    // hoist declarator -> lexical_declaration/variable_declaration ->
    // export_statement; and field/pair headers to any decorator-inclusive
    // parent start. Two levels are sufficient for every allowlisted shape.
    for _ in 0..2 {
        let Some(parent) = cur.parent() else { break };
        match parent.kind() {
            "lexical_declaration" | "variable_declaration" | "export_statement"
            | "ambient_declaration" => {
                start = parent.start_byte();
                cur = parent;
            }
            _ => break,
        }
    }
    Some(start)
}

/// `python_blocks` for the JS/TS family via tree-sitter. Same output
/// contract (see the E23 block comment above); `rel` picks the grammar
/// (.tsx -> TSX, .ts -> TypeScript, .js/.jsx -> JavaScript, which parses
/// JSX natively).
fn ts_blocks(text: &str, rel: &str) -> Vec<(usize, usize)> {
    let lines = py_splitlines(text);
    let n = lines.len();
    let language: tree_sitter::Language = if rel.ends_with(".tsx") {
        tree_sitter_typescript::LANGUAGE_TSX.into()
    } else if rel.ends_with(".ts") {
        tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into()
    } else {
        tree_sitter_javascript::LANGUAGE.into()
    };
    let mut parser = tree_sitter::Parser::new();
    if parser.set_language(&language).is_err() {
        return vec![(1, n)];
    }
    let Some(tree) = parser.parse(text, None) else {
        return vec![(1, n)];
    };

    // py_splitlines line-start byte offsets (each returned slice borrows
    // from `text`, so pointer arithmetic recovers its offset exactly).
    let base = text.as_ptr() as usize;
    let starts: Vec<usize> = lines.iter().map(|l| l.as_ptr() as usize - base).collect();
    let line_of_byte = |b: usize| -> usize {
        match starts.binary_search(&b) {
            Ok(i) => i,
            Err(0) => 0,
            Err(i) => i - 1,
        }
    };

    // Iterative pre-order walk (recursion would be stack-bound on deeply
    // nested minified JS). `headers` collects (0-indexed line, depth) where
    // depth counts EMITTED ancestors only -- the CST analogue of
    // python_blocks' indent column.
    let mut headers: Vec<(usize, usize)> = Vec::new();
    let mut cursor = tree.root_node().walk();
    let mut depth = 0usize;
    let mut emitted_stack: Vec<bool> = Vec::new();
    'walk: loop {
        let node = cursor.node();
        let emitted = match ts_header_start(&node) {
            Some(start_byte) => {
                headers.push((line_of_byte(start_byte), depth));
                true
            }
            None => false,
        };
        if cursor.goto_first_child() {
            emitted_stack.push(emitted);
            if emitted {
                depth += 1;
            }
            continue;
        }
        loop {
            if cursor.goto_next_sibling() {
                break;
            }
            if !cursor.goto_parent() {
                break 'walk;
            }
            if emitted_stack.pop().unwrap_or(false) {
                depth -= 1;
            }
        }
    }

    if headers.is_empty() {
        return vec![(1, n)];
    }
    // Hoisted starts can place a header a line before an already-collected
    // one (export wrapper) and same-line multi-declarators duplicate a
    // line: sort by (line, depth) and keep the first (shallowest) header
    // per line, mirroring python_blocks' one-header-per-line invariant.
    headers.sort();
    headers.dedup_by_key(|h| h.0);

    let mut spans: Vec<(usize, usize)> = Vec::new();
    if headers[0].0 > 0 {
        spans.push((1, headers[0].0)); // leading preamble (imports)
    }
    for (idx, &(i, d)) in headers.iter().enumerate() {
        let mut end = n;
        for &(j, d2) in &headers[idx + 1..] {
            if d2 <= d {
                end = j;
                break;
            }
        }
        spans.push((i + 1, end));
    }
    spans.into_iter().filter(|&(a, b)| b >= a).collect()
}

fn hit_lines(text: &str, terms: &HashSet<String>) -> Vec<usize> {
    let mut hits = Vec::new();
    for (i, ln) in py_splitlines(text).iter().enumerate() {
        let low = py_lower(ln);
        if terms.iter().any(|t| low.contains(t.as_str())) {
            hits.push(i + 1);
        }
    }
    hits
}

struct Candidate {
    file: String,
    span: (usize, usize),
    tok: usize,
    terms: HashSet<String>,
    gain: f64,
    text: String,
    name_score: f64,
    // `tok.max(1) as f64` raised to the E14 length-normalization exponent
    // (`len_exp`), precomputed exactly once per candidate at construction
    // time. Both selection-metric comparators (pass-1 `best_ratio` and
    // pass-2 `marginal`) divide by this field instead of calling `.powf()`
    // inline -- a determinism requirement, not just an optimization: `tok`
    // never changes after construction, but re-deriving `tok_pow` on every
    // comparator call (rather than reading a value computed once) would
    // reintroduce exactly the kind of "not a pure function of a stable
    // snapshot" hazard that the pass-2 `marginal` closure's own doc comment
    // (see below) documents as the root cause of issue #14's nondeterminism.
    tok_pow: f64,
}

// ---------------------------------------------------------------- region-level symbol-name anchoring
//
// Dogfood bug (query "how is the token budget enforced when packing regions
// into the bundle" against this repo's own core.rs/core.py): the query
// names `pack_regions` almost verbatim, yet pack_regions' region-scoring
// only rewarded query-TERM DENSITY in a region's body -- a region whose name
// IS the query (pack_regions) had no scoring edge over a same-file region
// that merely happens to mention "token" a lot in its body (e.g.
// subtokens()). Ported from lab/lanes2.py's pack_regions region-name-
// anchoring fix, integrated with THIS module's idf-weighted gain +
// anchor_symbols channel-aware forcing (neither of which lanes2 has).

/// Which definition-symbol regex (if any) applies to `rel`, by extension --
/// the same per-language mapping `Corpus::build` uses inline, factored out
/// so region candidates can be matched back to the symbol that defines them.
fn def_re_for(rel: &str) -> Option<&'static Regex> {
    if rel.ends_with(".py") {
        Some(&PY_DEF_RE)
    } else if rel.ends_with(".go") {
        Some(&GO_DEF_RE)
    } else if rel.ends_with(".rs") {
        Some(&RS_DEF_RE)
    } else if rel.ends_with(".js") || rel.ends_with(".ts") || rel.ends_with(".jsx") || rel.ends_with(".tsx") {
        Some(&JS_DEF_RE)
    } else {
        None
    }
}

/// (line_number, symbol_name) for every def/class/fn header `def_re`
/// matches in `text`, sorted ascending by line -- mirrors lanes2.py's
/// `_file_def_lines`. Line number is derived from the matched GROUP's start
/// byte offset, not the overall match's start: these regexes' leading
/// `\s*`/`^\s*` is greedy and, under multi-line mode, `^` matches at the
/// start of every line, so the overall match can begin several blank lines
/// above the actual `def`/`class` keyword. The captured identifier itself
/// is always on the same physical line as its keyword, so anchoring off
/// the group's own start is correct regardless of how much leading
/// whitespace was swallowed.
fn file_def_lines(text: &str, def_re: Option<&'static Regex>) -> Vec<(usize, String)> {
    let Some(re) = def_re else { return Vec::new() };
    let mut out: Vec<(usize, String)> = Vec::new();
    for cap in re.captures_iter(text) {
        for gi in 1..cap.len() {
            if let Some(g) = cap.get(gi) {
                let line = text[..g.start()].matches('\n').count() + 1;
                out.push((line, g.as_str().to_string()));
                break;
            }
        }
    }
    out.sort();
    out
}

/// The defining symbol whose header line falls inside span [a, b] -- i.e.
/// the region's own defining symbol, if any. Picks the EARLIEST matching
/// header (the region's "primary" symbol) when more than one falls in
/// range. Mirrors lanes2.py's `_region_symbol`.
fn region_symbol(def_lines: &[(usize, String)], a: usize, b: usize) -> Option<&str> {
    for (line, sym) in def_lines {
        if *line > b {
            break;
        }
        if *line >= a {
            return Some(sym.as_str());
        }
    }
    None
}

/// Region name-anchoring score: raw count of query-term subtokens the
/// defining symbol's own name contains, i.e.
/// |subtokens(symbol) intersect query_terms| -- NOT normalized by the
/// symbol's subtoken count (normalizing would score a single-subtoken
/// symbol like `subtokens` (1/1 = 1.0) as high as a two-subtoken symbol
/// like `pack_regions` matching BOTH query terms (2/2 = 1.0) -- exactly the
/// collision this fix exists to break). A symbol whose EVERY subtoken is a
/// query term gets a further +1 bonus. Mirrors lanes2.py's `_name_score`.
fn name_score(sym: Option<&str>, tset: &HashSet<String>) -> f64 {
    let Some(s) = sym else { return 0.0 };
    let sym_subs: HashSet<String> = subtokens(s).into_iter().collect();
    if sym_subs.is_empty() {
        return 0.0;
    }
    let overlap_count = sym_subs.intersection(tset).count();
    let mut score = overlap_count as f64;
    if overlap_count > 0 && overlap_count == sym_subs.len() {
        score += 1.0;
    }
    score
}

// ---------------------------------------------------------------- E18/E19 sibling expansion helpers
//
// Campaign #4 wave-5 (E17 case mining + the wave5 sweep-localization survey):
// post-adoption D-class mass is dominated by multi-function "sweep" patches
// (11/30 top-D cases have no majority owner function), which no single-pick
// ranking mechanism can capture. Given pass-1's pick in a file (the seed),
// these helpers let `pack_regions` deterministically add SIBLING spans as
// extra depth for that file:
//
//   E19 (`family_enum`): def-name-family members -- same method name across
//   sibling classes in the file, or a shared def-name prefix/suffix segment
//   family with >= FAMILY_MIN_AFFIX members (the "18 sibling constructors"
//   shape). The seed must itself BE a family member; membership is derived
//   from ITS name only.
//
//   E18 (`sibling_sim` > 0): spans whose identifier-token-bag overlap with
//   the seed is >= the threshold (SourcererCC-style: multiset intersection
//   over max bag size; Type-2 rename-only clone recall is 97-98% at 0.7),
//   top `max_siblings` by overlap. Keywords are excluded from the bags;
//   operators never match IDENT_RE in the first place.
//
// Explicitly NOT a re-rank: E16's rejected density boost re-weighted the
// query-density metric for class members and regressed monotonically.
// Similarity-to-seed / name-family membership are signals the density metric
// does not contain, and the added spans are DEPTH (extra pass-2-style,
// budget-checked, evictable seats) -- the existing ranking is never touched.

/// Max family members E19 will queue per seed (guards against huge visitor
/// classes / mega-families; nearest-to-seed members win).
const FAMILY_CAP: usize = 8;
/// Minimum family size for the prefix/suffix segment families (exact-name
/// method families need only 2: the seed + one sibling).
const FAMILY_MIN_AFFIX: usize = 4;

static PY_FAMILY_DEF_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^([ \t]*)(async[ \t]+def|def|class)[ \t]+(\w+)").unwrap());

/// One `def`/`class` header line of a Python file, for E19 family grouping.
struct DefEntry {
    /// 1-indexed header line number.
    line: usize,
    is_class: bool,
    name: String,
}

/// Every def/class header in `text`, ascending by line (Python only).
fn py_family_def_entries(text: &str) -> Vec<DefEntry> {
    let mut out = Vec::new();
    for (i, ln) in py_splitlines(text).iter().enumerate() {
        if let Some(caps) = PY_FAMILY_DEF_RE.captures(ln) {
            out.push(DefEntry {
                line: i + 1,
                is_class: caps.get(2).unwrap().as_str() == "class",
                name: caps.get(3).unwrap().as_str().to_string(),
            });
        }
    }
    out
}

/// Raw lowercase name segments (underscore + camelCase split), WITHOUT the
/// stemming/stopword/length filtering `subtokens` applies -- family keys are
/// literal affix identity (`_print_X` -> ["print", "x"],
/// `ArcsinDistribution` -> ["arcsin", "distribution"]), so a segment must
/// survive even when it is short or a stopword.
fn name_segments(name: &str) -> Vec<String> {
    let mut parts: Vec<String> = Vec::new();
    for chunk in name.split('_') {
        if chunk.is_empty() {
            continue;
        }
        for m in camel_matches(chunk) {
            parts.push(py_lower(&m));
        }
    }
    parts
}

/// Identifier-token bag (multiset) of a span's text for E18 similarity:
/// `tokenize` output (identifiers only -- stems + subtokens, stopwords and
/// <=2-char tokens already dropped) minus the stemmed keyword-exclusion set.
fn sibling_token_bag(text: &str, kw_excl: &HashSet<String>) -> HashMap<String, usize> {
    let mut bag: HashMap<String, usize> = HashMap::new();
    for t in tokenize(text) {
        if !kw_excl.contains(&t) {
            *bag.entry(t).or_insert(0) += 1;
        }
    }
    bag
}

/// SourcererCC-style bag overlap: multiset intersection size over the larger
/// bag's size. Pure integer arithmetic until the single final division, so
/// the value is exactly reproducible regardless of hash-map iteration order.
fn sibling_bag_overlap(a: &HashMap<String, usize>, b: &HashMap<String, usize>) -> f64 {
    let na: usize = a.values().sum();
    let nb: usize = b.values().sum();
    if na == 0 || nb == 0 {
        return 0.0;
    }
    // usize addition is associative/commutative: iteration order of `a`
    // cannot change this sum (no float accumulation here -- see the
    // canonical-summation discipline in pack_regions' weight()).
    let inter: usize = a.iter().map(|(k, &ca)| ca.min(b.get(k).copied().unwrap_or(0))).sum();
    inter as f64 / na.max(nb) as f64
}

/// Greedy weighted-coverage packing of regions under budget. See
/// lanes2.py's `pack_regions` docstring.
///
/// A region's term coverage is weighted by each matched term's corpus idf
/// rather than counted flatly, so a region hitting a couple of rare,
/// highly-specific identifiers outranks one hitting many generic terms
/// ("error", "value", ...) that happen to be query terms too.
///
/// `anchor_symbols` (see `anchor_def_symbols`), if given, maps an
/// anchor-channel file to the definition-symbol(s) that anchored it in.
/// Channel-aware packing: the anchored symbol's OWN signature+body block
/// (found among `python_blocks`' nested spans by matching def-line number,
/// see `py_def_line_numbers`) is force-included as that file's pass-1
/// region, at a deeper cap than the generic score-proportional one -- the
/// query named this exact symbol, so its definition is the region least
/// likely to be noise, independent of how it happens to score on term
/// density.
///
/// `w_name` (0.0 from the production caller, i.e. DISABLED: a sweep of
/// {0.0, 0.5, 1.0} on the exact harness -- parity/region_eval2.py +
/// lab/agentless_metric.py, full300_v9 vs full300_v8/wname05, issue #4 --
/// measured that any positive weight regresses the shipped engine, LINE
/// all-or-nothing 35.7% -> 29.3% and line-fraction 0.4564 -> 0.3989, while
/// 0.5 and 1.0 score identically, i.e. the weight saturates; the original
/// validation was against the diverged lab pipeline, issue #8; parameter
/// and code paths kept for re-tuning) additionally
/// rewards a region whose OWN defining symbol name matches query terms (see
/// `name_score`), independent of the anchor channel above: `anchor_symbols`
/// only fires for files the anchor channel itself promoted, whereas this
/// term applies to every file's regions, so a region like `pack_regions`
/// can win purely on its name matching query terms "pack"/"region" even
/// when no anchor promotion happened. Applied to the SELECTION METRIC
/// (gain/tok, post-division) rather than folded into `gain` pre-division: a
/// flat additive term inside `gain` would be diluted away for large
/// regions by the same `/tok` division that makes them expensive, so a big
/// true-match region (e.g. ~1800-token `pack_regions`) could never
/// out-rank a small merely-dense one under gain/tok alone -- adding the
/// name bonus AFTER the division keeps it undiluted by region size, since
/// a symbol-name match is identity evidence independent of how long the
/// matched definition happens to be (measured via this repo's own dogfood
/// case, see lab/dogfood_pack_regions.py).
///
/// `len_exp` (E14/issue #14 case mining -- 1.0 reproduces the exact pre-E14
/// `gain/tok` ranking, BYTE-IDENTICAL; the production caller (main.rs)
/// defaulted to 1.0 pre-adoption and now defaults to 0.85, the comboA
/// campaign result, see #4): the exponent
/// applied to the token-count denominator of the selection metric in both
/// passes, i.e. `gain / tok.max(1)^len_exp` (pass 1) and the analogous
/// `.../tok.max(1)^len_exp` marginal-coverage density (pass 2), rather than
/// the flat `gain/tok` linear-length penalty. Motivation: mining E13's
/// mismatch cases found the `/tok` objective systematically crushes long
/// real-fix functions in favor of short lucky stubs that happen to contain a
/// query term (gold region >3x longer than the chosen one in 22/26 mined
/// cases). `len_exp < 1.0` softens (sub-linearly discounts) the length
/// penalty, letting a region's raw `gain` (term-density salience) compete
/// more on its own terms against a merely-shorter rival; `len_exp == 1.0`
/// reproduces the original linear penalty exactly; `len_exp > 1.0` would
/// sharpen it further (steeper preference for short regions, untested by
/// E14). Only the density DENOMINATOR changes -- the post-division `w_name`
/// bonus terms stay undiluted by region size exactly as before (see the
/// `w_name` doc above), since those are identity evidence, not term-density
/// evidence, and E14 doesn't touch that distinction.
///
/// `pad_lines` (E12/issue "span padding"): 0 is OFF and takes the pre-E12
/// code path verbatim -- byte-identical output. The production caller
/// (main.rs) defaulted to 0 pre-adoption and now defaults to 5, the comboA
/// campaign result (see #4). When > 0, AFTER
/// both selection passes above finish (this function never re-runs or
/// re-scores the selection comparator for padding), every selected span is
/// extended by up to `pad_lines` lines in each direction (clamped to the
/// file's own line count), same-file padded spans that now overlap or touch
/// are merged. E12b guard: since padding only ever grows the bundle, if the
/// padded total now exceeds `budget_tokens`, padding is first DE-ESCALATED
/// -- shrunk back toward 0, one line at a time, on the lowest-gain selected
/// span first (fully drained before the next-lowest is touched) -- until
/// the bundle fits again; only if it STILL doesn't fit once every span has
/// been de-escalated all the way to 0 (i.e. even the unpadded selection
/// exceeds budget, which pass 1's unconditional one-span-per-file seating
/// makes possible at small budgets) are WHOLE spans evicted (never
/// partially truncated) lowest-gain-first -- and only ever pass-2 spans:
/// pass-1 origin spans (one per selected file, anchor-forced ones included)
/// are exempt from eviction, so the guard's invariant -- a file present in
/// the unpadded (pad=0) selection is never evicted purely because padding
/// grew the bundle -- holds at every budget. If nothing evictable remains,
/// the bundle is returned over budget, matching the pad=0 path's own
/// overshoot behavior on the same input -- see `pack_regions`' own
/// de-escalation/eviction blocks below for the precise, precomputed
/// (non-recomputed) gain metric and tie-break order. Applied
/// AFTER `len_exp`-based selection: padding operates on whichever spans the
/// (possibly len_exp-adjusted) selection passes chose, and re-derives each
/// padded span's own `tok`/`text` from the file directly rather than
/// touching `tok_pow` (a selection-time-only field), so the two experiments
/// compose without either one reaching into the other's fields.
///
/// `family_enum` / `sibling_sim` / `max_siblings` (E18/E19 sibling
/// expansion, campaign #4 wave 5 -- see the helper block above
/// `pack_regions` for the mechanism and rationale): defaults
/// (`false`/`0.0`/any) are OFF and BYTE-IDENTICAL to the pre-E18/E19
/// engine -- the sibling block is skipped entirely and no other code path
/// reads these parameters. When enabled, sibling spans are seated BETWEEN
/// pass 1 and pass 2 (depth for the files pass 1 anchored, ahead of the
/// generic marginal race), budget-checked like pass-2 seats (a sibling
/// that does not fit is skipped, never force-seated), and marked as
/// pass-2 spans for the E12b guard (evictable; a file's pass-1 span --
/// its last-span guarantee -- is never displaced by a sibling).
///
/// `use_ts_blocks` (E23, campaign #4 wave 5): default `false` is OFF and
/// BYTE-IDENTICAL to the pre-E23 engine. When enabled, .js/.jsx/.ts/.tsx
/// files get tree-sitter structural block candidates (`ts_blocks`, same
/// span shape as `python_blocks`) instead of `window_blocks(±30)` -- see
/// the E23 block comment above `ts_blocks`. Python files are untouched by
/// the flag in either state.
pub fn pack_regions(
    corpus: &Corpus,
    files: &[String],
    terms: &[String],
    scores: &IndexMap<String, f64>,
    budget_tokens: i64,
    count_tokens: &dyn Fn(&str) -> usize,
    anchor_symbols: Option<&IndexMap<String, Vec<String>>>,
    w_name: f64,
    pad_lines: usize,
    len_exp: f64,
    family_enum: bool,
    sibling_sim: f64,
    max_siblings: usize,
    use_ts_blocks: bool,
) -> (IndexMap<String, Vec<(usize, usize)>>, String) {
    let tset: HashSet<String> = terms.iter().cloned().collect();
    let idf: HashMap<String, f64> = tset
        .iter()
        .map(|t| {
            let df = corpus.df.get(t).copied().unwrap_or(0) as f64;
            let v = (1.0 + (corpus.n_docs as f64 - df + 0.5) / (df + 0.5)).ln();
            (t.clone(), v)
        })
        .collect();
    // Sum in a canonical (lexicographically sorted) term order rather than
    // raw HashSet iteration order: HashSet's iteration order depends on
    // std's per-process-random hasher seed, and float addition is not
    // associative, so summing the same IDF values in a different order can
    // produce a different ULP-level result across processes -- which then
    // flips exact gain/tok ties in `pack_regions` nondeterministically. This
    // was the root cause of the observed cross-process region-selection
    // flakiness on exact ties (see PARITY_NOTES.md / issue #14).
    let weight = |seg_terms: &HashSet<String>| -> f64 {
        let mut terms: Vec<&String> = seg_terms.iter().collect();
        terms.sort();
        terms.iter().map(|t| idf.get(*t).copied().unwrap_or(0.0)).sum()
    };

    let mut candidates: Vec<Candidate> = Vec::new();
    // E18/E19 only (empty and never read otherwise): spans the zero-query-
    // term filter below drops from `candidates`, kept as SIBLING-ONLY
    // material -- a sweep-family member (e.g. one of 18 near-identical
    // constructors) need not contain a single query term, so it must still
    // be reachable by the sibling block even though the ranked passes never
    // see it. Collected only when a sibling flag is on: the default path
    // does not even pay the `count_tokens` cost, let alone change behavior.
    let sibling_flags_on = family_enum || sibling_sim > 0.0;
    let mut extra_cands: Vec<Candidate> = Vec::new();

    for rel in files {
        let text = &corpus.text[rel];
        let lines = py_splitlines(text);
        let hits = hit_lines(text, &tset);
        // E23: with --ts-blocks, the JS/TS family gets tree-sitter structural
        // blocks instead of fixed windows -- the flag-OFF path is
        // byte-identical to the pre-E23 engine (same two branches).
        let spans = if rel.ends_with(".py") {
            python_blocks(text)
        } else if use_ts_blocks && is_ts_family(rel) {
            ts_blocks(text, rel)
        } else {
            window_blocks(text, &hits, 30)
        };
        let hitset: HashSet<usize> = hits.into_iter().collect();
        let def_lines: Vec<(usize, String)> =
            if w_name != 0.0 { file_def_lines(text, def_re_for(rel)) } else { Vec::new() };
        for (a, b) in spans {
            if a == 0 || b < a || a > lines.len() {
                // guard against degenerate spans; Python's 1-indexed slicing
                // lines[a-1:b] silently no-ops out of range.
            }
            let seg_lines: Vec<&str> = if a >= 1 && a <= lines.len() + 1 {
                let start = a.saturating_sub(1).min(lines.len());
                let end = b.min(lines.len());
                if start < end {
                    lines[start..end].to_vec()
                } else {
                    Vec::new()
                }
            } else {
                Vec::new()
            };
            let seg = seg_lines.join("\n");
            let seg_tokens: HashSet<String> = tokenize(&seg).into_iter().collect();
            let seg_terms: HashSet<String> = tset.intersection(&seg_tokens).cloned().collect();
            let n_hits = (a..=b).filter(|l| hitset.contains(l)).count();
            if seg_terms.is_empty() && n_hits == 0 && a > 1 {
                if sibling_flags_on {
                    let tok = count_tokens(&seg);
                    if tok > 0 {
                        // gain is exactly what the formula below yields for
                        // empty terms + zero hits: 0.0 -- so if seated by
                        // the sibling block, such a span is the first to be
                        // de-escalated/evicted by the E12b guard.
                        let ns = if w_name != 0.0 { name_score(region_symbol(&def_lines, a, b), &tset) } else { 0.0 };
                        let tok_pow = (tok.max(1) as f64).powf(len_exp);
                        extra_cands.push(Candidate {
                            file: rel.clone(), span: (a, b), tok, terms: seg_terms, gain: 0.0, text: seg,
                            name_score: ns, tok_pow,
                        });
                    }
                }
                continue;
            }
            let tok = count_tokens(&seg);
            if tok == 0 {
                continue;
            }
            let gain = (weight(&seg_terms) + 0.5 * n_hits as f64) * (0.3 + scores.get(rel).copied().unwrap_or(0.0));
            let ns = if w_name != 0.0 { name_score(region_symbol(&def_lines, a, b), &tset) } else { 0.0 };
            let tok_pow = (tok.max(1) as f64).powf(len_exp);
            candidates.push(Candidate {
                file: rel.clone(), span: (a, b), tok, terms: seg_terms, gain, text: seg, name_score: ns, tok_pow,
            });
        }
    }

    // Channel-aware forced region: for each anchor-selected file, seat its
    // anchored symbol's own def block (a candidate whose span starts exactly
    // at that symbol's def line, per `py_def_line_numbers`) as the pass-1
    // pick -- bypassing the generic gain/tok ranking entirely, since the
    // query named this exact symbol.
    let mut forced: HashMap<String, usize> = HashMap::new(); // file -> candidate index
    if let Some(anchor_map) = anchor_symbols {
        for (rel, syms) in anchor_map {
            if !rel.ends_with(".py") || !files.iter().any(|f| f == rel) {
                continue;
            }
            let def_lines = py_def_line_numbers(&corpus.text[rel]);
            let mut cand_by_start: HashMap<usize, usize> = HashMap::new();
            for (i, c) in candidates.iter().enumerate() {
                if &c.file == rel {
                    cand_by_start.insert(c.span.0, i);
                }
            }
            for sym in syms {
                if let Some(&ln) = def_lines.get(sym) {
                    if let Some(&idx) = cand_by_start.get(&ln) {
                        forced.insert(rel.clone(), idx);
                        break;
                    }
                }
            }
        }
    }

    let mut all_segments: Vec<Candidate> = Vec::new();
    let mut chosen_map: IndexMap<String, Vec<usize>> = IndexMap::new(); // file -> indices into all_segments
    let mut spent: i64 = 0;
    let mut covered: HashSet<String> = HashSet::new();
    // (file, ORIGINAL candidate index of its pass-1 pick), in files order --
    // the E18/E19 sibling block below uses the untrimmed original candidate
    // as each file's seed. Recorded unconditionally (a plain index copy, no
    // scoring): with the sibling flags off nothing ever reads it, so the
    // default path is untouched.
    let mut pass1_orig_idx: Vec<(String, usize)> = Vec::new();

    let n_files = files.len().max(1) as i64;
    let floor_tok: i64 = 120;
    let spare = (budget_tokens / 2 - floor_tok * n_files).max(0);
    let total_score: f64 = {
        let s: f64 = files.iter().map(|f| scores.get(f).copied().unwrap_or(0.0)).sum();
        if s > 0.0 {
            s
        } else {
            1.0
        }
    };
    let caps: HashMap<String, i64> = files
        .iter()
        .map(|f| {
            let sc = scores.get(f).copied().unwrap_or(0.0);
            // Guard against a non-finite `scores` entry (NaN/inf, e.g. from
            // an upstream normalization/idf bug): `ratio` can otherwise be
            // NaN or +inf, and `(x as i64)` on +inf saturates to i64::MAX,
            // which then overflows the `floor_tok +` add below (checked
            // arithmetic panics in debug; silently wraps in release either
            // way it's wrong). A non-finite ratio contributes no bonus
            // depth instead; finite-input behavior is unchanged.
            let ratio = sc / total_score;
            let bonus_tok = if ratio.is_finite() { ((spare as f64) * ratio) as i64 } else { 0 };
            (f.clone(), floor_tok + bonus_tok)
        })
        .collect();
    // Anchor-forced files get a deeper cap on top of their score-proportional
    // one (up to budget/10) -- the definition block a query explicitly named
    // is worth more depth than generic density would otherwise buy it.
    let anchor_cap: i64 = (budget_tokens / 10).max(floor_tok);

    for rel in files {
        let idxs: Vec<usize> = candidates.iter().enumerate().filter(|(_, c)| &c.file == rel).map(|(i, _)| i).collect();
        if idxs.is_empty() {
            continue;
        }
        let forced_idx = forced.get(rel).copied();
        // Python's `max(cands, key=...)` returns the FIRST maximal element
        // on ties; Rust's `Iterator::max_by` returns the LAST. Replicate
        // Python's tie behavior with an explicit "strictly greater only
        // replaces" fold.
        let best_idx = if let Some(fi) = forced_idx {
            fi
        } else {
            let mut best_idx = idxs[0];
            let mut best_ratio =
                candidates[best_idx].gain / candidates[best_idx].tok_pow + w_name * candidates[best_idx].name_score;
            for &i in &idxs[1..] {
                let ratio = candidates[i].gain / candidates[i].tok_pow + w_name * candidates[i].name_score;
                if ratio > best_ratio {
                    best_ratio = ratio;
                    best_idx = i;
                }
            }
            best_idx
        };
        let mut best_span = candidates[best_idx].span;
        let mut best_text = candidates[best_idx].text.clone();
        let mut best_tok = candidates[best_idx].tok;
        let best_terms = candidates[best_idx].terms.clone();
        let mut per_file_cap = *caps.get(rel).unwrap_or(&floor_tok);
        if forced_idx.is_some() {
            per_file_cap = per_file_cap.max((best_tok as i64).min(anchor_cap));
        }

        if best_tok as i64 > per_file_cap {
            let (a, b) = best_span;
            let full_lines = py_splitlines(&corpus.text[rel]);
            let start = a.saturating_sub(1).min(full_lines.len());
            let end = b.min(full_lines.len());
            let seg_lines: Vec<&str> = if start < end { full_lines[start..end].to_vec() } else { Vec::new() };
            // NOTE: `keep` (used for the reported SPAN) is deliberately NOT
            // clamped to seg_lines.len() here, matching a quirk of the
            // Python original: `keep = max(4, int(len(seg_lines) *
            // per_file_cap / best["tok"]))` can exceed len(seg_lines) for a
            // very short/dense segment, but `seg_lines[:keep]` silently
            // no-ops at the slice boundary while the reported span
            // `(a, a + keep - 1)` still uses the uncapped value. Only the
            // TEXT slice is bounds-limited.
            let keep = (4usize).max(((seg_lines.len() as f64) * (per_file_cap as f64) / (best_tok as f64)) as usize);
            let slice_end = keep.min(seg_lines.len());
            let mut seg = seg_lines[..slice_end].join("\n");
            let mut tok = count_tokens(&seg);
            if tok as i64 > 2 * per_file_cap {
                let char_cap = (per_file_cap * 4) as usize;
                let truncated: String = seg.chars().take(char_cap).collect();
                seg = truncated;
                tok = count_tokens(&seg);
            }
            best_span = (a, a + keep - 1);
            best_text = seg;
            best_tok = tok;
        }

        let best_name_score = candidates[best_idx].name_score;
        // `gain` here is the ORIGINAL (pre-per-file-cap-trim) candidate's
        // precomputed selection gain, kept (not zeroed) so E12's padding
        // eviction below has a real per-span score to rank by; nothing in
        // the pre-E12 (`pad_lines == 0`) output path ever reads this field,
        // so this is a no-op for default behavior.
        //
        // `tok_pow` is re-derived here (not copied from
        // `candidates[best_idx].tok_pow`) because `best_tok` may have just
        // been overwritten above by the per-file-cap trim -- this candidate
        // is output-only (never fed back into a ranking comparator), so
        // recomputing once, off the trimmed `best_tok`, is exact and
        // doesn't touch the determinism concern that applies to the
        // comparator hot paths.
        let best_tok_pow = (best_tok.max(1) as f64).powf(len_exp);
        let cand = Candidate {
            file: rel.clone(), span: best_span, tok: best_tok, terms: best_terms, gain: candidates[best_idx].gain,
            text: best_text, name_score: best_name_score, tok_pow: best_tok_pow,
        };
        covered.extend(cand.terms.iter().cloned());
        spent += cand.tok as i64;
        let seg_idx = all_segments.len();
        all_segments.push(cand);
        chosen_map.entry(rel.clone()).or_default().push(seg_idx);
        pass1_orig_idx.push((rel.clone(), best_idx));
    }

    // Boundary between pass-1 and pass-2 segments: every all_segments index
    // below this was seated by pass 1 (exactly one span per file, seated
    // UNCONDITIONALLY -- note `spent += cand.tok` above has no budget
    // check), everything at/after it by pass 2 (budget-checked). The E12b
    // eviction guard below keys its pass-1 exemption off this boundary.
    let pass1_seg_count = all_segments.len();

    // ---------------------------------------------------------------- E18/E19: sibling expansion
    //
    // Flag-gated (defaults skip the whole block: byte-identical output).
    // Seated here -- after `pass1_seg_count` is fixed, before pass 2 -- so
    // sibling spans (a) count as pass-2 spans for the E12b guard
    // (evictable, never displacing a file's pass-1 last-span guarantee),
    // (b) get depth priority over pass 2's generic marginal race, and
    // (c) are excluded from pass 2's `remaining` pool via the chosen-keys
    // set built below, exactly like pass-1 picks. See the helper block
    // above `pack_regions` for the mechanism/rationale.
    if family_enum || sibling_sim > 0.0 {
        // Stemmed exclusion set for E18's identifier bags: Python keywords +
        // ubiquitous receiver names, run through the SAME `tokenize` as the
        // bags themselves so the exclusion matches post-stemming forms.
        let kw_excl: HashSet<String> = if sibling_sim > 0.0 {
            tokenize(
                "def class return yield lambda import from raise except finally global \
                 nonlocal assert while break continue pass else elif for with try del \
                 not and await async self cls none true false",
            )
            .into_iter()
            .collect()
        } else {
            HashSet::new()
        };

        for (rel, si) in &pass1_orig_idx {
            let seed = &candidates[*si];
            let seed_span = seed.span;
            // Spans already seated for this file (seed + accepted siblings):
            // a queued sibling overlapping any of them is skipped -- nested
            // python_blocks spans (class + its own methods) would otherwise
            // double-seat the same lines.
            let mut occupied: Vec<(usize, usize)> = vec![seed_span];

            // Same-file sibling pool: the ranked candidates (minus the seed)
            // plus this file's sibling-only `extra_cands` (zero-query-term
            // spans the ranked passes never see). Order is deterministic:
            // construction order of each vector, ranked candidates first.
            let pool: Vec<&Candidate> = candidates
                .iter()
                .enumerate()
                .filter(|(i, c)| i != si && &c.file == rel)
                .map(|(_, c)| c)
                .chain(extra_cands.iter().filter(|c| &c.file == rel))
                .collect();
            if pool.is_empty() {
                continue;
            }

            // Ordered additions: E19 family members first (nameable-family
            // membership is the higher-precision signal), then E18's
            // similarity ranking over whatever E19 didn't already queue.
            let mut queue: Vec<usize> = Vec::new();

            if family_enum && rel.ends_with(".py") {
                let entries = py_family_def_entries(&corpus.text[rel]);
                // A span's primary def entry: the FIRST header line falling
                // inside it (same "earliest header wins" rule as
                // `region_symbol`) -- a class span maps to the class header,
                // a method span to its own def.
                let primary = |a: usize, b: usize| entries.iter().position(|e| e.line >= a && e.line <= b);
                if let Some(sei) = primary(seed_span.0, seed_span.1) {
                    let se = &entries[sei];
                    let segs = name_segments(&se.name);
                    // Family definitions, all requiring the seed to BE a member:
                    //   exact: same def name elsewhere in the file (method
                    //          sweeps across sibling classes), >= 2 total;
                    //   prefix/suffix: shared first/last name segment
                    //          (>= 3 chars), >= FAMILY_MIN_AFFIX members.
                    let exact_ok = !se.is_class
                        && entries.iter().filter(|e| !e.is_class && e.name == se.name).count() >= 2;
                    let prefix_key: Option<String> =
                        segs.first().filter(|s| s.chars().count() >= 3).cloned();
                    let suffix_key: Option<String> = if segs.len() >= 2 {
                        segs.last().filter(|s| s.chars().count() >= 3).cloned()
                    } else {
                        None
                    };
                    let affix_count = |is_prefix: bool, key: &str| {
                        entries
                            .iter()
                            .filter(|e| {
                                let s = name_segments(&e.name);
                                if is_prefix {
                                    s.first().map(|x| x == key).unwrap_or(false)
                                } else {
                                    s.len() >= 2 && s.last().map(|x| x == key).unwrap_or(false)
                                }
                            })
                            .count()
                    };
                    let prefix_ok = prefix_key
                        .as_deref()
                        .map(|k| affix_count(true, k) >= FAMILY_MIN_AFFIX)
                        .unwrap_or(false);
                    let suffix_ok = suffix_key
                        .as_deref()
                        .map(|k| affix_count(false, k) >= FAMILY_MIN_AFFIX)
                        .unwrap_or(false);

                    if exact_ok || prefix_ok || suffix_ok {
                        // (pool idx, |start distance to seed|): nearest
                        // members win the FAMILY_CAP, ties by ascending start.
                        let mut fam: Vec<(usize, usize)> = Vec::new();
                        for (ci, c) in pool.iter().enumerate() {
                            let (a, b) = c.span;
                            if let Some(pi) = primary(a, b) {
                                if pi == sei {
                                    continue; // another span of the seed's own def
                                }
                                let e = &entries[pi];
                                let member = (exact_ok && !e.is_class && e.name == se.name)
                                    || (prefix_ok
                                        && name_segments(&e.name).first() == prefix_key.as_ref())
                                    || (suffix_ok && {
                                        let s = name_segments(&e.name);
                                        s.len() >= 2 && s.last() == suffix_key.as_ref()
                                    });
                                if member {
                                    let d = (a as i64 - seed_span.0 as i64).unsigned_abs() as usize;
                                    fam.push((ci, d));
                                }
                            }
                        }
                        fam.sort_by(|x, y| {
                            x.1.cmp(&y.1).then(pool[x.0].span.0.cmp(&pool[y.0].span.0))
                        });
                        queue.extend(fam.into_iter().take(FAMILY_CAP).map(|(ci, _)| ci));
                    }
                }
            }

            if sibling_sim > 0.0 {
                let seed_bag = sibling_token_bag(&seed.text, &kw_excl);
                if !seed_bag.is_empty() {
                    // Precompute every similarity exactly once, then sort the
                    // snapshot (total_cmp) -- same "no comparator
                    // recomputation" discipline as pass 2's marginal cache.
                    let mut scored: Vec<(usize, f64)> = Vec::new();
                    for (ci, c) in pool.iter().enumerate() {
                        if queue.contains(&ci) {
                            continue;
                        }
                        let sim = sibling_bag_overlap(&seed_bag, &sibling_token_bag(&c.text, &kw_excl));
                        if sim >= sibling_sim {
                            scored.push((ci, sim));
                        }
                    }
                    scored.sort_by(|a, b| {
                        b.1.total_cmp(&a.1).then(pool[a.0].span.0.cmp(&pool[b.0].span.0))
                    });
                    queue.extend(scored.into_iter().take(max_siblings).map(|(ci, _)| ci));
                }
            }

            for ci in queue {
                let c = pool[ci];
                if occupied.iter().any(|o| c.span.0 <= o.1 && o.0 <= c.span.1) {
                    continue;
                }
                if spent + c.tok as i64 > budget_tokens {
                    continue; // budget-checked like pass 2: skip, never force-seat
                }
                spent += c.tok as i64;
                covered.extend(c.terms.iter().cloned());
                occupied.push(c.span);
                let seg_idx = all_segments.len();
                all_segments.push(Candidate {
                    file: c.file.clone(),
                    span: c.span,
                    tok: c.tok,
                    terms: c.terms.clone(),
                    gain: c.gain,
                    text: c.text.clone(),
                    name_score: c.name_score,
                    tok_pow: c.tok_pow,
                });
                chosen_map.entry(rel.clone()).or_default().push(seg_idx);
            }
        }
    }

    // pass 2: greedy marginal coverage over the ORIGINAL candidates minus
    // whichever became the pass-1 pick per file (Python compares dicts by
    // identity/equality against the `chosen` accumulator; here we track by
    // (file, span) identity, which uniquely determines a Python candidate
    // dict too since span+file is the natural key for this list).
    // NOTE: despite the historical name, this set now covers every span
    // seated so far -- pass-1 picks AND (when the E18/E19 flags are on)
    // sibling-expansion seats, both of which must be excluded from the
    // pass-2 pool. With the flags off it is exactly the pass-1 pick set.
    let pass1_keys: HashSet<(String, (usize, usize))> = chosen_map
        .iter()
        .flat_map(|(f, idxs)| idxs.iter().map(|&i| (f.clone(), all_segments[i].span)))
        .collect();
    let mut remaining: Vec<usize> = candidates
        .iter()
        .enumerate()
        .filter(|(_, c)| {
            // A pass-1 pick may have been re-spanned (trimmed); only the
            // untrimmed original candidate remains eligible for pass 2 if
            // it wasn't the one chosen (same file+span as an ORIGINAL
            // candidate is excluded only if it's literally the chosen one).
            !pass1_keys.contains(&(c.file.clone(), c.span))
        })
        .map(|(i, _)| i)
        .collect();

    while !remaining.is_empty() && spent < budget_tokens {
        let marginal = |i: usize| -> f64 {
            let c = &candidates[i];
            let diff: HashSet<String> = c.terms.difference(&covered).cloned().collect();
            let new_weight = weight(&diff);
            let base = (new_weight + 0.25 * weight(&c.terms) + 0.1) * (0.3 + scores.get(&c.file).copied().unwrap_or(0.0))
                / c.tok_pow;
            // same undiluted-by-size name bonus as pass 1's selection metric
            // (see pack_regions' doc comment) -- otherwise a name-anchored
            // region too large to win pass 1 could never win pass 2's
            // marginal race either.
            base + w_name * c.name_score
        };
        // total_cmp, not partial_cmp().unwrap(): `marginal` folds in
        // `scores.get(&c.file)`, an externally-supplied score that isn't
        // guaranteed NaN-free (a caller-side idf/normalization bug upstream
        // could hand pack_regions a NaN here), and partial_cmp().unwrap()
        // panics ("called `Option::unwrap()` on a `None` value") the
        // instant a NaN is compared against anything. total_cmp gives a
        // deterministic, non-panicking total order and agrees with
        // partial_cmp on every finite, non-NaN input, so this is a pure
        // hardening for real inputs, not a ranking change.
        //
        // Root cause of issue #14's resurfacing (E1, blocks mode): `marginal`
        // builds a FRESH `diff` HashSet on every call and sums IDF floats over
        // its iteration order. A brand-new HashSet's bucket layout (and thus
        // iteration order) is not guaranteed stable across separate
        // instantiations, so two calls to `marginal(i)` for the very same
        // candidate `i` within a single sort can return float-epsilon-different
        // values. That makes the comparator not a deterministic function of
        // its inputs, which `total_cmp` cannot fix (it only removes the NaN
        // panic; a comparator that isn't a pure function of (a, b) can still
        // violate transitivity/antisymmetry and trip Rust's sort's internal
        // "does not correctly implement a total order" panic). Snapshot every
        // remaining candidate's marginal score exactly once per greedy
        // iteration and sort that cache instead: this also cuts evaluations
        // from O(n log n) to O(n) per iteration.
        let scored: Vec<(usize, f64)> = remaining.iter().map(|&i| (i, marginal(i))).collect();
        remaining = {
            let mut scored = scored;
            scored.sort_by(|a, b| b.1.total_cmp(&a.1));
            scored.into_iter().map(|(i, _)| i).collect()
        };
        let i = remaining.remove(0);
        let tok = candidates[i].tok as i64;
        if spent + tok > budget_tokens {
            if candidates[i].tok > 200 {
                continue;
            }
            break;
        }
        spent += tok;
        covered.extend(candidates[i].terms.iter().cloned());
        let file = candidates[i].file.clone();
        let seg_idx = all_segments.len();
        all_segments.push(Candidate {
            file: candidates[i].file.clone(),
            span: candidates[i].span,
            tok: candidates[i].tok,
            terms: candidates[i].terms.clone(),
            gain: candidates[i].gain,
            text: candidates[i].text.clone(),
            name_score: candidates[i].name_score,
            tok_pow: candidates[i].tok_pow,
        });
        chosen_map.entry(file).or_default().push(seg_idx);
    }

    if pad_lines == 0 {
        // pre-E12 path, byte-identical.
        let mut parts: Vec<String> = Vec::new();
        let mut spans_out: IndexMap<String, Vec<(usize, usize)>> = IndexMap::new();
        for rel in files {
            let idxs = match chosen_map.get(rel) {
                Some(v) if !v.is_empty() => v,
                _ => continue,
            };
            let mut segs: Vec<&Candidate> = idxs.iter().map(|&i| &all_segments[i]).collect();
            segs.sort_by_key(|c| c.span.0);
            spans_out.insert(rel.clone(), segs.iter().map(|c| c.span).collect());
            let body = segs.iter().map(|c| c.text.as_str()).collect::<Vec<_>>().join("\n...\n");
            parts.push(format!("### {rel}\n{body}"));
        }
        return (spans_out, parts.join("\n\n"));
    }

    // ---------------------------------------------------------------- E12: span padding
    //
    // Motivated by the E7 miss autopsy: 14% of gold lines are missed within
    // +-20 lines of a returned span (61% within 10) while measured
    // precision is ~0.45%, so the marginal lines padding pulls in are
    // overwhelmingly noise already -- padding is expected to convert most
    // of that near-miss mass to captured at low cost.
    //
    // Each ORIGINALLY selected span (from both passes above) is extended by
    // up to `pad_lines` lines in each direction, clamped to the file's own
    // line count (this also subsumes the pre-existing pass-1
    // per-file-cap-trim quirk where a reported span's end can already
    // exceed the file's true line count -- clamping against `n_lines` here
    // fixes that up too). Same-file padded spans that now overlap OR touch
    // (gap 0) are merged into one, pooling their gains. `text`/`tok` are
    // re-derived from the padded/merged span's actual file lines (the
    // original candidate's `text` only ever covered the UNpadded lines).
    struct PaddedSpan {
        file: String,
        span: (usize, usize),
        text: String,
        tok: i64,
        gain: f64,
        /// True if any origin merged into this padded span was a pass-1
        /// pick: such spans are EXEMPT from the fallback whole-span
        /// eviction below (see the guard's invariant comment).
        pass1: bool,
    }

    // Each originally-selected span (pass 1 or pass 2) keeps its OWN,
    // independently adjustable pad amount -- initialized to `pad_lines` for
    // every span, but see the de-escalation guard (E12b) below, which can
    // shave individual spans' pads back down toward 0 before ever evicting
    // a whole span/file.
    struct OriginSpan {
        span: (usize, usize),
        gain: f64,
        pad: i64,
        /// Seated by pass 1 (one unconditional span per file, which includes
        /// every anchor-forced span -- `forced` only ever feeds pass-1
        /// picks). Pass-1 origins are exempt from whole-span eviction.
        pass1: bool,
    }

    let mut origins: Vec<OriginSpan> = Vec::new();
    let mut by_file_idx: IndexMap<String, Vec<usize>> = IndexMap::new();
    for rel in files {
        let idxs = match chosen_map.get(rel) {
            Some(v) if !v.is_empty() => v,
            _ => continue,
        };
        for &i in idxs {
            let c = &all_segments[i];
            let oi = origins.len();
            origins.push(OriginSpan { span: c.span, gain: c.gain, pad: pad_lines as i64, pass1: i < pass1_seg_count });
            by_file_idx.entry(rel.clone()).or_default().push(oi);
        }
    }

    // Pad + same-file merge, driven by each origin's CURRENT `pad` (not a
    // single global constant): re-derivable at any point during
    // de-escalation, so the guard loop below can call this repeatedly as it
    // shaves individual origins' pads down. Deterministic merge order: sort
    // by padded start once per call (a single, precomputed pass -- no
    // per-merge-iteration comparator recomputation), ties broken by padded
    // end.
    let build_padded = |origins: &[OriginSpan]| -> Vec<PaddedSpan> {
        let mut out: Vec<PaddedSpan> = Vec::new();
        for rel in files {
            let idxs = match by_file_idx.get(rel) {
                Some(v) if !v.is_empty() => v,
                _ => continue,
            };
            let full_lines = py_splitlines(&corpus.text[rel]);
            let n_lines = full_lines.len();

            let mut raw: Vec<((usize, usize), f64, bool)> = idxs
                .iter()
                .map(|&i| {
                    let o = &origins[i];
                    let (a, b) = o.span;
                    let pad = o.pad;
                    let pa = ((a as i64 - pad).max(1)) as usize;
                    let pb = ((b as i64 + pad).min(n_lines as i64).max(1)) as usize;
                    ((pa, pb), o.gain, o.pass1)
                })
                .collect();
            raw.sort_by(|a, b| a.0.cmp(&b.0));

            let mut merged: Vec<((usize, usize), f64, bool)> = Vec::new();
            for (span, gain, pass1) in raw {
                if let Some(last) = merged.last_mut() {
                    if span.0 <= last.0 .1 + 1 {
                        last.0 .1 = last.0 .1.max(span.1);
                        last.1 += gain;
                        // A merged span containing ANY pass-1 origin
                        // inherits the eviction exemption -- evicting the
                        // merge would drop pass-1 content with it.
                        last.2 |= pass1;
                        continue;
                    }
                }
                merged.push((span, gain, pass1));
            }

            for ((a, b), gain, pass1) in merged {
                let start = a.saturating_sub(1).min(n_lines);
                let end = b.min(n_lines);
                let text = if start < end { full_lines[start..end].join("\n") } else { String::new() };
                let tok = count_tokens(&text) as i64;
                out.push(PaddedSpan { file: rel.clone(), span: (a, b), text, tok, gain, pass1 });
            }
        }
        out
    };

    let mut padded: Vec<PaddedSpan> = build_padded(&origins);
    let mut total: i64 = padded.iter().map(|p| p.tok).sum();

    // E12b guard: de-escalate padding before ever evicting a whole span.
    //
    // If the padded bundle exceeds budget, shrink padding one line at a
    // time on the LOWEST-gain origin span first, fully draining it back to
    // pad=0 before touching the next-lowest-gain one, re-measuring the
    // total after every single-line shave (`gain` is fixed per origin --
    // precomputed once, never recomputed here -- so this priority order is
    // itself computed exactly once, up front, same "no comparator
    // recomputation" discipline as pass 2's `marginal` cache and the
    // eviction sort below). This is deliberately the coarsest-grained
    // origin ever touched at each step: the cheapest span gives up ALL its
    // padding before a more valuable span gives up any, which maximizes how
    // much padding the bundle keeps overall for a given budget.
    //
    // INVARIANT (E12b, hardened): the guard promises that the FILE SET
    // never shrinks versus the pad=0 selection. Note the pad=0 bundle does
    // NOT necessarily fit budget by construction -- pass 1 seats one span
    // per file UNCONDITIONALLY (no budget check on its `spent +=`; only
    // pass 2 is budget-checked), so with enough files even the fully
    // unpadded bundle can exceed `budget_tokens` (e.g. 25 files at budget
    // 800), exactly as the pre-E12 pad=0 path could overshoot. De-escalation
    // therefore is NOT guaranteed to converge to a fitting bundle; when it
    // doesn't, the fallback below may evict pass-2 spans, but pass-1 origin
    // spans (one per selected file, including every anchor-forced span) are
    // structurally EXEMPT from eviction -- which is what actually enforces
    // the file-set invariant at every budget. If the bundle still exceeds
    // budget once every pad is drained and every evictable pass-2 span is
    // gone, it overshoots, exactly as the pad=0 path always has.
    if total > budget_tokens && !origins.is_empty() {
        let mut order: Vec<usize> = (0..origins.len()).collect();
        order.sort_by(|&i, &j| origins[i].gain.total_cmp(&origins[j].gain).then(i.cmp(&j)));
        'deescalate: for oi in order {
            while origins[oi].pad > 0 {
                origins[oi].pad -= 1;
                padded = build_padded(&origins);
                total = padded.iter().map(|p| p.tok).sum();
                if total <= budget_tokens {
                    break 'deescalate;
                }
            }
        }
    }

    // Fallback eviction: only reached if the bundle STILL exceeds budget
    // once every origin span has been de-escalated all the way to pad=0
    // (i.e. even the unpadded selection doesn't fit -- possible, since
    // pass 1 seats unconditionally; see the invariant comment above). Drop
    // WHOLE evictable padded spans (never truncate one mid-way)
    // lowest-gain-first until it fits, where "evictable" excludes any span
    // containing a pass-1 origin: pass-1 spans are the pad=0 file set
    // (every selected file has exactly one, and anchor-forced spans are
    // pass-1 picks too), so exempting them is what makes the guard's
    // file-set invariant hold at every budget. If only exempt spans remain
    // and the bundle is still over budget, it is returned overshooting --
    // the same overshoot the pad=0 path (and the pre-adoption engine)
    // produces on such inputs. Eviction order is a single precomputed sort
    // over the (already precomputed, unchanging) per-span `gain` -- exactly
    // the "no comparator recomputation" pass-2's `marginal` closure had to
    // be hardened against (see above): here there is nothing to recompute
    // per eviction, `gain` was fixed the moment each span was built.
    // `total_cmp` (not `partial_cmp().unwrap()`) for the same
    // NaN/inf-hardening reason as every other score sort in this function.
    // Ties keep `padded`'s own build order (files' order, then ascending
    // span-start within a file) via `sort_by`'s stability.
    let mut evicted = vec![false; padded.len()];
    if total > budget_tokens {
        let mut order: Vec<usize> = (0..padded.len()).collect();
        order.sort_by(|&i, &j| padded[i].gain.total_cmp(&padded[j].gain));
        for i in order {
            if total <= budget_tokens {
                break;
            }
            if padded[i].pass1 {
                continue;
            }
            total -= padded[i].tok;
            evicted[i] = true;
        }
    }
    let padded: Vec<PaddedSpan> =
        padded.into_iter().zip(evicted).filter(|(_, ev)| !*ev).map(|(p, _)| p).collect();

    let mut by_file: IndexMap<String, Vec<&PaddedSpan>> = IndexMap::new();
    for p in &padded {
        by_file.entry(p.file.clone()).or_default().push(p);
    }
    let mut parts: Vec<String> = Vec::new();
    let mut spans_out: IndexMap<String, Vec<(usize, usize)>> = IndexMap::new();
    for rel in files {
        let specs = match by_file.get(rel) {
            Some(v) if !v.is_empty() => v,
            _ => continue,
        };
        spans_out.insert(rel.clone(), specs.iter().map(|p| p.span).collect());
        let body = specs.iter().map(|p| p.text.as_str()).collect::<Vec<_>>().join("\n...\n");
        parts.push(format!("### {rel}\n{body}"));
    }
    (spans_out, parts.join("\n\n"))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 20+ fixtures generated from the Python reference:
    ///   PYTHONHASHSEED=0 uv run --project <archex venv> python3 -c
    ///     "import sys; sys.path.insert(0, '<repo>/lab'); import lanes2 as L;
    ///      print(L.stem('validators'))"  # etc.
    #[test]
    fn stem_matches_python_reference() {
        let cases: &[(&str, &str)] = &[
            ("validators", "validat"),
            ("validate", "validat"),
            ("dependencies", "dependenci"),
            ("dependency", "dependenci"),
            ("routing", "rout"),
            ("route", "rout"),
            ("router", "rout"),
            ("classes", "class"),
            ("glasses", "glass"),
            ("passes", "pass"),
            ("runs", "run"),
            ("running", "runn"),
            ("tested", "test"),
            ("tester", "test"),
            ("collector", "collect"),
            ("monitor", "monit"),
            ("factory", "factori"),
            ("category", "categori"),
            ("type", "type"),
            ("name", "name"),
            ("service", "servic"),
            ("using", "using"),
            ("handled", "handl"),
        ];
        for (input, expected) in cases {
            assert_eq!(stem(input), *expected, "stem({input:?})");
        }
    }

    /// Subtoken splitter fixtures (camelCase/snake_case boundary cases),
    /// generated from `lanes2.subtokens()` via the same archex venv.
    #[test]
    fn subtokens_matches_python_reference() {
        let cases: &[(&str, &[&str])] = &[
            ("HTTPResponse", &["http", "respons"]),
            ("parseHTTPResponse2", &["pars", "http", "respons"]),
            ("snake_case_name", &["snak", "case", "name"]),
            ("XMLHttpRequest", &["xml", "http", "request"]),
            ("A", &[]),
            ("ABc", &[]),
            ("alreadylower", &["alreadylow"]),
        ];
        for (input, expected) in cases {
            assert_eq!(subtokens(input), *expected, "subtokens({input:?})");
        }
    }

    /// tokenize() on 5 code snippets (Python/Go/JS/Rust/import-statement
    /// styles), generated from `lanes2.tokenize()` via the archex venv.
    #[test]
    fn tokenize_matches_python_reference() {
        let snippet0 = "def parseHTTPResponse2(self, data):\n    validators = self.get_validators()\n    return validators";
        assert_eq!(
            tokenize(snippet0),
            vec!["parsehttpresponse2", "pars", "http", "respons", "data", "validat", "get_validat", "get", "validat", "validat"]
        );

        let snippet1 = "class ConnectionPool:\n    def __init__(self):\n        self.routing_table = {}\n    def get_router(self):\n        pass";
        assert_eq!(
            tokenize(snippet1),
            vec!["connectionpool", "connection", "pool", "__init__", "init", "routing_tabl", "rout", "tabl", "get_rout", "get", "rout", "pass"]
        );

        let snippet2 = "function XMLHttpRequestHandler(req, res) {\n    const dependency_graph = buildGraph();\n    return dependency_graph;\n}";
        assert_eq!(
            tokenize(snippet2),
            vec![
                "xmlhttprequesthandl", "xml", "http", "request", "handl", "req", "res", "dependency_graph",
                "dependenci", "graph", "buildgraph", "build", "graph", "dependency_graph", "dependenci", "graph"
            ]
        );

        let snippet3 = "// snake_case_name test\nstruct HTTPClient {\n    keep_alive: bool,\n}";
        assert_eq!(
            tokenize(snippet3),
            vec!["snake_case_nam", "snak", "case", "name", "test", "httpclient", "http", "client", "keep_aliv", "keep", "aliv"]
        );

        let snippet4 = "import os\nfrom collections import defaultdict\n# a comment about testing\n";
        assert_eq!(tokenize(snippet4), vec!["collection", "defaultdict", "comment", "about", "test"]);
    }

    #[test]
    fn tokenize_already_lower() {
        assert_eq!(tokenize("already lower"), vec!["alreadi", "lower"]);
    }

    /// impl_prior() path classification, generated from
    /// `lanes2.impl_prior()` via the archex venv.
    #[test]
    fn impl_prior_matches_python_reference() {
        let cases: &[(&str, f64)] = &[
            ("src/main.py", 1.0),
            ("tests/test_main.py", 0.3),
            ("test_foo.py", 0.3),
            ("foo_test.py", 0.3),
            ("docs/index.md", 0.3),
            ("examples/demo.py", 0.3),
            ("lib/router.rs", 1.0),
            ("benches/bench_x.rs", 0.3),
            ("a/b/conftest.py", 0.3),
            ("spec/foo.spec.js", 0.3),
            ("foo.test.js", 0.3),
            ("vendor/x.js", 1.0),
            ("node_modules/y.js", 1.0),
            ("src/t/z.py", 0.3),
        ];
        for (path, expected) in cases {
            assert_eq!(impl_prior(path), *expected, "impl_prior({path:?})");
        }
    }

    /// Region-name-anchoring fix: `_file_def_lines`/`_region_symbol` fixtures
    /// generated from `lanes2._file_def_lines`/`_region_symbol` (also ported
    /// verbatim into src/roust/core.py) via the archex venv.
    #[test]
    fn file_def_lines_and_region_symbol_match_python_reference() {
        let text = "import os\n\n\ndef alpha(x):\n    return x\n\n\nclass Beta:\n    def gamma(self):\n        pass\n";
        let def_lines = file_def_lines(text, def_re_for("mod.py"));
        assert_eq!(
            def_lines,
            vec![(4, "alpha".to_string()), (8, "Beta".to_string()), (9, "gamma".to_string())]
        );
        assert_eq!(region_symbol(&def_lines, 1, 5), Some("alpha"));
        assert_eq!(region_symbol(&def_lines, 8, 10), Some("Beta"));
        assert_eq!(region_symbol(&def_lines, 9, 10), Some("gamma"));
        assert_eq!(region_symbol(&def_lines, 20, 30), None);
    }

    /// `_name_score` fixtures generated from `lanes2._name_score` (also
    /// ported verbatim into src/roust/core.py) via the archex venv.
    #[test]
    fn name_score_matches_python_reference() {
        let full_match: HashSet<String> = ["pack".to_string(), "region".to_string()].into_iter().collect();
        assert_eq!(name_score(Some("pack_regions"), &full_match), 3.0);

        let no_overlap: HashSet<String> =
            ["token".to_string(), "pack".to_string(), "budget".to_string()].into_iter().collect();
        assert_eq!(name_score(Some("subtokens"), &no_overlap), 0.0);

        let partial: HashSet<String> = ["pack".to_string()].into_iter().collect();
        assert_eq!(name_score(Some("pack_regions"), &partial), 1.0);

        assert_eq!(name_score(None, &full_match), 0.0);
        assert_eq!(name_score(Some("__init__"), &full_match), 0.0);
    }

    /// Dogfood regression (see lab/dogfood_pack_regions.py): a region whose
    /// DEFINING SYMBOL matches query terms must win pass-1 selection over a
    /// same-file region that only has denser body term matches for a
    /// generic term, once `w_name` is on -- and must NOT win when `w_name`
    /// is 0.0 (byte-identical to pre-fix ranking), so this also pins the
    /// pre-fix bug reproduction. budget_tokens=1 isolates pass-1's pick
    /// (pass 2 never runs since `spent >= budget_tokens` immediately after
    /// pass 1, which spends unconditionally regardless of budget).
    #[test]
    fn pack_regions_name_score_promotes_symbol_name_match() {
        let tmp = std::env::temp_dir().join(format!("roust_namescore_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        // subtokens: SHORT region, dense in query terms (token/budget/enforc)
        // -- wins on gain/tok pre-fix. pack_regions: LONG region (40 filler
        // lines) whose only query-term evidence is its own def line
        // ("pack"/"region" from the identifier) -- loses on density despite
        // being the actual query target, exactly the real dogfood bug's
        // shape (a big true-match region diluted by the /tok division).
        let filler: String = (0..40).map(|i| format!("    x{i} = {i}\n")).collect();
        let src = format!(
            "def subtokens(word):\n    \"\"\"token budget enforced.\"\"\"\n    return word.split('_')\n\n\ndef pack_regions(cap):\n{filler}    return cap\n"
        );
        std::fs::write(tmp.join("core.py"), src).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("how is the token budget enforced when packing regions", &[]);
        let scores: IndexMap<String, f64> = [("core.py".to_string(), 1.0)].into_iter().collect();
        let files = vec!["core.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let def_lines = file_def_lines(&corpus.text["core.py"], def_re_for("core.py"));
        let sym_of = |spans: &IndexMap<String, Vec<(usize, usize)>>| -> Option<String> {
            spans["core.py"].first().and_then(|&(a, b)| region_symbol(&def_lines, a, b)).map(|s| s.to_string())
        };

        let (spans_off, _) = pack_regions(&corpus, &files, &terms, &scores, 1, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
        assert_eq!(sym_of(&spans_off), Some("subtokens".to_string()), "pre-fix (w_name=0.0) reproduces the bug: body term-density picks the wrong region");

        let (spans_on, _) = pack_regions(&corpus, &files, &terms, &scores, 1, &count_tokens, None, 1.0, 0, 1.0, false, 0.0, 3, false);
        assert_eq!(sym_of(&spans_on), Some("pack_regions".to_string()), "w_name=1.0 must select pack_regions via name-score anchoring");

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// E14 directional fixture: a 3-line stub (`stub_widget`, one query
    /// term hit -- "widget") competes against a 30-line real function
    /// (`real_gadget_sprocket_cog_lever`, all 4 query terms present and
    /// repeated throughout the body) in the SAME file, so pass 1's per-file
    /// `max` fold picks between them directly. `budget_tokens=1` isolates
    /// pass 1 (mirrors `pack_regions_name_score_promotes_symbol_name_match`
    /// above): pass 1 always spends unconditionally, so `spent >=
    /// budget_tokens` immediately afterward and pass 2 never runs.
    ///
    /// At `len_exp=1.0` (default, pre-E14 `gain/tok` ranking) the stub wins
    /// -- exactly the E13 case-mining failure mode this experiment targets
    /// (a short lucky-term-match stub outranks a long real, densely-
    /// on-topic function purely because of the linear `/tok` length
    /// penalty). At `len_exp=0.7`, softening that penalty lets the real
    /// function's 4x term coverage win instead. The actual crossover for
    /// this fixture (probed empirically) falls between len_exp=0.79 (real
    /// wins) and len_exp=0.80 (stub still wins).
    #[test]
    fn pack_regions_len_exp_shifts_selection_toward_longer_real_function() {
        let tmp = std::env::temp_dir().join(format!("roust_e14_crossover_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let stub = "def stub_widget(x):\n    # widget\n    return x\n";
        let mut real = String::new();
        real.push_str("def real_gadget_sprocket_cog_lever(a, b, c, d):\n");
        real.push_str("    \"\"\"widget gadget sprocket cog\"\"\"\n");
        real.push_str("    widget = a\n");
        real.push_str("    gadget = b\n");
        real.push_str("    sprocket = c\n");
        real.push_str("    cog = d\n");
        for i in 0..23 {
            let term = ["widget", "gadget", "sprocket", "cog"][i % 4];
            real.push_str(&format!("    tmp_{i} = {term} + {i}\n"));
        }
        real.push_str("    return widget + gadget + sprocket + cog\n");
        assert_eq!(real.lines().count(), 30, "fixture must be a 30-line real function");
        let src = format!("{stub}\n\n{real}");
        std::fs::write(tmp.join("mod.py"), &src).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("widget gadget sprocket cog", &[]);
        let scores: IndexMap<String, f64> = [("mod.py".to_string(), 1.0)].into_iter().collect();
        let files = vec!["mod.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let def_lines = file_def_lines(&corpus.text["mod.py"], def_re_for("mod.py"));
        let sym_of = |spans: &IndexMap<String, Vec<(usize, usize)>>| -> Option<String> {
            spans["mod.py"].first().and_then(|&(a, b)| region_symbol(&def_lines, a, b)).map(|s| s.to_string())
        };

        let (spans_linear, _) = pack_regions(&corpus, &files, &terms, &scores, 1, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
        assert_eq!(
            sym_of(&spans_linear),
            Some("stub_widget".to_string()),
            "len_exp=1.0 (pre-E14 linear gain/tok) must reproduce the crushed-long-fix failure mode: stub wins"
        );

        let (spans_softened, _) = pack_regions(&corpus, &files, &terms, &scores, 1, &count_tokens, None, 0.0, 0, 0.7, false, 0.0, 3, false);
        assert_eq!(
            sym_of(&spans_softened),
            Some("real_gadget_sprocket_cog_lever".to_string()),
            "len_exp=0.7 must flip the pick to the longer, more densely on-topic real function"
        );

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// Regression for issue #14: pack_regions' pass-2 greedy loop sorts
    /// `remaining` candidates by a `marginal` score that folds in a
    /// caller-supplied `scores` entry per file. If that score is NaN (e.g.
    /// upstream normalization/idf drift), the pre-fix
    /// `partial_cmp().unwrap()` comparator panics the instant the NaN
    /// candidate is compared against anything. Assert pack_regions instead
    /// completes without panicking and produces a deterministic ordering
    /// (same spans across repeated calls with the same NaN input).
    #[test]
    fn pack_regions_survives_nan_and_inf_scores() {
        let tmp = std::env::temp_dir().join(format!("roust_nanscore_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let filler: String = (0..20).map(|i| format!("    x{i} = {i}\n")).collect();
        std::fs::write(
            &tmp.join("a.py"),
            format!("def alpha_token():\n{filler}    return 1\n\n\ndef beta_budget():\n{filler}    return 2\n"),
        )
        .unwrap();
        std::fs::write(
            &tmp.join("b.py"),
            format!("def gamma_token():\n{filler}    return 3\n\n\ndef delta_budget():\n{filler}    return 4\n"),
        )
        .unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("token budget", &[]);
        let files = vec!["a.py".to_string(), "b.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        // NaN and +inf scores, directly on the pack_regions contract (a
        // caller-supplied score map), not manufactured via any specific
        // upstream idf/normalization path.
        let scores: IndexMap<String, f64> =
            [("a.py".to_string(), f64::NAN), ("b.py".to_string(), f64::INFINITY)].into_iter().collect();

        // Large budget so pass 2's greedy loop actually runs over multiple
        // remaining candidates (pass 1 alone would only ever touch one span
        // per file).
        let (spans1, _) = pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
        let (spans2, _) = pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
        assert_eq!(spans1, spans2, "pack_regions must be deterministic given identical (NaN/inf-bearing) inputs");
        assert!(!spans1.is_empty(), "pack_regions should still select regions despite NaN/inf scores");

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// Determinism regression for issue #14's TRUE root cause, which
    /// resurfaced under the E1 blocks-mode experiment (panics on
    /// sympy__sympy-17139 and sympy__sympy-21171): pass-2's `marginal`
    /// closure built a FRESH `diff` HashSet on every call and summed IDF
    /// floats over that set's iteration order. A brand-new HashSet's
    /// bucket layout isn't guaranteed stable across separate
    /// instantiations, so two calls to `marginal(i)` for the very same
    /// candidate `i`, within a SINGLE sort, could return float-epsilon-
    /// different values -- a comparator that isn't a deterministic
    /// function of its inputs, which `total_cmp` alone cannot fix (it only
    /// removes the NaN-panic case; a comparator that returns inconsistent
    /// answers for the same pair can still violate transitivity and trip
    /// sort's "does not correctly implement a total order" panic). Fifty
    /// candidates sharing the exact same query-term content maximize the
    /// number of equal/near-equal marginal scores pass-2 must rank in one
    /// sort, which is the shape that exposed the bug. Assert repeated
    /// calls with identical inputs never panic and produce byte-identical
    /// (same file, same spans, in order) output.
    #[test]
    fn pack_regions_deterministic_with_many_equal_marginal_scores() {
        let tmp = std::env::temp_dir().join(format!("roust_detfix_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        // 50 functions with identical bodies/docstrings (only the def name
        // and return value vary): every candidate's `terms` HashSet is the
        // same "token"/"budget"/"enforc" set, so pass-2's marginal scores
        // for them cluster into ties/near-ties.
        let mut src = String::new();
        for i in 0..50 {
            src.push_str(&format!("def fn_{i}(x):\n    \"\"\"token budget enforced.\"\"\"\n    return x + {i}\n\n\n"));
        }
        std::fs::write(tmp.join("many.py"), &src).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("how is the token budget enforced", &[]);
        let files = vec!["many.py".to_string()];
        let scores: IndexMap<String, f64> = [("many.py".to_string(), 1.0)].into_iter().collect();
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        // Large budget so pass 2's greedy loop actually runs over many
        // remaining candidates per iteration -- the exact scenario that
        // triggers repeated `marginal(i)` calls for the same `i` within a
        // single sort.
        let (first, _) = pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
        assert!(!first.is_empty());
        for _ in 0..10 {
            let (spans, _) = pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
            assert_eq!(
                spans, first,
                "pack_regions must produce byte-identical spans across repeated calls given many equal/near-equal marginal scores (and must never panic)"
            );
        }

        std::fs::remove_dir_all(&tmp).ok();
    }

    // ---------------------------------------------------------------- E12:
    // span padding (--pad-lines)

    /// `pad_lines=0` (default) must reproduce the pre-E12 code path exactly,
    /// including its "no merge" quirk: `alpha_needle`'s and `beta_needle`'s
    /// python_blocks spans are naturally ADJACENT (block partitioning
    /// leaves no gap between consecutive top-level defs -- span1=(1,5),
    /// span2=(6,8), see `python_blocks`), so if the default path were
    /// accidentally routed through any merge logic they'd collapse into
    /// one entry. Golden check that they do NOT: two separate span entries
    /// for the file, byte-identical to before E12 existed.
    #[test]
    fn pack_regions_pad_lines_zero_keeps_adjacent_spans_unmerged_golden() {
        let tmp = std::env::temp_dir().join(format!("roust_pad_zero_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        std::fs::write(
            tmp.join("needles.py"),
            "def alpha_needle(x):\n    \"\"\"token budget marker alpha.\"\"\"\n    return x\n\n\ndef beta_needle(y):\n    \"\"\"token budget marker beta.\"\"\"\n    return y\n",
        )
        .unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("alpha beta token budget marker needle", &[]);
        let scores: IndexMap<String, f64> = [("needles.py".to_string(), 1.0)].into_iter().collect();
        let files = vec!["needles.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let (spans, _) = pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
        let got = &spans["needles.py"];
        assert_eq!(got, &vec![(1, 5), (6, 8)], "pad_lines=0 must keep the two naturally-adjacent spans as separate, unmerged entries (pre-E12 behavior)");

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// `pad_lines>0` correctness: the same naturally-adjacent two-span
    /// fixture above, but with `pad_lines=1`. Each span, padded by 1 line in
    /// each direction, now overlaps the other (span1 (1,5)->(1,6), span2
    /// (6,8)->(5,8), and 5<=6+1) and must merge into a single (1,8) span
    /// covering the whole 8-line file.
    #[test]
    fn pack_regions_pad_lines_merges_adjacent_spans() {
        let tmp = std::env::temp_dir().join(format!("roust_pad_merge_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let src = "def alpha_needle(x):\n    \"\"\"token budget marker alpha.\"\"\"\n    return x\n\n\ndef beta_needle(y):\n    \"\"\"token budget marker beta.\"\"\"\n    return y\n";
        std::fs::write(tmp.join("needles.py"), src).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("alpha beta token budget marker needle", &[]);
        let scores: IndexMap<String, f64> = [("needles.py".to_string(), 1.0)].into_iter().collect();
        let files = vec!["needles.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let (spans, bundle) = pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 1, 1.0, false, 0.0, 3, false);
        let got = &spans["needles.py"];
        assert_eq!(got, &vec![(1, 8)], "pad_lines=1 must merge the two adjacent spans into one (1,8) covering the whole file");
        // merged text must be the FULL file content, not a truncated slice.
        let expected_lines: Vec<&str> = src.lines().collect();
        assert!(bundle.contains(&expected_lines.join("\n")), "merged region text must contain every line of the merged span, not a partial slice");

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// Clamping at file edges: a tiny 3-line file with `pad_lines` far
    /// larger than the file itself must clamp to (1, n_lines), never
    /// underflow below line 1 or run past the file's actual last line.
    #[test]
    fn pack_regions_pad_lines_clamps_at_file_bounds() {
        let tmp = std::env::temp_dir().join(format!("roust_pad_clamp_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        std::fs::write(tmp.join("tiny.py"), "def needle(x):\n    \"\"\"token budget marker.\"\"\"\n    return x\n").unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("token budget marker needle", &[]);
        let scores: IndexMap<String, f64> = [("tiny.py".to_string(), 1.0)].into_iter().collect();
        let files = vec!["tiny.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let (spans, _) = pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 500, 1.0, false, 0.0, 3, false);
        assert_eq!(spans["tiny.py"], vec![(1, 3)], "pad_lines far exceeding the file's own length must clamp to (1, n_lines)");

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// Pass-1 eviction exemption (the E12b guard's actual enforcement
    /// mechanism, hardened): two files with byte-identical bodies (so
    /// identical token counts and identical `weight(seg_terms)`/`n_hits`
    /// contribution to `gain`) but different caller-supplied `scores` --
    /// `hi.py` scores 5.0, `lo.py` scores 0.0 -- so `lo.py`'s span has the
    /// strictly lower `gain`. `budget_tokens` is set (dynamically, from the
    /// fixture's own real token count) to fit exactly ONE span but not
    /// both. Both spans are PASS-1 picks (one per file, seated
    /// unconditionally), so even though the fully de-escalated (pad=0)
    /// bundle exceeds budget, NEITHER may be evicted: the pad=0 path
    /// returns both files (overshooting budget), and the guard's invariant
    /// is precisely that padding never shrinks that file set. Pre-fix, this
    /// exact shape evicted `lo.py` (the reviewer's 25-file/budget-800
    /// repro, minimized): the padded path returned fewer files than pad=0.
    /// Assert: both files survive at pad>0, with full untruncated spans,
    /// same as the pad=0 baseline.
    #[test]
    fn pack_regions_pad_lines_pass1_spans_exempt_from_eviction() {
        let tmp = std::env::temp_dir().join(format!("roust_pad_evict_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let body = "def needle(x):\n    \"\"\"token budget marker phrase evict here now.\"\"\"\n    return x\n";
        std::fs::write(tmp.join("hi.py"), body).unwrap();
        std::fs::write(tmp.join("lo.py"), body).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("token budget marker phrase evict needle", &[]);
        let scores: IndexMap<String, f64> =
            [("hi.py".to_string(), 5.0), ("lo.py".to_string(), 0.0)].into_iter().collect();
        let files = vec!["hi.py".to_string(), "lo.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        // T = a single file's own span token count (both files are
        // byte-identical, so this is the same for either) -- budget just
        // above T fits exactly one span but not two (2T), forcing eviction
        // without depending on a hand-counted magic number.
        let t = count_tokens(body.trim_end());
        assert!(t > 5, "fixture body too small for a meaningful eviction margin");
        let budget = (t + 3) as i64;
        assert!(budget < 2 * t as i64, "budget must fall strictly between one span's tokens and two");

        // Tiny `budget_tokens` passed to pack_regions itself doesn't matter
        // for WHICH pass-1 picks get made (pass 1 spends unconditionally,
        // ignoring budget) -- it only gates pass 2 and the post-padding
        // de-escalation/eviction step, so both hi.py and lo.py's pass-1
        // spans are seated before padding/eviction ever runs.
        let (spans0, _) = pack_regions(&corpus, &files, &terms, &scores, budget, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
        assert!(
            spans0.contains_key("hi.py") && spans0.contains_key("lo.py"),
            "pad=0 baseline seats BOTH pass-1 spans (unconditionally), overshooting budget"
        );

        let (spans, _) = pack_regions(&corpus, &files, &terms, &scores, budget, &count_tokens, None, 0.0, 2, 1.0, false, 0.0, 3, false);
        let got: HashSet<&String> = spans.keys().collect();
        let baseline: HashSet<&String> = spans0.keys().collect();
        assert_eq!(
            got, baseline,
            "pass-1 spans are eviction-exempt: the padded file set must equal the pad=0 file set even when the unpadded bundle itself exceeds budget"
        );
        assert_eq!(spans["hi.py"], vec![(1, 3)], "hi.py span must be the full, untruncated 3-line span");
        assert_eq!(spans["lo.py"], vec![(1, 3)], "lo.py span must survive whole (pre-fix it was evicted here), not truncated");

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// The reviewer's live repro, as a fixture: 25 files whose pass-1 spans
    /// alone exceed budget 800 even fully unpadded (pass 1 seats one span
    /// per file unconditionally). Pre-fix, the padded path's fallback
    /// eviction then dropped whole low-gain files, so `--pad-lines 5`
    /// returned FEWER files than `--pad-lines 0` at the same budget --
    /// violating the guard's stated invariant. Post-fix, pass-1 spans are
    /// eviction-exempt: pad=5 must return the same 25 files as pad=0, with
    /// the bundle overshooting budget exactly as the pad=0 path does.
    #[test]
    fn pack_regions_pad_guard_holds_at_small_budget_25_files() {
        let tmp = std::env::temp_dir().join(format!("roust_pad_guard25_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let mut files: Vec<String> = Vec::new();
        for i in 0..25 {
            // ~40 whitespace tokens per selected span so 25 unpadded spans
            // total ~1000 tokens, comfortably past budget 800. Each file
            // matches the query so every one of the 25 is selected.
            let body = format!(
                "def handler_{i}(request):\n    \"\"\"widget frobnicate dispatch pathway number {i} extra filler words alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega\"\"\"\n    return {i}\n"
            );
            let rel = format!("mod_{i:02}.py");
            std::fs::write(tmp.join(&rel), body).unwrap();
            files.push(rel);
        }

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("widget frobnicate dispatch pathway", &[]);
        // Distinct scores so per-span gains are strictly ordered -- the
        // pre-fix eviction had an unambiguous lowest-gain victim.
        let scores: IndexMap<String, f64> =
            files.iter().enumerate().map(|(i, f)| (f.clone(), 0.1 + i as f64 * 0.05)).collect();
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };
        let budget: i64 = 800;

        let (spans0, _) = pack_regions(&corpus, &files, &terms, &scores, budget, &count_tokens, None, 0.0, 0, 0.85, false, 0.0, 3, false);
        assert_eq!(spans0.len(), 25, "pad=0 baseline must select all 25 files (pass 1 seats unconditionally)");

        let (spans5, _) = pack_regions(&corpus, &files, &terms, &scores, budget, &count_tokens, None, 0.0, 5, 0.85, false, 0.0, 3, false);
        let got: HashSet<&String> = spans5.keys().collect();
        let baseline: HashSet<&String> = spans0.keys().collect();
        assert_eq!(
            got, baseline,
            "pad_lines=5 at budget 800 must return the SAME 25 files as pad_lines=0 (pre-fix it evicted low-gain files)"
        );

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// E12b guard invariant: the SET OF FILES returned with `pad_lines=N`
    /// (guard active) must equal the set returned at `pad_lines=0`, even on
    /// a fixture that -- under the old (unguarded) E12 policy -- would have
    /// evicted a whole lower-gain file purely because padding grew it past
    /// budget. Two files share an identical body: a short `needle` function
    /// (matches every query term) preceded by an unrelated, unselected
    /// `other_stuff` block whose two filler lines sit a few lines above
    /// `needle` and carry real token mass. `hi.py` scores 5.0, `lo.py`
    /// scores 0.0, so `lo.py`'s selected span has the strictly lower `gain`
    /// and is the guard's first de-escalation target. `budget_tokens` is
    /// sized to fit both files' UNPADDED `needle` spans comfortably, but
    /// not both files' FULLY padded spans (which reach all the way back to
    /// the filler lines) -- so the guard must actually fire to avoid
    /// exceeding budget, and (per the invariant) must do so WITHOUT ever
    /// evicting a whole file.
    #[test]
    fn pack_regions_pad_lines_guard_preserves_unpadded_file_set() {
        let tmp = std::env::temp_dir().join(format!("roust_pad_guard_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let src = "def other_stuff():\n    filler line one aaaa bbbb cccc dddd eeee ffff gggg hhhh\n    filler line two iiii jjjj kkkk llll mmmm nnnn oooo pppp\n    return 1\n\n\ndef needle(x):\n    \"\"\"token budget marker phrase evict guard test words needle\"\"\"\n    return x\n";
        std::fs::write(tmp.join("hi.py"), src).unwrap();
        std::fs::write(tmp.join("lo.py"), src).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("token budget marker phrase evict guard test words needle", &[]);
        let scores: IndexMap<String, f64> =
            [("hi.py".to_string(), 5.0), ("lo.py".to_string(), 0.0)].into_iter().collect();
        let files = vec!["hi.py".to_string(), "lo.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        // needle's own unpadded span is lines 7-9 (1-indexed): "def
        // needle(x):" through "return x".
        let lines: Vec<&str> = src.lines().collect();
        let needle_text = lines[6..9].join("\n");
        let t_needle = count_tokens(&needle_text) as i64;
        let whole_file_tok = count_tokens(src.trim_end()) as i64;

        let budget = 2 * t_needle + 3;
        assert!(
            budget < 2 * whole_file_tok,
            "budget must be too small for both files' FULLY padded (whole-file) spans, so the guard actually has to fire"
        );

        // pad=0 baseline: both files' own needle spans are seated
        // unconditionally by pass 1 and comfortably fit budget on their own.
        let (spans0, _) = pack_regions(&corpus, &files, &terms, &scores, budget, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
        assert!(
            spans0.contains_key("hi.py") && spans0.contains_key("lo.py"),
            "pad_lines=0 baseline must select both files"
        );
        let baseline: HashSet<&String> = spans0.keys().collect();

        for pad in [2usize, 6, 15] {
            let (spans, _bundle) = pack_regions(&corpus, &files, &terms, &scores, budget, &count_tokens, None, 0.0, pad, 1.0, false, 0.0, 3, false);
            let got: HashSet<&String> = spans.keys().collect();
            assert_eq!(
                got, baseline,
                "pad_lines={pad}+guard must return the SAME file set as pad_lines=0 -- no file may be evicted purely from padding growth"
            );
            // Budget accounting mirrors pack_regions' own internal `total`
            // (sum of each returned span's OWN text token count) -- not the
            // pretty-printed `### file\n...` bundle string, which carries a
            // fixed per-file header overhead that pack_regions' budget
            // check never counted against, pre-E12 or post-.
            let total_tok: i64 = spans
                .iter()
                .map(|(rel, ranges)| {
                    let full_lines: Vec<&str> = corpus.text[rel].lines().collect();
                    ranges
                        .iter()
                        .map(|&(a, b)| {
                            let start = a.saturating_sub(1).min(full_lines.len());
                            let end = b.min(full_lines.len());
                            let text = if start < end { full_lines[start..end].join("\n") } else { String::new() };
                            count_tokens(&text) as i64
                        })
                        .sum::<i64>()
                })
                .sum();
            assert!(
                total_tok <= budget,
                "guarded bundle at pad_lines={pad} must respect budget_tokens ({total_tok} > {budget})"
            );
        }

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// Determinism of the guard itself: repeated calls on the fixture above
    /// (at a pad_lines value large enough to force full de-escalation, i.e.
    /// the guard's own iterative loop runs to completion) must produce
    /// byte-identical spans every time.
    #[test]
    fn pack_regions_pad_lines_guard_deterministic_across_repeated_calls() {
        let tmp = std::env::temp_dir().join(format!("roust_pad_guard_det_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let src = "def other_stuff():\n    filler line one aaaa bbbb cccc dddd eeee ffff gggg hhhh\n    filler line two iiii jjjj kkkk llll mmmm nnnn oooo pppp\n    return 1\n\n\ndef needle(x):\n    \"\"\"token budget marker phrase evict guard test words needle\"\"\"\n    return x\n";
        std::fs::write(tmp.join("hi.py"), src).unwrap();
        std::fs::write(tmp.join("lo.py"), src).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("token budget marker phrase evict guard test words needle", &[]);
        let scores: IndexMap<String, f64> =
            [("hi.py".to_string(), 5.0), ("lo.py".to_string(), 0.0)].into_iter().collect();
        let files = vec!["hi.py".to_string(), "lo.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let lines: Vec<&str> = src.lines().collect();
        let needle_text = lines[6..9].join("\n");
        let t_needle = count_tokens(&needle_text) as i64;
        let budget = 2 * t_needle + 3;

        let (first, _) = pack_regions(&corpus, &files, &terms, &scores, budget, &count_tokens, None, 0.0, 15, 1.0, false, 0.0, 3, false);
        assert!(!first.is_empty());
        for _ in 0..10 {
            let (spans, _) = pack_regions(&corpus, &files, &terms, &scores, budget, &count_tokens, None, 0.0, 15, 1.0, false, 0.0, 3, false);
            assert_eq!(
                spans, first,
                "pack_regions with the E12b guard active must produce byte-identical spans across repeated calls"
            );
        }

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// Determinism: `pad_lines>0` must produce byte-identical spans across
    /// repeated calls with identical inputs (same fixture/rationale as
    /// `pack_regions_deterministic_with_many_equal_marginal_scores` above,
    /// now exercising the padding/merge/eviction step too).
    #[test]
    fn pack_regions_pad_lines_deterministic_across_repeated_calls() {
        let tmp = std::env::temp_dir().join(format!("roust_pad_det_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let mut src = String::new();
        for i in 0..50 {
            src.push_str(&format!("def fn_{i}(x):\n    \"\"\"token budget enforced.\"\"\"\n    return x + {i}\n\n\n"));
        }
        std::fs::write(tmp.join("many.py"), &src).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("how is the token budget enforced", &[]);
        let files = vec!["many.py".to_string()];
        let scores: IndexMap<String, f64> = [("many.py".to_string(), 1.0)].into_iter().collect();
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let (first, _) = pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 3, 1.0, false, 0.0, 3, false);
        assert!(!first.is_empty());
        for _ in 0..10 {
            let (spans, _) = pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 3, 1.0, false, 0.0, 3, false);
            assert_eq!(
                spans, first,
                "pack_regions with pad_lines>0 must produce byte-identical spans across repeated calls"
            );
        }

        std::fs::remove_dir_all(&tmp).ok();
    }

    // ---------------------------------------------------------------- E14:
    // length normalization (--len-exp)

    /// E14 golden test: `len_exp=1.0` is documented as reproducing the
    /// exact pre-E14 `gain/tok` ranking, byte-identical -- pin the FULL
    /// output (both the `spans` map AND the packed bundle text, not just a
    /// selected symbol name) on a small fixture as an explicit snapshot, so
    /// any future change to the division sites this experiment touched
    /// would have to also touch this literal expected value.
    #[test]
    fn pack_regions_len_exp_default_is_byte_identical_golden() {
        let tmp = std::env::temp_dir().join(format!("roust_e14_golden_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        std::fs::write(tmp.join("a.py"), "def alpha_widget(x):\n    return x + 1\n").unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("widget", &[]);
        let scores: IndexMap<String, f64> = [("a.py".to_string(), 1.0)].into_iter().collect();
        let files = vec!["a.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let (spans, bundle) = pack_regions(&corpus, &files, &terms, &scores, 8192, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);

        let expected_spans: IndexMap<String, Vec<(usize, usize)>> =
            [("a.py".to_string(), vec![(1usize, 2usize)])].into_iter().collect();
        assert_eq!(spans, expected_spans, "len_exp=1.0 must pin the exact pre-E14 span selection");
        assert_eq!(
            bundle, "### a.py\ndef alpha_widget(x):\n    return x + 1",
            "len_exp=1.0 must pin the exact pre-E14 bundle text"
        );

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// E14 determinism test: 10 repeated calls at a NON-default `len_exp`
    /// (0.7, i.e. actually exercising the new `tok_pow` division sites, not
    /// just the `len_exp=1.0` identity path) must produce byte-identical
    /// spans, on the same many-near-tied-candidates fixture that pins issue
    /// #14's determinism contract above.
    #[test]
    fn pack_regions_deterministic_with_len_exp_below_one() {
        let tmp = std::env::temp_dir().join(format!("roust_e14_det_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let mut src = String::new();
        for i in 0..50 {
            src.push_str(&format!("def fn_{i}(x):\n    \"\"\"token budget enforced.\"\"\"\n    return x + {i}\n\n\n"));
        }
        std::fs::write(tmp.join("many.py"), &src).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("how is the token budget enforced", &[]);
        let files = vec!["many.py".to_string()];
        let scores: IndexMap<String, f64> = [("many.py".to_string(), 1.0)].into_iter().collect();
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let (first, _) = pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 0.7, false, 0.0, 3, false);
        assert!(!first.is_empty());
        for _ in 0..10 {
            let (spans, _) = pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 0.7, false, 0.0, 3, false);
            assert_eq!(
                spans, first,
                "pack_regions must produce byte-identical spans across repeated calls at len_exp=0.7"
            );
        }

        std::fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn camel_matches_edge_cases() {
        assert_eq!(camel_matches("A"), vec!["A"]);
        assert_eq!(camel_matches("ABc"), vec!["A", "Bc"]);
        assert_eq!(camel_matches("HTTPResponse"), vec!["HTTP", "Response"]);
        assert_eq!(camel_matches("XMLHttpRequest"), vec!["XML", "Http", "Request"]);
        assert_eq!(camel_matches("alreadylower"), vec!["alreadylower"]);
    }

    #[test]
    fn end_to_end_synthetic_repo_smoke() {
        // 3-file synthetic repo: a router module importing a validators
        // module, plus an unrelated test file, exercising Corpus building,
        // BM25, the import graph, and select_files' structural-expansion
        // path end to end.
        let tmp = std::env::temp_dir().join(format!("roust_smoke_{}", std::process::id()));
        std::fs::create_dir_all(tmp.join("pkg")).unwrap();
        std::fs::create_dir_all(tmp.join("tests")).unwrap();
        std::fs::write(
            tmp.join("pkg/router.py"),
            "from .validators import validate_request\n\n\ndef route_request(req):\n    \"\"\"Route an incoming request after validation.\"\"\"\n    validate_request(req)\n    return handle(req)\n\n\ndef handle(req):\n    return req\n",
        )
        .unwrap();
        std::fs::write(
            tmp.join("pkg/validators.py"),
            "def validate_request(req):\n    \"\"\"Validate an incoming request payload.\"\"\"\n    if not req:\n        raise ValueError('bad request')\n    return True\n",
        )
        .unwrap();
        std::fs::write(
            tmp.join("tests/test_router.py"),
            "from pkg.router import route_request\n\n\ndef test_route_request():\n    assert route_request({'a': 1})\n",
        )
        .unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        assert_eq!(corpus.n_docs, 3);
        assert!(corpus.files.contains(&"pkg/router.py".to_string()));

        let terms = query_terms("how does the router validate an incoming request", &[]);
        assert!(terms.contains(&"rout".to_string()));
        assert!(terms.contains(&"validat".to_string()));

        let params = SelectParams::default();
        let (files, _scores, _explain) = select_files(&corpus, &terms, true, &params);
        assert!(files.contains(&"pkg/router.py".to_string()));
        assert!(files.contains(&"pkg/validators.py".to_string()));

        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };
        let (spans, bundle) = pack_regions(&corpus, &files, &terms, &_scores, 4096, &count_tokens, None, 1.0, 0, 1.0, false, 0.0, 3, false);
        assert!(!bundle.is_empty());
        assert!(spans.contains_key("pkg/router.py"));

        std::fs::remove_dir_all(&tmp).ok();
    }

    // ---------------------------------------------------------------- issue #25:
    // low-confidence signal + query-term-coverage helpers

    #[test]
    fn query_term_coverage_counts_partial_match() {
        let tmp = std::env::temp_dir().join(format!("roust_qtc_partial_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        std::fs::write(&tmp.join("widget.py"), "def widget_handler():\n    return 1\n").unwrap();
        let corpus = Corpus::build(&tmp, None, false, false);

        let terms = query_terms("widget handler zzznonexistentxyzzy", &[]);
        let (matched, total) = query_term_coverage(&corpus, &terms);
        assert_eq!(total, terms.len());
        assert!(matched >= 1 && matched < total, "expected a partial match, got {matched}/{total}");

        std::fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn query_term_coverage_zero_when_nothing_in_vocabulary() {
        let tmp = std::env::temp_dir().join(format!("roust_qtc_zero_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        std::fs::write(&tmp.join("widget.py"), "def widget_handler():\n    return 1\n").unwrap();
        let corpus = Corpus::build(&tmp, None, false, false);

        let terms = query_terms("zzznonexistentxyzzy qqxwibblewonk", &[]);
        let (matched, total) = query_term_coverage(&corpus, &terms);
        assert_eq!(matched, 0);
        assert_eq!(total, terms.len());
        assert!(total > 0);

        std::fs::remove_dir_all(&tmp).ok();
    }

    #[test]
    fn is_low_confidence_threshold_logic() {
        // Strong raw score + full term coverage: confident.
        assert!(!is_low_confidence(LOW_CONFIDENCE_TOP_SCORE + 1.0, 5, 5));
        // Weak raw score even with full coverage: low-confidence.
        assert!(is_low_confidence(1.0, 5, 5));
        // Strong raw score but most terms unmatched: low-confidence.
        assert!(is_low_confidence(1000.0, 1, 10));
        // Literal zero-match case: low-confidence (superseded by the exit-1
        // gate in main.rs, but the predicate itself must not claim confidence).
        assert!(is_low_confidence(0.0, 0, 5));
        // No terms at all: low-confidence (vacuous, defensive case).
        assert!(is_low_confidence(5.0, 0, 0));
        // Right at the boundary: not low-confidence (strict `<`, not `<=`).
        assert!(!is_low_confidence(LOW_CONFIDENCE_TOP_SCORE, 5, 5));
    }

    // ------------------------------------------------------------ E18/E19 sibling expansion

    /// Shared fixture for the E19 method-family tests: three sibling classes
    /// each defining a `transform` method. Only `Alpha.transform` carries
    /// query-term evidence -- the sibling `transform`s are deliberately
    /// query-term-FREE, so (a) they are not even ranked candidates (the
    /// zero-term filter drops them into the sibling-only pool) and (b) no
    /// amount of pass-2 budget could ever seat them without E19.
    fn family_fixture_src() -> String {
        let mut src = String::new();
        src.push_str("class Alpha:\n    def transform(self, frobnicate_budget):\n        \"\"\"frobnicate the widget budget\"\"\"\n        return frobnicate_budget\n\n");
        src.push_str("class Beta:\n    def transform(self, qq):\n        zz = qq\n        return zz\n\n");
        src.push_str("class Gamma:\n    def transform(self, mm):\n        nn = mm\n        return nn\n\n");
        src.push_str("class Delta:\n    def unrelated_thing(self, pp):\n        return pp\n");
        src
    }

    /// E19: with `--family-enum`, the seed method's exact-name family
    /// (same def name across sibling classes) is added as depth; with the
    /// flags off (defaults) those query-term-free siblings must be absent --
    /// the default path is the unchanged engine.
    #[test]
    fn pack_regions_family_enum_adds_method_family_across_classes() {
        let tmp = std::env::temp_dir().join(format!("roust_e19_family_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        std::fs::write(tmp.join("mod.py"), family_fixture_src()).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("frobnicate the widget budget", &[]);
        let scores: IndexMap<String, f64> = [("mod.py".to_string(), 1.0)].into_iter().collect();
        let files = vec!["mod.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        // Beta.transform's span starts at its def line (7); Gamma's at 12.
        // Delta.unrelated_thing (17) is NOT family.
        let (spans_off, _) =
            pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
        let starts_off: Vec<usize> = spans_off["mod.py"].iter().map(|s| s.0).collect();
        assert!(
            !starts_off.contains(&7) && !starts_off.contains(&12),
            "defaults (family off): query-term-free sibling transforms must be absent, got {starts_off:?}"
        );

        let (spans_on, _) =
            pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, true, 0.0, 3, false);
        let starts_on: Vec<usize> = spans_on["mod.py"].iter().map(|s| s.0).collect();
        assert!(
            starts_on.contains(&7) && starts_on.contains(&12),
            "family-enum must add Beta.transform (7) and Gamma.transform (12), got {starts_on:?}"
        );
        assert!(
            !starts_on.contains(&17),
            "Delta.unrelated_thing (17) is not a family member and must not be added, got {starts_on:?}"
        );

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// E19 suffix-segment family: four module-level `*_handler` defs share
    /// the trailing name segment; seeding on one must pull in the other
    /// three (>= FAMILY_MIN_AFFIX members, seed included). A def NOT
    /// sharing the segment stays out.
    #[test]
    fn pack_regions_family_enum_suffix_segment_family() {
        let tmp = std::env::temp_dir().join(format!("roust_e19_suffix_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let src = "\
def alpha_handler(x):
    \"\"\"frobnicate the widget budget\"\"\"
    return x

def beta_handler(qq):
    return qq

def gamma_handler(mm):
    return mm

def delta_handler(nn):
    return nn

def omega_worker(pp):
    return pp
";
        std::fs::write(tmp.join("handlers.py"), src).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("frobnicate the widget budget", &[]);
        let scores: IndexMap<String, f64> = [("handlers.py".to_string(), 1.0)].into_iter().collect();
        let files = vec!["handlers.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let (spans, _) =
            pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, true, 0.0, 3, false);
        let starts: Vec<usize> = spans["handlers.py"].iter().map(|s| s.0).collect();
        for (start, who) in [(5usize, "beta_handler"), (8, "gamma_handler"), (11, "delta_handler")] {
            assert!(starts.contains(&start), "suffix family must add {who} (line {start}), got {starts:?}");
        }
        assert!(!starts.contains(&14), "omega_worker (14) shares no name segment and must stay out, got {starts:?}");

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// E18: rename-only (Type-2) clones of the seed pass the 0.7 bag-overlap
    /// threshold and are added (capped at --max-siblings, best overlap
    /// first); a lexically unrelated function in the same file does not.
    #[test]
    fn pack_regions_sibling_sim_adds_type2_clones_capped() {
        let tmp = std::env::temp_dir().join(format!("roust_e18_sim_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        // Seed carries the query terms in a docstring; the clones share its
        // body verbatim (rename-only at the def line) but have no query
        // terms at all. `weird_other` shares nothing.
        let body = "    total_marmalade = accumulate_marmalade(jar_registry)\n    sticky_ledger = reconcile_ledger(total_marmalade)\n    return sticky_ledger\n";
        let src = format!(
            "def seed_fn(jar_registry):\n    \"\"\"frobnicate the widget budget\"\"\"\n{body}\ndef clone_one(jar_registry):\n{body}\ndef clone_two(jar_registry):\n{body}\ndef weird_other(zz):\n    qq = zz + 1\n    return qq\n"
        );
        std::fs::write(tmp.join("clones.py"), src).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("frobnicate the widget budget", &[]);
        let scores: IndexMap<String, f64> = [("clones.py".to_string(), 1.0)].into_iter().collect();
        let files = vec!["clones.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        // Layout: seed_fn at 1 (body 3-5), clone_one at 7 (body 8-10),
        // clone_two at 12 (body 13-15), weird_other at 17.
        let (spans_off, _) =
            pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
        let starts_off: Vec<usize> = spans_off["clones.py"].iter().map(|s| s.0).collect();
        assert!(
            !starts_off.contains(&7) && !starts_off.contains(&12),
            "defaults (sim off): term-free clones must be absent, got {starts_off:?}"
        );

        let (spans_on, _) =
            pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, false, 0.7, 3, false);
        let starts_on: Vec<usize> = spans_on["clones.py"].iter().map(|s| s.0).collect();
        assert!(
            starts_on.contains(&7) && starts_on.contains(&12),
            "sim=0.7 must add clone_one (7) and clone_two (12), got {starts_on:?}"
        );
        assert!(
            !starts_on.contains(&17),
            "weird_other (17) is lexically unrelated and must stay out, got {starts_on:?}"
        );

        // --max-siblings 1 caps the additions to the single best-overlap
        // sibling; equal-overlap ties break by ascending span start
        // (clone_one before clone_two).
        let (spans_cap, _) =
            pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, false, 0.7, 1, false);
        let starts_cap: Vec<usize> = spans_cap["clones.py"].iter().map(|s| s.0).collect();
        assert!(
            starts_cap.contains(&7) && !starts_cap.contains(&12),
            "max-siblings=1 must keep only clone_one (7), got {starts_cap:?}"
        );

        std::fs::remove_dir_all(&tmp).ok();
    }

    /// Sibling seats are budget-checked (skip, never force-seat): at
    /// budget=1 pass 1 seats the seed unconditionally (its historical
    /// overshoot behavior) but no sibling can ever be added on top.
    #[test]
    fn pack_regions_siblings_budget_checked_never_force_seated() {
        let tmp = std::env::temp_dir().join(format!("roust_e18_budget_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        std::fs::write(tmp.join("mod.py"), family_fixture_src()).unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("frobnicate the widget budget", &[]);
        let scores: IndexMap<String, f64> = [("mod.py".to_string(), 1.0)].into_iter().collect();
        let files = vec!["mod.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let (spans, _) =
            pack_regions(&corpus, &files, &terms, &scores, 1, &count_tokens, None, 0.0, 0, 1.0, true, 0.7, 3, false);
        assert_eq!(
            spans["mod.py"].len(),
            1,
            "budget=1: the unconditional pass-1 seed must be the file's ONLY span (siblings skipped), got {:?}",
            spans["mod.py"]
        );

        std::fs::remove_dir_all(&tmp).ok();
    }

    // ------------------------------------------------------------ E11 routing

    fn e11_corpus(tag: &str) -> (std::path::PathBuf, Corpus) {
        let tmp = std::env::temp_dir().join(format!("roust_e11_{tag}_{}", std::process::id()));
        std::fs::create_dir_all(tmp.join("pkg/sub")).unwrap();
        std::fs::create_dir_all(tmp.join("tests")).unwrap();
        // pkg/sub/engine.py: the trace-frame target; imports pkg/util.py.
        std::fs::write(
            tmp.join("pkg/sub/engine.py"),
            "from pkg.util import helper_widget\n\ndef run_engine(payload):\n    return helper_widget(payload)\n",
        )
        .unwrap();
        std::fs::write(
            tmp.join("pkg/util.py"),
            "def helper_widget(payload):\n    return payload\n",
        )
        .unwrap();
        // A lexical decoy that mentions generic query vocabulary heavily.
        std::fs::write(
            tmp.join("pkg/decoy.py"),
            "def crash_report_analysis():\n    crash = 'crash crash crash report report'\n    return crash\n",
        )
        .unwrap();
        // Test-shaped file dense in fence-ish identifiers.
        std::fs::write(
            tmp.join("tests/test_widget.py"),
            "def test_widget_frobnicate():\n    frobnicate_widget = 1\n    return frobnicate_widget\n",
        )
        .unwrap();
        // Production file for the fence class.
        std::fs::write(
            tmp.join("pkg/widget.py"),
            "def frobnicate_widget(x):\n    return x\n",
        )
        .unwrap();
        let corpus = Corpus::build(&tmp, None, false, false);
        (tmp, corpus)
    }

    /// Prose-only queries must return EXACTLY query_terms(question) -- the
    /// routed path is a no-op for the unstructured class.
    #[test]
    fn route_prose_only_matches_query_terms_exactly() {
        let (tmp, corpus) = e11_corpus("prose");
        let q = "The engine crashes when the payload widget is empty.\nPlease fix the crash in the report path.";
        let rq = route_query(q, &corpus);
        assert_eq!(rq.terms, query_terms(q, &[]));
        assert_eq!(rq.class(), "prose");
        assert!(rq.trace_files.is_empty());
        assert!(!rq.fence_dominant);
        std::fs::remove_dir_all(&tmp).ok();
    }

    /// Traceback treatment: frame files resolved raise-site-first by
    /// trailing-component match; function names + exception + message kept
    /// as terms; raw trace bulk (site-packages path junk, context code)
    /// dropped.
    #[test]
    fn route_traceback_extracts_frames_and_drops_bulk() {
        let (tmp, corpus) = e11_corpus("trace");
        let q = concat!(
            "Engine explodes on empty payload.\n",
            "\n",
            "Traceback (most recent call last):\n",
            "  File \"/home/user/repro_zzqx.py\", line 3, in <module>\n",
            "    run_engine(None)\n",
            "  File \"/usr/lib/python3.9/site-packages/pkg/sub/engine.py\", line 4, in run_engine\n",
            "    return helper_widget(payload)\n",
            "ValueError: payload frobnality must not be empty\n",
        );
        let rq = route_query(q, &corpus);
        assert_eq!(rq.class(), "trace");
        // raise-site frame resolved (2+ trailing components), repro script skipped
        assert_eq!(rq.trace_files, vec!["pkg/sub/engine.py".to_string()]);
        // exception name + message + frame function terms present
        assert!(rq.terms.contains(&stem("valueerror")), "exception name kept: {:?}", rq.terms);
        assert!(rq.terms.iter().any(|t| t.starts_with("frobnal")), "message kept: {:?}", rq.terms);
        assert!(rq.terms.contains(&"run_engin".to_string()), "frame function kept: {:?}", rq.terms);
        // trace bulk dropped: the repro filename token appears nowhere
        assert!(!rq.terms.iter().any(|t| t.contains("zzqx")), "trace bulk dropped: {:?}", rq.terms);
        std::fs::remove_dir_all(&tmp).ok();
    }

    /// Fence treatment: identifiers mined (call targets, attributes,
    /// assignment LHS), bulk fence text (comments/strings) discarded;
    /// fence_dominant flips when mined terms are a strict majority.
    #[test]
    fn route_fence_mines_identifiers_discards_bulk() {
        let (tmp, corpus) = e11_corpus("fence");
        let q = concat!(
            "Crash here.\n",
            "```python\n",
            "w = frobnicate_widget(3)\n",
            "w.payload_slot = 1  # some ordinary commentary vocabulary garbanzo\n",
            "```\n",
        );
        let rq = route_query(q, &corpus);
        assert_eq!(rq.class(), "fence");
        assert!(rq.terms.iter().any(|t| t.contains("frobnic")), "call target mined: {:?}", rq.terms);
        assert!(rq.terms.iter().any(|t| t.contains("payload_slot") || t.contains("slot")), "attr mined: {:?}", rq.terms);
        // comment bulk dropped
        assert!(!rq.terms.iter().any(|t| t.contains("garbanzo")), "fence bulk dropped: {:?}", rq.terms);
        assert!(rq.fence_dominant, "fence terms are the majority here");
        std::fs::remove_dir_all(&tmp).ok();
    }

    /// REPL (>>>) lines are fence-channel even without markdown fences.
    #[test]
    fn route_repl_lines_are_fence_channel() {
        let (tmp, corpus) = e11_corpus("repl");
        let q = "Wrong result:\n>>> frobnicate_widget(2).payload_slot\n0\n";
        let rq = route_query(q, &corpus);
        assert!(rq.fence_bearing);
        assert!(rq.terms.iter().any(|t| t.contains("frobnic")), "{:?}", rq.terms);
        std::fs::remove_dir_all(&tmp).ok();
    }

    /// The trace FILE boost must rescue a frame-named file with ZERO
    /// query-term overlap (E-class rescue) and rank it first; the import
    /// spillover must pull the frame file's own import target into the pool.
    #[test]
    fn select_files_trace_boost_rescues_and_spills() {
        let (tmp, corpus) = e11_corpus("boost");
        // Query terms deliberately match ONLY the decoy.
        let terms = query_terms("crash report analysis", &[]);
        let baseline = select_files(&corpus, &terms, true, &SelectParams::default());
        assert_eq!(baseline.0.first().map(String::as_str), Some("pkg/decoy.py"));

        let tfs = vec!["pkg/sub/engine.py".to_string()];
        let params = SelectParams { trace_files: Some(&tfs), ..Default::default() };
        let (files, scores, _) = select_files(&corpus, &terms, true, &params);
        // Rescue semantics: a zero-lexical-overlap frame file gets boost
        // 1/1 = 1.0, TYING the normalized lexical max (additive-on-
        // normalized, BRTracer); presence in the top of the ranked list is
        // the rescue, strict rank-1 is not guaranteed.
        let pos = files.iter().position(|f| f == "pkg/sub/engine.py");
        assert!(pos.is_some_and(|p| p < 2), "frame file rescued into top-2: {files:?}");
        // spillover: engine.py imports pkg/util.py -> present in the pool
        assert!(scores.contains_key("pkg/util.py"), "import spillover scored: {:?}", scores.keys().collect::<Vec<_>>());
        std::fs::remove_dir_all(&tmp).ok();
    }

    /// The conditional test penalty fires only when test_penalty < 1.0 and
    /// only on TESTLIKE paths.
    #[test]
    fn select_files_test_penalty_downweights_testlike_paths() {
        let (tmp, corpus) = e11_corpus("penalty");
        let terms = query_terms("frobnicate widget payload", &[]);
        let off = select_files(&corpus, &terms, true, &SelectParams::default());
        let on = select_files(
            &corpus,
            &terms,
            true,
            &SelectParams { test_penalty: 0.5, ..Default::default() },
        );
        let s_off = off.1.get("tests/test_widget.py").copied().unwrap();
        let s_on = on.1.get("tests/test_widget.py").copied().unwrap();
        assert!((s_on - s_off * 0.5).abs() < 1e-12, "testlike path halved: {s_off} -> {s_on}");
        let p_off = off.1.get("pkg/widget.py").copied().unwrap();
        let p_on = on.1.get("pkg/widget.py").copied().unwrap();
        assert_eq!(p_off, p_on, "non-test path untouched");
        std::fs::remove_dir_all(&tmp).ok();
    }

    /// Frame-path resolution: >= 2 trailing components required, src/
    /// layout mismatches still resolve via the components that DO align.
    #[test]
    fn resolve_frame_path_component_semantics() {
        let (tmp, corpus) = e11_corpus("resolve");
        assert_eq!(
            resolve_frame_path("/x/site-packages/pkg/sub/engine.py", &corpus),
            Some("pkg/sub/engine.py".to_string())
        );
        // 1 shared component only -> unresolved
        assert_eq!(resolve_frame_path("/somewhere/else/engine.py", &corpus), None);
        // exact relative path -> resolved
        assert_eq!(resolve_frame_path("pkg/util.py", &corpus), Some("pkg/util.py".to_string()));
        std::fs::remove_dir_all(&tmp).ok();
    }

    // ------------------------------------------------------------ E11b trace-boost

    /// `trace_frame_files` must produce EXACTLY `route_query(...).trace_files`
    /// (same frames, same raise-site-first order, same dedupe) on a mixed
    /// trace+fence+prose issue -- the equivalence the E11b flag relies on --
    /// and be empty on prose.
    #[test]
    fn trace_frame_files_matches_route_query() {
        let (tmp, corpus) = e11_corpus("e11b_eq");
        let q = concat!(
            "Engine explodes on empty payload.\n",
            "```python\n",
            "run_engine(None)\n",
            "```\n",
            "Traceback (most recent call last):\n",
            "  File \"/home/user/repro_zzqx.py\", line 3, in <module>\n",
            "    run_engine(None)\n",
            "  File \"/usr/lib/python3.9/site-packages/pkg/sub/engine.py\", line 4, in run_engine\n",
            "    return helper_widget(payload)\n",
            "  File \"/usr/lib/python3.9/site-packages/pkg/util.py\", line 2, in helper_widget\n",
            "    return payload\n",
            "ValueError: payload must not be empty\n",
        );
        let rq = route_query(q, &corpus);
        let tf = trace_frame_files(q, &corpus);
        assert_eq!(tf, rq.trace_files, "trace_frame_files == route_query trace_files");
        // raise-site (util.py, last frame) first
        assert_eq!(tf, vec!["pkg/util.py".to_string(), "pkg/sub/engine.py".to_string()]);
        assert!(trace_frame_files("The engine crashes on empty payload.", &corpus).is_empty());
        std::fs::remove_dir_all(&tmp).ok();
    }

    // ------------------------------------------------------------ E20 LexBoost

    /// Corpus for the LexBoost tests: gold.py has WEAK direct overlap with
    /// the query but two import-neighbors (a.py, b.py) that score well;
    /// decoy.py has a moderate direct score and no scored neighbors;
    /// hub.py is imported by everything (top-decile in-degree).
    fn e20_corpus(tag: &str) -> (std::path::PathBuf, Corpus) {
        let tmp = std::env::temp_dir().join(format!("roust_e20_{tag}_{}", std::process::id()));
        std::fs::create_dir_all(tmp.join("pkg")).unwrap();
        // Query will be "frobnicate widget quux". gold.py mentions none of
        // the query terms; its neighbors a.py/b.py are dense in them.
        std::fs::write(
            tmp.join("pkg/gold.py"),
            "from pkg.a import alpha_frob\nfrom pkg.b import beta_frob\n\ndef golden_path(x):\n    return alpha_frob(beta_frob(x))\n",
        )
        .unwrap();
        std::fs::write(
            tmp.join("pkg/a.py"),
            "def alpha_frob(x):\n    frobnicate = x\n    widget = frobnicate\n    quux = widget\n    return quux\n",
        )
        .unwrap();
        std::fs::write(
            tmp.join("pkg/b.py"),
            "def beta_frob(x):\n    frobnicate_widget = x\n    quux_widget = frobnicate_widget\n    return quux_widget\n",
        )
        .unwrap();
        // Moderate direct match, no neighbors.
        std::fs::write(tmp.join("pkg/decoy.py"), "def lonely():\n    widget = 1\n    return widget\n").unwrap();
        // Hub: imported by many files, mild direct overlap.
        std::fs::write(tmp.join("pkg/hub.py"), "def hub_util(x):\n    widget = x\n    return widget\n").unwrap();
        for i in 0..6 {
            std::fs::write(
                tmp.join(format!("pkg/user{i}.py")),
                "from pkg.hub import hub_util\n\ndef unrelated_stuff():\n    return hub_util(1)\n",
            )
            .unwrap();
        }
        let corpus = Corpus::build(&tmp, None, false, false);
        (tmp, corpus)
    }

    /// Import-graph neighbor lists are sorted and symmetric; the hub guard
    /// marks exactly the top-decile-in-degree file (hub.py, in-degree 6)
    /// and nothing else.
    #[test]
    fn lexboost_import_neighbors_and_hubs() {
        let (tmp, corpus) = e20_corpus("nbrs");
        let edges = build_import_graph(&corpus);
        let nbrs = lexboost_import_neighbors(&edges);
        let g = nbrs.get("pkg/gold.py").expect("gold has import neighbors");
        assert_eq!(g, &vec!["pkg/a.py".to_string(), "pkg/b.py".to_string()]);
        // symmetry: a.py lists gold back
        assert!(nbrs.get("pkg/a.py").unwrap().contains(&"pkg/gold.py".to_string()));
        let hubs = lexboost_hubs(&nbrs);
        assert!(hubs.contains("pkg/hub.py"), "hub.py (in-degree 6) is a hub: {hubs:?}");
        assert!(!hubs.contains("pkg/gold.py"), "gold (in-degree 2) is not: {hubs:?}");
        std::fs::remove_dir_all(&tmp).ok();
    }

    /// The smoothing math: S' = lambda*S + (1-lambda)*prior*MEAN(neighbors),
    /// verified to float precision for a scored file, a hub (neighbor term
    /// forced to 0), and an inserted zero-direct-score file (E-class
    /// rescue). MEAN (not sum): gold's smoothed score uses /2 for its two
    /// neighbors.
    #[test]
    fn lexboost_smoothing_math_hub_guard_and_insertion() {
        let (tmp, corpus) = e20_corpus("math");
        let terms = query_terms("frobnicate widget quux", &[]);
        let base = select_files(&corpus, &terms, true, &SelectParams::default());
        let bm = corpus.bm25(&terms);
        let bm_n = {
            let mx = bm.values().cloned().fold(f64::MIN, f64::max);
            let m: IndexMap<String, f64> = bm.iter().map(|(k, v)| (k.clone(), v / mx)).collect();
            m
        };
        assert!(!bm_n.contains_key("pkg/gold.py"), "gold must have ZERO direct score for the rescue case");

        let edges = build_import_graph(&corpus);
        let nbrs = lexboost_import_neighbors(&edges);
        let hubs = lexboost_hubs(&nbrs);
        let lambda = 0.7;
        let (sm, diag) = apply_lexboost(&bm_n, &corpus, &nbrs, &hubs, lambda);

        // Inserted rescue: gold = (1-lambda) * mean(a, b)
        let sa = bm_n["pkg/a.py"];
        let sb = bm_n["pkg/b.py"];
        let expect_gold = (1.0 - lambda) * (sa + sb) / 2.0;
        let got_gold = sm.get("pkg/gold.py").copied().expect("gold inserted by neighbor rescue");
        assert!((got_gold - expect_gold).abs() < 1e-12, "gold {got_gold} != {expect_gold}");

        // Hub: neighbor term forced to zero -> lambda * S exactly.
        let hub_direct = bm_n["pkg/hub.py"];
        let got_hub = sm["pkg/hub.py"];
        assert!((got_hub - lambda * hub_direct).abs() < 1e-12, "hub gets no neighbor term");

        // Scored non-hub file (a.py): lambda*S + (1-lambda)*mean(its nbrs).
        let nb_a = &nbrs["pkg/a.py"];
        let mean_a: f64 = nb_a.iter().map(|x| bm_n.get(x).copied().unwrap_or(0.0)).sum::<f64>() / nb_a.len() as f64;
        assert!((sm["pkg/a.py"] - (lambda * sa + (1.0 - lambda) * mean_a)).abs() < 1e-12);

        // Diagnostics carry the anatomy.
        assert!(diag.iter().any(|(f, _, d, m, _)| f == "pkg/gold.py" && *d == 0.0 && *m > 0.0));

        // End-to-end at the LEX stage (structural expansion can add gold as
        // a graph "addition" in the baseline too -- the smoothing claim is
        // specifically that gold enters the lexical ranking itself):
        // baseline lex_picks cannot contain gold (zero direct score);
        // lexboost lex_picks must.
        assert!(!base.2.lex_picks.contains(&"pkg/gold.py".to_string()), "gold not in baseline lex_picks: {:?}", base.2.lex_picks);
        let params = SelectParams {
            lexboost: lambda,
            lexboost_nbrs: Some(&nbrs),
            lexboost_hubs: Some(&hubs),
            ..Default::default()
        };
        let boosted = select_files(&corpus, &terms, true, &params);
        assert!(boosted.2.lex_picks.contains(&"pkg/gold.py".to_string()), "lexboost lifts gold into lex_picks: {:?}", boosted.2.lex_picks);
        assert!(boosted.0.contains(&"pkg/gold.py".to_string()), "gold in final selection: {:?}", boosted.0);
        std::fs::remove_dir_all(&tmp).ok();
    }

    /// lambda = 1.0 must leave every score identical (no neighbor term, no
    /// insertions) -- the blend degenerates to the identity.
    #[test]
    fn lexboost_lambda_one_is_identity() {
        let (tmp, corpus) = e20_corpus("ident");
        let terms = query_terms("frobnicate widget quux", &[]);
        let bm = corpus.bm25(&terms);
        let mx = bm.values().cloned().fold(f64::MIN, f64::max);
        let bm_n: IndexMap<String, f64> = bm.iter().map(|(k, v)| (k.clone(), v / mx)).collect();
        let edges = build_import_graph(&corpus);
        let nbrs = lexboost_import_neighbors(&edges);
        let hubs = lexboost_hubs(&nbrs);
        let (sm, _) = apply_lexboost(&bm_n, &corpus, &nbrs, &hubs, 1.0);
        assert_eq!(sm.len(), bm_n.len(), "no insertions at lambda=1");
        for (f, v) in &bm_n {
            assert_eq!(sm[f], *v, "identity at lambda=1 for {f}");
        }
        std::fs::remove_dir_all(&tmp).ok();
    }

    /// The kNN graph is deterministic across repeated construction, lists
    /// are path-sorted, self is never a neighbor, and K caps the list size.
    #[test]
    fn lexboost_knn_deterministic_sorted_no_self() {
        let (tmp, corpus) = e20_corpus("knn");
        let g1 = lexboost_knn_neighbors(&corpus, 16);
        let g2 = lexboost_knn_neighbors(&corpus, 16);
        assert_eq!(g1, g2, "kNN graph deterministic across construction");
        assert!(!g1.is_empty());
        for (f, nb) in &g1 {
            assert!(!nb.contains(f), "no self-neighbor for {f}");
            assert!(nb.len() <= 16);
            let mut sorted = nb.clone();
            sorted.sort();
            assert_eq!(&sorted, nb, "neighbor list sorted for {f}");
        }
        // k=2 caps harder
        let g3 = lexboost_knn_neighbors(&corpus, 2);
        for nb in g3.values() {
            assert!(nb.len() <= 2);
        }
        std::fs::remove_dir_all(&tmp).ok();
    }

    /// The neighbor term is damped by impl_prior: a test-shaped file with
    /// the same neighborhood as a production file receives 0.3x the
    /// neighbor mean (it cannot ride neighbor support past the engine's
    /// existing test-file damping).
    #[test]
    fn lexboost_neighbor_term_respects_impl_prior() {
        let tmp = std::env::temp_dir().join(format!("roust_e20_prior_{}", std::process::id()));
        std::fs::create_dir_all(tmp.join("pkg")).unwrap();
        std::fs::create_dir_all(tmp.join("tests")).unwrap();
        std::fs::write(tmp.join("pkg/a.py"), "def alpha():\n    return 1\n").unwrap();
        std::fs::write(tmp.join("pkg/gold.py"), "def golden():\n    return 2\n").unwrap();
        std::fs::write(tmp.join("tests/test_x.py"), "def test_things():\n    return 3\n").unwrap();
        let corpus = Corpus::build(&tmp, None, false, false);
        // Synthetic neighbor map: both files neighbor a.py only.
        let mut nbrs: NeighborMap = BTreeMap::new();
        nbrs.insert("pkg/gold.py".to_string(), vec!["pkg/a.py".to_string()]);
        nbrs.insert("tests/test_x.py".to_string(), vec!["pkg/a.py".to_string()]);
        let mut bm_n: IndexMap<String, f64> = IndexMap::new();
        bm_n.insert("pkg/a.py".to_string(), 1.0);
        let (sm, _) = apply_lexboost(&bm_n, &corpus, &nbrs, &HashSet::new(), 0.7);
        let g = sm.get("pkg/gold.py").copied().unwrap_or(0.0);
        let t = sm.get("tests/test_x.py").copied().unwrap_or(0.0);
        assert!((g - 0.3_f64 * 1.0).abs() < 1e-12, "production rescue = (1-l)*mean = 0.3, got {g}");
        assert!((t - 0.3_f64 * 0.3).abs() < 1e-12, "testlike rescue damped by prior 0.3, got {t}");
        std::fs::remove_dir_all(&tmp).ok();
    }

    /// Defaults-off guarantee at the API level: SelectParams::default()
    /// leaves lexboost off and select_files output identical with an
    /// explicitly-supplied-but-disabled configuration.
    #[test]
    fn lexboost_defaults_off_identical() {
        let (tmp, corpus) = e20_corpus("off");
        let terms = query_terms("frobnicate widget quux", &[]);
        let a = select_files(&corpus, &terms, true, &SelectParams::default());
        let edges = build_import_graph(&corpus);
        let nbrs = lexboost_import_neighbors(&edges);
        // lexboost == 0.0 -> nbrs present but ignored.
        let params = SelectParams { lexboost: 0.0, lexboost_nbrs: Some(&nbrs), ..Default::default() };
        let b = select_files(&corpus, &terms, true, &params);
        assert_eq!(a.0, b.0);
        assert_eq!(a.1, b.1);
        std::fs::remove_dir_all(&tmp).ok();
    }

    // ------------------------------------------------------------ E23 tests

    /// E23 JS fixture: arrow-function-in-const, export default, nested
    /// named function, object-literal methods (method shorthand, arrow
    /// pair, function-expression pair), nested class inside a method, and
    /// an arrow-function class field. Expected spans follow python_blocks'
    /// contract exactly: 1-indexed inclusive, preamble first, each header
    /// runs to the next header at same-or-lower CST depth (so top-level
    /// spans partition the file after the preamble and trailing lines are
    /// swallowed by the last block -- same as python_blocks' last method
    /// swallowing the class's closing lines).
    #[test]
    fn ts_blocks_js_fixture_multigranularity_spans() {
        let js = "import { x } from './x';\n\nconst f = (a) => {\n  return a + 1;\n};\n\nexport default function main() {\n  function inner() { return 2; }\n  return inner();\n}\n\nconst obj = {\n  plain: 1,\n  method() { return 3; },\n  arrow: () => 4,\n  fnval: function () { return 5; },\n};\n\nclass Outer {\n  constructor() { this.v = 1; }\n  handle = () => { return this.v; }\n  method() {\n    class Inner {\n      m() { return 9; }\n    }\n    return new Inner();\n  }\n}\n";
        let spans = ts_blocks(js, "a.js");
        assert_eq!(
            spans,
            vec![
                (1, 2),   // preamble (import + blank)
                (3, 6),   // const f = (a) => ...  (declarator-bound arrow)
                (7, 13),  // export default function main (export line hoisted;
                          //  swallows the non-header `const obj = {` opener,
                          //  python_blocks-style)
                (8, 13),  // nested named function inner (depth 1)
                (14, 14), // obj.method() -- object-literal method shorthand
                (15, 15), // obj.arrow: () => 4 -- function-valued pair
                (16, 18), // obj.fnval: function () -- function-expression pair
                (19, 28), // class Outer (whole-class span, to EOF)
                (20, 20), // constructor
                (21, 21), // handle = () => -- arrow-function class field
                (22, 28), // method() (last member swallows class close)
                (23, 28), // class Inner nested inside method (depth 2)
                (24, 28), // Inner.m (depth 3)
            ],
            "JS fixture spans changed -- ts_blocks contract regression"
        );
    }

    /// E23 TS fixture: interface/enum/namespace declarations (the trivial
    /// TS-only allowlist kinds), export-hoisted arrow-in-const, abstract
    /// class, and a function inside a namespace. `abstract run(): void;`
    /// is a method SIGNATURE, not an implementation, and is deliberately
    /// not a header (mirrors the Python side counting `def` bodies only).
    #[test]
    fn ts_blocks_ts_declaration_kinds() {
        let ts = "import type { T } from './t';\n\nexport interface Props { name: string; }\n\nenum Color { Red, Green }\n\nnamespace NS {\n  export function nsFn(): number { return 1; }\n}\n\nexport const useThing = (p: Props): number => {\n  const helper = () => 2;\n  return helper();\n};\n\nexport abstract class Base {\n  abstract run(): void;\n  concrete(): number { return 3; }\n}\n";
        let spans = ts_blocks(ts, "a.ts");
        assert_eq!(
            spans,
            vec![
                (1, 2),   // preamble
                (3, 4),   // export interface Props
                (5, 6),   // enum Color
                (7, 10),  // namespace NS (internal_module)
                (8, 10),  // NS.nsFn (export-hoisted, depth 1)
                (11, 15), // export const useThing = arrow
                (12, 15), // nested helper arrow (depth 1)
                (16, 19), // export abstract class Base
                (18, 19), // Base.concrete (abstract run() is signature-only: no span)
            ],
            "TS fixture spans changed -- ts_blocks contract regression"
        );
    }

    /// E23 TSX fixture: an arrow-function component with JSX (needs the
    /// TSX grammar -- the TypeScript grammar cannot parse JSX) plus an
    /// export-default function component.
    #[test]
    fn ts_blocks_tsx_components() {
        let tsx = "import React from 'react';\n\nexport const App = ({ name }: { name: string }) => {\n  const onClick = () => console.log(name);\n  return <button onClick={onClick}>{name}</button>;\n};\n\nexport default function Page() {\n  return <App name=\"x\" />;\n}\n";
        let spans = ts_blocks(tsx, "a.tsx");
        assert_eq!(
            spans,
            vec![
                (1, 2),  // preamble
                (3, 7),  // export const App = (...) => JSX
                (4, 7),  // nested onClick arrow (depth 1)
                (8, 10), // export default function Page
            ],
            "TSX fixture spans changed -- ts_blocks contract regression"
        );
    }

    /// E23: a headerless script degrades to the whole-file span, exactly
    /// python_blocks' no-headers behavior (the packer's fallback shape).
    #[test]
    fn ts_blocks_headerless_whole_file() {
        let js = "const a = 1;\nconsole.log(a);\n";
        assert_eq!(ts_blocks(js, "a.js"), vec![(1, 2)]);
    }

    /// E23 flag gating in pack_regions: OFF keeps the JS file on
    /// window_blocks (span centered on the hit line, start != function
    /// header); ON substitutes the structural function span (starts at the
    /// header). The .py control file's spans must be IDENTICAL in both
    /// runs -- the flag must not touch the Python path.
    #[test]
    fn pack_regions_ts_blocks_flag_gates_js_only() {
        let tmp = std::env::temp_dir().join(format!("roust_e23_gate_{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let mut js = String::from("import { z } from './z';\n\nfunction big() {\n");
        for i in 4..=54 {
            js.push_str(&format!("  const v{i} = {i};\n"));
        }
        js.push_str("  return frobnicate_widget();\n}\n"); // term on line 55
        std::fs::write(tmp.join("a.js"), &js).unwrap();
        std::fs::write(
            tmp.join("b.py"),
            "def frobnicate_widget():\n    return 1\n",
        )
        .unwrap();

        let corpus = Corpus::build(&tmp, None, false, false);
        let terms = query_terms("frobnicate widget", &[]);
        let scores: IndexMap<String, f64> =
            [("a.js".to_string(), 1.0), ("b.py".to_string(), 1.0)].into_iter().collect();
        let files = vec!["a.js".to_string(), "b.py".to_string()];
        let count_tokens = |s: &str| -> usize { s.split_whitespace().count() };

        let (spans_off, _) =
            pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, false);
        let (spans_on, _) =
            pack_regions(&corpus, &files, &terms, &scores, 100_000, &count_tokens, None, 0.0, 0, 1.0, false, 0.0, 3, true);

        let js_starts_off: Vec<usize> = spans_off["a.js"].iter().map(|s| s.0).collect();
        let js_starts_on: Vec<usize> = spans_on["a.js"].iter().map(|s| s.0).collect();
        assert!(
            !js_starts_off.contains(&3),
            "flag OFF must keep window_blocks for .js (no span at the function header), got {js_starts_off:?}"
        );
        assert!(
            js_starts_on.contains(&3),
            "flag ON must seat the structural function span starting at the header (line 3), got {js_starts_on:?}"
        );
        assert_eq!(
            spans_off["b.py"], spans_on["b.py"],
            "the .py file's spans must be untouched by --ts-blocks"
        );

        std::fs::remove_dir_all(&tmp).ok();
    }
}
