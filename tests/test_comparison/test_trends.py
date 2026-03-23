"""Tests for per-pixel Mann-Kendall trend analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.trends import (
    TrendResult,
    _aggregate_time_series,
    _pixel_mann_kendall,
    compute_pixel_trends,
    compute_regional_summary,
    compute_year_over_year_change,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_surface(
    values_1d: list[float],
    *,
    start: str = "2000-01",
    freq: str = "MS",
    lat: list[float] | None = None,
    lon: list[float] | None = None,
) -> xr.DataArray:
    """Create a (time, lat, lon) DataArray with the same 1-D values at every pixel."""
    if lat is None:
        lat = [1.0, 0.0]
    if lon is None:
        lon = [100.0, 101.0]

    n = len(values_1d)
    times = pd.date_range(start=start, periods=n, freq=freq)
    arr = np.array(values_1d, dtype=float)
    # Broadcast to (time, lat, lon)
    data = np.broadcast_to(
        arr[:, None, None], (n, len(lat), len(lon))
    ).copy()
    return xr.DataArray(
        data,
        dims=["time", "lat", "lon"],
        coords={"time": times, "lat": lat, "lon": lon},
    )


# 60 monthly steps = 5 years → annual aggregation gives 5 annual obs (≥ min_observations=5)
_INCREASING = list(np.linspace(0.1, 0.9, 60))  # clear upward trend
_DECREASING = list(np.linspace(0.9, 0.1, 60))  # clear downward trend
_STABLE = [0.5] * 60  # no trend


# ---------------------------------------------------------------------------
# _pixel_mann_kendall unit tests
# ---------------------------------------------------------------------------


def test_pixel_mk_increasing():
    vals = np.linspace(0.1, 0.9, 20)
    slope, pval, z, sig, direction = _pixel_mann_kendall(vals, alpha=0.05)
    assert slope > 0
    assert pval < 0.05
    assert direction == 1.0


def test_pixel_mk_decreasing():
    vals = np.linspace(0.9, 0.1, 20)
    slope, pval, z, sig, direction = _pixel_mann_kendall(vals, alpha=0.05)
    assert slope < 0
    assert pval < 0.05
    assert direction == -1.0


def test_pixel_mk_stable_flat():
    vals = np.full(20, 0.5)
    slope, pval, z, sig, direction = _pixel_mann_kendall(vals, alpha=0.05)
    assert slope == 0.0
    assert direction == 0.0


def test_pixel_mk_too_short():
    vals = np.array([0.1, 0.5, 0.9])
    slope, pval, z, sig, direction = _pixel_mann_kendall(vals, alpha=0.05)
    assert np.isnan(slope)
    assert pval == 1.0
    assert direction == 0.0


# ---------------------------------------------------------------------------
# compute_pixel_trends
# ---------------------------------------------------------------------------


def test_compute_pixel_trends_increasing():
    surface = _make_surface(_INCREASING)
    result = compute_pixel_trends(surface, dataset_id="wad2m", aggregation="annual")
    assert isinstance(result, TrendResult)
    assert result.status == "computed"
    # All pixels should show positive slope
    assert float(result.sens_slope.min()) > 0
    # All pixels should have direction = +1
    assert int(result.trend_direction.min()) == 1


def test_compute_pixel_trends_decreasing():
    surface = _make_surface(_DECREASING)
    result = compute_pixel_trends(surface, dataset_id="wad2m", aggregation="annual")
    assert result.status == "computed"
    assert float(result.sens_slope.max()) < 0
    assert int(result.trend_direction.max()) == -1


def test_compute_pixel_trends_stable():
    surface = _make_surface(_STABLE)
    result = compute_pixel_trends(surface, dataset_id="wad2m", aggregation="annual")
    assert result.status == "computed"
    # Slope should be ~0, direction should be 0
    assert abs(float(result.sens_slope.mean())) < 1e-10
    assert int(result.trend_direction.max()) == 0


def test_compute_pixel_trends_insufficient_observations():
    """Fewer than min_observations time steps → insufficient_observations."""
    surface = _make_surface([0.1, 0.5, 0.9])  # only 3 months
    result = compute_pixel_trends(
        surface, dataset_id="wad2m", aggregation="annual", min_observations=5
    )
    assert result.status == "insufficient_observations"
    assert result.observation_count < 5
    # Slope should be all-NaN
    assert np.all(np.isnan(result.sens_slope.values))


def test_compute_pixel_trends_metadata():
    surface = _make_surface(_INCREASING)
    result = compute_pixel_trends(
        surface, dataset_id="swamps", aggregation="monthly"
    )
    assert result.dataset_id == "swamps"
    assert result.aggregation == "monthly"
    assert result.time_range[0] <= result.time_range[1]


# ---------------------------------------------------------------------------
# compute_year_over_year_change
# ---------------------------------------------------------------------------


def test_compute_yoy_change_increasing():
    # Linearly increasing → all deltas positive
    values = list(np.linspace(0.1, 0.9, 5))
    # Use yearly frequency so annual resample gives one point per year
    times = pd.date_range("2000", periods=5, freq="YS")
    data = xr.DataArray(
        np.broadcast_to(
            np.array(values)[:, None, None], (5, 2, 2)
        ).copy(),
        dims=["time", "lat", "lon"],
        coords={"time": times, "lat": [1.0, 0.0], "lon": [100.0, 101.0]},
    )
    ds = compute_year_over_year_change(data, dataset_id="wad2m")
    assert "delta_fraction" in ds
    assert "change_direction" in ds
    # All deltas should be positive
    assert float(ds["delta_fraction"].min()) > 0
    assert int(ds["change_direction"].min()) == 1


# ---------------------------------------------------------------------------
# compute_regional_summary
# ---------------------------------------------------------------------------


def test_compute_regional_summary_covers_all_regions():
    from WA.comparison.focus_areas import DEFAULT_FOCUS_REGION_BBOXES

    surface = _make_surface(_INCREASING)
    result = compute_pixel_trends(surface, dataset_id="wad2m", aggregation="annual")
    summary = compute_regional_summary(result, DEFAULT_FOCUS_REGION_BBOXES)

    assert isinstance(summary, __import__("pandas").DataFrame)
    # "global" row always present
    assert "global" in summary["region"].values


def test_compute_regional_summary_columns():
    from WA.comparison.focus_areas import DEFAULT_FOCUS_REGION_BBOXES

    surface = _make_surface(_INCREASING)
    result = compute_pixel_trends(surface, dataset_id="wad2m", aggregation="annual")
    summary = compute_regional_summary(result, DEFAULT_FOCUS_REGION_BBOXES)

    expected_cols = {
        "region",
        "total_valid_pixels",
        "mean_slope",
        "median_slope",
        "fraction_significant",
        "fraction_increasing",
        "fraction_decreasing",
        "fraction_stable",
    }
    assert expected_cols.issubset(set(summary.columns))


# ---------------------------------------------------------------------------
# _aggregate_time_series
# ---------------------------------------------------------------------------


def test_annual_aggregation():
    surface = _make_surface(_INCREASING, start="2000-01", freq="MS")
    agg = _aggregate_time_series(surface, "annual")
    assert "time" in agg.dims
    # 20 monthly steps ≈ 1-2 full years
    assert agg.sizes["time"] >= 1


def test_monthly_aggregation_preserves_resolution():
    surface = _make_surface(_INCREASING, start="2000-01", freq="MS")
    agg = _aggregate_time_series(surface, "monthly")
    # Monthly resampling of monthly data → same number of steps
    assert agg.sizes["time"] == surface.sizes["time"]


def test_seasonal_aggregation_groups():
    # 4 years of monthly data → 4 seasons
    n = 48
    surface = _make_surface(list(np.linspace(0.1, 0.9, n)), start="2000-01", freq="MS")
    agg = _aggregate_time_series(surface, "seasonal")
    assert "season" in agg.dims
    # Should have at most 4 seasons
    assert agg.sizes["season"] <= 4
