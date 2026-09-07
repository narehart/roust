//! Persistent block-cache invariants through separate CLI processes.
use std::path::{Path, PathBuf};
use std::process::Command;
use serde_json::{json, Value};

fn fixture(tag: &str) -> PathBuf {
    let p = std::env::temp_dir().join(format!("roust_block_{tag}_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&p);
    std::fs::create_dir_all(&p).unwrap();
    let text = (0..60).map(|i| format!("fn validate_widget_{i}() {{\n let widget = validate_price({i});\n println!(\"{{}}\", widget);\n}}\n")).collect::<String>();
    std::fs::write(p.join("widgets.rs"), text).unwrap();
    p
}
fn run(p: &Path, extra: &[&str]) -> Value {
    let o = Command::new(env!("CARGO_BIN_EXE_roust"))
        .args(["validate widget price", "--json", "--budget", "900"])
        .args(extra).arg(p).output().unwrap();
    assert!(o.status.success(), "{}", String::from_utf8_lossy(&o.stderr));
    let v: Value = serde_json::from_slice(&o.stdout).unwrap();
    json!({"regions": v["regions"], "bundle": v["bundle"]})
}
#[test]
fn count_only_entries_recompute_lexical_tokens_and_survive_reload() {
    let p = fixture("count_only");
    let expected = run(&p, &["--no-cache"]);
    assert_eq!(run(&p, &[]), expected);
    let path = p.join(".roust/blocks.json");
    let mut cache: Value = serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
    for fs in cache["segs"].as_object_mut().unwrap().values_mut() {
        for entry in fs["segs"].as_object_mut().unwrap().values_mut() {
            entry["ids"] = Value::Null;
        }
    }
    std::fs::write(&path, serde_json::to_vec(&cache).unwrap()).unwrap();
    assert_eq!(run(&p, &[]), expected);
    assert_eq!(run(&p, &[]), expected);
    // E52 writes token-count-only unions: later block modes must remain
    // observationally identical to an uncached invocation of that mode.
    run(&p, &["--unique-span-budget"]);
    for mode in ["--shape-union-blocks", "--hit-window-blocks"] {
        assert_eq!(run(&p, &[mode]), run(&p, &[mode, "--no-cache"]));
    }
    std::fs::remove_dir_all(p).unwrap();
}
#[test]
fn legacy_ambiguous_cache_is_rebuilt_without_shape_work_on_default_path() {
    let p = fixture("legacy");
    let expected = run(&p, &[]);
    let path = p.join(".roust/blocks.json");
    let mut cache: Value = serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
    assert!(cache["blocks"].as_object().unwrap().keys().all(|k| !k.ends_with("|shape")));
    cache.as_object_mut().unwrap().remove("version");
    for fs in cache["segs"].as_object_mut().unwrap().values_mut() {
        for entry in fs["segs"].as_object_mut().unwrap().values_mut() {
            *entry = json!([entry["tok"], []]);
        }
    }
    std::fs::write(&path, serde_json::to_vec(&cache).unwrap()).unwrap();
    assert_eq!(run(&p, &[]), expected);
    let rebuilt: Value = serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
    assert!(rebuilt["segs"].as_object().unwrap().values().all(|f|
        f["segs"].as_object().unwrap().values().all(|e| e.is_object())));
    std::fs::remove_dir_all(p).unwrap();
}
#[test]
fn concurrent_block_cache_writers_publish_complete_json() {
    let p = fixture("concurrent");
    let expected = run(&p, &[]); // build corpus index before racing block writers
    std::fs::remove_file(p.join(".roust/blocks.json")).unwrap();
    let workers: Vec<_> = (0..6).map(|_| {
        let p = p.clone();
        std::thread::spawn(move || run(&p, &[]))
    }).collect();
    for worker in workers { assert_eq!(worker.join().unwrap(), expected); }
    let _: Value = serde_json::from_slice(&std::fs::read(p.join(".roust/blocks.json")).unwrap()).unwrap();
    assert_eq!(run(&p, &[]), expected);
    assert!(std::fs::read_dir(p.join(".roust")).unwrap().all(|f|
        !f.unwrap().file_name().to_string_lossy().ends_with(".tmp")));
    std::fs::remove_dir_all(p).unwrap();
}
