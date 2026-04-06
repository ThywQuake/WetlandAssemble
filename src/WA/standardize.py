"""Standardize all wetland datasets onto a unified WGS84 500m grid.

Phase 1.5: converts raw data (GeoTIFF / NetCDF at varying resolutions)
into compressed per-year netCDF files on a common grid for downstream
comparison.
"""

from __future__ import annotations

import gc
import json
import logging
import os
import re
from collections import defaultdict
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import xarray as xr
from netCDF4 import Dataset as NetCDFDataset
from rasterio.enums import Resampling

from WA.comparison.harmonize import create_comparison_grid
from WA.loaders._shared import reproject_to_grid
from WA.loaders.base import (
    BBox,
    DatasetLoader,
    TimeRange,
    apply_bbox,
    normalize_spatial_dimensions,
)
from WA.utils.progress import tqdm

logger = logging.getLogger(__name__)

_CHUNK_PATH_PATTERN = re.compile(
    r"^chunk_r(?P<row_start>\d{5})-(?P<row_stop>\d{5})_"
    r"c(?P<col_start>\d{5})-(?P<col_stop>\d{5})\.nc$"
)


@dataclass(frozen=True)
class GridChunk:
    """One spatial chunk of the target reference grid."""

    row_start: int
    row_stop: int
    col_start: int
    col_stop: int

    @property
    def token(self) -> str:
        return (
            f"r{self.row_start:05d}-{self.row_stop:05d}_"
            f"c{self.col_start:05d}-{self.col_stop:05d}"
        )


@dataclass(frozen=True)
class _Gwd30RebucketTarget:
    """One chunk-local partial to materialize from a staged GWD30 tile file."""

    chunk: GridChunk
    contribution_path: Path
    contribution_bbox: BBox

# ---------------------------------------------------------------------------
# netCDF encoding defaults
# ---------------------------------------------------------------------------
_ENCODING_DEFAULTS: dict[str, Any] = {
    "zlib": True,
    "complevel": 4,
    "shuffle": True,
}

_SPATIAL_CHUNK_CELLS: dict[str, int] = {
    "g2017": 512,
    "glwd_v2": 1024,
    "gwd30": 256,
    "swamps": 1024,
    "topmodel": 1024,
    "wad2m": 1024,
    "giems_mc": 1024,
    "berkeley_rwawc": 512,
}

_THREAD_SAFE_CHUNK_PARALLEL_DATASETS: set[str] = set()


# ---------------------------------------------------------------------------
# Reference grid
# ---------------------------------------------------------------------------

def build_reference_grid(bbox: BBox, resolution_m: float = 500) -> xr.DataArray:
    """Create the WGS84 reference grid at the requested resolution.

    Delegates to ``create_comparison_grid`` with the resolution converted
    from metres to degrees (using the equatorial approximation
    ``1° ≈ 111 320 m``).
    """
    resolution_deg = resolution_m / 111_320
    return create_comparison_grid(bbox, resolution_deg=resolution_deg)


# ---------------------------------------------------------------------------
# Classification → fraction conversion
# ---------------------------------------------------------------------------

def classification_to_fractions(
    data: xr.DataArray,
    reference_grid: xr.DataArray,
    class_values: list[int],
    *,
    prefix: str = "frac",
) -> xr.Dataset:
    """Convert a classification raster into per-class area-fraction variables.

    For each class value *C*:
      1. Create a binary mask ``(data == C).astype(float32)``
      2. Reproject onto *reference_grid* with ``Resampling.average``
      3. Store as ``{prefix}_{C}``

    Returns an ``xr.Dataset`` with one variable per class.
    """
    variables: dict[str, xr.DataArray] = {}
    for class_val in tqdm(class_values, desc=f"  {prefix} classes"):
        mask = (data == class_val).astype(np.float32)
        # Propagate CRS from the source data
        if data.rio.crs is not None:
            mask = mask.rio.write_crs(data.rio.crs)
        # Set spatial dims
        x_dim = next((d for d in ("lon", "x") if d in mask.dims), None)
        y_dim = next((d for d in ("lat", "y") if d in mask.dims), None)
        if x_dim is not None and y_dim is not None:
            try:
                mask = mask.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim)
            except Exception:
                pass
        frac = _reproject_and_normalize(
            mask,
            reference_grid,
            resampling=Resampling.average,
        )
        variables[f"{prefix}_{class_val}"] = frac
    return xr.Dataset(variables)


def glwd_ha_to_fractions(
    ha_data: xr.DataArray,
    reference_grid: xr.DataArray,
) -> xr.Dataset:
    """Convert GLWD area-by-class (ha) into normalised fraction variables.

    Steps:
      1. For each ``glwd_class`` slice: bilinear reproject ha onto 500 m grid
      2. Sum all classes → ``total_ha``
      3. ``frac_C = ha_C / total_ha``  (NaN where total_ha == 0)
    """
    class_ids = ha_data["glwd_class"].values
    reprojected: dict[int, xr.DataArray] = {}

    for class_id in tqdm(class_ids, desc="  GLWD ha→frac"):
        slice_da = ha_data.sel(glwd_class=class_id).drop_vars("glwd_class")
        # Ensure CRS + spatial dims
        if slice_da.rio.crs is None:
            slice_da = slice_da.rio.write_crs("EPSG:4326")
        x_dim = next((d for d in ("lon", "x") if d in slice_da.dims), None)
        y_dim = next((d for d in ("lat", "y") if d in slice_da.dims), None)
        if x_dim is not None and y_dim is not None:
            try:
                slice_da = slice_da.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim)
            except Exception:
                pass
        reprojected[int(class_id)] = _reproject_and_normalize(
            slice_da,
            reference_grid,
            resampling=Resampling.bilinear,
        )

    # Stack into (class, lat, lon) for normalisation
    total_ha = sum(reprojected.values())
    total_ha = xr.where(total_ha == 0, np.nan, total_ha)

    variables: dict[str, xr.DataArray] = {}
    for class_id, ha_reproj in reprojected.items():
        variables[f"frac_{class_id}"] = ha_reproj / total_ha

    return xr.Dataset(variables)


# ---------------------------------------------------------------------------
# Continuous data standardisation
# ---------------------------------------------------------------------------

def standardize_continuous(
    dataset: xr.Dataset,
    reference_grid: xr.DataArray,
    *,
    resampling: Resampling = Resampling.bilinear,
) -> xr.Dataset:
    """Reproject continuous data onto the reference grid and clip to [0, 1]."""
    from WA.loaders._shared import reproject_dataset_to_grid

    result = reproject_dataset_to_grid(dataset, reference_grid, resampling=resampling)
    for var_name in result.data_vars:
        result[var_name] = result[var_name].clip(0, 1)
    return result


# ---------------------------------------------------------------------------
# netCDF encoding
# ---------------------------------------------------------------------------

def _build_encoding(dataset: xr.Dataset) -> dict[str, dict[str, Any]]:
    """Build per-variable netCDF encoding with zlib compression + chunking."""
    encoding: dict[str, dict[str, Any]] = {}
    for var_name, da in dataset.data_vars.items():
        var_enc = dict(_ENCODING_DEFAULTS)
        # Determine chunk sizes based on dimensions
        chunks: list[int] = []
        for dim in da.dims:
            if dim in ("lat", "lon", "y", "x"):
                chunks.append(min(500, da.sizes[dim]))
            else:
                # time, config, forcing, etc. → chunk of 1
                chunks.append(1)
        var_enc["chunksizes"] = tuple(chunks)
        encoding[var_name] = var_enc
    return encoding


def _sanitize_attr_value(value: Any) -> Any:
    """Convert values unsupported by netCDF attrs into stable JSON strings."""
    if isinstance(value, bool | np.bool_):
        return int(value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    if isinstance(value, list | tuple):
        if any(isinstance(item, dict | list | tuple) for item in value):
            return json.dumps(value)
        return list(value)
    return value


def _sanitize_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    """Return a netCDF-safe copy of an attribute dictionary."""
    return {
        key: _sanitize_attr_value(value)
        for key, value in attrs.items()
        if value is not None
    }


def _sanitize_dataset_for_netcdf(dataset: xr.Dataset) -> xr.Dataset:
    """Return a dataset whose dataset/variable attrs are netCDF-safe."""
    clean = dataset.copy(deep=False)
    clean.attrs = _sanitize_attrs(dict(clean.attrs))
    for var_name in clean.data_vars:
        clean[var_name].attrs = _sanitize_attrs(dict(clean[var_name].attrs))
    for coord_name in clean.coords:
        clean[coord_name].attrs = _sanitize_attrs(dict(clean[coord_name].attrs))
        clean[coord_name].encoding = {}
    return clean


def _save_dataset(
    dataset: xr.Dataset,
    output_path: Path,
    *,
    log_output: bool = True,
) -> None:
    """Write dataset to compressed netCDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean = _sanitize_dataset_for_netcdf(dataset)
    encoding = _build_encoding(clean)
    temp_output_path = output_path.parent / (
        f".{output_path.name}.tmp-{os.getpid()}-{uuid4().hex}"
    )
    try:
        clean.to_netcdf(
            temp_output_path,
            format="NETCDF4",
            engine="netcdf4",
            encoding=encoding,
        )
        os.replace(temp_output_path, output_path)
    except Exception:
        try:
            temp_output_path.unlink()
        except FileNotFoundError:
            pass
        raise
    if log_output:
        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info("  → %s (%.1f MB)", output_path.name, size_mb)


def _is_readable_netcdf(path: Path) -> bool:
    """Return whether one staged netCDF file can be opened successfully."""

    try:
        with xr.open_dataset(path, engine="netcdf4"):
            return True
    except Exception:
        return False


def _is_valid_staged_chunk(path: Path, reference_grid: xr.DataArray) -> bool:
    """Return whether one staged chunk matches the current spatial coord contract."""

    y_dim, x_dim = _reference_grid_dims(reference_grid)
    try:
        with xr.open_dataset(path, engine="netcdf4") as dataset:
            if y_dim not in dataset.dims or x_dim not in dataset.dims:
                return False
            if y_dim not in dataset.coords or x_dim not in dataset.coords:
                return False
            if dataset.sizes.get(y_dim, 0) == 0 or dataset.sizes.get(x_dim, 0) == 0:
                return False
            if dataset.coords[y_dim].ndim != 1 or dataset.coords[x_dim].ndim != 1:
                return False
            return True
    except Exception:
        return False


def _find_unreadable_netcdf_paths(paths: list[Path]) -> list[Path]:
    """Return staged netCDF paths that cannot be opened."""

    return [path for path in paths if not _is_readable_netcdf(path)]


def _find_invalid_staged_chunk_paths(
    paths: list[Path],
    reference_grid: xr.DataArray,
) -> list[Path]:
    """Return staged chunk paths that fail the current merge contract."""

    return [path for path in paths if not _is_valid_staged_chunk(path, reference_grid)]


def _reference_grid_dims(reference_grid: xr.DataArray) -> tuple[str, str]:
    """Return the y/x dimension names used by a reference grid."""
    y_dim = "lat" if "lat" in reference_grid.dims else "y"
    x_dim = "lon" if "lon" in reference_grid.dims else "x"
    return y_dim, x_dim


def _dataarray_spatial_dims(data: xr.DataArray) -> tuple[str | None, str | None]:
    """Return the y/x-like spatial dims present on a DataArray."""
    y_dim = next((dim for dim in ("lat", "y") if dim in data.dims), None)
    x_dim = next((dim for dim in ("lon", "x") if dim in data.dims), None)
    return y_dim, x_dim


def _normalize_spatial_dataarray(data: xr.DataArray) -> xr.DataArray:
    """Normalize a DataArray to the project's canonical WGS84 spatial dims."""
    original_name = data.name
    dataset_name = original_name or "__value__"
    normalized = normalize_spatial_dimensions(data.to_dataset(name=dataset_name))[dataset_name]
    if original_name is None:
        normalized = normalized.rename(None)

    y_dim, x_dim = _dataarray_spatial_dims(normalized)
    if x_dim is not None and y_dim is not None:
        try:
            normalized = normalized.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim)
        except Exception:
            pass
    if data.rio.crs is not None:
        normalized = normalized.rio.write_crs(data.rio.crs)
    return normalized


def _reproject_and_normalize(
    data: xr.DataArray,
    reference_grid: xr.DataArray,
    *,
    resampling: Resampling,
) -> xr.DataArray:
    """Reproject a DataArray and normalize any x/y output back to canonical dims."""
    return _normalize_spatial_dataarray(
        reproject_to_grid(data, reference_grid, resampling=resampling)
    )


def _reference_grid_axis_step(reference_grid: xr.DataArray, dim: str) -> float:
    """Infer one spatial axis step for a regular reference grid."""
    coords = np.asarray(reference_grid.coords[dim].values, dtype=np.float64)
    if coords.size > 1:
        diffs = np.abs(np.diff(coords))
        nonzero = diffs[diffs > 0]
        if nonzero.size > 0:
            return float(nonzero[0])

    attr_resolution = reference_grid.attrs.get("comparison_resolution_deg")
    if attr_resolution is not None:
        return float(attr_resolution)

    try:
        x_res, y_res = reference_grid.rio.resolution()
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise ValueError(
            f"Could not infer spatial step for {dim!r} from reference grid"
        ) from exc

    if dim in {"lon", "x"}:
        return abs(float(x_res))
    return abs(float(y_res))


def _reference_grid_resolution_m(reference_grid: xr.DataArray) -> float:
    """Return the approximate spatial resolution in metres for a WGS84 grid."""
    _, x_dim = _reference_grid_dims(reference_grid)
    return _reference_grid_axis_step(reference_grid, x_dim) * 111_320


def _bbox_from_reference_grid(reference_grid: xr.DataArray) -> BBox:
    """Compute the lon/lat bbox covered by a reference grid.

    The coordinates stored on the comparison grid are pixel centres, so the
    bbox must expand by half a cell on each side. This keeps single-cell chunks
    non-degenerate and prevents chunk-wise loads from clipping away edge data.
    """
    y_dim, x_dim = _reference_grid_dims(reference_grid)
    lats = reference_grid.coords[y_dim].values
    lons = reference_grid.coords[x_dim].values
    lat_step = _reference_grid_axis_step(reference_grid, y_dim)
    lon_step = _reference_grid_axis_step(reference_grid, x_dim)
    return (
        float(max(-180.0, np.min(lons) - lon_step / 2)),
        float(max(-90.0, np.min(lats) - lat_step / 2)),
        float(min(180.0, np.max(lons) + lon_step / 2)),
        float(min(90.0, np.max(lats) + lat_step / 2)),
    )


def _coord_bbox_from_grid(reference_grid: xr.DataArray) -> BBox:
    """Compute the exact coord-center bbox covered by a reference-grid subset."""

    y_dim, x_dim = _reference_grid_dims(reference_grid)
    lats = np.asarray(reference_grid.coords[y_dim].values, dtype=np.float64)
    lons = np.asarray(reference_grid.coords[x_dim].values, dtype=np.float64)
    return (
        float(np.min(lons)),
        float(np.min(lats)),
        float(np.max(lons)),
        float(np.max(lats)),
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


def _axis_index_span_for_bounds(
    reference_grid: xr.DataArray,
    dim: str,
    lower: float,
    upper: float,
) -> tuple[int, int]:
    """Return the index span whose coord centers fall within one bbox interval."""

    coords = np.asarray(reference_grid.coords[dim].values, dtype=np.float64)
    if coords.size == 0:
        return (0, 0)

    step = _reference_grid_axis_step(reference_grid, dim)
    tolerance = max(1e-12, step * 0.25)
    if coords[0] <= coords[-1]:
        start = int(np.searchsorted(coords, lower - tolerance, side="left"))
        stop = int(np.searchsorted(coords, upper + tolerance, side="right"))
    else:
        ascending = coords[::-1]
        rev_start = int(np.searchsorted(ascending, lower - tolerance, side="left"))
        rev_stop = int(np.searchsorted(ascending, upper + tolerance, side="right"))
        start = max(0, len(coords) - rev_stop)
        stop = max(0, len(coords) - rev_start)

    start = max(0, min(start, len(coords)))
    stop = max(0, min(stop, len(coords)))
    if stop < start:
        return (0, 0)
    return (start, stop)


def _gwd30_chunks_for_bbox(
    reference_grid: xr.DataArray,
    *,
    chunk_cells: int,
    bbox: BBox,
) -> list[GridChunk]:
    """Return the chunk grid cells touched by one staged GWD30 tile bbox."""

    y_dim, x_dim = _reference_grid_dims(reference_grid)
    row_start, row_stop = _axis_index_span_for_bounds(
        reference_grid,
        y_dim,
        bbox[1],
        bbox[3],
    )
    col_start, col_stop = _axis_index_span_for_bounds(
        reference_grid,
        x_dim,
        bbox[0],
        bbox[2],
    )
    if row_stop <= row_start or col_stop <= col_start:
        return []

    height = int(reference_grid.sizes[y_dim])
    width = int(reference_grid.sizes[x_dim])
    row_chunk_start = row_start // chunk_cells
    row_chunk_stop = (row_stop - 1) // chunk_cells
    col_chunk_start = col_start // chunk_cells
    col_chunk_stop = (col_stop - 1) // chunk_cells

    chunks: list[GridChunk] = []
    for row_chunk in range(row_chunk_start, row_chunk_stop + 1):
        for col_chunk in range(col_chunk_start, col_chunk_stop + 1):
            chunk_row_start = row_chunk * chunk_cells
            chunk_col_start = col_chunk * chunk_cells
            chunks.append(
                GridChunk(
                    row_start=chunk_row_start,
                    row_stop=min(chunk_row_start + chunk_cells, height),
                    col_start=chunk_col_start,
                    col_stop=min(chunk_col_start + chunk_cells, width),
                )
            )
    return chunks


def _iter_grid_chunks(
    reference_grid: xr.DataArray,
    *,
    chunk_cells: int,
) -> Iterator[GridChunk]:
    """Yield spatial chunks covering the reference grid."""
    y_dim, x_dim = _reference_grid_dims(reference_grid)
    height = reference_grid.sizes[y_dim]
    width = reference_grid.sizes[x_dim]
    for row_start in range(0, height, chunk_cells):
        row_stop = min(row_start + chunk_cells, height)
        for col_start in range(0, width, chunk_cells):
            col_stop = min(col_start + chunk_cells, width)
            yield GridChunk(
                row_start=row_start,
                row_stop=row_stop,
                col_start=col_start,
                col_stop=col_stop,
            )


def _grid_chunk_view(reference_grid: xr.DataArray, chunk: GridChunk) -> xr.DataArray:
    """Extract one chunk view from the full reference grid."""
    y_dim, x_dim = _reference_grid_dims(reference_grid)
    chunk_grid = reference_grid.isel(
        {
            y_dim: slice(chunk.row_start, chunk.row_stop),
            x_dim: slice(chunk.col_start, chunk.col_stop),
        }
    )
    chunk_grid = chunk_grid.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=False)
    if reference_grid.rio.crs is not None:
        chunk_grid = chunk_grid.rio.write_crs(reference_grid.rio.crs, inplace=False)
    return chunk_grid


def _staging_dir_for_output(output_path: Path) -> Path:
    """Return the staging directory for chunk files of one final output."""
    return output_path.parent / "_staging" / output_path.stem


def _json_bbox(value: Any) -> BBox:
    """Coerce one JSON bbox payload into a validated bbox tuple."""

    if not isinstance(value, list | tuple) or len(value) != 4:
        raise ValueError(f"Expected bbox list of length 4, got {value!r}")
    west, south, east, north = (float(item) for item in value)
    return (west, south, east, north)


def _load_gwd30_staged_tiles_from_stage_shard_manifests(
    staging_root: Path,
) -> list[tuple[Path, BBox]]:
    """Restore staged GWD30 tile partial metadata from shard manifest JSON files."""

    manifest_paths = sorted(staging_root.glob("stage_shard_*.json"))
    if not manifest_paths:
        return []

    staged_by_path: dict[Path, BBox] = {}
    missing_paths: list[Path] = []
    for manifest_path in manifest_paths:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in payload.get("staged_tiles", []):
            stage_path = Path(item["path"])
            stage_bbox = _json_bbox(item["bbox"])
            if not stage_path.exists():
                missing_paths.append(stage_path)
                continue
            previous_bbox = staged_by_path.get(stage_path)
            if previous_bbox is not None and previous_bbox != stage_bbox:
                raise ValueError(
                    f"Conflicting bbox metadata for staged tile {stage_path}: "
                    f"{previous_bbox} vs {stage_bbox}"
                )
            staged_by_path[stage_path] = stage_bbox

    if missing_paths:
        logger.warning(
            "GWD30 merge restore skipped %d staged tile path(s) referenced by shard manifests "
            "because the files do not exist",
            len(missing_paths),
        )

    return sorted(staged_by_path.items(), key=lambda item: str(item[0]))


def _parse_chunk_from_path(path: Path) -> GridChunk:
    """Parse one staged chunk filename back into its grid slice token."""

    match = _CHUNK_PATH_PATTERN.match(path.name)
    if match is None:
        raise ValueError(f"Unrecognized staged chunk filename: {path.name}")
    return GridChunk(
        row_start=int(match.group("row_start")),
        row_stop=int(match.group("row_stop")),
        col_start=int(match.group("col_start")),
        col_stop=int(match.group("col_stop")),
    )


def _copy_netcdf_attrs(
    source: Any,
    target: Any,
    *,
    skip: set[str] | None = None,
) -> None:
    """Copy netCDF attrs from one object to another."""

    skipped = skip or set()
    for attr_name in source.ncattrs():
        if attr_name in skipped:
            continue
        target.setncattr(attr_name, source.getncattr(attr_name))


def _netcdf_variable_create_kwargs(
    source_var: Any,
    *,
    reference_grid: xr.DataArray,
) -> dict[str, Any]:
    """Translate one netCDF source variable layout into createVariable kwargs."""

    y_dim, x_dim = _reference_grid_dims(reference_grid)
    kwargs: dict[str, Any] = {}
    if "_FillValue" in source_var.ncattrs():
        kwargs["fill_value"] = source_var.getncattr("_FillValue")

    filters = source_var.filters()
    if filters.get("zlib"):
        kwargs["zlib"] = True
        kwargs["complevel"] = filters.get("complevel", 4)
        kwargs["shuffle"] = filters.get("shuffle", True)
        if filters.get("fletcher32"):
            kwargs["fletcher32"] = True

    chunking = source_var.chunking()
    if chunking == "contiguous":
        kwargs["contiguous"] = True
    elif isinstance(chunking, list | tuple):
        chunk_sizes: list[int] = []
        for dim_name, chunk_size in zip(source_var.dimensions, chunking, strict=False):
            if dim_name == y_dim:
                chunk_sizes.append(min(int(chunk_size), int(reference_grid.sizes[y_dim])))
            elif dim_name == x_dim:
                chunk_sizes.append(min(int(chunk_size), int(reference_grid.sizes[x_dim])))
            else:
                chunk_sizes.append(int(chunk_size))
        kwargs["chunksizes"] = tuple(chunk_sizes)

    return kwargs


def _validate_streaming_chunk_layout(
    *,
    chunk_path: Path,
    source: NetCDFDataset,
    reference_grid: xr.DataArray,
    chunk: GridChunk,
) -> None:
    """Validate that one staged chunk still matches the current reference grid."""

    y_dim, x_dim = _reference_grid_dims(reference_grid)
    y_size = int(reference_grid.sizes[y_dim])
    x_size = int(reference_grid.sizes[x_dim])
    if chunk.row_start < 0 or chunk.col_start < 0:
        raise ValueError(f"Negative staged chunk bounds are invalid: {chunk_path}")
    if chunk.row_stop > y_size or chunk.col_stop > x_size:
        raise ValueError(
            f"Staged chunk {chunk_path} exceeds the current reference grid bounds"
        )

    expected_height = chunk.row_stop - chunk.row_start
    expected_width = chunk.col_stop - chunk.col_start
    if y_dim not in source.dimensions or x_dim not in source.dimensions:
        raise ValueError(
            f"Staged chunk {chunk_path} is missing required spatial dimensions"
        )
    if len(source.dimensions[y_dim]) != expected_height:
        raise ValueError(
            f"Staged chunk {chunk_path} has {len(source.dimensions[y_dim])} {y_dim} cells; "
            f"expected {expected_height}"
        )
    if len(source.dimensions[x_dim]) != expected_width:
        raise ValueError(
            f"Staged chunk {chunk_path} has {len(source.dimensions[x_dim])} {x_dim} cells; "
            f"expected {expected_width}"
        )
    if y_dim not in source.variables or x_dim not in source.variables:
        raise ValueError(
            f"Staged chunk {chunk_path} is missing required spatial coordinate variables"
        )

    expected_y = np.asarray(
        reference_grid.coords[y_dim].values[chunk.row_start:chunk.row_stop],
        dtype=np.float64,
    )
    expected_x = np.asarray(
        reference_grid.coords[x_dim].values[chunk.col_start:chunk.col_stop],
        dtype=np.float64,
    )
    actual_y = np.asarray(source.variables[y_dim][:], dtype=np.float64)
    actual_x = np.asarray(source.variables[x_dim][:], dtype=np.float64)
    if actual_y.shape != expected_y.shape or not np.allclose(
        actual_y,
        expected_y,
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError(
            f"Staged chunk {chunk_path} has stale {y_dim} coordinates for the current grid"
        )
    if actual_x.shape != expected_x.shape or not np.allclose(
        actual_x,
        expected_x,
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError(
            f"Staged chunk {chunk_path} has stale {x_dim} coordinates for the current grid"
        )


def _stream_gwd30_staged_chunks(
    *,
    chunk_paths: list[Path],
    output_path: Path,
    reference_grid: xr.DataArray,
) -> None:
    """Pack staged GWD30 chunk files into one final netCDF without open_mfdataset."""

    y_dim, x_dim = _reference_grid_dims(reference_grid)
    temp_output_path = output_path.parent / (
        f".{output_path.name}.tmp-{os.getpid()}-{uuid4().hex}"
    )
    try:
        with (
            NetCDFDataset(chunk_paths[0], mode="r") as template,
            NetCDFDataset(temp_output_path, mode="w", format="NETCDF4") as target,
        ):
            _copy_netcdf_attrs(template, target)
            for dim_name, source_dim in template.dimensions.items():
                if dim_name == y_dim:
                    target.createDimension(dim_name, int(reference_grid.sizes[y_dim]))
                elif dim_name == x_dim:
                    target.createDimension(dim_name, int(reference_grid.sizes[x_dim]))
                else:
                    target.createDimension(
                        dim_name,
                        None if source_dim.isunlimited() else len(source_dim),
                    )

            for var_name, source_var in template.variables.items():
                target_var = target.createVariable(
                    var_name,
                    source_var.datatype,
                    source_var.dimensions,
                    **_netcdf_variable_create_kwargs(
                        source_var,
                        reference_grid=reference_grid,
                    ),
                )
                _copy_netcdf_attrs(source_var, target_var, skip={"_FillValue"})

            for var_name, source_var in template.variables.items():
                target_var = target.variables[var_name]
                if var_name == y_dim:
                    target_var[:] = np.asarray(
                        reference_grid.coords[y_dim].values,
                        dtype=source_var.dtype,
                    )
                    continue
                if var_name == x_dim:
                    target_var[:] = np.asarray(
                        reference_grid.coords[x_dim].values,
                        dtype=source_var.dtype,
                    )
                    continue
                if y_dim not in source_var.dimensions and x_dim not in source_var.dimensions:
                    target_var[...] = source_var[...]

            for chunk_path in chunk_paths:
                chunk = _parse_chunk_from_path(chunk_path)
                with NetCDFDataset(chunk_path, mode="r") as source:
                    _validate_streaming_chunk_layout(
                        chunk_path=chunk_path,
                        source=source,
                        reference_grid=reference_grid,
                        chunk=chunk,
                    )
                    for var_name, target_var in target.variables.items():
                        if var_name in {y_dim, x_dim}:
                            continue
                        if (
                            y_dim not in target_var.dimensions
                            and x_dim not in target_var.dimensions
                        ):
                            continue
                        if var_name not in source.variables:
                            raise ValueError(
                                f"Staged chunk {chunk_path} is missing expected variable {var_name}"
                            )
                        source_var = source.variables[var_name]
                        indexers: list[slice] = []
                        for dim_name in target_var.dimensions:
                            if dim_name == y_dim:
                                indexers.append(slice(chunk.row_start, chunk.row_stop))
                            elif dim_name == x_dim:
                                indexers.append(slice(chunk.col_start, chunk.col_stop))
                            else:
                                indexers.append(slice(None))
                        target_var[tuple(indexers)] = source_var[...]

        os.replace(temp_output_path, output_path)
    except Exception:
        try:
            temp_output_path.unlink()
        except FileNotFoundError:
            pass
        raise

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("  → %s (%.1f MB)", output_path.name, size_mb)


def _merge_staged_chunks(
    *,
    staging_dir: Path,
    output_path: Path,
    reference_grid: xr.DataArray,
    chunk_paths: list[Path] | None = None,
) -> None:
    """Merge spatial chunk files into the final yearly/static netCDF."""
    if chunk_paths is None:
        chunk_paths = sorted(staging_dir.glob("chunk_*.nc"))
    else:
        chunk_paths = sorted(path for path in chunk_paths if path.exists())
    if not chunk_paths:
        raise FileNotFoundError(f"No staged chunk files found in {staging_dir}")

    logger.info(
        "%s: merging %d staged chunk file(s) from %s",
        output_path.stem,
        len(chunk_paths),
        staging_dir,
    )
    if output_path.stem.startswith("gwd30_"):
        _stream_gwd30_staged_chunks(
            chunk_paths=chunk_paths,
            output_path=output_path,
            reference_grid=reference_grid,
        )
        return
    try:
        merged = xr.open_mfdataset(
            chunk_paths,
            combine="by_coords",
            parallel=False,
            engine="netcdf4",
            coords="minimal",
            compat="override",
            combine_attrs="override",
        )
    except ValueError as exc:
        invalid_paths = _find_invalid_staged_chunk_paths(chunk_paths, reference_grid)
        if invalid_paths:
            invalid_display = ", ".join(str(path) for path in invalid_paths[:3])
            if len(invalid_paths) > 3:
                invalid_display += f", ... ({len(invalid_paths)} total)"
            raise ValueError(
                f"{exc} Staged chunk file(s) are readable but incompatible with the current "
                f"merge contract: {invalid_display}. This usually means old chunk files were "
                "reused from a previous code version. Rerun with --no-skip-existing or let "
                "the current code rebuild those chunk files."
            ) from exc
        if "unable to decode time units" not in str(exc):
            raise
        raise ValueError(
            f"{exc} This usually means stale staged chunk files under {staging_dir} "
            "were reused from an older run. Rerun with --no-skip-existing to rebuild "
            "that staging directory."
        ) from exc
    except OSError as exc:
        bad_paths = _find_unreadable_netcdf_paths(chunk_paths)
        if not bad_paths:
            raise
        bad_display = ", ".join(str(path) for path in bad_paths[:3])
        if len(bad_paths) > 3:
            bad_display += f", ... ({len(bad_paths)} total)"
        raise OSError(
            f"{exc} Unreadable staged chunk file(s): {bad_display}. "
            "This usually means a staged chunk was truncated or corrupted during a "
            "previous run and then reused. Rerun with --no-skip-existing to rebuild "
            "that staging directory."
        ) from exc
    y_dim, x_dim = _reference_grid_dims(reference_grid)
    try:
        merged = merged.reindex(
            {
                y_dim: reference_grid.coords[y_dim].values,
                x_dim: reference_grid.coords[x_dim].values,
            }
        )
        _save_dataset(merged, output_path)
    finally:
        merged.close()


def _chunk_file_path(staging_dir: Path, chunk: GridChunk) -> Path:
    """Build the filename for one staged chunk file."""
    return staging_dir / f"chunk_{chunk.token}.nc"


def _chunk_cell_size(dataset_id: str) -> int:
    """Return the spatial chunk size in target-grid cells."""
    return _SPATIAL_CHUNK_CELLS.get(dataset_id, 512)


def _resolve_parallel_worker_count(worker_count: int | None = None) -> int:
    """Resolve a worker count from args, HPC env, or local CPU affinity."""

    if worker_count is not None and worker_count > 0:
        return worker_count

    for env_name in (
        "WA_STANDARDIZE_WORKERS",
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


def _chunk_parallel_worker_count(dataset_id: str) -> int:
    """Return a safe chunk-parallel worker count for one dataset.

    Only datasets whose chunk build path is currently verified to be safe under
    in-process threading are allowed to use multiple workers. NetCDF/HDF-backed
    loaders remain serial until they are moved to a process-safe strategy.
    """

    if dataset_id in _THREAD_SAFE_CHUNK_PARALLEL_DATASETS:
        return _resolve_parallel_worker_count()
    return 1


def _build_chunked_output(
    *,
    output_path: Path,
    reference_grid: xr.DataArray,
    chunk_cells: int,
    skip_existing: bool,
    desc: str,
    build_chunk_dataset: Callable[[xr.DataArray, BBox], xr.Dataset],
    max_workers: int = 1,
    log_chunk_start: bool = False,
) -> list[Path]:
    """Materialize a large output by staged spatial chunk files, then merge."""
    if skip_existing and output_path.exists():
        logger.info("  skipping %s (exists)", output_path.name)
        return [output_path]

    staging_dir = _staging_dir_for_output(output_path)
    if staging_dir.exists() and not skip_existing:
        stale_chunks = list(staging_dir.glob("chunk_*.nc"))
        for stale_chunk in stale_chunks:
            stale_chunk.unlink()
        if stale_chunks:
            logger.info(
                "%s: cleared %d stale staged chunk file(s)",
                output_path.stem,
                len(stale_chunks),
            )
    staging_dir.mkdir(parents=True, exist_ok=True)

    chunks = list(_iter_grid_chunks(reference_grid, chunk_cells=chunk_cells))
    written = 0
    skipped = 0
    expected_chunk_paths = [_chunk_file_path(staging_dir, chunk) for chunk in chunks]

    def process_chunk(chunk: GridChunk) -> str:
        chunk_path = _chunk_file_path(staging_dir, chunk)
        if skip_existing and chunk_path.exists():
            if _is_valid_staged_chunk(chunk_path, reference_grid):
                return "skipped"
            logger.warning(
                "%s: staged chunk %s is unreadable or incompatible, rebuilding",
                output_path.stem,
                chunk.token,
            )
            chunk_path.unlink(missing_ok=True)

        if log_chunk_start:
            logger.info("%s: starting chunk %s", output_path.stem, chunk.token)
        chunk_grid = _grid_chunk_view(reference_grid, chunk)
        chunk_bbox = _bbox_from_reference_grid(chunk_grid)
        try:
            chunk_dataset = build_chunk_dataset(chunk_grid, chunk_bbox)
        except FileNotFoundError:
            logger.debug("%s: no data for chunk %s", output_path.stem, chunk.token)
            return "missing"

        _save_dataset(chunk_dataset, chunk_path)
        del chunk_dataset
        gc.collect()
        return "written"

    if max_workers > 1 and len(chunks) > 1:
        progress = tqdm(
            total=len(chunks),
            desc=desc,
            unit="chunk",
            dynamic_ncols=True,
            mininterval=5.0,
        )
        progress.update(0)
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                chunk_iter = iter(chunks)
                active: dict[Any, GridChunk] = {}

                def submit_next() -> bool:
                    try:
                        next_chunk = next(chunk_iter)
                    except StopIteration:
                        return False
                    active[executor.submit(process_chunk, next_chunk)] = next_chunk
                    return True

                for _ in range(min(max_workers, len(chunks))):
                    if not submit_next():
                        break

                while active:
                    future = next(as_completed(tuple(active)))
                    chunk = active.pop(future)
                    progress.set_postfix_str(chunk.token, refresh=False)
                    try:
                        status = future.result()
                    except Exception as exc:
                        logger.error(
                            "%s: chunk %s failed (%s: %s)",
                            output_path.stem,
                            chunk.token,
                            type(exc).__name__,
                            exc,
                        )
                        raise
                    if status == "written":
                        written += 1
                    elif status == "skipped":
                        skipped += 1
                    progress.update(1)
                    submit_next()
        finally:
            progress.close()
    else:
        for chunk in tqdm(chunks, desc=desc):
            status = process_chunk(chunk)
            if status == "written":
                written += 1
            elif status == "skipped":
                skipped += 1

    logger.info(
        "%s: staged %d new chunk(s), reused %d existing chunk(s)",
        output_path.stem,
        written,
        skipped,
    )
    _merge_staged_chunks(
        staging_dir=staging_dir,
        output_path=output_path,
        reference_grid=reference_grid,
        chunk_paths=expected_chunk_paths,
    )
    return [output_path]


def _gwd30_rebucket_partial_path(
    rebucket_dir: Path,
    chunk: GridChunk,
    stage_path: Path,
) -> Path:
    """Build the filename for one rebucketed chunk-local GWD30 contribution."""

    return rebucket_dir / f"chunk_{chunk.token}__{stage_path.name}"


def _build_gwd30_output_from_staged_tiles(
    *,
    loader: DatasetLoader,
    output_path: Path,
    reference_grid: xr.DataArray,
    staged_tiles: list[tuple[Path, BBox]],
    year: int,
    resolution_m: float,
    skip_existing: bool,
) -> list[Path]:
    """Rebucket staged GWD30 tiles by chunk, then merge only non-empty chunks."""

    if skip_existing and output_path.exists():
        logger.info("  skipping %s (exists)", output_path.name)
        return [output_path]

    merge_staged_tiles = getattr(loader, "merge_staged_time_fraction_tiles", None)
    if not callable(merge_staged_tiles):
        raise TypeError("GWD30 loader does not implement merge_staged_time_fraction_tiles()")

    staging_dir = _staging_dir_for_output(output_path)
    rebucket_dir = staging_dir / "rebucketed"
    staging_dir.mkdir(parents=True, exist_ok=True)
    rebucket_dir.mkdir(parents=True, exist_ok=True)

    if not skip_existing:
        stale_rebucketed = list(rebucket_dir.glob("chunk_*.nc"))
        for stale_path in stale_rebucketed:
            stale_path.unlink()
        stale_chunks = list(staging_dir.glob("chunk_*.nc"))
        for stale_chunk in stale_chunks:
            stale_chunk.unlink()
        if stale_rebucketed:
            logger.info(
                "%s: cleared %d stale rebucketed chunk partial(s)",
                output_path.stem,
                len(stale_rebucketed),
            )
        if stale_chunks:
            logger.info(
                "%s: cleared %d stale merged chunk file(s)",
                output_path.stem,
                len(stale_chunks),
            )

    chunk_cells = _chunk_cell_size(loader.dataset_id)
    chunk_bbox_cache: dict[str, BBox] = {}
    chunk_by_token: dict[str, GridChunk] = {}
    tile_plans: list[tuple[Path, list[_Gwd30RebucketTarget]]] = []
    contribs_by_chunk: dict[str, list[tuple[Path, BBox]]] = defaultdict(list)

    for stage_path, stage_bbox in staged_tiles:
        targets: list[_Gwd30RebucketTarget] = []
        for chunk in _gwd30_chunks_for_bbox(
            reference_grid,
            chunk_cells=chunk_cells,
            bbox=stage_bbox,
        ):
            chunk_by_token[chunk.token] = chunk
            chunk_bbox = chunk_bbox_cache.get(chunk.token)
            if chunk_bbox is None:
                chunk_bbox = _bbox_from_reference_grid(_grid_chunk_view(reference_grid, chunk))
                chunk_bbox_cache[chunk.token] = chunk_bbox
            contribution_path = _gwd30_rebucket_partial_path(rebucket_dir, chunk, stage_path)
            target = _Gwd30RebucketTarget(
                chunk=chunk,
                contribution_path=contribution_path,
                contribution_bbox=chunk_bbox,
            )
            targets.append(target)
            contribs_by_chunk[chunk.token].append((contribution_path, chunk_bbox))
        if targets:
            tile_plans.append((stage_path, targets))

    if not tile_plans:
        raise FileNotFoundError(
            f"No staged GWD30 tiles intersect the requested reference grid for {output_path.name}"
        )

    logger.info(
        "%s: rebucket plan prepared %d staged tile(s) across %d non-empty chunk(s)",
        output_path.stem,
        len(tile_plans),
        len(contribs_by_chunk),
    )

    y_dim, x_dim = _reference_grid_dims(reference_grid)
    written_contribs = 0
    reused_contribs = 0
    for stage_path, targets in tqdm(
        tile_plans,
        desc=f"gwd30 {year} rebucket",
        unit="tile",
        dynamic_ncols=True,
        mininterval=5.0,
    ):
        pending_targets: list[_Gwd30RebucketTarget] = []
        for target in targets:
            if skip_existing and target.contribution_path.exists():
                if _is_readable_netcdf(target.contribution_path):
                    reused_contribs += 1
                    continue
                logger.warning(
                    "%s: rebucketed partial %s is unreadable, rebuilding",
                    output_path.stem,
                    target.contribution_path.name,
                )
                target.contribution_path.unlink(missing_ok=True)
            pending_targets.append(target)

        if not pending_targets:
            continue

        with xr.open_dataset(stage_path, engine="netcdf4") as source:
            stage_y = np.asarray(source.coords[y_dim].values)
            stage_x = np.asarray(source.coords[x_dim].values)
            for target in pending_targets:
                chunk_grid = _grid_chunk_view(reference_grid, target.chunk)
                chunk_y = np.asarray(chunk_grid.coords[y_dim].values)
                chunk_x = np.asarray(chunk_grid.coords[x_dim].values)
                y_indices = np.flatnonzero(np.isin(stage_y, chunk_y))
                x_indices = np.flatnonzero(np.isin(stage_x, chunk_x))
                if y_indices.size == 0 or x_indices.size == 0:
                    continue

                subset = (
                    source[["weighted", "coverage"]]
                    .isel({y_dim: y_indices, x_dim: x_indices})
                    .load()
                )
                if not np.any(np.asarray(subset["coverage"].values) > 0):
                    subset.close()
                    continue
                subset.attrs = {
                    **dict(subset.attrs),
                    "source": "gwd30_rebucketed_chunk_partial",
                    "source_stage_tile": stage_path.name,
                    "chunk_token": target.chunk.token,
                }
                _save_dataset(subset, target.contribution_path, log_output=False)
                subset.close()
                written_contribs += 1

    logger.info(
        "%s: rebucketed %d chunk contribution file(s), reused %d existing contribution(s)",
        output_path.stem,
        written_contribs,
        reused_contribs,
    )

    merged_chunk_paths: list[Path] = []
    written_chunks = 0
    reused_chunks = 0
    metadata_attrs = loader.metadata().to_attrs()
    for chunk_token in tqdm(
        sorted(contribs_by_chunk),
        desc=f"gwd30 {year} merge",
        unit="chunk",
        dynamic_ncols=True,
        mininterval=5.0,
    ):
        chunk = chunk_by_token[chunk_token]
        chunk_path = _chunk_file_path(staging_dir, chunk)
        if skip_existing and chunk_path.exists():
            if _is_valid_staged_chunk(chunk_path, reference_grid):
                merged_chunk_paths.append(chunk_path)
                reused_chunks += 1
                continue
            logger.warning(
                "%s: merged chunk %s is unreadable or incompatible, rebuilding",
                output_path.stem,
                chunk.token,
            )
            chunk_path.unlink(missing_ok=True)

        staged_contribs = [
            (contrib_path, contrib_bbox)
            for contrib_path, contrib_bbox in contribs_by_chunk[chunk_token]
            if contrib_path.exists()
        ]
        if not staged_contribs:
            continue

        chunk_grid = _grid_chunk_view(reference_grid, chunk)
        chunk_bbox = _bbox_from_reference_grid(chunk_grid)
        merge_index_cache = getattr(loader, "_merge_index_cache", None)
        if isinstance(merge_index_cache, dict):
            merge_index_cache.pop(year, None)
        chunk_dataset = merge_staged_tiles(
            staged_tiles=staged_contribs,
            reference_grid=chunk_grid,
            bbox=chunk_bbox,
            year=year,
        )
        chunk_dataset.attrs.update(metadata_attrs)
        chunk_dataset.attrs["standardized_resolution_m"] = resolution_m
        _save_dataset(chunk_dataset, chunk_path, log_output=False)
        chunk_dataset.close()
        merged_chunk_paths.append(chunk_path)
        written_chunks += 1

    if not merged_chunk_paths:
        raise FileNotFoundError(
            f"No rebucketed GWD30 chunk files were produced for {output_path.name}"
        )

    logger.info(
        "%s: merged %d non-empty chunk(s), reused %d existing merged chunk(s)",
        output_path.stem,
        written_chunks,
        reused_chunks,
    )
    _merge_staged_chunks(
        staging_dir=staging_dir,
        output_path=output_path,
        reference_grid=reference_grid,
        chunk_paths=sorted(merged_chunk_paths),
    )
    return [output_path]


# ---------------------------------------------------------------------------
# Year-range helpers
# ---------------------------------------------------------------------------

def _get_available_years(loader: DatasetLoader) -> list[int]:
    """Determine the list of years available for a dataset."""
    # Explicit years list in config (GWD30)
    years = loader.config.get("years")
    if isinstance(years, list) and years:
        return sorted(int(y) for y in years)

    # time_range in config
    time_range_cfg = loader.config.get("time_range")
    if isinstance(time_range_cfg, dict):
        start = str(time_range_cfg.get("start", ""))
        end = str(time_range_cfg.get("end", ""))
        start_year = int(start[:4]) if len(start) >= 4 else None
        end_year = int(end[:4]) if len(end) >= 4 else None
        if start_year is not None and end_year is not None:
            return list(range(start_year, end_year + 1))

    # TOPMODEL: discover from filesystem
    meta = loader.metadata()
    tc = meta.temporal_coverage
    if tc is not None:
        s, e = tc
        if s is not None and e is not None:
            return list(range(int(s[:4]), int(e[:4]) + 1))

    return []


def _filter_selected_years(
    dataset_id: str,
    available_years: list[int],
    selected_years: list[int] | None,
) -> list[int]:
    """Return the requested subset of years, validating against availability."""
    if selected_years is None:
        return available_years

    requested = sorted({int(year) for year in selected_years})
    available = set(available_years)
    missing = [year for year in requested if year not in available]
    if missing:
        available_display = ", ".join(str(year) for year in available_years) or "none"
        missing_display = ", ".join(str(year) for year in missing)
        raise ValueError(
            f"{dataset_id}: requested year(s) not available: {missing_display}. "
            f"Available years: {available_display}"
        )

    return [year for year in available_years if year in set(requested)]


# ---------------------------------------------------------------------------
# Per-dataset standardisation
# ---------------------------------------------------------------------------

def _standardize_g2017(
    loader: DatasetLoader,
    reference_grid: xr.DataArray,
    bbox: BBox,
    output_dir: Path,
    *,
    skip_existing: bool = False,
) -> list[Path]:
    """G2017: classification → per-class fraction via chunked average resampling."""
    output_path = output_dir / "g2017.nc"
    wetland_classes = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    peatland_classes = [0, 1]
    resolution_m = _reference_grid_resolution_m(reference_grid)
    chunk_workers = _chunk_parallel_worker_count(loader.dataset_id)

    def build_chunk(chunk_grid: xr.DataArray, chunk_bbox: BBox) -> xr.Dataset:
        raw = loader.load(bbox=chunk_bbox)
        wetland_fracs = classification_to_fractions(
            raw["wetland"], chunk_grid, wetland_classes, prefix="frac",
        )
        peatland_fracs = classification_to_fractions(
            raw["peatland"], chunk_grid, peatland_classes, prefix="peatland_frac",
        )
        dataset = xr.merge([wetland_fracs, peatland_fracs])
        dataset.attrs.update(loader.metadata().to_attrs())
        dataset.attrs["standardized_resolution_m"] = resolution_m
        return dataset

    return _build_chunked_output(
        output_path=output_path,
        reference_grid=reference_grid,
        chunk_cells=_chunk_cell_size(loader.dataset_id),
        skip_existing=skip_existing,
        desc="g2017 chunks",
        build_chunk_dataset=build_chunk,
        max_workers=chunk_workers,
    )


def _standardize_glwd(
    loader: DatasetLoader,
    reference_grid: xr.DataArray,
    bbox: BBox,
    output_dir: Path,
    *,
    skip_existing: bool = False,
) -> list[Path]:
    """GLWD v2: chunked ha bilinear → normalised fractions."""
    output_path = output_dir / "glwd_v2.nc"
    resolution_m = _reference_grid_resolution_m(reference_grid)
    chunk_workers = _chunk_parallel_worker_count(loader.dataset_id)

    def build_chunk(chunk_grid: xr.DataArray, chunk_bbox: BBox) -> xr.Dataset:
        raw = loader.load(bbox=chunk_bbox)
        dataset = glwd_ha_to_fractions(raw["area_by_class_ha"], chunk_grid)
        dataset.attrs.update(loader.metadata().to_attrs())
        dataset.attrs["standardized_resolution_m"] = resolution_m
        return dataset

    return _build_chunked_output(
        output_path=output_path,
        reference_grid=reference_grid,
        chunk_cells=_chunk_cell_size(loader.dataset_id),
        skip_existing=skip_existing,
        desc="glwd chunks",
        build_chunk_dataset=build_chunk,
        max_workers=chunk_workers,
    )


def _standardize_gwd30(
    loader: DatasetLoader,
    reference_grid: xr.DataArray,
    bbox: BBox,
    output_dir: Path,
    *,
    years: list[int] | None = None,
    skip_existing: bool = False,
) -> list[Path]:
    """GWD30: chunked per-year, per-timestep, per-class binary mask + average."""

    years = _filter_selected_years(
        loader.dataset_id,
        _get_available_years(loader),
        years,
    )
    if not years:
        logger.warning("GWD30: no years found")
        return []

    output_paths: list[Path] = []
    resolution_m = _reference_grid_resolution_m(reference_grid)
    for year in years:
        output_path = output_dir / f"gwd30_{year}.nc"
        logger.info("GWD30 %s: standardizing %s", year, output_path.name)
        if skip_existing and output_path.exists():
            logger.info("  skipping %s (exists)", output_path.name)
            output_paths.append(output_path)
            continue

        stage_tiles = getattr(loader, "stage_time_fraction_tiles", None)
        merge_staged_tiles = getattr(loader, "merge_staged_time_fraction_tiles", None)
        if not callable(stage_tiles) or not callable(merge_staged_tiles):
            raise TypeError(
                "GWD30 loader does not implement staged coarse time-fraction helpers()"
            )

        staging_root = _staging_dir_for_output(output_path)
        tile_stage_dir = staging_root / "tile_partials"
        if tile_stage_dir.exists() and not skip_existing:
            stale_stage_tiles = list(tile_stage_dir.glob("tile_*.nc"))
            for stale_stage_tile in stale_stage_tiles:
                stale_stage_tile.unlink()
            if stale_stage_tiles:
                logger.info(
                    "%s: cleared %d stale staged tile partial(s)",
                    output_path.stem,
                    len(stale_stage_tiles),
                )
        tile_stage_dir.mkdir(parents=True, exist_ok=True)

        staged_tiles = (
            _load_gwd30_staged_tiles_from_stage_shard_manifests(staging_root)
            if skip_existing
            else []
        )
        if staged_tiles:
            logger.info(
                "GWD30 %s: restored %d coarse tile partial(s) from shard manifests",
                year,
                len(staged_tiles),
            )
        else:
            staged_tiles = stage_tiles(
                bbox=bbox,
                reference_grid=reference_grid,
                year=year,
                staging_dir=tile_stage_dir,
                worker_count=_resolve_parallel_worker_count(),
                show_progress=True,
                skip_existing=skip_existing,
            )
        if not staged_tiles:
            logger.warning("GWD30 %d: no coarse tile partials were produced, skipping", year)
            continue
        logger.info("GWD30 %s: prepared %d coarse tile partial(s)", year, len(staged_tiles))

        try:
            output_paths.extend(
                _build_gwd30_output_from_staged_tiles(
                    loader=loader,
                    output_path=output_path,
                    reference_grid=reference_grid,
                    staged_tiles=staged_tiles,
                    year=year,
                    resolution_m=resolution_m,
                    skip_existing=skip_existing,
                )
            )
        except FileNotFoundError:
            logger.warning("GWD30 %d: no staged chunk files or raw data found, skipping", year)
            continue
        finally:
            # Clear per-year merge index cache to free memory
            if hasattr(loader, "_merge_index_cache") and year in loader._merge_index_cache:
                del loader._merge_index_cache[year]
                logger.debug("GWD30 %d: cleared merge index cache", year)

    return output_paths


def _reproject_dataarray_slices(
    data: xr.DataArray,
    reference_grid: xr.DataArray,
    *,
    resampling: Resampling,
) -> xr.DataArray:
    """Reproject one DataArray slice-by-slice over all non-spatial dimensions."""
    y_dim_src, x_dim_src = _dataarray_spatial_dims(data)
    if y_dim_src is None or x_dim_src is None:
        return data

    non_spatial_dims = [dim for dim in data.dims if dim not in {y_dim_src, x_dim_src}]
    if not non_spatial_dims:
        result = _reproject_and_normalize(data, reference_grid, resampling=resampling)
        result.attrs = data.attrs
        return result

    stacked = data.stack(_reproject_sample=non_spatial_dims)
    slices: list[xr.DataArray] = []
    for sample_position in range(stacked.sizes["_reproject_sample"]):
        sample = stacked.isel(_reproject_sample=sample_position, drop=True)
        reproj = _reproject_and_normalize(sample, reference_grid, resampling=resampling)
        reproj = reproj.expand_dims(_reproject_sample=[sample_position])
        slices.append(reproj)

    result = xr.concat(slices, dim="_reproject_sample")
    result = result.assign_coords(
        _reproject_sample=stacked.coords["_reproject_sample"],
    ).unstack("_reproject_sample")
    y_dim_out, x_dim_out = _dataarray_spatial_dims(result)
    if y_dim_out is None or x_dim_out is None:
        return result
    result = result.transpose(*non_spatial_dims, y_dim_out, x_dim_out)
    result.attrs = data.attrs
    return result


def _reproject_per_timestep(
    dataset: xr.Dataset,
    reference_grid: xr.DataArray,
    *,
    resampling: Resampling = Resampling.bilinear,
) -> xr.Dataset:
    """Reproject one dataset slice-by-slice over every non-spatial dimension."""
    reprojected_vars: dict[str, xr.DataArray] = {}
    for var_name in dataset.data_vars:
        data = dataset[var_name]
        if any(dim in data.dims for dim in ("lat", "lon", "y", "x")):
            data = _reproject_dataarray_slices(
                data,
                reference_grid,
                resampling=resampling,
            )
        reprojected_vars[var_name] = data

    result = xr.Dataset(reprojected_vars, attrs=dataset.attrs)
    spatial_coord_names = {"lat", "lon", "latitude", "longitude", "x", "y", "spatial_ref"}
    for coord_name in dataset.coords:
        if coord_name not in result.coords and coord_name not in spatial_coord_names:
            result = result.assign_coords({coord_name: dataset[coord_name]})
    return result


def _standardize_continuous_yearly(
    loader: DatasetLoader,
    reference_grid: xr.DataArray,
    bbox: BBox,
    output_dir: Path,
    *,
    file_prefix: str,
    resampling: Resampling = Resampling.bilinear,
    years: list[int] | None = None,
    skip_existing: bool = False,
) -> list[Path]:
    """Chunked path for continuous time-series datasets, one file per year."""
    meta = loader.metadata()
    output_paths: list[Path] = []
    resolution_m = _reference_grid_resolution_m(reference_grid)
    chunk_workers = _chunk_parallel_worker_count(loader.dataset_id)
    open_time_series = getattr(loader, "open_time_series", None)

    if meta.is_static:
        output_path = output_dir / f"{file_prefix}.nc"

        def build_static_chunk(chunk_grid: xr.DataArray, chunk_bbox: BBox) -> xr.Dataset:
            raw = loader.load(bbox=chunk_bbox)
            dataset = _reproject_per_timestep(raw, chunk_grid, resampling=resampling)
            dataset = _clip_continuous(dataset)
            dataset.attrs.update(meta.to_attrs())
            dataset.attrs["standardized_resolution_m"] = resolution_m
            return dataset

        return _build_chunked_output(
            output_path=output_path,
            reference_grid=reference_grid,
            chunk_cells=_chunk_cell_size(loader.dataset_id),
            skip_existing=skip_existing,
            desc=f"{file_prefix} chunks",
            build_chunk_dataset=build_static_chunk,
            max_workers=chunk_workers,
        )

    years = _filter_selected_years(
        loader.dataset_id,
        _get_available_years(loader),
        years,
    )
    if not years:
        logger.warning("%s: no years found", file_prefix)
        return []

    for year in tqdm(years, desc=f"{file_prefix} years"):
        output_path = output_dir / f"{file_prefix}_{year}.nc"
        year_time_range: TimeRange = (f"{year}-01-01", f"{year}-12-31")
        if callable(open_time_series):
            try:
                year_source = open_time_series(bbox=bbox, time_range=year_time_range)
            except FileNotFoundError:
                logger.warning(
                    "%s %d: no staged chunk files or raw data found, skipping",
                    file_prefix,
                    year,
                )
                continue

            try:
                extra_dims: list[str] = []
                for dim_name in ("config", "forcing"):
                    if dim_name in year_source.sizes:
                        extra_dims.append(f"{dim_name}={year_source.sizes[dim_name]}")
                extra_suffix = f" ({', '.join(extra_dims)})" if extra_dims else ""
                logger.info(
                    "%s %s: opened %d time step(s) once for chunking%s",
                    file_prefix,
                    year,
                    year_source.sizes.get("time", 0),
                    extra_suffix,
                )

                def build_year_chunk(
                    chunk_grid: xr.DataArray,
                    chunk_bbox: BBox,
                    *,
                    source: xr.Dataset = year_source,
                ) -> xr.Dataset:
                    raw = apply_bbox(source, chunk_bbox)
                    dataset = _reproject_per_timestep(raw, chunk_grid, resampling=resampling)
                    dataset = _clip_continuous(dataset)
                    dataset.attrs.update(meta.to_attrs())
                    dataset.attrs["standardized_resolution_m"] = resolution_m
                    return dataset

                output_paths.extend(
                    _build_chunked_output(
                        output_path=output_path,
                        reference_grid=reference_grid,
                        chunk_cells=_chunk_cell_size(loader.dataset_id),
                        skip_existing=skip_existing,
                        desc=f"{file_prefix} {year} chunks",
                        build_chunk_dataset=build_year_chunk,
                        max_workers=chunk_workers,
                    )
                )
            finally:
                year_source.close()
            continue

        def build_year_chunk(
            chunk_grid: xr.DataArray,
            chunk_bbox: BBox,
            *,
            time_range: TimeRange = year_time_range,
        ) -> xr.Dataset:
            raw = loader.load(bbox=chunk_bbox, time_range=time_range)
            dataset = _reproject_per_timestep(raw, chunk_grid, resampling=resampling)
            dataset = _clip_continuous(dataset)
            dataset.attrs.update(meta.to_attrs())
            dataset.attrs["standardized_resolution_m"] = resolution_m
            return dataset

        try:
            output_paths.extend(
                _build_chunked_output(
                    output_path=output_path,
                    reference_grid=reference_grid,
                    chunk_cells=_chunk_cell_size(loader.dataset_id),
                    skip_existing=skip_existing,
                    desc=f"{file_prefix} {year} chunks",
                    build_chunk_dataset=build_year_chunk,
                    max_workers=chunk_workers,
                )
            )
        except FileNotFoundError:
            logger.warning(
                "%s %d: no staged chunk files or raw data found, skipping",
                file_prefix,
                year,
            )
            continue

    return output_paths


def _clip_continuous(dataset: xr.Dataset) -> xr.Dataset:
    """Clip all data variables to [0, 1]."""
    for var_name in dataset.data_vars:
        dataset[var_name] = dataset[var_name].clip(0, 1)
    return dataset


def _standardize_berkeley(
    loader: DatasetLoader,
    reference_grid: xr.DataArray,
    bbox: BBox,
    output_dir: Path,
    *,
    years: list[int] | None = None,
    skip_existing: bool = False,
) -> list[Path]:
    """Berkeley: open monthly files once per year, then process larger coarse chunks."""
    years = _filter_selected_years(
        loader.dataset_id,
        _get_available_years(loader),
        years,
    )
    if not years:
        logger.warning("berkeley_rwawc: no years found")
        return []

    open_time_series = getattr(loader, "open_time_series", None)
    if not callable(open_time_series):
        raise TypeError("Berkeley loader does not implement open_time_series()")

    meta = loader.metadata()
    output_paths: list[Path] = []
    resolution_m = _reference_grid_resolution_m(reference_grid)

    for year in tqdm(years, desc="berkeley years"):
        output_path = output_dir / f"berkeley_rwawc_{year}.nc"
        year_time_range: TimeRange = (f"{year}-01-01", f"{year}-12-31")

        if skip_existing and output_path.exists():
            logger.info("  skipping %s (exists)", output_path.name)
            output_paths.append(output_path)
            continue

        try:
            year_source = open_time_series(year_time_range)
        except FileNotFoundError:
            logger.warning(
                "berkeley_rwawc %d: no staged chunk files or raw data found, skipping",
                year,
            )
            continue

        try:
            year_source = apply_bbox(year_source, bbox)
            logger.info(
                "berkeley_rwawc %s: opened %d monthly source slice(s) once for chunking",
                year,
                year_source.sizes.get("time", 0),
            )

            def build_year_chunk(
                chunk_grid: xr.DataArray,
                chunk_bbox: BBox,
                *,
                source: xr.Dataset = year_source,
            ) -> xr.Dataset:
                raw = apply_bbox(source, chunk_bbox)
                dataset = _reproject_per_timestep(
                    raw,
                    chunk_grid,
                    resampling=Resampling.average,
                )
                dataset = _clip_continuous(dataset)
                dataset.attrs.update(meta.to_attrs())
                dataset.attrs["standardized_resolution_m"] = resolution_m
                return dataset

            output_paths.extend(
                _build_chunked_output(
                    output_path=output_path,
                    reference_grid=reference_grid,
                    chunk_cells=_chunk_cell_size(loader.dataset_id),
                    skip_existing=skip_existing,
                    desc=f"berkeley_rwawc {year} chunks",
                    build_chunk_dataset=build_year_chunk,
                    max_workers=1,
                )
            )
        finally:
            year_source.close()

    return output_paths


# ---------------------------------------------------------------------------
# Dataset dispatch
# ---------------------------------------------------------------------------

_DATASET_HANDLERS: dict[str, str] = {
    "g2017": "g2017",
    "glwd_v2": "glwd",
    "gwd30": "gwd30",
    "swamps": "continuous",
    "topmodel": "continuous",
    "wad2m": "continuous",
    "giems_mc": "continuous",
    "berkeley_rwawc": "berkeley",
}

_CONTINUOUS_FILE_PREFIXES: dict[str, str] = {
    "swamps": "swamps",
    "topmodel": "topmodel",
    "wad2m": "wad2m",
    "giems_mc": "giems_mc",
}


def standardize_dataset(
    loader: DatasetLoader,
    reference_grid: xr.DataArray,
    bbox: BBox,
    output_dir: Path,
    *,
    years: list[int] | None = None,
    skip_existing: bool = False,
) -> list[Path]:
    """Standardise one dataset onto the reference grid.

    Returns the list of output file paths written.
    """
    dataset_id = loader.dataset_id
    handler = _DATASET_HANDLERS.get(dataset_id)

    if handler == "g2017":
        if years is not None:
            raise ValueError("g2017 is static and does not support year filtering")
        return _standardize_g2017(
            loader, reference_grid, bbox, output_dir, skip_existing=skip_existing,
        )
    elif handler == "glwd":
        if years is not None:
            raise ValueError("glwd_v2 is static and does not support year filtering")
        return _standardize_glwd(
            loader, reference_grid, bbox, output_dir, skip_existing=skip_existing,
        )
    elif handler == "gwd30":
        return _standardize_gwd30(
            loader,
            reference_grid,
            bbox,
            output_dir,
            years=years,
            skip_existing=skip_existing,
        )
    elif handler == "berkeley":
        return _standardize_berkeley(
            loader,
            reference_grid,
            bbox,
            output_dir,
            years=years,
            skip_existing=skip_existing,
        )
    elif handler == "continuous":
        prefix = _CONTINUOUS_FILE_PREFIXES[dataset_id]
        return _standardize_continuous_yearly(
            loader, reference_grid, bbox, output_dir,
            file_prefix=prefix, years=years, skip_existing=skip_existing,
        )
    else:
        raise ValueError(f"No standardisation handler for dataset {dataset_id!r}")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

ALL_DATASET_IDS = list(_DATASET_HANDLERS.keys())


def standardize_all(
    dataset_configs: dict[str, dict[str, Any]],
    dataset_ids: list[str],
    bbox: BBox,
    reference_grid: xr.DataArray,
    output_dir: Path,
    *,
    years: list[int] | None = None,
    skip_existing: bool = False,
    config_path: str = "config/datasets.yaml",
    metadata_path: Path | None = None,
    write_metadata: bool = True,
) -> dict[str, Any]:
    """Standardise multiple datasets and write a ``metadata.json`` summary."""
    # Ensure loader modules are imported so the registry is populated.
    import WA.loaders.berkeley  # noqa: F401
    import WA.loaders.g2017  # noqa: F401
    import WA.loaders.glwd  # noqa: F401
    import WA.loaders.gwd30  # noqa: F401
    import WA.loaders.netcdf_generic  # noqa: F401
    import WA.loaders.swamps  # noqa: F401
    import WA.loaders.topmodel  # noqa: F401
    from WA.loaders.registry import get_loader

    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    resolution_m = _reference_grid_resolution_m(reference_grid)
    _, x_dim = _reference_grid_dims(reference_grid)
    resolution_deg = _reference_grid_axis_step(reference_grid, x_dim)

    for dataset_id in tqdm(dataset_ids, desc="Datasets"):
        if dataset_id not in dataset_configs:
            logger.warning("Dataset %s not found in config, skipping", dataset_id)
            results[dataset_id] = {"status": "skipped", "reason": "not in config"}
            continue

        logger.info("=== Standardising %s ===", dataset_id)
        try:
            loader = get_loader(dataset_id, dataset_configs[dataset_id])
            paths = standardize_dataset(
                loader,
                reference_grid,
                bbox,
                output_dir,
                years=years,
                skip_existing=skip_existing,
            )
            results[dataset_id] = {
                "status": "success",
                "files": [p.name for p in paths],
                "file_count": len(paths),
            }
        except Exception as exc:
            logger.exception("Failed to standardise %s", dataset_id)
            results[dataset_id] = {"status": "error", "error": str(exc)}

    # Write metadata
    if write_metadata:
        metadata = {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "parameters": {
                "resolution_m": resolution_m,
                "resolution_deg": resolution_deg,
                "bbox": list(bbox),
                "crs": "EPSG:4326",
            },
            "datasets": results,
        }
        if metadata_path is None:
            metadata_path = output_dir / "metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        logger.info("Metadata written to %s", metadata_path)

    return results
