//! CLI-level WS3d tests (campaign #56, anchor/trace displacement-guard
//! round): the flag-gated `--displacement-guard` fixture-dir anchor
//! exclusion (default OFF -- experiment flag, not adopted), exercised
//! through the real compiled binary because the flag is a process-global
//! set at CLI parse (same convention as tests/symbols_v2.rs).
//!
//! Fixture anatomy (mirrors mui-34337/34548/35178 exactly): a codemod
//! fixture DIRECTORY named `<transform>.test/` holds an actual/expected
//! near-duplicate pair that defines the same rare symbol the issue text
//! mentions. TESTLIKE_RE only matches `.test.` as a file-name infix, so
//! the pair is undamped and un-testlike everywhere in the engine; under
//! the adopted symbols-v2 defaults both files win the <=3-definers
//! rarity gate and are anchor-inserted, eating pass-1 pack budget from
//! the genuinely relevant files. Under --displacement-guard the pair is
//! excluded from anchor candidacy (ranking-side only: the files stay
//! indexed) while every non-fixture anchor is untouched.

use serde_json::Value;
use std::path::PathBuf;
use std::process::Command;

struct Run {
    explain: Value,
    stdout: String,
}

fn run(dir: &PathBuf, query: &str, guard: bool) -> Run {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_roust"));
    cmd.arg(query).arg(dir).arg("--no-cache").arg("--explain").arg("--budget").arg("3000");
    if guard {
        cmd.arg("--displacement-guard");
    }
    let out = cmd.output().expect("failed to run roust binary");
    let stderr = String::from_utf8_lossy(&out.stderr).into_owned();
    let a = stderr.find('{').unwrap_or_else(|| panic!("no explain JSON on stderr: {stderr}"));
    let b = stderr.rfind('}').unwrap();
    let explain: Value = serde_json::from_str(&stderr[a..=b])
        .unwrap_or_else(|e| panic!("stderr must contain the explain JSON, got err {e}: {stderr}"));
    Run { explain, stdout: String::from_utf8_lossy(&out.stdout).into_owned() }
}

fn promoted_files(explain: &Value) -> Vec<String> {
    explain["anchor_promotions"]
        .as_array()
        .map(|a| a.iter().filter_map(|p| p[0].as_str().map(|s| s.to_string())).collect())
        .unwrap_or_default()
}

/// Call-site files carrying the query's prose terms so the fixture pair
/// (which defines the rare symbol) never earns lexical rank on its own --
/// the mined displacing fires were all `insert` promotions of files
/// absent from the ranked list.
fn write_fillers(dir: &PathBuf) {
    for i in 0..25 {
        // call sites USE the rare symbols (no definitions), so the query
        // terms are corpus-common while def_index still holds only the
        // true definers.
        let body = format!(
            "// widget spacing migration transform helpers\n\
             function migrateSpacing{i}() {{\n\
             \x20 const probe = themeSpacingProbe(currentTheme());\n\
             \x20 runSpacingMigration(collectFiles(probe));\n\
             \x20 return applyTransform(widgetSpacingTable(), migrationLog());\n\
             }}\n"
        );
        std::fs::write(dir.join(format!("caller{i}.js")), body).unwrap();
    }
}

/// Junk padding (borrowed from tests/symbols_v2.rs): inflate doclen so
/// BM25 length normalization buries the padded file below the lexical
/// picks -- the mined displacing fires were all `insert` promotions of
/// files ABSENT from the ranked list.
fn junk(n: usize) -> String {
    (0..n).map(|i| format!("const zqval{i} = internalHousekeeping{i}();\n")).collect()
}

/// The codemod fixture pair: same rare symbol defined in both files of a
/// `<name>.test/` DIRECTORY (the shape TESTLIKE_RE misses).
fn write_fixture_pair(dir: &PathBuf) {
    let fixdir = dir.join("codemod").join("spacing-transform.test");
    std::fs::create_dir_all(&fixdir).unwrap();
    for name in ["first.actual.js", "first.expected.js"] {
        let body = format!(
            "const themeSpacingProbe = (theme) => {{\n\
             \x20 return theme.spacing(2);\n\
             }};\n\
             \n{}",
            junk(900)
        );
        std::fs::write(fixdir.join(name), body).unwrap();
    }
}

#[test]
fn displacement_guard_excludes_fixture_dir_anchors_only() {
    let tmp = std::env::temp_dir().join(format!("roust_ws3d_guard_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(&tmp).unwrap();
    write_fillers(&tmp);
    write_fixture_pair(&tmp);
    // A legitimate (non-fixture) defining file for a second rare symbol
    // the query also names: its promotion must survive the guard. In its
    // own subdirectory so the same-dir additions pool (fed by the
    // root-dir callers) cannot rank it without the anchor channel.
    std::fs::create_dir_all(tmp.join("lib")).unwrap();
    std::fs::write(
        tmp.join("lib/transformRunner.js"),
        format!(
            "const runSpacingMigration = (files) => {{\n\
             \x20 return files.map(applyTransform);\n\
             }};\n\
             \n{}",
            junk(900)
        ),
    )
    .unwrap();

    let q = "themeSpacingProbe output wrong after runSpacingMigration in the widget spacing migration transform";
    let base = run(&tmp, q, false);
    let guarded = run(&tmp, q, true);

    let base_promoted = promoted_files(&base.explain);
    assert!(
        base_promoted.iter().any(|f| f.contains("spacing-transform.test/")),
        "defaults: the fixture pair must be anchor-promoted (reproducing the mui-34337 anatomy), got {base_promoted:?}"
    );
    let guard_promoted = promoted_files(&guarded.explain);
    assert!(
        !guard_promoted.iter().any(|f| f.contains("spacing-transform.test/")),
        "--displacement-guard: fixture-dir files must be excluded from anchor candidacy, got {guard_promoted:?}"
    );
    assert!(
        guard_promoted.contains(&"lib/transformRunner.js".to_string()),
        "--displacement-guard: non-fixture anchors must be untouched, got {guard_promoted:?}"
    );

    let _ = std::fs::remove_dir_all(&tmp);
}

#[test]
fn displacement_guard_defaults_byte_identical_without_fixture_dirs() {
    let tmp = std::env::temp_dir().join(format!("roust_ws3d_ident_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(&tmp).unwrap();
    write_fillers(&tmp);
    std::fs::create_dir_all(tmp.join("lib")).unwrap();
    std::fs::write(
        tmp.join("lib/transformRunner.js"),
        format!(
            "const runSpacingMigration = (files) => {{\n\
             \x20 return files.map(applyTransform);\n\
             }};\n\
             \n{}",
            junk(900)
        ),
    )
    .unwrap();

    let q = "wrong output from runSpacingMigration in the widget spacing migration transform";
    let base = run(&tmp, q, false);
    let guarded = run(&tmp, q, true);
    assert_eq!(
        base.stdout, guarded.stdout,
        "no fixture-dir files in the tree: guard ON must be byte-identical to defaults"
    );
    // ... including an actually-firing non-fixture anchor in both states.
    assert_eq!(promoted_files(&base.explain), promoted_files(&guarded.explain));
    assert!(
        promoted_files(&base.explain).contains(&"lib/transformRunner.js".to_string()),
        "identity fixture must exercise a live non-fixture anchor, got {:?}",
        promoted_files(&base.explain)
    );

    let _ = std::fs::remove_dir_all(&tmp);
}
