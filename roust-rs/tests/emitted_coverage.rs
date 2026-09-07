use serde_json::Value;
use std::process::Command;

#[test]
fn trace_exposes_unemitted_terms_without_changing_payload() {
    let repo = std::env::temp_dir().join(format!("roust_emitted_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&repo);
    std::fs::create_dir_all(&repo).unwrap();
    let text = format!("fn process() {{\n{}\n let deepneedle = raretarget();\n}}\n",
        " let padding = conventional_operation();\n".repeat(500));
    std::fs::write(repo.join("deep.rs"), text).unwrap();
    let run = |flags: &[&str]| {
        let o = Command::new(env!("CARGO_BIN_EXE_roust"))
            .args(["deepneedle raretarget", "--json", "--no-cache", "--budget", "900"])
            .args(flags).arg(&repo).output().unwrap();
        assert!(o.status.success(), "{}", String::from_utf8_lossy(&o.stderr));
        let payload: Value = serde_json::from_slice(&o.stdout).unwrap();
        let traces: Vec<Value> = String::from_utf8(o.stderr).unwrap().lines()
            .filter_map(|line| line.strip_prefix("ROUST_PACK_TRACE "))
            .map(|line| serde_json::from_str(line).unwrap()).collect();
        (payload, traces)
    };
    for padding in ["0", "5"] {
        let (plain, _) = run(&["--pad-lines", padding]);
        let (traced, trace) = run(&["--pad-lines", padding, "--pack-trace"]);
        assert_eq!(plain["regions"], traced["regions"]);
        assert_eq!(plain["bundle"], traced["bundle"]);
        let seat = trace.iter().find(|r| r["stage"] == "pass1").unwrap();
        assert!(seat["omitted_query_terms"].as_array().unwrap().contains(&Value::from(roust::core::stem("deepneedle"))));
        assert!(seat["retained_query_terms"].as_array().unwrap().is_empty());
        let (_, trace) = run(&["--pad-lines", padding, "--pack-trace", "--emitted-coverage"]);
        assert!(trace.iter().find(|r| r["stage"] == "pass1").unwrap()["emitted_coverage"].as_bool().unwrap());
    }
    std::fs::remove_dir_all(repo).unwrap();
}
