"""Shared helpers for raster-based and time-indexed dataset loaders."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pandas as pd
import rasterio
import xarray as xr
from rasterio.warp import transform_bounds
from rioxarray import open_rasterio
from rioxarray.merge import merge_arrays

from WA.loaders.base import BBox


def open_single_band_raster(
    path: Path,
    *,
    reproject_to_wgs84: bool = True,
    bbox: BBox | None = None,
) -> xr.DataArray:
    """Open a single-band raster as a 2D DataArray."""

    raster = cast(xr.DataArray, open_rasterio(path, masked=True)).squeeze("band", drop=True)
    if bbox is not None and raster.rio.crs is not None:
        raster = cast(
            xr.DataArray,
            raster.rio.clip_box(
                *bbox,
                crs="EPSG:4326",
                auto_expand=True,
                allow_one_dimensional_raster=True,
            ),
        )
    if reproject_to_wgs84 and raster.rio.crs is not None and str(raster.rio.crs) != "EPSG:4326":
        raster = raster.rio.reproject("EPSG:4326")
    return raster


def open_multiband_raster(
    path: Path,
    *,
    reproject_to_wgs84: bool = True,
    bbox: BBox | None = None,
    band_indexes: Sequence[int] | None = None,
) -> xr.DataArray:
    """Open a multi-band raster, optionally reprojecting it to WGS84."""

    raster = cast(xr.DataArray, open_rasterio(path, masked=True))
    if band_indexes is not None:
        raster = raster.isel(band=list(band_indexes))
    if bbox is not None and raster.rio.crs is not None:
        raster = cast(
            xr.DataArray,
            raster.rio.clip_box(
                *bbox,
                crs="EPSG:4326",
                auto_expand=True,
                allow_one_dimensional_raster=True,
            ),
        )
    if reproject_to_wgs84 and raster.rio.crs is not None and str(raster.rio.crs) != "EPSG:4326":
        raster = raster.rio.reproject("EPSG:4326")
    return raster


def merge_rasters(rasters: Sequence[xr.DataArray]) -> xr.DataArray:
    """Merge reprojected rasters into one virtual mosaic."""

    if not rasters:
        raise ValueError("No rasters were provided for merging")

    if len(rasters) == 1:
        return rasters[0]

    return merge_arrays(list(rasters))


def parse_first_integer(text: str) -> int:
    """Extract the first integer token from a path or file stem."""

    match = re.search(r"(\d+)", text)
    if match is None:
        raise ValueError(f"Could not extract an integer from {text!r}")
    return int(match.group(1))


def parse_compact_date(path: Path) -> pd.Timestamp:
    """Parse the first YYYYMMDD token found in a filename."""

    match = re.search(r"(?<!\d)(\d{8})(?!\d)", path.stem)
    if match is None:
        raise ValueError(f"Could not parse YYYYMMDD date from {path.name}")
    return pd.Timestamp(match.group(1))


def intersects_bbox(path: Path, bbox: BBox) -> bool:
    """Return whether a raster intersects a lon/lat bounding box."""

    min_lon, min_lat, max_lon, max_lat = bbox
    with rasterio.open(path) as src:
        if src.crs is None:
            candidate_bounds = (min_lon, min_lat, max_lon, max_lat)
        elif str(src.crs) == "EPSG:4326":
            candidate_bounds = (min_lon, min_lat, max_lon, max_lat)
        else:
            candidate_bounds = transform_bounds(
                "EPSG:4326",
                src.crs,
                min_lon,
                min_lat,
                max_lon,
                max_lat,
                densify_pts=21,
            )

        left, bottom, right, top = src.bounds
        query_left, query_bottom, query_right, query_top = candidate_bounds
        return not (
            query_right < left
            or query_left > right
            or query_top < bottom
            or query_bottom > top
        )


def monthly_index_for_year(year: int, month_numbers: Sequence[int]) -> pd.DatetimeIndex:
    """Convert 1-based month numbers into monthly timestamps for a given year."""

    return pd.DatetimeIndex(
        [pd.Timestamp(year=year, month=int(month), day=1) for month in month_numbers]
    )


def four_day_index_for_year(year: int, count: int) -> pd.DatetimeIndex:
    """Build a 4-day interval timestamp index from January 1st."""

    base = pd.Timestamp(year=year, month=1, day=1)
    return pd.DatetimeIndex([base + pd.Timedelta(days=4 * offset) for offset in range(count)])
