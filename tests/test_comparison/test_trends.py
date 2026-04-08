"""Tests for per-pixel Mann-Kendall trend analysis."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rioxarray  # noqa: F401
import xarray as xr
from pytest import MonkeyPatch

from WA.comparison import trends as trends_module
from WA.comparison.harmonize import create_comparison_grid
from WA.comparison.trends import (
    TrendResult,
    _aggregate_time_series,
    _pixel_mann_kendall,
    build_gwd30_native_pixel_statistics_tiles,
    build_gwd30_pixel_statistics,
    compute_pixel_trends,
    compute_regional_summary,
    compute_year_over_year_change,
    load_trend_checkpoint,
    materialize_trend_checkpoint,
    phase4_gwd30_pixel_stats_tile_dir,
    trend_checkpoint_output_path,
    write_trend_checkpoint,
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


def test_materialize_trend_checkpoint_reuses_existing_checkpoint(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    load_calls: list[dict[str, object]] = []
    surface = _make_surface(_INCREASING)

    def _fake_load_trend_surface(*args, **kwargs):  # type: ignore[no-untyped-def]
        load_calls.append(kwargs)
        return surface

    monkeypatch.setattr(trends_module, "load_trend_surface", _fake_load_trend_surface)

    first = materialize_trend_checkpoint(
        output_root=tmp_path,
        region_id="amazon",
        bbox=(99.5, -0.5, 101.5, 1.5),
        dataset_id="wad2m",
        time_range=("2000-01-01", "2004-12-31"),
        aggregation="annual",
        min_observations=5,
        show_progress=False,
        skip_existing=True,
    )
    second = materialize_trend_checkpoint(
        output_root=tmp_path,
        region_id="amazon",
        bbox=(99.5, -0.5, 101.5, 1.5),
        dataset_id="wad2m",
        time_range=("2000-01-01", "2004-12-31"),
        aggregation="annual",
        min_observations=5,
        show_progress=False,
        skip_existing=True,
    )

    assert len(load_calls) == 1
    assert first.checkpoint_path == second.checkpoint_path
    assert second.requested_time_range == ("2000-01-01", "2004-12-31")
    assert second.time_range == ("2000-01-01", "2004-12-01")
    assert second.trend_result.status == "computed"
    assert trend_checkpoint_output_path(
        tmp_path,
        region_id="amazon",
        dataset_id="wad2m",
        aggregation="annual",
        time_range=("2000-01-01", "2004-12-31"),
    ).is_file()


def test_load_trend_checkpoint_rejects_mixed_metadata(tmp_path: Path) -> None:
    trend_result = compute_pixel_trends(
        _make_surface(_INCREASING),
        dataset_id="wad2m",
        aggregation="annual",
    )
    checkpoint_path = trend_checkpoint_output_path(
        tmp_path,
        region_id="amazon",
        dataset_id="wad2m",
        aggregation="annual",
        time_range=("2000-01-01", "2004-12-31"),
    )
    write_trend_checkpoint(
        checkpoint_path,
        region_id="amazon",
        requested_time_range=("2000-01-01", "2004-12-31"),
        bbox=(99.5, -0.5, 101.5, 1.5),
        trend_result=trend_result,
    )

    broken = xr.load_dataset(checkpoint_path)
    broken.attrs["aggregation"] = "monthly"
    broken.to_netcdf(checkpoint_path, mode="w")

    with pytest.raises(ValueError, match="mixed checkpoint metadata"):
        load_trend_checkpoint(
            checkpoint_path,
            expected_region_id="amazon",
            expected_dataset_id="wad2m",
            expected_aggregation="annual",
            expected_time_range=("2000-01-01", "2004-12-31"),
        )


def test_load_trend_surface_uses_gwd30_staged_tiles(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    bbox = (100.0, 0.0, 102.0, 2.0)
    reference_grid = create_comparison_grid(bbox, resolution_deg=1.0)
    merge_calls: list[dict[str, object]] = []
    standardized_dir = tmp_path / "standardized"

    class FakeGwd30Loader:
        def merge_staged_time_fraction_tiles(self, **kwargs):  # type: ignore[no-untyped-def]
            merge_calls.append(kwargs)
            year = int(kwargs["year"])
            wetland_value = 1.0 if year == 2013 else 0.0
            times = pd.to_datetime([f"{year}-01-01", f"{year}-01-05"])
            wetland = np.full((2, 2, 2), wetland_value, dtype=np.float32)
            non_wetland = np.full((2, 2, 2), 1.0 - wetland_value, dtype=np.float32)
            coords = {
                "time": times,
                "lat": reference_grid.coords["lat"].values,
                "lon": reference_grid.coords["lon"].values,
            }
            return xr.Dataset(
                {
                    "frac_0": xr.DataArray(
                        non_wetland,
                        dims=("time", "lat", "lon"),
                        coords=coords,
                    ),
                    "frac_8": xr.DataArray(
                        wetland,
                        dims=("time", "lat", "lon"),
                        coords=coords,
                    ),
                },
                attrs={"dataset_id": "gwd30"},
            )

    fake_loader = FakeGwd30Loader()
    monkeypatch.setattr(
        trends_module,
        "get_dataset_config",
        lambda _dataset_id: {"years": [2013, 2014]},
    )
    monkeypatch.setattr(
        trends_module,
        "get_loader",
        lambda _dataset_id, _dataset_config: fake_loader,
    )

    for year in (2013, 2014):
        staging_root = standardized_dir / "_staging" / f"gwd30_{year}"
        tile_dir = staging_root / "tile_partials"
        tile_dir.mkdir(parents=True)
        tile_path = tile_dir / f"tile_{year}.nc"
        tile_path.touch()
        (staging_root / "stage_shard_0000_of_0064.json").write_text(
            (
                '{\n'
                '  "staged_tiles": [\n'
                f'    {{"path": "{tile_path}", "bbox": [100.0, 0.0, 102.0, 2.0]}}\n'
                "  ]\n"
                "}\n"
            ),
            encoding="utf-8",
        )

    surface = trends_module.load_trend_surface(
        "gwd30",
        bbox=bbox,
        time_range=("2013-01-01", "2014-01-05"),
        reference_grid=reference_grid,
        gwd30_standardized_dir=standardized_dir,
        show_progress=False,
    )

    assert len(merge_calls) == 2
    assert [int(call["year"]) for call in merge_calls] == [2013, 2014]
    assert all(call["reference_grid"] is reference_grid for call in merge_calls)
    assert all(
        Path(call["staged_tiles"][0][0]).parent.parent.parent == standardized_dir / "_staging"
        for call in merge_calls
    )
    assert surface.sizes["time"] == 4
    np.testing.assert_allclose(
        np.asarray(surface.sel(time="2013-01-01").values, dtype=np.float32),
        1.0,
    )
    np.testing.assert_allclose(
        np.asarray(surface.sel(time="2014-01-05").values, dtype=np.float32),
        0.0,
    )


def test_build_gwd30_pixel_statistics_monthly(monkeypatch: MonkeyPatch) -> None:
    bbox = (100.0, 0.0, 102.0, 2.0)
    reference_grid = create_comparison_grid(bbox, resolution_deg=1.0)
    times = pd.to_datetime(
        [
            "2013-01-01",
            "2013-01-05",
            "2013-02-01",
            "2013-02-05",
        ]
    )
    values = np.array([0.2, 0.4, 0.6, 0.8], dtype=np.float32)
    surface = xr.DataArray(
        np.broadcast_to(values[:, None, None], (4, 2, 2)).copy(),
        dims=("time", "lat", "lon"),
        coords={
            "time": times,
            "lat": reference_grid.coords["lat"].values,
            "lon": reference_grid.coords["lon"].values,
        },
        name="wetland_fraction",
    )
    surface = surface.rio.write_crs("EPSG:4326", inplace=False)
    surface = surface.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)

    monkeypatch.setattr(
        trends_module,
        "load_trend_surface",
        lambda *args, **kwargs: surface,
    )

    stats_ds = build_gwd30_pixel_statistics(
        bbox=bbox,
        time_range=("2013-01-01", "2013-12-31"),
        aggregation="monthly",
        reference_grid=reference_grid,
        show_progress=False,
    )

    assert set(stats_ds.data_vars) == {
        "wetland_fraction",
        "valid_observation_count",
        "mean_wetland_fraction",
        "std_wetland_fraction",
        "cell_area_km2",
    }
    assert stats_ds["wetland_fraction"].sizes["time"] == 2
    np.testing.assert_allclose(
        np.asarray(stats_ds["wetland_fraction"].isel(time=0).values, dtype=np.float32),
        0.3,
    )
    np.testing.assert_allclose(
        np.asarray(stats_ds["wetland_fraction"].isel(time=1).values, dtype=np.float32),
        0.7,
    )
    np.testing.assert_array_equal(
        np.asarray(stats_ds["valid_observation_count"].values, dtype=np.int32),
        np.full((2, 2), 2, dtype=np.int32),
    )
    assert float(stats_ds["cell_area_km2"].min()) > 0.0


def test_build_gwd30_native_pixel_statistics_tiles_monthly(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    standardized_dir = tmp_path / "standardized"
    staging_root = standardized_dir / "_staging" / "gwd30_2013"
    tile_dir = staging_root / "tile_partials"
    tile_dir.mkdir(parents=True)
    tile_path = tile_dir / "tile_demo.nc"

    times = pd.to_datetime(
        [
            "2013-01-01",
            "2013-01-05",
            "2013-02-01",
            "2013-02-05",
        ]
    )
    weighted = xr.DataArray(
        np.array(
            [
                [[[0.2]]],
                [[[0.4]]],
                [[[0.6]]],
                [[[0.8]]],
            ],
            dtype=np.float32,
        ),
        dims=("time", "class_id", "lat", "lon"),
        coords={"time": times, "class_id": [8], "lat": [0.5], "lon": [100.5]},
        name="weighted",
    )
    coverage = xr.DataArray(
        np.ones((4, 1, 1), dtype=np.float32),
        dims=("time", "lat", "lon"),
        coords={"time": times, "lat": [0.5], "lon": [100.5]},
        name="coverage",
    )
    xr.Dataset({"weighted": weighted, "coverage": coverage}).to_netcdf(tile_path)
    (staging_root / "stage_shard_0000_of_0064.json").write_text(
        (
            '{\n'
            '  "staged_tiles": [\n'
            f'    {{"path": "{tile_path}", "bbox": [100.0, 0.0, 101.0, 1.0]}}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        trends_module,
        "get_dataset_config",
        lambda _dataset_id: {
            "name": "GWD30",
            "loader_type": "gwd30",
            "path": str(tmp_path),
            "years": [2013],
        },
    )

    transformed = build_gwd30_native_pixel_statistics_tiles(
        output_root=tmp_path / "results",
        standardized_dir=standardized_dir,
        years=[2013],
        aggregation="monthly",
        worker_count=1,
        show_progress=False,
        skip_existing=False,
    )

    assert 2013 in transformed
    assert len(transformed[2013]) == 1
    output_dir = phase4_gwd30_pixel_stats_tile_dir(
        output_root=tmp_path / "results",
        year=2013,
        aggregation="monthly",
    )
    transformed_path = output_dir / "tile_demo.nc"
    assert transformed_path.is_file()
    stats_tile = xr.open_dataset(transformed_path)
    try:
        assert set(stats_tile.data_vars) == {
            "wetland_fraction",
            "valid_observation_count",
            "mean_wetland_fraction",
            "std_wetland_fraction",
            "cell_area_km2",
        }
        assert stats_tile["wetland_fraction"].sizes["time"] == 2
        np.testing.assert_allclose(
            np.asarray(stats_tile["wetland_fraction"].isel(time=0).values, dtype=np.float32),
            0.3,
        )
        np.testing.assert_allclose(
            np.asarray(stats_tile["wetland_fraction"].isel(time=1).values, dtype=np.float32),
            0.7,
        )
    finally:
        stats_tile.close()


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
