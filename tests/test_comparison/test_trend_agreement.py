"""Tests for cross-dataset trend agreement analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.trend_agreement import (
    TrendAgreementResult,
    compute_overlap_window,
    compute_trend_agreement,
)
from WA.comparison.trends import TrendResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trend_result(
    dataset_id: str,
    direction: float,
    *,
    start: str = "2000-01-01",
    end: str = "2009-12-31",
    slope: float = 0.01,
    lat: list[float] | None = None,
    lon: list[float] | None = None,
) -> TrendResult:
    """Create a TrendResult with uniform direction/slope across all pixels."""
    if lat is None:
        lat = [1.0, 0.0]
    if lon is None:
        lon = [100.0, 101.0]

    shape = (len(lat), len(lon))
    coords = {"lat": lat, "lon": lon}

    def _da(value: float, dtype: type = float) -> xr.DataArray:
        return xr.DataArray(
            np.full(shape, value, dtype=dtype),
            dims=["lat", "lon"],
            coords=coords,
        )

    return TrendResult(
        dataset_id=dataset_id,
        aggregation="annual",
        time_range=(start, end),
        observation_count=10,
        sens_slope=_da(slope if direction > 0 else -slope if direction < 0 else 0.0),
        p_value=_da(0.01),
        z_score=_da(2.5 * direction),
        significant=_da(1.0 if direction != 0 else 0.0).astype(bool),
        trend_direction=_da(direction, dtype=np.int8),
        status="computed",
    )


# ---------------------------------------------------------------------------
# compute_overlap_window
# ---------------------------------------------------------------------------


def test_overlap_window_common_range():
    results = {
        "a": _make_trend_result("a", 1.0, start="2000-01-01", end="2010-12-31"),
        "b": _make_trend_result("b", 1.0, start="2003-01-01", end="2015-12-31"),
    }
    window = compute_overlap_window(results)
    assert window is not None
    start, end = window
    assert pd.Timestamp(start) == pd.Timestamp("2003-01-01")
    assert pd.Timestamp(end) == pd.Timestamp("2010-12-31")


def test_overlap_window_no_overlap():
    results = {
        "a": _make_trend_result("a", 1.0, start="2000-01-01", end="2005-12-31"),
        "b": _make_trend_result("b", 1.0, start="2006-01-01", end="2010-12-31"),
    }
    window = compute_overlap_window(results)
    assert window is None


def test_overlap_window_single_dataset():
    results = {
        "a": _make_trend_result("a", 1.0, start="2000-01-01", end="2010-12-31"),
    }
    window = compute_overlap_window(results)
    assert window is not None


# ---------------------------------------------------------------------------
# compute_trend_agreement
# ---------------------------------------------------------------------------


def test_trend_agreement_all_increasing():
    results = {
        "a": _make_trend_result("a", 1.0),
        "b": _make_trend_result("b", 1.0),
        "c": _make_trend_result("c", 1.0),
    }
    agreement = compute_trend_agreement(results, min_overlap_years=1)
    assert agreement.status == "computed"
    # All datasets increasing → robust_increase everywhere
    assert bool(agreement.robust_increase.all().item())
    assert not bool(agreement.robust_decrease.any().item())
    assert not bool(agreement.disputed.any().item())
    # Agreement ratio should be 1.0
    assert float(agreement.agreement_ratio.min()) == pytest.approx(1.0)


def test_trend_agreement_all_decreasing():
    results = {
        "a": _make_trend_result("a", -1.0),
        "b": _make_trend_result("b", -1.0),
    }
    agreement = compute_trend_agreement(results, min_overlap_years=1)
    assert agreement.status == "computed"
    assert bool(agreement.robust_decrease.all().item())
    assert not bool(agreement.robust_increase.any().item())
    assert float(agreement.agreement_ratio.min()) == pytest.approx(1.0)


def test_trend_agreement_disputed():
    results = {
        "a": _make_trend_result("a", 1.0),
        "b": _make_trend_result("b", -1.0),
    }
    agreement = compute_trend_agreement(results, min_overlap_years=1)
    assert agreement.status == "computed"
    # Neither all-increase nor all-decrease
    assert not bool(agreement.robust_increase.any().item())
    assert not bool(agreement.robust_decrease.any().item())
    # Disputed everywhere
    assert bool(agreement.disputed.all().item())
    # Agreement ratio = 0.5 (one out of two)
    assert float(agreement.agreement_ratio.mean()) == pytest.approx(0.5)


def test_trend_agreement_overlap_too_short():
    """Overlap shorter than min_overlap_years → overlap_window_empty."""
    results = {
        "a": _make_trend_result("a", 1.0, start="2000-01-01", end="2001-06-30"),
        "b": _make_trend_result("b", 1.0, start="2000-01-01", end="2001-06-30"),
    }
    agreement = compute_trend_agreement(results, min_overlap_years=5)
    assert agreement.status == "overlap_window_empty"


def test_trend_agreement_regional_summary():
    results = {
        "a": _make_trend_result("a", 1.0),
        "b": _make_trend_result("b", 1.0),
    }
    from WA.comparison.focus_areas import DEFAULT_FOCUS_REGION_BBOXES

    agreement = compute_trend_agreement(
        results,
        min_overlap_years=1,
        region_bboxes=DEFAULT_FOCUS_REGION_BBOXES,
    )
    assert agreement.status == "computed"
    summary = agreement.regional_summary
    assert "global" in summary["region"].values
    expected_cols = {
        "region",
        "total_valid_pixels",
        "mean_agreement_ratio",
        "fraction_robust_increase",
        "fraction_robust_decrease",
        "fraction_robust_stable",
        "fraction_disputed",
        "mean_slope_across_datasets",
    }
    assert expected_cols.issubset(set(summary.columns))


def test_trend_agreement_mean_slope():
    """Mean slope should average across datasets."""
    results = {
        "a": _make_trend_result("a", 1.0, slope=0.02),
        "b": _make_trend_result("b", 1.0, slope=0.04),
    }
    agreement = compute_trend_agreement(results, min_overlap_years=1)
    assert agreement.status == "computed"
    # Mean slope of 0.02 and 0.04 → 0.03
    assert float(agreement.mean_slope.mean()) == pytest.approx(0.03, abs=1e-6)
