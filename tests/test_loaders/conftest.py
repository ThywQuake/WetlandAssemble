from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import xarray as xr
from rasterio.transform import from_origin


def write_netcdf(path: Path, dataset: xr.Dataset) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_netcdf(path)
    return path


def write_single_band_geotiff(
    path: Path,
    data: np.ndarray,
    *,
    crs: str = "EPSG:4326",
    transform: rasterio.Affine | None = None,
    nodata: float | int | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if transform is None:
        transform = from_origin(0.0, float(data.shape[0]), 1.0, 1.0)

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data, 1)

    return path


def write_multiband_geotiff(
    path: Path,
    data: np.ndarray,
    *,
    crs: str = "EPSG:4326",
    transform: rasterio.Affine | None = None,
    nodata: float | int | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if transform is None:
        transform = from_origin(0.0, float(data.shape[1]), 1.0, 1.0)

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[1],
        width=data.shape[2],
        count=data.shape[0],
        dtype=data.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data)

    return path


def with_common_fields(path: Path, **extra: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        "name": "Dataset",
        "path": str(path),
        "resolution": "1deg",
    }
    config.update(extra)
    return config
