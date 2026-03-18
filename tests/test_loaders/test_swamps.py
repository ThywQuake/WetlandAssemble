from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from tests.test_loaders.conftest import with_common_fields, write_netcdf
from WA.loaders import get_loader


def test_swamps_loader_handles_sensor_shift_patterns(tmp_path: Path) -> None:
    base_path = tmp_path / "swamps"
    december_1999 = xr.Dataset(
        {
            "fw": (("lat", "lon"), np.array([[0.1, 0.2]], dtype=np.float32)),
            "flag": (("lat", "lon"), np.array([[0, 1]], dtype=np.int8)),
        },
        coords={"lat": [0.5], "lon": [100.0, 101.0]},
    )
    january_2000 = xr.Dataset(
        {
            "fw": (("lat", "lon"), np.array([[0.3, 0.4]], dtype=np.float32)),
            "flag": (("lat", "lon"), np.array([[1, 0]], dtype=np.int8)),
        },
        coords={"lat": [0.5], "lon": [100.0, 101.0]},
    )

    write_netcdf(base_path / "stable/1999/12/SWAMPS.FW.F11.ERS.19991231.nc", december_1999)
    write_netcdf(base_path / "stable/2000/01/SWAMPS.FW.F13.QUIKSCAT.20000101.nc", january_2000)

    loader = get_loader(
        "swamps",
        with_common_fields(
            base_path,
            loader_type="swamps",
            pattern="stable/{year}/{month}/*.nc",
            sensor_shift_year=2000,
        ),
    )

    result = loader.load()

    assert list(result.data_vars) == ["wetland_fraction", "flag"]
    assert result.sizes["time"] == 2
    assert str(result.time.values[0])[:10] == "1999-12-31"
    assert result.attrs["sensor_shift_year"] == 2000
