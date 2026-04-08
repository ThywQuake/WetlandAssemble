"""Contract-aware Phase 4 percentage surface and summary helpers.

This module restores the missing reusable backbone between the existing
`plot_tropical_wetland_025deg.py` surface route and the live
`phase4_regional.py` summary route.

Key properties:
- non-GWD30 surfaces continue to use the existing live 0.25° plotting logic
- GWD30 surfaces are restored from Phase 4 Stage-1 pixel-statistics tiles
- contract-backed surface and summary artifacts are written/reloaded by
  `dataset_key + region_id` semantics instead of ad hoc filenames
- cache reuse, stage-tagged logging, and atomic writes remain visible
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
import yaml
from matplotlib.colors import LinearSegmentedColormap

from WA._geo_env import configure_geospatial_runtime
from WA.comparison.evidence_contract import (
    DEFAULT_PHASE4_REGIONS_FILE,
    EvidenceContract,
    json_safe_value,
    metadata_json,
    validate_stem_token,
)
from WA.comparison.phase4_regional import (
    DEFAULT_PHASE4_OUTPUT_ROOT,
    DEFAULT_PHASE4_STANDARDIZED_DIR,
    load_phase4_gwd30_pixel_stats_tiles,
    read_phase4_table,
)
from WA.config import load_config
from WA.loaders import get_loader
from WA.loaders.base import BBox
from WA.utils.progress import tqdm
from WA.visualization.coarse_scale import (
    DATASET_DISPLAY_NAMES,
    _aggregate_non_spatial,
    _clip_to_bbox,
    _get_wetland_variable,
    area_weighted_mean_to_regular_grid,
)

configure_geospatial_runtime()

logger = logging.getLogger(__name__)

DEFAULT_TARGET_YEAR = 2016
BERKELEY_TARGET_YEAR = 2019
DEFAULT_RESOLUTION_DEG = 0.25
DEFAULT_CACHE_DIR = Path("results/cache/tropical_025deg")
DEFAULT_PLOT_OUTPUT_DIR = Path("results/figures/tropical_025deg")
DEFAULT_OUTPUT_ROOT = DEFAULT_PHASE4_OUTPUT_ROOT
DEFAULT_STANDARDIZED_DIR = DEFAULT_PHASE4_STANDARDIZED_DIR
DEFAULT_REGIONS_FILE = DEFAULT_PHASE4_REGIONS_FILE
DEFAULT_REGION_ID = "global_tropical_subtropical_35"
DEFAULT_PLOT_DATASET_IDS = (
    "berkeley_rwawc",
    "g2017",
    "giems_mc",
    "glwd_v2",
    "swamps",
    "topmodel",
    "wad2m",
)
SUPPORTED_SURFACE_DATASET_IDS = (
    "berkeley_rwawc",
    "g2017",
    "giems_mc",
    "glwd_v2",
    "gwd30",
    "swamps",
    "topmodel",
    "wad2m",
)
DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS = (
    "gwd30",
    "giems_mc",
    "topmodel",
    "swamps",
    "wad2m",
    "berkeley_rwawc",
)
DEFAULT_PERCENTAGE_DATASET_KEY = "canonical"

STAGE_LOADED = "01_loaded_dataset"
STAGE_WETLAND = "02_wetland_surface"
STAGE_AGGREGATED = "03_aggregated_surface"
STAGE_CLIPPED = "04_clipped_surface"
STAGE_COARSE = "05_coarse_surface"

STAGE_LABELS = {
    STAGE_LOADED: "loaded dataset",
    STAGE_WETLAND: "wetland surface",
    STAGE_AGGREGATED: "aggregated surface",
    STAGE_CLIPPED: "clipped surface",
    STAGE_COARSE: "coarse 0.25deg surface",
}
STAGE_CACHE_VERSIONS = {
    STAGE_WETLAND: 1,
    STAGE_COARSE: 3,
}
CACHE_VERSION_ATTR = "wa_stage_cache_version"

PERCENTAGE_SUMMARY_COLUMNS = (
    "dataset_id",
    "dataset_key",
    "region_id",
    "series_type",
    "time",
    "year",
    "month",
    "wetland_area_km2",
    "valid_area_km2",
    "wetland_percentage",
    "observation_count",
    "is_auxiliary_dataset",
    "contract_metadata_json",
)
REQUIRED_SUMMARY_COLUMNS = (
    "dataset_id",
    "region_id",
    "series_type",
    "time",
    "year",
    "month",
    "wetland_area_km2",
    "valid_area_km2",
    "wetland_percentage",
    "observation_count",
    "is_auxiliary_dataset",
)
REQUIRED_SURFACE_VARS = (
    "wetland_fraction",
    "mean_wetland_percentage",
    "std_wetland_percentage",
    "valid_dataset_count",
)


@dataclass(frozen=True)
class PercentageSurfaceBundle:
    """One contract-backed multi-dataset percentage surface artifact."""

    surface_path: Path
    region_id: str
    region_label: str
    dataset_key: str
    dataset_ids: tuple[str, ...]
    bbox: BBox
    target_year: int | None
    resolution_deg: float
    actual_years: dict[str, int | None]
    dataset: xr.Dataset
    contract_metadata_json: str
    contract_metadata: dict[str, Any]


@dataclass(frozen=True)
class PercentageSummaryBundle:
    """One contract-backed percentage regional summary artifact."""

    summary_path: Path
    region_id: str
    region_label: str
    dataset_key: str
    dataset_ids: tuple[str, ...]
    time_range: tuple[str, str]
    table: pd.DataFrame
    contract_metadata_json: str
    contract_metadata: dict[str, Any]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot regional wetland fraction maps on a 0.25 degree grid. "
            "Explicit GWD30 requests restore the surface from Phase 4 Stage-1 "
            "pixel-statistics tiles."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_PLOT_OUTPUT_DIR,
        help="Directory for PNG and NetCDF outputs.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=(
            "Phase 4 output root used for GWD30 Stage-1 pixel-statistics manifests "
            "(default: results/phase4)."
        ),
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_TARGET_YEAR,
        help="Default target year for dynamic datasets (default: 2016).",
    )
    parser.add_argument(
        "--resolution-deg",
        type=float,
        default=DEFAULT_RESOLUTION_DEG,
        help="Target output resolution in degrees (default: 0.25).",
    )
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=list(DEFAULT_PLOT_DATASET_IDS),
        help=(
            "Dataset ids to process. GWD30 is now supported when explicitly requested "
            "and when Phase 4 Stage-1 pixel-statistics tiles already exist."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Directory for staged processed caches (default: results/cache/tropical_025deg).",
    )
    parser.add_argument(
        "--regions-file",
        type=Path,
        default=DEFAULT_REGIONS_FILE,
        help="Region catalog YAML (default: config/priority_regions.yaml).",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION_ID,
        help="Region id from the region catalog (default: global_tropical_subtropical_35).",
    )
    parser.add_argument(
        "--no-prefer-cache",
        action="store_false",
        dest="prefer_cache",
        help="Recompute from source even if staged processed caches already exist.",
    )
    parser.add_argument(
        "--no-write-cache",
        action="store_false",
        dest="write_cache",
        help="Do not write staged processed caches for this run.",
    )
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show tqdm progress for GWD30 tile restores when available (default: True).",
    )
    return parser.parse_args(argv)


def resolve_surface_dataset_ids(
    requested: Iterable[str] | None = None,
    *,
    default_dataset_ids: tuple[str, ...] = DEFAULT_PLOT_DATASET_IDS,
    allowed_dataset_ids: tuple[str, ...] = SUPPORTED_SURFACE_DATASET_IDS,
) -> tuple[str, ...]:
    """Resolve one explicit dataset-id selection for the surface path."""

    normalized = _flatten_cli_values(requested)
    if not normalized:
        return tuple(default_dataset_ids)
    duplicates = sorted({value for value in normalized if normalized.count(value) > 1})
    if duplicates:
        raise ValueError("Duplicate dataset ids requested: " + ", ".join(duplicates))
    unknown = sorted(set(normalized) - set(allowed_dataset_ids))
    if unknown:
        raise KeyError("Unknown percentage surface dataset ids: " + ", ".join(unknown))
    return tuple(normalized)


def resolve_contract_dataset_ids(requested: Iterable[str] | None = None) -> tuple[str, ...]:
    """Resolve one deterministic ordered percentage contract dataset set."""

    normalized = _flatten_cli_values(requested)
    if not normalized:
        return DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS
    duplicates = sorted({value for value in normalized if normalized.count(value) > 1})
    if duplicates:
        raise ValueError("Duplicate dataset ids requested: " + ", ".join(duplicates))
    unknown = sorted(set(normalized) - set(DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS))
    if unknown:
        raise KeyError("Unknown percentage contract dataset ids: " + ", ".join(unknown))
    wanted = set(normalized)
    return tuple(
        dataset_id for dataset_id in DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS if dataset_id in wanted
    )


def build_percentage_dataset_key(dataset_ids: Iterable[str]) -> str:
    """Build one stable dataset-key token for the percentage family."""

    ordered = tuple(
        validate_stem_token(dataset_id, label="dataset_id") for dataset_id in dataset_ids
    )
    if not ordered:
        raise ValueError("dataset_ids must not be empty")
    if ordered == DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS:
        return DEFAULT_PERCENTAGE_DATASET_KEY
    return "+".join(ordered)


def resolved_target_year(dataset_id: str, default_year: int) -> int | None:
    if dataset_id == "berkeley_rwawc":
        return BERKELEY_TARGET_YEAR
    if dataset_id in {"g2017", "glwd_v2"}:
        return None
    return default_year


def requested_time_range(dataset_id: str, target_year: int | None) -> tuple[str, str] | None:
    if target_year is None:
        return None
    return (f"{target_year}-01-01", f"{target_year}-12-31")


def _year_key(target_year: int | None) -> str:
    return f"year_{target_year}" if target_year is not None else "static"


def _resolution_key(resolution_deg: float) -> str:
    text = f"{resolution_deg:.6f}".rstrip("0").rstrip(".")
    return f"res_{text.replace('.', 'p')}"


def stage_cache_dir(
    cache_root: Path,
    dataset_id: str,
    region_id: str,
    *,
    target_year: int | None,
    resolution_deg: float,
) -> Path:
    return (
        cache_root
        / region_id
        / dataset_id
        / _year_key(target_year)
        / _resolution_key(resolution_deg)
    )


def stage_cache_path(
    cache_root: Path,
    dataset_id: str,
    region_id: str,
    *,
    target_year: int | None,
    resolution_deg: float,
    stage_name: str,
) -> Path:
    return (
        stage_cache_dir(
            cache_root,
            dataset_id,
            region_id,
            target_year=target_year,
            resolution_deg=resolution_deg,
        )
        / f"{stage_name}.nc"
    )


def _log(dataset_id: str, message: str) -> None:
    print(f"[{dataset_id}] {message}", flush=True)


def _write_netcdf_atomically(path: Path, write_fn) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp-{os.getpid()}-{uuid4().hex}"
    try:
        write_fn(tmp_path)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    try:
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _sanitize_attr_value(value: Any) -> Any:
    if isinstance(value, bool | np.bool_):
        return int(value)
    if isinstance(value, dict | list | tuple | set):
        return json.dumps(json_safe_value(value), sort_keys=True)
    return value


def _sanitize_attrs(attrs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): _sanitize_attr_value(value) for key, value in attrs.items() if value is not None
    }


def _sanitize_dataset_for_netcdf(dataset: xr.Dataset) -> xr.Dataset:
    clean = dataset.copy(deep=False)
    clean.attrs = _sanitize_attrs(dict(clean.attrs))
    for var_name in clean.data_vars:
        clean[var_name].attrs = _sanitize_attrs(dict(clean[var_name].attrs))
    for coord_name in clean.coords:
        clean[coord_name].attrs = _sanitize_attrs(dict(clean[coord_name].attrs))
        clean[coord_name].encoding = {}
    return clean


def _sanitize_dataarray_for_netcdf(data: xr.DataArray) -> xr.DataArray:
    clean = data.copy(deep=False)
    clean.attrs = _sanitize_attrs(dict(clean.attrs))
    for coord_name in clean.coords:
        clean[coord_name].attrs = _sanitize_attrs(dict(clean[coord_name].attrs))
        clean[coord_name].encoding = {}
    return clean


def _save_cached_dataset(
    path: Path,
    dataset: xr.Dataset,
    *,
    dataset_id: str,
    stage_name: str,
) -> None:
    clean = _sanitize_dataset_for_netcdf(dataset)
    _log(
        dataset_id,
        f"stage=percentage-surface action=cache-write stage={stage_name} path={path}",
    )
    _write_netcdf_atomically(path, clean.to_netcdf)


def _save_cached_dataarray(
    path: Path,
    data: xr.DataArray,
    *,
    dataset_id: str,
    stage_name: str,
) -> None:
    clean = _sanitize_dataarray_for_netcdf(data)
    expected_version = STAGE_CACHE_VERSIONS.get(stage_name)
    if expected_version is not None:
        clean.attrs[CACHE_VERSION_ATTR] = expected_version
    _log(
        dataset_id,
        f"stage=percentage-surface action=cache-write stage={stage_name} path={path}",
    )
    _write_netcdf_atomically(path, clean.to_netcdf)


def _load_cached_dataset(
    path: Path,
    *,
    dataset_id: str,
    stage_name: str,
) -> xr.Dataset | None:
    if not path.is_file():
        _log(
            dataset_id,
            f"stage=percentage-surface action=cache-miss stage={stage_name} path={path}",
        )
        return None
    try:
        cached = xr.open_dataset(path)
        try:
            loaded = cached.load()
        finally:
            cached.close()
        _log(
            dataset_id,
            f"stage=percentage-surface action=cache-hit stage={stage_name} path={path}",
        )
        return loaded
    except Exception as exc:  # noqa: BLE001
        _log(
            dataset_id,
            "stage=percentage-surface action=cache-invalid "
            f"stage={stage_name} path={path} error={type(exc).__name__}: {exc}",
        )
        return None


def _load_cached_dataarray(
    path: Path,
    *,
    dataset_id: str,
    stage_name: str,
) -> xr.DataArray | None:
    if not path.is_file():
        _log(
            dataset_id,
            f"stage=percentage-surface action=cache-miss stage={stage_name} path={path}",
        )
        return None
    try:
        cached = xr.open_dataarray(path)
        try:
            loaded = cached.load()
        finally:
            cached.close()
        expected_version = STAGE_CACHE_VERSIONS.get(stage_name)
        if expected_version is not None:
            actual_version = loaded.attrs.get(CACHE_VERSION_ATTR)
            if actual_version != expected_version:
                _log(
                    dataset_id,
                    "stage=percentage-surface action=cache-stale "
                    f"stage={stage_name} path={path} "
                    f"expected={expected_version} got={actual_version!r}",
                )
                return None
        _log(
            dataset_id,
            f"stage=percentage-surface action=cache-hit stage={stage_name} path={path}",
        )
        return loaded
    except Exception as exc:  # noqa: BLE001
        _log(
            dataset_id,
            "stage=percentage-surface action=cache-invalid "
            f"stage={stage_name} path={path} error={type(exc).__name__}: {exc}",
        )
        return None


def _as_dataset(data: xr.Dataset | xr.DataArray) -> xr.Dataset:
    if isinstance(data, xr.Dataset):
        return data
    name = data.name or "wetland_fraction"
    return data.to_dataset(name=name)


def _bbox_to_cartopy_extent(bbox: BBox) -> BBox:
    west, south, east, north = bbox
    return (west, east, south, north)


def load_plot_regions(path: Path) -> dict[str, dict[str, object]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict) or not isinstance(document.get("regions"), dict):
        raise ValueError("Region document must contain a top-level 'regions' mapping")

    loaded: dict[str, dict[str, object]] = {}
    for region_id, payload in document["regions"].items():
        if not isinstance(payload, dict):
            raise ValueError(f"Region {region_id!r} must be a mapping")
        bbox = payload.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"Region {region_id!r} must define bbox as 4-item list")
        loaded[str(region_id)] = {
            "label": str(payload.get("label", region_id)),
            "bbox": (
                float(bbox[0]),
                float(bbox[1]),
                float(bbox[2]),
                float(bbox[3]),
            ),
        }
    return loaded


def resolve_plot_region(
    region_id: str,
    *,
    regions_file: Path,
) -> tuple[str, BBox]:
    regions = load_plot_regions(regions_file)
    if region_id not in regions:
        available = ", ".join(sorted(regions))
        raise KeyError(f"Unknown region {region_id!r}; available regions: {available}")
    region = regions[region_id]
    label = str(region["label"])
    bbox_values = region["bbox"]
    bbox: BBox = (
        float(bbox_values[0]),
        float(bbox_values[1]),
        float(bbox_values[2]),
        float(bbox_values[3]),
    )
    return label, bbox


def load_tropical_surface(
    dataset_id: str,
    *,
    region_id: str,
    bbox: BBox,
    target_year: int | None,
    resolution_deg: float,
    cache_dir: Path,
    prefer_cache: bool = True,
    write_cache: bool = True,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    standardized_dir: str | Path = DEFAULT_STANDARDIZED_DIR,
    show_progress: bool = True,
) -> tuple[int | None, xr.DataArray]:
    """Load one dataset's region-scoped coarse surface with visible cache reuse.

    For non-GWD30 datasets this remains the existing plotting route.
    For GWD30 the wetland surface is rebuilt from Stage-1 pixel-statistics tiles.
    """

    normalized_dataset_id = validate_stem_token(dataset_id, label="dataset_id")
    if normalized_dataset_id not in SUPPORTED_SURFACE_DATASET_IDS:
        supported = ", ".join(SUPPORTED_SURFACE_DATASET_IDS)
        raise KeyError(
            "stage=percentage-surface "
            f"dataset_id={normalized_dataset_id} region_id={region_id} "
            f"unknown dataset_id; supported={supported}"
        )

    cache_stage_dir = stage_cache_dir(
        cache_dir,
        normalized_dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
    )
    loaded_cache_path = stage_cache_path(
        cache_dir,
        normalized_dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
        stage_name=STAGE_LOADED,
    )
    wetland_cache_path = stage_cache_path(
        cache_dir,
        normalized_dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
        stage_name=STAGE_WETLAND,
    )
    aggregated_cache_path = stage_cache_path(
        cache_dir,
        normalized_dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
        stage_name=STAGE_AGGREGATED,
    )
    clipped_cache_path = stage_cache_path(
        cache_dir,
        normalized_dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
        stage_name=STAGE_CLIPPED,
    )
    coarse_cache_path = stage_cache_path(
        cache_dir,
        normalized_dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
        stage_name=STAGE_COARSE,
    )

    dataset: xr.Dataset | None = None
    try:
        _log(
            normalized_dataset_id,
            "stage=percentage-surface action=pipeline-start "
            f"region_id={region_id} cache_root={cache_stage_dir}",
        )
        coarse = (
            _load_cached_dataarray(
                coarse_cache_path,
                dataset_id=normalized_dataset_id,
                stage_name=STAGE_COARSE,
            )
            if prefer_cache
            else None
        )
        if coarse is None:
            clipped = (
                _load_cached_dataarray(
                    clipped_cache_path,
                    dataset_id=normalized_dataset_id,
                    stage_name=STAGE_CLIPPED,
                )
                if prefer_cache
                else None
            )
            if clipped is None:
                if normalized_dataset_id == "gwd30":
                    wetland = (
                        _load_cached_dataarray(
                            wetland_cache_path,
                            dataset_id=normalized_dataset_id,
                            stage_name=STAGE_WETLAND,
                        )
                        if prefer_cache
                        else None
                    )
                    if wetland is None:
                        wetland = _build_gwd30_stage1_surface(
                            dataset_id=normalized_dataset_id,
                            region_id=region_id,
                            bbox=bbox,
                            target_year=target_year,
                            output_root=Path(output_root),
                            show_progress=show_progress,
                        )
                        if write_cache:
                            _save_cached_dataarray(
                                wetland_cache_path,
                                wetland,
                                dataset_id=normalized_dataset_id,
                                stage_name=STAGE_WETLAND,
                            )
                    clipped = _clip_to_bbox(wetland, bbox)
                    if int(clipped.count().item()) == 0:
                        raise ValueError(
                            f"stage=percentage-surface dataset_id={normalized_dataset_id} "
                            f"region_id={region_id} empty clipped GWD30 surface"
                        )
                else:
                    aggregated = (
                        _load_cached_dataarray(
                            aggregated_cache_path,
                            dataset_id=normalized_dataset_id,
                            stage_name=STAGE_AGGREGATED,
                        )
                        if prefer_cache
                        else None
                    )
                    if aggregated is None:
                        wetland = (
                            _load_cached_dataarray(
                                wetland_cache_path,
                                dataset_id=normalized_dataset_id,
                                stage_name=STAGE_WETLAND,
                            )
                            if prefer_cache
                            else None
                        )
                        if wetland is None:
                            dataset = (
                                _load_cached_dataset(
                                    loaded_cache_path,
                                    dataset_id=normalized_dataset_id,
                                    stage_name=STAGE_LOADED,
                                )
                                if prefer_cache
                                else None
                            )
                            if dataset is None:
                                _log(
                                    normalized_dataset_id,
                                    "stage=percentage-surface action=load-source "
                                    f"region_id={region_id} target_year={target_year}",
                                )
                                config = load_config(
                                    "config/datasets.yaml", "config/gee_config.yaml"
                                )
                                dataset_config = config.datasets[normalized_dataset_id]
                                loader = get_loader(normalized_dataset_id, dataset_config)
                                dataset = _as_dataset(
                                    loader.load(
                                        bbox=bbox,
                                        time_range=requested_time_range(
                                            normalized_dataset_id,
                                            target_year,
                                        ),
                                    )
                                )
                                if write_cache:
                                    _save_cached_dataset(
                                        loaded_cache_path,
                                        dataset,
                                        dataset_id=normalized_dataset_id,
                                        stage_name=STAGE_LOADED,
                                    )

                            wetland = _get_wetland_variable(dataset, normalized_dataset_id)
                            if wetland is None:
                                raise ValueError(
                                    f"stage=percentage-surface dataset_id={normalized_dataset_id} "
                                    f"region_id={region_id} has no wetland variable"
                                )
                            if target_year is not None and "time" in wetland.dims:
                                time_coord = wetland.coords["time"]
                                if hasattr(time_coord.dt, "year"):
                                    wetland = wetland.sel(time=time_coord.dt.year == target_year)
                            if write_cache:
                                _save_cached_dataarray(
                                    wetland_cache_path,
                                    wetland,
                                    dataset_id=normalized_dataset_id,
                                    stage_name=STAGE_WETLAND,
                                )

                        aggregated = _aggregate_non_spatial(wetland, aggregation="mean")
                        if write_cache:
                            _save_cached_dataarray(
                                aggregated_cache_path,
                                aggregated,
                                dataset_id=normalized_dataset_id,
                                stage_name=STAGE_AGGREGATED,
                            )

                    clipped = _clip_to_bbox(aggregated, bbox)
                    if int(clipped.count().item()) == 0:
                        raise ValueError(
                            f"stage=percentage-surface dataset_id={normalized_dataset_id} "
                            f"region_id={region_id} produced no valid cells"
                        )

                if write_cache:
                    _save_cached_dataarray(
                        clipped_cache_path,
                        clipped,
                        dataset_id=normalized_dataset_id,
                        stage_name=STAGE_CLIPPED,
                    )

            coarse = area_weighted_mean_to_regular_grid(
                clipped,
                bbox,
                resolution_deg=resolution_deg,
            )
            if int(coarse.count().item()) == 0:
                raise ValueError(
                    f"stage=percentage-surface dataset_id={normalized_dataset_id} "
                    f"region_id={region_id} produced an empty coarse surface"
                )
            if write_cache:
                _save_cached_dataarray(
                    coarse_cache_path,
                    coarse,
                    dataset_id=normalized_dataset_id,
                    stage_name=STAGE_COARSE,
                )

        actual_year = target_year
        if dataset is not None and target_year is None and "time" in dataset.coords:
            actual_year = int(dataset["time"].dt.year.values[0])
        _log(
            normalized_dataset_id,
            "stage=percentage-surface action=pipeline-complete "
            f"region_id={region_id} "
            f"actual_year={actual_year if actual_year is not None else 'static'}",
        )
        return actual_year, coarse
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, (FileNotFoundError, KeyError, ValueError)):
            raise type(exc)(
                f"stage=percentage-surface dataset_id={normalized_dataset_id} "
                f"region_id={region_id} {exc}"
            ) from exc
        raise RuntimeError(
            f"stage=percentage-surface dataset_id={normalized_dataset_id} "
            f"region_id={region_id} {type(exc).__name__}: {exc}"
        ) from exc
    finally:
        close = getattr(dataset, "close", None)
        if callable(close):
            close()


def _build_gwd30_stage1_surface(
    *,
    dataset_id: str,
    region_id: str,
    bbox: BBox,
    target_year: int | None,
    output_root: Path,
    show_progress: bool,
) -> xr.DataArray:
    if target_year is None:
        raise ValueError("GWD30 requires an explicit target_year")

    stats_tiles = load_phase4_gwd30_pixel_stats_tiles(
        output_root,
        year=target_year,
        aggregation="monthly",
    )
    candidate_tiles = [
        (tile_path, tile_bbox)
        for tile_path, tile_bbox in stats_tiles
        if _bbox_intersects(tile_bbox, bbox)
    ]
    _log(
        dataset_id,
        "stage=percentage-surface action=gwd30-tile-restore "
        f"region_id={region_id} year={target_year} restored={len(stats_tiles)} "
        f"candidates={len(candidate_tiles)}",
    )
    if not candidate_tiles:
        raise FileNotFoundError(
            f"No Stage-1 GWD30 pixel-statistics tiles intersect the requested bbox {bbox!r}"
        )

    annual_datasets: list[xr.Dataset] = []
    tile_progress = tqdm(
        candidate_tiles,
        total=len(candidate_tiles),
        desc=f"percentage-surface gwd30 {region_id} {target_year}",
        disable=not show_progress,
    )
    for tile_path, _tile_bbox in tile_progress:
        with xr.open_dataset(tile_path, engine="netcdf4") as source:
            if "wetland_fraction" not in source:
                raise KeyError(
                    f"Expected wetland_fraction in Stage-1 pixel-statistics tile: {tile_path}"
                )
            wetland_fraction = source["wetland_fraction"].load()
        if "band" in wetland_fraction.dims:
            if wetland_fraction.sizes["band"] != 1:
                raise ValueError(
                    f"Expected a singleton band dimension in GWD30 Stage-1 tile: {tile_path}"
                )
            wetland_fraction = wetland_fraction.isel(band=0, drop=True)
        if "time" in wetland_fraction.dims:
            time_coord = pd.to_datetime(wetland_fraction.coords["time"].values)
            in_year = xr.DataArray(
                time_coord.year == target_year,
                dims=("time",),
                coords={"time": wetland_fraction.coords["time"]},
            )
            wetland_fraction = wetland_fraction.sel(time=in_year)
            if wetland_fraction.sizes.get("time", 0) == 0:
                continue
            wetland_fraction = wetland_fraction.mean(dim="time", skipna=True)
        wetland_fraction = wetland_fraction.astype(np.float32)
        clipped = _clip_to_bbox(wetland_fraction, bbox)
        if int(clipped.count().item()) == 0:
            continue
        annual_datasets.append(clipped.to_dataset(name="wetland_fraction"))

    if not annual_datasets:
        raise ValueError(
            "No valid GWD30 Stage-1 tile cells remained after clipping to the region bbox"
        )

    merged = xr.combine_by_coords(annual_datasets, combine_attrs="drop_conflicts")
    wetland = merged["wetland_fraction"].load()
    if int(wetland.count().item()) == 0:
        raise ValueError("Merged GWD30 Stage-1 surface is empty")
    wetland.attrs.update(
        {
            "dataset_id": dataset_id,
            "source": "phase4_stage1_pixel_stats",
            "stage": "percentage-surface",
            "region_id": region_id,
            "target_year": int(target_year),
            "candidate_tile_count": int(len(candidate_tiles)),
        }
    )
    return wetland


def percentage_surface_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_key: str,
) -> Path:
    return contract.artifact_output_path(
        kind="surface",
        dataset_or_key=dataset_key,
        region_id=region_id,
    )


def percentage_summary_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_key: str,
) -> Path:
    return contract.artifact_output_path(
        kind="regional_summary",
        dataset_or_key=dataset_key,
        region_id=region_id,
    )


def build_contract_percentage_surface_bundle(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_label: str,
    bbox: BBox,
    dataset_key: str,
    dataset_ids: Iterable[str],
    surface_year: int,
    resolution_deg: float,
    cache_dir: Path,
    output_root: str | Path,
    standardized_dir: str | Path,
    prefer_cache: bool,
    write_cache: bool,
    show_progress: bool,
) -> PercentageSurfaceBundle:
    """Build and write the contract-backed multi-dataset coarse surface."""

    ordered_dataset_ids = tuple(dataset_ids)
    actual_years: dict[str, int | None] = {}
    surfaces: dict[str, xr.DataArray] = {}
    for dataset_id in ordered_dataset_ids:
        target_year = resolved_target_year(dataset_id, surface_year)
        actual_year, surface = load_tropical_surface(
            dataset_id,
            region_id=region_id,
            bbox=bbox,
            target_year=target_year,
            resolution_deg=resolution_deg,
            cache_dir=cache_dir,
            prefer_cache=prefer_cache,
            write_cache=write_cache,
            output_root=output_root,
            standardized_dir=standardized_dir,
            show_progress=show_progress,
        )
        actual_years[dataset_id] = actual_year
        surfaces[dataset_id] = surface
    return write_contract_percentage_surface(
        contract=contract,
        region_id=region_id,
        region_label=region_label,
        dataset_key=dataset_key,
        dataset_ids=ordered_dataset_ids,
        bbox=bbox,
        surface_year=surface_year,
        resolution_deg=resolution_deg,
        actual_years=actual_years,
        surfaces=surfaces,
    )


def write_contract_percentage_surface(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_label: str,
    dataset_key: str,
    dataset_ids: Iterable[str],
    bbox: BBox,
    surface_year: int,
    resolution_deg: float,
    actual_years: Mapping[str, int | None],
    surfaces: Mapping[str, xr.DataArray],
) -> PercentageSurfaceBundle:
    ordered_dataset_ids = tuple(
        validate_stem_token(dataset_id, label="dataset_id") for dataset_id in dataset_ids
    )
    if not ordered_dataset_ids:
        raise ValueError("dataset_ids must not be empty")
    if set(ordered_dataset_ids) != set(surfaces.keys()):
        raise ValueError("surfaces keys must match dataset_ids exactly")

    reference = surfaces[ordered_dataset_ids[0]]
    y_dim, x_dim = _surface_spatial_dims(reference)
    stack = xr.concat(
        [
            surfaces[dataset_id]
            .rename("wetland_fraction")
            .expand_dims(dataset_id=[dataset_id])
            .transpose("dataset_id", y_dim, x_dim)
            for dataset_id in ordered_dataset_ids
        ],
        dim="dataset_id",
    ).astype(np.float32)
    max_dataset_id_len = max(len(dataset_id) for dataset_id in ordered_dataset_ids)
    stack = stack.assign_coords(
        dataset_id=(
            "dataset_id",
            np.asarray(list(ordered_dataset_ids), dtype=f"<U{max_dataset_id_len}"),
        )
    )
    for dataset_id in ordered_dataset_ids[1:]:
        current = surfaces[dataset_id]
        current_y_dim, current_x_dim = _surface_spatial_dims(current)
        if current_y_dim != y_dim or current_x_dim != x_dim:
            raise ValueError("All percentage surfaces must share the same spatial-dim names")
        if not np.array_equal(current.coords[y_dim].values, reference.coords[y_dim].values):
            raise ValueError("All percentage surfaces must share the same y coordinates")
        if not np.array_equal(current.coords[x_dim].values, reference.coords[x_dim].values):
            raise ValueError("All percentage surfaces must share the same x coordinates")

    mean_fraction = stack.mean(dim="dataset_id", skipna=True)
    std_fraction = stack.std(dim="dataset_id", skipna=True)
    valid_dataset_count = stack.notnull().sum(dim="dataset_id").astype(np.int16)

    contract_metadata = {
        "artifact_kind": "surface",
        "dataset_key": dataset_key,
        "dataset_ids": list(ordered_dataset_ids),
        "region_id": region_id,
        "region_label": region_label,
        "bbox": list(bbox),
        "surface_year": int(surface_year),
        "resolution_deg": float(resolution_deg),
        "actual_years": dict(actual_years),
        "surface_variable": "wetland_fraction",
        "metric_variables": [
            "mean_wetland_percentage",
            "std_wetland_percentage",
            "valid_dataset_count",
        ],
    }
    contract_metadata_json = metadata_json(contract_metadata)
    dataset = xr.Dataset(
        data_vars={
            "wetland_fraction": stack,
            "mean_wetland_percentage": (mean_fraction * 100.0).astype(np.float32),
            "std_wetland_percentage": (std_fraction * 100.0).astype(np.float32),
            "valid_dataset_count": valid_dataset_count,
        }
    )
    max_year_label_len = max(
        len("static")
        if actual_years.get(dataset_id) is None
        else len(str(actual_years.get(dataset_id)))
        for dataset_id in ordered_dataset_ids
    )
    dataset = dataset.assign_coords(
        dataset_year_label=(
            "dataset_id",
            np.asarray(
                [
                    "static"
                    if actual_years.get(dataset_id) is None
                    else str(actual_years.get(dataset_id))
                    for dataset_id in ordered_dataset_ids
                ],
                dtype=f"<U{max_year_label_len}",
            ),
        )
    )
    dataset.attrs.update(
        {
            "region_id": region_id,
            "region_label": region_label,
            "dataset_key": dataset_key,
            "dataset_ids_json": json.dumps(list(ordered_dataset_ids), separators=(",", ":")),
            "bbox_json": json.dumps(list(bbox), separators=(",", ":")),
            "surface_year": int(surface_year),
            "resolution_deg": float(resolution_deg),
            "actual_years_json": json.dumps(dict(actual_years), sort_keys=True),
            "contract_metadata_json": contract_metadata_json,
        }
    )

    surface_path = percentage_surface_output_path(
        contract,
        region_id=region_id,
        dataset_key=dataset_key,
    )
    clean = _sanitize_dataset_for_netcdf(dataset)
    _write_netcdf_atomically(surface_path, clean.to_netcdf)
    logger.info(
        "stage=percentage-surface region=%s action=write-complete "
        "dataset_key=%s datasets=%s path=%s",
        region_id,
        dataset_key,
        ordered_dataset_ids,
        surface_path,
    )
    return load_contract_percentage_surface(
        contract=contract,
        region_id=region_id,
        dataset_key=dataset_key,
        expected_dataset_ids=ordered_dataset_ids,
    )


def load_contract_percentage_surface(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_key: str,
    expected_dataset_ids: Iterable[str] | None = None,
) -> PercentageSurfaceBundle:
    surface_path = percentage_surface_output_path(
        contract,
        region_id=region_id,
        dataset_key=dataset_key,
    )
    if not surface_path.is_file():
        raise FileNotFoundError(
            "Contract percentage surface is missing: "
            f"region_id={region_id} dataset_key={dataset_key} path={surface_path}"
        )

    dataset = xr.load_dataset(surface_path)
    missing_vars = [name for name in REQUIRED_SURFACE_VARS if name not in dataset.data_vars]
    if missing_vars:
        raise ValueError(
            "Contract percentage surface is missing required variables: " + ", ".join(missing_vars)
        )
    if str(dataset.attrs.get("region_id", "")).strip() != region_id:
        raise ValueError(
            "Contract percentage surface region_id does not match the requested region"
        )
    if str(dataset.attrs.get("dataset_key", "")).strip() != dataset_key:
        raise ValueError("Contract percentage surface dataset_key does not match the requested key")

    try:
        dataset_ids_raw = json.loads(str(dataset.attrs.get("dataset_ids_json", "")))
    except json.JSONDecodeError as exc:
        raise ValueError("Malformed dataset_ids_json on contract percentage surface") from exc
    if not isinstance(dataset_ids_raw, list) or not dataset_ids_raw:
        raise ValueError(
            "Contract percentage surface dataset_ids_json must decode to a non-empty list"
        )
    dataset_ids = tuple(
        validate_stem_token(str(dataset_id), label="dataset_id") for dataset_id in dataset_ids_raw
    )
    expected_order = (
        tuple(expected_dataset_ids) if expected_dataset_ids is not None else dataset_ids
    )
    if tuple(dataset.coords["dataset_id"].astype(str).values.tolist()) != dataset_ids:
        raise ValueError(
            "Contract percentage surface dataset_id coordinate does not match dataset_ids_json"
        )
    if expected_dataset_ids is not None and dataset_ids != expected_order:
        raise ValueError("Contract percentage surface dataset ids do not match the expected set")

    try:
        bbox_raw = json.loads(str(dataset.attrs.get("bbox_json", "")))
    except json.JSONDecodeError as exc:
        raise ValueError("Malformed bbox_json on contract percentage surface") from exc
    if not isinstance(bbox_raw, list) or len(bbox_raw) != 4:
        raise ValueError("Contract percentage surface bbox_json must decode to a 4-item list")
    bbox = tuple(float(value) for value in bbox_raw)
    if int(dataset["mean_wetland_percentage"].count().item()) == 0:
        raise ValueError("Contract percentage surface is empty")

    contract_metadata_json = str(dataset.attrs.get("contract_metadata_json", "")).strip()
    if not contract_metadata_json:
        raise ValueError("Contract percentage surface is missing contract_metadata_json")
    try:
        contract_metadata = json.loads(contract_metadata_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Malformed contract_metadata_json on contract percentage surface") from exc
    if not isinstance(contract_metadata, dict):
        raise ValueError(
            "Contract percentage surface contract_metadata_json must decode to an object"
        )

    try:
        actual_years = json.loads(str(dataset.attrs.get("actual_years_json", "{}")))
    except json.JSONDecodeError as exc:
        raise ValueError("Malformed actual_years_json on contract percentage surface") from exc
    if not isinstance(actual_years, dict):
        raise ValueError("Contract percentage surface actual_years_json must decode to an object")

    return PercentageSurfaceBundle(
        surface_path=surface_path.resolve(),
        region_id=region_id,
        region_label=str(dataset.attrs.get("region_label", region_id)),
        dataset_key=dataset_key,
        dataset_ids=dataset_ids,
        bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
        target_year=int(dataset.attrs.get("surface_year", DEFAULT_TARGET_YEAR)),
        resolution_deg=float(dataset.attrs.get("resolution_deg", DEFAULT_RESOLUTION_DEG)),
        actual_years={
            key: (None if value is None else int(value)) for key, value in actual_years.items()
        },
        dataset=dataset,
        contract_metadata_json=contract_metadata_json,
        contract_metadata=contract_metadata,
    )


def write_contract_percentage_summary(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_label: str,
    dataset_key: str,
    dataset_ids: Iterable[str],
    table: pd.DataFrame,
    time_range: tuple[str, str],
    source_region_table_path: str | Path | None = None,
) -> PercentageSummaryBundle:
    ordered_dataset_ids = tuple(
        validate_stem_token(dataset_id, label="dataset_id") for dataset_id in dataset_ids
    )
    prepared = table.copy()
    missing_columns = [
        column for column in REQUIRED_SUMMARY_COLUMNS if column not in prepared.columns
    ]
    if missing_columns:
        raise ValueError(
            "Contract percentage summary is missing required columns: " + ", ".join(missing_columns)
        )
    prepared = prepared.loc[prepared["dataset_id"].isin(ordered_dataset_ids)].copy()
    if prepared.empty:
        raise ValueError("Contract percentage summary is empty after dataset filtering")
    present_dataset_ids = tuple(
        dataset_id
        for dataset_id in ordered_dataset_ids
        if dataset_id in set(prepared["dataset_id"])
    )
    if present_dataset_ids != ordered_dataset_ids:
        missing_dataset_ids = [
            dataset_id
            for dataset_id in ordered_dataset_ids
            if dataset_id not in set(prepared["dataset_id"])
        ]
        raise ValueError(
            "Contract percentage summary is missing dataset rows for: "
            + ", ".join(missing_dataset_ids)
        )
    if any(str(value).strip() != region_id for value in prepared["region_id"]):
        raise ValueError("Contract percentage summary contains mixed region_id values")

    prepared["time"] = pd.to_datetime(prepared["time"])
    contract_metadata = {
        "artifact_kind": "regional_summary",
        "dataset_key": dataset_key,
        "dataset_ids": list(ordered_dataset_ids),
        "region_id": region_id,
        "region_label": region_label,
        "time_range": list(time_range),
        "source_region_table_path": (
            str(Path(source_region_table_path).resolve())
            if source_region_table_path is not None
            else None
        ),
    }
    contract_metadata_json = metadata_json(contract_metadata)
    prepared["dataset_key"] = dataset_key
    prepared["contract_metadata_json"] = contract_metadata_json
    prepared = prepared.loc[:, list(PERCENTAGE_SUMMARY_COLUMNS)]
    prepared = prepared.sort_values(["dataset_id", "series_type", "time"], kind="mergesort")

    summary_path = percentage_summary_output_path(
        contract,
        region_id=region_id,
        dataset_key=dataset_key,
    )
    _write_text_atomic(summary_path, prepared.to_csv(index=False, lineterminator="\n"))
    logger.info(
        "stage=percentage-summary region=%s action=write-complete dataset_key=%s rows=%s path=%s",
        region_id,
        dataset_key,
        len(prepared),
        summary_path,
    )
    return load_contract_percentage_summary(
        contract=contract,
        region_id=region_id,
        dataset_key=dataset_key,
        expected_dataset_ids=ordered_dataset_ids,
    )


def load_contract_percentage_summary(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_key: str,
    expected_dataset_ids: Iterable[str] | None = None,
) -> PercentageSummaryBundle:
    summary_path = percentage_summary_output_path(
        contract,
        region_id=region_id,
        dataset_key=dataset_key,
    )
    if not summary_path.is_file():
        raise FileNotFoundError(
            "Contract percentage summary is missing: "
            f"region_id={region_id} dataset_key={dataset_key} path={summary_path}"
        )

    table = read_phase4_table(summary_path)
    missing_columns = [
        column for column in PERCENTAGE_SUMMARY_COLUMNS if column not in table.columns
    ]
    if missing_columns:
        raise ValueError(
            "Contract percentage summary is missing required columns: " + ", ".join(missing_columns)
        )
    if table.empty:
        raise ValueError("Contract percentage summary must not be empty")
    if any(str(value).strip() != region_id for value in table["region_id"]):
        raise ValueError("Contract percentage summary contains mixed region_id values")
    if any(str(value).strip() != dataset_key for value in table["dataset_key"]):
        raise ValueError("Contract percentage summary contains mixed dataset_key values")

    metadata_values = {str(value).strip() for value in table["contract_metadata_json"]}
    if len(metadata_values) != 1:
        raise ValueError(
            "Contract percentage summary must contain exactly one contract_metadata_json value"
        )
    contract_metadata_json = metadata_values.pop()
    try:
        contract_metadata = json.loads(contract_metadata_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Malformed contract_metadata_json in contract percentage summary") from exc
    if not isinstance(contract_metadata, dict):
        raise ValueError(
            "Contract percentage summary contract_metadata_json must decode to an object"
        )

    dataset_ids = tuple(
        validate_stem_token(str(dataset_id), label="dataset_id")
        for dataset_id in contract_metadata.get("dataset_ids", [])
    )
    if not dataset_ids:
        raise ValueError(
            "Contract percentage summary contract_metadata_json is missing dataset_ids"
        )
    if expected_dataset_ids is not None and dataset_ids != tuple(expected_dataset_ids):
        raise ValueError("Contract percentage summary dataset ids do not match the expected set")
    if set(table["dataset_id"]) != set(dataset_ids):
        raise ValueError(
            "Contract percentage summary table dataset_id values do not match metadata"
        )

    time_range_raw = contract_metadata.get("time_range")
    if not isinstance(time_range_raw, list) or len(time_range_raw) != 2:
        raise ValueError("Contract percentage summary metadata is missing a 2-item time_range")
    time_range = (str(time_range_raw[0]), str(time_range_raw[1]))

    return PercentageSummaryBundle(
        summary_path=summary_path.resolve(),
        region_id=region_id,
        region_label=str(contract_metadata.get("region_label", region_id)),
        dataset_key=dataset_key,
        dataset_ids=dataset_ids,
        time_range=time_range,
        table=table.copy(),
        contract_metadata_json=contract_metadata_json,
        contract_metadata=contract_metadata,
    )


def save_surface_plot(
    surface: xr.DataArray,
    dataset_id: str,
    *,
    region_id: str,
    region_label: str,
    bbox: BBox,
    output_dir: Path,
    actual_year: int | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"{dataset_id}_{region_id}_025deg.png"
    nc_path = output_dir / f"{dataset_id}_{region_id}_025deg.nc"

    display_name = DATASET_DISPLAY_NAMES.get(dataset_id, dataset_id)
    cmap = LinearSegmentedColormap.from_list("wetland_wb", ["#ffffff", "#1f77b4"])
    output_dataset = _sanitize_dataset_for_netcdf(surface.to_dataset(name="wetland_fraction"))

    _log(dataset_id, f"writing final NetCDF output -> {nc_path}")
    _write_netcdf_atomically(nc_path, output_dataset.to_netcdf)
    _log(dataset_id, "final NetCDF saved")

    use_cartopy = False
    transform = None
    try:
        import cartopy.crs as ccrs

        use_cartopy = True
        transform = ccrs.PlateCarree()
        _log(dataset_id, "cartopy detected, coastlines enabled")
    except ImportError:
        _log(dataset_id, "cartopy unavailable, falling back to plain matplotlib")

    if use_cartopy:
        fig = plt.figure(figsize=(12, 4.8))
        ax = fig.add_subplot(1, 1, 1, projection=transform)
    else:
        fig, ax = plt.subplots(figsize=(12, 4.8))

    plot_kwargs = {
        "ax": ax,
        "x": "lon",
        "y": "lat",
        "cmap": cmap,
        "vmin": 0.0,
        "vmax": 1.0,
        "add_colorbar": False,
        "rasterized": True,
    }
    if transform is not None:
        plot_kwargs["transform"] = transform

    try:
        _log(dataset_id, f"rendering PNG figure -> {png_path}")
        mesh = surface.plot.pcolormesh(**plot_kwargs)
        title = display_name if actual_year is None else display_name
        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect("equal")
        if use_cartopy:
            ax.set_extent(_bbox_to_cartopy_extent(bbox), crs=transform)
            ax.coastlines(linewidth=0.5, color="black")
        else:
            ax.set_xlim(bbox[0], bbox[2])
            ax.set_ylim(bbox[1], bbox[3])

        colorbar = fig.colorbar(mesh, ax=ax, pad=0.02)
        colorbar.set_label("Wetland Fraction")
        fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)

    _log(dataset_id, "PNG figure saved")


def save_overview_plot(
    surfaces: list[tuple[str, xr.DataArray]],
    *,
    region_id: str,
    region_label: str,
    bbox: BBox,
    output_dir: Path,
) -> Path | None:
    if not surfaces:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"overview_{region_id}_025deg.png"
    cmap = LinearSegmentedColormap.from_list("wetland_wb", ["#ffffff", "#1f77b4"])

    use_cartopy = False
    transform = None
    try:
        import cartopy.crs as ccrs

        use_cartopy = True
        transform = ccrs.PlateCarree()
        print("[overview] cartopy detected, coastlines enabled", flush=True)
    except ImportError:
        print("[overview] cartopy unavailable, falling back to plain matplotlib", flush=True)

    nrows = len(surfaces)
    figsize = (12, max(3.2 * nrows, 4.8))
    subplot_kwargs = {"projection": transform} if use_cartopy else {}
    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=1,
        figsize=figsize,
        squeeze=False,
        subplot_kw=subplot_kwargs,
    )
    axes_list = list(axes[:, 0])

    mesh = None
    try:
        print(f"[overview] rendering overview PNG -> {png_path}", flush=True)
        for index, ((dataset_id, surface), ax) in enumerate(zip(surfaces, axes_list, strict=False)):
            plot_kwargs = {
                "ax": ax,
                "x": "lon",
                "y": "lat",
                "cmap": cmap,
                "vmin": 0.0,
                "vmax": 1.0,
                "add_colorbar": False,
                "rasterized": True,
            }
            if transform is not None:
                plot_kwargs["transform"] = transform

            mesh = surface.plot.pcolormesh(**plot_kwargs)
            ax.set_title(
                DATASET_DISPLAY_NAMES.get(dataset_id, dataset_id),
                fontsize=12,
                fontweight="bold",
            )
            ax.set_ylabel("Latitude")
            ax.set_aspect("equal")
            if index == nrows - 1:
                ax.set_xlabel("Longitude")
            else:
                ax.set_xlabel("")

            if use_cartopy:
                ax.set_extent(_bbox_to_cartopy_extent(bbox), crs=transform)
                ax.coastlines(linewidth=0.5, color="black")
            else:
                ax.set_xlim(bbox[0], bbox[2])
                ax.set_ylim(bbox[1], bbox[3])

        if mesh is None:
            return None

        fig.suptitle(region_label, fontsize=14, fontweight="bold")
        colorbar = fig.colorbar(mesh, ax=axes_list, pad=0.02, fraction=0.025)
        colorbar.set_label("Wetland Fraction")
        fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)

    print("[overview] overview PNG saved", flush=True)
    return png_path


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    dataset_ids = resolve_surface_dataset_ids(args.datasets)
    region_label, region_bbox = resolve_plot_region(
        args.region,
        regions_file=args.regions_file,
    )
    print(
        f"[run] output_dir={args.output_dir} output_root={args.output_root} "
        f"cache_dir={args.cache_dir} region={args.region} "
        f"region_label={region_label} region_bbox={region_bbox} "
        f"resolution_deg={args.resolution_deg} prefer_cache={args.prefer_cache} "
        f"write_cache={args.write_cache} progress={args.progress} "
        f"datasets={list(dataset_ids)}",
        flush=True,
    )

    successful_surfaces: list[tuple[str, xr.DataArray]] = []
    for dataset_id in dataset_ids:
        target_year = resolved_target_year(dataset_id, args.year)
        target_label = target_year if target_year is not None else "static"
        _log(dataset_id, f"target year = {target_label}")
        _log(dataset_id, f"selected region = {args.region} ({region_label}) bbox={region_bbox}")
        try:
            actual_year, surface = load_tropical_surface(
                dataset_id,
                region_id=args.region,
                bbox=region_bbox,
                target_year=target_year,
                resolution_deg=args.resolution_deg,
                cache_dir=args.cache_dir,
                prefer_cache=args.prefer_cache,
                write_cache=args.write_cache,
                output_root=args.output_root,
                show_progress=args.progress,
            )
            save_surface_plot(
                surface,
                dataset_id,
                region_id=args.region,
                region_label=region_label,
                bbox=region_bbox,
                output_dir=args.output_dir,
                actual_year=actual_year,
            )
            successful_surfaces.append((dataset_id, surface))
        except Exception as exc:  # noqa: BLE001
            print(f"[{dataset_id}] skipped: {type(exc).__name__}: {exc}", flush=True)

    save_overview_plot(
        successful_surfaces,
        region_id=args.region,
        region_label=region_label,
        bbox=region_bbox,
        output_dir=args.output_dir,
    )


def _flatten_cli_values(values: Iterable[str] | None) -> list[str]:
    flattened: list[str] = []
    if values is None:
        return flattened
    for entry in values:
        flattened.extend(part.strip() for part in str(entry).split(",") if part.strip())
    return flattened


def _surface_spatial_dims(data: xr.DataArray) -> tuple[str, str]:
    if "lat" in data.dims and "lon" in data.dims:
        return ("lat", "lon")
    if "y" in data.dims and "x" in data.dims:
        return ("y", "x")
    raise ValueError(f"Could not resolve surface spatial dims from {data.dims!r}")


def _bbox_intersects(left: BBox, right: BBox) -> bool:
    return not (
        left[2] <= right[0] or left[0] >= right[2] or left[3] <= right[1] or left[1] >= right[3]
    )


if __name__ == "__main__":
    main()
