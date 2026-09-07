use serde_json::Value;
use std::process::Command;

#[test]
fn shared_source_expands_exact_locations_without_increasing_tokens() {
    let repo = std::env::temp_dir().join(format!("roust_shared_{}", std::process::id()));
    std::fs::create_dir_all(&repo).unwrap();
    let body = format!("void quasar_decode() {{\n{}}}\n", (0..120)
        .map(|n| format!("  process_value_{n}();\n")).collect::<String>());
    for path in ["a.cpp", "b.hpp"] { std::fs::write(repo.join(path), &body).unwrap(); }
    let run = |flags: &[&str]| {
        let output = Command::new(env!("CARGO_BIN_EXE_roust"))
            .args(["quasar_decode", "--json", "--budget", "1800", "--pad-lines", "0"])
            .args(flags).arg(&repo).output().unwrap();
        assert!(output.status.success(), "{}", String::from_utf8_lossy(&output.stderr));
        serde_json::from_slice::<Value>(&output.stdout).unwrap()
    };
    let before = run(&[]);
    let shared = run(&["--shared-source"]);
    let after = run(&[]);
    assert_eq!(before["regions"], after["regions"]);
    assert_eq!(before["bundle"], after["bundle"]);
    for path in ["a.cpp", "b.hpp"] {
        assert_eq!(shared["regions"][path], serde_json::json!([[1, 122]]));
    }
    assert!(shared["stats"]["bundle_tokens"].as_u64().unwrap() < before["stats"]["bundle_tokens"].as_u64().unwrap());
    let bundle = shared["bundle"].as_str().unwrap();
    assert!(bundle.contains("a.cpp:1-122; b.hpp:1-122"));
    assert_eq!(bundle.matches("process_value_0()").count(), 1);
    let cold = run(&["--shared-source", "--no-cache"]);
    assert_eq!(shared["regions"], cold["regions"]);
    assert_eq!(shared["bundle"], cold["bundle"]);
    std::fs::remove_dir_all(repo).unwrap();
}
