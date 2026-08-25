//! CLI-level WS3c tests (campaign #56, audit findings 3+6): the
//! `--symbols-v2` def/anchor channel + un-gated anchor-forced seating,
//! exercised through the real compiled binary because the flag is a
//! process-global set at CLI parse -- an in-process unit test would race
//! the parallel test threads (see `impl_prior_with`'s doc comment for the
//! convention). Each test spawns its own process, so the global is safely
//! per-invocation here.
//!
//! Fixture anatomy (mirrors the real MSWE failure mode): many "call-site"
//! files reference the queried symbol and carry the query's prose terms
//! densely, while the DEFINING file is long and junk-padded so BM25 ranks
//! it out of the lexical picks. Flag-off, the definition is invisible to
//! def_index (JS arrow / Java method -- exactly finding 6's blind spots),
//! so no anchor exists and the file stays unranked. Flag-on, the
//! tree-sitter def_index resolves the anchor, promotes the file, and the
//! seating fix packs the SYMBOL'S OWN block (not the decoy region that
//! wins on generic term density).

use serde_json::Value;
use std::path::PathBuf;
use std::process::Command;

struct Run {
    explain: Value,
    bundle: String,
}

fn run(dir: &PathBuf, query: &str, symbols_v2: bool) -> Run {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_roust"));
    cmd.arg(query).arg(dir).arg("--no-cache").arg("--explain").arg("--budget").arg("3000");
    if symbols_v2 {
        cmd.arg("--symbols-v2");
    }
    let out = cmd.output().expect("failed to run roust binary");
    let stderr = String::from_utf8_lossy(&out.stderr).into_owned();
    // stderr carries the pretty explain JSON followed by the one-line run
    // summary -- slice out the JSON object.
    let a = stderr.find('{').unwrap_or_else(|| panic!("no explain JSON on stderr: {stderr}"));
    let b = stderr.rfind('}').unwrap();
    let explain: Value = serde_json::from_str(&stderr[a..=b])
        .unwrap_or_else(|e| panic!("stderr must contain the explain JSON, got err {e}: {stderr}"));
    Run { explain, bundle: String::from_utf8_lossy(&out.stdout).into_owned() }
}

fn promoted_files(explain: &Value) -> Vec<String> {
    explain["anchor_promotions"]
        .as_array()
        .map(|a| a.iter().filter_map(|p| p[0].as_str().map(|s| s.to_string())).collect())
        .unwrap_or_default()
}

/// 40 call-site files: every query term (prose AND the symbol's own
/// subtokens, via call sites) appears in each, flooring the idf of
/// everything the defining file could match on.
fn write_fillers(dir: &PathBuf) {
    for i in 0..40 {
        let body = format!(
            "// dashboard panel layout crash rendering helpers\n\
             function dashboardPanel{i}() {{\n\
             \x20 const cfg = parseWidgetConfig(rawInput());\n\
             \x20 registry.registerWidget(cfg.title);\n\
             \x20 return renderDashboardLayout(cfg, panelCrashGuard());\n\
             }}\n\
             function panelLayoutCrash{i}() {{\n\
             \x20 return renderPanel(dashboardLayoutTable(), crashReporter());\n\
             }}\n"
        );
        std::fs::write(dir.join(format!("caller{i}.js")), body).unwrap();
    }
}

/// Junk padding: unique low-value identifiers inflating doclen so BM25's
/// length normalization buries the defining file below the lexical picks.
fn junk(n: usize) -> String {
    (0..n).map(|i| format!("const zqval{i} = internalHousekeeping{i}();\n")).collect()
}

#[test]
fn symbols_v2_seats_js_arrow_definition() {
    let tmp = std::env::temp_dir().join(format!("roust_ws3c_js_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(&tmp).unwrap();
    write_fillers(&tmp);
    // Defining file: decoy region dense in prose query terms FIRST (wins
    // generic gain/tok), the arrow definition after, then junk padding.
    let util = format!(
        "// decoy: dashboard panel layout crash render dashboard panel\n\
         function decoyDashboardPanelLayoutCrashRender() {{\n\
         \x20 return dashboard(panel(layout(crash(render()))));\n\
         }}\n\
         \n\
         const parseWidgetConfig = (raw) => {{\n\
         \x20 const data = JSON.parse(raw);\n\
         \x20 return {{ title: data.title, size: data.size }};\n\
         }};\n\
         \n{}",
        junk(1200)
    );
    std::fs::write(tmp.join("util.js"), util).unwrap();

    let q = "crash in `parseWidgetConfig` when rendering the dashboard panel layout";
    let base = run(&tmp, q, false);
    let v2 = run(&tmp, q, true);

    assert!(
        promoted_files(&base.explain).is_empty(),
        "flag OFF: the arrow definition must be invisible to the def/anchor channel, got {:?}",
        base.explain["anchor_promotions"]
    );
    assert!(
        promoted_files(&v2.explain).contains(&"util.js".to_string()),
        "flag ON: util.js must be anchor-promoted via the tree-sitter def_index, got {:?}",
        v2.explain["anchor_promotions"]
    );
    assert!(
        v2.bundle.contains("const parseWidgetConfig = (raw)") && v2.bundle.contains("JSON.parse"),
        "flag ON: the anchored symbol's OWN block must be seated (not just the decoy), bundle:\n{}",
        &v2.bundle[..v2.bundle.len().min(2000)]
    );

    let _ = std::fs::remove_dir_all(&tmp);
}

#[test]
fn symbols_v2_seats_java_method_definition() {
    let tmp = std::env::temp_dir().join(format!("roust_ws3c_java_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(&tmp).unwrap();
    write_fillers(&tmp);
    let registry = format!(
        "public class WidgetRegistry {{\n\
         \x20   // decoy: dashboard panel layout crash render dashboard panel\n\
         \x20   public void decoyDashboardPanelLayoutCrashRender() {{\n\
         \x20       dashboard(panel(layout(crash(render()))));\n\
         \x20   }}\n\
         \n\
         \x20   public void registerWidget(String title) {{\n\
         \x20       store.put(title, title);\n\
         \x20   }}\n\
         }}\n\
         \n{}",
        junk(1200).replace("const ", "// ")
    );
    std::fs::write(tmp.join("WidgetRegistry.java"), registry).unwrap();

    let q = "crash in `registerWidget` when rendering the dashboard panel layout";
    let base = run(&tmp, q, false);
    let v2 = run(&tmp, q, true);

    assert!(
        promoted_files(&base.explain).is_empty(),
        "flag OFF: Java has no def/anchor channel at all, got {:?}",
        base.explain["anchor_promotions"]
    );
    assert!(
        promoted_files(&v2.explain).contains(&"WidgetRegistry.java".to_string()),
        "flag ON: WidgetRegistry.java must be anchor-promoted, got {:?}",
        v2.explain["anchor_promotions"]
    );
    assert!(
        v2.bundle.contains("public void registerWidget(String title)")
            && v2.bundle.contains("store.put"),
        "flag ON: the Java method's own block must be seated, bundle:\n{}",
        &v2.bundle[..v2.bundle.len().min(2000)]
    );

    let _ = std::fs::remove_dir_all(&tmp);
}
