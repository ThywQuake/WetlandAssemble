from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import rioxarray  # noqa: F401
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


def make_reference_grid(
    lat_range: tuple[float, float] = (0.0, 2.0),
    lon_range: tuple[float, float] = (0.0, 2.0),
    resolution_deg: float = 1.0,
) -> xr.DataArray:
    """Build a small WGS84 reference grid for testing load(reference_grid=...)."""
    south, north = lat_range
    west, east = lon_range
    n_lat = max(1, round((north - south) / resolution_deg))
    n_lon = max(1, round((east - west) / resolution_deg))
    lats = np.linspace(
        north - resolution_deg / 2, south + resolution_deg / 2, n_lat,
    )
    lons = np.linspace(
        west + resolution_deg / 2, east - resolution_deg / 2, n_lon,
    )
    grid = xr.DataArray(
        np.zeros((n_lat, n_lon), dtype=np.float32),
        dims=("lat", "lon"),
        coords={"lat": lats, "lon": lons},
    )
    grid = grid.rio.write_crs("EPSG:4326")
    grid = grid.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    return grid


def with_common_fields(path: Path, **extra: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        "name": "Dataset",
        "path": str(path),
        "resolution": "1deg",
    }
    config.update(extra)
    return config
