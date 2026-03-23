"""Tests for the Phase 3.5 classification comparison panel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from WA.visualization.panel import (
    CLASS_CMAP,
    ENTROPY_CMAP,
    FINE_4CLASS_COLORS,
    FINE_4CLASS_LABELS,
    _map_to_4class,
    compute_vote_classification,
    load_native_classification,
    plot_classification_panel,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_grid(bbox: tuple[float, ...], res: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    west, south, east, north = bbox
    lats = np.arange(north - res / 2, south, -res)
    lons = np.arange(west + res / 2, east, res)
    return lats, lons


def _synthetic_classification(
    bbox: tuple[float, ...],
    res: float,
    fill_class: int = 2,
) -> xr.DataArray:
    """Create a uniform classification DataArray."""
    lats, lons = _make_grid(bbox, res)
    data = np.full((len(lats), len(lons)), fill_class, dtype=np.float32)
    da = xr.DataArray(data, dims=("lat", "lon"), coords={"lat": lats, "lon": lons})
    da = da.rio.write_crs("EPSG:4326")
    da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    return da


def _synthetic_entropy(
    bbox: tuple[float, ...],
    res: float = 0.01,
) -> xr.DataArray:
    lats, lons = _make_grid(bbox, res)
    rng = np.random.default_rng(42)
    data = rng.random((len(lats), len(lons))).astype(np.float32)
    da = xr.DataArray(data, dims=("lat", "lon"), coords={"lat": lats, "lon": lons})
    da = da.rio.write_crs("EPSG:4326")
    da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    da.name = "shannon_entropy"
    return da


BBOX = (110.0, -1.5, 111.0, -0.5)


# ---------------------------------------------------------------------------
# Colormap tests
# ---------------------------------------------------------------------------


class TestColormaps:
    def test_class_cmap_has_4_colors(self) -> None:
        assert CLASS_CMAP.N == 4

    def test_entropy_cmap_white_to_red(self) -> None:
        low = np.array(ENTROPY_CMAP(0.0)[:3])
        high = np.array(ENTROPY_CMAP(1.0)[:3])
        # Low end should be near white (all channels ≈ 1)
        assert np.allclose(low, [1.0, 1.0, 1.0], atol=0.01)
        # High end should be near red (R≈1, G≈0, B≈0)
        assert high[0] > 0.9
        assert high[1] < 0.1
        assert high[2] < 0.1

    def test_4class_colors_and_labels_match(self) -> None:
        assert set(FINE_4CLASS_COLORS.keys()) == set(FINE_4CLASS_LABELS.keys())


# ---------------------------------------------------------------------------
# Mapping tests
# ---------------------------------------------------------------------------


class TestMapping:
    def test_map_to_4class_g2017(self) -> None:
        # G2017 value 10 → Open Water (1), value 20 → Wetland (2)
        data = xr.DataArray([10.0, 20.0, 0.0], dims="x")
        result = _map_to_4class(data, "g2017")
        assert float(result[0]) == 1.0  # open water
        assert float(result[1]) == 2.0  # wetland
        assert float(result[2]) == 0.0  # non-wetland

    def test_map_to_4class_nan_preserved(self) -> None:
        data = xr.DataArray([np.nan, 10.0], dims="x")
        result = _map_to_4class(data, "g2017")
        assert np.isnan(float(result[0]))


# ---------------------------------------------------------------------------
# Vote classification tests
# ---------------------------------------------------------------------------


class TestVoteClassification:
    def test_unanimous_vote(self) -> None:
        """All datasets agree → vote = that class."""
        bbox = (110.0, -1.0, 110.5, -0.5)
        ds_glwd = _synthetic_classification(bbox, 0.01, fill_class=2).rename(
            "combined_classes"
        ).to_dataset()
        # G2017 value 20 → 4class 2 (wetland)
        g2017_raw = _synthetic_classification(bbox, 0.05, fill_class=20)
        ds_g2017 = g2017_raw.rename("wetland").to_dataset()
        # GWD30 value 8 → 4class 2 (wetland)
        gwd30_raw = _synthetic_classification(bbox, 0.01, fill_class=8)
        ds_gwd30 = gwd30_raw.rename("wetland_class").to_dataset()

        datasets = {"glwd_v2": ds_glwd, "g2017": ds_g2017, "gwd30": ds_gwd30}
        vote = compute_vote_classification(datasets, bbox, vote_resolution_deg=0.05)
        values = vote.values[np.isfinite(vote.values)]
        assert len(values) > 0
        # All should be class 2 (wetland)
        assert np.all(values == 2.0)

    def test_majority_wins(self) -> None:
        """Two datasets say class A, one says class B → A wins."""
        bbox = (110.0, -1.0, 110.5, -0.5)
        # GLWD: class 1 (open water) — raw value 1
        ds_glwd = _synthetic_classification(bbox, 0.01, fill_class=1).rename(
            "combined_classes"
        ).to_dataset()
        # G2017: class 1 (open water) — raw value 10
        ds_g2017 = _synthetic_classification(bbox, 0.05, fill_class=10).rename(
            "wetland"
        ).to_dataset()
        # GWD30: class 2 (wetland) — raw value 8
        ds_gwd30 = _synthetic_classification(bbox, 0.01, fill_class=8).rename(
            "wetland_class"
        ).to_dataset()

        datasets = {"glwd_v2": ds_glwd, "g2017": ds_g2017, "gwd30": ds_gwd30}
        vote = compute_vote_classification(datasets, bbox, vote_resolution_deg=0.05)
        values = vote.values[np.isfinite(vote.values)]
        assert len(values) > 0
        # Majority = open water (class 1): GLWD + G2017 vs GWD30
        assert np.all(values == 1.0)


# ---------------------------------------------------------------------------
# Native classification loading
# ---------------------------------------------------------------------------


class TestNativeClassification:
    def test_loads_glwd(self) -> None:
        bbox = (110.0, -1.0, 110.5, -0.5)
        ds = _synthetic_classification(bbox, 0.01, fill_class=8).rename(
            "combined_classes"
        ).to_dataset()
        result = load_native_classification("glwd_v2", ds, bbox)
        vals = result.values[np.isfinite(result.values)]
        # GLWD class 8 → 4class 2 (wetland)
        assert np.all(vals == 2.0)


# ---------------------------------------------------------------------------
# Panel plot integration test
# ---------------------------------------------------------------------------


class TestPanelPlot:
    def test_creates_png(self, tmp_path: Path) -> None:
        bbox = BBOX
        entropy = _synthetic_entropy(bbox, 0.05)
        vote = _synthetic_classification(bbox, 0.05, fill_class=2)
        vote.name = "vote_classification"

        native = {
            "glwd_v2": _synthetic_classification(bbox, 0.01, fill_class=1),
            "g2017": _synthetic_classification(bbox, 0.05, fill_class=2),
            "gwd30": _synthetic_classification(bbox, 0.01, fill_class=3),
        }

        out = tmp_path / "test_panel.png"
        result = plot_classification_panel(
            "test-hotspot-001",
            "test_region",
            bbox,
            satellite_image_path=None,
            entropy_surface=entropy,
            vote_classification=vote,
            native_classifications=native,
            output_path=out,
            dpi=72,
        )
        assert result == out
        assert out.exists()
        assert out.stat().st_size > 1000  # non-trivial PNG

    def test_handles_missing_datasets(self, tmp_path: Path) -> None:
        bbox = BBOX
        entropy = _synthetic_entropy(bbox, 0.05)
        vote = _synthetic_classification(bbox, 0.05, fill_class=0)
        vote.name = "vote_classification"

        # Only one dataset available
        native = {"g2017": _synthetic_classification(bbox, 0.05, fill_class=2)}

        out = tmp_path / "sparse_panel.png"
        result = plot_classification_panel(
            "sparse-001",
            "test_region",
            bbox,
            satellite_image_path=None,
            entropy_surface=entropy,
            vote_classification=vote,
            native_classifications=native,
            output_path=out,
            dpi=72,
        )
        assert result.exists()
