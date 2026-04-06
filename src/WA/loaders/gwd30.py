"""Loader for GWD30 tiled multi-band GeoTIFF mosaics."""

from __future__ import annotations

import gc
import logging
import os
import re
import tempfile
import time
import warnings
from collections import defaultdict
from collections.abc import Callable, Mapping
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from rasterio.enums import Resampling
from rasterio.errors import WindowError
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds

from WA.classification import source_class_ids_by_unified_id, unified_class_ids
from WA.comparison.harmonize import _CLASSIFICATION_BINARY_MAPS, BINARY_WETLAND_THRESHOLD
from WA.loaders._shared import (
    four_day_index_for_year,
    merge_rasters,
    open_multiband_raster,
)
from WA.loaders.base import (
    BBox,
    DatasetLoader,
    DatasetMetadata,
    TimeRange,
    ensure_datetime_index,
    validate_reference_grid,
)
from WA.loaders.registry import register_loader
from WA.utils.mgrs_tiling import GWD30TilingSystem
from WA.utils.progress import tqdm

logger = logging.getLogger(__name__)

# Spatial index for staged tiles: grid hash mapping (row_bin, col_bin) -> list of (path, bbox)
# This avoids O(N) linear scan when finding tiles intersecting a chunk bbox
_TILE_CODE_PATTERN = re.compile(r"(?<![A-Z0-9])T?(\d{1,2}[C-HJ-NP-X][A-HJ-NP-Z]{2})(?![A-Z0-9])")
_TEMP_TILE_NODATA = np.float32(-9999.0)
_GWD30_CLASS_COUNT = 15
_GWD30_STAGE_MAX_WORKERS = 4
_GWD30_STAGE_LOCK_STALE_SECONDS = 6 * 60 * 60


StagedTileTransform = Callable[[xr.Dataset], xr.Dataset]


def _build_binary_lookup(mapping: Mapping[int, float]) -> np.ndarray:
    """Build a fixed-size lookup table for fast class-to-binary conversion."""

    lookup = np.full(256, np.nan, dtype=np.float32)
    for source_value, binary_value in mapping.items():
        if 0 <= int(source_value) < len(lookup):
            lookup[int(source_value)] = np.float32(binary_value)
    return lookup


_GWD30_BINARY_LOOKUP = _build_binary_lookup(_CLASSIFICATION_BINARY_MAPS["gwd30"])


def _bbox_intersects(a: BBox, b: BBox) -> bool:
    """Return whether two lon/lat bounding boxes intersect."""

    a_min_lon, a_min_lat, a_max_lon, a_max_lat = a
    b_min_lon, b_min_lat, b_max_lon, b_max_lat = b
    return not (
        a_max_lon < b_min_lon
        or b_max_lon < a_min_lon
        or a_max_lat < b_min_lat
        or b_max_lat < a_min_lat
    )


def _bbox_intersection(a: BBox, b: BBox) -> BBox | None:
    """Return the lon/lat intersection of two bounding boxes."""

    min_lon = max(a[0], b[0])
    min_lat = max(a[1], b[1])
    max_lon = min(a[2], b[2])
    max_lat = min(a[3], b[3])
    if min_lon >= max_lon or min_lat >= max_lat:
        return None
    return (min_lon, min_lat, max_lon, max_lat)


def _grid_hash_key(bbox: BBox, bin_size_deg: float = 5.0) -> set[tuple[int, int]]:
    """Return grid hash keys for a bbox.

    Used for spatial indexing: divide the world into bin_size_deg x bin_size_deg cells,
    return all cell keys that the bbox touches.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    min_row = int((min_lat + 90) / bin_size_deg)
    max_row = int((max_lat + 90) / bin_size_deg)
    min_col = int((min_lon + 180) / bin_size_deg)
    max_col = int((max_lon + 180) / bin_size_deg)
    return {(r, c) for r in range(min_row, max_row + 1) for c in range(min_col, max_col + 1)}


def _build_staged_tile_index(
    staged_tiles: list[tuple[Path, BBox]]
) -> tuple[dict[tuple[int, int], list[tuple[Path, BBox]]], float]:
    """Build a grid hash spatial index for staged tiles.

    Returns:
        - index: dict mapping (row_bin, col_bin) -> list of (path, bbox)
        - bin_size_deg: the bin size used (degrees)
    """
    # Adaptive bin size: ~5 degrees for global coverage
    bin_size_deg = 5.0
    index: dict[tuple[int, int], list[tuple[Path, BBox]]] = defaultdict(list)

    for stage_path, stage_bbox in staged_tiles:
        keys = _grid_hash_key(stage_bbox, bin_size_deg)
        for key in keys:
            index[key].append((stage_path, stage_bbox))

    return dict(index), bin_size_deg
def _path_bounds_wgs84(path: Path) -> BBox | None:
    """Return one raster's bounds in EPSG:4326 coordinates."""

    try:
        with rasterio.open(path) as src:
            if src.crs is None or str(src.crs) == "EPSG:4326":
                bounds = cast(BBox, src.bounds)
            else:
                bounds = cast(
                    BBox,
                    transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21),
                )
    except Exception:
        return None

    return (
        max(-180.0, float(bounds[0])),
        max(-90.0, float(bounds[1])),
        min(180.0, float(bounds[2])),
        min(90.0, float(bounds[3])),
    )


def _reference_grid_axis_step(reference_grid: xr.DataArray, dim: str) -> float:
    """Infer one spatial axis step for a regular reference grid."""

    coords = np.asarray(reference_grid.coords[dim].values, dtype=np.float64)
    if coords.size > 1:
        diffs = np.abs(np.diff(coords))
        nonzero = diffs[diffs > 0]
        if nonzero.size > 0:
            return float(nonzero[0])

    x_res, y_res = reference_grid.rio.resolution()
    if dim in {"lon", "x"}:
        return abs(float(x_res))
    return abs(float(y_res))


def _ordered_coord_slice(coord: xr.DataArray, lower: float, upper: float) -> slice:
    """Build a coordinate-aware slice that respects ascending or descending axes."""

    values = np.asarray(coord.values)
    if values.size < 2 or values[0] <= values[-1]:
        return slice(lower, upper)
    return slice(upper, lower)


def _reference_subgrid_for_bbox(
    reference_grid: xr.DataArray,
    bbox: BBox,
) -> xr.DataArray | None:
    """Return the reference-grid subset touched by a lon/lat bbox."""

    y_dim = "lat" if "lat" in reference_grid.coords else "y"
    x_dim = "lon" if "lon" in reference_grid.coords else "x"
    x_step = _reference_grid_axis_step(reference_grid, x_dim)
    y_step = _reference_grid_axis_step(reference_grid, y_dim)
    min_lon, min_lat, max_lon, max_lat = bbox
    subgrid = reference_grid.sel(
        {
            x_dim: _ordered_coord_slice(
                reference_grid.coords[x_dim],
                min_lon - x_step / 2,
                max_lon + x_step / 2,
            ),
            y_dim: _ordered_coord_slice(
                reference_grid.coords[y_dim],
                min_lat - y_step / 2,
                max_lat + y_step / 2,
            ),
        }
    )
    if subgrid.sizes.get(x_dim, 0) == 0 or subgrid.sizes.get(y_dim, 0) == 0:
        return None
    subgrid = subgrid.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=False)
    if reference_grid.rio.crs is not None:
        subgrid = subgrid.rio.write_crs(reference_grid.rio.crs, inplace=False)
    return subgrid


def _grid_bbox(reference_grid: xr.DataArray) -> BBox:
    """Return the coordinate bounds of a reference-grid subset."""

    y_dim = "lat" if "lat" in reference_grid.coords else "y"
    x_dim = "lon" if "lon" in reference_grid.coords else "x"
    lats = np.asarray(reference_grid.coords[y_dim].values, dtype=np.float64)
    lons = np.asarray(reference_grid.coords[x_dim].values, dtype=np.float64)
    return (
        float(np.min(lons)),
        float(np.min(lats)),
        float(np.max(lons)),
        float(np.max(lats)),
    )


def _build_partial_encoding(dataset: xr.Dataset) -> dict[str, dict[str, Any]]:
    """Build compressed netCDF encoding for staged coarse partial files."""

    encoding: dict[str, dict[str, Any]] = {}
    for var_name, data in dataset.data_vars.items():
        chunks: list[int] = []
        for dim in data.dims:
            if dim in {"lat", "lon", "y", "x"}:
                chunks.append(min(256, int(data.sizes[dim])))
            elif dim == "class_id":
                chunks.append(min(15, int(data.sizes[dim])))
            else:
                chunks.append(1)
        encoding[var_name] = {
            "zlib": True,
            "complevel": 4,
            "shuffle": True,
            "chunksizes": tuple(chunks),
        }
    return encoding


def _stage_lock_path(stage_path: Path) -> Path:
    """Return the lock-file path guarding one staged tile output."""

    return stage_path.parent / f".{stage_path.name}.lock"


def _is_stale_stage_lock(lock_path: Path, stale_after_seconds: int) -> bool:
    """Return whether one stage lock is old enough to be treated as stale."""

    try:
        age_seconds = time.time() - lock_path.stat().st_mtime
    except FileNotFoundError:
        return False
    return age_seconds >= stale_after_seconds


def _try_acquire_stage_lock(stage_path: Path) -> Path | None:
    """Try to exclusively claim one staged tile path across processes/nodes."""

    lock_path = _stage_lock_path(stage_path)
    for attempt in range(2):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            break
        except FileExistsError:
            if attempt == 0 and _is_stale_stage_lock(lock_path, _GWD30_STAGE_LOCK_STALE_SECONDS):
                logger.warning("Reclaiming stale GWD30 stage lock %s", lock_path.name)
                lock_path.unlink(missing_ok=True)
                continue
            return None

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()}\n")
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        lock_path.unlink(missing_ok=True)
        raise
    return lock_path


def _time_fraction_partials_to_dataset(
    *,
    weighted: np.ndarray,
    coverage: np.ndarray,
    y_dim: str,
    x_dim: str,
    y_coords: np.ndarray,
    x_coords: np.ndarray,
    year: int,
    time_index: pd.DatetimeIndex,
    source_tile: str,
) -> xr.Dataset:
    """Convert one tile's weighted/coverage partial arrays into a staged dataset."""

    coords = {
        "time": time_index,
        "class_id": np.arange(_GWD30_CLASS_COUNT, dtype=np.int16),
        y_dim: y_coords,
        x_dim: x_coords,
    }
    return xr.Dataset(
        data_vars={
            "weighted": xr.DataArray(
                weighted,
                dims=("time", "class_id", y_dim, x_dim),
                coords=coords,
            ),
            "coverage": xr.DataArray(
                coverage,
                dims=("time", y_dim, x_dim),
                coords={
                    "time": time_index,
                    y_dim: y_coords,
                    x_dim: x_coords,
                },
            ),
        },
        attrs={
            "dataset_id": "gwd30",
            "year": year,
            "source_tile": source_tile,
            "source": "coarse_time_fraction_tile_partial",
        },
    )


def _staged_spatial_dims(data: xr.Dataset | xr.DataArray) -> tuple[str, str]:
    dims = set(data.dims)
    if {"lat", "lon"}.issubset(dims):
        return "lat", "lon"
    if {"y", "x"}.issubset(dims):
        return "y", "x"
    raise ValueError(f"Expected staged tile spatial dims lat/lon or y/x, got {sorted(dims)}")


def phase36_reduce_staged_time_fraction_tile(source: xr.Dataset) -> xr.Dataset:
    """Reduce one staged GWD30 tile to annual unified weighted sums for Phase 3.6."""

    if "weighted" not in source.data_vars or "coverage" not in source.data_vars:
        raise ValueError("Expected staged GWD30 tile dataset with weighted and coverage variables")

    y_dim, x_dim = _staged_spatial_dims(source)
    weighted = np.asarray(source["weighted"].values, dtype=np.float32)
    coverage = np.asarray(source["coverage"].values, dtype=np.float32)
    class_coords = np.asarray(source.coords["class_id"].values, dtype=np.int16)
    class_index_by_id = {int(class_id): index for index, class_id in enumerate(class_coords)}
    unified_ids = np.asarray(unified_class_ids(), dtype=np.int16)
    grouped_source_ids = source_class_ids_by_unified_id("gwd30")
    annual_source_weighted_sum = weighted.sum(axis=0, dtype=np.float32)

    annual_unified_weighted_sum = np.zeros(
        (len(unified_ids), weighted.shape[2], weighted.shape[3]),
        dtype=np.float32,
    )
    for unified_index, unified_id in enumerate(unified_ids):
        source_indices = [
            class_index_by_id[source_id]
            for source_id in grouped_source_ids.get(int(unified_id), ())
            if source_id in class_index_by_id
        ]
        if not source_indices:
            continue
        annual_unified_weighted_sum[unified_index] = weighted[:, source_indices, :, :].sum(
            axis=(0, 1),
            dtype=np.float32,
        )

    annual_coverage_sum = coverage.sum(axis=0, dtype=np.float32)
    reduced = xr.Dataset(
        data_vars={
            "annual_source_weighted_sum": xr.DataArray(
                annual_source_weighted_sum,
                dims=("source_class_id", y_dim, x_dim),
                coords={
                    "source_class_id": class_coords,
                    y_dim: source.coords[y_dim].values,
                    x_dim: source.coords[x_dim].values,
                },
            ),
            "annual_unified_weighted_sum": xr.DataArray(
                annual_unified_weighted_sum,
                dims=("class_id", y_dim, x_dim),
                coords={
                    "class_id": unified_ids,
                    y_dim: source.coords[y_dim].values,
                    x_dim: source.coords[x_dim].values,
                },
            ),
            "annual_coverage_sum": xr.DataArray(
                annual_coverage_sum,
                dims=(y_dim, x_dim),
                coords={
                    y_dim: source.coords[y_dim].values,
                    x_dim: source.coords[x_dim].values,
                },
            ),
        },
        attrs={
            "dataset_id": "gwd30",
            "year": int(source.attrs.get("year", 0)),
            "source": "phase36_annual_unified_weighted_tile",
        },
    )
    return reduced


def _extract_tile_code(path: Path) -> str | None:
    """Extract a GWD30/MGRS-like tile code from a filename."""

    match = _TILE_CODE_PATTERN.search(path.stem.upper())
    if match is None:
        return None
    zone_text, suffix = match.group(1)[:-3], match.group(1)[-3:]
    return f"{int(zone_text):02d}{suffix}"


def _filter_files_by_bounds(files: list[Path], bbox: BBox) -> list[Path]:
    """Slow-path bbox filter using raster bounds converted to WGS84."""

    matched: list[Path] = []
    for file_path in files:
        try:
            with rasterio.open(file_path) as src:
                if src.crs is None:
                    candidate_bounds = cast(BBox, src.bounds)
                elif str(src.crs) == "EPSG:4326":
                    candidate_bounds = cast(BBox, src.bounds)
                else:
                    candidate_bounds = cast(
                        BBox,
                        transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21),
                    )
        except Exception:
            continue

        if _bbox_intersects(candidate_bounds, bbox):
            matched.append(file_path)
    return matched


def _reference_grid_spec(reference_grid: xr.DataArray) -> tuple[str, Any, int, int]:
    """Extract raster-space metadata from the coarse comparison grid."""

    reference_crs = reference_grid.rio.crs
    if reference_crs is None:
        raise ValueError("reference_grid must define a CRS")

    x_dim = "lon" if "lon" in reference_grid.sizes else "x"
    y_dim = "lat" if "lat" in reference_grid.sizes else "y"
    return (
        str(reference_crs),
        reference_grid.rio.transform(),
        int(reference_grid.sizes[x_dim]),
        int(reference_grid.sizes[y_dim]),
    )


def _source_window_for_bbox(src: rasterio.io.DatasetReader, bbox: BBox) -> Window | None:
    """Build the smallest source window intersecting the requested lon/lat bbox."""

    if src.crs is None:
        return Window(0, 0, src.width, src.height)

    if str(src.crs) == "EPSG:4326":
        query_bounds = bbox
    else:
        query_bounds = cast(
            BBox,
            transform_bounds("EPSG:4326", src.crs, *bbox, densify_pts=21),
        )

    left = max(float(src.bounds.left), float(query_bounds[0]))
    bottom = max(float(src.bounds.bottom), float(query_bounds[1]))
    right = min(float(src.bounds.right), float(query_bounds[2]))
    top = min(float(src.bounds.top), float(query_bounds[3]))
    if left >= right or bottom >= top:
        return None

    requested = from_bounds(left, bottom, right, top, transform=src.transform)
    requested = requested.round_offsets().round_lengths()
    full_window = Window(0, 0, src.width, src.height)
    try:
        return requested.intersection(full_window)
    except WindowError:
        return None


def _masked_classes_to_binary_fraction(
    data: np.ma.MaskedArray[Any],
    *,
    lookup: np.ndarray,
) -> np.ndarray:
    """Convert masked GWD30 class codes into a float binary-fraction array."""

    mask = np.ma.getmaskarray(data)
    filled = np.asarray(np.ma.filled(data, 0), dtype=np.int16)
    clipped = np.clip(filled, 0, len(lookup) - 1)
    mapped = lookup[clipped].astype(np.float32, copy=True)
    mapped[mask] = np.nan
    return mapped


def _iter_tiles_with_progress(paths: list[Path], *, desc: str) -> Any:
    """Wrap tile iteration with tqdm for long-running HPC loads."""
    progress = tqdm(
        total=len(paths),
        desc=desc,
        unit="tile",
        dynamic_ncols=True,
        mininterval=5.0,
    )
    try:
        for path in paths:
            progress.set_postfix_str(path.name, refresh=False)
            yield path
            progress.update(1)
    finally:
        progress.close()


def _resolve_parallel_worker_count(worker_count: int | None) -> int:
    """Resolve the desired GWD30 parallel worker count from args or HPC env."""

    if worker_count is not None and worker_count > 0:
        return worker_count

    for env_name in (
        "WA_GWD30_WORKERS",
        "SLURM_CPUS_PER_TASK",
        "OMP_NUM_THREADS",
        "PBS_NUM_PPN",
        "NSLOTS",
    ):
        raw_value = os.environ.get(env_name)
        if raw_value is None:
            continue
        try:
            resolved = int(raw_value.split("(")[0].split(",")[0])
        except ValueError:
            continue
        if resolved > 0:
            return resolved
    try:
        sched_getaffinity = getattr(os, "sched_getaffinity", None)
        affinity_count = len(sched_getaffinity(0)) if sched_getaffinity is not None else 0
    except Exception:
        affinity_count = 0
    if affinity_count > 0:
        return affinity_count
    return max(1, os.cpu_count() or 1)


def _resolve_stage_worker_count(worker_count: int | None, pending_tile_count: int) -> int:
    """Resolve a memory-safe worker count for staged GWD30 tile preprocessing."""

    if pending_tile_count <= 1:
        return pending_tile_count

    if worker_count is not None and worker_count > 0:
        explicit = max(1, min(int(worker_count), pending_tile_count))
        if explicit > _GWD30_STAGE_MAX_WORKERS:
            logger.warning(
                "GWD30 stage worker count explicitly set to %d, above the automatic safe cap %d; "
                "use only when the HPC node has enough memory",
                explicit,
                _GWD30_STAGE_MAX_WORKERS,
            )
        return explicit

    requested = _resolve_parallel_worker_count(worker_count)
    capped = max(1, min(requested, pending_tile_count, _GWD30_STAGE_MAX_WORKERS))
    if capped < requested:
        logger.info(
            "GWD30 stage worker count capped at %d (requested %d) to avoid OOM "
            "from per-tile coarse arrays",
            capped,
            requested,
        )
    return capped


def _normalize_shard_spec(shard_index: int, shard_count: int) -> tuple[int, int]:
    """Validate and normalize a shard spec."""

    if shard_count < 1:
        raise ValueError("shard_count must be >= 1")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard_index must satisfy 0 <= shard_index < shard_count")
    return shard_index, shard_count


def _select_paths_for_shard(
    paths: list[Path],
    *,
    shard_index: int,
    shard_count: int,
) -> list[Path]:
    """Select the deterministic subset of tile paths assigned to one shard."""

    _normalize_shard_spec(shard_index, shard_count)
    if shard_count == 1:
        return paths
    return [path for index, path in enumerate(paths) if index % shard_count == shard_index]


def _project_rough_tile_to_coarse_array(
    *,
    path: str,
    bbox: BBox,
    band_indexes: list[int],
    aggregation: str,
    reference_crs: str,
    reference_transform: Any,
    width: int,
    height: int,
) -> tuple[np.ndarray | None, int]:
    """Read one GWD30 tile, aggregate it, and project it into the coarse grid."""

    with rasterio.open(path) as src:
        window = _source_window_for_bbox(src, bbox)
        if window is None:
            return None, 0
        source_height = int(window.height)
        source_width = int(window.width)
        if source_height <= 0 or source_width <= 0:
            return None, 0
        source_transform = src.window_transform(window)

        if aggregation == "max":
            source_monthly = np.full((source_height, source_width), np.nan, dtype=np.float32)
        else:
            source_sum = np.zeros((source_height, source_width), dtype=np.float32)
            source_count = np.zeros((source_height, source_width), dtype=np.uint8)

        for band_index in band_indexes:
            band = src.read(band_index + 1, window=window, masked=True)
            if band.size == 0:
                continue
            mapped = _masked_classes_to_binary_fraction(
                band,
                lookup=_GWD30_BINARY_LOOKUP,
            )
            valid = np.isfinite(mapped)
            if aggregation == "max":
                source_monthly = np.where(
                    valid,
                    np.where(
                        np.isnan(source_monthly),
                        mapped,
                        np.maximum(source_monthly, mapped),
                    ),
                    source_monthly,
                )
            else:
                source_sum[valid] = source_sum[valid] + mapped[valid]
                source_count[valid] = source_count[valid] + 1

        if aggregation != "max":
            source_monthly = np.full((source_height, source_width), np.nan, dtype=np.float32)
            valid_counts = source_count > 0
            source_monthly[valid_counts] = source_sum[valid_counts] / source_count[valid_counts]

        if not np.isfinite(source_monthly).any():
            return None, 0

        coarse = np.full((height, width), np.nan, dtype=np.float32)
        reproject(
            source=source_monthly,
            destination=coarse,
            src_transform=source_transform,
            src_crs=src.crs,
            dst_transform=reference_transform,
            dst_crs=reference_crs,
            src_nodata=np.nan,
            dst_nodata=np.nan,
            resampling=Resampling.average,
        )

    coarse_non_null_count = int(np.count_nonzero(np.isfinite(coarse)))
    if coarse_non_null_count == 0:
        return None, 0
    return coarse, coarse_non_null_count


def _process_rough_tile_to_partial(
    *,
    path: str,
    bbox: BBox,
    band_indexes: list[int],
    aggregation: str,
    reference_crs: str,
    reference_transform: Any,
    width: int,
    height: int,
) -> tuple[np.ndarray | None, np.ndarray | None, int]:
    """Project one GWD30 tile and return partial sum/count coarse arrays."""

    coarse, coarse_non_null_count = _project_rough_tile_to_coarse_array(
        path=path,
        bbox=bbox,
        band_indexes=band_indexes,
        aggregation=aggregation,
        reference_crs=reference_crs,
        reference_transform=reference_transform,
        width=width,
        height=height,
    )
    if coarse is None:
        return None, None, 0

    valid = np.isfinite(coarse)
    tile_sum = np.where(valid, coarse, 0.0).astype(np.float32)
    tile_count = valid.astype(np.uint8)
    return tile_sum, tile_count, coarse_non_null_count


def _process_fine_tile_to_fractions(
    *,
    path: str,
    bbox: BBox,
    reference_crs: str,
    reference_transform: Any,
    width: int,
    height: int,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Project one GWD30 tile into coarse-grid class fractions.

    The workflow mirrors the Phase 3 HPC probe:
      1. windowed band-by-band read inside ``bbox``
      2. per-pixel temporal mode at native 30m resolution
      3. per-class binary-mask averaging into ``reference_grid``

    Returns
    -------
    tuple[np.ndarray | None, np.ndarray | None]
        ``(fractions, valid_mask)`` where fractions has shape
        ``(class_id, lat, lon)`` and valid_mask marks coarse cells touched by
        this tile. ``None`` is returned when the tile contributes no data.
    """

    with rasterio.open(path) as src:
        window = _source_window_for_bbox(src, bbox)
        if window is None:
            return None, None

        source_height = int(window.height)
        source_width = int(window.width)
        if source_height <= 0 or source_width <= 0:
            return None, None

        source_transform = src.window_transform(window)
        source_crs = src.crs
        if source_crs is None:
            return None, None

        counts = np.zeros(
            (_GWD30_CLASS_COUNT, source_height, source_width),
            dtype=np.int16,
        )
        has_data = np.zeros((source_height, source_width), dtype=bool)

        for band_index in range(1, src.count + 1):
            band = src.read(band_index, window=window, masked=True)
            if band.size == 0:
                continue

            band_mask = np.ma.getmaskarray(band)
            valid = ~band_mask
            if not np.any(valid):
                continue

            has_data |= valid
            safe = np.clip(
                np.asarray(np.ma.filled(band, 0), dtype=np.int16),
                0,
                _GWD30_CLASS_COUNT - 1,
            )
            for class_id in range(_GWD30_CLASS_COUNT):
                counts[class_id] += safe == class_id

        if not np.any(has_data):
            return None, None

        mode_30m = counts.argmax(axis=0).astype(np.float32)
        mode_30m[~has_data] = np.nan
        del counts

        fractions = np.zeros((_GWD30_CLASS_COUNT, height, width), dtype=np.float32)
        for class_id in range(_GWD30_CLASS_COUNT):
            binary = np.where(mode_30m == class_id, 1.0, 0.0).astype(np.float32)
            binary[~has_data] = np.nan
            coarse = np.full((height, width), np.nan, dtype=np.float32)
            reproject(
                source=binary,
                destination=coarse,
                src_transform=source_transform,
                src_crs=source_crs,
                dst_transform=reference_transform,
                dst_crs=reference_crs,
                src_nodata=np.nan,
                dst_nodata=np.nan,
                resampling=Resampling.average,
            )
            fractions[class_id] = np.where(np.isfinite(coarse), coarse, 0.0)

        valid_mask = fractions.sum(axis=0) > 0
        if not np.any(valid_mask):
            return None, None

        return fractions, valid_mask


def _process_time_fraction_tile_to_partial(
    *,
    path: str,
    bbox: BBox,
    reference_crs: str,
    reference_transform: Any,
    width: int,
    height: int,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Project one GWD30 tile into coarse-grid time-resolved class fractions.

    Returns
    -------
    tuple[np.ndarray | None, np.ndarray | None]
        ``(weighted_fractions, coverage)`` where:
        - ``weighted_fractions`` has shape ``(time, class_id, lat, lon)``
          and stores ``class_fraction * valid_coverage`` for one tile
        - ``coverage`` has shape ``(time, lat, lon)`` and stores the fraction
          of each coarse cell covered by valid source pixels from this tile
    """

    with rasterio.open(path) as src:
        window = _source_window_for_bbox(src, bbox)
        if window is None:
            return None, None

        source_height = int(window.height)
        source_width = int(window.width)
        if source_height <= 0 or source_width <= 0:
            return None, None

        source_transform = src.window_transform(window)
        source_crs = src.crs
        if source_crs is None:
            return None, None

        weighted = np.zeros((src.count, _GWD30_CLASS_COUNT, height, width), dtype=np.float32)
        coverage = np.zeros((src.count, height, width), dtype=np.float32)

        for band_index in range(1, src.count + 1):
            band = src.read(band_index, window=window, masked=True)
            if band.size == 0:
                continue

            band_mask = np.ma.getmaskarray(band)
            valid = ~band_mask
            if not np.any(valid):
                continue

            source_coverage = np.where(valid, 1.0, np.nan).astype(np.float32)
            coarse_coverage = np.full((height, width), np.nan, dtype=np.float32)
            reproject(
                source=source_coverage,
                destination=coarse_coverage,
                src_transform=source_transform,
                src_crs=source_crs,
                dst_transform=reference_transform,
                dst_crs=reference_crs,
                src_nodata=np.nan,
                dst_nodata=np.nan,
                resampling=Resampling.average,
            )
            coarse_coverage = np.where(np.isfinite(coarse_coverage), coarse_coverage, 0.0)
            if not np.any(coarse_coverage > 0):
                continue
            coverage[band_index - 1] = coarse_coverage

            safe = np.clip(
                np.asarray(np.ma.filled(band, 0), dtype=np.int16),
                0,
                _GWD30_CLASS_COUNT - 1,
            )
            for class_id in range(_GWD30_CLASS_COUNT):
                binary = np.where(valid & (safe == class_id), 1.0, 0.0).astype(np.float32)
                binary[~valid] = np.nan
                coarse = np.full((height, width), np.nan, dtype=np.float32)
                reproject(
                    source=binary,
                    destination=coarse,
                    src_transform=source_transform,
                    src_crs=source_crs,
                    dst_transform=reference_transform,
                    dst_crs=reference_crs,
                    src_nodata=np.nan,
                    dst_nodata=np.nan,
                    resampling=Resampling.average,
                )
                weighted[band_index - 1, class_id] = np.where(
                    np.isfinite(coarse),
                    coarse * coarse_coverage,
                    0.0,
                )

    if not np.any(coverage > 0):
        return None, None
    return weighted, coverage


def _process_time_fraction_tile_to_stage_file(
    *,
    path: str,
    stage_path: str,
    manifest_bbox: BBox,
    stage_bbox: BBox,
    reference_crs: str,
    reference_transform: Any,
    width: int,
    height: int,
    y_dim: str,
    x_dim: str,
    y_coords: np.ndarray,
    x_coords: np.ndarray,
    year: int,
    time_index: pd.DatetimeIndex,
) -> tuple[Path, BBox] | None:
    """Process one tile and write its staged coarse partial directly to disk."""

    stage_path_obj = Path(stage_path)
    if stage_path_obj.exists():
        return stage_path_obj, manifest_bbox

    lock_path = _try_acquire_stage_lock(stage_path_obj)
    if lock_path is None:
        if stage_path_obj.exists():
            return stage_path_obj, manifest_bbox
        logger.info("GWD30 staged tile already claimed elsewhere, skipping %s", stage_path_obj.name)
        return None
    try:
        weighted, coverage = _process_time_fraction_tile_to_partial(
            path=path,
            bbox=stage_bbox,
            reference_crs=reference_crs,
            reference_transform=reference_transform,
            width=width,
            height=height,
        )
        if weighted is None or coverage is None:
            return None

        dataset = _time_fraction_partials_to_dataset(
            weighted=weighted,
            coverage=coverage,
            y_dim=y_dim,
            x_dim=x_dim,
            y_coords=y_coords,
            x_coords=x_coords,
            year=year,
            time_index=time_index,
            source_tile=Path(path).name,
        )
        temp_stage_path = stage_path_obj.parent / (
            f".{stage_path_obj.name}.tmp-{os.getpid()}-{uuid4().hex}"
        )
        try:
            dataset.to_netcdf(
                temp_stage_path,
                format="NETCDF4",
                engine="netcdf4",
                encoding=_build_partial_encoding(dataset),
            )
            os.replace(temp_stage_path, stage_path_obj)
        finally:
            dataset.close()
            temp_stage_path.unlink(missing_ok=True)
    finally:
        lock_path.unlink(missing_ok=True)
    return stage_path_obj, manifest_bbox


def _stage_file_signature(stage_path: Path) -> tuple[int, int]:
    """Return one compact signature for a staged tile file."""

    stat = stage_path.stat()
    return int(stat.st_size), int(stat.st_mtime_ns)


def _transformed_tile_cache_is_current(
    *,
    output_path: Path,
    stage_path: Path,
    transform_name: str,
    transform_version: int,
) -> bool:
    """Return whether one transformed tile still matches its staged source."""

    if not output_path.is_file() or not stage_path.is_file():
        return False

    stage_size, stage_mtime_ns = _stage_file_signature(stage_path)
    try:
        with xr.open_dataset(output_path, engine="netcdf4") as cached:
            attrs = dict(cached.attrs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ignoring unreadable transformed GWD30 tile %s: %s", output_path, exc)
        return False

    if str(attrs.get("transform_name", "")) != transform_name:
        return False
    if int(attrs.get("transform_version", -1)) != int(transform_version):
        return False
    if str(attrs.get("source_stage_path", "")) != str(stage_path):
        return False
    if int(attrs.get("source_stage_size", -1)) != stage_size:
        return False
    if int(attrs.get("source_stage_mtime_ns", -1)) != stage_mtime_ns:
        return False
    return True


def _transform_staged_time_fraction_tile_to_file(
    *,
    stage_path: str,
    output_path: str,
    manifest_bbox: BBox,
    transform_name: str,
    transform_version: int,
    transform_tile: StagedTileTransform,
) -> tuple[Path, BBox] | None:
    """Load one staged tile netCDF, transform it, and write one reduced tile netCDF."""

    stage_path_obj = Path(stage_path)
    output_path_obj = Path(output_path)
    if output_path_obj.exists():
        return output_path_obj, manifest_bbox

    lock_path = _try_acquire_stage_lock(output_path_obj)
    if lock_path is None:
        if output_path_obj.exists():
            return output_path_obj, manifest_bbox
        logger.info(
            "GWD30 transformed tile already claimed elsewhere, skipping %s",
            output_path_obj.name,
        )
        return None
    try:
        with xr.open_dataset(stage_path, engine="netcdf4") as source:
            transformed = transform_tile(source.load())
        stage_size, stage_mtime_ns = _stage_file_signature(stage_path_obj)
        transformed.attrs.update(
            {
                "transform_name": transform_name,
                "transform_version": int(transform_version),
                "source_stage_path": str(stage_path_obj),
                "source_stage_size": stage_size,
                "source_stage_mtime_ns": stage_mtime_ns,
            }
        )
        temp_output_path = output_path_obj.parent / (
            f".{output_path_obj.name}.tmp-{os.getpid()}-{uuid4().hex}"
        )
        try:
            transformed.to_netcdf(
                temp_output_path,
                format="NETCDF4",
                engine="netcdf4",
                encoding=_build_partial_encoding(transformed),
            )
            os.replace(temp_output_path, output_path_obj)
        finally:
            transformed.close()
            temp_output_path.unlink(missing_ok=True)
    finally:
        lock_path.unlink(missing_ok=True)
    return output_path_obj, manifest_bbox


def _reproject_tile_bands_to_grid(
    *,
    path: str,
    bbox: BBox,
    band_indexes: list[int] | None,
    reference_crs: str,
    reference_transform: Any,
    width: int,
    height: int,
) -> np.ndarray | None:
    """Reproject selected bands of one GWD30 tile onto the coarse reference grid.

    Returns an array of shape ``(n_bands, height, width)`` containing class
    codes (``Resampling.mode``), or ``None`` when the tile contributes no data.
    """

    with rasterio.open(path) as src:
        window = _source_window_for_bbox(src, bbox)
        if window is None:
            return None
        source_height = int(window.height)
        source_width = int(window.width)
        if source_height <= 0 or source_width <= 0:
            return None
        source_transform = src.window_transform(window)
        source_crs = src.crs
        if source_crs is None:
            return None

        if band_indexes is None:
            band_list = list(range(src.count))
        else:
            band_list = band_indexes

        result = np.full((len(band_list), height, width), np.nan, dtype=np.float32)
        for out_idx, band_idx in enumerate(band_list):
            band = src.read(band_idx + 1, window=window, masked=True)
            if band.size == 0:
                continue
            source_data = np.asarray(
                np.ma.filled(band, -1), dtype=np.float32
            )
            dst = np.full((height, width), np.nan, dtype=np.float32)
            reproject(
                source=source_data,
                destination=dst,
                src_transform=source_transform,
                src_crs=source_crs,
                dst_transform=reference_transform,
                dst_crs=reference_crs,
                src_nodata=-1.0,
                dst_nodata=np.nan,
                resampling=Resampling.mode,
            )
            result[out_idx] = dst

    if not np.isfinite(result).any():
        return None
    return result


@register_loader("gwd30")
class GWD30Loader(DatasetLoader):
    """Load annual GWD30 tiles and merge them into year-wise mosaics."""

    def __init__(self, dataset_id: str, config: dict[str, object]) -> None:
        super().__init__(dataset_id, config)
        self._tiling = GWD30TilingSystem()
        self._discover_tiles_cache: dict[
            tuple[BBox | None, TimeRange | None],
            dict[int, list[Path]],
        ] = {}
        self._tile_bbox_cache: dict[Path, BBox | None] = {}
        self._merge_index_cache: dict[
            int,
            tuple[dict[tuple[int, int], list[tuple[Path, BBox]]], float],
        ] = {}

    def metadata(self) -> DatasetMetadata:
        return DatasetMetadata(
            dataset_id=self.dataset_id,
            name=self.name,
            source_path=str(self.base_path),
            crs="EPSG:4326",
            spatial_resolution=self.config.get("resolution"),
            temporal_coverage=self.temporal_coverage(),
            time_resolution=self.config.get("time_resolution", "4-day"),
            is_static=False,
            is_classification=True,
            native_variables=("wetland_class",),
            semantic_mapping={"wetland_class": "gwd30_native_class_code"},
        )

    def load(
        self,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
        *,
        reference_grid: xr.DataArray | None = None,
    ) -> xr.Dataset:
        if reference_grid is not None:
            validate_reference_grid(reference_grid)
            return self._load_to_reference_grid(
                bbox=bbox,
                time_range=time_range,
                reference_grid=reference_grid,
            )

        # Legacy full-resolution mosaic path – warn about OOM risk.
        warnings.warn(
            "GWD30Loader.load() without reference_grid materialises the full "
            "30 m mosaic in memory and may OOM for large bounding boxes. "
            "Pass a reference_grid to use the memory-efficient path.",
            stacklevel=2,
        )
        return self._load_native(bbox=bbox, time_range=time_range)

    # ------------------------------------------------------------------
    # Private helpers for the two load() paths
    # ------------------------------------------------------------------

    def _load_native(
        self,
        *,
        bbox: BBox | None,
        time_range: TimeRange | None,
    ) -> xr.Dataset:
        """Legacy full-resolution mosaic path (kept for backward compat)."""

        tiles_by_year = self._discover_tiles(bbox=bbox, time_range=time_range)
        if not tiles_by_year:
            raise FileNotFoundError(f"No GWD30 tiles found under {self.base_path}")

        year_datasets: list[xr.Dataset] = []
        for year, paths in sorted(tiles_by_year.items()):
            if not paths:
                continue
            logger.debug("GWD30 loading year %s with %s tile(s)", year, len(paths))
            band_indexes: list[int] | None = None
            selected_times: list[pd.Timestamp] | None = None
            if time_range is not None:
                band_indexes, selected_times = self._selected_band_window(
                    year,
                    paths[0],
                    time_range=time_range,
                )
                if not band_indexes:
                    continue
            mosaics = [
                open_multiband_raster(
                    path,
                    reproject_to_wgs84=True,
                    bbox=bbox,
                    band_indexes=band_indexes,
                )
                for path in _iter_tiles_with_progress(paths, desc=f"GWD30 {year} load")
            ]
            merged = merge_rasters(mosaics)
            if selected_times is None:
                time_index = four_day_index_for_year(year, merged.sizes["band"])
            else:
                time_index = pd.DatetimeIndex(selected_times)
            merged = merged.assign_coords(band=time_index).rename({"band": "time"})
            year_datasets.append(merged.rename("wetland_class").to_dataset())

        if not year_datasets:
            raise FileNotFoundError(
                f"No GWD30 tiles found under {self.base_path} for requested time window"
            )

        dataset = xr.concat(year_datasets, dim="time").sortby("time")
        dataset = ensure_datetime_index(dataset)
        return self.finalize_dataset(dataset, bbox=bbox, time_range=time_range)

    def _load_to_reference_grid(
        self,
        *,
        bbox: BBox | None,
        time_range: TimeRange | None,
        reference_grid: xr.DataArray,
    ) -> xr.Dataset:
        """Memory-efficient path: reproject each tile onto the reference grid."""

        from WA.loaders.base import _bbox_from_reference_grid

        if bbox is None:
            bbox = _bbox_from_reference_grid(reference_grid)

        tiles_by_year = self._discover_tiles(bbox=bbox, time_range=time_range)
        if not tiles_by_year:
            raise FileNotFoundError(f"No GWD30 tiles found under {self.base_path}")

        reference_crs, reference_transform, width, height = _reference_grid_spec(
            reference_grid,
        )

        year_datasets: list[xr.Dataset] = []
        for year, paths in sorted(tiles_by_year.items()):
            if not paths:
                continue
            logger.debug(
                "GWD30 loading year %s with %s tile(s) [reference_grid]",
                year,
                len(paths),
            )

            band_indexes: list[int] | None = None
            selected_times: list[pd.Timestamp] | None = None
            if time_range is not None:
                band_indexes, selected_times = self._selected_band_window(
                    year,
                    paths[0],
                    time_range=time_range,
                )
                if not band_indexes:
                    continue

            # Determine the number of bands we expect.
            if band_indexes is not None:
                n_bands = len(band_indexes)
            else:
                with rasterio.open(paths[0]) as sample:
                    n_bands = int(sample.count)

            # Accumulate tiles onto the coarse grid (first-valid wins).
            merged = np.full((n_bands, height, width), np.nan, dtype=np.float32)
            for tile_path in _iter_tiles_with_progress(
                paths, desc=f"GWD30 {year} grid-load"
            ):
                tile_data = _reproject_tile_bands_to_grid(
                    path=str(tile_path),
                    bbox=bbox,
                    band_indexes=band_indexes,
                    reference_crs=reference_crs,
                    reference_transform=reference_transform,
                    width=width,
                    height=height,
                )
                if tile_data is None:
                    continue
                # Fill only pixels that are still NaN.
                for b in range(n_bands):
                    fill_mask = np.isnan(merged[b]) & np.isfinite(tile_data[b])
                    merged[b][fill_mask] = tile_data[b][fill_mask]
                del tile_data
                gc.collect()

            # Build time coordinate.
            if selected_times is None:
                time_index = four_day_index_for_year(year, n_bands)
            else:
                time_index = pd.DatetimeIndex(selected_times)

            x_dim = "lon" if "lon" in reference_grid.coords else "x"
            y_dim = "lat" if "lat" in reference_grid.coords else "y"
            da = xr.DataArray(
                merged,
                dims=("time", y_dim, x_dim),
                coords={
                    "time": time_index,
                    y_dim: reference_grid.coords[y_dim].values,
                    x_dim: reference_grid.coords[x_dim].values,
                },
                name="wetland_class",
            )
            year_datasets.append(da.to_dataset())

        if not year_datasets:
            raise FileNotFoundError(
                f"No GWD30 tiles found under {self.base_path} for requested time window"
            )

        dataset = xr.concat(year_datasets, dim="time").sortby("time")
        dataset = ensure_datetime_index(dataset)
        return self.finalize_dataset(
            dataset,
            bbox=bbox,
            time_range=time_range,
            reference_grid=reference_grid,
        )

    def load_fine_classification_grid(
        self,
        *,
        bbox: BBox,
        reference_grid: xr.DataArray,
        year: int,
        worker_count: int | None = None,
    ) -> xr.Dataset:
        """Load one GWD30 year into a coarse classification grid.

        This avoids materializing the full 30m × 92-band annual mosaic in
        memory. The returned dataset contains:
        - ``wetland_class``: dominant raw GWD30 class per coarse cell
        - ``class_fractions``: raw class fractions (0-14) per coarse cell
        """

        time_range = (f"{year}-01-01", f"{year}-12-31")
        tiles_by_year = self._discover_tiles(bbox=bbox, time_range=time_range)
        paths = list(tiles_by_year.get(year, []))
        if not paths:
            raise FileNotFoundError(f"No GWD30 tiles found under {self.base_path} for year {year}")

        reference_crs, reference_transform, width, height = _reference_grid_spec(reference_grid)
        resolved_worker_count = _resolve_parallel_worker_count(worker_count)
        all_fractions = np.zeros((_GWD30_CLASS_COUNT, height, width), dtype=np.float32)
        covered = np.zeros((height, width), dtype=bool)

        def accumulate_tile(tile_path: Path) -> None:
            fractions, valid_mask = _process_fine_tile_to_fractions(
                path=str(tile_path),
                bbox=bbox,
                reference_crs=reference_crs,
                reference_transform=reference_transform,
                width=width,
                height=height,
            )
            if fractions is None or valid_mask is None:
                return
            new = valid_mask & ~covered
            all_fractions[:, new] = fractions[:, new]
            covered[:] = covered | valid_mask

        if resolved_worker_count > 1 and len(paths) > 1:
            fallback_to_serial = False
            processed_indices: set[int] = set()
            progress = tqdm(
                total=len(paths),
                desc=f"GWD30 {year} fine-parallel",
                unit="tile",
                dynamic_ncols=True,
                mininterval=5.0,
            )
            try:
                try:
                    with ProcessPoolExecutor(
                        max_workers=resolved_worker_count,
                        max_tasks_per_child=1,
                    ) as executor:
                        future_to_meta = {
                            executor.submit(
                                _process_fine_tile_to_fractions,
                                path=str(path),
                                bbox=bbox,
                                reference_crs=reference_crs,
                                reference_transform=reference_transform,
                                width=width,
                                height=height,
                            ): (index, path)
                            for index, path in enumerate(paths)
                        }
                        for future in as_completed(future_to_meta):
                            index, _path = future_to_meta[future]
                            try:
                                fractions, valid_mask = future.result()
                                processed_indices.add(index)
                                if fractions is not None and valid_mask is not None:
                                    new = valid_mask & ~covered
                                    all_fractions[:, new] = fractions[:, new]
                                    covered[:] = covered | valid_mask
                                progress.update(1)
                            except BrokenProcessPool:
                                fallback_to_serial = True
                                break
                            except Exception as exc:
                                logger.warning(
                                    "GWD30 tile %s skipped during fine parallel reduction (%s: %s)",
                                    paths[index].name,
                                    type(exc).__name__,
                                    exc,
                                )
                                processed_indices.add(index)
                                progress.update(1)
                except Exception as pool_exc:
                    logger.warning(
                        "GWD30 fine parallel execution failed (%s: %s); will retry serially",
                        type(pool_exc).__name__,
                        pool_exc,
                    )
                    fallback_to_serial = True

                if fallback_to_serial:
                    remaining = [
                        index for index in range(len(paths))
                        if index not in processed_indices
                    ]
                    logger.warning(
                        "GWD30 fine parallel failed after %d/%d tiles; "
                        "falling back to serial for %d remaining",
                        len(processed_indices),
                        len(paths),
                        len(remaining),
                    )
                    for index in remaining:
                        try:
                            accumulate_tile(paths[index])
                        except Exception as exc:
                            logger.warning(
                                "GWD30 tile %s failed during fine serial fallback (%s: %s)",
                                paths[index].name,
                                type(exc).__name__,
                                exc,
                            )
                        progress.update(1)
            finally:
                progress.close()
        else:
            for path in _iter_tiles_with_progress(paths, desc=f"GWD30 {year} fine"):
                accumulate_tile(path)

        dominant = all_fractions.argmax(axis=0).astype(np.float32)
        dominant[~covered] = np.nan

        data_vars = {
            "wetland_class": reference_grid.copy(data=dominant),
            "class_fractions": xr.DataArray(
                all_fractions,
                dims=("class_id", "lat", "lon"),
                coords={
                    "class_id": np.arange(_GWD30_CLASS_COUNT, dtype=np.int16),
                    "lat": reference_grid.coords["lat"].values,
                    "lon": reference_grid.coords["lon"].values,
                },
                attrs={"description": "GWD30 raw class fractions on coarse grid"},
            ),
        }
        dataset = xr.Dataset(data_vars)
        dataset["wetland_class"] = dataset["wetland_class"].rio.write_crs(reference_crs)
        dataset["wetland_class"] = dataset["wetland_class"].rio.set_spatial_dims(
            x_dim="lon",
            y_dim="lat",
        )
        dataset["class_fractions"].attrs.update(
            {"dataset_id": self.dataset_id, "year": year, "source": "low_memory_fine_grid"}
        )
        dataset["wetland_class"].attrs.update(
            {"dataset_id": self.dataset_id, "year": year, "source": "low_memory_fine_grid"}
        )
        return dataset

    def load_time_fraction_grid(
        self,
        *,
        bbox: BBox,
        reference_grid: xr.DataArray,
        year: int,
        worker_count: int | None = None,
        show_progress: bool = True,
    ) -> xr.Dataset:
        """Load one GWD30 year into coarse, time-resolved per-class fractions.

        The returned dataset contains ``frac_0`` ... ``frac_14`` variables with
        dimensions ``(time, lat, lon)`` (or ``time, y, x`` when the reference
        grid uses projected spatial dimension names).
        """

        time_range = (f"{year}-01-01", f"{year}-12-31")
        tiles_by_year = self._discover_tiles(bbox=bbox, time_range=time_range)
        paths = list(tiles_by_year.get(year, []))
        if not paths:
            raise FileNotFoundError(f"No GWD30 tiles found under {self.base_path} for year {year}")

        reference_crs, reference_transform, width, height = _reference_grid_spec(reference_grid)
        resolved_worker_count = _resolve_parallel_worker_count(worker_count)
        y_dim = "lat" if "lat" in reference_grid.coords else "y"
        x_dim = "lon" if "lon" in reference_grid.coords else "x"

        if not show_progress:
            logger.info(
                "GWD30 %s: chunk bbox=%s matched %d tile(s), worker_count=%d",
                year,
                bbox,
                len(paths),
                resolved_worker_count,
            )

        with rasterio.open(paths[0]) as sample:
            band_count = int(sample.count)
        time_index = four_day_index_for_year(year, band_count)

        weighted_sum = np.zeros(
            (band_count, _GWD30_CLASS_COUNT, height, width),
            dtype=np.float32,
        )
        coverage_sum = np.zeros((band_count, height, width), dtype=np.float32)

        def accumulate_partial(
            weighted: np.ndarray | None,
            coverage: np.ndarray | None,
        ) -> None:
            if weighted is None or coverage is None:
                return
            weighted_sum[...] += weighted
            coverage_sum[...] += coverage

        def process_tile(tile_path: Path) -> tuple[np.ndarray | None, np.ndarray | None]:
            return _process_time_fraction_tile_to_partial(
                path=str(tile_path),
                bbox=bbox,
                reference_crs=reference_crs,
                reference_transform=reference_transform,
                width=width,
                height=height,
            )

        if resolved_worker_count > 1 and len(paths) > 1:
            fallback_to_serial = False
            processed_indices: set[int] = set()
            progress = (
                tqdm(
                    total=len(paths),
                    desc=f"GWD30 {year} time-frac-parallel",
                    unit="tile",
                    dynamic_ncols=True,
                    mininterval=5.0,
                )
                if show_progress
                else None
            )
            try:
                try:
                    with ProcessPoolExecutor(
                        max_workers=resolved_worker_count,
                        max_tasks_per_child=1,
                    ) as executor:
                        future_to_meta = {
                            executor.submit(
                                _process_time_fraction_tile_to_partial,
                                path=str(path),
                                bbox=bbox,
                                reference_crs=reference_crs,
                                reference_transform=reference_transform,
                                width=width,
                                height=height,
                            ): (index, path)
                            for index, path in enumerate(paths)
                        }
                        for future in as_completed(future_to_meta):
                            index, path = future_to_meta[future]
                            if progress is not None:
                                progress.set_postfix_str(path.name, refresh=False)
                            try:
                                weighted, coverage = future.result()
                                processed_indices.add(index)
                                accumulate_partial(weighted, coverage)
                                if progress is not None:
                                    progress.update(1)
                            except BrokenProcessPool:
                                fallback_to_serial = True
                                break
                            except Exception as exc:
                                logger.warning(
                                    "GWD30 tile %s skipped during time-fraction "
                                    "parallel reduction (%s: %s)",
                                    path.name,
                                    type(exc).__name__,
                                    exc,
                                )
                                processed_indices.add(index)
                                if progress is not None:
                                    progress.update(1)
                except Exception as pool_exc:
                    logger.warning(
                        "GWD30 time-fraction parallel execution failed "
                        "(%s: %s); will retry serially",
                        type(pool_exc).__name__,
                        pool_exc,
                    )
                    fallback_to_serial = True

                if fallback_to_serial:
                    remaining = [
                        index for index in range(len(paths))
                        if index not in processed_indices
                    ]
                    logger.warning(
                        "GWD30 time-fraction parallel failed after %d/%d tiles; "
                        "falling back to serial for %d remaining",
                        len(processed_indices),
                        len(paths),
                        len(remaining),
                    )
                    for index in remaining:
                        path = paths[index]
                        if progress is not None:
                            progress.set_postfix_str(path.name, refresh=False)
                        try:
                            weighted, coverage = process_tile(path)
                            accumulate_partial(weighted, coverage)
                        except Exception as exc:
                            logger.warning(
                                "GWD30 tile %s failed during time-fraction "
                                "serial fallback (%s: %s)",
                                path.name,
                                type(exc).__name__,
                                exc,
                            )
                        if progress is not None:
                            progress.update(1)
            finally:
                if progress is not None:
                    progress.close()
        else:
            iter_paths = (
                _iter_tiles_with_progress(paths, desc=f"GWD30 {year} time-frac")
                if show_progress
                else paths
            )
            for index, path in enumerate(iter_paths, start=1):
                if not show_progress and (
                    index == 1 or index == len(paths) or index % 8 == 0
                ):
                    logger.info(
                        "GWD30 %s: reading tile %d/%d | %s",
                        year,
                        index,
                        len(paths),
                        path.name,
                    )
                weighted, coverage = process_tile(path)
                accumulate_partial(weighted, coverage)

        coverage = coverage_sum[:, None, :, :]
        if not np.any(coverage > 0):
            raise FileNotFoundError(
                "GWD30 tiles found under "
                f"{self.base_path} for year {year} but none intersected {bbox}"
            )

        fractions = np.full_like(weighted_sum, np.nan)
        np.divide(
            weighted_sum,
            coverage,
            out=fractions,
            where=coverage > 0,
        )
        fractions = np.clip(fractions, 0.0, 1.0)

        coords = {
            "time": time_index,
            y_dim: reference_grid.coords[y_dim].values,
            x_dim: reference_grid.coords[x_dim].values,
        }
        data_vars = {
            f"frac_{class_id}": xr.DataArray(
                fractions[:, class_id],
                dims=("time", y_dim, x_dim),
                coords=coords,
                attrs={
                    "dataset_id": self.dataset_id,
                    "year": year,
                    "source": "low_memory_time_fraction_grid",
                    "description": f"GWD30 raw class-{class_id} fraction on coarse grid",
                },
            )
            for class_id in range(_GWD30_CLASS_COUNT)
        }
        dataset = xr.Dataset(data_vars)
        dataset = self.finalize_dataset(
            dataset,
            bbox=bbox,
            time_range=time_range,
            reference_grid=reference_grid,
        )
        dataset.attrs.update({"year": year, "source": "low_memory_time_fraction_grid"})
        return dataset

    def stage_time_fraction_tiles(
        self,
        *,
        bbox: BBox,
        reference_grid: xr.DataArray,
        year: int,
        staging_dir: Path,
        worker_count: int | None = None,
        show_progress: bool = True,
        skip_existing: bool = False,
        shard_index: int | None = None,
        shard_count: int | None = None,
    ) -> list[tuple[Path, BBox]]:
        """Preprocess each source TIFF into one coarse local partial file.

        Each staged file stores:
        - ``weighted``: ``class_fraction * valid_coverage`` on the tile's local coarse grid
        - ``coverage``: valid coarse coverage per timestep on the same local grid
        """

        time_range = (f"{year}-01-01", f"{year}-12-31")
        logger.info("GWD30 %s: discovering source tiles for bbox=%s", year, bbox)
        tiles_by_year = self._discover_tiles(bbox=bbox, time_range=time_range)
        paths = list(tiles_by_year.get(year, []))
        if not paths:
            raise FileNotFoundError(f"No GWD30 tiles found under {self.base_path} for year {year}")
        logger.info("GWD30 %s: %d source tile(s) matched after filtering", year, len(paths))

        if shard_index is not None or shard_count is not None:
            if shard_index is None or shard_count is None:
                raise ValueError("shard_index and shard_count must be provided together")
            shard_index, shard_count = _normalize_shard_spec(shard_index, shard_count)
            total_paths = len(paths)
            paths = _select_paths_for_shard(
                paths,
                shard_index=shard_index,
                shard_count=shard_count,
            )
            logger.info(
                "GWD30 %s: shard %d/%d assigned %d/%d source tile(s)",
                year,
                shard_index + 1,
                shard_count,
                len(paths),
                total_paths,
            )
            if not paths:
                return []

        staging_dir.mkdir(parents=True, exist_ok=True)

        with rasterio.open(paths[0]) as sample:
            time_index = four_day_index_for_year(year, int(sample.count))

        reusable_stage_paths: list[tuple[Path, BBox]] = []
        pending_specs: list[dict[str, Any]] = []
        planning_iterable = (
            _iter_tiles_with_progress(paths, desc=f"GWD30 {year} plan")
            if show_progress and len(paths) > 1
            else paths
        )
        for path in planning_iterable:
            tile_bounds = self._tile_bounds_for_stage(path)
            if tile_bounds is None:
                continue
            stage_bbox = _bbox_intersection(tile_bounds, bbox)
            if stage_bbox is None:
                continue
            stage_grid = _reference_subgrid_for_bbox(reference_grid, stage_bbox)
            if stage_grid is None:
                continue

            stage_path = staging_dir / f"tile_{path.stem}.nc"
            manifest_bbox = _grid_bbox(stage_grid)
            if skip_existing and stage_path.exists():
                reusable_stage_paths.append((stage_path, manifest_bbox))
                continue

            reference_crs, reference_transform, width, height = _reference_grid_spec(stage_grid)
            pending_specs.append(
                {
                    "path": path,
                    "stage_path": stage_path,
                    "manifest_bbox": manifest_bbox,
                    "stage_bbox": stage_bbox,
                    "reference_crs": reference_crs,
                    "reference_transform": reference_transform,
                    "width": width,
                    "height": height,
                    "y_dim": "lat" if "lat" in stage_grid.coords else "y",
                    "x_dim": "lon" if "lon" in stage_grid.coords else "x",
                    "y_coords": np.asarray(
                        stage_grid.coords["lat" if "lat" in stage_grid.coords else "y"].values
                    ),
                    "x_coords": np.asarray(
                        stage_grid.coords["lon" if "lon" in stage_grid.coords else "x"].values
                    ),
                }
            )

        staged_paths: list[tuple[Path, BBox]] = list(reusable_stage_paths)
        logger.info(
            "GWD30 %s: stage plan prepared %d pending tile(s), reused %d staged tile(s)",
            year,
            len(pending_specs),
            len(reusable_stage_paths),
        )
        if not pending_specs:
            return staged_paths

        resolved_worker_count = _resolve_stage_worker_count(worker_count, len(pending_specs))
        logger.info(
            "GWD30 %s: staging %d pending tile(s) with %d worker(s)",
            year,
            len(pending_specs),
            resolved_worker_count,
        )

        def process_spec(spec: dict[str, Any]) -> tuple[Path, BBox] | None:
            return _process_time_fraction_tile_to_stage_file(
                path=str(cast(Path, spec["path"])),
                stage_path=str(cast(Path, spec["stage_path"])),
                manifest_bbox=cast(BBox, spec["manifest_bbox"]),
                stage_bbox=cast(BBox, spec["stage_bbox"]),
                reference_crs=cast(str, spec["reference_crs"]),
                reference_transform=spec["reference_transform"],
                width=cast(int, spec["width"]),
                height=cast(int, spec["height"]),
                y_dim=cast(str, spec["y_dim"]),
                x_dim=cast(str, spec["x_dim"]),
                y_coords=cast(np.ndarray, spec["y_coords"]),
                x_coords=cast(np.ndarray, spec["x_coords"]),
                year=year,
                time_index=time_index,
            )

        if resolved_worker_count > 1 and len(pending_specs) > 1:
            fallback_to_serial = False
            processed_indices: set[int] = set()
            progress = (
                tqdm(
                    total=len(pending_specs),
                    desc=f"GWD30 {year} stage",
                    unit="tile",
                    dynamic_ncols=True,
                    mininterval=5.0,
                )
                if show_progress
                else None
            )
            try:
                try:
                    with ProcessPoolExecutor(
                        max_workers=resolved_worker_count,
                        max_tasks_per_child=1,
                    ) as executor:
                        future_to_meta = {
                            executor.submit(
                                _process_time_fraction_tile_to_stage_file,
                                path=str(cast(Path, spec["path"])),
                                stage_path=str(cast(Path, spec["stage_path"])),
                                manifest_bbox=cast(BBox, spec["manifest_bbox"]),
                                stage_bbox=cast(BBox, spec["stage_bbox"]),
                                reference_crs=cast(str, spec["reference_crs"]),
                                reference_transform=spec["reference_transform"],
                                width=cast(int, spec["width"]),
                                height=cast(int, spec["height"]),
                                y_dim=cast(str, spec["y_dim"]),
                                x_dim=cast(str, spec["x_dim"]),
                                y_coords=cast(np.ndarray, spec["y_coords"]),
                                x_coords=cast(np.ndarray, spec["x_coords"]),
                                year=year,
                                time_index=time_index,
                            ): (index, spec)
                            for index, spec in enumerate(pending_specs)
                        }
                        for future in as_completed(future_to_meta):
                            index, spec = future_to_meta[future]
                            path = cast(Path, spec["path"])
                            if progress is not None:
                                progress.set_postfix_str(path.name, refresh=False)
                            try:
                                staged = future.result()
                                processed_indices.add(index)
                                if staged is not None:
                                    staged_paths.append(staged)
                                if progress is not None:
                                    progress.update(1)
                            except BrokenProcessPool:
                                fallback_to_serial = True
                                break
                            except Exception as exc:
                                logger.warning(
                                    "GWD30 tile %s failed during coarse stage (%s: %s)",
                                    path.name,
                                    type(exc).__name__,
                                    exc,
                                )
                                processed_indices.add(index)
                                if progress is not None:
                                    progress.update(1)
                except Exception as pool_exc:
                    logger.warning(
                        "GWD30 coarse stage parallel execution failed (%s: %s); "
                        "will retry serially",
                        type(pool_exc).__name__,
                        pool_exc,
                    )
                    fallback_to_serial = True

                if fallback_to_serial:
                    remaining = [
                        index for index in range(len(pending_specs))
                        if index not in processed_indices
                    ]
                    logger.warning(
                        "GWD30 coarse stage parallel failed after %d/%d tiles; "
                        "falling back to serial for %d remaining",
                        len(processed_indices),
                        len(pending_specs),
                        len(remaining),
                    )
                    for index in remaining:
                        spec = pending_specs[index]
                        path = cast(Path, spec["path"])
                        if progress is not None:
                            progress.set_postfix_str(path.name, refresh=False)
                        try:
                            staged = process_spec(spec)
                            if staged is not None:
                                staged_paths.append(staged)
                        except Exception as exc:
                            logger.warning(
                                "GWD30 tile %s failed during coarse stage serial fallback "
                                "(%s: %s)",
                                path.name,
                                type(exc).__name__,
                                exc,
                            )
                        if progress is not None:
                            progress.update(1)
            finally:
                if progress is not None:
                    progress.close()
        else:
            iterable = (
                _iter_tiles_with_progress(
                    [cast(Path, spec["path"]) for spec in pending_specs],
                    desc=f"GWD30 {year} stage",
                )
                if show_progress
                else [cast(Path, spec["path"]) for spec in pending_specs]
            )
            spec_by_path = {cast(Path, spec["path"]): spec for spec in pending_specs}
            for index, path in enumerate(iterable, start=1):
                spec = spec_by_path[path]
                if not show_progress and (
                    index == 1 or index == len(pending_specs) or index % 8 == 0
                ):
                    logger.info(
                        "GWD30 %s: staging tile %d/%d | %s",
                        year,
                        index,
                        len(pending_specs),
                        path.name,
                    )
                staged = process_spec(spec)
                if staged is not None:
                    staged_paths.append(staged)

        logger.info("GWD30 %s: staged %d tile partial(s)", year, len(staged_paths))

        return staged_paths

    def transform_staged_time_fraction_tiles(
        self,
        *,
        staged_tiles: list[tuple[Path, BBox]],
        output_dir: Path,
        transform_name: str,
        transform_version: int,
        transform_tile: StagedTileTransform,
        year: int,
        worker_count: int | None = None,
        show_progress: bool = True,
        skip_existing: bool = False,
    ) -> list[tuple[Path, BBox]]:
        """Apply one tile-local transform to staged tile netCDF files.

        The transform must be a top-level callable so it can be executed in worker
        processes. Each transformed output is guarded by the same atomic lock and
        rename strategy used by `stage_time_fraction_tiles()`.
        """

        output_dir.mkdir(parents=True, exist_ok=True)
        if not skip_existing:
            stale_outputs = list(output_dir.glob("tile_*.nc"))
            for stale_output in stale_outputs:
                stale_output.unlink()
            if stale_outputs:
                logger.info(
                    "GWD30 %s: cleared %d stale transformed tile file(s) under %s",
                    year,
                    len(stale_outputs),
                    output_dir,
                )

        reusable_outputs: list[tuple[Path, BBox]] = []
        pending_specs: list[dict[str, Any]] = []
        stale_output_count = 0
        for stage_path, manifest_bbox in staged_tiles:
            output_path = output_dir / stage_path.name
            if skip_existing and output_path.exists():
                if _transformed_tile_cache_is_current(
                    output_path=output_path,
                    stage_path=stage_path,
                    transform_name=transform_name,
                    transform_version=transform_version,
                ):
                    reusable_outputs.append((output_path, manifest_bbox))
                    continue
                output_path.unlink(missing_ok=True)
                stale_output_count += 1
            pending_specs.append(
                {
                    "stage_path": stage_path,
                    "output_path": output_path,
                    "manifest_bbox": manifest_bbox,
                }
            )

        transformed_paths: list[tuple[Path, BBox]] = list(reusable_outputs)
        logger.info(
            "GWD30 %s: transform[%s] plan prepared %d pending tile(s), "
            "reused %d transformed tile(s), refreshed %d stale tile(s)",
            year,
            transform_name,
            len(pending_specs),
            len(reusable_outputs),
            stale_output_count,
        )
        if not pending_specs:
            return transformed_paths

        resolved_worker_count = _resolve_stage_worker_count(worker_count, len(pending_specs))
        logger.info(
            "GWD30 %s: transform[%s] running %d pending tile(s) with %d worker(s)",
            year,
            transform_name,
            len(pending_specs),
            resolved_worker_count,
        )

        def process_spec(spec: dict[str, Any]) -> tuple[Path, BBox] | None:
            return _transform_staged_time_fraction_tile_to_file(
                stage_path=str(cast(Path, spec["stage_path"])),
                output_path=str(cast(Path, spec["output_path"])),
                manifest_bbox=cast(BBox, spec["manifest_bbox"]),
                transform_name=transform_name,
                transform_version=transform_version,
                transform_tile=transform_tile,
            )

        if resolved_worker_count > 1 and len(pending_specs) > 1:
            fallback_to_serial = False
            processed_indices: set[int] = set()
            progress = (
                tqdm(
                    total=len(pending_specs),
                    desc=f"GWD30 {year} transform[{transform_name}]",
                    unit="tile",
                    dynamic_ncols=True,
                    mininterval=5.0,
                )
                if show_progress
                else None
            )
            try:
                try:
                    with ProcessPoolExecutor(
                        max_workers=resolved_worker_count,
                        max_tasks_per_child=1,
                    ) as executor:
                        future_to_meta = {
                            executor.submit(
                                _transform_staged_time_fraction_tile_to_file,
                                stage_path=str(cast(Path, spec["stage_path"])),
                                output_path=str(cast(Path, spec["output_path"])),
                                manifest_bbox=cast(BBox, spec["manifest_bbox"]),
                                transform_name=transform_name,
                                transform_version=transform_version,
                                transform_tile=transform_tile,
                            ): (index, spec)
                            for index, spec in enumerate(pending_specs)
                        }
                        for future in as_completed(future_to_meta):
                            index, spec = future_to_meta[future]
                            path = cast(Path, spec["stage_path"])
                            if progress is not None:
                                progress.set_postfix_str(path.name, refresh=False)
                            try:
                                transformed = future.result()
                                processed_indices.add(index)
                                if transformed is not None:
                                    transformed_paths.append(transformed)
                                if progress is not None:
                                    progress.update(1)
                            except BrokenProcessPool:
                                fallback_to_serial = True
                                break
                            except Exception as exc:
                                logger.warning(
                                    "GWD30 staged tile %s failed during transform[%s] (%s: %s)",
                                    path.name,
                                    transform_name,
                                    type(exc).__name__,
                                    exc,
                                )
                                processed_indices.add(index)
                                if progress is not None:
                                    progress.update(1)
                except Exception as pool_exc:
                    logger.warning(
                        "GWD30 transform[%s] parallel execution failed (%s: %s); "
                        "will retry serially",
                        transform_name,
                        type(pool_exc).__name__,
                        pool_exc,
                    )
                    fallback_to_serial = True

                if fallback_to_serial:
                    remaining = [
                        index
                        for index in range(len(pending_specs))
                        if index not in processed_indices
                    ]
                    logger.warning(
                        "GWD30 transform[%s] parallel failed after %d/%d tiles; "
                        "falling back to serial for %d remaining",
                        transform_name,
                        len(processed_indices),
                        len(pending_specs),
                        len(remaining),
                    )
                    for index in remaining:
                        spec = pending_specs[index]
                        path = cast(Path, spec["stage_path"])
                        if progress is not None:
                            progress.set_postfix_str(path.name, refresh=False)
                        try:
                            transformed = process_spec(spec)
                            if transformed is not None:
                                transformed_paths.append(transformed)
                        except Exception as exc:
                            logger.warning(
                                "GWD30 staged tile %s failed during transform[%s] serial fallback "
                                "(%s: %s)",
                                path.name,
                                transform_name,
                                type(exc).__name__,
                                exc,
                            )
                        if progress is not None:
                            progress.update(1)
            finally:
                if progress is not None:
                    progress.close()
        else:
            iterable = (
                _iter_tiles_with_progress(
                    [cast(Path, spec["stage_path"]) for spec in pending_specs],
                    desc=f"GWD30 {year} transform[{transform_name}]",
                )
                if show_progress
                else [cast(Path, spec["stage_path"]) for spec in pending_specs]
            )
            spec_by_path = {cast(Path, spec["stage_path"]): spec for spec in pending_specs}
            for index, path in enumerate(iterable, start=1):
                spec = spec_by_path[path]
                if not show_progress and (
                    index == 1 or index == len(pending_specs) or index % 8 == 0
                ):
                    logger.info(
                        "GWD30 %s: transform[%s] tile %d/%d | %s",
                        year,
                        transform_name,
                        index,
                        len(pending_specs),
                        path.name,
                    )
                transformed = process_spec(spec)
                if transformed is not None:
                    transformed_paths.append(transformed)

        logger.info(
            "GWD30 %s: transform[%s] produced %d tile cache(s)",
            year,
            transform_name,
            len(transformed_paths),
        )
        return transformed_paths

    def prepare_staged_tile_merge_index(
        self,
        *,
        year: int,
        staged_tiles: list[tuple[Path, BBox]],
    ) -> None:
        """Build and cache a spatial index for one year's staged tile partials."""

        self._merge_index_cache[year] = _build_staged_tile_index(staged_tiles)

    def _candidate_staged_tiles_for_merge(
        self,
        *,
        staged_tiles: list[tuple[Path, BBox]],
        bbox: BBox,
        year: int,
    ) -> list[tuple[Path, BBox]]:
        """Return staged tile partials whose coarse bbox intersects one merge chunk."""

        cached = self._merge_index_cache.get(year)
        if cached is None:
            cached = _build_staged_tile_index(staged_tiles)
            self._merge_index_cache[year] = cached

        index, bin_size_deg = cached
        candidate_by_path: dict[Path, tuple[Path, BBox]] = {}
        for key in _grid_hash_key(bbox, bin_size_deg):
            for stage_path, stage_bbox in index.get(key, []):
                candidate_by_path[stage_path] = (stage_path, stage_bbox)

        return [
            (stage_path, stage_bbox)
            for stage_path, stage_bbox in candidate_by_path.values()
            if _bbox_intersects(stage_bbox, bbox)
        ]

    def merge_staged_time_fraction_tiles(
        self,
        *,
        staged_tiles: list[tuple[Path, BBox]],
        reference_grid: xr.DataArray,
        bbox: BBox,
        year: int,
        batch_size: int = 100,
    ) -> xr.Dataset:
        """Merge staged tiles into one output chunk.

        Processes tiles in batches to control memory usage.

        Args:
            staged_tiles: List of (path, bbox) tuples
            reference_grid: Target reference grid
            bbox: Target bounding box
            year: Year to process
            batch_size: Process N tiles at a time (default: 100)
        """

        time_range = (f"{year}-01-01", f"{year}-12-31")

        candidate_tiles = self._candidate_staged_tiles_for_merge(
            staged_tiles=staged_tiles,
            bbox=bbox,
            year=year,
        )

        if not candidate_tiles:
            raise FileNotFoundError(f"No staged GWD30 coarse tiles intersect {bbox}")

        y_dim = "lat" if "lat" in reference_grid.coords else "y"
        x_dim = "lon" if "lon" in reference_grid.coords else "x"
        chunk_y = reference_grid.coords[y_dim].values
        chunk_x = reference_grid.coords[x_dim].values

        # Pre-read time/class coords from first tile
        first_path = candidate_tiles[0][0]
        with xr.open_dataset(first_path, engine="netcdf4") as first_source:
            time_coords = np.asarray(first_source.coords["time"].values)
            class_coords = np.asarray(first_source.coords["class_id"].values)

        # Accumulate in batches
        weighted_sum: np.ndarray | None = None
        coverage_sum: np.ndarray | None = None

        total = len(candidate_tiles)
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch = candidate_tiles[batch_start:batch_end]

            batch_weighted = None
            batch_coverage = None

            for stage_path, _ in batch:
                with xr.open_dataset(stage_path, engine="netcdf4") as source:
                    weighted = source["weighted"].reindex(
                        {y_dim: chunk_y, x_dim: chunk_x},
                        fill_value=0.0,
                    ).transpose("time", "class_id", y_dim, x_dim)
                    coverage = source["coverage"].reindex(
                        {y_dim: chunk_y, x_dim: chunk_x},
                        fill_value=0.0,
                    ).transpose("time", y_dim, x_dim)

                    w = np.asarray(weighted.values, dtype=np.float32)
                    c = np.asarray(coverage.values, dtype=np.float32)

                    if batch_weighted is None:
                        batch_weighted = w
                        batch_coverage = c
                    else:
                        batch_weighted = batch_weighted + w
                        batch_coverage = batch_coverage + c

            # Accumulate batch result
            if weighted_sum is None:
                weighted_sum = batch_weighted
                coverage_sum = batch_coverage
            else:
                weighted_sum = weighted_sum + batch_weighted
                coverage_sum = coverage_sum + batch_coverage

            # Clear batch memory
            del batch_weighted, batch_coverage
            gc.collect()

        if weighted_sum is None or coverage_sum is None:
            raise FileNotFoundError(f"Failed to merge staged GWD30 coarse tiles for {bbox}")

        # Compute fractions: weighted / coverage
        fractions = np.full_like(weighted_sum, np.nan)
        np.divide(
            weighted_sum,
            coverage_sum[:, None, :, :],
            out=fractions,
            where=coverage_sum[:, None, :, :] > 0,
        )
        fractions = np.clip(fractions, 0.0, 1.0)

        coords = {
            "time": time_coords,
            y_dim: chunk_y,
            x_dim: chunk_x,
        }
        dataset = xr.Dataset(
            {
                f"frac_{int(class_id)}": xr.DataArray(
                    fractions[:, class_index],
                    dims=("time", y_dim, x_dim),
                    coords=coords,
                    attrs={
                        "dataset_id": self.dataset_id,
                        "year": year,
                        "source": "staged_time_fraction_tiles",
                        "description": (
                            f"GWD30 raw class-{int(class_id)} fraction on coarse grid"
                        ),
                    },
                )
                for class_index, class_id in enumerate(class_coords)
            }
        )
        dataset = self.finalize_dataset(
            dataset,
            bbox=bbox,
            time_range=time_range,
            reference_grid=reference_grid,
        )
        dataset.attrs.update({"year": year, "source": "staged_time_fraction_tiles"})
        return dataset

    def _discover_tiles(
        self,
        *,
        bbox: BBox | None,
        time_range: TimeRange | None,
    ) -> dict[int, list[Path]]:
        cache_key = (bbox, time_range)
        if cache_key in self._discover_tiles_cache:
            return self._discover_tiles_cache[cache_key]

        allowed_years = {int(year) for year in self.config.get("years", [])}
        if time_range is not None:
            start_year = int(time_range[0][:4])
            end_year = int(time_range[1][:4])
            allowed_years &= set(range(start_year, end_year + 1))

        grouped: dict[int, list[Path]] = defaultdict(list)
        for year in sorted(allowed_years):
            pattern = str(self.config["pattern"]).format(year=year)
            paths = sorted(self.base_path.glob(pattern))
            logger.debug("GWD30 discovered %s candidate tile(s) for year %s", len(paths), year)
            if bbox is not None:
                paths = self._filter_tiles_for_bbox(paths, bbox)
                logger.debug(
                    "GWD30 kept %s tile(s) for year %s after bbox filter",
                    len(paths),
                    year,
                )
            for path in paths:
                grouped[year].append(path)
        self._discover_tiles_cache[cache_key] = grouped
        return grouped

    def _filter_tiles_for_bbox(self, paths: list[Path], bbox: BBox) -> list[Path]:
        """Filter candidate tiles for a lon/lat bbox using GWD30 tile codes first."""

        min_lon, min_lat, max_lon, max_lat = bbox
        tile_codes = set(self._tiling.bbox_to_tiles(min_lat, min_lon, max_lat, max_lon))
        if tile_codes:
            matched = [
                path
                for path in paths
                if (tile_code := _extract_tile_code(path)) is not None and tile_code in tile_codes
            ]
            if matched:
                logger.debug(
                    "GWD30 tile-code prefilter matched %s/%s tile(s) for bbox %s",
                    len(matched),
                    len(paths),
                    bbox,
                )
                return matched

        logger.debug("GWD30 falling back to raster-bounds scan for bbox %s", bbox)
        return _filter_files_by_bounds(paths, bbox)

    def load_rough_binary_surface(
        self,
        *,
        bbox: BBox,
        time_range: TimeRange,
        reference_grid: xr.DataArray,
        aggregation: str,
        target_time: pd.Timestamp,
        worker_count: int | None = None,
    ) -> tuple[xr.DataArray, dict[str, Any]]:
        """Load GWD30 directly into the coarse rough-comparison grid.

        This avoids materializing a full high-resolution annual mosaic, which can
        exceed memory for large tropical basins.
        """

        tiles_by_year = self._discover_tiles(bbox=bbox, time_range=time_range)
        if not tiles_by_year:
            raise FileNotFoundError(f"No GWD30 tiles found under {self.base_path}")

        trace: dict[str, Any] = {
            "strategy": "direct_to_reference_grid",
            "intermediate_storage": "temporary_coarse_geotiff_tiles",
            "mosaic_strategy": "average_of_processed_tiles",
            "bbox": list(bbox),
            "time_range": list(time_range),
            "target_time": target_time.isoformat(),
            "years": [],
        }
        resolved_worker_count = _resolve_parallel_worker_count(worker_count)
        trace["worker_count"] = resolved_worker_count
        with tempfile.TemporaryDirectory(prefix="wa_gwd30_rough_") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            processed_tile_paths: list[Path] = []
            accumulated_sum = np.zeros(reference_grid.shape, dtype=np.float32)
            accumulated_count = np.zeros(reference_grid.shape, dtype=np.int16)

            for year, paths in sorted(tiles_by_year.items()):
                if not paths:
                    continue
                band_indexes, selected_times = self._selected_band_window(
                    year,
                    paths[0],
                    time_range=time_range,
                )
                year_trace: dict[str, Any] = {
                    "year": year,
                    "matched_tile_count": len(paths),
                    "selected_band_indexes": [int(index) for index in band_indexes],
                    "selected_band_timestamps": [
                        timestamp.isoformat() for timestamp in selected_times
                    ],
                    "selected_tiles": [],
                }
                if not band_indexes:
                    trace["years"].append(year_trace)
                    continue

                logger.info(
                    "GWD30 direct rough load year %s with %s tile(s) and %s selected band(s)",
                    year,
                    len(paths),
                    len(band_indexes),
                )

                if resolved_worker_count > 1 and len(paths) > 1:
                    trace["strategy"] = "parallel_direct_to_reference_grid"
                    trace["intermediate_storage"] = "in_memory_partial_reduce"
                    trace["mosaic_strategy"] = "main_process_sum_count_reduce"
                    year_tile_entries, year_sum, year_count = self._reduce_year_tiles_parallel(
                        year=year,
                        paths=paths,
                        bbox=bbox,
                        band_indexes=band_indexes,
                        aggregation=aggregation,
                        reference_grid=reference_grid,
                        worker_count=resolved_worker_count,
                    )
                    year_trace["selected_tiles"].extend(year_tile_entries)
                    accumulated_sum = accumulated_sum + year_sum
                    accumulated_count = accumulated_count + year_count
                else:
                    for tile_index, path in enumerate(
                        _iter_tiles_with_progress(paths, desc=f"GWD30 {year} process"),
                        start=1,
                    ):
                        tile_code = _extract_tile_code(path)
                        tile_bbox = self._tile_bbox(tile_code) if tile_code is not None else None
                        temp_tile_path, coarse_non_null_count = self._process_rough_tile_to_temp(
                            path=path,
                            bbox=bbox,
                            band_indexes=band_indexes,
                            aggregation=aggregation,
                            temp_dir=temp_dir,
                            tile_token=f"{year}_{tile_index:05d}_{path.stem}",
                            reference_grid=reference_grid,
                        )
                        year_trace["selected_tiles"].append(
                            {
                                "path": str(path),
                                "tile_code": tile_code,
                                "tile_bbox": list(tile_bbox) if tile_bbox is not None else None,
                                "coarse_non_null_count": coarse_non_null_count,
                                "processed_temp_written": temp_tile_path is not None,
                            }
                        )
                        if temp_tile_path is not None:
                            processed_tile_paths.append(temp_tile_path)
                        gc.collect()

                trace["years"].append(year_trace)

            if trace["intermediate_storage"] == "in_memory_partial_reduce":
                surface_values = np.full(reference_grid.shape, np.nan, dtype=np.float32)
                valid_counts = accumulated_count > 0
                surface_values[valid_counts] = (
                    accumulated_sum[valid_counts] / accumulated_count[valid_counts]
                )
                surface = reference_grid.copy(data=surface_values.astype(np.float32))
            else:
                surface = self._mosaic_processed_tiles(
                    processed_tile_paths,
                    reference_grid=reference_grid,
                )

        trace["processed_temp_tile_count"] = len(processed_tile_paths)
        surface.name = "wetland_fraction"
        surface.attrs.update(
            {
                "dataset_id": self.dataset_id,
                "comparison_source_variable": "wetland_class",
                "comparison_aggregation": aggregation,
                "comparison_time": target_time.isoformat(),
                "comparison_source_time": target_time.isoformat(),
                "comparison_threshold": BINARY_WETLAND_THRESHOLD,
            }
        )
        return surface, trace

    def compute_rough_binary_partial(
        self,
        *,
        bbox: BBox,
        time_range: TimeRange,
        reference_grid: xr.DataArray,
        aggregation: str,
        target_time: pd.Timestamp,
        worker_count: int | None = None,
        shard_index: int = 0,
        shard_count: int = 1,
    ) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
        """Compute one shard's partial coarse-grid sum/count for GWD30 rough loading."""

        shard_index, shard_count = _normalize_shard_spec(shard_index, shard_count)
        tiles_by_year = self._discover_tiles(bbox=bbox, time_range=time_range)
        if not tiles_by_year:
            raise FileNotFoundError(f"No GWD30 tiles found under {self.base_path}")

        resolved_worker_count = _resolve_parallel_worker_count(worker_count)
        accumulated_sum = np.zeros(reference_grid.shape, dtype=np.float32)
        accumulated_count = np.zeros(reference_grid.shape, dtype=np.int16)
        trace: dict[str, Any] = {
            "strategy": "sharded_partial_reduce",
            "bbox": list(bbox),
            "time_range": list(time_range),
            "target_time": target_time.isoformat(),
            "worker_count": resolved_worker_count,
            "shard_index": shard_index,
            "shard_count": shard_count,
            "years": [],
        }

        for year, paths in sorted(tiles_by_year.items()):
            assigned_paths = _select_paths_for_shard(
                paths,
                shard_index=shard_index,
                shard_count=shard_count,
            )
            band_indexes, selected_times = self._selected_band_window(
                year,
                paths[0],
                time_range=time_range,
            )
            year_trace: dict[str, Any] = {
                "year": year,
                "matched_tile_count": len(paths),
                "assigned_tile_count": len(assigned_paths),
                "selected_band_indexes": [int(index) for index in band_indexes],
                "selected_band_timestamps": [
                    timestamp.isoformat() for timestamp in selected_times
                ],
                "selected_tiles": [],
            }
            if not band_indexes or not assigned_paths:
                trace["years"].append(year_trace)
                continue

            if resolved_worker_count > 1 and len(assigned_paths) > 1:
                year_tile_entries, year_sum, year_count = self._reduce_year_tiles_parallel(
                    year=year,
                    paths=assigned_paths,
                    bbox=bbox,
                    band_indexes=band_indexes,
                    aggregation=aggregation,
                    reference_grid=reference_grid,
                    worker_count=resolved_worker_count,
                )
            else:
                year_tile_entries, year_sum, year_count = self._reduce_year_tiles_serial(
                    year=year,
                    paths=assigned_paths,
                    bbox=bbox,
                    band_indexes=band_indexes,
                    aggregation=aggregation,
                    reference_grid=reference_grid,
                )
            year_trace["selected_tiles"].extend(year_tile_entries)
            accumulated_sum = accumulated_sum + year_sum
            accumulated_count = accumulated_count + year_count
            trace["years"].append(year_trace)

        return accumulated_sum, accumulated_count, trace

    def build_surface_from_partial(
        self,
        *,
        partial_sum: np.ndarray,
        partial_count: np.ndarray,
        reference_grid: xr.DataArray,
        aggregation: str,
        target_time: pd.Timestamp,
    ) -> xr.DataArray:
        """Convert reduced sum/count partial arrays into a final GWD30 coarse surface."""

        surface_values = np.full(reference_grid.shape, np.nan, dtype=np.float32)
        valid_counts = partial_count > 0
        surface_values[valid_counts] = partial_sum[valid_counts] / partial_count[valid_counts]
        surface = reference_grid.copy(data=surface_values.astype(np.float32))
        surface.name = "wetland_fraction"
        surface.attrs.update(
            {
                "dataset_id": self.dataset_id,
                "comparison_source_variable": "wetland_class",
                "comparison_aggregation": aggregation,
                "comparison_time": target_time.isoformat(),
                "comparison_source_time": target_time.isoformat(),
                "comparison_threshold": BINARY_WETLAND_THRESHOLD,
            }
        )
        return surface

    def _reduce_year_tiles_serial(
        self,
        *,
        year: int,
        paths: list[Path],
        bbox: BBox,
        band_indexes: list[int],
        aggregation: str,
        reference_grid: xr.DataArray,
    ) -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray]:
        """Process one year's tiles serially and accumulate coarse sum/count arrays."""

        reference_crs, reference_transform, width, height = _reference_grid_spec(reference_grid)
        accumulated_sum = np.zeros(reference_grid.shape, dtype=np.float32)
        accumulated_count = np.zeros(reference_grid.shape, dtype=np.int16)
        selected_tiles: list[dict[str, Any]] = []

        for path in _iter_tiles_with_progress(paths, desc=f"GWD30 {year} shard"):
            tile_code = _extract_tile_code(path)
            tile_bbox = self._tile_bbox(tile_code) if tile_code is not None else None
            coarse, coarse_non_null_count = _project_rough_tile_to_coarse_array(
                path=str(path),
                bbox=bbox,
                band_indexes=band_indexes,
                aggregation=aggregation,
                reference_crs=reference_crs,
                reference_transform=reference_transform,
                width=width,
                height=height,
            )
            if coarse is not None:
                valid = np.isfinite(coarse)
                accumulated_sum[valid] = accumulated_sum[valid] + coarse[valid]
                accumulated_count[valid] = accumulated_count[valid] + 1
            selected_tiles.append(
                {
                    "path": str(path),
                    "tile_code": tile_code,
                    "tile_bbox": list(tile_bbox) if tile_bbox is not None else None,
                    "coarse_non_null_count": coarse_non_null_count,
                    "processed_temp_written": False,
                    "processed_in_memory": coarse is not None,
                }
            )
        return selected_tiles, accumulated_sum, accumulated_count

    def _reduce_year_tiles_parallel(
        self,
        *,
        year: int,
        paths: list[Path],
        bbox: BBox,
        band_indexes: list[int],
        aggregation: str,
        reference_grid: xr.DataArray,
        worker_count: int,
    ) -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray]:
        """Process one year's GWD30 tiles in parallel and reduce them in memory.

        Falls back to serial processing if the process pool breaks (e.g. OOM).
        """

        reference_crs, reference_transform, width, height = _reference_grid_spec(reference_grid)
        accumulated_sum = np.zeros(reference_grid.shape, dtype=np.float32)
        accumulated_count = np.zeros(reference_grid.shape, dtype=np.int16)
        selected_tiles: list[dict[str, Any] | None] = [None] * len(paths)
        processed_indices: set[int] = set()
        fallback_to_serial = False

        progress = tqdm(
            total=len(paths),
            desc=f"GWD30 {year} parallel",
            unit="tile",
            dynamic_ncols=True,
            mininterval=5.0,
        )
        try:
            try:
                with ProcessPoolExecutor(
                    max_workers=worker_count,
                    max_tasks_per_child=1,
                ) as executor:
                    future_to_meta = {
                        executor.submit(
                            _process_rough_tile_to_partial,
                            path=str(path),
                            bbox=bbox,
                            band_indexes=band_indexes,
                            aggregation=aggregation,
                            reference_crs=reference_crs,
                            reference_transform=reference_transform,
                            width=width,
                            height=height,
                        ): (
                            index,
                            path,
                            _extract_tile_code(path),
                        )
                        for index, path in enumerate(paths)
                    }
                    for future in as_completed(future_to_meta):
                        index, path, tile_code = future_to_meta[future]
                        tile_bbox = self._tile_bbox(tile_code) if tile_code is not None else None
                        try:
                            tile_sum, tile_count, coarse_non_null_count = future.result()
                            processed_indices.add(index)
                            if tile_sum is not None and tile_count is not None:
                                accumulated_sum = accumulated_sum + tile_sum
                                accumulated_count = accumulated_count + tile_count.astype(np.int16)
                            progress.update(1)
                        except BrokenProcessPool:
                            fallback_to_serial = True
                            break
                        except Exception as exc:
                            processed_indices.add(index)
                            logger.warning(
                                "GWD30 tile %s skipped during parallel reduction (%s: %s)",
                                path.name,
                                type(exc).__name__,
                                exc,
                            )
                            tile_sum = None
                            tile_count = None
                            coarse_non_null_count = 0
                            progress.update(1)
                        selected_tiles[index] = {
                            "path": str(path),
                            "tile_code": tile_code,
                            "tile_bbox": list(tile_bbox) if tile_bbox is not None else None,
                            "coarse_non_null_count": coarse_non_null_count,
                            "processed_temp_written": False,
                            "processed_in_memory": tile_sum is not None and tile_count is not None,
                        }
            except Exception as pool_exc:
                if not isinstance(pool_exc, BrokenProcessPool):
                    logger.warning(
                        "GWD30 parallel execution failed (%s: %s); will retry serially",
                        type(pool_exc).__name__,
                        pool_exc,
                    )
                fallback_to_serial = True

            if fallback_to_serial:
                remaining = [i for i in range(len(paths)) if i not in processed_indices]
                logger.warning(
                    "GWD30 parallel failed after %d/%d tiles; "
                    "falling back to serial for %d remaining",
                    len(processed_indices),
                    len(paths),
                    len(remaining),
                )
                for i in remaining:
                    path = paths[i]
                    tile_code = _extract_tile_code(path)
                    tile_bbox = self._tile_bbox(tile_code) if tile_code is not None else None
                    try:
                        tile_sum, tile_count, coarse_non_null_count = (
                            _process_rough_tile_to_partial(
                                path=str(path),
                                bbox=bbox,
                                band_indexes=band_indexes,
                                aggregation=aggregation,
                                reference_crs=reference_crs,
                                reference_transform=reference_transform,
                                width=width,
                                height=height,
                            )
                        )
                        if tile_sum is not None and tile_count is not None:
                            accumulated_sum = accumulated_sum + tile_sum
                            accumulated_count = accumulated_count + tile_count.astype(np.int16)
                    except Exception as exc:
                        logger.warning(
                            "GWD30 tile %s failed during serial fallback (%s: %s)",
                            path.name,
                            type(exc).__name__,
                            exc,
                        )
                        tile_sum = None
                        tile_count = None
                        coarse_non_null_count = 0
                    selected_tiles[i] = {
                        "path": str(path),
                        "tile_code": tile_code,
                        "tile_bbox": list(tile_bbox) if tile_bbox is not None else None,
                        "coarse_non_null_count": coarse_non_null_count,
                        "processed_temp_written": False,
                        "processed_in_memory": tile_sum is not None and tile_count is not None,
                    }
                    progress.update(1)
        finally:
            progress.close()

        return (
            [entry for entry in selected_tiles if entry is not None],
            accumulated_sum,
            accumulated_count,
        )

    def _selected_band_window(
        self,
        year: int,
        sample_path: Path,
        *,
        time_range: TimeRange,
    ) -> tuple[list[int], list[pd.Timestamp]]:
        start_time = pd.Timestamp(time_range[0])
        end_time = pd.Timestamp(time_range[1])
        with rasterio.open(sample_path) as src:
            band_count = int(src.count)
        time_index = four_day_index_for_year(year, band_count)
        selected_indexes = [
            int(index)
            for index, timestamp in enumerate(time_index)
            if start_time <= timestamp <= end_time
        ]
        selected_times = [time_index[index] for index in selected_indexes]
        return selected_indexes, selected_times

    def _tile_bbox(self, tile_code: str | None) -> BBox | None:
        if tile_code is None:
            return None
        try:
            return self._tiling.tile_to_extent(tile_code)
        except Exception:
            return None

    def _tile_bounds_for_stage(self, path: Path) -> BBox | None:
        cached = self._tile_bbox_cache.get(path)
        if path in self._tile_bbox_cache:
            return cached

        bounds = self._tile_bbox(_extract_tile_code(path))
        if bounds is None:
            bounds = _path_bounds_wgs84(path)
        self._tile_bbox_cache[path] = bounds
        return bounds

    def _process_rough_tile_to_temp(
        self,
        *,
        path: Path,
        bbox: BBox,
        band_indexes: list[int],
        aggregation: str,
        temp_dir: Path,
        tile_token: str,
        reference_grid: xr.DataArray,
    ) -> tuple[Path | None, int]:
        """Project one source tile to the coarse grid and persist it as a temp GeoTIFF."""

        reference_crs, reference_transform, width, height = _reference_grid_spec(reference_grid)
        coarse, coarse_non_null_count = _project_rough_tile_to_coarse_array(
            path=str(path),
            bbox=bbox,
            band_indexes=band_indexes,
            aggregation=aggregation,
            reference_crs=reference_crs,
            reference_transform=reference_transform,
            width=width,
            height=height,
        )
        if coarse is None or coarse_non_null_count == 0:
            return None, 0

        temp_tile_path = temp_dir / f"{tile_token}_coarse.tif"
        with rasterio.open(
            temp_tile_path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype="float32",
            crs=reference_crs,
            transform=reference_transform,
            nodata=float(_TEMP_TILE_NODATA),
            compress="deflate",
        ) as dst:
            temp_data = np.where(np.isfinite(coarse), coarse, _TEMP_TILE_NODATA).astype(np.float32)
            dst.write(temp_data, 1)

        return temp_tile_path, coarse_non_null_count

    def _mosaic_processed_tiles(
        self,
        temp_tile_paths: list[Path],
        *,
        reference_grid: xr.DataArray,
    ) -> xr.DataArray:
        """Average all processed coarse temp tiles into one final comparison surface."""

        accumulated_sum = np.zeros(reference_grid.shape, dtype=np.float32)
        accumulated_count = np.zeros(reference_grid.shape, dtype=np.int16)

        for temp_tile_path in _iter_tiles_with_progress(
            temp_tile_paths,
            desc="GWD30 mosaic",
        ):
            with rasterio.open(temp_tile_path) as src:
                tile = src.read(1, masked=True)
            tile_values = np.asarray(tile.filled(np.nan), dtype=np.float32)
            valid = np.isfinite(tile_values)
            accumulated_sum[valid] = accumulated_sum[valid] + tile_values[valid]
            accumulated_count[valid] = accumulated_count[valid] + 1

        surface_values = np.full(reference_grid.shape, np.nan, dtype=np.float32)
        valid_counts = accumulated_count > 0
        surface_values[valid_counts] = (
            accumulated_sum[valid_counts] / accumulated_count[valid_counts]
        )
        return reference_grid.copy(data=surface_values.astype(np.float32))
