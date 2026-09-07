//! Lab-only controlled file-selection diagnostic. JSON request on stdin.
//! Supplying gold files makes the result an oracle diagnostic, not retrieval.
use roust::{cache, core::*};
use serde::Deserialize;
use std::{collections::HashSet, io::Read, path::PathBuf};

#[derive(Deserialize)]
struct Request {
    repo: PathBuf,
    query: String,
    /// None reproduces normal selection. Some replaces only file selection.
    files: Option<Vec<String>>,
}

fn main() {
    if std::env::args().any(|a| a == "--version") {
        println!("research_pack ({}, {})", env!("ROUST_GIT_SHA"), env!("ROUST_GIT_DIRTY"));
        return;
    }
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).unwrap();
    let request: Request = serde_json::from_str(&input).unwrap();
    set_cfamily_ext(true);
    set_ext_v2(true);
    set_symbols_v2(true);
    set_displacement_guard(true);
    set_pack_floor(0.15);
    set_tail_seat(40, 16);
    let (corpus, _edges, history, _) = cache::load_or_build(&request.repo, true, true, true, false);
    block_cache_open(&request.repo);
    let terms = query_terms(&request.query, &[]);
    let anchors = extract_symbol_anchors(&request.query, &corpus);
    let trace = trace_frame_files_v2(&request.query, &corpus);
    let params = SelectParams {
        k_lex: 10,
        cochange: history.as_ref().map(|h| &h.cochange),
        anchors: Some(&anchors),
        use_testbridge: true,
        use_docsbridge: true,
        trace_files: if trace.is_empty() { None } else { Some(&trace) },
        ..Default::default()
    };
    let (selected, scores, explain) = select_files(&corpus, &terms, true, &params);
    let anchor_files: HashSet<String> = explain.anchor_promotions.iter().map(|(f, ..)| f.clone()).collect();
    let symbols = anchor_def_symbols(&request.query, &corpus, &anchor_files);
    let requested = request.files.as_ref().unwrap_or(&selected);
    let files: Vec<String> = requested.iter().filter(|f| corpus.text.contains_key(f.as_str())).cloned().collect();
    let absent: Vec<&String> = requested.iter().filter(|f| !corpus.text.contains_key(f.as_str())).collect();
    assert_eq!(files.iter().collect::<HashSet<_>>().len(), files.len(), "duplicate files");
    let encoder = tiktoken_rs::cl100k_base_singleton();
    let tokens = |s: &str| encoder.lock().encode_ordinary(s).len();
    let (regions, bundle) = pack_regions(&corpus, &files, &terms, &scores, 8192,
        &tokens, Some(&symbols), 0.0, 5, 0.85, false, 0.0, 3, BlockMode::Structural);
    block_cache_save();
    println!("{}", serde_json::json!({
        "regions": regions, "bundle": bundle,
        "stats": {"bundle_tokens": tokens(&bundle), "engine_sha": env!("ROUST_GIT_SHA"),
                  "engine_dirty": env!("ROUST_GIT_DIRTY") == "dirty"},
        "diagnostic": {"overridden": request.files.is_some(), "absent_files": absent,
                       "selected_files": selected, "packed_input_files": files}
    }));
}
