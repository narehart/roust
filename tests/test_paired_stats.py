"""Unit tests for lab/stats/paired_tests.py against hand-computed answers.

McNemar exact values are computed by hand from the binomial definition
p = min(1, 2 * P(X <= min(n01, n10))), X ~ Binomial(n01 + n10, 1/2):
  (1, 9):  2 * (C(10,0) + C(10,1)) / 2^10 = 2 * 11 / 1024 = 0.021484375
  (0, 8):  2 * C(8,0) / 2^8              = 2 / 256       = 0.0078125
Bootstrap known answers use degenerate paired data where every resample's
delta is forced (identical arrays -> 0; constant elementwise shift -> the
shift), so the CI must collapse to a point regardless of resampling."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lab" / "stats"))

from paired_tests import (  # noqa: E402
    compare_runs,
    mcnemar_exact_p,
    paired_bootstrap_ci,
    per_instance_metrics,
)


# ---------------------------------------------------------------------------
# McNemar exact
# ---------------------------------------------------------------------------


def test_mcnemar_known_value_1_9():
    assert mcnemar_exact_p(1, 9) == pytest.approx(0.021484375, abs=1e-12)


def test_mcnemar_known_value_0_8():
    assert mcnemar_exact_p(0, 8) == pytest.approx(0.0078125, abs=1e-12)


def test_mcnemar_no_discordant_pairs_is_1():
    assert mcnemar_exact_p(0, 0) == 1.0


def test_mcnemar_balanced_discordants_capped_at_1():
    # 2 * P(X <= 5), X ~ Bin(10, 1/2) = 2 * 638/1024 = 1.246... -> capped
    assert mcnemar_exact_p(5, 5) == 1.0


def test_mcnemar_symmetric_in_arguments():
    assert mcnemar_exact_p(2, 7) == mcnemar_exact_p(7, 2)


def test_mcnemar_rejects_negative_counts():
    with pytest.raises(ValueError):
        mcnemar_exact_p(-1, 3)


# ---------------------------------------------------------------------------
# paired bootstrap
# ---------------------------------------------------------------------------


def test_bootstrap_identical_arrays_gives_zero_point_ci():
    a = [0.0, 1.0, 1.0, 0.0, 1.0] * 4
    delta, lo, hi = paired_bootstrap_ci(a, list(a), n_boot=500, seed=1)
    assert delta == 0.0 and lo == 0.0 and hi == 0.0


def test_bootstrap_constant_shift_gives_point_ci_at_shift():
    a = [0.1 * i for i in range(20)]
    b = [x + 0.5 for x in a]
    delta, lo, hi = paired_bootstrap_ci(a, b, n_boot=500, seed=1)
    assert delta == pytest.approx(0.5)
    assert lo == pytest.approx(0.5) and hi == pytest.approx(0.5)


def test_bootstrap_deterministic_for_seed_and_ordered():
    a = [0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0]
    b = [1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0]
    r1 = paired_bootstrap_ci(a, b, n_boot=2000, seed=42)
    r2 = paired_bootstrap_ci(a, b, n_boot=2000, seed=42)
    assert r1 == r2
    delta, lo, hi = r1
    assert lo <= delta <= hi
    # delta bounded by the extreme per-instance diffs
    assert lo >= min(bv - av for av, bv in zip(a, b))
    assert hi <= max(bv - av for av, bv in zip(a, b))


def test_bootstrap_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        paired_bootstrap_ci([1.0, 2.0], [1.0], n_boot=10, seed=1)


# ---------------------------------------------------------------------------
# per-instance extraction
# ---------------------------------------------------------------------------


def test_per_instance_metrics_extraction_and_error_convention():
    predictions = {
        "ok-full": {"instance_id": "ok-full", "error": None,
                     "all_gold_files_retrieved": True, "hunk_line_recall": 1.0},
        "ok-partial": {"instance_id": "ok-partial", "error": None,
                        "all_gold_files_retrieved": True, "hunk_line_recall": 0.25},
        "engine-err": {"instance_id": "engine-err", "error": "timed out"},
    }
    detail = {"ok-full": True}  # ok-partial judged wrong is absent -> False
    m = per_instance_metrics(predictions, detail)
    assert m["ok-full"] == {"file": 1.0, "function": 1.0, "line": 1.0, "fraction": 1.0}
    assert m["ok-partial"] == {"file": 1.0, "function": 0.0, "line": 0.0, "fraction": 0.25}
    # error records: wrong at every level, fraction 0.0, SAME denominator
    assert m["engine-err"] == {"file": 0.0, "function": 0.0, "line": 0.0, "fraction": 0.0}


# ---------------------------------------------------------------------------
# end-to-end comparison on synthetic runs
# ---------------------------------------------------------------------------


def _mk(vals: dict[str, tuple[float, float, float, float]]) -> dict[str, dict[str, float]]:
    return {iid: {"file": f, "function": fn, "line": ln, "fraction": fr}
            for iid, (f, fn, ln, fr) in vals.items()}


def test_compare_runs_known_deltas_and_mcnemar():
    # 4 instances; FILE: A correct on {i1}, B correct on {i1, i2, i3}
    a = _mk({
        "i1": (1, 1, 1, 1.0),
        "i2": (0, 0, 0, 0.5),
        "i3": (0, 0, 0, 0.0),
        "i4": (0, 0, 0, 0.5),
    })
    b = _mk({
        "i1": (1, 1, 1, 1.0),
        "i2": (1, 0, 0, 0.5),
        "i3": (1, 0, 0, 1.0),
        "i4": (0, 0, 0, 0.5),
    })
    rep = compare_runs(a, b, n_boot=200, seed=7)
    f = rep["metrics"]["file"]
    assert f["mean_a"] == 25.0 and f["mean_b"] == 75.0
    assert f["delta"] == pytest.approx(50.0)
    mc = f["mcnemar"]
    assert mc["n01_a_wrong_b_correct"] == 2 and mc["n10_a_correct_b_wrong"] == 0
    # 2 * P(X <= 0), X ~ Bin(2, 1/2) = 2 * 1/4 = 0.5
    assert mc["p_exact_two_sided"] == pytest.approx(0.5)
    # FUNCTION identical between arms -> delta 0, point CI, p = 1
    fn = rep["metrics"]["function"]
    assert fn["delta"] == 0.0 and fn["ci95"] == [0.0, 0.0]
    assert fn["mcnemar"]["p_exact_two_sided"] == 1.0
    # fraction: mean_a = 0.5, mean_b = 0.75 (raw fraction units, not pp)
    fr = rep["metrics"]["fraction"]
    assert fr["mean_a"] == pytest.approx(0.5) and fr["mean_b"] == pytest.approx(0.75)
    assert fr["units"] == "fraction"


def test_compare_runs_rejects_mismatched_instance_sets():
    a = _mk({"i1": (1, 1, 1, 1.0)})
    b = _mk({"i2": (1, 1, 1, 1.0)})
    with pytest.raises(SystemExit):
        compare_runs(a, b, n_boot=10, seed=1)
