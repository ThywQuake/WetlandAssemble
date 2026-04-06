from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from tests.test_loaders.conftest import with_common_fields, write_netcdf
from WA.loaders import get_loader


def test_berkeley_loader_parses_time_and_subsets(tmp_path: Path) -> None:
    base_path = tmp_path / "berkeley"
    coords = {
        "time": [-2147483647],
        "lat": [-1.0, 1.0],
        "lon": [100.0, 101.0],
    }
    january = xr.Dataset(
        {"water_mask": (("time", "lat", "lon"), np.array([[[0, 1], [1, 0]]], dtype=np.int16))},
        coords=coords,
    )
    february = xr.Dataset(
        {"water_mask": (("time", "lat", "lon"), np.array([[[1, 1], [0, 0]]], dtype=np.int16))},
        coords=coords,
    )

    write_netcdf(base_path / "cyg_202001_watermask.nc", january)
    write_netcdf(base_path / "cyg_202002_watermask.nc", february)

    loader = get_loader(
        "berkeley_rwawc",
        with_common_fields(
            base_path,
            loader_type="berkeley",
            variables={"watermask": "water_mask"},
            pattern="*.nc",
        ),
    )

    dataset = loader.load(bbox=(99.5, -2.0, 100.5, 2.0), time_range=("2020-01-01", "2020-01-31"))

    assert list(dataset.data_vars) == ["watermask"]
    assert dataset.sizes["time"] == 1
    assert dataset.sizes["lon"] == 1
    assert str(dataset.time.values[0])[:10] == "2020-01-01"


def test_berkeley_loader_falls_back_to_watermask_variable_name(tmp_path: Path) -> None:
    base_path = tmp_path / "berkeley"
    coords = {
        "time": [-2147483647],
        "lat": [-1.0, 1.0],
        "lon": [100.0, 101.0],
    }
    january = xr.Dataset(
        {"watermask": (("time", "lat", "lon"), np.array([[[0, 1], [1, 0]]], dtype=np.int16))},
        coords=coords,
    )

    write_netcdf(base_path / "cyg_202001_watermask.nc", january)

    loader = get_loader(
        "berkeley_rwawc",
        with_common_fields(
            base_path,
            loader_type="berkeley",
            variables={"watermask": "water_mask"},
            pattern="*.nc",
        ),
    )

    dataset = loader.load(time_range=("2020-01-01", "2020-01-31"))

    assert list(dataset.data_vars) == ["watermask"]
    assert dataset.sizes["time"] == 1


def test_berkeley_open_time_series_merges_months_lazily(tmp_path: Path) -> None:
    base_path = tmp_path / "berkeley"
    coords = {
        "time": [-2147483647],
        "lat": [-1.0, 1.0],
        "lon": [100.0, 101.0],
    }
    january = xr.Dataset(
        {"water_mask": (("time", "lat", "lon"), np.array([[[0, 1], [1, 0]]], dtype=np.int16))},
        coords=coords,
    )
    february = xr.Dataset(
        {"water_mask": (("time", "lat", "lon"), np.array([[[1, 1], [0, 0]]], dtype=np.int16))},
        coords=coords,
    )

    write_netcdf(base_path / "cyg_202001_watermask.nc", january)
    write_netcdf(base_path / "cyg_202002_watermask.nc", february)

    loader = get_loader(
        "berkeley_rwawc",
        with_common_fields(
            base_path,
            loader_type="berkeley",
            variables={"watermask": "water_mask"},
            pattern="*.nc",
        ),
    )

    dataset = loader.open_time_series(("2020-01-01", "2020-02-29"))
    try:
        assert list(dataset.data_vars) == ["watermask"]
        assert dataset.sizes["time"] == 2
        assert str(dataset.time.values[0])[:10] == "2020-01-01"
        assert str(dataset.time.values[1])[:10] == "2020-02-01"
    finally:
        dataset.close()
