"""Shared loader contracts and helper utilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr

BBox = tuple[float, float, float, float]
TimeRange = tuple[str, str]


@dataclass(frozen=True)
class DatasetMetadata:
    """Standard metadata returned by every wetland dataset loader."""

    dataset_id: str
    name: str
    source_path: str
    crs: str | None
    spatial_resolution: str | None
    temporal_coverage: tuple[str | None, str | None] | None
    time_resolution: str | None
    is_static: bool
    is_classification: bool
    native_variables: tuple[str, ...] = field(default_factory=tuple)
    semantic_mapping: Mapping[str, str] = field(default_factory=dict)

    def to_attrs(self) -> dict[str, object]:
        temporal_start = None
        temporal_end = None
        if self.temporal_coverage is not None:
            temporal_start, temporal_end = self.temporal_coverage

        return {
            "dataset_id": self.dataset_id,
            "dataset_name": self.name,
            "source_path": self.source_path,
            "dataset_crs": self.crs,
            "spatial_resolution": self.spatial_resolution,
            "time_resolution": self.time_resolution,
            "temporal_start": temporal_start,
            "temporal_end": temporal_end,
            "is_static": self.is_static,
            "is_classification": self.is_classification,
            "native_variables": list(self.native_variables),
            "semantic_mapping": dict(self.semantic_mapping),
        }


class DatasetLoader(ABC):
    """Common contract for all raw dataset loaders."""

    def __init__(self, dataset_id: str, config: Mapping[str, Any]) -> None:
        self.dataset_id = dataset_id
        self.config = dict(config)
        self.name = str(self.config["name"])
        self.base_path = Path(str(self.config["path"]))

    @abstractmethod
    def load(
        self,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
    ) -> xr.Dataset:
        """Load data, optionally subsetting by bounding box and time window."""

    @abstractmethod
    def metadata(self) -> DatasetMetadata:
        """Return dataset metadata without loading raster or NetCDF payloads."""

    def finalize_dataset(
        self,
        dataset: xr.Dataset,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
    ) -> xr.Dataset:
        """Apply shared dimension normalization, subsetting, and metadata."""

        dataset = normalize_spatial_dimensions(dataset)
        dataset = apply_bbox(dataset, bbox)
        dataset = apply_time_range(dataset, time_range)
        dataset.attrs.update(self.metadata().to_attrs())
        return dataset

    def temporal_coverage(self) -> tuple[str | None, str | None] | None:
        time_range = self.config.get("time_range")
        if isinstance(time_range, Mapping):
            start = time_range.get("start")
            end = time_range.get("end")
            return (
                str(start) if start is not None else None,
                str(end) if end is not None else None,
            )

        years = self.config.get("years")
        if isinstance(years, list) and years:
            return (str(min(years)), str(max(years)))

        return None


def normalize_spatial_dimensions(dataset: xr.Dataset) -> xr.Dataset:
    """Normalize common latitude/longitude dimension names."""

    rename_map: dict[str, str] = {}
    if "latitude" in dataset.dims or "latitude" in dataset.coords:
        rename_map["latitude"] = "lat"
    if "longitude" in dataset.dims or "longitude" in dataset.coords:
        rename_map["longitude"] = "lon"

    if {"x", "y"}.issubset(set(dataset.dims) | set(dataset.coords)):
        crs = None
        if hasattr(dataset, "rio"):
            crs = dataset.rio.crs
        if crs is not None and str(crs).upper().endswith("4326"):
            rename_map["x"] = "lon"
            rename_map["y"] = "lat"

    if rename_map:
        dataset = dataset.rename(rename_map)

    return dataset


def apply_bbox(dataset: xr.Dataset, bbox: BBox | None) -> xr.Dataset:
    """Subset a dataset to the requested lon/lat bounding box when available."""

    if bbox is None:
        return dataset

    lon_name = _first_present(dataset, ("lon", "longitude", "x"))
    lat_name = _first_present(dataset, ("lat", "latitude", "y"))
    if lon_name is None or lat_name is None:
        return dataset

    min_lon, min_lat, max_lon, max_lat = bbox
    lon_slice = _ordered_slice(dataset[lon_name], min_lon, max_lon)
    lat_slice = _ordered_slice(dataset[lat_name], min_lat, max_lat)
    return dataset.sel({lon_name: lon_slice, lat_name: lat_slice})


def apply_time_range(dataset: xr.Dataset, time_range: TimeRange | None) -> xr.Dataset:
    """Subset a dataset to the requested time range when a time dimension exists."""

    if time_range is None or "time" not in dataset.coords:
        return dataset

    start, end = time_range
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    return dataset.sel(time=slice(start_ts, end_ts))


def ensure_datetime_index(dataset: xr.Dataset) -> xr.Dataset:
    """Ensure the `time` coordinate is backed by pandas timestamps."""

    if "time" not in dataset.coords:
        return dataset

    dataset = dataset.assign_coords(time=pd.to_datetime(dataset["time"].values))
    return dataset


def _ordered_slice(coordinate: xr.DataArray, lower: float, upper: float) -> slice:
    values = coordinate.values
    if values[0] <= values[-1]:
        return slice(lower, upper)
    return slice(upper, lower)


def _first_present(dataset: xr.Dataset, names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in dataset.dims or name in dataset.coords:
            return name
    return None
