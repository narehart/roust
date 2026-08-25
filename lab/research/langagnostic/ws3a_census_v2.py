"""WS3a census re-check (campaign #56, round WS3a): damped-gold under
impl_prior v1 vs --impl-prior-v2, per language slice.

Part 1 -- gold-file census over the committed parquets (same slices and
methodology as mine_ws3_audit.py census 2): fraction of INDEXED gold files
whose path the prior damps, and fraction of instances carrying >=1 damped
indexed gold file, under both predicates. The audit's v1 numbers (jsts
21.4%, cpp 15.6%, rust 9.2%, Lite 0.0%) must reproduce exactly; the v2
column is the round's acceptance evidence (jsts should collapse; Lite must
stay 0.0%).

Part 2 -- repo-tree spot-check: walk real checkouts (Python + jsts + rust
+ cpp) and classify every indexed file's (v1, v2) damped status. Proves
(a) Python test files still damp under v2 (no tests/-path file may flip to
undamped), and (b) every v1->v2 flip is a code file under a doc-like
component (docs?/examples?/benchmarks?/benches).

The predicates are line-for-line ports of roust-rs/src/core.rs
`impl_prior_with(rel, v2, cfamily=True)` -- this script never invokes the
binary (mine_ws3_audit.py precedent).

Usage: uv run --no-project --with pandas --with pyarrow python \
           lab/research/langagnostic/ws3a_census_v2.py [--repos-check]
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

LAB = Path(__file__).resolve().parents[2]  # lab/

# ---------------------------------------------------------------- engine ports
# Mirror roust-rs/src/core.rs @ ws3a-impl-prior exactly.

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

TESTLIKE_V2_RE = re.compile(
    r"(?i)(^|/)(tests?|testing|spec|specs|fixtures?|mocks?|__tests__|e2e|"
    r"docs_src|tutorials?|samples?|demos?|playground|scripts?|integration|t)"
    r"(/|$)|(^|/)(test_|conftest)|_test\.[A-Za-z0-9]+$|\.test\.|\.spec\."
)

DOCLIKE_V2_RE = re.compile(r"(?i)(^|/)(docs?|examples?|benchmarks?|benches)(/|$)")


def is_code(rel: str) -> bool:
    # roust `is_code_file_with(rel, cfamily=True)`: ends_with over both lists.
    return any(rel.endswith(e) for e in CODE_EXTENSIONS) or any(
        rel.endswith(e) for e in CFAMILY_EXTENSIONS)


def damped_v1(rel: str) -> bool:
    return bool(TESTLIKE_RE.search(rel))


def damped_v2(rel: str) -> bool:
    if TESTLIKE_V2_RE.search(rel):
        return True
    return bool(DOCLIKE_V2_RE.search(rel)) and not is_code(rel)


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
    if "c_h" in votes:
        votes["cpp" if votes.get("cpp", 0) >= votes.get("c", 0) else "c"] += votes.pop("c_h")
    return votes.most_common(1)[0][0]


def indexed_suffix(f: str) -> bool:
    suf = "." + f.rsplit(".", 1)[-1] if "." in f.rsplit("/", 1)[-1] else ""
    return suf in INDEXED


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos-check", action="store_true",
                    help="also walk real checkouts (part 2 spot-check)")
    args = ap.parse_args()

    frames = {
        "lite(py)": pd.read_parquet(LAB / "swebench_lite.parquet"),
        "mswe_jsts": pd.read_parquet(LAB / "mswe_jsts.parquet"),
        "mswe_ws2c": pd.read_parquet(LAB / "mswe_ws2c.parquet"),
        "mswe_c": pd.read_parquet(LAB / "mswe_c.parquet"),
        "mswe_cpp": pd.read_parquet(LAB / "mswe_cpp.parquet"),
    }

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for name, df in frames.items():
        for _, r in df.iterrows():
            gold = gold_files(r["patch"])
            lang = lang_of(gold)
            idx_gold = [g for g in gold if indexed_suffix(g)]
            groups[(name, lang)].append({
                "n_idx": len(idx_gold),
                "v1": sum(1 for g in idx_gold if damped_v1(g)),
                "v2": sum(1 for g in idx_gold if damped_v2(g)),
                "v1_hit": any(damped_v1(g) for g in idx_gold),
                "v2_hit": any(damped_v2(g) for g in idx_gold),
            })

    print("=== Part 1: damped INDEXED gold files, v1 vs --impl-prior-v2 ===")
    print(f"{'dataset':10s} {'lang':7s} {'n':>5s} {'goldidx':>7s} "
          f"{'v1_damped%':>10s} {'v2_damped%':>10s} {'v1_inst%':>9s} {'v2_inst%':>9s}")
    for (ds, lang), rs in sorted(groups.items()):
        n = len(rs)
        if n < 5:
            continue
        tot = sum(r["n_idx"] for r in rs)
        v1 = sum(r["v1"] for r in rs)
        v2 = sum(r["v2"] for r in rs)
        i1 = sum(r["v1_hit"] for r in rs)
        i2 = sum(r["v2_hit"] for r in rs)
        print(f"{ds:10s} {lang:7s} {n:5d} {tot:7d} "
              f"{100*v1/max(tot,1):9.1f}% {100*v2/max(tot,1):9.1f}% "
              f"{100*i1/n:8.1f}% {100*i2/n:8.1f}%")

    if not args.repos_check:
        return

    print("\n=== Part 2: repo-tree spot-check (v1 vs v2 damped status) ===")
    repos = [
        ("python", LAB / "ws3a_repos/repos_gate/django__django"),
        ("python", LAB / "ws3a_repos/repos_gate/sympy__sympy"),
        ("python", LAB / "ws3a_repos/repos_gate/matplotlib__matplotlib"),
        ("jsts", LAB / "mswe_repos_e23/mui__material-ui"),
        ("rust", LAB / "ws3a_repos/rust_base/BurntSushi__ripgrep"),
        ("cpp", LAB / "ws3a_repos/cpp_base/catchorg__Catch2"),
    ]
    bad_flips = []
    for lang, rp in repos:
        if not rp.is_dir():
            print(f"  SKIP (missing): {rp}")
            continue
        rels = []
        for p in rp.rglob("*"):
            if p.is_file() and indexed_suffix(p.name) and ".git" not in p.parts:
                rels.append(p.relative_to(rp).as_posix())
        n_v1 = sum(damped_v1(f) for f in rels)
        n_v2 = sum(damped_v2(f) for f in rels)
        undamped = [f for f in rels if damped_v1(f) and not damped_v2(f)]
        newly = [f for f in rels if damped_v2(f) and not damped_v1(f)]
        # invariant (a): no test-convention file may flip to undamped
        for f in undamped:
            if TESTLIKE_V2_RE.search(f):
                bad_flips.append((rp.name, f))
        # invariant (b): every flip must be a code file under a doc-like dir
        for f in undamped:
            if not (DOCLIKE_V2_RE.search(f) and is_code(f)):
                bad_flips.append((rp.name, f))
        print(f"  {lang:7s} {rp.name:28s} files={len(rels):6d} "
              f"v1_damped={n_v1:6d} v2_damped={n_v2:6d} "
              f"undamped_by_v2={len(undamped):5d} newly_damped={len(newly):4d}")
        for f in undamped[:3]:
            print(f"           example undamped: {f}")
        for f in newly[:3]:
            print(f"           example newly-damped: {f}")
    if bad_flips:
        print("\nSPOT-CHECK FAILURES (test-convention files undamped, or "
              "non-doc-dir flips):")
        for repo, f in bad_flips[:20]:
            print(f"  {repo}: {f}")
        raise SystemExit(1)
    print("\nspot-check OK: all v1->v2 flips are code files in doc-like dirs; "
          "every test-convention path still damps")


if __name__ == "__main__":
    main()
