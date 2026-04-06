"""Tests for comparison panel visualization."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from tests.test_loaders.conftest import with_common_fields, write_netcdf
from WA.loaders import get_loader
from WA.visualization.comparison_panel import (
    ENTROPY_CMAP,
    WETLAND_CMAP,
    load_native_wetland_surface,
    make_dataset_labels,
    plot_comparison_panel,
)


def _make_surface(
    lat: list[float],
    lon: list[float],
    fill: float = 0.5,
) -> xr.DataArray:
    """Create a synthetic 2D surface for testing."""
    data = np.full((len(lat), len(lon)), fill, dtype=np.float32)
    return xr.DataArray(data, coords={"lat": lat, "lon": lon}, dims=("lat", "lon"))


def test_plot_comparison_panel_creates_png(tmp_path: Path) -> None:
    """Smoke test: panel figure is created as a PNG file."""
    bbox = (100.0, -2.0, 102.0, 0.0)
    lats = [0.0, -0.5, -1.0, -1.5, -2.0]
    lons = [100.0, 100.5, 101.0, 101.5, 102.0]

    entropy = _make_surface(lats, lons, fill=0.3)
    mean_wetland = _make_surface(lats, lons, fill=0.6)
    dataset_surfaces = {
        "ds_a": _make_surface(lats, lons, fill=0.7),
        "ds_b": _make_surface(lats, lons, fill=0.4),
        "ds_c": _make_surface(lats, lons, fill=0.2),
        "ds_d": _make_surface(lats, lons, fill=0.9),
    }

    out = tmp_path / "test_panel.png"
    result = plot_comparison_panel(
        bbox,
        satellite_image_path=None,
        entropy_surface=entropy,
        mean_wetland_surface=mean_wetland,
        dataset_surfaces=dataset_surfaces,
        year=2016,
        region_label="Test Region",
        hotspot_id="test-001",
        output_path=out,
        dpi=72,
    )

    assert result == out
    assert out.exists()
    assert out.stat().st_size > 1000  # non-trivial PNG


def test_plot_comparison_panel_correct_layout(tmp_path: Path) -> None:
    """With 5 datasets: 1 header row + 2 data rows = 3 rows."""
    bbox = (100.0, -1.0, 101.0, 0.0)
    lats = [0.0, -0.5, -1.0]
    lons = [100.0, 100.5, 101.0]

    entropy = _make_surface(lats, lons, fill=0.5)
    mean_wetland = _make_surface(lats, lons, fill=0.5)
    dataset_surfaces = {f"ds_{i}": _make_surface(lats, lons) for i in range(5)}

    out = tmp_path / "layout.png"
    plot_comparison_panel(
        bbox,
        satellite_image_path=None,
        entropy_surface=entropy,
        mean_wetland_surface=mean_wetland,
        dataset_surfaces=dataset_surfaces,
        year=2016,
        region_label="Layout Test",
        hotspot_id="layout-001",
        output_path=out,
        dpi=72,
    )
    assert out.exists()


def test_plot_comparison_panel_single_dataset(tmp_path: Path) -> None:
    """Edge case: only 1 dataset should still produce valid figure."""
    bbox = (100.0, -1.0, 101.0, 0.0)
    lats = [0.0, -0.5, -1.0]
    lons = [100.0, 100.5, 101.0]

    entropy = _make_surface(lats, lons, fill=0.1)
    mean_wetland = _make_surface(lats, lons, fill=0.8)
    dataset_surfaces = {"single": _make_surface(lats, lons, fill=0.5)}

    out = tmp_path / "single.png"
    plot_comparison_panel(
        bbox,
        satellite_image_path=None,
        entropy_surface=entropy,
        mean_wetland_surface=mean_wetland,
        dataset_surfaces=dataset_surfaces,
        year=2016,
        region_label="Single",
        hotspot_id="single-001",
        output_path=out,
        dpi=72,
    )
    assert out.exists()


def test_entropy_cmap_is_white_to_red() -> None:
    """Entropy colormap goes from white to red."""
    low = ENTROPY_CMAP(0.0)
    high = ENTROPY_CMAP(1.0)
    # Low end should be white-ish
    assert low[0] > 0.95 and low[1] > 0.95 and low[2] > 0.95
    # High end should be red-ish (R > G, R > B)
    assert high[0] > 0.7
    assert high[1] < 0.3


def test_wetland_cmap_is_white_to_blue() -> None:
    """Wetland colormap goes from white to blue."""
    low = WETLAND_CMAP(0.0)
    high = WETLAND_CMAP(1.0)
    # Low end should be white-ish
    assert low[0] > 0.95 and low[1] > 0.95 and low[2] > 0.95
    # High end should be blue-ish (B > R)
    assert high[2] > 0.5
    assert high[0] < 0.3


def test_make_dataset_labels() -> None:
    """Labels should contain display name + resolution."""
    labels = make_dataset_labels(["g2017", "swamps", "unknown_ds"])
    assert "G2017" in labels["g2017"]
    assert "0.05" in labels["g2017"]
    assert "SWAMPS" in labels["swamps"]
    assert labels["unknown_ds"] == "unknown_ds"


def test_load_native_wetland_surface_uses_target_month_for_dynamic_dataset(
    tmp_path: Path,
) -> None:
    """Dynamic datasets should load the focus month, not the full time series."""

    base_path = tmp_path / "swamps"
    january = xr.Dataset(
        {"fw": (("lat", "lon"), np.array([[10.0]], dtype=np.float32))},
        coords={"lat": [0.5], "lon": [100.0]},
    )
    february = xr.Dataset(
        {"fw": (("lat", "lon"), np.array([[90.0]], dtype=np.float32))},
        coords={"lat": [0.5], "lon": [100.0]},
    )
    write_netcdf(base_path / "stable/2010/01/SWAMPS.FW.F13.QUIKSCAT.20100101.nc", january)
    write_netcdf(base_path / "stable/2010/02/SWAMPS.FW.F13.QUIKSCAT.20100201.nc", february)

    loader = get_loader(
        "swamps",
        with_common_fields(
            base_path,
            loader_type="swamps",
            pattern="stable/{year}/{month}/*.nc",
            sensor_shift_year=2000,
        ),
    )

    surface = load_native_wetland_surface(
        "swamps",
        loader,
        (99.5, 0.0, 100.5, 1.0),
        target_time="2010-02-01",
    )

    assert surface is not None
    assert surface.dtype == np.float32
    assert surface.squeeze().item() == np.float32(0.9)
