from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import rioxarray  # noqa: F401
import xarray as xr

from WA.comparison.harmonize import (
    BinaryComparisonUnavailableError,
    EmptyBinarySurfaceError,
    _is_already_aligned,
    create_comparison_grid,
    harmonize_binary_dataset,
    select_comparison_slice,
)


def test_harmonize_binary_dataset_rejects_auxiliary_berkeley() -> None:
    dataset = xr.Dataset(
        {"watermask": (("lat", "lon"), np.array([[1, 0]], dtype=np.float32))},
        coords={"lat": [0.5], "lon": [100.5, 101.5]},
    )
    dataset.attrs["time_resolution"] = "monthly"
    reference = create_comparison_grid((100.0, 0.0, 102.0, 1.0), resolution_deg=1.0)

    try:
        harmonize_binary_dataset("berkeley_rwawc", dataset, reference_grid=reference)
    except BinaryComparisonUnavailableError as exc:
        assert "not eligible" in str(exc)
    else:
        raise AssertionError("Expected Berkeley-RWAWC to be rejected for binary comparison")


def test_harmonize_binary_dataset_uses_standardized_class_fractions_without_water() -> None:
    dataset = xr.Dataset(
        {
            "frac_1": (("lat", "lon"), np.array([[0.2]], dtype=np.float32)),
            "frac_8": (("lat", "lon"), np.array([[0.3]], dtype=np.float32)),
            "frac_29": (("lat", "lon"), np.array([[0.4]], dtype=np.float32)),
        },
        coords={"lat": [0.5], "lon": [100.5]},
    )
    reference = create_comparison_grid((100.0, 0.0, 101.0, 1.0), resolution_deg=1.0)

    harmonized = harmonize_binary_dataset("glwd_v2", dataset, reference_grid=reference)

    np.testing.assert_allclose(harmonized.values, np.array([[0.7]], dtype=np.float32))
    assert harmonized.attrs["comparison_source_variable"] == "classified_fractions"


def test_harmonize_binary_dataset_uses_g2017_fraction_surface() -> None:
    dataset = xr.Dataset(
        {
            "wetland": (("lat", "lon"), np.array([[10, 20], [30, 80]], dtype=np.uint8)),
            "wetland_nolake": (
                ("lat", "lon"),
                np.array([[0.0, 0.75], [1.0, 0.25]], dtype=np.float32),
            ),
        },
        coords={"lat": [1.5, 0.5], "lon": [100.5, 101.5]},
    )
    reference = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        coords={"lat": [1.5, 0.5], "lon": [100.5, 101.5]},
        dims=("lat", "lon"),
        name="comparison_grid",
    )
    reference = reference.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    reference = reference.rio.write_crs("EPSG:4326", inplace=False)

    harmonized = harmonize_binary_dataset("g2017", dataset, reference_grid=reference)

    assert harmonized.name == "wetland_fraction"
    assert harmonized.attrs["comparison_source_variable"] == "wetland_nolake"
    np.testing.assert_allclose(
        harmonized.values,
        np.array([[0.0, 0.75], [1.0, 0.25]], dtype=np.float32),
    )


def test_harmonize_binary_dataset_collapses_topmodel_ensemble() -> None:
    dataset = xr.Dataset(
        {
            "wetland_fraction": (
                ("config", "forcing", "time", "lat", "lon"),
                np.array(
                    [
                        [[[[0.2]], [[0.4]]]],
                        [[[[0.6]], [[0.8]]]],
                    ],
                    dtype=np.float32,
                ),
            )
        },
        coords={
            "config": ["cfg_a", "cfg_b"],
            "forcing": ["era5"],
            "time": pd.to_datetime(["2001-01-01", "2001-02-01"]),
            "lat": [0.5],
            "lon": [100.5],
        },
    )
    dataset.attrs["time_resolution"] = "monthly"
    reference = create_comparison_grid((100.0, 0.0, 101.0, 1.0), resolution_deg=1.0)

    harmonized = harmonize_binary_dataset("topmodel", dataset, reference_grid=reference)

    assert harmonized.dims == ("time", "lat", "lon")
    np.testing.assert_allclose(
        harmonized.sel(time="2001-01-01").values,
        np.array([[0.4]], dtype=np.float32),
    )
    np.testing.assert_allclose(
        harmonized.sel(time="2001-02-01").values,
        np.array([[0.6]], dtype=np.float32),
    )


def test_harmonize_binary_dataset_aligns_single_cell_fraction_source() -> None:
    dataset = xr.Dataset(
        {
            "wetland_fraction": (
                ("time", "lat", "lon"),
                np.array([[[0.6]]], dtype=np.float32),
            )
        },
        coords={
            "time": pd.to_datetime(["2019-07-01"]),
            "lat": [0.875],
            "lon": [112.125],
        },
    )
    dataset.attrs["time_resolution"] = "monthly"
    reference = create_comparison_grid((111.95, 0.75, 112.3333, 1.0333), resolution_deg=0.25)

    harmonized = harmonize_binary_dataset("wad2m", dataset, reference_grid=reference)
    selected = select_comparison_slice(harmonized, "2019-07-01")

    values = np.asarray(selected.values, dtype=float)
    assert int(np.count_nonzero(~np.isnan(values))) >= 1
    assert float(np.nanmax(values)) == pytest.approx(0.6)


def test_select_comparison_slice_matches_month_for_midpoint_timestamp() -> None:
    data = xr.DataArray(
        np.array([[[0.2]], [[0.4]]], dtype=np.float32),
        coords={
            "time": pd.to_datetime(["2000-03-16", "2000-04-16"]),
            "lat": [0.5],
            "lon": [100.5],
        },
        dims=("time", "lat", "lon"),
        name="wetland_fraction",
    )

    selected = select_comparison_slice(data, "2000-03-01")

    np.testing.assert_allclose(selected.values, np.array([[0.2]], dtype=np.float32))
    assert selected.attrs["comparison_time"] == "2000-03-01T00:00:00"
    assert selected.attrs["comparison_source_time"] == "2000-03-16T00:00:00"
    assert "time" not in selected.coords


def test_harmonize_binary_dataset_rejects_empty_glwd_surface() -> None:
    dataset = xr.Dataset(
        {
            "combined_classes": (
                ("lat", "lon"),
                np.array([[np.nan, np.nan], [np.nan, np.nan]], dtype=np.float32),
            )
        },
        coords={"lat": [1.5, 0.5], "lon": [100.5, 101.5]},
    )
    reference = create_comparison_grid((100.0, 0.0, 102.0, 2.0), resolution_deg=1.0)

    with pytest.raises(EmptyBinarySurfaceError, match="prepared_source"):
        harmonize_binary_dataset("glwd_v2", dataset, reference_grid=reference)


def test_harmonize_binary_dataset_rejects_glwd_surface_empty_after_alignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = xr.Dataset(
        {
            "combined_classes": (
                ("lat", "lon"),
                np.array([[8.0]], dtype=np.float32),
            )
        },
        coords={"lat": [0.5], "lon": [100.5]},
    )
    reference = create_comparison_grid((100.0, 0.0, 101.0, 1.0), resolution_deg=1.0)
    empty_aligned = xr.DataArray(
        np.full(reference.shape, np.nan, dtype=np.float32),
        coords=reference.coords,
        dims=reference.dims,
    )

    monkeypatch.setattr(
        "WA.comparison.harmonize._align_binary_fraction",
        lambda data, reference_grid, resampling: empty_aligned,
    )

    with pytest.raises(EmptyBinarySurfaceError, match="aligned_to_reference_grid"):
        harmonize_binary_dataset("glwd_v2", dataset, reference_grid=reference)


def test_is_already_aligned_detects_matching_coordinates() -> None:
    """Data with identical lat/lon coordinates as reference_grid should be detected as aligned."""
    reference = create_comparison_grid((100.0, 0.0, 102.0, 2.0), resolution_deg=1.0)
    data = xr.DataArray(
        np.ones(reference.shape, dtype=np.float32),
        coords=reference.coords,
        dims=reference.dims,
    )
    assert _is_already_aligned(data, reference) is True


def test_is_already_aligned_rejects_different_coordinates() -> None:
    """Data with different coordinates should not be detected as aligned."""
    reference = create_comparison_grid((100.0, 0.0, 102.0, 2.0), resolution_deg=1.0)
    data = xr.DataArray(
        np.ones((3, 3), dtype=np.float32),
        coords={"lat": [1.5, 0.5, -0.5], "lon": [100.5, 101.5, 102.5]},
        dims=("lat", "lon"),
    )
    assert _is_already_aligned(data, reference) is False


def test_is_already_aligned_rejects_different_shape() -> None:
    """Data with different shape should not be detected as aligned."""
    reference = create_comparison_grid((100.0, 0.0, 102.0, 2.0), resolution_deg=1.0)
    data = xr.DataArray(
        np.ones((4, 4), dtype=np.float32),
        coords={"lat": [1.75, 1.25, 0.75, 0.25], "lon": [100.25, 100.75, 101.25, 101.75]},
        dims=("lat", "lon"),
    )
    assert _is_already_aligned(data, reference) is False
