"""WS3b pre-run census (issue #56, round WS3b): multi-format trace counts,
gate-2 risk sets, and the thirdparty gold data-check.

Over all 8 committed slice parquets:

  1. Per-slice trace-format counts under the WS3b parsers (line-for-line
     the engine's `--trace-formats-v2` regexes incl. the Java FQCN->path
     derivation): how many instances carry >=1 parseable non-Python frame,
     and how many of those have a frame that resolves (>=2 trailing
     components against GOLD, resolve_frame_path's gate) to a gold file.
     This is the go/jsts arm decision input and the java/rust ceiling.

  2. Gate-2 risk sets: for Lite + Verified (Python), the instance IDs whose
     issue text matches ANY new-format regex (the only instances where
     `--trace-formats-v2` could possibly change output), plus the CPython
     trace-bearing IDs (the empirical byte-identity sample).

  3. Thirdparty data-check: gold file paths matching the new unconditional
     `(^|/)thirdparty(/|$)` vendor alternate -- expected ZERO everywhere.

Usage: uv run --no-project --with pandas --with pyarrow python \
           lab/research/langagnostic/ws3b_census.py
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

LAB = Path(__file__).resolve().parents[2]

# ------------------------------------------------ engine ports (WS3b regexes)
TB_FRAME_RE = re.compile(r'^\s*File "([^"]+)", line \d+(?:, in (\S.*))?\s*$')
JAVA_FRAME_RE = re.compile(r"^\s*at\s+([\w.$<>/]+)\((([\w$]+)\.(?:java|kt|scala)):\d+\)\s*$")
NODE_FRAME_RE = re.compile(
    r"^\s*at\s+(?:[^\s(]+(?:\s+\[as\s+[^\]]+\])?\s+\()?"
    r"((?:[A-Za-z]:\\|/|\.{1,2}/|[\w@][\w@./-]*/)[^():]+?):\d+:\d+\)?\s*$"
)
GO_FRAME_RE = re.compile(r"^\s*([\w@./-]+\.go):\d+(?:\s+\+0x[0-9a-f]+)?\s*$")
RUST_AT_RE = re.compile(r"^\s*at\s+([\w@./-]+\.rs):\d+(?::\d+)?\s*$")
VENDOR_THIRDPARTY_RE = re.compile(r"(?i)(^|/)thirdparty(/|$)")


def java_frame_path(qualifier: str, filename: str) -> str:
    q = qualifier.rsplit("/", 1)[-1]
    stem = filename.split(".", 1)[0]
    parts = [p for p in q.split(".") if p]
    cls_idx = None
    for i, p in enumerate(parts):
        if p.split("$", 1)[0] == stem:
            cls_idx = i
    if cls_idx is not None:
        pkg = parts[:cls_idx]
    elif len(parts) >= 2:
        pkg = parts[:-2]
    else:
        pkg = []
    return "/".join(pkg + [filename]) if pkg else filename


def v2_frames(text: str) -> list[tuple[str, str]]:
    """(format, derived_path) per non-Python frame, engine classification
    order (python > java > node > rust > go-with-indent-guard)."""
    out: list[tuple[str, str]] = []
    lines = (text or "").splitlines()
    for i, ln in enumerate(lines):
        if TB_FRAME_RE.match(ln):
            continue
        m = JAVA_FRAME_RE.match(ln)
        if m:
            out.append(("java", java_frame_path(m.group(1), m.group(2))))
            continue
        m = NODE_FRAME_RE.match(ln)
        if m:
            out.append(("node", m.group(1)))
            continue
        m = RUST_AT_RE.match(ln)
        if m:
            out.append(("rust", m.group(1)))
            continue
        if i > 0 and (ln.startswith("\t") or ln.startswith("    ")):
            m = GO_FRAME_RE.match(ln)
            if m:
                out.append(("go", m.group(1)))
    return out


def py_trace(text: str) -> bool:
    return any(TB_FRAME_RE.match(ln) for ln in (text or "").splitlines())


def gold_files(patch: str) -> list[str]:
    return sorted({m.group(2) for m in
                   re.finditer(r"^diff --git a/(\S+) b/(\S+)", patch or "", re.M)})


def frame_resolves_gold(path: str, gold: list[str]) -> bool:
    parts = [x for x in path.replace("\\", "/").split("/") if x]
    if not parts:
        return False
    for g in gold:
        gp = g.split("/")
        shared = 0
        while (shared < len(gp) and shared < len(parts)
               and gp[-1 - shared] == parts[-1 - shared]):
            shared += 1
        if shared == len(gp) or shared >= 2:
            return True
    return False


def main() -> None:
    slices = {
        "lite": LAB / "swebench_lite.parquet",
        "verified": LAB / "swebench_verified_heldout.parquet",
        "full": LAB / "swebench_full.parquet",
        "mswe_jsts": LAB / "mswe_jsts.parquet",
        "mswe_ws2c": LAB / "mswe_ws2c.parquet",
        "mswe_c": LAB / "mswe_c.parquet",
        "mswe_cpp": LAB / "mswe_cpp.parquet",
        "ws3a_rust": LAB / "ws3a_rust.parquet",
    }
    rows = []
    thirdparty_gold = []
    for name, pq in slices.items():
        df = pd.read_parquet(pq)
        for _, r in df.iterrows():
            gold = gold_files(r["patch"])
            text = r.get("problem_statement") or ""
            frames = v2_frames(text)
            fmts = Counter(f for f, _ in frames)
            gold_hit_fmts = sorted({f for f, p in frames if frame_resolves_gold(p, gold)})
            tp_gold = [g for g in gold if VENDOR_THIRDPARTY_RE.search(g)]
            thirdparty_gold.extend((name, r["instance_id"], g) for g in tp_gold)
            rows.append({
                "slice": name,
                "instance_id": r["instance_id"],
                "repo": r["repo"],
                "py_trace": py_trace(text),
                "v2_formats": dict(fmts),
                "n_v2_frames": len(frames),
                "v2_gold_resolving_formats": gold_hit_fmts,
                "v2_frame_paths": [p for _, p in frames][:20],
            })

    out = LAB / "research" / "langagnostic" / "ws3b_census.jsonl"
    with out.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")

    print(f"{'slice':10s} {'n':>5s} {'pyTB':>5s} {'v2TB':>5s} {'v2->gold':>8s}  per-format (inst / ->gold)")
    by = defaultdict(list)
    for r in rows:
        by[r["slice"]].append(r)
    for name in slices:
        rs = by[name]
        n = len(rs)
        pytb = sum(r["py_trace"] for r in rs)
        v2tb = sum(1 for r in rs if r["n_v2_frames"] > 0)
        v2g = sum(1 for r in rs if r["v2_gold_resolving_formats"])
        fmt_counts = Counter()
        fmt_gold = Counter()
        for r in rs:
            for f in r["v2_formats"]:
                fmt_counts[f] += 1
            for f in r["v2_gold_resolving_formats"]:
                fmt_gold[f] += 1
        detail = " ".join(f"{f}:{fmt_counts[f]}/{fmt_gold.get(f, 0)}"
                          for f in ("java", "node", "go", "rust") if fmt_counts.get(f))
        print(f"{name:10s} {n:5d} {pytb:5d} {v2tb:5d} {v2g:8d}  {detail}")

    print("\n-- gate-2 risk sets (python slices, any v2-format match) --")
    for name in ("lite", "verified", "full"):
        ids = [r["instance_id"] for r in by[name] if r["n_v2_frames"] > 0]
        print(f"{name}: {len(ids)} -> {ids}")
    lite_tb = [r["instance_id"] for r in by["lite"] if r["py_trace"]]
    print(f"\nlite CPython-trace-bearing: {len(lite_tb)}")
    ver_tb = [r["instance_id"] for r in by["verified"] if r["py_trace"]]
    print(f"verified CPython-trace-bearing: {len(ver_tb)}")

    print("\n-- go/jsts decision + affected-slice gold-resolving IDs --")
    for name in ("mswe_ws2c", "mswe_jsts", "ws3a_rust"):
        hits = [(r["instance_id"], r["v2_gold_resolving_formats"]) for r in by[name]
                if r["v2_gold_resolving_formats"]]
        print(f"{name}: {hits}")

    print(f"\n-- thirdparty gold check: {len(thirdparty_gold)} matches (expect 0) --")
    for row in thirdparty_gold:
        print("   ", row)
    print(f"\nwrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
