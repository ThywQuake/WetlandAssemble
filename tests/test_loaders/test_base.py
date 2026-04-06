"""Tests for base loader utilities."""

from __future__ import annotations

import numpy as np
import pytest
import rioxarray  # noqa: F401
import xarray as xr

from WA.loaders.base import ensure_datetime_index, validate_reference_grid


def test_validate_reference_grid_accepts_valid_grid() -> None:
    """A properly constructed WGS84 grid should pass validation."""
    grid = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        dims=("lat", "lon"),
        coords={"lat": [1.5, 0.5], "lon": [100.5, 101.5]},
    )
    grid = grid.rio.write_crs("EPSG:4326")
    grid = grid.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    # Should not raise
    validate_reference_grid(grid)


def test_validate_reference_grid_rejects_missing_crs() -> None:
    """A grid without CRS should be rejected."""
    grid = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        dims=("lat", "lon"),
        coords={"lat": [1.5, 0.5], "lon": [100.5, 101.5]},
    )
    with pytest.raises(ValueError, match="CRS"):
        validate_reference_grid(grid)


def test_validate_reference_grid_rejects_wrong_dims() -> None:
    """A grid without lat/lon or y/x dims should be rejected."""
    grid = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        dims=("a", "b"),
        coords={"a": [1.5, 0.5], "b": [100.5, 101.5]},
    )
    grid = grid.rio.write_crs("EPSG:4326")
    with pytest.raises(ValueError, match="spatial dimensions"):
        validate_reference_grid(grid)


def test_ensure_datetime_index_clears_time_cf_encoding() -> None:
    dataset = xr.Dataset(
        {"value": (("time",), np.array([1.0, 2.0], dtype=np.float32))},
        coords={"time": np.array(["2000-01-16", "2000-02-15"], dtype="datetime64[ns]")},
    )
    dataset["time"].attrs.update(
        {
            "units": "days since 2000-01-16 00:00:00",
            "calendar": "proleptic_gregorian",
            "note": "keep-me",
        }
    )
    dataset["time"].encoding = {
        "units": "days since 2000-01-16 00:00:00",
        "calendar": "proleptic_gregorian",
    }

    result = ensure_datetime_index(dataset)

    assert "units" not in result["time"].attrs
    assert "calendar" not in result["time"].attrs
    assert result["time"].attrs["note"] == "keep-me"
    assert result["time"].encoding == {}
