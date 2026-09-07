use serde_json::Value;
use std::process::Command;

#[test]
fn comment_cache_is_separate_and_anchors_keep_their_declaration() {
    let repo = std::env::temp_dir().join(format!("roust_comments_{}", std::process::id()));
    std::fs::create_dir_all(&repo).unwrap();
    let source = format!("fn unrelated() {{\n{}\n}}\n/// A specialized decoder.\n#[inline]\nfn quasar_decode() {{\n{}\n}}\n",
        " let noise = 1;\n".repeat(30), " let useful = 2;\n".repeat(30));
    std::fs::write(repo.join("lib.rs"), source).unwrap();
    let run = |flags: &[&str]| {
        let output = Command::new(env!("CARGO_BIN_EXE_roust"))
            .args(["quasar_decode", "--json", "--budget", "300", "--pad-lines", "0"])
            .args(flags).arg(&repo).output().unwrap();
        assert!(output.status.success(), "{}", String::from_utf8_lossy(&output.stderr));
        serde_json::from_slice::<Value>(&output.stdout).unwrap()
    };
    let before = run(&[]);
    let attached = run(&["--leading-comments"]);
    let after = run(&[]);
    assert_eq!(before["regions"], after["regions"]);
    assert_eq!(before["bundle"], after["bundle"]);
    assert!(attached["bundle"].as_str().unwrap().contains("quasar_decode"));
    assert!(attached["bundle"].as_str().unwrap().contains("specialized decoder"));
    let cold = run(&["--leading-comments", "--no-cache"]);
    assert_eq!(attached["regions"], cold["regions"]);
    assert_eq!(attached["bundle"], cold["bundle"]);
    std::fs::remove_dir_all(repo).unwrap();
}
