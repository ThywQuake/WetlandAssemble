"""Phase 3.6 helpers for global 500m classification disagreement analysis."""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import ExitStack, nullcontext
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import numpy as np
import rioxarray  # noqa: F401
import xarray as xr
from netCDF4 import Dataset as NetCDFDataset

from WA.classification import (
    NON_WETLAND_UNIFIED_ID,
    WATER_UNIFIED_ID,
    class_to_unified_id,
    dataset_display_name,
    normalize_classification_dataset_id,
    source_class_ids,
    source_class_ids_by_unified_id,
    source_class_names,
    unified_class_ids,
    unified_class_names,
    unified_priority_order,
)
from WA.config import get_dataset_config
from WA.loaders import get_loader
from WA.loaders.base import BBox
from WA.loaders.gwd30 import phase36_reduce_staged_time_fraction_tile
from WA.standardize import _load_gwd30_staged_tiles_from_stage_shard_manifests
from WA.standardized_loader import StandardizedDataLoader

PHASE36_DATASET_IDS = ("g2017", "glwd_v2", "gwd30")
PHASE36_STATIC_DATASET_IDS = ("g2017", "glwd_v2")
DEFAULT_PHASE36_TARGET_YEAR = 2016
DEFAULT_PHASE36_LAT_CHUNK_SIZE = 512
DEFAULT_PHASE36_STANDARDIZED_DIR = Path("output/standardized")
DEFAULT_PHASE36_OUTPUT_DIR = Path("results/phase3.6")
DEFAULT_PHASE36_CACHE_DIR = Path("results/cache/phase3_6")
ENTROPY_HISTOGRAM_BINS = 1000
INVALID_CLASS_VALUE = np.int16(-1)
INVALID_COUNT_VALUE = np.int16(-1)
PHASE36_CACHE_VERSION = 4
PHASE36_CACHE_VERSION_ATTR = "wa_phase36_cache_version"
PHASE36_GWD30_REDUCE_NAME = "phase36_annual_unified"
PHASE36_GWD30_REDUCE_VERSION = 2

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Phase36Inputs:
    """Materialized dataset handles for one Phase 3.6 run."""

    datasets: dict[str, xr.Dataset]
    year: int
    bbox: BBox | None = None


@dataclass(frozen=True)
class Phase36OutputPaths:
    """Output paths produced by one Phase 3.6 run."""

    metrics_path: Path
    dominant_classes_path: Path
    summary_path: Path


@dataclass(frozen=True)
class Phase36GridTemplate:
    """Spatial grid metadata shared by all Phase 3.6 stage files."""

    y_dim: str
    x_dim: str
    lat_values: np.ndarray
    lon_values: np.ndarray


@dataclass(frozen=True)
class Phase36StaticStripeResult:
    """Computed static-dataset stripe payload ready for NetCDF write-out."""

    dataset_id: str
    row_start: int
    row_stop: int
    unified_values: np.ndarray
    source_dominant_values: np.ndarray
    valid_cell_count: int


def load_phase36_inputs(
    standardized_dir: str | Path = DEFAULT_PHASE36_STANDARDIZED_DIR,
    *,
    year: int = DEFAULT_PHASE36_TARGET_YEAR,
    bbox: BBox | None = None,
) -> Phase36Inputs:
    """Open the three standardized classification datasets used by Phase 3.6."""

    logger.info(
        "Phase3.6 inputs: standardized_dir=%s year=%s bbox=%s",
        standardized_dir,
        year,
        bbox,
    )
    loader = StandardizedDataLoader(standardized_dir)
    g2017 = loader.load("g2017", bbox=bbox)
    glwd_v2 = loader.load("glwd_v2", bbox=bbox)
    reference_grid = _build_phase36_reference_grid(g2017)
    datasets = {
        "g2017": g2017,
        "glwd_v2": glwd_v2,
        "gwd30": _load_phase36_gwd30(
            standardized_dir=standardized_dir,
            year=year,
            bbox=bbox,
            reference_grid=reference_grid,
        ),
    }
    _validate_spatial_grid(datasets)
    for dataset_id, dataset in datasets.items():
        y_dim, x_dim = _spatial_dims(dataset)
        logger.info(
            "Phase3.6 inputs ready: %s dims=%s x %s vars=%s",
            dataset_id,
            dataset.sizes[y_dim],
            dataset.sizes[x_dim],
            len(dataset.data_vars),
        )
    return Phase36Inputs(datasets=datasets, year=year, bbox=bbox)


def _load_phase36_standardized_dataset(
    standardized_dir: str | Path,
    dataset_id: str,
    *,
    bbox: BBox | None = None,
) -> xr.Dataset:
    loader = StandardizedDataLoader(standardized_dir)
    return loader.load(dataset_id, bbox=bbox)


def _load_phase36_static_inputs(
    standardized_dir: str | Path,
    *,
    bbox: BBox | None = None,
) -> dict[str, xr.Dataset]:
    return {
        dataset_id: _load_phase36_standardized_dataset(
            standardized_dir,
            dataset_id,
            bbox=bbox,
        )
        for dataset_id in PHASE36_STATIC_DATASET_IDS
    }


def _write_global_static_phase36_caches_from_standardized(
    *,
    standardized_dir: str | Path,
    dataset_id: str,
    cache_path: Path,
    source_dominant_cache_path: Path,
    grid_template: Phase36GridTemplate,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
) -> None:
    dataset = _load_phase36_standardized_dataset(
        standardized_dir,
        dataset_id,
        bbox=bbox,
    )
    try:
        _validate_grid_template_against_dataset(grid_template, dataset)
        _write_global_unified_fraction_cache(
            dataset_id=dataset_id,
            dataset=dataset,
            cache_path=cache_path,
            source_dominant_cache_path=source_dominant_cache_path,
            grid_template=grid_template,
            year=year,
            bbox=bbox,
            lat_chunk_size=lat_chunk_size,
        )
    finally:
        dataset.close()


def _compute_static_phase36_stripe_from_standardized(
    *,
    standardized_dir: str | Path,
    dataset_id: str,
    bbox: BBox | None,
    row_start: int,
    row_stop: int,
) -> Phase36StaticStripeResult:
    dataset = _load_phase36_standardized_dataset(
        standardized_dir,
        dataset_id,
        bbox=bbox,
    )
    try:
        lat_slice = slice(row_start, row_stop)
        unified = aggregate_source_fractions_to_unified(
            dataset_id,
            dataset,
            lat_slice=lat_slice,
        )
        source_dominant = compute_source_dominant_class(
            dataset_id,
            dataset,
            lat_slice=lat_slice,
        )
        return Phase36StaticStripeResult(
            dataset_id=dataset_id,
            row_start=row_start,
            row_stop=row_stop,
            unified_values=np.asarray(unified.values, dtype=np.float32),
            source_dominant_values=np.asarray(source_dominant.values, dtype=np.int16),
            valid_cell_count=int(compute_valid_mask(unified).sum().item()),
        )
    finally:
        dataset.close()


def _write_global_static_phase36_caches_parallel(
    *,
    standardized_dir: str | Path,
    dataset_ids: tuple[str, ...],
    unified_cache_paths: dict[str, Path],
    source_dominant_cache_paths: dict[str, Path],
    grid_template: Phase36GridTemplate,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
    worker_count: int,
) -> None:
    logger.info(
        "Phase3.6 stage[01] static stripe-parallel start: datasets=%s workers=%s",
        list(dataset_ids),
        worker_count,
    )
    class_ids = np.asarray(unified_class_ids(), dtype=np.int16)
    temp_paths = {
        dataset_id: _temp_output_path(unified_cache_paths[dataset_id]) for dataset_id in dataset_ids
    }
    source_temp_paths = {
        dataset_id: _temp_output_path(source_dominant_cache_paths[dataset_id])
        for dataset_id in dataset_ids
    }
    stripe_specs = [
        (dataset_id, row_start, min(len(grid_template.lat_values), row_start + lat_chunk_size))
        for dataset_id in dataset_ids
        for row_start in range(0, len(grid_template.lat_values), lat_chunk_size)
    ]
    try:
        with ExitStack() as stack:
            unified_targets: dict[str, NetCDFDataset] = {}
            source_targets: dict[str, NetCDFDataset] = {}
            for dataset_id in dataset_ids:
                unified_target = stack.enter_context(
                    NetCDFDataset(temp_paths[dataset_id], mode="w", format="NETCDF4")
                )
                source_target = stack.enter_context(
                    NetCDFDataset(source_temp_paths[dataset_id], mode="w", format="NETCDF4")
                )
                _initialize_unified_fraction_file(
                    unified_target,
                    grid_template=grid_template,
                    dataset_id=dataset_id,
                    year=year,
                    bbox=bbox,
                    class_ids=class_ids,
                    lat_chunk_size=lat_chunk_size,
                )
                _initialize_single_dominant_class_file(
                    source_target,
                    grid_template=grid_template,
                    dataset_id=dataset_id,
                    classification_level="source",
                    year=year,
                    bbox=bbox,
                    lat_chunk_size=lat_chunk_size,
                )
                unified_targets[dataset_id] = unified_target
                source_targets[dataset_id] = source_target

            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                future_to_spec = {
                    executor.submit(
                        _compute_static_phase36_stripe_from_standardized,
                        standardized_dir=standardized_dir,
                        dataset_id=dataset_id,
                        bbox=bbox,
                        row_start=row_start,
                        row_stop=row_stop,
                    ): (dataset_id, row_start, row_stop)
                    for dataset_id, row_start, row_stop in stripe_specs
                }
                for future in as_completed(future_to_spec):
                    dataset_id, row_start, row_stop = future_to_spec[future]
                    stripe = future.result()
                    unified_targets[dataset_id].variables["unified_fraction"][
                        :,
                        row_start:row_stop,
                        :,
                    ] = stripe.unified_values
                    source_targets[dataset_id].variables["dominant_class"][
                        row_start:row_stop,
                        :,
                    ] = stripe.source_dominant_values
                    logger.info(
                        "Phase3.6 stage[01] %s stripe done: %s valid_cells=%s [parallel]",
                        dataset_id,
                        _stripe_progress_text(
                            row_start=row_start,
                            row_stop=row_stop,
                            total_rows=len(grid_template.lat_values),
                        ),
                        stripe.valid_cell_count,
                    )

        for dataset_id in dataset_ids:
            unified_cache_paths[dataset_id].parent.mkdir(parents=True, exist_ok=True)
            source_dominant_cache_paths[dataset_id].parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp_paths[dataset_id], unified_cache_paths[dataset_id])
            os.replace(source_temp_paths[dataset_id], source_dominant_cache_paths[dataset_id])
            logger.info(
                "Phase3.6 stage[01] static stripe-parallel complete: dataset=%s cache=%s "
                "source_cache=%s",
                dataset_id,
                unified_cache_paths[dataset_id],
                source_dominant_cache_paths[dataset_id],
            )
    except Exception:
        for dataset_id in dataset_ids:
            for temp_path in (temp_paths[dataset_id], source_temp_paths[dataset_id]):
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
        raise


def aggregate_source_fractions_to_unified(
    dataset_id: str,
    dataset: xr.Dataset,
    *,
    lat_slice: slice | None = None,
) -> xr.DataArray:
    """Aggregate one standardized classification dataset to unified 8-class fractions."""

    normalized_id = normalize_classification_dataset_id(dataset_id)
    y_dim, x_dim = _spatial_dims(dataset)
    subset = dataset if lat_slice is None else dataset.isel({y_dim: lat_slice})

    reduced_sources: dict[int, xr.DataArray] = {}
    for source_class_id, _unified_id in sorted(
        _dataset_class_to_unified(normalized_id).items(),
        key=lambda item: item[0],
    ):
        variable_name = f"frac_{source_class_id}"
        if variable_name not in subset.data_vars:
            continue
        reduced_sources[source_class_id] = _reduce_source_variable(
            subset[variable_name],
            variable_name=variable_name,
        )

    if not reduced_sources:
        raise ValueError(f"{dataset_id} has no standardized frac_* variables for Phase 3.6")

    base_valid = _valid_mask_from_source_arrays(tuple(reduced_sources.values()))
    template = next(iter(reduced_sources.values()))
    grouped_source_ids = source_class_ids_by_unified_id(normalized_id)

    unified_surfaces: list[xr.DataArray] = []
    for class_id in unified_class_ids():
        source_ids = grouped_source_ids.get(int(class_id), ())
        contributing = [
            reduced_sources[source_id]
            for source_id in source_ids
            if source_id in reduced_sources
        ]
        if contributing:
            combined = contributing[0]
            for data in contributing[1:]:
                combined = combined + data
        else:
            combined = xr.zeros_like(template, dtype=np.float32)
        combined = xr.where(base_valid, combined.astype(np.float32), np.nan).astype(np.float32)
        unified_surfaces.append(combined.expand_dims(class_id=[int(class_id)]))

    result = xr.concat(unified_surfaces, dim="class_id").transpose("class_id", y_dim, x_dim)
    result.name = "unified_fraction"
    result.attrs["dataset_id"] = normalized_id
    result.attrs["phase"] = "phase3.6"
    result.attrs["unified_class_names_json"] = json.dumps(unified_class_names(), sort_keys=True)
    return result


def _build_phase36_reference_grid(dataset: xr.Dataset) -> xr.DataArray:
    y_dim, x_dim = _spatial_dims(dataset)
    grid = xr.DataArray(
        np.zeros((dataset.sizes[y_dim], dataset.sizes[x_dim]), dtype=np.float32),
        dims=(y_dim, x_dim),
        coords={
            y_dim: dataset.coords[y_dim].values,
            x_dim: dataset.coords[x_dim].values,
        },
        name="phase36_reference_grid",
    )
    grid = grid.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=False)
    return grid.rio.write_crs("EPSG:4326", inplace=False)


def _phase36_reference_grid_bbox(reference_grid: xr.DataArray) -> BBox:
    y_dim, x_dim = _spatial_dims(reference_grid)
    lats = np.asarray(reference_grid.coords[y_dim].values, dtype=np.float64)
    lons = np.asarray(reference_grid.coords[x_dim].values, dtype=np.float64)
    return (
        float(np.min(lons)),
        float(np.min(lats)),
        float(np.max(lons)),
        float(np.max(lats)),
    )


def _load_phase36_gwd30(
    *,
    standardized_dir: str | Path,
    year: int,
    bbox: BBox | None,
    reference_grid: xr.DataArray,
) -> xr.Dataset:
    dataset_config = get_dataset_config("gwd30")
    loader = get_loader("gwd30", dataset_config)
    merge_staged_time_fraction_tiles = getattr(loader, "merge_staged_time_fraction_tiles", None)
    if not callable(merge_staged_time_fraction_tiles):
        raise TypeError(
            "Configured GWD30 loader does not expose merge_staged_time_fraction_tiles()"
        )
    staged_tiles = _load_phase36_gwd30_staged_tiles(standardized_dir, year=year)
    effective_bbox = bbox if bbox is not None else _phase36_reference_grid_bbox(reference_grid)
    logger.info(
        "Phase3.6 GWD30: merging %d staged tile partial(s) with reference grid, year=%s bbox=%s",
        len(staged_tiles),
        year,
        effective_bbox,
    )
    return merge_staged_time_fraction_tiles(
        staged_tiles=staged_tiles,
        bbox=effective_bbox,
        reference_grid=reference_grid,
        year=year,
    )


def _load_phase36_gwd30_staged_tiles(
    standardized_dir: str | Path,
    *,
    year: int,
) -> list[tuple[Path, BBox]]:
    staging_root = Path(standardized_dir) / "_staging" / f"gwd30_{year}"
    staged_tiles = _load_gwd30_staged_tiles_from_stage_shard_manifests(staging_root)
    if staged_tiles:
        logger.info(
            "Phase3.6 GWD30: restored %d staged tile partial(s) from manifests under %s",
            len(staged_tiles),
            staging_root,
        )
        return staged_tiles
    raise FileNotFoundError(
        "No staged GWD30 tile manifests were found under "
        f"{staging_root}. Expected stage_shard_*.json referencing tile_partials/tile_*.nc."
    )


def compute_joint_valid_mask(unified_fractions: dict[str, xr.DataArray]) -> xr.DataArray:
    """Return the mask of cells where all three datasets are valid."""

    if set(unified_fractions) != set(PHASE36_DATASET_IDS):
        raise ValueError(
            "Phase 3.6 joint-valid mask requires exactly g2017, glwd_v2, and gwd30"
        )

    valid_masks = {
        dataset_id: compute_valid_mask(fractions)
        for dataset_id, fractions in unified_fractions.items()
    }
    return combine_valid_masks(valid_masks)


def combine_valid_masks(valid_masks: dict[str, xr.DataArray]) -> xr.DataArray:
    """Return the mask of cells where all three datasets are valid."""

    if set(valid_masks) != set(PHASE36_DATASET_IDS):
        raise ValueError(
            "Phase 3.6 joint-valid mask requires exactly g2017, glwd_v2, and gwd30"
        )

    joint_valid = valid_masks["g2017"] & valid_masks["glwd_v2"] & valid_masks["gwd30"]
    joint_valid.name = "joint_valid_mask"
    joint_valid.attrs["phase"] = "phase3.6"
    return joint_valid.astype(bool)


def compute_valid_mask(unified_fractions: xr.DataArray) -> xr.DataArray:
    """Return whether one unified-fraction cube contains a usable cell."""

    finite_any = unified_fractions.notnull().any(dim="class_id")
    total = unified_fractions.fillna(0).sum(dim="class_id")
    valid = finite_any & (total > 0)
    valid.name = "valid_mask"
    return valid.astype(bool)


def compute_dominant_class(
    unified_fractions: xr.DataArray,
    *,
    valid_mask: xr.DataArray | None = None,
) -> xr.DataArray:
    """Return the dominant unified class with YAML priority tie-breaking."""

    if "class_id" not in unified_fractions.dims:
        raise ValueError("unified_fractions must include a class_id dimension")

    if valid_mask is None:
        valid_mask = compute_valid_mask(unified_fractions)

    class_ids = np.asarray(unified_fractions.coords["class_id"].values, dtype=np.int16)
    priority_lookup = _priority_rank_lookup(class_ids)
    values = np.asarray(unified_fractions.values, dtype=np.float32)
    valid = np.asarray(valid_mask.values, dtype=bool)
    safe_values = np.where(np.isfinite(values), values, -np.inf)
    safe_values = np.where(valid[None, ...], safe_values, -np.inf)
    max_values = safe_values.max(axis=0)
    is_candidate = np.isfinite(values) & np.isclose(
        safe_values,
        max_values[None, ...],
        rtol=0.0,
        atol=1e-12,
    ) & valid[None, ...]
    ranks = priority_lookup[:, None, None]
    masked_ranks = np.where(is_candidate, ranks, len(priority_lookup) + 1)
    chosen_index = np.argmin(masked_ranks, axis=0)
    chosen_class = class_ids[chosen_index].astype(np.int16)

    y_dim, x_dim = _spatial_dims(unified_fractions)
    dominant = xr.DataArray(
        chosen_class,
        dims=(y_dim, x_dim),
        coords={
            y_dim: unified_fractions.coords[y_dim].values,
            x_dim: unified_fractions.coords[x_dim].values,
        },
        name="dominant_class",
    )
    dominant = dominant.where(valid_mask, other=INVALID_CLASS_VALUE)
    dominant.attrs["phase"] = "phase3.6"
    dominant.attrs["priority_order_json"] = json.dumps(list(unified_priority_order()))
    return dominant.astype(np.int16)


def compute_source_dominant_class(
    dataset_id: str,
    dataset: xr.Dataset,
    *,
    lat_slice: slice | None = None,
) -> xr.DataArray:
    """Return the dominant source class using the raw standardized fractions."""

    y_dim, x_dim = _spatial_dims(dataset)
    subset = dataset if lat_slice is None else dataset.isel({y_dim: lat_slice})
    class_ids: list[int] = []
    layers: list[np.ndarray] = []

    for class_id in source_class_ids(dataset_id):
        variable_name = f"frac_{class_id}"
        if variable_name not in subset.data_vars:
            continue
        surface = subset[variable_name]
        if "time" in surface.dims:
            surface = surface.mean(dim="time", skipna=True)
        class_ids.append(int(class_id))
        layers.append(np.asarray(surface.values, dtype=np.float32))

    if not layers:
        raise ValueError(f"{dataset_id} has no raw frac_* variables available")

    stacked = np.stack(layers, axis=0)
    finite_any = np.isfinite(stacked).any(axis=0)
    totals = np.nansum(stacked, axis=0, dtype=np.float32)
    valid_mask = finite_any & (totals > 0)
    dominant_values = _compute_source_dominant_values(
        dataset_id,
        np.asarray(class_ids, dtype=np.int16),
        stacked,
        valid_mask=valid_mask,
    )

    dominant = xr.DataArray(
        dominant_values,
        dims=(y_dim, x_dim),
        coords={
            y_dim: subset.coords[y_dim].values,
            x_dim: subset.coords[x_dim].values,
        },
        name="source_dominant_class",
    )
    dominant.attrs["phase"] = "phase3.6"
    dominant.attrs["dataset_id"] = normalize_classification_dataset_id(dataset_id)
    dominant.attrs["classification_level"] = "source"
    dominant.attrs["dataset_display_name"] = dataset_display_name(dataset_id)
    dominant.attrs["source_class_names_json"] = json.dumps(
        source_class_names(dataset_id),
        sort_keys=True,
    )
    dominant.attrs["invalid_value"] = int(INVALID_CLASS_VALUE)
    if normalize_classification_dataset_id(dataset_id) == "gwd30":
        dominant.attrs["selection_rule"] = (
            "prefer_gwd30_wetland_source_classes_over_water_then_non_wetland"
        )
    return dominant.astype(np.int16)


def compute_source_dominant_class_from_fractions(
    dataset_id: str,
    source_fractions: xr.DataArray,
    *,
    valid_mask: xr.DataArray | None = None,
) -> xr.DataArray:
    """Return the dominant source class from a source-class fraction cube."""

    if "source_class_id" not in source_fractions.dims:
        raise ValueError("source_fractions must include a source_class_id dimension")

    if valid_mask is None:
        finite_any = source_fractions.notnull().any(dim="source_class_id")
        total = source_fractions.fillna(0).sum(dim="source_class_id")
        valid_mask = (finite_any & (total > 0)).astype(bool)

    source_ids = np.asarray(source_fractions.coords["source_class_id"].values, dtype=np.int16)
    values = np.asarray(source_fractions.values, dtype=np.float32)
    valid = np.asarray(valid_mask.values, dtype=bool)
    dominant_values = _compute_source_dominant_values(
        dataset_id,
        source_ids,
        values,
        valid_mask=valid,
    )

    y_dim, x_dim = _spatial_dims(source_fractions)
    dominant = xr.DataArray(
        dominant_values,
        dims=(y_dim, x_dim),
        coords={
            y_dim: source_fractions.coords[y_dim].values,
            x_dim: source_fractions.coords[x_dim].values,
        },
        name="source_dominant_class",
    )
    dominant.attrs["phase"] = "phase3.6"
    dominant.attrs["dataset_id"] = normalize_classification_dataset_id(dataset_id)
    dominant.attrs["classification_level"] = "source"
    dominant.attrs["dataset_display_name"] = dataset_display_name(dataset_id)
    dominant.attrs["source_class_names_json"] = json.dumps(
        source_class_names(dataset_id),
        sort_keys=True,
    )
    dominant.attrs["invalid_value"] = int(INVALID_CLASS_VALUE)
    if normalize_classification_dataset_id(dataset_id) == "gwd30":
        dominant.attrs["selection_rule"] = (
            "prefer_gwd30_wetland_source_classes_over_water_then_non_wetland"
        )
    return dominant.astype(np.int16)


def _compute_source_dominant_values(
    dataset_id: str,
    source_ids: np.ndarray,
    values: np.ndarray,
    *,
    valid_mask: np.ndarray,
) -> np.ndarray:
    safe_values = np.where(np.isfinite(values), values, -np.inf)
    safe_values = np.where(valid_mask[None, ...], safe_values, -np.inf)

    normalized_id = normalize_classification_dataset_id(dataset_id)
    if normalized_id == "gwd30":
        source_to_unified = class_to_unified_id(normalized_id)
        source_unified_ids = np.asarray(
            [source_to_unified[int(source_id)] for source_id in source_ids],
            dtype=np.int16,
        )
        wetland_mask = (
            (source_unified_ids != NON_WETLAND_UNIFIED_ID)
            & (source_unified_ids != WATER_UNIFIED_ID)
        )[:, None, None]
        water_mask = (source_unified_ids == WATER_UNIFIED_ID)[:, None, None]
        non_wetland_mask = (source_unified_ids == NON_WETLAND_UNIFIED_ID)[:, None, None]

        wetland_values = np.where(wetland_mask, safe_values, -np.inf)
        water_values = np.where(water_mask, safe_values, -np.inf)
        non_wetland_values = np.where(non_wetland_mask, safe_values, -np.inf)

        wetland_present = np.max(wetland_values, axis=0) > 0.0
        water_present = np.max(water_values, axis=0) > 0.0
        non_wetland_present = np.max(non_wetland_values, axis=0) > 0.0

        selected_values = np.where(
            wetland_present[None, ...],
            wetland_values,
            np.where(
                water_present[None, ...],
                water_values,
                np.where(non_wetland_present[None, ...], non_wetland_values, safe_values),
            ),
        )
    else:
        selected_values = safe_values

    chosen_index = np.argmax(selected_values, axis=0)
    dominant_values = source_ids[chosen_index].astype(np.int16)
    dominant_values[~valid_mask] = INVALID_CLASS_VALUE
    return dominant_values


def compute_gwd30_annual_dominant_class(
    unified_fractions: xr.DataArray,
    *,
    valid_mask: xr.DataArray | None = None,
) -> xr.DataArray:
    """Return the annual GWD30 dominant class using a wetland-first selection rule."""

    if "class_id" not in unified_fractions.dims:
        raise ValueError("unified_fractions must include a class_id dimension")

    if valid_mask is None:
        valid_mask = compute_valid_mask(unified_fractions)

    class_ids = np.asarray(unified_fractions.coords["class_id"].values, dtype=np.int16)
    values = np.asarray(unified_fractions.values, dtype=np.float32)
    valid = np.asarray(valid_mask.values, dtype=bool)
    safe_values = np.where(np.isfinite(values), values, -np.inf)
    safe_values = np.where(valid[None, ...], safe_values, -np.inf)

    wetland_mask = (
        (class_ids != NON_WETLAND_UNIFIED_ID) & (class_ids != WATER_UNIFIED_ID)
    )[:, None, None]
    fallback_mask = (
        (class_ids == NON_WETLAND_UNIFIED_ID) | (class_ids == WATER_UNIFIED_ID)
    )[:, None, None]

    wetland_values = np.where(wetland_mask, safe_values, -np.inf)
    wetland_present = np.max(wetland_values, axis=0) > 0.0
    selected_values = np.where(
        wetland_present[None, ...],
        wetland_values,
        np.where(fallback_mask, safe_values, -np.inf),
    )

    max_values = selected_values.max(axis=0)
    is_candidate = np.isfinite(selected_values) & np.isclose(
        selected_values,
        max_values[None, ...],
        rtol=0.0,
        atol=1e-12,
    ) & valid[None, ...]
    priority_lookup = _priority_rank_lookup(class_ids)
    masked_ranks = np.where(is_candidate, priority_lookup[:, None, None], len(class_ids) + 1)
    chosen_index = np.argmin(masked_ranks, axis=0)
    chosen_class = class_ids[chosen_index].astype(np.int16)

    y_dim, x_dim = _spatial_dims(unified_fractions)
    dominant = xr.DataArray(
        chosen_class,
        dims=(y_dim, x_dim),
        coords={
            y_dim: unified_fractions.coords[y_dim].values,
            x_dim: unified_fractions.coords[x_dim].values,
        },
        name="dominant_class",
    )
    dominant = dominant.where(valid_mask, other=INVALID_CLASS_VALUE)
    dominant.attrs["phase"] = "phase3.6"
    dominant.attrs["priority_order_json"] = json.dumps(list(unified_priority_order()))
    dominant.attrs["selection_rule"] = (
        "prefer_wetland_classes_over_non_wetland_and_water_for_gwd30_annual_aggregation"
    )
    dominant.attrs["fallback_class_ids_json"] = json.dumps(
        [NON_WETLAND_UNIFIED_ID, WATER_UNIFIED_ID]
    )
    return dominant.astype(np.int16)


def compute_vote_entropy(
    dominant_classes: dict[str, xr.DataArray],
    *,
    joint_valid_mask: xr.DataArray,
) -> xr.Dataset:
    """Compute vote-based normalized Shannon entropy on the joint-valid domain."""

    if set(dominant_classes) != set(PHASE36_DATASET_IDS):
        raise ValueError(
            "Phase 3.6 vote entropy requires exactly g2017, glwd_v2, and gwd30 dominant classes"
        )

    votes = np.stack(
        [
            np.asarray(dominant_classes[dataset_id].values, dtype=np.int16)
            for dataset_id in PHASE36_DATASET_IDS
        ],
        axis=0,
    )
    joint_valid = np.asarray(joint_valid_mask.values, dtype=bool)
    class_ids = np.asarray(unified_class_ids(), dtype=np.int16)
    class_counts = np.zeros((len(class_ids), *joint_valid.shape), dtype=np.int16)
    for index, class_id in enumerate(class_ids):
        class_counts[index] = np.sum(votes == class_id, axis=0, dtype=np.int16)

    agreement_count = class_counts.max(axis=0).astype(np.int16)
    majority_class = _majority_class_from_vote_counts(class_counts, class_ids)
    entropy = _entropy_from_vote_counts(class_counts, joint_valid=joint_valid).astype(np.float32)

    y_dim, x_dim = _spatial_dims(joint_valid_mask)
    coords = {
        y_dim: joint_valid_mask.coords[y_dim].values,
        x_dim: joint_valid_mask.coords[x_dim].values,
    }

    result = xr.Dataset(
        {
            "entropy": xr.DataArray(
                entropy,
                dims=(y_dim, x_dim),
                coords=coords,
                attrs={
                    "long_name": "Normalized Shannon entropy of dominant-class votes",
                    "normalization": "log2(3)",
                    "units": "1",
                },
            ),
            "majority_class": xr.DataArray(
                np.where(joint_valid, majority_class, INVALID_CLASS_VALUE).astype(np.int16),
                dims=(y_dim, x_dim),
                coords=coords,
                attrs={
                    "long_name": "Majority class across the three classification datasets",
                    "invalid_value": int(INVALID_CLASS_VALUE),
                },
            ),
            "agreement_count": xr.DataArray(
                np.where(joint_valid, agreement_count, INVALID_COUNT_VALUE).astype(np.int16),
                dims=(y_dim, x_dim),
                coords=coords,
                attrs={
                    "long_name": "Number of datasets agreeing on the majority class",
                    "invalid_value": int(INVALID_COUNT_VALUE),
                },
            ),
            "joint_valid_mask": xr.DataArray(
                joint_valid.astype(np.int8),
                dims=(y_dim, x_dim),
                coords=coords,
                attrs={
                    "long_name": "Cells where g2017, glwd_v2, and gwd30 are all valid",
                    "flag_values": [0, 1],
                    "flag_meanings": "not_joint_valid joint_valid",
                },
            ),
        }
    )
    result.attrs["phase"] = "phase3.6"
    result.attrs["dataset_ids_json"] = json.dumps(list(PHASE36_DATASET_IDS))
    result.attrs["unified_class_names_json"] = json.dumps(unified_class_names(), sort_keys=True)
    return result


def build_joint_dominant_class_dataset(
    dominant_classes: dict[str, xr.DataArray],
    *,
    joint_valid_mask: xr.DataArray,
    source_dominant_classes: dict[str, xr.DataArray] | None = None,
) -> xr.Dataset:
    """Return the per-dataset dominant-class surfaces restricted to joint-valid cells."""

    if set(dominant_classes) != set(PHASE36_DATASET_IDS):
        raise ValueError(
            "Phase 3.6 dominant-class export requires exactly g2017, glwd_v2, and gwd30"
        )
    if source_dominant_classes is not None and set(source_dominant_classes) != set(
        PHASE36_DATASET_IDS
    ):
        raise ValueError(
            "Phase 3.6 source dominant-class export requires exactly g2017, glwd_v2, and gwd30"
        )

    outputs: dict[str, xr.DataArray] = {}
    for dataset_id in PHASE36_DATASET_IDS:
        outputs[f"{dataset_id}_dominant_class"] = dominant_classes[dataset_id].where(
            joint_valid_mask,
            other=INVALID_CLASS_VALUE,
        ).astype(np.int16)
        if source_dominant_classes is not None:
            outputs[f"{dataset_id}_source_dominant_class"] = source_dominant_classes[
                dataset_id
            ].where(
                joint_valid_mask,
                other=INVALID_CLASS_VALUE,
            ).astype(np.int16)

    dataset = xr.Dataset(outputs)
    dataset.attrs["phase"] = "phase3.6"
    dataset.attrs["joint_valid_only"] = 1
    return dataset


def run_phase36_analysis(
    *,
    standardized_dir: str | Path = DEFAULT_PHASE36_STANDARDIZED_DIR,
    output_dir: str | Path = DEFAULT_PHASE36_OUTPUT_DIR,
    cache_dir: str | Path = DEFAULT_PHASE36_CACHE_DIR,
    year: int = DEFAULT_PHASE36_TARGET_YEAR,
    bbox: BBox | None = None,
    lat_chunk_size: int = DEFAULT_PHASE36_LAT_CHUNK_SIZE,
    static_worker_count: int | None = None,
    gwd30_worker_count: int | None = None,
    prefer_cache: bool = True,
    write_cache: bool = True,
) -> Phase36OutputPaths:
    """Execute the full Phase 3.6 workflow and write output products."""

    if lat_chunk_size <= 0:
        raise ValueError("lat_chunk_size must be positive")
    if static_worker_count is not None and static_worker_count <= 0:
        raise ValueError("static_worker_count must be positive when provided")

    logger.info(
        "Phase3.6 run start: standardized_dir=%s output_dir=%s cache_dir=%s year=%s bbox=%s "
        "lat_chunk_size=%s static_worker_count=%s gwd30_worker_count=%s "
        "prefer_cache=%s write_cache=%s",
        standardized_dir,
        output_dir,
        cache_dir,
        year,
        bbox,
        lat_chunk_size,
        static_worker_count,
        gwd30_worker_count,
        prefer_cache,
        write_cache,
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = _output_suffix(year=year, bbox=bbox)
    metrics_path = output_dir / f"phase3_6_entropy_{suffix}.nc"
    dominant_path = output_dir / f"phase3_6_unified_classes_{suffix}.nc"
    summary_path = output_dir / f"phase3_6_summary_{suffix}.json"
    cache_root = Path(cache_dir)
    stage_paths = _stage_cache_paths(
        cache_root,
        year=year,
        bbox=bbox,
        lat_chunk_size=lat_chunk_size,
    )
    logger.info(
        "Phase3.6 run paths: metrics=%s dominant=%s summary=%s cache_run_dir=%s",
        metrics_path,
        dominant_path,
        summary_path,
        stage_paths["run_dir"],
    )

    if (
        prefer_cache
        and stage_paths["metrics"].is_file()
        and stage_paths["dominant"].is_file()
        and stage_paths["summary"].is_file()
    ):
        logger.info("Phase3.6 cache shortcut: final staged outputs already complete; materializing")
        _materialize_cached_file(stage_paths["metrics"], metrics_path)
        _materialize_cached_file(stage_paths["dominant"], dominant_path)
        _write_output_summary_from_cache(
            cache_summary_path=stage_paths["summary"],
            output_summary_path=summary_path,
            metrics_path=metrics_path,
            dominant_path=dominant_path,
        )
        return Phase36OutputPaths(
            metrics_path=metrics_path,
            dominant_classes_path=dominant_path,
            summary_path=summary_path,
        )

    if not write_cache:
        logger.info(
            "Phase3.6 cache writes disabled: using a temporary staged workspace "
            "instead of the legacy in-memory direct path"
        )
        with tempfile.TemporaryDirectory(prefix="phase36-no-cache-", dir=output_dir) as temp_dir:
            return run_phase36_analysis(
                standardized_dir=standardized_dir,
                output_dir=output_dir,
                cache_dir=Path(temp_dir),
                year=year,
                bbox=bbox,
                lat_chunk_size=lat_chunk_size,
                prefer_cache=False,
                write_cache=True,
            )

    grid_template = None
    if prefer_cache:
        grid_template = _load_cached_grid_template(stage_paths["grid"])
    if grid_template is None:
        logger.info("Phase3.6 stage[00] grid template cache miss; deriving from source datasets")
        template_dataset = _load_phase36_standardized_dataset(
            standardized_dir,
            "g2017",
            bbox=bbox,
        )
        try:
            grid_template = _grid_template_from_dataset(template_dataset)
        finally:
            template_dataset.close()
        if write_cache:
            _save_cached_grid_template(
                stage_paths["grid"],
                grid_template,
                year=year,
                bbox=bbox,
            )
    else:
        logger.info(
            "Phase3.6 stage[00] grid template cache hit: y_dim=%s x_dim=%s rows=%s cols=%s",
            grid_template.y_dim,
            grid_template.x_dim,
            len(grid_template.lat_values),
            len(grid_template.lon_values),
        )

    assert grid_template is not None

    unified_cache_paths = {
        dataset_id: stage_paths[f"unified_{dataset_id}"]
        for dataset_id in PHASE36_STATIC_DATASET_IDS
    }
    static_source_dominant_cache_paths = {
        dataset_id: stage_paths[f"source_dominant_{dataset_id}"]
        for dataset_id in PHASE36_STATIC_DATASET_IDS
    }
    pending_static_dataset_ids: list[str] = []
    for dataset_id in PHASE36_STATIC_DATASET_IDS:
        cache_path = unified_cache_paths[dataset_id]
        source_cache_path = static_source_dominant_cache_paths[dataset_id]
        if (
            prefer_cache
            and _phase36_cache_file_is_current(cache_path)
            and _phase36_cache_file_is_current(source_cache_path)
        ):
            logger.info(
                "Phase3.6 cache hit: unified/source dominant %s <- %s, %s",
                dataset_id,
                cache_path,
                source_cache_path,
            )
            continue
        logger.info(
            "Phase3.6 cache miss: unified/source dominant %s -> %s, %s",
            dataset_id,
            cache_path,
            source_cache_path,
        )
        pending_static_dataset_ids.append(dataset_id)

    if pending_static_dataset_ids:
        static_parallel_workers = static_worker_count or 1
        if static_parallel_workers <= 1:
            logger.info(
                "Phase3.6 stage[01] static serial: datasets=%s",
                pending_static_dataset_ids,
            )
            for dataset_id in pending_static_dataset_ids:
                _write_global_static_phase36_caches_from_standardized(
                    standardized_dir=standardized_dir,
                    dataset_id=dataset_id,
                    cache_path=unified_cache_paths[dataset_id],
                    source_dominant_cache_path=static_source_dominant_cache_paths[dataset_id],
                    grid_template=grid_template,
                    year=year,
                    bbox=bbox,
                    lat_chunk_size=lat_chunk_size,
                )
        else:
            try:
                _write_global_static_phase36_caches_parallel(
                    standardized_dir=standardized_dir,
                    dataset_ids=tuple(pending_static_dataset_ids),
                    unified_cache_paths=unified_cache_paths,
                    source_dominant_cache_paths=static_source_dominant_cache_paths,
                    grid_template=grid_template,
                    year=year,
                    bbox=bbox,
                    lat_chunk_size=lat_chunk_size,
                    worker_count=static_parallel_workers,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Phase3.6 stage[01] static parallel failed; falling back to serial: "
                    "datasets=%s workers=%s",
                    pending_static_dataset_ids,
                    static_parallel_workers,
                )
                for dataset_id in pending_static_dataset_ids:
                    _write_global_static_phase36_caches_from_standardized(
                        standardized_dir=standardized_dir,
                        dataset_id=dataset_id,
                        cache_path=unified_cache_paths[dataset_id],
                        source_dominant_cache_path=static_source_dominant_cache_paths[dataset_id],
                        grid_template=grid_template,
                        year=year,
                        bbox=bbox,
                        lat_chunk_size=lat_chunk_size,
                    )

    if (
        prefer_cache
        and _phase36_cache_file_is_current(stage_paths["gwd30_valid"])
        and _phase36_cache_file_is_current(stage_paths["gwd30_dominant_single"])
        and _phase36_cache_file_is_current(stage_paths["gwd30_source_dominant_single"])
    ):
        logger.info(
            "Phase3.6 cache hit: gwd30 valid/dominant/source <- %s, %s, %s",
            stage_paths["gwd30_valid"],
            stage_paths["gwd30_dominant_single"],
            stage_paths["gwd30_source_dominant_single"],
        )
    else:
        logger.info(
            "Phase3.6 cache miss: gwd30 valid/dominant/source -> %s, %s, %s",
            stage_paths["gwd30_valid"],
            stage_paths["gwd30_dominant_single"],
            stage_paths["gwd30_source_dominant_single"],
        )
        _write_global_gwd30_phase36_caches(
            standardized_dir=standardized_dir,
            valid_cache_path=stage_paths["gwd30_valid"],
            dominant_cache_path=stage_paths["gwd30_dominant_single"],
            source_dominant_cache_path=stage_paths["gwd30_source_dominant_single"],
            reduced_tile_dir=stage_paths["gwd30_reduced_dir"],
            grid_template=grid_template,
            year=year,
            bbox=bbox,
            lat_chunk_size=lat_chunk_size,
            gwd30_worker_count=gwd30_worker_count,
            prefer_cache=prefer_cache,
        )

    if prefer_cache and _phase36_cache_file_is_current(stage_paths["joint_valid"]):
        logger.info(
            "Phase3.6 cache hit: joint_valid_mask <- %s",
            stage_paths["joint_valid"],
        )
    else:
        logger.info("Phase3.6 cache miss: joint_valid_mask -> %s", stage_paths["joint_valid"])
        _write_global_joint_valid_cache(
            cache_path=stage_paths["joint_valid"],
            static_unified_cache_paths=unified_cache_paths,
            gwd30_valid_cache_path=stage_paths["gwd30_valid"],
            grid_template=grid_template,
            year=year,
            bbox=bbox,
            lat_chunk_size=lat_chunk_size,
        )

    if prefer_cache and _phase36_cache_file_is_current(stage_paths["dominant"]):
        logger.info(
            "Phase3.6 cache hit: dominant_classes <- %s",
            stage_paths["dominant"],
        )
    else:
        logger.info("Phase3.6 cache miss: dominant_classes -> %s", stage_paths["dominant"])
        _write_global_dominant_cache(
            cache_path=stage_paths["dominant"],
            static_unified_cache_paths=unified_cache_paths,
            static_source_dominant_cache_paths=static_source_dominant_cache_paths,
            gwd30_dominant_cache_path=stage_paths["gwd30_dominant_single"],
            gwd30_source_dominant_cache_path=stage_paths["gwd30_source_dominant_single"],
            joint_valid_cache_path=stage_paths["joint_valid"],
            grid_template=grid_template,
            year=year,
            bbox=bbox,
            lat_chunk_size=lat_chunk_size,
        )

    if prefer_cache and _phase36_cache_file_is_current(stage_paths["metrics"]):
        logger.info("Phase3.6 cache hit: metrics <- %s", stage_paths["metrics"])
    else:
        logger.info("Phase3.6 cache miss: metrics -> %s", stage_paths["metrics"])
        _write_global_metrics_cache(
            cache_path=stage_paths["metrics"],
            dominant_cache_path=stage_paths["dominant"],
            joint_valid_cache_path=stage_paths["joint_valid"],
            grid_template=grid_template,
            year=year,
            bbox=bbox,
            lat_chunk_size=lat_chunk_size,
        )

    if prefer_cache and _phase36_cache_file_is_current(stage_paths["summary"]):
        logger.info("Phase3.6 cache hit: summary <- %s", stage_paths["summary"])
    else:
        logger.info("Phase3.6 cache miss: summary -> %s", stage_paths["summary"])
        _write_cached_summary(
            cache_path=stage_paths["summary"],
            metrics_cache_path=stage_paths["metrics"],
            grid_template=grid_template,
            year=year,
            bbox=bbox,
            lat_chunk_size=lat_chunk_size,
        )

    _materialize_cached_file(stage_paths["metrics"], metrics_path)
    _materialize_cached_file(stage_paths["dominant"], dominant_path)
    _write_output_summary_from_cache(
        cache_summary_path=stage_paths["summary"],
        output_summary_path=summary_path,
        metrics_path=metrics_path,
        dominant_path=dominant_path,
    )
    logger.info(
        "Phase3.6 run complete: metrics=%s dominant=%s summary=%s",
        metrics_path,
        dominant_path,
        summary_path,
    )

    return Phase36OutputPaths(
        metrics_path=metrics_path,
        dominant_classes_path=dominant_path,
        summary_path=summary_path,
    )


def _run_phase36_analysis_direct(
    *,
    standardized_dir: str | Path,
    metrics_path: Path,
    dominant_path: Path,
    summary_path: Path,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
) -> Phase36OutputPaths:
    logger.info(
        "Phase3.6 direct mode start: standardized_dir=%s year=%s bbox=%s lat_chunk_size=%s",
        standardized_dir,
        year,
        bbox,
        lat_chunk_size,
    )
    inputs = load_phase36_inputs(standardized_dir, year=year, bbox=bbox)
    template = inputs.datasets["g2017"]
    y_dim, x_dim = _spatial_dims(template)
    lat_values = np.asarray(template.coords[y_dim].values)
    lon_values = np.asarray(template.coords[x_dim].values)
    metrics_temp = _temp_output_path(metrics_path)
    dominant_temp = _temp_output_path(dominant_path)
    summary_builder = _StreamingPhase36Summary(lat_values=lat_values)

    try:
        with (
            NetCDFDataset(metrics_temp, mode="w", format="NETCDF4") as metrics_nc,
            NetCDFDataset(dominant_temp, mode="w", format="NETCDF4") as dominant_nc,
        ):
            _initialize_metrics_file(
                metrics_nc,
                lat_values=lat_values,
                lon_values=lon_values,
                y_dim=y_dim,
                x_dim=x_dim,
                year=year,
                bbox=bbox,
                lat_chunk_size=lat_chunk_size,
            )
            _initialize_dominant_file(
                dominant_nc,
                lat_values=lat_values,
                lon_values=lon_values,
                y_dim=y_dim,
                x_dim=x_dim,
                year=year,
                bbox=bbox,
                lat_chunk_size=lat_chunk_size,
            )

            for row_start in range(0, len(lat_values), lat_chunk_size):
                row_stop = min(len(lat_values), row_start + lat_chunk_size)
                lat_slice = slice(row_start, row_stop)
                logger.info(
                    "Phase3.6 direct stripe start: %s",
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(lat_values),
                    ),
                )
                unified = {
                    dataset_id: aggregate_source_fractions_to_unified(
                        dataset_id,
                        inputs.datasets[dataset_id],
                        lat_slice=lat_slice,
                    )
                    for dataset_id in PHASE36_DATASET_IDS
                }
                joint_valid = compute_joint_valid_mask(unified)
                dominant_classes = {
                    dataset_id: (
                        compute_gwd30_annual_dominant_class(
                            unified[dataset_id],
                            valid_mask=compute_valid_mask(unified[dataset_id]),
                        )
                        if dataset_id == "gwd30"
                        else compute_dominant_class(
                            unified[dataset_id],
                            valid_mask=compute_valid_mask(unified[dataset_id]),
                        )
                    )
                    for dataset_id in PHASE36_DATASET_IDS
                }
                source_dominant_classes = {
                    dataset_id: compute_source_dominant_class(
                        dataset_id,
                        inputs.datasets[dataset_id],
                        lat_slice=lat_slice,
                    )
                    for dataset_id in PHASE36_DATASET_IDS
                }
                metrics = compute_vote_entropy(
                    dominant_classes,
                    joint_valid_mask=joint_valid,
                )
                dominant_dataset = build_joint_dominant_class_dataset(
                    dominant_classes,
                    joint_valid_mask=joint_valid,
                    source_dominant_classes=source_dominant_classes,
                )
                _write_metrics_stripe(
                    metrics_nc,
                    metrics,
                    y_dim=y_dim,
                    x_dim=x_dim,
                    row_start=row_start,
                    row_stop=row_stop,
                )
                _write_dominant_stripe(
                    dominant_nc,
                    dominant_dataset,
                    y_dim=y_dim,
                    x_dim=x_dim,
                    row_start=row_start,
                    row_stop=row_stop,
                )
                summary_builder.update(
                    metrics=metrics,
                    row_start=row_start,
                    row_stop=row_stop,
                    y_dim=y_dim,
                )
                joint_valid_count = int(np.asarray(joint_valid.values, dtype=bool).sum())
                entropy_stats = _entropy_stats(metrics["entropy"])
                logger.info(
                    "Phase3.6 direct stripe done: %s joint_valid=%s entropy_mean=%s "
                    "entropy_min=%s entropy_max=%s",
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(lat_values),
                    ),
                    joint_valid_count,
                    _format_optional_float(entropy_stats["mean"]),
                    _format_optional_float(entropy_stats["min"]),
                    _format_optional_float(entropy_stats["max"]),
                )

        os.replace(metrics_temp, metrics_path)
        os.replace(dominant_temp, dominant_path)
    except Exception:
        for path in (metrics_temp, dominant_temp):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        for dataset in inputs.datasets.values():
            dataset.close()
        raise

    try:
        summary = summary_builder.to_dict(year=year, bbox=bbox)
        summary["metrics_path"] = str(metrics_path)
        summary["dominant_classes_path"] = str(dominant_path)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info(
            "Phase3.6 direct summary ready: joint_valid=%s area_weighted_entropy=%s path=%s",
            summary["joint_valid_cell_count"],
            _format_optional_float(summary["mean_entropy_area_weighted"]),
            summary_path,
        )
    finally:
        for dataset in inputs.datasets.values():
            dataset.close()

    return Phase36OutputPaths(
        metrics_path=metrics_path,
        dominant_classes_path=dominant_path,
        summary_path=summary_path,
    )


def _dataset_class_to_unified(dataset_id: str) -> dict[int, int]:
    return class_to_unified_id(dataset_id)


def _reduce_source_variable(data: xr.DataArray, *, variable_name: str) -> xr.DataArray:
    y_dim, x_dim = _spatial_dims(data)
    other_dims = [dim for dim in data.dims if dim not in {y_dim, x_dim}]
    if other_dims and other_dims != ["time"]:
        raise ValueError(
            f"{variable_name} has unsupported non-spatial dims for Phase 3.6: {other_dims}"
        )
    if "time" in other_dims:
        data = data.mean(dim="time", skipna=True)
    return data.astype(np.float32)


def _valid_mask_from_source_arrays(arrays: tuple[xr.DataArray, ...]) -> xr.DataArray:
    finite_any = xr.concat([array.notnull() for array in arrays], dim="_source").any("_source")
    total = xr.concat([array.fillna(0) for array in arrays], dim="_source").sum("_source")
    return (finite_any & (total > 0)).astype(bool)


def _spatial_dims(data: xr.Dataset | xr.DataArray) -> tuple[str, str]:
    dims = set(data.dims)
    if {"lat", "lon"}.issubset(dims):
        return "lat", "lon"
    if {"y", "x"}.issubset(dims):
        return "y", "x"
    raise ValueError(f"Expected spatial dims lat/lon or y/x, got {sorted(dims)}")


def _validate_spatial_grid(datasets: dict[str, xr.Dataset]) -> None:
    template_id = PHASE36_DATASET_IDS[0]
    template = datasets[template_id]
    y_dim, x_dim = _spatial_dims(template)
    template_y = np.asarray(template.coords[y_dim].values, dtype=np.float64)
    template_x = np.asarray(template.coords[x_dim].values, dtype=np.float64)

    for dataset_id in PHASE36_DATASET_IDS[1:]:
        dataset = datasets[dataset_id]
        other_y_dim, other_x_dim = _spatial_dims(dataset)
        other_y = np.asarray(dataset.coords[other_y_dim].values, dtype=np.float64)
        other_x = np.asarray(dataset.coords[other_x_dim].values, dtype=np.float64)
        if template_y.shape != other_y.shape or not np.allclose(
            template_y,
            other_y,
            rtol=0.0,
            atol=1e-12,
        ):
            raise ValueError(f"{dataset_id} does not share the template latitude grid")
        if template_x.shape != other_x.shape or not np.allclose(
            template_x,
            other_x,
            rtol=0.0,
            atol=1e-12,
        ):
            raise ValueError(f"{dataset_id} does not share the template longitude grid")


def _priority_rank_lookup(class_ids: np.ndarray) -> np.ndarray:
    ranks = {class_id: index for index, class_id in enumerate(unified_priority_order())}
    return np.asarray([ranks[int(class_id)] for class_id in class_ids], dtype=np.int16)


def _majority_class_from_vote_counts(
    class_counts: np.ndarray,
    class_ids: np.ndarray,
) -> np.ndarray:
    priority_ranks = _priority_rank_lookup(class_ids)
    best_count = class_counts.max(axis=0)
    is_candidate = class_counts == best_count[None, ...]
    masked_ranks = np.where(is_candidate, priority_ranks[:, None, None], len(class_ids) + 1)
    chosen_index = np.argmin(masked_ranks, axis=0)
    return class_ids[chosen_index].astype(np.int16)


def _entropy_from_vote_counts(
    class_counts: np.ndarray,
    *,
    joint_valid: np.ndarray,
) -> np.ndarray:
    entropy = np.zeros(joint_valid.shape, dtype=np.float32)
    for count in class_counts:
        probabilities = count.astype(np.float32) / np.float32(3.0)
        valid_probability = probabilities > 0
        contribution = np.zeros_like(probabilities, dtype=np.float32)
        contribution[valid_probability] = (
            probabilities[valid_probability]
            * np.log2(probabilities[valid_probability])
        )
        entropy -= contribution.astype(np.float32)
    normalizer = np.float32(math.log2(3.0))
    entropy = np.where(joint_valid, entropy / normalizer, np.nan).astype(np.float32)
    return entropy


def _initialize_metrics_file(
    target: NetCDFDataset,
    *,
    lat_values: np.ndarray,
    lon_values: np.ndarray,
    y_dim: str,
    x_dim: str,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int = DEFAULT_PHASE36_LAT_CHUNK_SIZE,
) -> None:
    _initialize_spatial_file(
        target,
        lat_values=lat_values,
        lon_values=lon_values,
        y_dim=y_dim,
        x_dim=x_dim,
        year=year,
        bbox=bbox,
    )
    target.createVariable(
        "entropy",
        "f4",
        (y_dim, x_dim),
        zlib=True,
        complevel=4,
        shuffle=True,
        fill_value=np.float32(np.nan),
        chunksizes=(min(lat_chunk_size, len(lat_values)), min(2048, len(lon_values))),
    )
    target.createVariable(
        "majority_class",
        "i2",
        (y_dim, x_dim),
        zlib=True,
        complevel=4,
        shuffle=True,
        chunksizes=(min(lat_chunk_size, len(lat_values)), min(2048, len(lon_values))),
    )
    target.createVariable(
        "agreement_count",
        "i2",
        (y_dim, x_dim),
        zlib=True,
        complevel=4,
        shuffle=True,
        chunksizes=(min(lat_chunk_size, len(lat_values)), min(2048, len(lon_values))),
    )
    target.createVariable(
        "joint_valid_mask",
        "i1",
        (y_dim, x_dim),
        zlib=True,
        complevel=4,
        shuffle=True,
        chunksizes=(min(lat_chunk_size, len(lat_values)), min(2048, len(lon_values))),
    )


def _initialize_dominant_file(
    target: NetCDFDataset,
    *,
    lat_values: np.ndarray,
    lon_values: np.ndarray,
    y_dim: str,
    x_dim: str,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int = DEFAULT_PHASE36_LAT_CHUNK_SIZE,
) -> None:
    _initialize_spatial_file(
        target,
        lat_values=lat_values,
        lon_values=lon_values,
        y_dim=y_dim,
        x_dim=x_dim,
        year=year,
        bbox=bbox,
    )
    for dataset_id in PHASE36_DATASET_IDS:
        target.createVariable(
            f"{dataset_id}_dominant_class",
            "i2",
            (y_dim, x_dim),
            zlib=True,
            complevel=4,
            shuffle=True,
            chunksizes=(min(lat_chunk_size, len(lat_values)), min(2048, len(lon_values))),
        )
        target.createVariable(
            f"{dataset_id}_source_dominant_class",
            "i2",
            (y_dim, x_dim),
            zlib=True,
            complevel=4,
            shuffle=True,
            chunksizes=(min(lat_chunk_size, len(lat_values)), min(2048, len(lon_values))),
        )


def _initialize_spatial_file(
    target: NetCDFDataset,
    *,
    lat_values: np.ndarray,
    lon_values: np.ndarray,
    y_dim: str,
    x_dim: str,
    year: int,
    bbox: BBox | None,
) -> None:
    target.setncattr("phase", "phase3.6")
    target.setncattr("target_year", int(year))
    target.setncattr("dataset_ids_json", json.dumps(list(PHASE36_DATASET_IDS)))
    target.setncattr("unified_class_names_json", json.dumps(unified_class_names(), sort_keys=True))
    if bbox is not None:
        target.setncattr("bbox_json", json.dumps(list(bbox)))

    target.createDimension(y_dim, len(lat_values))
    target.createDimension(x_dim, len(lon_values))
    lat_var = target.createVariable(y_dim, lat_values.dtype.str, (y_dim,))
    lon_var = target.createVariable(x_dim, lon_values.dtype.str, (x_dim,))
    lat_var[:] = lat_values
    lon_var[:] = lon_values
    if y_dim == "lat":
        lat_var.setncattr("units", "degrees_north")
        lon_var.setncattr("units", "degrees_east")


def _write_metrics_stripe(
    target: NetCDFDataset,
    metrics: xr.Dataset,
    *,
    y_dim: str,
    x_dim: str,
    row_start: int,
    row_stop: int,
) -> None:
    del x_dim
    target.variables["entropy"][row_start:row_stop, :] = np.asarray(
        metrics["entropy"].values,
        dtype=np.float32,
    )
    target.variables["majority_class"][row_start:row_stop, :] = np.asarray(
        metrics["majority_class"].values,
        dtype=np.int16,
    )
    target.variables["agreement_count"][row_start:row_stop, :] = np.asarray(
        metrics["agreement_count"].values,
        dtype=np.int16,
    )
    target.variables["joint_valid_mask"][row_start:row_stop, :] = np.asarray(
        metrics["joint_valid_mask"].values,
        dtype=np.int8,
    )


def _write_dominant_stripe(
    target: NetCDFDataset,
    dominant_dataset: xr.Dataset,
    *,
    y_dim: str,
    x_dim: str,
    row_start: int,
    row_stop: int,
) -> None:
    del y_dim, x_dim
    for dataset_id in PHASE36_DATASET_IDS:
        target.variables[f"{dataset_id}_dominant_class"][row_start:row_stop, :] = np.asarray(
            dominant_dataset[f"{dataset_id}_dominant_class"].values,
            dtype=np.int16,
        )
        if f"{dataset_id}_source_dominant_class" in dominant_dataset.data_vars:
            target.variables[f"{dataset_id}_source_dominant_class"][row_start:row_stop, :] = (
                np.asarray(
                    dominant_dataset[f"{dataset_id}_source_dominant_class"].values,
                    dtype=np.int16,
                )
            )


def _output_suffix(*, year: int, bbox: BBox | None) -> str:
    if bbox is None:
        return f"global_500m_{year}"
    west, south, east, north = bbox
    return (
        f"bbox_{west:g}_{south:g}_{east:g}_{north:g}_500m_{year}"
        .replace(".", "p")
        .replace("-", "m")
    )


def _stage_cache_paths(
    cache_root: Path,
    *,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
) -> dict[str, Path]:
    run_dir = (
        cache_root
        / _output_suffix(year=year, bbox=bbox)
        / f"lat_chunk_{lat_chunk_size}"
    )
    return {
        "run_dir": run_dir,
        "grid": run_dir / "00_grid_template.nc",
        "unified_g2017": run_dir / "01_g2017_unified_fraction.nc",
        "source_dominant_g2017": run_dir / "01_g2017_source_dominant_class.nc",
        "unified_glwd_v2": run_dir / "01_glwd_v2_unified_fraction.nc",
        "source_dominant_glwd_v2": run_dir / "01_glwd_v2_source_dominant_class.nc",
        "gwd30_reduced_dir": run_dir
        / f"01_gwd30_{PHASE36_GWD30_REDUCE_NAME}_v{PHASE36_GWD30_REDUCE_VERSION}",
        "gwd30_valid": run_dir / "01_gwd30_valid_mask.nc",
        "gwd30_dominant_single": run_dir / "01_gwd30_dominant_class.nc",
        "gwd30_source_dominant_single": run_dir / "01_gwd30_source_dominant_class.nc",
        "joint_valid": run_dir / "02_joint_valid_mask.nc",
        "dominant": run_dir / "03_dominant_classes.nc",
        "metrics": run_dir / "04_metrics.nc",
        "summary": run_dir / "05_summary.json",
    }


def _stripe_progress_text(
    *,
    row_start: int,
    row_stop: int,
    total_rows: int,
) -> str:
    percent = (row_stop / total_rows * 100.0) if total_rows > 0 else 100.0
    return (
        f"rows={row_start}:{row_stop}/{total_rows} "
        f"nrows={row_stop - row_start} percent={percent:.1f}%"
    )


def _entropy_stats(entropy: xr.DataArray) -> dict[str, float | None]:
    values = np.asarray(entropy.values, dtype=np.float64)
    finite = np.isfinite(values)
    if not finite.any():
        return {"mean": None, "min": None, "max": None}
    return {
        "mean": float(values[finite].mean()),
        "min": float(values[finite].min()),
        "max": float(values[finite].max()),
    }


def _format_optional_float(value: object) -> str:
    if value is None:
        return "nan"
    return f"{float(value):.6f}"


def _grid_template_from_dataset(dataset: xr.Dataset) -> Phase36GridTemplate:
    y_dim, x_dim = _spatial_dims(dataset)
    return Phase36GridTemplate(
        y_dim=y_dim,
        x_dim=x_dim,
        lat_values=np.asarray(dataset.coords[y_dim].values),
        lon_values=np.asarray(dataset.coords[x_dim].values),
    )


def _validate_grid_template_against_dataset(
    grid_template: Phase36GridTemplate,
    dataset: xr.Dataset,
) -> None:
    template = _grid_template_from_dataset(dataset)
    if grid_template.y_dim != template.y_dim or grid_template.x_dim != template.x_dim:
        raise ValueError("Cached Phase 3.6 grid template dims do not match source dataset")
    if (
        grid_template.lat_values.shape != template.lat_values.shape
        or not np.allclose(grid_template.lat_values, template.lat_values, rtol=0.0, atol=1e-12)
    ):
        raise ValueError("Cached Phase 3.6 latitude grid does not match source dataset")
    if (
        grid_template.lon_values.shape != template.lon_values.shape
        or not np.allclose(grid_template.lon_values, template.lon_values, rtol=0.0, atol=1e-12)
    ):
        raise ValueError("Cached Phase 3.6 longitude grid does not match source dataset")


def _save_cached_grid_template(
    path: Path,
    grid_template: Phase36GridTemplate,
    *,
    year: int,
    bbox: BBox | None,
) -> None:
    logger.info("Phase3.6 stage[00] writing grid template cache -> %s", path)
    dataset = xr.Dataset(
        coords={
            grid_template.y_dim: grid_template.lat_values,
            grid_template.x_dim: grid_template.lon_values,
        }
    )
    dataset.attrs.update(
        {
            "phase": "phase3.6",
            "target_year": int(year),
            "bbox_json": json.dumps(list(bbox)) if bbox is not None else "",
            "y_dim": grid_template.y_dim,
            "x_dim": grid_template.x_dim,
            PHASE36_CACHE_VERSION_ATTR: PHASE36_CACHE_VERSION,
        }
    )
    _write_xarray_dataset_atomically(path, dataset)
    logger.info("Phase3.6 stage[00] grid template cache ready: %s", path)


def _load_cached_grid_template(path: Path) -> Phase36GridTemplate | None:
    if not path.is_file():
        logger.info("Phase3.6 stage[00] grid template cache miss: %s", path)
        return None
    try:
        cached = xr.open_dataset(path)
        try:
            loaded = cached.load()
        finally:
            cached.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phase3.6 ignoring unreadable grid cache %s: %s", path, exc)
        return None

    if int(loaded.attrs.get(PHASE36_CACHE_VERSION_ATTR, -1)) != PHASE36_CACHE_VERSION:
        logger.info("Phase3.6 ignoring stale grid cache: %s", path)
        return None

    y_dim = str(loaded.attrs.get("y_dim", "lat"))
    x_dim = str(loaded.attrs.get("x_dim", "lon"))
    if y_dim not in loaded.coords or x_dim not in loaded.coords:
        logger.info("Phase3.6 ignoring malformed grid cache: %s", path)
        return None

    return Phase36GridTemplate(
        y_dim=y_dim,
        x_dim=x_dim,
        lat_values=np.asarray(loaded.coords[y_dim].values),
        lon_values=np.asarray(loaded.coords[x_dim].values),
    )


def _phase36_cache_file_is_current(path: Path) -> bool:
    if not path.is_file():
        return False

    try:
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            version = int(payload.get(PHASE36_CACHE_VERSION_ATTR, -1))
        else:
            with xr.open_dataset(path, engine="netcdf4") as cached:
                version = int(cached.attrs.get(PHASE36_CACHE_VERSION_ATTR, -1))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phase3.6 ignoring unreadable cache %s: %s", path, exc)
        return False

    if version != PHASE36_CACHE_VERSION:
        logger.info("Phase3.6 ignoring stale cache: %s", path)
        return False
    return True


def _write_global_unified_fraction_cache(
    *,
    dataset_id: str,
    dataset: xr.Dataset,
    cache_path: Path,
    source_dominant_cache_path: Path | None,
    grid_template: Phase36GridTemplate,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
) -> None:
    logger.info(
        "Phase3.6 stage[01] start: building unified fraction cache for %s -> %s",
        dataset_id,
        cache_path,
    )
    temp_path = _temp_output_path(cache_path)
    source_temp_path = (
        _temp_output_path(source_dominant_cache_path)
        if source_dominant_cache_path is not None
        else None
    )
    class_ids = np.asarray(unified_class_ids(), dtype=np.int16)
    try:
        source_context = (
            NetCDFDataset(source_temp_path, mode="w", format="NETCDF4")
            if source_temp_path is not None
            else nullcontext(None)
        )
        with (
            NetCDFDataset(temp_path, mode="w", format="NETCDF4") as target,
            source_context as source_target,
        ):
            _initialize_unified_fraction_file(
                target,
                grid_template=grid_template,
                dataset_id=dataset_id,
                year=year,
                bbox=bbox,
                class_ids=class_ids,
                lat_chunk_size=lat_chunk_size,
            )
            if source_target is not None:
                _initialize_single_dominant_class_file(
                    source_target,
                    grid_template=grid_template,
                    dataset_id=dataset_id,
                    classification_level="source",
                    year=year,
                    bbox=bbox,
                    lat_chunk_size=lat_chunk_size,
                )
            for row_start in range(0, len(grid_template.lat_values), lat_chunk_size):
                row_stop = min(len(grid_template.lat_values), row_start + lat_chunk_size)
                logger.info(
                    "Phase3.6 stage[01] %s stripe start: %s",
                    dataset_id,
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(grid_template.lat_values),
                    ),
                )
                unified = aggregate_source_fractions_to_unified(
                    dataset_id,
                    dataset,
                    lat_slice=slice(row_start, row_stop),
                )
                source_dominant = (
                    compute_source_dominant_class(
                        dataset_id,
                        dataset,
                        lat_slice=slice(row_start, row_stop),
                    )
                    if source_target is not None
                    else None
                )
                valid_cell_count = int(compute_valid_mask(unified).sum().item())
                _write_unified_fraction_stripe(
                    target,
                    unified,
                    row_start=row_start,
                    row_stop=row_stop,
                )
                if source_target is not None and source_dominant is not None:
                    _write_single_dominant_class_stripe(
                        source_target,
                        source_dominant,
                        row_start=row_start,
                        row_stop=row_stop,
                    )
                logger.info(
                    "Phase3.6 stage[01] %s stripe done: %s valid_cells=%s",
                    dataset_id,
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(grid_template.lat_values),
                    ),
                    valid_cell_count,
                )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_path, cache_path)
        if source_temp_path is not None and source_dominant_cache_path is not None:
            source_dominant_cache_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source_temp_path, source_dominant_cache_path)
        logger.info(
            "Phase3.6 stage[01] complete: dataset=%s cache=%s source_cache=%s",
            dataset_id,
            cache_path,
            source_dominant_cache_path,
        )
    except Exception:
        for stale_path in (temp_path, source_temp_path):
            if stale_path is None:
                continue
            try:
                stale_path.unlink()
            except FileNotFoundError:
                pass
        raise


def _build_reference_grid_from_template(
    grid_template: Phase36GridTemplate,
    *,
    row_start: int,
    row_stop: int,
) -> xr.DataArray:
    lat_values = grid_template.lat_values[row_start:row_stop]
    lon_values = grid_template.lon_values
    grid = xr.DataArray(
        np.zeros((len(lat_values), len(lon_values)), dtype=np.float32),
        dims=(grid_template.y_dim, grid_template.x_dim),
        coords={
            grid_template.y_dim: lat_values,
            grid_template.x_dim: lon_values,
        },
        name="phase36_reference_grid",
    )
    grid = grid.rio.set_spatial_dims(
        x_dim=grid_template.x_dim,
        y_dim=grid_template.y_dim,
        inplace=False,
    )
    return grid.rio.write_crs("EPSG:4326", inplace=False)


def _bbox_intersects(a: BBox, b: BBox) -> bool:
    return not (
        a[2] < b[0]
        or b[2] < a[0]
        or a[3] < b[1]
        or b[3] < a[1]
    )


def _stripe_bbox(
    grid_template: Phase36GridTemplate,
    *,
    row_start: int,
    row_stop: int,
) -> BBox:
    stripe_lats = grid_template.lat_values[row_start:row_stop]
    return (
        float(np.min(grid_template.lon_values)),
        float(np.min(stripe_lats)),
        float(np.max(grid_template.lon_values)),
        float(np.max(stripe_lats)),
    )


def _coord_index_lookup(values: np.ndarray) -> dict[float, int]:
    return {float(value): index for index, value in enumerate(values)}


def _coord_span_from_lookup(
    lookup: dict[float, int],
    coords: np.ndarray,
) -> tuple[int, int]:
    start = lookup[float(coords[0])]
    stop = lookup[float(coords[-1])] + 1
    if stop <= start:
        raise ValueError("Expected monotonically ordered tile coordinates")
    if stop - start != len(coords):
        raise ValueError("Tile coordinates do not map to a contiguous global slice")
    return start, stop


def _initialize_valid_mask_file(
    target: NetCDFDataset,
    *,
    grid_template: Phase36GridTemplate,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
) -> None:
    _initialize_spatial_file(
        target,
        lat_values=grid_template.lat_values,
        lon_values=grid_template.lon_values,
        y_dim=grid_template.y_dim,
        x_dim=grid_template.x_dim,
        year=year,
        bbox=bbox,
    )
    target.setncattr("dataset_id", "gwd30")
    target.setncattr(PHASE36_CACHE_VERSION_ATTR, PHASE36_CACHE_VERSION)
    target.createVariable(
        "valid_mask",
        "i1",
        (grid_template.y_dim, grid_template.x_dim),
        zlib=True,
        complevel=4,
        shuffle=True,
        chunksizes=(
            min(lat_chunk_size, len(grid_template.lat_values)),
            min(2048, len(grid_template.lon_values)),
        ),
    )


def _initialize_single_dominant_class_file(
    target: NetCDFDataset,
    *,
    grid_template: Phase36GridTemplate,
    dataset_id: str,
    classification_level: str,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
) -> None:
    _initialize_spatial_file(
        target,
        lat_values=grid_template.lat_values,
        lon_values=grid_template.lon_values,
        y_dim=grid_template.y_dim,
        x_dim=grid_template.x_dim,
        year=year,
        bbox=bbox,
    )
    target.setncattr("dataset_id", dataset_id)
    target.setncattr("classification_level", classification_level)
    target.setncattr(PHASE36_CACHE_VERSION_ATTR, PHASE36_CACHE_VERSION)
    if classification_level == "source":
        target.setncattr("dataset_display_name", dataset_display_name(dataset_id))
        target.setncattr(
            "source_class_names_json",
            json.dumps(source_class_names(dataset_id), sort_keys=True),
        )
    target.createVariable(
        "dominant_class",
        "i2",
        (grid_template.y_dim, grid_template.x_dim),
        zlib=True,
        complevel=4,
        shuffle=True,
        chunksizes=(
            min(lat_chunk_size, len(grid_template.lat_values)),
            min(2048, len(grid_template.lon_values)),
        ),
    )


def _write_valid_mask_stripe(
    target: NetCDFDataset,
    valid_mask: xr.DataArray,
    *,
    row_start: int,
    row_stop: int,
) -> None:
    target.variables["valid_mask"][row_start:row_stop, :] = np.asarray(
        valid_mask.values,
        dtype=np.int8,
    )


def _write_single_dominant_class_stripe(
    target: NetCDFDataset,
    dominant_class: xr.DataArray,
    *,
    row_start: int,
    row_stop: int,
) -> None:
    target.variables["dominant_class"][row_start:row_stop, :] = np.asarray(
        dominant_class.values,
        dtype=np.int16,
    )


def _write_global_gwd30_phase36_caches(
    *,
    standardized_dir: str | Path,
    valid_cache_path: Path,
    dominant_cache_path: Path,
    source_dominant_cache_path: Path,
    reduced_tile_dir: Path,
    grid_template: Phase36GridTemplate,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
    gwd30_worker_count: int | None,
    prefer_cache: bool,
) -> None:
    dataset_config = get_dataset_config("gwd30")
    loader = get_loader("gwd30", dataset_config)
    transform_staged_time_fraction_tiles = getattr(
        loader,
        "transform_staged_time_fraction_tiles",
        None,
    )
    if not callable(transform_staged_time_fraction_tiles):
        raise TypeError(
            "Configured GWD30 loader does not expose transform_staged_time_fraction_tiles()"
        )

    staged_tiles = _load_phase36_gwd30_staged_tiles(standardized_dir, year=year)
    reduced_tiles = transform_staged_time_fraction_tiles(
        staged_tiles=staged_tiles,
        output_dir=reduced_tile_dir,
        transform_name=PHASE36_GWD30_REDUCE_NAME,
        transform_version=PHASE36_GWD30_REDUCE_VERSION,
        transform_tile=phase36_reduce_staged_time_fraction_tile,
        year=year,
        worker_count=gwd30_worker_count,
        show_progress=True,
        skip_existing=prefer_cache,
    )

    valid_temp_path = _temp_output_path(valid_cache_path)
    dominant_temp_path = _temp_output_path(dominant_cache_path)
    source_dominant_temp_path = _temp_output_path(source_dominant_cache_path)
    unified_ids = np.asarray(unified_class_ids(), dtype=np.int16)
    gwd30_source_ids = np.asarray(source_class_ids("gwd30"), dtype=np.int16)
    y_index_lookup = _coord_index_lookup(grid_template.lat_values)
    x_index_lookup = _coord_index_lookup(grid_template.lon_values)
    stripe_lon_count = len(grid_template.lon_values)
    try:
        with (
            NetCDFDataset(valid_temp_path, mode="w", format="NETCDF4") as valid_target,
            NetCDFDataset(dominant_temp_path, mode="w", format="NETCDF4") as dominant_target,
            NetCDFDataset(source_dominant_temp_path, mode="w", format="NETCDF4") as source_target,
        ):
            _initialize_valid_mask_file(
                valid_target,
                grid_template=grid_template,
                year=year,
                bbox=bbox,
                lat_chunk_size=lat_chunk_size,
            )
            _initialize_single_dominant_class_file(
                dominant_target,
                grid_template=grid_template,
                dataset_id="gwd30",
                classification_level="unified",
                year=year,
                bbox=bbox,
                lat_chunk_size=lat_chunk_size,
            )
            _initialize_single_dominant_class_file(
                source_target,
                grid_template=grid_template,
                dataset_id="gwd30",
                classification_level="source",
                year=year,
                bbox=bbox,
                lat_chunk_size=lat_chunk_size,
            )
            for row_start in range(0, len(grid_template.lat_values), lat_chunk_size):
                row_stop = min(len(grid_template.lat_values), row_start + lat_chunk_size)
                stripe_bbox = _stripe_bbox(
                    grid_template,
                    row_start=row_start,
                    row_stop=row_stop,
                )
                candidate_tiles = [
                    (tile_path, tile_bbox)
                    for tile_path, tile_bbox in reduced_tiles
                    if _bbox_intersects(tile_bbox, stripe_bbox)
                ]
                logger.info(
                    "Phase3.6 stage[01] gwd30 stripe start: %s candidate_tiles=%s",
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(grid_template.lat_values),
                    ),
                    len(candidate_tiles),
                )
                weighted_sum = np.zeros(
                    (len(unified_ids), row_stop - row_start, stripe_lon_count),
                    dtype=np.float32,
                )
                source_weighted_sum = np.zeros(
                    (len(gwd30_source_ids), row_stop - row_start, stripe_lon_count),
                    dtype=np.float32,
                )
                coverage_sum = np.zeros((row_stop - row_start, stripe_lon_count), dtype=np.float32)
                for tile_path, _tile_bbox in candidate_tiles:
                    with xr.open_dataset(tile_path, engine="netcdf4") as tile_dataset:
                        source_weighted = tile_dataset["annual_source_weighted_sum"].load()
                        weighted = tile_dataset["annual_unified_weighted_sum"].load()
                        coverage = tile_dataset["annual_coverage_sum"].load()
                    tile_row_start, tile_row_stop = _coord_span_from_lookup(
                        y_index_lookup,
                        np.asarray(weighted.coords[grid_template.y_dim].values),
                    )
                    tile_col_start, tile_col_stop = _coord_span_from_lookup(
                        x_index_lookup,
                        np.asarray(weighted.coords[grid_template.x_dim].values),
                    )
                    overlap_row_start = max(row_start, tile_row_start)
                    overlap_row_stop = min(row_stop, tile_row_stop)
                    if overlap_row_stop <= overlap_row_start:
                        continue
                    stripe_row_start = overlap_row_start - row_start
                    stripe_row_stop = overlap_row_stop - row_start
                    tile_row_slice = slice(
                        overlap_row_start - tile_row_start,
                        overlap_row_stop - tile_row_start,
                    )
                    weighted_sum[
                        :,
                        stripe_row_start:stripe_row_stop,
                        tile_col_start:tile_col_stop,
                    ] += np.asarray(weighted.values[:, tile_row_slice, :], dtype=np.float32)
                    source_weighted_sum[
                        :,
                        stripe_row_start:stripe_row_stop,
                        tile_col_start:tile_col_stop,
                    ] += np.asarray(source_weighted.values[:, tile_row_slice, :], dtype=np.float32)
                    coverage_sum[
                        stripe_row_start:stripe_row_stop,
                        tile_col_start:tile_col_stop,
                    ] += np.asarray(coverage.values[tile_row_slice, :], dtype=np.float32)

                valid_mask_values = coverage_sum > 0
                for class_index in range(len(unified_ids)):
                    plane = weighted_sum[class_index]
                    np.divide(plane, coverage_sum, out=plane, where=valid_mask_values)
                    plane[~valid_mask_values] = np.nan
                np.clip(weighted_sum, 0.0, 1.0, out=weighted_sum)
                stripe_coords = {
                    "class_id": unified_ids,
                    grid_template.y_dim: grid_template.lat_values[row_start:row_stop],
                    grid_template.x_dim: grid_template.lon_values,
                }
                gwd30_fraction = xr.DataArray(
                    weighted_sum,
                    dims=("class_id", grid_template.y_dim, grid_template.x_dim),
                    coords=stripe_coords,
                    name="unified_fraction",
                )
                gwd30_valid_mask = xr.DataArray(
                    valid_mask_values,
                    dims=(grid_template.y_dim, grid_template.x_dim),
                    coords={
                        grid_template.y_dim: grid_template.lat_values[row_start:row_stop],
                        grid_template.x_dim: grid_template.lon_values,
                    },
                    name="valid_mask",
                ).astype(bool)
                gwd30_dominant = compute_gwd30_annual_dominant_class(
                    gwd30_fraction,
                    valid_mask=gwd30_valid_mask,
                )
                _write_valid_mask_stripe(
                    valid_target,
                    gwd30_valid_mask.astype(np.int8),
                    row_start=row_start,
                    row_stop=row_stop,
                )
                _write_single_dominant_class_stripe(
                    dominant_target,
                    gwd30_dominant,
                    row_start=row_start,
                    row_stop=row_stop,
                )
                source_fraction_values = np.full_like(source_weighted_sum, np.nan, dtype=np.float32)
                np.divide(
                    source_weighted_sum,
                    coverage_sum[None, :, :],
                    out=source_fraction_values,
                    where=coverage_sum[None, :, :] > 0,
                )
                np.clip(source_fraction_values, 0.0, 1.0, out=source_fraction_values)
                source_fraction = xr.DataArray(
                    source_fraction_values,
                    dims=("source_class_id", grid_template.y_dim, grid_template.x_dim),
                    coords={
                        "source_class_id": gwd30_source_ids,
                        grid_template.y_dim: grid_template.lat_values[row_start:row_stop],
                        grid_template.x_dim: grid_template.lon_values,
                    },
                    name="source_fraction",
                )
                gwd30_source_dominant = compute_source_dominant_class_from_fractions(
                    "gwd30",
                    source_fraction,
                    valid_mask=gwd30_valid_mask,
                )
                _write_single_dominant_class_stripe(
                    source_target,
                    gwd30_source_dominant,
                    row_start=row_start,
                    row_stop=row_stop,
                )
                logger.info(
                    "Phase3.6 stage[01] gwd30 stripe done: %s valid_cells=%s",
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(grid_template.lat_values),
                    ),
                    int(valid_mask_values.sum()),
                )
        valid_cache_path.parent.mkdir(parents=True, exist_ok=True)
        dominant_cache_path.parent.mkdir(parents=True, exist_ok=True)
        source_dominant_cache_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(valid_temp_path, valid_cache_path)
        os.replace(dominant_temp_path, dominant_cache_path)
        os.replace(source_dominant_temp_path, source_dominant_cache_path)
        logger.info(
            "Phase3.6 stage[01] complete: gwd30 valid=%s dominant=%s source=%s reduced_tiles=%s",
            valid_cache_path,
            dominant_cache_path,
            source_dominant_cache_path,
            reduced_tile_dir,
        )
    except Exception:
        for temp_path in (valid_temp_path, dominant_temp_path, source_dominant_temp_path):
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
        raise


def _write_global_joint_valid_cache(
    *,
    cache_path: Path,
    static_unified_cache_paths: dict[str, Path],
    gwd30_valid_cache_path: Path,
    grid_template: Phase36GridTemplate,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
) -> None:
    logger.info(
        "Phase3.6 stage[02] start: building joint-valid cache -> %s",
        cache_path,
    )
    temp_path = _temp_output_path(cache_path)
    unified_datasets = {
        dataset_id: xr.open_dataset(static_unified_cache_paths[dataset_id], decode_cf=True)
        for dataset_id in PHASE36_STATIC_DATASET_IDS
    }
    gwd30_valid_dataset = xr.open_dataset(gwd30_valid_cache_path, decode_cf=True)
    try:
        with NetCDFDataset(temp_path, mode="w", format="NETCDF4") as target:
            _initialize_joint_valid_file(
                target,
                grid_template=grid_template,
                year=year,
                bbox=bbox,
                lat_chunk_size=lat_chunk_size,
            )
            for row_start in range(0, len(grid_template.lat_values), lat_chunk_size):
                row_stop = min(len(grid_template.lat_values), row_start + lat_chunk_size)
                logger.info(
                    "Phase3.6 stage[02] stripe start: %s",
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(grid_template.lat_values),
                    ),
                )
                unified = {
                    dataset_id: unified_datasets[dataset_id]["unified_fraction"]
                    .isel({grid_template.y_dim: slice(row_start, row_stop)})
                    .load()
                    for dataset_id in PHASE36_STATIC_DATASET_IDS
                }
                valid_masks = {
                    dataset_id: compute_valid_mask(unified[dataset_id])
                    for dataset_id in PHASE36_STATIC_DATASET_IDS
                }
                valid_masks["gwd30"] = gwd30_valid_dataset["valid_mask"].isel(
                    {grid_template.y_dim: slice(row_start, row_stop)}
                ).load().astype(bool)
                joint_valid = combine_valid_masks(valid_masks)
                joint_valid_count = int(np.asarray(joint_valid.values, dtype=bool).sum())
                _write_joint_valid_stripe(
                    target,
                    joint_valid,
                    row_start=row_start,
                    row_stop=row_stop,
                )
                logger.info(
                    "Phase3.6 stage[02] stripe done: %s joint_valid=%s",
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(grid_template.lat_values),
                    ),
                    joint_valid_count,
                )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_path, cache_path)
        logger.info("Phase3.6 stage[02] complete: cache=%s", cache_path)
    except Exception:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        gwd30_valid_dataset.close()
        for dataset in unified_datasets.values():
            dataset.close()


def _write_global_dominant_cache(
    *,
    cache_path: Path,
    static_unified_cache_paths: dict[str, Path],
    static_source_dominant_cache_paths: dict[str, Path],
    gwd30_dominant_cache_path: Path,
    gwd30_source_dominant_cache_path: Path,
    joint_valid_cache_path: Path,
    grid_template: Phase36GridTemplate,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
) -> None:
    logger.info(
        "Phase3.6 stage[03] start: building dominant-class cache -> %s",
        cache_path,
    )
    temp_path = _temp_output_path(cache_path)
    unified_datasets = {
        dataset_id: xr.open_dataset(static_unified_cache_paths[dataset_id], decode_cf=True)
        for dataset_id in PHASE36_STATIC_DATASET_IDS
    }
    source_dominant_datasets = {
        dataset_id: xr.open_dataset(static_source_dominant_cache_paths[dataset_id], decode_cf=True)
        for dataset_id in PHASE36_STATIC_DATASET_IDS
    }
    gwd30_dominant_dataset = xr.open_dataset(gwd30_dominant_cache_path, decode_cf=True)
    gwd30_source_dominant_dataset = xr.open_dataset(
        gwd30_source_dominant_cache_path,
        decode_cf=True,
    )
    joint_valid_dataset = xr.open_dataset(joint_valid_cache_path, decode_cf=True)
    try:
        with NetCDFDataset(temp_path, mode="w", format="NETCDF4") as target:
            _initialize_dominant_file(
                target,
                lat_values=grid_template.lat_values,
                lon_values=grid_template.lon_values,
                y_dim=grid_template.y_dim,
                x_dim=grid_template.x_dim,
                year=year,
                bbox=bbox,
                lat_chunk_size=lat_chunk_size,
            )
            target.setncattr(PHASE36_CACHE_VERSION_ATTR, PHASE36_CACHE_VERSION)

            for row_start in range(0, len(grid_template.lat_values), lat_chunk_size):
                row_stop = min(len(grid_template.lat_values), row_start + lat_chunk_size)
                logger.info(
                    "Phase3.6 stage[03] stripe start: %s",
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(grid_template.lat_values),
                    ),
                )
                joint_valid = joint_valid_dataset["joint_valid_mask"].isel(
                    {grid_template.y_dim: slice(row_start, row_stop)}
                ).load()
                dominant_classes = {
                    dataset_id: compute_dominant_class(
                        unified_datasets[dataset_id]["unified_fraction"]
                        .isel({grid_template.y_dim: slice(row_start, row_stop)})
                        .load(),
                    )
                    for dataset_id in PHASE36_STATIC_DATASET_IDS
                }
                dominant_classes["gwd30"] = gwd30_dominant_dataset["dominant_class"].isel(
                    {grid_template.y_dim: slice(row_start, row_stop)}
                ).load()
                source_dominant_classes = {
                    dataset_id: source_dominant_datasets[dataset_id]["dominant_class"]
                    .isel({grid_template.y_dim: slice(row_start, row_stop)})
                    .load()
                    for dataset_id in PHASE36_STATIC_DATASET_IDS
                }
                source_dominant_classes["gwd30"] = gwd30_source_dominant_dataset[
                    "dominant_class"
                ].isel(
                    {grid_template.y_dim: slice(row_start, row_stop)}
                ).load()
                dominant_dataset = build_joint_dominant_class_dataset(
                    dominant_classes,
                    joint_valid_mask=joint_valid.astype(bool),
                    source_dominant_classes=source_dominant_classes,
                )
                valid_counts = {
                    dataset_id: int(
                        np.sum(
                            np.asarray(
                                dominant_dataset[f"{dataset_id}_dominant_class"].values,
                                dtype=np.int16,
                            )
                            != int(INVALID_CLASS_VALUE)
                        )
                    )
                    for dataset_id in PHASE36_DATASET_IDS
                }
                _write_dominant_stripe(
                    target,
                    dominant_dataset,
                    y_dim=grid_template.y_dim,
                    x_dim=grid_template.x_dim,
                    row_start=row_start,
                    row_stop=row_stop,
                )
                logger.info(
                    "Phase3.6 stage[03] stripe done: %s valid_g2017=%s valid_glwd_v2=%s "
                    "valid_gwd30=%s",
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(grid_template.lat_values),
                    ),
                    valid_counts["g2017"],
                    valid_counts["glwd_v2"],
                    valid_counts["gwd30"],
                )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_path, cache_path)
        logger.info("Phase3.6 stage[03] complete: cache=%s", cache_path)
    except Exception:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        gwd30_dominant_dataset.close()
        gwd30_source_dominant_dataset.close()
        joint_valid_dataset.close()
        for dataset in unified_datasets.values():
            dataset.close()
        for dataset in source_dominant_datasets.values():
            dataset.close()


def _write_global_metrics_cache(
    *,
    cache_path: Path,
    dominant_cache_path: Path,
    joint_valid_cache_path: Path,
    grid_template: Phase36GridTemplate,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
) -> None:
    logger.info(
        "Phase3.6 stage[04] start: building metrics cache -> %s",
        cache_path,
    )
    temp_path = _temp_output_path(cache_path)
    dominant_dataset = xr.open_dataset(dominant_cache_path, decode_cf=True)
    joint_valid_dataset = xr.open_dataset(joint_valid_cache_path, decode_cf=True)
    try:
        with NetCDFDataset(temp_path, mode="w", format="NETCDF4") as target:
            _initialize_metrics_file(
                target,
                lat_values=grid_template.lat_values,
                lon_values=grid_template.lon_values,
                y_dim=grid_template.y_dim,
                x_dim=grid_template.x_dim,
                year=year,
                bbox=bbox,
                lat_chunk_size=lat_chunk_size,
            )
            target.setncattr(PHASE36_CACHE_VERSION_ATTR, PHASE36_CACHE_VERSION)

            for row_start in range(0, len(grid_template.lat_values), lat_chunk_size):
                row_stop = min(len(grid_template.lat_values), row_start + lat_chunk_size)
                logger.info(
                    "Phase3.6 stage[04] stripe start: %s",
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(grid_template.lat_values),
                    ),
                )
                joint_valid = joint_valid_dataset["joint_valid_mask"].isel(
                    {grid_template.y_dim: slice(row_start, row_stop)}
                ).load()
                dominant_classes = {
                    dataset_id: dominant_dataset[f"{dataset_id}_dominant_class"]
                    .isel({grid_template.y_dim: slice(row_start, row_stop)})
                    .load()
                    for dataset_id in PHASE36_DATASET_IDS
                }
                metrics = compute_vote_entropy(
                    dominant_classes,
                    joint_valid_mask=joint_valid.astype(bool),
                )
                joint_valid_count = int(
                    np.asarray(metrics["joint_valid_mask"].values, dtype=bool).sum()
                )
                entropy_stats = _entropy_stats(metrics["entropy"])
                _write_metrics_stripe(
                    target,
                    metrics,
                    y_dim=grid_template.y_dim,
                    x_dim=grid_template.x_dim,
                    row_start=row_start,
                    row_stop=row_stop,
                )
                logger.info(
                    "Phase3.6 stage[04] stripe done: %s joint_valid=%s entropy_mean=%s "
                    "entropy_min=%s entropy_max=%s",
                    _stripe_progress_text(
                        row_start=row_start,
                        row_stop=row_stop,
                        total_rows=len(grid_template.lat_values),
                    ),
                    joint_valid_count,
                    _format_optional_float(entropy_stats["mean"]),
                    _format_optional_float(entropy_stats["min"]),
                    _format_optional_float(entropy_stats["max"]),
                )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_path, cache_path)
        logger.info("Phase3.6 stage[04] complete: cache=%s", cache_path)
    except Exception:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        dominant_dataset.close()
        joint_valid_dataset.close()


def _write_cached_summary(
    *,
    cache_path: Path,
    metrics_cache_path: Path,
    grid_template: Phase36GridTemplate,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
) -> None:
    logger.info(
        "Phase3.6 stage[05] start: summarizing metrics cache %s -> %s",
        metrics_cache_path,
        cache_path,
    )
    summary_builder = _StreamingPhase36Summary(lat_values=grid_template.lat_values)
    metrics_dataset = xr.open_dataset(metrics_cache_path, decode_cf=True)
    try:
        for row_start in range(0, len(grid_template.lat_values), lat_chunk_size):
            row_stop = min(len(grid_template.lat_values), row_start + lat_chunk_size)
            metrics = metrics_dataset.isel(
                {grid_template.y_dim: slice(row_start, row_stop)}
            ).load()
            stripe_joint_valid = int(
                np.asarray(metrics["joint_valid_mask"].values, dtype=bool).sum()
            )
            summary_builder.update(
                metrics=metrics,
                row_start=row_start,
                row_stop=row_stop,
                y_dim=grid_template.y_dim,
            )
            logger.info(
                "Phase3.6 stage[05] stripe done: %s joint_valid=%s",
                _stripe_progress_text(
                    row_start=row_start,
                    row_stop=row_stop,
                    total_rows=len(grid_template.lat_values),
                ),
                stripe_joint_valid,
            )
    finally:
        metrics_dataset.close()

    summary = summary_builder.to_dict(year=year, bbox=bbox)
    summary["metrics_path"] = str(metrics_cache_path)
    summary["dominant_classes_path"] = str(cache_path.parent / "03_dominant_classes.nc")
    summary[PHASE36_CACHE_VERSION_ATTR] = PHASE36_CACHE_VERSION
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _temp_output_path(cache_path)
    try:
        temp_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        os.replace(temp_path, cache_path)
        logger.info(
            "Phase3.6 stage[05] complete: cache=%s joint_valid=%s area_weighted_entropy=%s",
            cache_path,
            summary["joint_valid_cell_count"],
            _format_optional_float(summary["mean_entropy_area_weighted"]),
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _initialize_unified_fraction_file(
    target: NetCDFDataset,
    *,
    grid_template: Phase36GridTemplate,
    dataset_id: str,
    year: int,
    bbox: BBox | None,
    class_ids: np.ndarray,
    lat_chunk_size: int,
) -> None:
    _initialize_spatial_file(
        target,
        lat_values=grid_template.lat_values,
        lon_values=grid_template.lon_values,
        y_dim=grid_template.y_dim,
        x_dim=grid_template.x_dim,
        year=year,
        bbox=bbox,
    )
    target.setncattr("dataset_id", dataset_id)
    target.setncattr(PHASE36_CACHE_VERSION_ATTR, PHASE36_CACHE_VERSION)
    target.createDimension("class_id", len(class_ids))
    class_id_var = target.createVariable("class_id", "i2", ("class_id",))
    class_id_var[:] = class_ids
    chunksizes = (
        len(class_ids),
        min(lat_chunk_size, len(grid_template.lat_values)),
        min(2048, len(grid_template.lon_values)),
    )
    target.createVariable(
        "unified_fraction",
        "f4",
        ("class_id", grid_template.y_dim, grid_template.x_dim),
        zlib=True,
        complevel=4,
        shuffle=True,
        fill_value=np.float32(np.nan),
        chunksizes=chunksizes,
    )


def _initialize_joint_valid_file(
    target: NetCDFDataset,
    *,
    grid_template: Phase36GridTemplate,
    year: int,
    bbox: BBox | None,
    lat_chunk_size: int,
) -> None:
    _initialize_spatial_file(
        target,
        lat_values=grid_template.lat_values,
        lon_values=grid_template.lon_values,
        y_dim=grid_template.y_dim,
        x_dim=grid_template.x_dim,
        year=year,
        bbox=bbox,
    )
    target.setncattr(PHASE36_CACHE_VERSION_ATTR, PHASE36_CACHE_VERSION)
    target.createVariable(
        "joint_valid_mask",
        "i1",
        (grid_template.y_dim, grid_template.x_dim),
        zlib=True,
        complevel=4,
        shuffle=True,
        chunksizes=(
            min(lat_chunk_size, len(grid_template.lat_values)),
            min(2048, len(grid_template.lon_values)),
        ),
    )


def _write_unified_fraction_stripe(
    target: NetCDFDataset,
    unified: xr.DataArray,
    *,
    row_start: int,
    row_stop: int,
) -> None:
    target.variables["unified_fraction"][:, row_start:row_stop, :] = np.asarray(
        unified.values,
        dtype=np.float32,
    )


def _write_joint_valid_stripe(
    target: NetCDFDataset,
    joint_valid: xr.DataArray,
    *,
    row_start: int,
    row_stop: int,
) -> None:
    target.variables["joint_valid_mask"][row_start:row_stop, :] = np.asarray(
        joint_valid.values,
        dtype=np.int8,
    )


def _write_xarray_dataset_atomically(path: Path, dataset: xr.Dataset) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _temp_output_path(path)
    try:
        dataset.to_netcdf(temp_path)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _materialize_cached_file(source: Path, target: Path) -> None:
    if source.resolve() == target.resolve():
        return
    logger.info("Phase3.6 materialize cache: %s -> %s", source, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _temp_output_path(target)
    try:
        try:
            os.link(source, temp_path)
        except OSError:
            shutil.copy2(source, temp_path)
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _write_output_summary_from_cache(
    *,
    cache_summary_path: Path,
    output_summary_path: Path,
    metrics_path: Path,
    dominant_path: Path,
) -> None:
    logger.info(
        "Phase3.6 materialize summary from cache: %s -> %s",
        cache_summary_path,
        output_summary_path,
    )
    summary = json.loads(cache_summary_path.read_text(encoding="utf-8"))
    summary["metrics_path"] = str(metrics_path)
    summary["dominant_classes_path"] = str(dominant_path)
    output_summary_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _temp_output_path(output_summary_path)
    try:
        temp_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        os.replace(temp_path, output_summary_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    logger.info("Phase3.6 summary materialized: %s", output_summary_path)


def _temp_output_path(path: Path) -> Path:
    return path.parent / f".{path.name}.tmp-{os.getpid()}-{uuid4().hex}"


class _StreamingPhase36Summary:
    """Streaming accumulator for global Phase 3.6 summary statistics."""

    def __init__(self, *, lat_values: np.ndarray) -> None:
        self.lat_values = np.asarray(lat_values, dtype=np.float64)
        self.valid_cell_count = 0
        self.total_cell_count = 0
        self.weighted_entropy_sum = 0.0
        self.weight_total = 0.0
        self.total_area_weight = 0.0
        self.majority_weight_by_class = {
            int(class_id): 0.0 for class_id in unified_class_ids()
        }
        self.agreement_count_histogram = {1: 0, 2: 0, 3: 0}
        self.entropy_histogram_edges = np.linspace(
            0.0,
            1.0,
            ENTROPY_HISTOGRAM_BINS + 1,
            dtype=np.float64,
        )
        self.entropy_histogram_counts = np.zeros(ENTROPY_HISTOGRAM_BINS, dtype=np.int64)

    def update(
        self,
        *,
        metrics: xr.Dataset,
        row_start: int,
        row_stop: int,
        y_dim: str,
    ) -> None:
        del y_dim
        joint_valid = np.asarray(metrics["joint_valid_mask"].values, dtype=bool)
        entropy = np.asarray(metrics["entropy"].values, dtype=np.float64)
        majority_class = np.asarray(metrics["majority_class"].values, dtype=np.int16)
        agreement_count = np.asarray(metrics["agreement_count"].values, dtype=np.int16)

        lat_slice = self.lat_values[row_start:row_stop]
        weights = np.cos(np.deg2rad(lat_slice))[:, None]
        weights = np.broadcast_to(weights, joint_valid.shape)

        self.total_cell_count += int(joint_valid.size)
        self.total_area_weight += float(weights.sum())
        self.valid_cell_count += int(joint_valid.sum())

        valid_entropy = joint_valid & np.isfinite(entropy)
        if valid_entropy.any():
            self.weighted_entropy_sum += float(
                np.sum(entropy[valid_entropy] * weights[valid_entropy])
            )
            self.weight_total += float(np.sum(weights[valid_entropy]))
            hist, _ = np.histogram(
                entropy[valid_entropy],
                bins=self.entropy_histogram_edges,
            )
            self.entropy_histogram_counts += hist.astype(np.int64)

        for class_id in unified_class_ids():
            mask = joint_valid & (majority_class == int(class_id))
            if mask.any():
                self.majority_weight_by_class[int(class_id)] += float(np.sum(weights[mask]))

        for vote_count in (1, 2, 3):
            self.agreement_count_histogram[vote_count] += int(
                np.sum(joint_valid & (agreement_count == vote_count))
            )

    def to_dict(self, *, year: int, bbox: BBox | None) -> dict[str, object]:
        mean_entropy = None
        if self.weight_total > 0:
            mean_entropy = self.weighted_entropy_sum / self.weight_total

        valid_area_share = None
        if self.total_area_weight > 0:
            valid_area_share = self.weight_total / self.total_area_weight

        total_majority_weight = sum(self.majority_weight_by_class.values())
        majority_class_area_share = {
            str(class_id): (
                weight / total_majority_weight if total_majority_weight > 0 else None
            )
            for class_id, weight in self.majority_weight_by_class.items()
        }

        return {
            "phase": "phase3.6",
            "target_year": int(year),
            "bbox": list(bbox) if bbox is not None else None,
            "dataset_ids": list(PHASE36_DATASET_IDS),
            "joint_valid_cell_count": int(self.valid_cell_count),
            "total_cell_count": int(self.total_cell_count),
            "joint_valid_cell_share": (
                self.valid_cell_count / self.total_cell_count
                if self.total_cell_count > 0
                else None
            ),
            "joint_valid_area_share": valid_area_share,
            "mean_entropy_area_weighted": mean_entropy,
            "entropy_quantiles_approx": {
                "p50": self._approx_quantile(0.50),
                "p90": self._approx_quantile(0.90),
                "p99": self._approx_quantile(0.99),
            },
            "majority_class_area_share": majority_class_area_share,
            "agreement_count_histogram": self.agreement_count_histogram,
        }

    def _approx_quantile(self, quantile: float) -> float | None:
        total = int(self.entropy_histogram_counts.sum())
        if total <= 0:
            return None
        threshold = total * quantile
        cumulative = np.cumsum(self.entropy_histogram_counts)
        index = int(np.searchsorted(cumulative, threshold, side="left"))
        index = min(max(index, 0), len(self.entropy_histogram_edges) - 2)
        left = self.entropy_histogram_edges[index]
        right = self.entropy_histogram_edges[index + 1]
        return float((left + right) / 2.0)
