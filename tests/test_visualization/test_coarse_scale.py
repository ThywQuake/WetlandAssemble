"""Tests for coarse-scale wetland percentage visualization."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest
import xarray as xr


def _create_mock_static_dataset() -> xr.Dataset:
    """Create a mock static standardized dataset (like G2017)."""
    lat = np.linspace(23.5, -35, 100)
    lon = np.linspace(-180, 180, 200)

    # Mock wetland fraction data
    np.random.seed(42)
    wetland_frac = np.random.uniform(0, 1, size=(len(lat), len(lon))).astype(np.float32)

    return xr.Dataset(
        {
            "wetland_fraction": (("lat", "lon"), wetland_frac),
        },
        coords={
            "lat": lat,
            "lon": lon,
        },
    )


def _create_mock_time_series_dataset() -> xr.Dataset:
    """Create a mock time-series standardized dataset (like SWAMPS)."""
    time = xr.cftime_range("2016-01", periods=12, freq="M")
    lat = np.linspace(23.5, -35, 50)
    lon = np.linspace(-180, 180, 100)

    # Mock wetland fraction data with temporal variation
    np.random.seed(42)
    wetland_frac = np.random.uniform(0, 1, size=(len(time), len(lat), len(lon))).astype(np.float32)

    return xr.Dataset(
        {
            "wetland_fraction": (("time", "lat", "lon"), wetland_frac),
        },
        coords={
            "time": time,
            "lat": lat,
            "lon": lon,
        },
    )


def _create_mock_classification_dataset() -> xr.Dataset:
    """Create a mock classification dataset with frac_* variables (like GLWD)."""
    lat = np.linspace(23.5, -35, 50)
    lon = np.linspace(-180, 180, 100)

    np.random.seed(42)
    # Create fraction variables for different classes
    frac_0 = np.random.uniform(0.3, 0.7, size=(len(lat), len(lon))).astype(np.float32)
    frac_1 = np.random.uniform(0, 0.3, size=(len(lat), len(lon))).astype(np.float32)
    frac_2 = np.random.uniform(0, 0.2, size=(len(lat), len(lon))).astype(np.float32)

    return xr.Dataset(
        {
            "frac_0": (("lat", "lon"), frac_0),
            "frac_1": (("lat", "lon"), frac_1),
            "frac_2": (("lat", "lon"), frac_2),
        },
        coords={
            "lat": lat,
            "lon": lon,
        },
    )


class TestWetlandVariableExtraction:
    """Test wetland variable extraction from different dataset types."""

    def test_extract_from_continuous_dataset(self):
        """Test extracting wetland_fraction from continuous dataset."""
        from WA.visualization.coarse_scale import _get_wetland_variable

        ds = _create_mock_static_dataset()
        wetland = _get_wetland_variable(ds, "test_dataset")

        assert wetland is not None
        assert "wetland_fraction" == ds["wetland_fraction"].name
        assert wetland.shape == (100, 200)

    def test_extract_from_classification_dataset(self):
        """Test extracting wetland fraction from classification dataset."""
        from WA.visualization.coarse_scale import _get_wetland_variable

        ds = _create_mock_classification_dataset()
        wetland = _get_wetland_variable(ds, "test_dataset")

        assert wetland is not None
        # Should sum frac_1 and frac_2 (excluding frac_0 which is non-wetland)
        assert wetland.shape == (50, 100)

    def test_extract_from_known_classification_dataset_excludes_waterbody(self):
        """Known datasets should follow YAML mapping instead of summing water classes."""
        from WA.visualization.coarse_scale import _get_wetland_variable

        ds = xr.Dataset(
            {
                "frac_1": (("lat", "lon"), np.array([[0.2]], dtype=np.float32)),
                "frac_8": (("lat", "lon"), np.array([[0.3]], dtype=np.float32)),
                "frac_29": (("lat", "lon"), np.array([[0.4]], dtype=np.float32)),
            },
            coords={"lat": [0.5], "lon": [100.5]},
        )

        wetland = _get_wetland_variable(ds, "glwd_v2")

        assert wetland is not None
        np.testing.assert_allclose(wetland.values, np.array([[0.7]], dtype=np.float32))

    def test_extract_missing_variable(self):
        """Test handling of dataset without wetland variable."""
        from WA.visualization.coarse_scale import _get_wetland_variable

        ds = xr.Dataset({"other_var": (("lat", "lon"), np.zeros((10, 10)))})
        wetland = _get_wetland_variable(ds, "test_dataset")

        assert wetland is None


class TestTemporalAggregation:
    """Test temporal aggregation functions."""

    def test_aggregate_mean(self):
        """Test mean aggregation over time dimension."""
        from WA.visualization.coarse_scale import _aggregate_temporal

        ds = _create_mock_time_series_dataset()
        wetland = ds["wetland_fraction"]
        aggregated = _aggregate_temporal(wetland, aggregation="mean")

        assert "time" not in aggregated.dims
        assert aggregated.shape == (50, 100)

    def test_aggregate_no_time_dim(self):
        """Test aggregation when no time dimension exists."""
        from WA.visualization.coarse_scale import _aggregate_temporal

        ds = _create_mock_static_dataset()
        wetland = ds["wetland_fraction"]
        aggregated = _aggregate_temporal(wetland, aggregation="mean")

        # Should return unchanged
        assert aggregated.shape == (100, 200)


class TestBboxClipping:
    """Test bounding box clipping."""

    def test_clip_to_tropical(self):
        """Test clipping to tropical region."""
        from WA.visualization.coarse_scale import _clip_to_bbox

        ds = _create_mock_static_dataset()
        wetland = ds["wetland_fraction"]
        tropical_bbox = (-180, -23.5, 180, 23.5)
        clipped = _clip_to_bbox(wetland, tropical_bbox)

        assert clipped is not None
        # Check that latitude is clipped to tropical range
        lat_min = float(clipped.coords["lat"].min())
        lat_max = float(clipped.coords["lat"].max())
        assert lat_max <= 23.5
        assert lat_min >= -23.5

    def test_clip_to_subtropical(self):
        """Test clipping to subtropical region."""
        from WA.visualization.coarse_scale import _clip_to_bbox

        ds = _create_mock_static_dataset()
        wetland = ds["wetland_fraction"]
        subtropical_bbox = (-180, -35, 180, -23.5)
        clipped = _clip_to_bbox(wetland, subtropical_bbox)

        assert clipped is not None
        # Check that latitude is clipped to subtropical range
        lat_min = float(clipped.coords["lat"].min())
        lat_max = float(clipped.coords["lat"].max())
        assert lat_max <= -23.5
        assert lat_min >= -35


class TestAreaWeightedAggregation:
    """Test area-weighted aggregation to a regular target grid."""

    def test_area_weighted_mean_returns_same_surface_when_already_on_target_grid(self):
        """Already aligned 0.25 degree surfaces should pass through unchanged."""
        from WA.visualization.coarse_scale import area_weighted_mean_to_regular_grid

        data = xr.DataArray(
            np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32),
            dims=("lat", "lon"),
            coords={"lat": [0.375, 0.125], "lon": [100.125, 100.375]},
        )

        result = area_weighted_mean_to_regular_grid(
            data,
            (100.0, 0.0, 100.5, 0.5),
            resolution_deg=0.25,
        )

        np.testing.assert_allclose(result.values, data.values)
        np.testing.assert_allclose(result["lat"].values, data["lat"].values)
        np.testing.assert_allclose(result["lon"].values, data["lon"].values)

    def test_area_weighted_mean_uses_cosine_latitude_weights(self):
        """Aggregation should weight high-latitude pixels by smaller cell area."""
        from WA.visualization.coarse_scale import area_weighted_mean_to_regular_grid

        data = xr.DataArray(
            np.array([[1.0], [0.0]], dtype=np.float32),
            dims=("lat", "lon"),
            coords={"lat": [75.0, 65.0], "lon": [10.0]},
        )

        result = area_weighted_mean_to_regular_grid(
            data,
            (0.0, 60.0, 20.0, 80.0),
            resolution_deg=20.0,
        )

        expected = (
            np.cos(np.deg2rad(75.0)) * 1.0 + np.cos(np.deg2rad(65.0)) * 0.0
        ) / (
            np.cos(np.deg2rad(75.0)) + np.cos(np.deg2rad(65.0))
        )
        np.testing.assert_allclose(result.values, np.array([[expected]], dtype=np.float32))
        assert result.attrs["aggregation_method"] == "cosine_latitude_area_weighted_mean"

    def test_area_weighted_mean_interpolates_when_source_grid_is_coarser_than_target(self):
        """Coarser source grids should be interpolated instead of leaving empty stripes."""
        from WA.visualization.coarse_scale import area_weighted_mean_to_regular_grid

        data = xr.DataArray(
            np.array([[0.2, 0.4], [0.6, 0.8]], dtype=np.float32),
            dims=("lat", "lon"),
            coords={"lat": [0.01, 0.49], "lon": [0.01, 0.49]},
        )

        result = area_weighted_mean_to_regular_grid(
            data,
            (0.0, 0.0, 0.5, 0.5),
            resolution_deg=0.125,
        )

        assert result.shape == (4, 4)
        assert not np.isnan(result.values).any()
        assert result.attrs["aggregation_method"] == "interpolated_to_regular_grid"


class TestStatisticsComputation:
    """Test statistics computation."""

    def test_compute_statistics(self):
        """Test computing basic statistics."""
        from WA.visualization.coarse_scale import _compute_statistics

        ds = _create_mock_static_dataset()
        wetland = ds["wetland_fraction"]
        stats = _compute_statistics(wetland)

        assert "mean" in stats
        assert "std" in stats
        assert "min" in stats
        assert "max" in stats
        assert "total" in stats

        # Verify values are in expected ranges
        assert 0 <= stats["mean"] <= 1
        assert 0 <= stats["std"] <= 0.5
        assert 0 <= stats["min"] <= 1
        assert 0 <= stats["max"] <= 1


class TestSingleDatasetPlot:
    """Test single dataset visualization."""

    def test_plot_static_dataset(self):
        """Test plotting static dataset distribution."""
        from WA.visualization.coarse_scale import plot_single_dataset_distribution

        ds = _create_mock_static_dataset()

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output.png"
            result = plot_single_dataset_distribution(
                dataset=ds,
                dataset_id="test_dataset",
                region="all",
                output_path=output_path,
                dpi=100,
            )

            assert result.exists()
            assert result.stat().st_size > 0

    def test_plot_time_series_dataset(self):
        """Test plotting time-series dataset distribution."""
        from WA.visualization.coarse_scale import plot_single_dataset_distribution

        ds = _create_mock_time_series_dataset()

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output.png"
            result = plot_single_dataset_distribution(
                dataset=ds,
                dataset_id="test_dataset",
                region="tropical",
                year=2016,
                output_path=output_path,
                dpi=100,
            )

            assert result.exists()
            assert result.stat().st_size > 0

    def test_plot_with_invalid_region(self):
        """Test handling of invalid region."""
        from WA.visualization.coarse_scale import plot_single_dataset_distribution

        ds = _create_mock_static_dataset()

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output.png"
            # Should use default bbox for unknown region
            result = plot_single_dataset_distribution(
                dataset=ds,
                dataset_id="test_dataset",
                region="unknown",
                output_path=output_path,
                dpi=100,
            )

            assert result.exists()


class TestMultiDatasetComparison:
    """Test multi-dataset comparison visualization."""

    def test_plot_multi_dataset(self):
        """Test plotting multi-dataset comparison."""
        from WA.visualization.coarse_scale import plot_multi_dataset_comparison

        datasets = {
            "dataset1": _create_mock_static_dataset(),
            "dataset2": _create_mock_time_series_dataset(),
        }

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_comparison.png"
            result = plot_multi_dataset_comparison(
                datasets=datasets,
                region="all",
                year=2016,
                output_path=output_path,
                dpi=100,
            )

            assert result.exists()
            assert result.stat().st_size > 0

    def test_plot_empty_datasets(self):
        """Test handling of empty datasets dict."""
        from WA.visualization.coarse_scale import plot_multi_dataset_comparison

        with pytest.raises(ValueError, match="No valid datasets"):
            with TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "test.png"
                plot_multi_dataset_comparison(
                    datasets={},
                    region="all",
                    output_path=output_path,
                )


class TestTemporalComparison:
    """Test temporal comparison visualization."""

    def test_plot_temporal(self):
        """Test plotting temporal comparison."""
        from WA.visualization.coarse_scale import plot_temporal_comparison

        datasets = {
            "dataset1": _create_mock_time_series_dataset(),
        }

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_temporal.png"
            result = plot_temporal_comparison(
                datasets=datasets,
                region="all",
                output_path=output_path,
                dpi=100,
            )

            assert result.exists()
            assert result.stat().st_size > 0

    def test_plot_temporal_no_time_data(self):
        """Test handling of datasets without time dimension."""
        from WA.visualization.coarse_scale import plot_temporal_comparison

        datasets = {
            "static": _create_mock_static_dataset(),
        }

        with pytest.raises(ValueError, match="No datasets with temporal data"):
            with TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "test.png"
                plot_temporal_comparison(
                    datasets=datasets,
                    region="all",
                    output_path=output_path,
                )


class TestStatisticsPlot:
    """Test statistics visualization."""

    def test_plot_statistics(self):
        """Test plotting statistics comparison."""
        from WA.visualization.coarse_scale import plot_wetland_area_statistics

        datasets = {
            "dataset1": _create_mock_static_dataset(),
            "dataset2": _create_mock_time_series_dataset(),
        }

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_stats.png"
            result = plot_wetland_area_statistics(
                datasets=datasets,
                region="all",
                year=2016,
                output_path=output_path,
                dpi=100,
            )

            assert result.exists()
            assert result.stat().st_size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
