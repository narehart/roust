"""Regression test for a tie-break bug: select_files consumed an
import-graph neighbor set that could be iterated in a non-deterministic
order, so when two candidate files tied exactly on add_score (Guarantee 1's
`max(imp, key=add_score)`, and the pool dict's insertion order feeding
`sorted(pool, key=add_score, reverse=True)`), which one won the tie could
swap across otherwise-identical process invocations. Fixed by sorting the
neighbor set at the point it's converted to a list; this test builds a repo
engineered to have an exact score tie across several import-graph siblings
and checks the result is byte-identical across two fresh subprocess
invocations of the roust-rs binary.

The original Python-era test also ran the CLI under two different
PYTHONHASHSEED values, since CPython's per-process string-hash
randomization was the mechanism that could flip Python set iteration order.
The Rust binary has no such hash-randomization-dependent iteration, so that
axis is irrelevant here; instead this test simply runs the binary twice,
fresh (no cache), and asserts the JSON output is byte-identical.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from _roust_bin import roust_binary

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


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(roust_binary()), *args],
        capture_output=True, text=True, timeout=60,
    )


def test_cli_json_deterministic_across_fresh_runs(tmp_path: Path) -> None:
    repo = _make_tie_repo(tmp_path)
    args = [_QUERY, str(repo), "--no-cache", "--no-history", "--json"]

    payloads = []
    for _ in range(2):
        r = _run_cli(args)
        assert r.returncode == 0, r.stderr
        payloads.append(json.loads(r.stdout))

    p1, p2 = payloads
    assert p1["files"] == p2["files"], (
        f"files list diverged across fresh runs: {p1['files']} vs {p2['files']}"
    )
    assert p1["regions"] == p2["regions"]
    assert p1["bundle"] == p2["bundle"]

    # The engineered tie must actually be exercised: all N siblings should
    # have been pulled in as candidates (via the shared dispatcher.py
    # source).
    paths = {f["path"] for f in p1["files"]}
    for n in _SIBLING_NAMES:
        assert any(p.endswith(f"{n}.py") for p in paths), f"{n}.py missing from candidates"
