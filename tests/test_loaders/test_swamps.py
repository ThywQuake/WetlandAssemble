from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from tests.test_loaders.conftest import with_common_fields, write_netcdf
from WA.loaders import get_loader


def test_swamps_loader_masks_fill_values(tmp_path: Path) -> None:
    base_path = tmp_path / "swamps"
    data_with_fill = xr.Dataset(
        {
            "fw": (("lat", "lon"), np.array([[0.5, -9999.0, 0.1, -9999.0]], dtype=np.float32)),
        },
        coords={"lat": [0.5], "lon": [100.0, 101.0, 102.0, 103.0]},
    )
    write_netcdf(base_path / "stable/2010/01/SWAMPS.FW.F13.QUIKSCAT.20100101.nc", data_with_fill)

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

    wf = result["wetland_fraction"].values.flatten()
    assert np.isnan(wf[1]), "fill value -9999 should be masked to NaN"
    assert np.isnan(wf[3]), "fill value -9999 should be masked to NaN"
    assert wf[0] == np.float32(0.5), "valid value should be preserved"
    assert wf[2] == np.float32(0.1), "valid value should be preserved"


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
