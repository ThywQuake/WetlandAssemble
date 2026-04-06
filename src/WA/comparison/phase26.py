"""Phase 2.6 cache-backed coarse wetland comparison helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
import xarray as xr

DEFAULT_PHASE26_CACHE_DIR = Path("results/cache/tropical_025deg")
DEFAULT_PHASE26_DATASET_IDS = (
    "berkeley_rwawc",
    "g2017",
    "giems_mc",
    "glwd_v2",
    "swamps",
    "topmodel",
    "wad2m",
)
DEFAULT_PHASE26_STD_EXCLUDED_DATASET_IDS = (
    "berkeley_rwawc",
    "g2017",
    "glwd_v2",
)
DEFAULT_PHASE26_REGION_ID = "global_tropical_subtropical_35"
DEFAULT_PHASE26_RESOLUTION_DEG = 0.25
DEFAULT_PHASE26_TARGET_YEAR = 2016
DEFAULT_PHASE26_LANDMASK_DATASET_ID = "glwd_v2"
BERKELEY_TARGET_YEAR = 2019

STAGE_COARSE = "05_coarse_surface"
STAGE_CACHE_VERSION_ATTR = "wa_stage_cache_version"
EXPECTED_COARSE_CACHE_VERSION = 2


@dataclass(frozen=True)
class Phase26CacheLoadResult:
    """Loaded coarse cache surfaces plus skipped datasets."""

    surfaces: dict[str, xr.DataArray]
    cache_paths: dict[str, Path]
    skipped: dict[str, str]


def resolved_target_year(dataset_id: str, default_year: int) -> int | None:
    """Resolve the target year used by the plotting cache layout."""

    if dataset_id == "berkeley_rwawc":
        return BERKELEY_TARGET_YEAR
    if dataset_id in {"g2017", "glwd_v2"}:
        return None
    return default_year


def coarse_cache_path(
    cache_root: Path,
    dataset_id: str,
    region_id: str,
    *,
    target_year: int | None,
    resolution_deg: float,
) -> Path:
    """Return the expected path for one coarse plotting cache file."""

    year_key = f"year_{target_year}" if target_year is not None else "static"
    resolution_text = f"{resolution_deg:.6f}".rstrip("0").rstrip(".")
    resolution_key = f"res_{resolution_text.replace('.', 'p')}"
    return (
        cache_root
        / region_id
        / dataset_id
        / year_key
        / resolution_key
        / f"{STAGE_COARSE}.nc"
    )


def load_cached_coarse_surfaces(
    cache_root: Path,
    *,
    region_id: str = DEFAULT_PHASE26_REGION_ID,
    dataset_ids: tuple[str, ...] | list[str] = DEFAULT_PHASE26_DATASET_IDS,
    default_year: int = DEFAULT_PHASE26_TARGET_YEAR,
    resolution_deg: float = DEFAULT_PHASE26_RESOLUTION_DEG,
) -> Phase26CacheLoadResult:
    """Load already computed 0.25° coarse wetland surfaces from plotting caches."""

    surfaces: dict[str, xr.DataArray] = {}
    cache_paths: dict[str, Path] = {}
    skipped: dict[str, str] = {}

    for dataset_id in dataset_ids:
        if dataset_id == "gwd30":
            skipped[dataset_id] = "GWD30 is intentionally excluded from Phase 2.6"
            continue

        target_year = resolved_target_year(dataset_id, default_year)
        path = coarse_cache_path(
            cache_root,
            dataset_id,
            region_id,
            target_year=target_year,
            resolution_deg=resolution_deg,
        )
        if not path.is_file():
            skipped[dataset_id] = f"missing cache: {path}"
            continue

        try:
            opened = xr.open_dataarray(path)
            try:
                loaded = opened.load()
            finally:
                opened.close()
        except Exception as exc:  # noqa: BLE001
            skipped[dataset_id] = f"unreadable cache {path}: {type(exc).__name__}: {exc}"
            continue

        actual_version = loaded.attrs.get(STAGE_CACHE_VERSION_ATTR)
        if actual_version != EXPECTED_COARSE_CACHE_VERSION:
            skipped[dataset_id] = (
                f"stale cache {path}: expected {STAGE_CACHE_VERSION_ATTR}="
                f"{EXPECTED_COARSE_CACHE_VERSION}, got {actual_version!r}"
            )
            continue

        prepared = _prepare_surface_for_stack(loaded).astype(np.float32)
        prepared.name = "wetland_fraction"
        prepared.attrs = {
            "dataset_id": dataset_id,
            "requested_target_year": target_year if target_year is not None else "static",
            "source_cache_path": str(path),
        }
        surfaces[dataset_id] = prepared
        cache_paths[dataset_id] = path

    return Phase26CacheLoadResult(
        surfaces=surfaces,
        cache_paths=cache_paths,
        skipped=skipped,
    )


def build_phase26_stack(surfaces: dict[str, xr.DataArray]) -> xr.DataArray:
    """Stack aligned coarse wetland-fraction surfaces on a dataset dimension."""

    if not surfaces:
        raise ValueError("surfaces must contain at least one dataset")

    stacked = xr.concat(
        [
            _prepare_surface_for_stack(surfaces[dataset_id]).expand_dims(dataset=[dataset_id])
            for dataset_id in sorted(surfaces)
        ],
        dim="dataset",
    ).astype(np.float32)
    stacked.name = "wetland_fraction"
    stacked.attrs["dataset_ids_json"] = json.dumps(sorted(surfaces))
    stacked.attrs["dataset_count"] = len(surfaces)
    landmask_dataset_id = _shared_landmask_dataset_id(surfaces)
    if landmask_dataset_id is not None:
        stacked.attrs["landmask_dataset_id"] = landmask_dataset_id
        stacked.attrs["landmask_rule"] = (
            f"valid cells where {landmask_dataset_id} coarse surface is non-null"
        )
    return stacked


def apply_landmask_to_surfaces(
    surfaces: dict[str, xr.DataArray],
    *,
    landmask_dataset_id: str = DEFAULT_PHASE26_LANDMASK_DATASET_ID,
) -> dict[str, xr.DataArray]:
    """Mask all Phase 2.6 surfaces to the valid extent of one reference dataset."""

    if not surfaces:
        raise ValueError("surfaces must contain at least one dataset")
    if landmask_dataset_id not in surfaces:
        raise ValueError(
            f"landmask dataset {landmask_dataset_id!r} is required but was not loaded"
        )

    landmask_surface = _prepare_surface_for_stack(surfaces[landmask_dataset_id])
    landmask = landmask_surface.notnull()

    masked_surfaces: dict[str, xr.DataArray] = {}
    for dataset_id, surface in surfaces.items():
        prepared = _prepare_surface_for_stack(surface)
        masked = prepared.where(landmask).astype(np.float32)
        masked.name = "wetland_fraction"
        attrs = dict(prepared.attrs)
        attrs["landmask_dataset_id"] = landmask_dataset_id
        attrs["landmask_rule"] = (
            f"valid cells where {landmask_dataset_id} coarse surface is non-null"
        )
        masked.attrs = attrs
        masked_surfaces[dataset_id] = masked

    return masked_surfaces


def compute_phase26_metrics(
    surfaces: dict[str, xr.DataArray],
    *,
    min_participants: int = 2,
    std_excluded_dataset_ids: tuple[str, ...]
    | list[str] = DEFAULT_PHASE26_STD_EXCLUDED_DATASET_IDS,
) -> xr.Dataset:
    """Compute coarse wetland comparison metrics from cached continuous surfaces."""

    if len(surfaces) < 2:
        raise ValueError("At least two dataset surfaces are required for Phase 2.6 metrics")
    if min_participants < 1:
        raise ValueError("min_participants must be >= 1")

    mean_stack = build_phase26_stack(surfaces)
    std_surfaces = select_std_surfaces(
        surfaces,
        excluded_dataset_ids=std_excluded_dataset_ids,
    )
    std_stack = build_phase26_stack(std_surfaces)

    participant_count = std_stack.count(dim="dataset").astype(np.int16)
    participant_count.attrs["long_name"] = (
        "Number of std-eligible datasets contributing valid cells"
    )
    participant_count.attrs["units"] = "count"
    participant_count.attrs["excluded_dataset_ids_json"] = json.dumps(
        sorted(std_excluded_dataset_ids)
    )

    mean_wetland = mean_stack.mean(dim="dataset", skipna=True).astype(np.float32)
    mean_wetland.name = "mean_wetland_fraction"
    mean_wetland.attrs["long_name"] = "Mean wetland fraction across all loaded datasets"
    mean_wetland.attrs["units"] = "1"

    std_wetland = _compute_std_wetland_fraction(
        std_stack,
        participant_count=participant_count,
        min_participants=min_participants,
    )

    metrics = xr.Dataset(
        {
            "mean_wetland_fraction": mean_wetland,
            "std_wetland_fraction": std_wetland,
            "participant_count": participant_count,
        }
    )
    metrics.attrs["dataset_ids_json"] = json.dumps(sorted(surfaces))
    metrics.attrs["dataset_count"] = len(surfaces)
    metrics.attrs["std_dataset_ids_json"] = json.dumps(sorted(std_surfaces))
    metrics.attrs["std_dataset_count"] = len(std_surfaces)
    metrics.attrs["std_excluded_dataset_ids_json"] = json.dumps(sorted(std_excluded_dataset_ids))
    metrics.attrs["dispersion_metric"] = "std_wetland_fraction"
    metrics.attrs["std_min_participants"] = int(min_participants)
    landmask_dataset_id = mean_stack.attrs.get("landmask_dataset_id")
    if landmask_dataset_id is not None:
        metrics.attrs["landmask_dataset_id"] = landmask_dataset_id
        metrics.attrs["landmask_rule"] = mean_stack.attrs.get("landmask_rule", "")
    return metrics


def _compute_std_wetland_fraction(
    stack: xr.DataArray,
    participant_count: xr.DataArray,
    *,
    min_participants: int,
) -> xr.DataArray:
    std = stack.std(dim="dataset", skipna=True, ddof=0).astype(np.float32)
    std = xr.where(participant_count >= min_participants, std, np.nan).astype(np.float32)
    std.name = "std_wetland_fraction"
    std.attrs["long_name"] = "Standard deviation of wetland fraction across datasets"
    std.attrs["units"] = "1"
    std.attrs["ddof"] = 0
    return cast(xr.DataArray, std)


def _prepare_surface_for_stack(surface: xr.DataArray) -> xr.DataArray:
    drop_names = [
        name for name in surface.coords if name not in surface.dims and name not in {"lat", "lon"}
    ]
    if not drop_names:
        return surface
    return surface.drop_vars(drop_names, errors="ignore")


def _shared_landmask_dataset_id(surfaces: dict[str, xr.DataArray]) -> str | None:
    landmask_ids = {
        str(surface.attrs["landmask_dataset_id"])
        for surface in surfaces.values()
        if "landmask_dataset_id" in surface.attrs
    }
    if len(landmask_ids) != 1:
        return None
    return next(iter(landmask_ids))


def select_std_surfaces(
    surfaces: dict[str, xr.DataArray],
    *,
    excluded_dataset_ids: tuple[str, ...] | list[str] = DEFAULT_PHASE26_STD_EXCLUDED_DATASET_IDS,
) -> dict[str, xr.DataArray]:
    """Return the subset of surfaces that should participate in rough-scale std."""

    excluded = set(excluded_dataset_ids)
    selected = {
        dataset_id: surface
        for dataset_id, surface in surfaces.items()
        if dataset_id not in excluded
    }
    if len(selected) < 2:
        raise ValueError(
            "At least two std-eligible datasets are required after excluding "
            f"{sorted(excluded)!r}"
        )
    return selected
