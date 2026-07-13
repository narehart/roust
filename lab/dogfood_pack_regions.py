#!/usr/bin/env python3
"""Dogfood repro/gate for the pack_regions symbol-name-anchoring fix.

Drives lanes2 directly (Corpus / query_terms / extract_symbol_anchors /
select_files / pack_regions) against THIS repo's own tracked source tree,
wired up exactly like parity/shim_reference.py's frozen-v7 config
(history=True, comments=False, anchors=True, testbridge=True,
docsbridge=True, use_ppr=True, keywords=[]) -- the same wiring
region_eval_lanes.py's quantitative harness uses, so the dogfood check and
the quantitative gate exercise the identical pipeline.

The corpus is scoped to `git ls-files` (tracked + untracked-but-not-ignored)
via symlinks into a scratch snapshot dir, mirroring src/roust/core.py's
_candidate_files -- lanes2.Corpus itself does a raw rglob, which would
otherwise pull in .venv/roust-rs/target/lab/swebench_repos and blow up the
corpus with unrelated files. Read-only: never writes into REPO_PATH.

For each of the two dogfood queries and each w_name in {0.0, 1.0, 2.0, 4.0},
prints the ranked regions returned for src/roust/core.py and reports whether
the target function (pack_regions / build_import_graph) made it in.

Usage: python3 lab/dogfood_pack_regions.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_PATH = Path(__file__).resolve().parent.parent
LAB_DIR = REPO_PATH / "lab"
sys.path.insert(0, str(LAB_DIR))

import lanes2 as L  # noqa: E402
from history import mine_history  # noqa: E402

import tiktoken  # noqa: E402

_ENCODER = tiktoken.get_encoding("cl100k_base")
_BUDGET_TOKENS = 8192

_SCRATCH = Path(
    "/private/tmp/claude-501/-Users-nicholasarehart-programming-projects-bgrep/"
    "3ab12e71-fab2-4a81-bb2b-84700d211ef2/scratchpad"
)

QUERIES = [
    ("how is the token budget enforced when packing regions into the bundle", "pack_regions"),
    ("where would I add support for a new language's import graph", "build_import_graph"),
]

W_NAME_SWEEP = [0.0, 1.0, 2.0, 4.0]

TARGET_FILE = "src/roust/core.py"


def count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text, disallowed_special=()))


def _git_scoped_snapshot(repo_path: Path, scratch_root: Path) -> Path:
    """Symlink snapshot of `git ls-files` (tracked + untracked-not-ignored)
    under scratch_root, so lanes2.Corpus's raw rglob only ever sees the
    repo's real tracked source tree -- never .venv/roust-rs/target/
    lab/swebench_repos/etc (all gitignored). Read-only against repo_path."""
    tracked = subprocess.run(
        ["git", "-C", str(repo_path), "ls-files", "-z"],
        capture_output=True,
    ).stdout.split(b"\0")
    untracked = subprocess.run(
        ["git", "-C", str(repo_path), "ls-files", "-z", "--others", "--exclude-standard"],
        capture_output=True,
    ).stdout.split(b"\0")
    rels = sorted({p.decode("utf-8", errors="replace") for p in tracked + untracked if p})

    snap = scratch_root / "dogfood_snapshot"
    if snap.exists():
        import shutil
        shutil.rmtree(snap)
    snap.mkdir(parents=True)
    for rel in rels:
        src = repo_path / rel
        if not src.is_file():
            continue
        dst = snap / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(src.resolve(), dst)
        except OSError:
            continue
    return snap


def _list_current_files(repo_path: Path) -> set[str]:
    """Mirror of shim_reference.py's _list_current_files, over the snapshot
    (identical content to the real tree, cheaper/safer to walk)."""
    files: set[str] = set()
    for p in repo_path.rglob("*"):
        if not p.is_file() or p.suffix not in L.CODE_EXTENSIONS:
            continue
        rel = str(p.relative_to(repo_path))
        if rel.startswith(".git/") or "/.git/" in rel:
            continue
        files.add(rel)
    return files


def main() -> None:
    snap = _git_scoped_snapshot(REPO_PATH, _SCRATCH)
    print(f"corpus snapshot: {snap} (git-ls-files scoped)")

    current_files = _list_current_files(snap)
    # mine_history walks `git log` from HEAD of its cwd -- run it against the
    # REAL repo (has .git; the snapshot doesn't), which is safe/read-only.
    history_msgs, cochange, _meta = mine_history(REPO_PATH, current_files=current_files)

    corpus = L.Corpus(snap, history_msgs=history_msgs, use_comments=False, build_docs=True)
    print(f"corpus: {corpus.n_docs} files\n")

    overall_pass = True
    for question, target_symbol in QUERIES:
        print("=" * 100)
        print(f"QUERY: {question!r}")
        print(f"expects: {target_symbol}() region present in {TARGET_FILE}'s packed regions")
        terms = L.query_terms(question, [])
        anchors = L.extract_symbol_anchors(question, corpus)
        files, scores = L.select_files(
            corpus, terms, use_ppr=True, cochange=cochange, anchors=anchors,
            use_testbridge=True, use_docsbridge=True,
        )
        rank = files.index(TARGET_FILE) + 1 if TARGET_FILE in files else None
        print(f"file rank of {TARGET_FILE}: {rank}")

        for w_name in W_NAME_SWEEP:
            spans, _bundle = L.pack_regions(
                corpus, files, terms, scores, _BUDGET_TOKENS, count_tokens, w_name=w_name
            )
            file_spans = spans.get(TARGET_FILE, [])
            # Resolve each returned span back to its defining symbol name for
            # a human-readable ranking printout.
            def_lines = L._file_def_lines(corpus.text[TARGET_FILE], L._def_re_for(TARGET_FILE))
            names = [L._region_symbol(def_lines, a, b) or f"<lines {a}-{b}>" for a, b in file_spans]
            hit = target_symbol in names
            if w_name == 0.0 and not hit:
                pass  # expected to fail pre-fix
            print(f"  w_name={w_name:4} -> {TARGET_FILE} regions: {names}  "
                  f"[{'PASS' if hit else 'FAIL'}: {target_symbol} {'present' if hit else 'ABSENT'}]")
            if w_name > 0.0 and not hit:
                overall_pass = False
        print()

    print("=" * 100)
    print("GATE:", "PASS (both queries return the target function at w_name>0)" if overall_pass
          else "FAIL (target function still missing at some w_name>0)")
    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
