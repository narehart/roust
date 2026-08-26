"""WS3 phase-1 Python-assumption audit: MSWE evidence mining (issue #56).

Three censuses over the committed MSWE parquets (plus SWE-bench Lite as the
Python baseline), all read-only:

  1. Trace-format census -- per language slice, how many instances carry a
     stack trace in each ecosystem's format. The engine's adopted-default
     trace-frame FILE boost (core.rs TB_FRAME_RE) only fires on CPython
     `File "X", line N` frames; every other format currently gets NO boost.
     For non-Python formats we also extract the frame paths and check whether
     any resolves (trailing-2-component match, resolve_frame_path's gate)
     to a gold file -- the upper bound on what a format extension could
     rescue.

  2. TESTLIKE damping census -- fraction of gold files (and instances with
     >=1 gold file) hit by TESTLIKE_RE's 0.3x impl_prior damping, per
     language, vs the Python Lite baseline. Asymmetric damping = ranking
     harm concentrated on ecosystems whose production layouts look
     test-like to the regex (or whose test conventions escape it, inverting
     the intended prior).

  3. Extension-coverage census -- gold files whose suffix is outside the
     indexed set (CODE_EXTENSIONS + CFAMILY default-on), per language:
     the hard FILE-recall ceiling the allowlist imposes (WS1 territory,
     quantified here per WS2 language for completeness).

Usage: uv run --no-project --with pandas --with pyarrow python \
           lab/research/langagnostic/mine_ws3_audit.py
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

LAB = Path(__file__).resolve().parents[2]  # lab/

# ---------------------------------------------------------------- engine ports
# Mirror roust-rs/src/core.rs exactly.

CODE_EXTENSIONS = [".py", ".ts", ".js", ".go", ".rs", ".java", ".kt", ".cs",
                   ".swift", ".tsx", ".jsx"]
CFAMILY_EXTENSIONS = [".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh"]
INDEXED = set(CODE_EXTENSIONS) | set(CFAMILY_EXTENSIONS)  # cfamily default-ON

TESTLIKE_RE = re.compile(
    r"(?i)(^|/)(tests?|testing|spec|specs|benches|benchmarks?|examples?|"
    r"fixtures?|mocks?|docs?|__tests__|e2e|docs_src|tutorials?|samples?|"
    r"demos?|playground|scripts?|integration|t)(/|$)|(^|/)(test_|conftest)|"
    r"_test\.(py|go|rs|ts|js)$|\.test\.|\.spec\."
)

TB_FRAME_RE = re.compile(r'^\s*File "([^"]+)", line \d+(?:, in (\S.*))?\s*$')

# ------------------------------------------------- non-Python trace formats
# Node/V8: `    at fnName (/abs/or/rel/path.js:10:15)` or `    at /path.js:1:2`
NODE_FRAME_RE = re.compile(
    r"^\s*at\s+(?:[^\s(]+(?:\s+\[as\s+[^\]]+\])?\s+\()?"
    r"((?:[A-Za-z]:\\|/|\.{1,2}/|[\w@][\w@./-]*/)[^():]+?):(\d+):(\d+)\)?\s*$"
)
# Java: `    at com.foo.Bar.baz(Bar.java:123)`
JAVA_FRAME_RE = re.compile(r"^\s*at\s+[\w.$<>/]+\(([\w$]+\.(?:java|kt|scala)):(\d+)\)\s*$")
# Go panic: goroutine header, or the tab-indented `pkg/file.go:123 +0x39` line
GO_HDR_RE = re.compile(r"^goroutine \d+ \[")
GO_FRAME_RE = re.compile(r"^\s*([\w@./-]+\.go):(\d+)(?:\s+\+0x[0-9a-f]+)?\s*$")
# Rust: panic line, `RUST_BACKTRACE` marker, or numbered backtrace frame with
# an `at path.rs:line[:col]` locator line
RUST_PANIC_RE = re.compile(r"thread '[^']*' panicked at|stack backtrace:|RUST_BACKTRACE")
RUST_AT_RE = re.compile(r"^\s*(?:at\s+)([\w@./-]+\.rs):(\d+)(?::\d+)?\s*$")
# C/C++: sanitizer/gdb frames `#3 0x7f.. in func /path/file.cpp:42` or
# `#3  func (args) at file.cpp:42`
CXX_FRAME_RE = re.compile(
    r"^\s*#\d+\s+(?:0x[0-9a-f]+\s+)?(?:in\s+)?.*?(?:\s+at\s+|\s+)([\w@./-]+\.(?:c|cc|cpp|cxx|h|hpp|hh)):(\d+)"
)


def gold_files(patch: str) -> list[str]:
    out = []
    for m in re.finditer(r"^diff --git a/(\S+) b/(\S+)", patch or "", re.M):
        out.append(m.group(2))
    return sorted(set(out))


def lang_of(files: list[str]) -> str:
    votes = Counter()
    for f in files:
        suf = "." + f.rsplit(".", 1)[-1] if "." in f.rsplit("/", 1)[-1] else ""
        lang = {".py": "python", ".js": "jsts", ".jsx": "jsts", ".ts": "jsts",
                ".tsx": "jsts", ".mjs": "jsts", ".cjs": "jsts", ".go": "go",
                ".rs": "rust", ".java": "java", ".kt": "java", ".c": "c",
                ".h": "c_h", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp",
                ".hpp": "cpp", ".hh": "cpp"}.get(suf)
        if lang:
            votes[lang] += 1
    if not votes:
        return "none"
    # .h alone is ambiguous C/C++; fold into whichever of c/cpp co-occurs
    if "c_h" in votes:
        votes["cpp" if votes.get("cpp", 0) >= votes.get("c", 0) else "c"] += votes.pop("c_h")
    return votes.most_common(1)[0][0]


def trace_paths(text: str) -> dict[str, list[str]]:
    """Format -> frame paths found in the issue text, line-classified."""
    found: dict[str, list[str]] = defaultdict(list)
    lines = (text or "").splitlines()
    for i, ln in enumerate(lines):
        m = TB_FRAME_RE.match(ln)
        if m:
            found["python"].append(m.group(1))
            continue
        m = JAVA_FRAME_RE.match(ln)
        if m:
            found["java"].append(m.group(1))
            continue
        m = NODE_FRAME_RE.match(ln)
        if m:
            found["node"].append(m.group(1))
            continue
        m = RUST_AT_RE.match(ln)
        if m:
            found["rust"].append(m.group(1))
            continue
        if RUST_PANIC_RE.search(ln):
            found["rust_marker"].append("")
            continue
        m = CXX_FRAME_RE.match(ln)
        if m:
            found["cxx"].append(m.group(1))
            continue
        if GO_HDR_RE.match(ln):
            found["go_marker"].append("")
            continue
        m = GO_FRAME_RE.match(ln)
        # Go frame-locator lines are tab-indented under a `pkg.func(...)`
        # line; require that shape so bare `file.go:12` prose mentions
        # don't count as a trace.
        if m and i > 0 and (ln.startswith("\t") or ln.startswith("    ")):
            found["go"].append(m.group(1))
    return found


def resolves_to_gold(paths: list[str], gold: list[str]) -> bool:
    """resolve_frame_path's gate, approximated against the gold set only:
    >=2 shared trailing components, or exact relpath / basename==single-
    component-gold match."""
    for p in paths:
        parts = [x for x in p.replace("\\", "/").split("/") if x]
        if not parts:
            continue
        for g in gold:
            gp = g.split("/")
            shared = 0
            while (shared < len(gp) and shared < len(parts)
                   and gp[-1 - shared] == parts[-1 - shared]):
                shared += 1
            if shared == len(gp) or shared >= 2:
                return True
            # basename-only frame (Java traces carry only `Bar.java`):
            # count a basename match as a *potential* resolution
            if len(parts) == 1 and gp[-1] == parts[0]:
                return True
    return False


def census(name: str, df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        gold = gold_files(r["patch"])
        lang = lang_of(gold)
        text = (r.get("problem_statement") or "")
        tp = trace_paths(text)
        code_gold = [g for g in gold
                     if ("." + g.rsplit(".", 1)[-1] if "." in g.rsplit("/", 1)[-1] else "") in INDEXED]
        rows.append({
            "dataset": name,
            "instance_id": r["instance_id"],
            "repo": r["repo"],
            "lang": lang,
            "n_gold": len(gold),
            "n_gold_indexed": len(code_gold),
            "n_gold_testlike": sum(1 for g in gold if TESTLIKE_RE.search(g)),
            "n_code_gold_testlike": sum(1 for g in code_gold if TESTLIKE_RE.search(g)),
            "trace_formats": {k: len(v) for k, v in tp.items()},
            "py_trace": bool(tp.get("python")),
            "nonpy_trace": any(k in tp for k in
                               ("node", "java", "go", "go_marker", "rust", "rust_marker", "cxx")),
            "nonpy_trace_hits_gold": resolves_to_gold(
                sum((tp.get(k, []) for k in ("node", "java", "go", "rust", "cxx")), []), gold),
        })
    return rows


def main() -> None:
    frames = {
        "lite(py)": pd.read_parquet(LAB / "swebench_lite.parquet"),
        "mswe_jsts": pd.read_parquet(LAB / "mswe_jsts.parquet"),
        "mswe_ws2c": pd.read_parquet(LAB / "mswe_ws2c.parquet"),
        "mswe_c": pd.read_parquet(LAB / "mswe_c.parquet"),
        "mswe_cpp": pd.read_parquet(LAB / "mswe_cpp.parquet"),
    }
    all_rows: list[dict] = []
    for name, df in frames.items():
        all_rows.extend(census(name, df))

    out = LAB / "research" / "langagnostic" / "ws3_audit_census.jsonl"
    with out.open("w") as fh:
        for row in all_rows:
            fh.write(json.dumps(row) + "\n")

    # ---------------------------------------------------------- summary table
    key = lambda r: (r["dataset"], r["lang"])
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in all_rows:
        groups[key(r)].append(r)
    print(f"{'dataset':10s} {'lang':7s} {'n':>5s} {'pyTB':>5s} {'otherTB':>7s} "
          f"{'TB->gold':>8s} {'gold_testlike%':>14s} {'inst_damped%':>12s} {'gold_unidx%':>11s}")
    for (ds, lang), rs in sorted(groups.items()):
        n = len(rs)
        if n < 5:
            continue
        pytb = sum(r["py_trace"] for r in rs)
        otb = sum(r["nonpy_trace"] for r in rs)
        otbg = sum(r["nonpy_trace_hits_gold"] for r in rs)
        tot_gold = sum(r["n_gold"] for r in rs)
        tl = sum(r["n_gold_testlike"] for r in rs)
        inst_damped = sum(1 for r in rs if r["n_gold_testlike"] > 0)
        unidx = sum(r["n_gold"] - r["n_gold_indexed"] for r in rs)
        print(f"{ds:10s} {lang:7s} {n:5d} {pytb:5d} {otb:7d} {otbg:8d} "
              f"{100*tl/max(tot_gold,1):13.1f}% {100*inst_damped/n:11.1f}% "
              f"{100*unidx/max(tot_gold,1):10.1f}%")
    print(f"\nwrote {out} ({len(all_rows)} rows)")


if __name__ == "__main__":
    main()
