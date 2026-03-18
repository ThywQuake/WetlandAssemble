from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from tests.test_loaders.conftest import with_common_fields, write_netcdf
from WA.loaders import get_loader


def test_giems_loader_masks_flag_values_and_renames_axes(tmp_path: Path) -> None:
    base_path = tmp_path / "giems"
    dataset = xr.Dataset(
        {
            "inund_sat_wetland_frac": (
                ("time", "latitude", "longitude"),
                np.array([[[-999.0, 0.2], [0.4, -998.0]]], dtype=np.float32),
            )
        },
        coords={
            "time": np.array(["1993-01-01"], dtype="datetime64[ns]"),
            "latitude": [-0.5, 0.5],
            "longitude": [100.0, 101.0],
        },
    )
    write_netcdf(base_path / "GIEMS-MC.nc", dataset)

    loader = get_loader(
        "giems_mc",
        with_common_fields(base_path, loader_type="netcdf", file="GIEMS-MC.nc"),
    )

    result = loader.load()

    assert "wetland_fraction" in result
    assert "lat" in result.coords
    assert np.isnan(result["wetland_fraction"].isel(time=0, lat=0, lon=0).item())


def test_wad2m_loader_normalizes_primary_variable_name(tmp_path: Path) -> None:
    base_path = tmp_path / "wad2m"
    dataset = xr.Dataset(
        {"Fw": (("time", "lat", "lon"), np.array([[[0.1]], [[0.3]]], dtype=np.float32))},
        coords={
            "time": np.array(["2000-01-16", "2000-02-15"], dtype="datetime64[ns]"),
            "lat": [0.5],
            "lon": [101.5],
        },
    )
    write_netcdf(base_path / "wad2m.nc", dataset)

    loader = get_loader(
        "wad2m",
        with_common_fields(base_path, loader_type="netcdf", file="wad2m.nc"),
    )

    result = loader.load(time_range=("2000-02-01", "2000-02-28"))

    assert list(result.data_vars) == ["wetland_fraction"]
    assert result.sizes["time"] == 1
    assert result["wetland_fraction"].item() == np.float32(0.3)
