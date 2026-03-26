"""Binary harmonization helpers for rough wetland comparison."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Literal, cast

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
from rasterio.enums import Resampling

from WA.loaders.base import BBox

logger = logging.getLogger(__name__)

BinaryAggregation = Literal["mean", "max"]

BINARY_WETLAND_THRESHOLD = 0.5
DEFAULT_COMPARISON_RESOLUTION_DEG = 0.25
EXCLUDED_BINARY_DATASET_IDS = frozenset({"berkeley_rwawc", "lstm_wetland"})
SUBMONTHLY_TIME_RESOLUTIONS = frozenset({"daily", "4-day"})

_CLASSIFICATION_BINARY_MAPS: dict[str, dict[int, float]] = {
    "g2017": {
        10: 0.0,
        20: 1.0,
        30: 1.0,
        40: 1.0,
        50: 1.0,
        60: 1.0,
        70: 1.0,
        80: 1.0,
        90: 1.0,
        100: 1.0,
    },
    "glwd_v2": {
        0: 0.0,
        1: 0.0,
        2: 0.0,
        3: 0.0,
        4: 0.0,
        5: 0.0,
        6: 0.0,
        7: 0.0,
        8: 1.0,
        9: 1.0,
        10: 1.0,
        11: 1.0,
        12: 1.0,
        13: 1.0,
        14: 1.0,
        15: 1.0,
        16: 1.0,
        17: 1.0,
        18: 1.0,
        19: 1.0,
        20: 1.0,
        21: 1.0,
        22: 1.0,
        23: 1.0,
        24: 1.0,
        25: 1.0,
        26: 1.0,
        27: 1.0,
        28: 1.0,
        29: 1.0,
        30: 1.0,
        31: 1.0,
        32: 1.0,
        33: 0.0,
    },
    "gwd30": {
        0: 0.0,
        1: 0.0,
        2: 0.0,
        3: 0.0,
        4: 0.0,
        5: 0.0,
        6: 0.0,
        7: 0.0,
        8: 1.0,
        9: 1.0,
        10: 1.0,
        11: 1.0,
        12: 1.0,
        13: 1.0,
        14: 0.0,
    },
}


class BinaryComparisonUnavailableError(ValueError):
    """Raised when a dataset cannot participate in rough binary comparison."""


class EmptyBinarySurfaceError(BinaryComparisonUnavailableError):
    """Raised when a dataset produces no usable binary surface for comparison."""

    def __init__(
        self,
        *,
        dataset_id: str,
        source_variable: str,
        stage: str,
    ) -> None:
        self.dataset_id = dataset_id
        self.source_variable = source_variable
        self.stage = stage
        super().__init__(
            f"{dataset_id} produced an empty binary surface from "
            f"{source_variable} at {stage}"
        )


def create_comparison_grid(
    bounds: BBox,
    *,
    resolution_deg: float = DEFAULT_COMPARISON_RESOLUTION_DEG,
    crs: str = "EPSG:4326",
) -> xr.DataArray:
    """Create a regular WGS84 comparison grid."""

    west, south, east, north = bounds
    if resolution_deg <= 0:
        raise ValueError("resolution_deg must be positive")
    if not west < east or not south < north:
        raise ValueError("bounds must be ordered as west < east and south < north")

    lons = np.arange(west, east, resolution_deg, dtype=np.float64)
    lats = np.arange(north, south, -resolution_deg, dtype=np.float64)
    grid = xr.DataArray(
        np.zeros((len(lats), len(lons)), dtype=np.float32),
        coords={"lat": lats, "lon": lons},
        dims=("lat", "lon"),
        name="comparison_grid",
    )
    grid.attrs["comparison_resolution_deg"] = float(resolution_deg)
    grid = grid.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    return cast(xr.DataArray, grid.rio.write_crs(crs, inplace=False))


def dataset_supports_binary_comparison(dataset_id: str) -> bool:
    """Return whether a dataset is eligible for rough binary comparison."""

    return dataset_id not in EXCLUDED_BINARY_DATASET_IDS


def harmonize_binary_collection(
    datasets: Mapping[str, xr.Dataset],
    reference_grid: xr.DataArray,
    *,
    aggregation: BinaryAggregation = "mean",
) -> dict[str, xr.DataArray]:
    """Harmonize all eligible datasets onto a shared binary-fraction grid."""

    harmonized: dict[str, xr.DataArray] = {}
    for dataset_id, dataset in datasets.items():
        if not dataset_supports_binary_comparison(dataset_id):
            continue
        harmonized[dataset_id] = harmonize_binary_dataset(
            dataset_id,
            dataset,
            reference_grid=reference_grid,
            aggregation=aggregation,
        )

    if not harmonized:
        raise BinaryComparisonUnavailableError("No eligible datasets were provided")

    return harmonized


def harmonize_binary_dataset(
    dataset_id: str,
    dataset: xr.Dataset,
    *,
    reference_grid: xr.DataArray,
    aggregation: BinaryAggregation = "mean",
) -> xr.DataArray:
    """Convert one dataset into an aligned wetland-fraction surface."""

    if not dataset_supports_binary_comparison(dataset_id):
        raise BinaryComparisonUnavailableError(
            f"{dataset_id} is not eligible for rough binary wetland comparison"
        )

    source, resampling, source_variable = _prepare_binary_source(
        dataset_id,
        dataset,
        aggregation=aggregation,
    )
    aligned = _align_binary_fraction(source, reference_grid, resampling=resampling)
    _ensure_non_empty_binary_surface(
        aligned,
        dataset_id=dataset_id,
        source_variable=source_variable,
        stage="aligned_to_reference_grid",
    )
    aligned.name = "wetland_fraction"
    aligned.attrs.update(
        {
            "dataset_id": dataset_id,
            "comparison_source_variable": source_variable,
            "comparison_aggregation": aggregation,
            "comparison_threshold": BINARY_WETLAND_THRESHOLD,
        }
    )
    return aligned


def select_comparison_slice(
    data: xr.DataArray,
    target_time: str | pd.Timestamp,
) -> xr.DataArray:
    """Select one comparison month from a harmonized surface."""

    timestamp = pd.Timestamp(target_time)
    if "time" not in data.dims:
        selected = data.copy()
        _ensure_non_empty_binary_surface(
            selected,
            dataset_id=str(selected.attrs.get("dataset_id", "unknown_dataset")),
            source_variable=str(
                selected.attrs.get("comparison_source_variable", "unknown_variable")
            ),
            stage="comparison_slice",
        )
        selected.attrs["comparison_time"] = timestamp.isoformat()
        selected.attrs["comparison_source_time"] = timestamp.isoformat()
        return selected

    selected = _select_time_slice(data, timestamp)
    _ensure_non_empty_binary_surface(
        selected,
        dataset_id=str(data.attrs.get("dataset_id", "unknown_dataset")),
        source_variable=str(data.attrs.get("comparison_source_variable", "unknown_variable")),
        stage="comparison_slice",
    )
    source_time = _serialize_source_time(selected)
    selected = _drop_auxiliary_coords(selected)
    selected.attrs.update(data.attrs)
    selected.attrs["comparison_time"] = timestamp.isoformat()
    selected.attrs["comparison_source_time"] = source_time
    return selected


def _prepare_binary_source(
    dataset_id: str,
    dataset: xr.Dataset,
    *,
    aggregation: BinaryAggregation,
) -> tuple[xr.DataArray, Resampling, str]:
    if dataset_id == "g2017" and "wetland_nolake" in dataset:
        source = _clip_fraction(dataset["wetland_nolake"])
        _ensure_non_empty_binary_surface(
            source,
            dataset_id=dataset_id,
            source_variable="wetland_nolake",
            stage="prepared_source",
        )
        return source, Resampling.bilinear, "wetland_nolake"

    if "wetland_fraction" in dataset:
        source = dataset["wetland_fraction"]
        if dataset_id == "topmodel":
            source = _collapse_topmodel_ensemble(source)
        source = _clip_fraction(source)
        source = _aggregate_submonthly_time(source, dataset, aggregation=aggregation)
        _ensure_non_empty_binary_surface(
            source,
            dataset_id=dataset_id,
            source_variable="wetland_fraction",
            stage="prepared_source",
        )
        return source, Resampling.bilinear, "wetland_fraction"

    if dataset_id == "g2017" and "wetland" in dataset:
        mapped = _map_classification_to_binary_fraction(
            dataset["wetland"],
            _CLASSIFICATION_BINARY_MAPS["g2017"],
        )
        _ensure_non_empty_binary_surface(
            mapped,
            dataset_id=dataset_id,
            source_variable="wetland",
            stage="prepared_source",
        )
        return mapped, Resampling.average, "wetland"

    if dataset_id == "glwd_v2" and "combined_classes" in dataset:
        mapped = _map_classification_to_binary_fraction(
            dataset["combined_classes"],
            _CLASSIFICATION_BINARY_MAPS["glwd_v2"],
        )
        _ensure_non_empty_binary_surface(
            mapped,
            dataset_id=dataset_id,
            source_variable="combined_classes",
            stage="prepared_source",
        )
        return mapped, Resampling.average, "combined_classes"

    if dataset_id == "gwd30" and "wetland_class" in dataset:
        mapped = _map_classification_to_binary_fraction(
            dataset["wetland_class"],
            _CLASSIFICATION_BINARY_MAPS["gwd30"],
        )
        mapped = _aggregate_submonthly_time(mapped, dataset, aggregation=aggregation)
        _ensure_non_empty_binary_surface(
            mapped,
            dataset_id=dataset_id,
            source_variable="wetland_class",
            stage="prepared_source",
        )
        return mapped, Resampling.average, "wetland_class"

    raise BinaryComparisonUnavailableError(
        f"Could not derive a binary wetland surface for {dataset_id}"
    )


def _collapse_topmodel_ensemble(data: xr.DataArray) -> xr.DataArray:
    collapse_dims = [dim for dim in ("config", "forcing") if dim in data.dims]
    if not collapse_dims:
        return data
    return data.mean(dim=collapse_dims, skipna=True)


def _aggregate_submonthly_time(
    data: xr.DataArray,
    dataset: xr.Dataset,
    *,
    aggregation: BinaryAggregation,
) -> xr.DataArray:
    if "time" not in data.dims:
        return data.astype(np.float32)

    time_resolution = str(dataset.attrs.get("time_resolution") or "")
    if time_resolution not in SUBMONTHLY_TIME_RESOLUTIONS:
        return (
            data.assign_coords(time=pd.to_datetime(data["time"].values))
            .sortby("time")
            .astype(np.float32)
        )

    monthly = data.assign_coords(time=pd.to_datetime(data["time"].values)).resample(time="MS")
    if aggregation == "max":
        reduced = monthly.max(skipna=True)
    else:
        reduced = monthly.mean(skipna=True)
    return reduced.sortby("time").astype(np.float32)


def _map_classification_to_binary_fraction(
    data: xr.DataArray,
    mapping: Mapping[int, float],
) -> xr.DataArray:
    result = xr.full_like(data, np.nan, dtype=np.float32)
    for source_value, binary_value in mapping.items():
        result = xr.where(  # type: ignore[no-untyped-call]
            data == source_value,
            np.float32(binary_value),
            result,
        )
    return result.where(data.notnull()).astype(np.float32)


def _clip_fraction(data: xr.DataArray) -> xr.DataArray:
    clipped = data.where(data.notnull())
    return clipped.clip(min=0.0, max=1.0).astype(np.float32)


def _align_binary_fraction(
    data: xr.DataArray,
    reference_grid: xr.DataArray,
    *,
    resampling: Resampling,
) -> xr.DataArray:
    if "time" not in data.dims:
        return _align_2d_surface(data, reference_grid, resampling=resampling)

    aligned_slices: list[xr.DataArray] = []
    for timestamp in pd.to_datetime(data["time"].values):
        aligned = _align_2d_surface(data.sel(time=timestamp), reference_grid, resampling=resampling)
        aligned_slices.append(aligned.expand_dims(time=[timestamp]))

    merged = xr.concat(aligned_slices, dim="time").sortby("time")
    return merged.astype(np.float32)


def _is_already_aligned(
    data: xr.DataArray,
    reference_grid: xr.DataArray,
    *,
    rtol: float = 1e-6,
) -> bool:
    """Return True when *data* is already on the same spatial grid as *reference_grid*."""

    for dim in ("lat", "lon"):
        if dim not in data.dims or dim not in reference_grid.dims:
            return False
        if data.sizes[dim] != reference_grid.sizes[dim]:
            return False
        if not np.allclose(
            data[dim].values, reference_grid[dim].values, rtol=rtol, atol=0,
        ):
            return False
    return True


def _align_2d_surface(
    data: xr.DataArray,
    reference_grid: xr.DataArray,
    *,
    resampling: Resampling,
) -> xr.DataArray:
    if _is_single_cell_latlon_surface(data):
        return _align_single_cell_surface(data, reference_grid)

    if _is_already_aligned(data, reference_grid):
        logger.debug("data already aligned to reference grid, skipping reproject")
        return cast(xr.DataArray, data.astype(np.float32))

    prepared = _prepare_spatial_array(data)
    reference = _prepare_spatial_array(reference_grid)
    aligned = prepared.rio.reproject_match(reference, resampling=resampling)
    aligned = aligned.drop_vars("spatial_ref", errors="ignore")
    aligned = aligned.drop_vars("band", errors="ignore")
    if "band" in aligned.dims:
        aligned = aligned.squeeze("band", drop=True)
    rename_map: dict[str, str] = {}
    if "x" in aligned.dims:
        rename_map["x"] = "lon"
    if "y" in aligned.dims:
        rename_map["y"] = "lat"
    if rename_map:
        aligned = aligned.rename(rename_map)
    return cast(xr.DataArray, aligned.astype(np.float32))


def _is_single_cell_latlon_surface(data: xr.DataArray) -> bool:
    return {"lat", "lon"}.issubset(data.dims) and data.sizes["lat"] == 1 and data.sizes["lon"] == 1


def _align_single_cell_surface(
    data: xr.DataArray,
    reference_grid: xr.DataArray,
) -> xr.DataArray:
    result = xr.full_like(reference_grid, np.nan, dtype=np.float32)
    value = float(data.isel(lat=0, lon=0).item())
    if np.isnan(value):
        return result

    source_lon = float(data["lon"].item())
    source_lat = float(data["lat"].item())
    reference_lons = np.asarray(reference_grid["lon"].values, dtype=np.float64)
    reference_lats = np.asarray(reference_grid["lat"].values, dtype=np.float64)
    fallback_resolution = float(
        reference_grid.attrs.get("comparison_resolution_deg", DEFAULT_COMPARISON_RESOLUTION_DEG)
    )
    lon_resolution = _infer_axis_resolution(reference_lons, fallback=fallback_resolution)
    lat_resolution = _infer_axis_resolution(reference_lats, fallback=fallback_resolution)

    lon_mask = _overlap_mask(reference_lons, source_lon, lon_resolution)
    lat_mask = _overlap_mask(reference_lats, source_lat, lat_resolution)

    if not lon_mask.any():
        _mark_nearest_if_close(lon_mask, reference_lons, source_lon, lon_resolution)
    if not lat_mask.any():
        _mark_nearest_if_close(lat_mask, reference_lats, source_lat, lat_resolution)

    if not lon_mask.any() or not lat_mask.any():
        return result

    result.loc[
        {
            "lat": reference_grid["lat"].values[lat_mask],
            "lon": reference_grid["lon"].values[lon_mask],
        }
    ] = np.float32(value)
    return result


def _infer_axis_resolution(values: np.ndarray, *, fallback: float) -> float:
    if values.size < 2:
        return fallback
    diffs = np.abs(np.diff(values))
    finite_diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    if finite_diffs.size == 0:
        return fallback
    return float(np.median(finite_diffs))


def _overlap_mask(
    reference_values: np.ndarray,
    source_center: float,
    resolution: float,
) -> np.ndarray:
    half_resolution = resolution / 2.0
    epsilon = resolution * 1e-6
    lower = source_center - half_resolution - epsilon
    upper = source_center + half_resolution + epsilon
    return (reference_values >= lower) & (reference_values <= upper)


def _mark_nearest_if_close(
    mask: np.ndarray,
    reference_values: np.ndarray,
    source_center: float,
    resolution: float,
) -> None:
    nearest_index = int(np.argmin(np.abs(reference_values - source_center)))
    max_distance = (resolution / 2.0) + (resolution * 1e-6)
    if abs(float(reference_values[nearest_index]) - source_center) <= max_distance:
        mask[nearest_index] = True


def _select_time_slice(data: xr.DataArray, timestamp: pd.Timestamp) -> xr.DataArray:
    """Select one time slice, falling back to month-level matching when needed."""

    try:
        return data.sel(time=timestamp)
    except KeyError:
        time_index = pd.DatetimeIndex(pd.to_datetime(data["time"].values))
        month_matches = np.flatnonzero(time_index.to_period("M") == timestamp.to_period("M"))
        if len(month_matches) == 0:
            raise KeyError(
                "No comparison slice matched target month "
                f"{timestamp.strftime('%Y-%m')} for available times {list(time_index[:6])}"
            ) from None
        if len(month_matches) > 1:
            matched_times = [str(time_index[index]) for index in month_matches.tolist()]
            raise ValueError(
                "Ambiguous comparison slice for target month "
                f"{timestamp.strftime('%Y-%m')}: matched {matched_times}"
            ) from None
        return data.isel(time=int(month_matches[0]))


def _serialize_source_time(selected: xr.DataArray) -> str:
    """Serialize the resolved source timestamp for reporting."""

    if "time" not in selected.coords:
        return ""
    return str(pd.Timestamp(selected["time"].item()).isoformat())


def _drop_auxiliary_coords(selected: xr.DataArray) -> xr.DataArray:
    """Drop scalar reporting coords so comparison surfaces stay concat-safe."""

    drop_names = [
        name
        for name in selected.coords
        if name not in selected.dims and name not in {"lat", "lon"}
    ]
    if not drop_names:
        return selected
    return selected.drop_vars(drop_names, errors="ignore")


def _ensure_non_empty_binary_surface(
    data: xr.DataArray,
    *,
    dataset_id: str,
    source_variable: str,
    stage: str,
) -> None:
    """Reject harmonized surfaces that contain no valid comparison cells."""

    if int(data.count().item()) == 0:
        raise EmptyBinarySurfaceError(
            dataset_id=dataset_id,
            source_variable=source_variable,
            stage=stage,
        )


def _prepare_spatial_array(data: xr.DataArray) -> xr.DataArray:
    prepared = data
    if {"lat", "lon"}.issubset(prepared.dims):
        prepared = prepared.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    if prepared.rio.crs is None:
        prepared = cast(xr.DataArray, prepared.rio.write_crs("EPSG:4326", inplace=False))
    return prepared
