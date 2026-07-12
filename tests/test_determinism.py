"""Regression test for a PYTHONHASHSEED-dependent tie-break bug: select_files
consumed an import-graph neighbor set via `list(edges.get(s, ()))` -- Python
set iteration order for str keys depends on PYTHONHASHSEED, so when two
candidate files tied exactly on add_score (Guarantee 1's `max(imp,
key=add_score)`, and the pool dict's insertion order feeding
`sorted(pool, key=add_score, reverse=True)`), which one won the tie could
swap across otherwise-identical process invocations. Fixed by sorting the
neighbor set at the point it's converted to a list (bgrep.core / lab/
lanes2.py); this test builds a repo engineered to have an exact score tie
across several import-graph siblings and checks the result is byte-identical
across two subprocesses with different PYTHONHASHSEED, and across two
in-process calls.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


# 8 tied siblings, not 2: empirically (see this task's investigation), a
# 2-way tie on this particular pair of path strings didn't happen to flip
# order across a 60-seed PYTHONHASHSEED sample -- a small set's internal hash
# table doesn't always expose the ordering difference for every string pair.
# An 8-way tie flips order on 59/61 sampled seeds pre-fix (and is stable at 1
# ordering across all of them post-fix), so this is what actually catches a
# regression.
_SIBLING_NAMES = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]


def _make_tie_repo(tmp_path: Path) -> Path:
    """A dispatcher file (the top lexical pick / source) that imports N
    sibling files whose content is structurally identical modulo the
    per-sibling name swap. That symmetry guarantees every sibling ties
    EXACTLY on add_score (same document frequency, same term frequency, same
    link strength from the shared source) -- a provable tie, not a numeric
    coincidence -- so Guarantee 1's `max(imp, key=add_score)` and the
    pool-insertion-order-dependent `sorted(pool, key=add_score, ...)` are
    both exercised on a genuine multi-way tie."""
    repo = tmp_path / "repo"
    pkg = repo / "pkg"
    pkg.mkdir(parents=True)
    imports = "\n".join(f"from pkg.{n} import handle_{n}" for n in _SIBLING_NAMES)
    calls = "\n".join(f"    handle_{n}(request)" for n in _SIBLING_NAMES)
    (pkg / "dispatcher.py").write_text(
        '"""Dispatches incoming requests through the pipeline."""\n\n'
        f"{imports}\n\n\n"
        "def dispatch_request(request):\n"
        '    """Route an incoming request through all pipeline branches."""\n'
        f"{calls}\n"
        "    return request\n"
    )
    for n in _SIBLING_NAMES:
        (pkg / f"{n}.py").write_text(
            f'"""{n.capitalize()} branch handler."""\n\n\n'
            f"def handle_{n}(request):\n"
            "    return request\n"
        )
    return repo


_QUERY = "how does the dispatcher route incoming requests through the pipeline"


def _run_cli(args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "bgrep.cli", *args],
        capture_output=True, text=True, timeout=60, env=env,
    )


def test_cli_json_deterministic_across_hashseeds(tmp_path: Path) -> None:
    repo = _make_tie_repo(tmp_path)
    args = [_QUERY, str(repo), "--no-cache", "--no-history", "--json"]

    payloads = []
    for seed in ("1", "2"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        r = _run_cli(args, env)
        assert r.returncode == 0, r.stderr
        payloads.append(json.loads(r.stdout))

    p1, p2 = payloads
    assert p1["files"] == p2["files"], (
        f"files list diverged across PYTHONHASHSEED: {p1['files']} vs {p2['files']}"
    )
    assert p1["regions"] == p2["regions"]
    assert p1["bundle"] == p2["bundle"]

    # The engineered tie must actually be exercised: all N siblings should
    # have been pulled in as candidates (via the shared dispatcher.py
    # source). Verified empirically that PYTHONHASHSEED=1 vs 2 on this exact
    # fixture produces two DIFFERENT orderings of these siblings on the
    # unpatched code, so this specific seed pair does catch the bug.
    paths = {f["path"] for f in p1["files"]}
    for n in _SIBLING_NAMES:
        assert any(p.endswith(f"{n}.py") for p in paths), f"{n}.py missing from candidates"


def test_select_files_deterministic_in_process(tmp_path: Path) -> None:
    from bgrep.core import Corpus, build_import_graph, query_terms, select_files

    repo = _make_tie_repo(tmp_path)
    corpus = Corpus(repo)
    terms = query_terms(_QUERY, [])

    edges = build_import_graph(corpus)
    files1, scores1, explain1 = select_files(
        corpus, terms, use_ppr=True, use_testbridge=True, use_docsbridge=False,
    )
    # Rebuild the import graph from scratch a second time: build_import_graph
    # iterates a fresh defaultdict(set), so this also exercises whether the
    # edges dict itself is assembled deterministically, not just select_files.
    edges2 = build_import_graph(corpus)
    assert edges == edges2
    files2, scores2, explain2 = select_files(
        corpus, terms, use_ppr=True, use_testbridge=True, use_docsbridge=False,
    )

    assert files1 == files2
    assert scores1 == scores2
    assert explain1 == explain2

    paths = set(files1)
    for n in _SIBLING_NAMES:
        assert any(p.endswith(f"{n}.py") for p in paths), f"{n}.py missing from candidates"
