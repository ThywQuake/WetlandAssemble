from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from tests.test_loaders.conftest import make_reference_grid, with_common_fields, write_netcdf
from WA.loaders import get_loader


def test_standardized_loader_reads_static_dataset(tmp_path: Path) -> None:
    dataset = xr.Dataset(
        {
            "frac_10": (("lat", "lon"), np.array([[0.4, 0.1]], dtype=np.float32)),
            "frac_20": (("lat", "lon"), np.array([[0.2, 0.3]], dtype=np.float32)),
        },
        coords={"lat": [0.5], "lon": [100.5, 101.5]},
    )
    write_netcdf(tmp_path / "g2017.nc", dataset)

    loader = get_loader(
        "g2017",
        with_common_fields(
            tmp_path,
            loader_type="standardized_netcdf",
            is_static=True,
            is_classification=True,
        ),
    )

    result = loader.load()

    assert set(result.data_vars) == {"frac_10", "frac_20"}
    assert result.sizes["lat"] == 1
    assert result.sizes["lon"] == 2


def test_standardized_loader_concatenates_annual_files_by_time_range(tmp_path: Path) -> None:
    first = xr.Dataset(
        {
            "watermask": (
                ("time", "lat", "lon"),
                np.array([[[0.1]], [[0.2]]], dtype=np.float32),
            )
        },
        coords={
            "time": xr.date_range("2020-11-01", periods=2, freq="MS"),
            "lat": [0.5],
            "lon": [100.5],
        },
    )
    second = xr.Dataset(
        {
            "watermask": (
                ("time", "lat", "lon"),
                np.array([[[0.3]], [[0.4]]], dtype=np.float32),
            )
        },
        coords={
            "time": xr.date_range("2021-01-01", periods=2, freq="MS"),
            "lat": [0.5],
            "lon": [100.5],
        },
    )
    write_netcdf(tmp_path / "berkeley_rwawc_2020.nc", first)
    write_netcdf(tmp_path / "berkeley_rwawc_2021.nc", second)

    loader = get_loader(
        "berkeley_rwawc",
        with_common_fields(
            tmp_path,
            loader_type="standardized_netcdf",
            is_static=False,
            is_classification=False,
            time_resolution="monthly",
        ),
    )

    result = loader.load(time_range=("2020-12-01", "2021-01-31"))

    assert list(result.data_vars) == ["watermask"]
    assert result.sizes["time"] == 2
    assert str(result["time"].values[0])[:10] == "2020-12-01"
    assert str(result["time"].values[1])[:10] == "2021-01-01"


def test_standardized_loader_reprojects_to_reference_grid(tmp_path: Path) -> None:
    dataset = xr.Dataset(
        {
            "wetland_fraction": (
                ("time", "lat", "lon"),
                np.array([[[0.1, 0.2], [0.3, 0.4]]], dtype=np.float32),
            )
        },
        coords={
            "time": xr.date_range("2016-01-01", periods=1, freq="MS"),
            "lat": [0.75, 0.25],
            "lon": [100.25, 100.75],
        },
    )
    write_netcdf(tmp_path / "topmodel_2016.nc", dataset)

    loader = get_loader(
        "topmodel",
        with_common_fields(
            tmp_path,
            loader_type="standardized_netcdf",
            is_static=False,
            is_classification=False,
            time_resolution="monthly",
        ),
    )

    grid = make_reference_grid(lat_range=(0.0, 1.0), lon_range=(100.0, 101.0), resolution_deg=1.0)
    result = loader.load(time_range=("2016-01-01", "2016-01-31"), reference_grid=grid)

    assert result.sizes["lat"] == grid.sizes["lat"]
    assert result.sizes["lon"] == grid.sizes["lon"]
    assert "wetland_fraction" in result.data_vars
