from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from tests.test_loaders.conftest import with_common_fields, write_netcdf
from WA.loaders import get_loader


def test_topmodel_loader_discovers_configs_and_rebuilds_timestamps(tmp_path: Path) -> None:
    base_path = tmp_path / "topmodel"
    template = xr.Dataset(
        {"fwet": (("time", "lat", "lon"), np.ones((2, 1, 1), dtype=np.float32))},
        coords={"time": [1, 2], "lat": [0.5], "lon": [100.5]},
    )

    write_netcdf(base_path / "cfg_a/force_a/fwet_cfg_a_force_a_reso025_2020.nc", template)
    write_netcdf(base_path / "cfg_a/force_a/fwet_cfg_a_force_a_reso025_2021.nc", template)
    write_netcdf(base_path / "cfg_b/force_a/fwet_cfg_b_force_a_reso025_2020.nc", template)

    loader = get_loader("topmodel", with_common_fields(base_path, loader_type="topmodel"))
    result = loader.load()

    assert result.sizes["config"] == 2
    assert result.sizes["forcing"] == 1
    assert str(result.time.values[0])[:10] == "2020-01-01"
    assert str(result.time.values[-1])[:10] == "2021-02-01"


def test_topmodel_loader_derives_temporal_coverage_and_filters_time_range(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "topmodel"
    template_2020 = xr.Dataset(
        {"fwet": (("time", "lat", "lon"), np.ones((2, 2, 2), dtype=np.float32))},
        coords={"time": [1, 2], "lat": [0.5, 1.5], "lon": [100.5, 101.5]},
    )
    template_2021 = xr.Dataset(
        {"fwet": (("time", "lat", "lon"), np.full((2, 2, 2), 7.0, dtype=np.float32))},
        coords={"time": [1, 2], "lat": [0.5, 1.5], "lon": [100.5, 101.5]},
    )

    write_netcdf(base_path / "cfg_a/force_a/fwet_cfg_a_force_a_reso025_2020.nc", template_2020)
    write_netcdf(base_path / "cfg_a/force_a/fwet_cfg_a_force_a_reso025_2021.nc", template_2021)

    loader = get_loader("topmodel", with_common_fields(base_path, loader_type="topmodel"))

    assert loader.metadata().temporal_coverage == ("2020", "2021")

    result = loader.load(time_range=("2021-01-01", "2021-01-31"))

    assert result.sizes["time"] == 1
    assert str(result.time.values[0])[:10] == "2021-01-01"
    assert float(result["wetland_fraction"].isel(time=0, lat=0, lon=0).item()) == 7.0
