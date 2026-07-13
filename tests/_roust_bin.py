"""Locates the release-mode roust-rs binary for subprocess-driven tests.

The Python test suite no longer imports the (now-deleted) roust package --
it drives the real Rust binary via subprocess, exactly as an end user would.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BINARY = _REPO_ROOT / "roust-rs" / "target" / "release" / "roust"


def roust_binary() -> Path:
    """Return the path to the built roust-rs release binary.

    Skips the calling test with a clear message (rather than failing
    confusingly on a missing-file subprocess error) if it hasn't been built:
    `cd roust-rs && cargo build --release`.
    """
    if not _BINARY.is_file():
        pytest.skip(
            f"roust-rs release binary not found at {_BINARY}; "
            "build it first with `cd roust-rs && cargo build --release`"
        )
    return _BINARY
