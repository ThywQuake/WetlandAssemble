"""Phase 4 regional wetland-percentage analysis helpers."""

from __future__ import annotations

import copy
import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
import yaml
from rasterio.enums import Resampling

from WA.classification import wetland_class_ids, wetland_fraction_from_standardized_classes
from WA.comparison.phase36 import (
    DEFAULT_PHASE36_CACHE_DIR,
    DEFAULT_PHASE36_LAT_CHUNK_SIZE,
    DEFAULT_PHASE36_STANDARDIZED_DIR,
)
from WA.comparison.trends import phase4_gwd30_pixel_stats_tile_dir
from WA.config import get_dataset_config
from WA.loaders import get_loader
from WA.loaders._shared import reproject_to_grid
from WA.loaders.base import BBox
from WA.standardized_loader import StandardizedDataLoader
from WA.utils.progress import tqdm

logger = logging.getLogger(__name__)

DEFAULT_PHASE4_DATASET_IDS = (
    "gwd30",
    "giems_mc",
    "topmodel",
    "swamps",
    "wad2m",
    "berkeley_rwawc",
)
DEFAULT_PHASE4_PRIMARY_DATASET_IDS = (
    "gwd30",
    "giems_mc",
    "topmodel",
    "swamps",
    "wad2m",
)
DEFAULT_PHASE4_REGIONS_FILE = Path("config/priority_regions.yaml")
DEFAULT_PHASE4_OUTPUT_ROOT = Path("results/phase4")
DEFAULT_PHASE4_TIME_RANGE = ("1990-01-01", "2020-12-31")
DEFAULT_PHASE4_MASK_YEAR = 2016
DEFAULT_PHASE4_STANDARDIZED_DIR = DEFAULT_PHASE36_STANDARDIZED_DIR
DEFAULT_PHASE4_TOPMODEL_RAW_PATH = Path("~/Wetland_Assemble/data/TOPMODEL").expanduser()
EARTH_RADIUS_KM = 6371.0088
PHASE4_CACHE_VERSION = 1

PHASE4_MACRO_REGIONS: tuple[dict[str, object], ...] = (
    {
        "region_id": "pan_trop_subtrop",
        "label": "Pan Tropical + Subtropical",
        "label_zh": "全热带和亚热带",
        "bbox": (-180.0, -35.0, 180.0, 35.0),
        "kind": "macro_region",
        "priority": 0,
    },
    {
        "region_id": "north_tropics",
        "label": "Northern Tropics",
        "label_zh": "北热带",
        "bbox": (-180.0, 0.0, 180.0, 35.0),
        "kind": "macro_region",
        "priority": 1,
    },
    {
        "region_id": "south_tropics",
        "label": "Southern Tropics",
        "label_zh": "南热带",
        "bbox": (-180.0, -35.0, 180.0, 0.0),
        "kind": "macro_region",
        "priority": 2,
    },
    {
        "region_id": "southeast_asia",
        "label": "Southeast Asia",
        "label_zh": "东南亚",
        "bbox": (90.0, -11.0, 130.0, 24.0),
        "kind": "macro_region",
        "priority": 3,
    },
    {
        "region_id": "africa",
        "label": "Africa",
        "label_zh": "非洲",
        "bbox": (-20.0, -35.0, 55.0, 22.0),
        "kind": "macro_region",
        "priority": 4,
    },
    {
        "region_id": "south_america",
        "label": "South America",
        "label_zh": "南美",
        "bbox": (-90.0, -35.0, -30.0, 15.0),
        "kind": "macro_region",
        "priority": 5,
    },
)
PHASE4_GWD30_TROPICAL_CACHE_KEY = "full_tropics"
PHASE4_GWD30_TROPICAL_BBOX: BBox = (-180.0, -35.0, 180.0, 35.0)
PHASE4_GWD30_TILE_REDUCTION_NAME = "phase4_wetland_weighted_time_cube"
PHASE4_GWD30_TILE_REDUCTION_VERSION = 1

PHASE4_RAW_CONFIG_OVERRIDES: dict[str, dict[str, object]] = {
    "topmodel": {
        "loader_type": "topmodel",
        "path": str(DEFAULT_PHASE4_TOPMODEL_RAW_PATH),
        "time_resolution": "monthly",
        "resolution": "0.25° (~25km)",
    },
}


@dataclass(frozen=True)
class Phase4Region:
    """One Phase 4 regional analysis window."""

    region_id: str
    label: str
    label_zh: str | None
    bbox: BBox
    kind: str
    priority: int
    is_priority_region: bool

    @property
    def display_label(self) -> str:
        return self.label_zh or self.label


def load_phase4_regions(
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
) -> list[Phase4Region]:
    """Load the fixed Phase 4 region catalog."""

    regions: list[Phase4Region] = [
        Phase4Region(
            region_id=str(entry["region_id"]),
            label=str(entry["label"]),
            label_zh=str(entry["label_zh"]),
            bbox=tuple(float(value) for value in entry["bbox"]),  # type: ignore[arg-type]
            kind=str(entry["kind"]),
            priority=int(entry["priority"]),
            is_priority_region=False,
        )
        for entry in PHASE4_MACRO_REGIONS
    ]

    document = yaml.safe_load(Path(regions_file).read_text(encoding="utf-8")) or {}
    payload_regions = document.get("regions")
    if not isinstance(payload_regions, dict):
        raise ValueError("priority region document must contain a top-level 'regions' mapping")

    ordered: list[tuple[int, str, dict[str, object]]] = []
    for region_id, payload in payload_regions.items():
        if not isinstance(payload, dict):
            raise ValueError(f"Region {region_id!r} must be a mapping")
        ordered.append((int(payload.get("priority", 9999)), str(region_id), payload))

    for priority, region_id, payload in sorted(ordered):
        bbox = payload.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"Region {region_id!r} must define bbox as 4-item list")
        regions.append(
            Phase4Region(
                region_id=region_id,
                label=str(payload.get("label", region_id)),
                label_zh=(
                    str(payload["label_zh"]) if payload.get("label_zh") is not None else None
                ),
                bbox=tuple(float(value) for value in bbox),  # type: ignore[arg-type]
                kind=str(payload.get("kind", "priority_region")),
                priority=priority,
                is_priority_region=True,
            )
        )

    return regions


def resolve_phase4_region_ids(
    regions: Sequence[Phase4Region],
    requested: Iterable[str] | None = None,
) -> list[str]:
    """Resolve the requested Phase 4 region ids."""

    if not requested:
        return [region.region_id for region in regions]

    known = {region.region_id for region in regions}
    flattened: list[str] = []
    for entry in requested:
        flattened.extend(part.strip() for part in str(entry).split(",") if part.strip())

    unknown = sorted(set(flattened) - known)
    if unknown:
        raise KeyError(f"Unknown Phase 4 region ids: {', '.join(unknown)}")

    return flattened


def resolve_phase4_dataset_ids(
    requested: Iterable[str] | None = None,
) -> list[str]:
    """Resolve the requested Phase 4 dataset ids."""

    if not requested:
        return list(DEFAULT_PHASE4_DATASET_IDS)

    flattened: list[str] = []
    for entry in requested:
        flattened.extend(part.strip() for part in str(entry).split(",") if part.strip())

    unknown = sorted(set(flattened) - set(DEFAULT_PHASE4_DATASET_IDS))
    if unknown:
        raise KeyError(f"Unknown Phase 4 dataset ids: {', '.join(unknown)}")

    return flattened


def resolve_phase4_dataset_config(
    dataset_id: str,
    *,
    standardized_dir: str | Path | None = None,
    topmodel_raw_path: str | Path | None = None,
) -> dict[str, object]:
    """Return the dataset config used by the Phase 4 regional workflow."""

    config = copy.deepcopy(get_dataset_config(dataset_id))
    if standardized_dir is not None and str(config.get("loader_type")) == "standardized_netcdf":
        config["path"] = str(Path(standardized_dir).expanduser())
    if dataset_id not in PHASE4_RAW_CONFIG_OVERRIDES:
        return config

    config.update(copy.deepcopy(PHASE4_RAW_CONFIG_OVERRIDES[dataset_id]))
    if dataset_id == "topmodel" and topmodel_raw_path is not None:
        config["path"] = str(Path(topmodel_raw_path).expanduser())
    return config


def default_phase36_mask_path(
    *,
    cache_dir: str | Path = DEFAULT_PHASE36_CACHE_DIR,
    year: int = DEFAULT_PHASE4_MASK_YEAR,
    lat_chunk_size: int = DEFAULT_PHASE36_LAT_CHUNK_SIZE,
) -> Path:
    """Return the default Phase 3.6 shared-mask cache path."""

    return (
        Path(cache_dir)
        / f"global_500m_{year}"
        / f"lat_chunk_{lat_chunk_size}"
        / "02_joint_valid_mask.nc"
    )


def load_phase36_shared_mask(mask_path: str | Path) -> xr.DataArray:
    """Open the Phase 3.6 joint-valid mask as a float mask fraction."""

    path = Path(mask_path)
    if not path.is_file():
        raise FileNotFoundError(f"Phase 3.6 shared mask was not found: {path}")

    opened = xr.open_dataset(path)
    try:
        if "joint_valid_mask" not in opened:
            raise KeyError(f"'joint_valid_mask' was not found in {path}")
        mask = opened["joint_valid_mask"].load()
    finally:
        opened.close()

    mask = _ensure_spatial_rio(mask.astype(np.float32))
    mask = mask.clip(min=0.0, max=1.0)
    mask.name = "shared_mask_fraction"
    mask.attrs["source_phase"] = "phase3.6"
    mask.attrs["source_path"] = str(path)
    return mask


def load_phase36_shared_mask_subset(
    mask_path: str | Path,
    *,
    bbox: BBox,
    y_dim: str,
    x_dim: str,
    y_values: np.ndarray,
    x_values: np.ndarray,
) -> xr.DataArray:
    """Load one bbox-sized subset from the Phase 3.6 shared mask."""

    path = Path(mask_path)
    if not path.is_file():
        raise FileNotFoundError(f"Phase 3.6 shared mask was not found: {path}")

    with xr.open_dataset(path) as opened:
        if "joint_valid_mask" not in opened:
            raise KeyError(f"'joint_valid_mask' was not found in {path}")
        subset = subset_phase4_mask_to_bbox(
            _ensure_spatial_rio(opened["joint_valid_mask"].astype(np.float32)),
            bbox,
        )
        mask_chunk = subset.reindex(
            {
                y_dim: y_values,
                x_dim: x_values,
            },
            fill_value=0.0,
        ).load()

    mask_chunk = _ensure_spatial_rio(mask_chunk.astype(np.float32))
    mask_chunk = mask_chunk.clip(min=0.0, max=1.0)
    mask_chunk.name = "shared_mask_fraction"
    mask_chunk.attrs["source_phase"] = "phase3.6"
    mask_chunk.attrs["source_path"] = str(path)
    return mask_chunk


def subset_phase4_mask_to_bbox(
    mask: xr.DataArray,
    bbox: BBox,
) -> xr.DataArray:
    """Subset the shared mask to one rectangular region."""

    min_lon, min_lat, max_lon, max_lat = bbox
    y_dim, x_dim = _spatial_dims(mask)
    lon_subset = mask.sel({x_dim: slice(min_lon, max_lon)})
    lat_values = np.asarray(lon_subset.coords[y_dim].values)
    lat_slice = (
        slice(min_lat, max_lat)
        if lat_values[0] <= lat_values[-1]
        else slice(max_lat, min_lat)
    )
    subset = lon_subset.sel({y_dim: lat_slice})
    if subset.sizes.get(y_dim, 0) == 0 or subset.sizes.get(x_dim, 0) == 0:
        raise ValueError(f"Region bbox {bbox!r} produces an empty Phase 4 mask subset")
    return _ensure_spatial_rio(subset)


def compute_phase4_region_dataset_table(
    dataset_id: str,
    *,
    region: Phase4Region,
    base_mask: xr.DataArray,
    gwd30_tropical_tile_cache: pd.DataFrame | None = None,
    output_root: str | Path = DEFAULT_PHASE4_OUTPUT_ROOT,
    standardized_dir: str | Path = DEFAULT_PHASE4_STANDARDIZED_DIR,
    time_range: tuple[str, str] = DEFAULT_PHASE4_TIME_RANGE,
    skip_existing: bool = True,
    topmodel_raw_path: str | Path | None = None,
    spatial_lat_chunk_size: int = 64,
    time_chunk_size: int = 12,
    show_progress: bool = True,
) -> pd.DataFrame:
    """Compute or load one dataset × region Phase 4 cache table."""

    cache_path = phase4_dataset_region_cache_path(
        output_root=output_root,
        dataset_id=dataset_id,
        region_id=region.region_id,
    )
    if skip_existing and cache_path.is_file():
        logger.info("Phase4 cache hit: regional_series <- %s", cache_path)
        return _read_phase4_table(cache_path)

    logger.info(
        "Phase4 cache miss: regional_series -> %s (dataset=%s region=%s)",
        cache_path,
        dataset_id,
        region.region_id,
    )
    if dataset_id == "gwd30":
        monthly = build_phase4_gwd30_monthly_series_from_pixel_stats_tiles(
            region=region,
            region_mask=base_mask,
            output_root=output_root,
            time_range=time_range,
            skip_existing=skip_existing,
            show_progress=show_progress,
        )
    else:
        dataset = _open_phase4_dataset(
            dataset_id,
            bbox=region.bbox,
            time_range=time_range,
            standardized_dir=standardized_dir,
            topmodel_raw_path=topmodel_raw_path,
        )
        try:
            data = _extract_phase4_analysis_dataarray(dataset_id, dataset)
            monthly_data = _to_monthly_dataarray(data)
            mask_fraction = build_or_load_phase4_mask_fraction(
                base_mask=base_mask,
                template=monthly_data,
                cache_path=phase4_mask_cache_path(
                    output_root=output_root,
                    dataset_id=dataset_id,
                    region_id=region.region_id,
                ),
                skip_existing=skip_existing,
            )
            monthly = _reduce_monthly_dataarray_to_regional_series(
                monthly_data=monthly_data,
                mask_fraction=mask_fraction,
                dataset_id=dataset_id,
                region_id=region.region_id,
                spatial_lat_chunk_size=spatial_lat_chunk_size,
                time_chunk_size=time_chunk_size,
                show_progress=show_progress,
            )
        finally:
            closer = getattr(dataset, "close", None)
            if callable(closer):
                closer()

    annual = build_phase4_annual_series(monthly)
    climatology = build_phase4_climatology(monthly)
    table = assemble_phase4_series_table(
        dataset_id=dataset_id,
        region_id=region.region_id,
        monthly=monthly,
        annual=annual,
        climatology=climatology,
    )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(cache_path, index=False)
    logger.info(
        "Phase4 cache write: dataset=%s region=%s rows=%s path=%s",
        dataset_id,
        region.region_id,
        len(table),
        cache_path,
    )
    return table


def build_phase4_region_table(
    *,
    region: Phase4Region,
    dataset_tables: Sequence[pd.DataFrame],
    output_root: str | Path = DEFAULT_PHASE4_OUTPUT_ROOT,
) -> Path:
    """Write the combined per-region Phase 4 table."""

    table_path = phase4_region_table_path(output_root=output_root, region_id=region.region_id)
    combined = pd.concat(dataset_tables, ignore_index=True) if dataset_tables else pd.DataFrame()
    table_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(table_path, index=False)
    logger.info(
        "Phase4 table write: region=%s rows=%s path=%s",
        region.region_id,
        len(combined),
        table_path,
    )
    return table_path


def phase4_dataset_region_cache_path(
    *,
    output_root: str | Path,
    dataset_id: str,
    region_id: str,
) -> Path:
    """Return the cache path for one dataset × region table."""

    return Path(output_root) / "cache" / dataset_id / region_id / "regional_series.csv"


def phase4_dataset_region_year_cache_path(
    *,
    output_root: str | Path,
    dataset_id: str,
    region_id: str,
    year: int,
) -> Path:
    """Return the monthly year-cache path for one dataset × region × year."""

    return (
        Path(output_root)
        / "cache"
        / dataset_id
        / region_id
        / "years"
        / f"regional_series_{year}.csv"
    )


def phase4_gwd30_tropical_tile_cache_path(
    *,
    output_root: str | Path,
    year: int,
) -> Path:
    """Return the Phase 4 GWD30 full-tropics tile-month cache path for one year."""

    return (
        Path(output_root)
        / "cache"
        / "gwd30"
        / PHASE4_GWD30_TROPICAL_CACHE_KEY
        / f"tile_monthly_{year}.csv"
    )


def phase4_mask_cache_path(
    *,
    output_root: str | Path,
    dataset_id: str,
    region_id: str,
) -> Path:
    """Return the shared-mask cache path for one dataset × region grid."""

    return (
        Path(output_root)
        / "cache"
        / "masks"
        / dataset_id
        / f"{region_id}_shared_mask_fraction.nc"
    )


def phase4_berkeley_valid_mask_cache_path(
    *,
    output_root: str | Path,
    region_id: str,
    time_range: tuple[str, str],
) -> Path:
    start_year = pd.Timestamp(time_range[0]).year
    end_year = pd.Timestamp(time_range[1]).year
    return (
        Path(output_root)
        / "cache"
        / "masks"
        / "berkeley_valid"
        / f"{region_id}_{start_year}_{end_year}.nc"
    )


def phase4_region_table_path(
    *,
    output_root: str | Path,
    region_id: str,
) -> Path:
    """Return the combined table path for one Phase 4 region."""

    return Path(output_root) / "tables" / f"{region_id}.csv"


def read_phase4_table(path: str | Path) -> pd.DataFrame:
    """Read one cached Phase 4 CSV table."""

    return _read_phase4_table(Path(path))


def load_phase4_gwd30_staged_tiles(
    standardized_dir: str | Path,
    *,
    year: int,
) -> list[tuple[Path, BBox]]:
    """Restore one year's staged GWD30 tiles from the standardized staging root."""

    manifest_paths = list_phase4_gwd30_stage_shard_manifests(standardized_dir, year=year)
    staged_tiles = load_phase4_gwd30_staged_tiles_from_manifest_paths(manifest_paths)
    if staged_tiles:
        logger.info(
            "Phase4 GWD30 manifest hit: restored %d staged tile partial(s) from %s",
            len(staged_tiles),
            manifest_paths[0].parent if manifest_paths else standardized_dir,
        )
        return staged_tiles
    staging_root = Path(standardized_dir).expanduser() / "_staging" / f"gwd30_{year}"
    raise FileNotFoundError(
        "No staged GWD30 tile manifests were found under "
        f"{staging_root}. Expected stage_shard_*.json referencing tile_partials/tile_*.nc."
    )


def phase4_gwd30_pixel_stats_manifest_path(
    *,
    output_root: str | Path,
    year: int,
    aggregation: str = "monthly",
) -> Path:
    """Return the Stage-1 GWD30 pixel-statistics manifest path for one year."""

    output_dir = phase4_gwd30_pixel_stats_tile_dir(
        output_root=output_root,
        year=year,
        aggregation=aggregation,
    )
    return output_dir.parent / "tile_manifest.json"


def load_phase4_gwd30_pixel_stats_tiles(
    output_root: str | Path,
    *,
    year: int,
    aggregation: str = "monthly",
) -> list[tuple[Path, BBox]]:
    """Restore Stage-1 GWD30 pixel-statistics tile metadata from one manifest."""

    manifest_path = phase4_gwd30_pixel_stats_manifest_path(
        output_root=output_root,
        year=year,
        aggregation=aggregation,
    )
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Phase 4 GWD30 pixel-statistics manifest was not found: {manifest_path}"
        )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = payload.get("tiles")
    if not isinstance(records, list):
        raise ValueError(f"Expected 'tiles' list in pixel-statistics manifest: {manifest_path}")

    restored: list[tuple[Path, BBox]] = []
    seen_paths: set[Path] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(
                f"Pixel-statistics manifest entries must be mappings: {manifest_path}"
            )
        path_value = record.get("path")
        bbox_value = record.get("bbox")
        if not isinstance(path_value, str):
            raise ValueError(f"Missing string 'path' in pixel-statistics manifest: {manifest_path}")
        if not isinstance(bbox_value, list) or len(bbox_value) != 4:
            raise ValueError(
                f"Missing 4-item 'bbox' in pixel-statistics manifest: {manifest_path}"
            )
        tile_path = Path(path_value)
        tile_bbox = tuple(float(value) for value in bbox_value)
        if tile_path in seen_paths:
            continue
        seen_paths.add(tile_path)
        restored.append((tile_path, tile_bbox))

    return restored


def list_phase4_gwd30_stage_shard_manifests(
    standardized_dir: str | Path,
    *,
    year: int,
) -> list[Path]:
    """List one year's GWD30 stage shard manifests from the standardized staging root."""

    staging_root = Path(standardized_dir).expanduser() / "_staging" / f"gwd30_{year}"
    manifest_paths = sorted(staging_root.glob("stage_shard_*.json"))
    if manifest_paths:
        logger.info(
            "Phase4 GWD30 manifest discovery: year=%s staging_root=%s manifests=%s",
            year,
            staging_root,
            len(manifest_paths),
        )
        return manifest_paths
    raise FileNotFoundError(
        "No staged GWD30 tile manifests were found under "
        f"{staging_root}. Expected stage_shard_*.json referencing tile_partials/tile_*.nc."
    )


def load_phase4_gwd30_staged_tiles_from_manifest_paths(
    manifest_paths: Sequence[str | Path],
) -> list[tuple[Path, BBox]]:
    """Restore staged GWD30 tile metadata from an explicit manifest path list."""

    if not manifest_paths:
        return []

    staged_by_path: dict[Path, BBox] = {}
    missing_paths: list[Path] = []
    normalized_paths = [Path(path) for path in manifest_paths]
    for manifest_path in normalized_paths:
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        for item in payload.get("staged_tiles", []):
            stage_path = Path(str(item["path"]))
            stage_bbox = _coerce_json_bbox(item["bbox"])
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
            "Phase4 GWD30 manifest restore skipped %d staged tile path(s) referenced by "
            "manifest list because the files do not exist",
            len(missing_paths),
        )

    logger.info(
        "Phase4 GWD30 manifest-list restore: manifests=%s restored_tiles=%s",
        len(normalized_paths),
        len(staged_by_path),
    )
    return sorted(staged_by_path.items(), key=lambda item: str(item[0]))


def build_or_load_phase4_gwd30_tropical_tile_cache(
    *,
    base_mask: xr.DataArray,
    output_root: str | Path = DEFAULT_PHASE4_OUTPUT_ROOT,
    standardized_dir: str | Path = DEFAULT_PHASE4_STANDARDIZED_DIR,
    time_range: tuple[str, str] = DEFAULT_PHASE4_TIME_RANGE,
    skip_existing: bool = True,
    show_progress: bool = True,
) -> pd.DataFrame:
    """Build or load the shared GWD30 full-tropics tile-month cache."""

    tropical_mask = subset_phase4_mask_to_bbox(base_mask, PHASE4_GWD30_TROPICAL_BBOX)
    dataset_config = get_dataset_config("gwd30")
    years = _gwd30_years_for_time_range(dataset_config, time_range)
    year_frames: list[pd.DataFrame] = []

    for year in years:
        cache_path = phase4_gwd30_tropical_tile_cache_path(output_root=output_root, year=year)
        if skip_existing and cache_path.is_file():
            logger.info("Phase4 cache hit: gwd30_tropical_tile_monthly <- %s", cache_path)
            year_frames.append(_read_phase4_table(cache_path))
            continue

        logger.info(
            "Phase4 cache miss: gwd30_tropical_tile_monthly -> %s (year=%s)",
            cache_path,
            year,
        )
        year_frame = _build_phase4_gwd30_tropical_tile_cache_year(
            year=year,
            tropical_mask=tropical_mask,
            standardized_dir=standardized_dir,
            time_range=time_range,
            show_progress=show_progress,
        )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        year_frame.to_csv(cache_path, index=False)
        logger.info(
            "Phase4 cache write: gwd30_tropical_tile_monthly year=%s rows=%s path=%s",
            year,
            len(year_frame),
            cache_path,
        )
        year_frames.append(year_frame)

    if not year_frames:
        return _empty_phase4_gwd30_tropical_tile_cache()

    combined = pd.concat(year_frames, ignore_index=True).sort_values(
        ["time", "tile_id"]
    ).reset_index(drop=True)
    combined["time"] = pd.to_datetime(combined["time"])
    return combined


def build_phase4_gwd30_monthly_series_from_tropical_tile_cache(
    *,
    tropical_tile_cache: pd.DataFrame,
    region: Phase4Region,
) -> pd.DataFrame:
    """Aggregate one region's monthly series from the shared GWD30 tropical tile cache."""

    if tropical_tile_cache.empty:
        return _empty_phase4_monthly_series()

    candidate = tropical_tile_cache.loc[
        (tropical_tile_cache["tile_east"] > region.bbox[0])
        & (tropical_tile_cache["tile_west"] < region.bbox[2])
        & (tropical_tile_cache["tile_north"] > region.bbox[1])
        & (tropical_tile_cache["tile_south"] < region.bbox[3])
    ].copy()
    if candidate.empty:
        logger.info(
            "Phase4 GWD30 tropical cache region extraction: region=%s candidate_tiles=0",
            region.region_id,
        )
        return _empty_phase4_monthly_series()

    monthly = (
        candidate.groupby("time", as_index=False)
        .agg(
            wetland_area_km2=("wetland_area_km2", "sum"),
            valid_area_km2=("valid_area_km2", "sum"),
            observation_count=("tile_id", "nunique"),
        )
        .sort_values("time")
        .reset_index(drop=True)
    )
    percentage = np.full(len(monthly), np.nan, dtype=np.float64)
    np.divide(
        monthly["wetland_area_km2"].to_numpy(dtype=np.float64),
        monthly["valid_area_km2"].to_numpy(dtype=np.float64),
        out=percentage,
        where=monthly["valid_area_km2"].to_numpy(dtype=np.float64) > 0,
    )
    monthly["wetland_percentage"] = percentage * 100.0
    monthly["year"] = monthly["time"].dt.year.astype(np.int64)
    monthly["month"] = monthly["time"].dt.month.astype(np.int64)
    monthly["observation_count"] = monthly["observation_count"].astype(np.int64)
    logger.info(
        "Phase4 GWD30 tropical cache region extraction: region=%s candidate_tiles=%s rows=%s",
        region.region_id,
        candidate["tile_id"].nunique(),
        len(monthly),
    )
    return monthly[
        [
            "time",
            "year",
            "month",
            "wetland_area_km2",
            "valid_area_km2",
            "wetland_percentage",
            "observation_count",
        ]
    ]


def build_phase4_gwd30_monthly_series_from_staged_tiles(
    *,
    region: Phase4Region,
    region_mask: xr.DataArray,
    standardized_dir: str | Path,
    time_range: tuple[str, str],
    show_progress: bool,
) -> pd.DataFrame:
    """Build one region's GWD30 monthly series directly from staged tiles."""

    dataset_config = get_dataset_config("gwd30")
    years = _gwd30_years_for_time_range(dataset_config, time_range)
    tile_frames: list[pd.DataFrame] = []

    for year in years:
        staged_tiles = load_phase4_gwd30_staged_tiles(standardized_dir, year=year)
        candidate_tiles = [
            (stage_path, stage_bbox)
            for stage_path, stage_bbox in staged_tiles
            if _bbox_intersects(stage_bbox, region.bbox)
        ]
        logger.info(
            "Phase4 GWD30 region staged selection: region=%s year=%s restored=%s candidates=%s",
            region.region_id,
            year,
            len(staged_tiles),
            len(candidate_tiles),
        )
        tile_progress = tqdm(
            candidate_tiles,
            total=len(candidate_tiles),
            desc=f"Phase4 gwd30 {region.region_id} {year}",
            disable=not show_progress,
        )
        for stage_path, stage_bbox in tile_progress:
            monthly_tile = build_phase4_gwd30_tropical_monthly_tile_from_stage_file(
                stage_path=stage_path,
                stage_bbox=stage_bbox,
                time_range=time_range,
                tropical_mask=region_mask,
            )
            if monthly_tile.empty:
                continue
            tile_frames.append(monthly_tile)

    if not tile_frames:
        return _empty_phase4_monthly_series()

    combined = pd.concat(tile_frames, ignore_index=True).sort_values(
        ["time", "tile_id"]
    ).reset_index(drop=True)
    return build_phase4_gwd30_monthly_series_from_tropical_tile_cache(
        tropical_tile_cache=combined,
        region=region,
    )


def build_phase4_gwd30_monthly_series_from_pixel_stats_tiles(
    *,
    region: Phase4Region,
    region_mask: xr.DataArray,
    output_root: str | Path,
    time_range: tuple[str, str],
    skip_existing: bool,
    show_progress: bool,
) -> pd.DataFrame:
    """Build one region's GWD30 monthly series from Stage-1 native pixel-statistics tiles."""

    dataset_config = get_dataset_config("gwd30")
    years = _gwd30_years_for_time_range(dataset_config, time_range)
    year_frames: list[pd.DataFrame] = []

    for year in years:
        year_cache_path = phase4_dataset_region_year_cache_path(
            output_root=output_root,
            dataset_id="gwd30",
            region_id=region.region_id,
            year=year,
        )
        year_time_range = (f"{year}-01-01", f"{year}-12-31")
        if skip_existing and year_cache_path.is_file():
            logger.info("Phase4 cache hit: gwd30 regional year <- %s", year_cache_path)
            year_frames.append(_read_phase4_table(year_cache_path))
            continue

        stats_tiles = load_phase4_gwd30_pixel_stats_tiles(
            output_root,
            year=year,
            aggregation="monthly",
        )
        candidate_tiles = [
            (tile_path, tile_bbox)
            for tile_path, tile_bbox in stats_tiles
            if _bbox_intersects(tile_bbox, region.bbox)
        ]
        logger.info(
            "Phase4 GWD30 pixel-stats selection: region=%s year=%s restored=%s candidates=%s",
            region.region_id,
            year,
            len(stats_tiles),
            len(candidate_tiles),
        )
        year_frame = _accumulate_phase4_gwd30_pixel_stats_tiles(
            candidate_tiles=candidate_tiles,
            region=region,
            region_mask=region_mask,
            time_range=year_time_range,
            year=year,
            show_progress=show_progress,
        )
        year_cache_path.parent.mkdir(parents=True, exist_ok=True)
        year_frame.to_csv(year_cache_path, index=False)
        logger.info(
            "Phase4 cache write: dataset=gwd30 region=%s year=%s rows=%s path=%s",
            region.region_id,
            year,
            len(year_frame),
            year_cache_path,
        )
        year_frames.append(year_frame)

    if not year_frames:
        return _empty_phase4_monthly_series()

    return pd.concat(year_frames, ignore_index=True).sort_values("time").reset_index(drop=True)


def _accumulate_phase4_gwd30_pixel_stats_tiles(
    *,
    candidate_tiles: Sequence[tuple[Path, BBox]],
    region: Phase4Region,
    region_mask: xr.DataArray,
    time_range: tuple[str, str],
    year: int,
    show_progress: bool,
) -> pd.DataFrame:
    """Reduce one year's Stage-1 pixel-statistics tiles into one monthly regional series."""

    if not candidate_tiles:
        return _empty_phase4_monthly_series()

    accumulated: dict[pd.Timestamp, dict[str, float | int]] = {}

    tile_progress = tqdm(
        candidate_tiles,
        total=len(candidate_tiles),
        desc=f"Phase4 gwd30 stats {region.region_id} {year}",
        disable=not show_progress,
    )
    for tile_path, tile_bbox in tile_progress:
        monthly_tile = build_phase4_gwd30_monthly_tile_from_pixel_stats_file(
            tile_path=tile_path,
            tile_bbox=tile_bbox,
            time_range=time_range,
            region_mask=region_mask,
        )
        if monthly_tile.empty:
            continue

        for row in monthly_tile.itertuples(index=False):
            timestamp = pd.Timestamp(row.time)
            bucket = accumulated.setdefault(
                timestamp,
                {
                    "wetland_area_km2": 0.0,
                    "valid_area_km2": 0.0,
                    "observation_count": 0,
                },
            )
            bucket["wetland_area_km2"] += float(row.wetland_area_km2)
            bucket["valid_area_km2"] += float(row.valid_area_km2)
            bucket["observation_count"] += 1

    if not accumulated:
        return _empty_phase4_monthly_series()

    sorted_times = sorted(accumulated.keys())
    monthly = pd.DataFrame(
        {
            "time": sorted_times,
            "wetland_area_km2": [
                float(accumulated[timestamp]["wetland_area_km2"])
                for timestamp in sorted_times
            ],
            "valid_area_km2": [
                float(accumulated[timestamp]["valid_area_km2"])
                for timestamp in sorted_times
            ],
            "observation_count": [
                int(accumulated[timestamp]["observation_count"])
                for timestamp in sorted_times
            ],
        }
    )
    percentage = np.full(len(monthly), np.nan, dtype=np.float64)
    np.divide(
        monthly["wetland_area_km2"].to_numpy(dtype=np.float64),
        monthly["valid_area_km2"].to_numpy(dtype=np.float64),
        out=percentage,
        where=monthly["valid_area_km2"].to_numpy(dtype=np.float64) > 0,
    )
    monthly["wetland_percentage"] = percentage * 100.0
    monthly["year"] = monthly["time"].dt.year.astype(np.int64)
    monthly["month"] = monthly["time"].dt.month.astype(np.int64)
    return monthly[
        [
            "time",
            "year",
            "month",
            "wetland_area_km2",
            "valid_area_km2",
            "wetland_percentage",
            "observation_count",
        ]
    ]


def build_phase4_gwd30_tropical_tile_index_for_staged_tiles(
    *,
    year: int,
    staged_tiles: Sequence[tuple[Path, BBox]],
) -> pd.DataFrame:
    """Build one lightweight tile index table for later masked reduction."""

    candidate_tiles = [
        (stage_path, manifest_bbox)
        for stage_path, manifest_bbox in staged_tiles
        if _bbox_intersects(manifest_bbox, PHASE4_GWD30_TROPICAL_BBOX)
    ]
    logger.info(
        "Phase4 GWD30 tropical tile index selection: year=%s restored=%s candidates=%s",
        year,
        len(staged_tiles),
        len(candidate_tiles),
    )
    if not candidate_tiles:
        return _empty_phase4_gwd30_tropical_tile_index()

    return pd.DataFrame(
        {
            "tile_id": [stage_path.stem for stage_path, _bbox in candidate_tiles],
            "stage_path": [str(stage_path) for stage_path, _bbox in candidate_tiles],
            "tile_west": [float(bbox[0]) for _stage_path, bbox in candidate_tiles],
            "tile_south": [float(bbox[1]) for _stage_path, bbox in candidate_tiles],
            "tile_east": [float(bbox[2]) for _stage_path, bbox in candidate_tiles],
            "tile_north": [float(bbox[3]) for _stage_path, bbox in candidate_tiles],
        }
    ).sort_values(["tile_id", "stage_path"]).reset_index(drop=True)


def phase4_reduce_staged_time_fraction_tile(source: xr.Dataset) -> xr.Dataset:
    """Reduce one staged GWD30 tile by dropping the source-class axis only."""

    if "weighted" not in source.data_vars or "coverage" not in source.data_vars:
        raise ValueError("Expected staged GWD30 tile dataset with weighted and coverage variables")

    y_dim, x_dim = _spatial_dims(source["coverage"])
    class_ids = np.asarray(source["weighted"].coords["class_id"].values, dtype=np.int16)
    wetland_ids = set(wetland_class_ids("gwd30", include_water=False))
    selected_indices = [
        index
        for index, class_id in enumerate(class_ids)
        if int(class_id) in wetland_ids
    ]

    if selected_indices:
        wetland_weighted = (
            source["weighted"]
            .isel(class_id=selected_indices)
            .sum(dim="class_id")
            .transpose("time", y_dim, x_dim)
            .astype(np.float32)
        )
    else:
        wetland_weighted = xr.zeros_like(
            source["coverage"].transpose("time", y_dim, x_dim),
        ).astype(np.float32)

    coverage = source["coverage"].transpose("time", y_dim, x_dim).astype(np.float32)
    reduced = xr.Dataset(
        data_vars={
            "wetland_weighted": wetland_weighted,
            "coverage": coverage,
        },
        attrs={
            "dataset_id": "gwd30",
            "year": int(source.attrs.get("year", 0)),
            "source": "phase4_wetland_weighted_time_cube",
        },
    )
    return reduced


def build_phase4_gwd30_reduced_tile_index_for_staged_tiles(
    *,
    year: int,
    staged_tiles: Sequence[tuple[Path, BBox]],
    output_dir: Path,
    skip_existing: bool,
    worker_count: int | None,
    show_progress: bool,
) -> pd.DataFrame:
    """Transform staged GWD30 tiles into reduced wetland-weighted time cubes."""

    candidate_tiles = [
        (stage_path, manifest_bbox)
        for stage_path, manifest_bbox in staged_tiles
        if _bbox_intersects(manifest_bbox, PHASE4_GWD30_TROPICAL_BBOX)
    ]
    logger.info(
        "Phase4 GWD30 reduced-tile selection: year=%s restored=%s candidates=%s",
        year,
        len(staged_tiles),
        len(candidate_tiles),
    )
    if not candidate_tiles:
        return _empty_phase4_gwd30_reduced_tile_index()

    dataset_config = get_dataset_config("gwd30")
    loader = get_loader("gwd30", dataset_config)
    transform_tiles = getattr(loader, "transform_staged_time_fraction_tiles", None)
    if not callable(transform_tiles):
        raise TypeError("GWD30 loader does not implement transform_staged_time_fraction_tiles()")

    reduced_tiles = transform_tiles(
        staged_tiles=list(candidate_tiles),
        output_dir=output_dir,
        transform_name=PHASE4_GWD30_TILE_REDUCTION_NAME,
        transform_version=PHASE4_GWD30_TILE_REDUCTION_VERSION,
        transform_tile=phase4_reduce_staged_time_fraction_tile,
        year=year,
        worker_count=worker_count,
        show_progress=show_progress,
        skip_existing=skip_existing,
    )
    if not reduced_tiles:
        return _empty_phase4_gwd30_reduced_tile_index()

    return pd.DataFrame(
        {
            "tile_id": [tile_path.stem for tile_path, _bbox in reduced_tiles],
            "reduced_path": [str(tile_path) for tile_path, _bbox in reduced_tiles],
            "tile_west": [float(bbox[0]) for _tile_path, bbox in reduced_tiles],
            "tile_south": [float(bbox[1]) for _tile_path, bbox in reduced_tiles],
            "tile_east": [float(bbox[2]) for _tile_path, bbox in reduced_tiles],
            "tile_north": [float(bbox[3]) for _tile_path, bbox in reduced_tiles],
        }
    ).sort_values(["tile_id", "reduced_path"]).reset_index(drop=True)


def build_phase4_gwd30_tropical_monthly_tile_from_stage_file(
    *,
    stage_path: str | Path,
    stage_bbox: BBox,
    time_range: tuple[str, str],
    tropical_mask: xr.DataArray | None = None,
    phase36_mask_path: str | Path | None = None,
) -> pd.DataFrame:
    """Compute one masked monthly tile series from one staged GWD30 tile partial."""

    if tropical_mask is None and phase36_mask_path is None:
        raise ValueError("Either tropical_mask or phase36_mask_path must be provided")

    wetland_ids = set(wetland_class_ids("gwd30", include_water=False))
    stage_path = Path(stage_path)
    with xr.open_dataset(stage_path, engine="netcdf4") as source:
        y_dim, x_dim = _spatial_dims(source["coverage"])
        coverage = source["coverage"].transpose("time", y_dim, x_dim).load()
        class_ids = np.asarray(source["weighted"].coords["class_id"].values, dtype=np.int16)
        selected_indices = [
            index
            for index, class_id in enumerate(class_ids)
            if int(class_id) in wetland_ids
        ]
        if not selected_indices:
            return _empty_phase4_gwd30_tropical_tile_cache()

        wetland_weighted = (
            source["weighted"]
            .isel(class_id=selected_indices)
            .sum(dim="class_id")
            .transpose("time", y_dim, x_dim)
            .load()
        )

    if tropical_mask is not None:
        mask_chunk = tropical_mask.reindex(
            {
                y_dim: coverage.coords[y_dim].values,
                x_dim: coverage.coords[x_dim].values,
            },
            fill_value=0.0,
        ).load()
    else:
        mask_chunk = load_phase36_shared_mask_subset(
            phase36_mask_path,
            bbox=stage_bbox,
            y_dim=y_dim,
            x_dim=x_dim,
            y_values=np.asarray(coverage.coords[y_dim].values),
            x_values=np.asarray(coverage.coords[x_dim].values),
        )

    mask_values = np.asarray(mask_chunk.values, dtype=np.float64)
    if not np.any(mask_values > 0.0):
        return _empty_phase4_gwd30_tropical_tile_cache()

    lat_terms, lon_terms = _area_terms_from_coords(
        coverage.isel(time=0, drop=True),
        lat_values=np.asarray(coverage.coords[y_dim].values, dtype=np.float64),
        lon_values=np.asarray(coverage.coords[x_dim].values, dtype=np.float64),
    )
    chunk_area = (
        (EARTH_RADIUS_KM**2)
        * lat_terms[:, None]
        * lon_terms[None, :]
    )
    effective_weights = chunk_area * mask_values

    coverage_values = np.asarray(coverage.values, dtype=np.float32)
    wetland_weighted_values = np.asarray(wetland_weighted.values, dtype=np.float32)
    raw_tile = pd.DataFrame(
        {
            "time": pd.to_datetime(coverage.coords["time"].values),
            "wetland_area_km2": np.sum(
                wetland_weighted_values * effective_weights[None, :, :],
                axis=(1, 2),
                dtype=np.float64,
            ),
            "valid_area_km2": np.sum(
                coverage_values * effective_weights[None, :, :],
                axis=(1, 2),
                dtype=np.float64,
            ),
        }
    )
    raw_tile = raw_tile.loc[
        raw_tile["time"].between(pd.Timestamp(time_range[0]), pd.Timestamp(time_range[1]))
    ].copy()
    if raw_tile.empty:
        return _empty_phase4_gwd30_tropical_tile_cache()

    percentage = np.full(len(raw_tile), np.nan, dtype=np.float64)
    np.divide(
        raw_tile["wetland_area_km2"].to_numpy(dtype=np.float64),
        raw_tile["valid_area_km2"].to_numpy(dtype=np.float64),
        out=percentage,
        where=raw_tile["valid_area_km2"].to_numpy(dtype=np.float64) > 0,
    )
    raw_tile["wetland_percentage"] = percentage * 100.0
    monthly_tile = _collapse_raw_timesteps_to_monthly(raw_tile)
    monthly_tile["tile_id"] = stage_path.stem
    monthly_tile["stage_path"] = str(stage_path)
    monthly_tile["tile_west"] = float(stage_bbox[0])
    monthly_tile["tile_south"] = float(stage_bbox[1])
    monthly_tile["tile_east"] = float(stage_bbox[2])
    monthly_tile["tile_north"] = float(stage_bbox[3])
    return monthly_tile[
        [
            "time",
            "year",
            "month",
            "tile_id",
            "stage_path",
            "tile_west",
            "tile_south",
            "tile_east",
            "tile_north",
            "wetland_area_km2",
            "valid_area_km2",
            "wetland_percentage",
            "observation_count",
        ]
    ]


def build_phase4_gwd30_monthly_tile_from_pixel_stats_file(
    *,
    tile_path: str | Path,
    tile_bbox: BBox,
    time_range: tuple[str, str],
    region_mask: xr.DataArray,
) -> pd.DataFrame:
    """Compute one masked monthly tile series from one Stage-1 pixel-statistics tile file."""

    tile_path = Path(tile_path)
    with xr.open_dataset(tile_path, engine="netcdf4") as source:
        if "wetland_fraction" not in source or "cell_area_km2" not in source:
            raise KeyError(
                f"Expected wetland_fraction and cell_area_km2 in pixel-statistics tile: {tile_path}"
            )
        wetland_fraction = source["wetland_fraction"].load()
        cell_area = source["cell_area_km2"].load()

    y_dim, x_dim = _spatial_dims(wetland_fraction)
    mask_chunk = _mask_fraction_for_template(
        base_mask=region_mask,
        template=wetland_fraction.isel(time=0, drop=True),
    )
    mask_values = np.asarray(mask_chunk.values, dtype=np.float64)
    if not np.any(mask_values > 0.0):
        return _empty_phase4_gwd30_tropical_tile_cache()

    wetland_values = np.asarray(
        wetland_fraction.transpose("time", y_dim, x_dim).values,
        dtype=np.float32,
    )
    cell_area_values = np.asarray(cell_area.transpose(y_dim, x_dim).values, dtype=np.float64)
    effective_weights = cell_area_values * mask_values
    valid = np.isfinite(wetland_values)
    safe_values = np.where(valid, wetland_values, 0.0)

    raw_tile = pd.DataFrame(
        {
            "time": pd.to_datetime(wetland_fraction.coords["time"].values),
            "wetland_area_km2": np.sum(
                safe_values * effective_weights[None, :, :],
                axis=(1, 2),
                dtype=np.float64,
            ),
            "valid_area_km2": np.sum(
                valid * effective_weights[None, :, :],
                axis=(1, 2),
                dtype=np.float64,
            ),
        }
    )
    raw_tile = raw_tile.loc[
        raw_tile["time"].between(pd.Timestamp(time_range[0]), pd.Timestamp(time_range[1]))
    ].copy()
    if raw_tile.empty:
        return _empty_phase4_gwd30_tropical_tile_cache()

    percentage = np.full(len(raw_tile), np.nan, dtype=np.float64)
    np.divide(
        raw_tile["wetland_area_km2"].to_numpy(dtype=np.float64),
        raw_tile["valid_area_km2"].to_numpy(dtype=np.float64),
        out=percentage,
        where=raw_tile["valid_area_km2"].to_numpy(dtype=np.float64) > 0,
    )
    raw_tile["wetland_percentage"] = percentage * 100.0
    raw_tile["year"] = raw_tile["time"].dt.year.astype(np.int64)
    raw_tile["month"] = raw_tile["time"].dt.month.astype(np.int64)
    raw_tile["observation_count"] = np.where(
        raw_tile["valid_area_km2"].to_numpy(dtype=np.float64) > 0.0,
        1,
        0,
    ).astype(np.int64)
    raw_tile["tile_id"] = tile_path.stem
    raw_tile["stage_path"] = str(tile_path)
    raw_tile["tile_west"] = float(tile_bbox[0])
    raw_tile["tile_south"] = float(tile_bbox[1])
    raw_tile["tile_east"] = float(tile_bbox[2])
    raw_tile["tile_north"] = float(tile_bbox[3])
    return raw_tile[
        [
            "time",
            "year",
            "month",
            "tile_id",
            "stage_path",
            "tile_west",
            "tile_south",
            "tile_east",
            "tile_north",
            "wetland_area_km2",
            "valid_area_km2",
            "wetland_percentage",
            "observation_count",
        ]
    ]


def build_phase4_gwd30_tropical_monthly_tile_from_reduced_file(
    *,
    reduced_path: str | Path,
    tile_bbox: BBox,
    time_range: tuple[str, str],
    tropical_mask: xr.DataArray | None = None,
    phase36_mask_path: str | Path | None = None,
) -> pd.DataFrame:
    """Compute one masked monthly tile series from one reduced GWD30 tile file."""

    if tropical_mask is None and phase36_mask_path is None:
        raise ValueError("Either tropical_mask or phase36_mask_path must be provided")

    reduced_path = Path(reduced_path)
    with xr.open_dataset(reduced_path, engine="netcdf4") as source:
        y_dim, x_dim = _spatial_dims(source["coverage"])
        coverage = source["coverage"].transpose("time", y_dim, x_dim).load()
        wetland_weighted = source["wetland_weighted"].transpose("time", y_dim, x_dim).load()

    if tropical_mask is not None:
        mask_chunk = tropical_mask.reindex(
            {
                y_dim: coverage.coords[y_dim].values,
                x_dim: coverage.coords[x_dim].values,
            },
            fill_value=0.0,
        ).load()
    else:
        mask_chunk = load_phase36_shared_mask_subset(
            phase36_mask_path,
            bbox=tile_bbox,
            y_dim=y_dim,
            x_dim=x_dim,
            y_values=np.asarray(coverage.coords[y_dim].values),
            x_values=np.asarray(coverage.coords[x_dim].values),
        )

    mask_values = np.asarray(mask_chunk.values, dtype=np.float64)
    if not np.any(mask_values > 0.0):
        return _empty_phase4_gwd30_tropical_tile_cache()

    lat_terms, lon_terms = _area_terms_from_coords(
        coverage.isel(time=0, drop=True),
        lat_values=np.asarray(coverage.coords[y_dim].values, dtype=np.float64),
        lon_values=np.asarray(coverage.coords[x_dim].values, dtype=np.float64),
    )
    chunk_area = (
        (EARTH_RADIUS_KM**2)
        * lat_terms[:, None]
        * lon_terms[None, :]
    )
    effective_weights = chunk_area * mask_values

    coverage_values = np.asarray(coverage.values, dtype=np.float32)
    wetland_weighted_values = np.asarray(wetland_weighted.values, dtype=np.float32)
    raw_tile = pd.DataFrame(
        {
            "time": pd.to_datetime(coverage.coords["time"].values),
            "wetland_area_km2": np.sum(
                wetland_weighted_values * effective_weights[None, :, :],
                axis=(1, 2),
                dtype=np.float64,
            ),
            "valid_area_km2": np.sum(
                coverage_values * effective_weights[None, :, :],
                axis=(1, 2),
                dtype=np.float64,
            ),
        }
    )
    raw_tile = raw_tile.loc[
        raw_tile["time"].between(pd.Timestamp(time_range[0]), pd.Timestamp(time_range[1]))
    ].copy()
    if raw_tile.empty:
        return _empty_phase4_gwd30_tropical_tile_cache()

    percentage = np.full(len(raw_tile), np.nan, dtype=np.float64)
    np.divide(
        raw_tile["wetland_area_km2"].to_numpy(dtype=np.float64),
        raw_tile["valid_area_km2"].to_numpy(dtype=np.float64),
        out=percentage,
        where=raw_tile["valid_area_km2"].to_numpy(dtype=np.float64) > 0,
    )
    raw_tile["wetland_percentage"] = percentage * 100.0
    monthly_tile = _collapse_raw_timesteps_to_monthly(raw_tile)
    monthly_tile["tile_id"] = reduced_path.stem
    monthly_tile["stage_path"] = str(reduced_path)
    monthly_tile["tile_west"] = float(tile_bbox[0])
    monthly_tile["tile_south"] = float(tile_bbox[1])
    monthly_tile["tile_east"] = float(tile_bbox[2])
    monthly_tile["tile_north"] = float(tile_bbox[3])
    return monthly_tile[
        [
            "time",
            "year",
            "month",
            "tile_id",
            "stage_path",
            "tile_west",
            "tile_south",
            "tile_east",
            "tile_north",
            "wetland_area_km2",
            "valid_area_km2",
            "wetland_percentage",
            "observation_count",
        ]
    ]


def build_phase4_gwd30_tropical_tile_cache_for_staged_tiles(
    *,
    year: int,
    tropical_mask: xr.DataArray,
    staged_tiles: Sequence[tuple[Path, BBox]],
    time_range: tuple[str, str],
    show_progress: bool,
    progress_label: str | None = None,
) -> pd.DataFrame:
    """Build one year's tropical tile-month cache from an explicit staged-tile list."""

    reference_grid = _ensure_spatial_rio(tropical_mask.astype(np.float32))
    tile_index = build_phase4_gwd30_tropical_tile_index_for_staged_tiles(
        year=year,
        staged_tiles=staged_tiles,
    )
    if tile_index.empty:
        return _empty_phase4_gwd30_tropical_tile_cache()

    candidate_tiles = [
        (
            Path(row["stage_path"]),
            (
                float(row["tile_west"]),
                float(row["tile_south"]),
                float(row["tile_east"]),
                float(row["tile_north"]),
            ),
        )
        for row in tile_index.to_dict(orient="records")
    ]
    tile_frames: list[pd.DataFrame] = []
    tile_progress = tqdm(
        candidate_tiles,
        total=len(candidate_tiles),
        desc=progress_label or f"Phase4 gwd30 {year} {PHASE4_GWD30_TROPICAL_CACHE_KEY}",
        disable=not show_progress,
    )
    for stage_path, stage_bbox in tile_progress:
        monthly_tile = build_phase4_gwd30_tropical_monthly_tile_from_stage_file(
            stage_path=stage_path,
            stage_bbox=stage_bbox,
            time_range=time_range,
            tropical_mask=reference_grid,
        )
        if monthly_tile.empty:
            continue
        tile_frames.append(monthly_tile)

    if not tile_frames:
        return _empty_phase4_gwd30_tropical_tile_cache()

    combined = pd.concat(tile_frames, ignore_index=True).sort_values(
        ["time", "tile_id"]
    ).reset_index(drop=True)
    logger.info(
        "Phase4 GWD30 tropical tile cache ready: year=%s rows=%s tiles=%s",
        year,
        len(combined),
        combined["tile_id"].nunique(),
    )
    return combined


def build_or_load_phase4_mask_fraction(
    *,
    base_mask: xr.DataArray,
    template: xr.DataArray,
    cache_path: Path,
    skip_existing: bool = True,
) -> xr.DataArray:
    """Build or load one dataset-grid shared mask fraction."""

    if skip_existing and cache_path.is_file():
        logger.info("Phase4 cache hit: shared_mask_fraction <- %s", cache_path)
        opened = xr.open_dataarray(cache_path)
        try:
            return _ensure_spatial_rio(opened.load())
        finally:
            opened.close()

    logger.info("Phase4 cache miss: shared_mask_fraction -> %s", cache_path)
    target_template = _spatial_template(template)
    source_mask = _ensure_spatial_rio(base_mask.astype(np.float32))

    if _same_spatial_grid(source_mask, target_template):
        mask_fraction = source_mask.copy()
    else:
        mask_fraction = reproject_to_grid(
            source_mask,
            _ensure_spatial_rio(target_template),
            resampling=Resampling.average,
        )

    mask_fraction = _ensure_spatial_rio(mask_fraction.astype(np.float32).fillna(0.0))
    mask_fraction.name = "shared_mask_fraction"
    mask_fraction.attrs["phase4_cache_version"] = PHASE4_CACHE_VERSION
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    mask_fraction.to_netcdf(
        cache_path,
        encoding={"shared_mask_fraction": {"zlib": True, "complevel": 4}},
    )
    logger.info("Phase4 cache write: shared_mask_fraction -> %s", cache_path)
    return mask_fraction


def build_or_load_phase4_berkeley_valid_mask(
    *,
    region: Phase4Region,
    output_root: str | Path,
    standardized_dir: str | Path,
    time_range: tuple[str, str],
    skip_existing: bool,
) -> xr.DataArray:
    """Build or load one region's Berkeley-valid spatial mask."""

    cache_path = phase4_berkeley_valid_mask_cache_path(
        output_root=output_root,
        region_id=region.region_id,
        time_range=time_range,
    )
    if skip_existing and cache_path.is_file():
        logger.info("Phase4 cache hit: berkeley_valid_mask <- %s", cache_path)
        opened = xr.open_dataarray(cache_path)
        try:
            return _ensure_spatial_rio(opened.load())
        finally:
            opened.close()

    logger.info(
        "Phase4 cache miss: berkeley_valid_mask -> %s (region=%s)",
        cache_path,
        region.region_id,
    )
    mask_source_time_range = _resolve_phase4_berkeley_mask_source_time_range(
        standardized_dir=standardized_dir,
        requested_time_range=time_range,
    )
    dataset = _open_phase4_dataset(
        "berkeley_rwawc",
        bbox=region.bbox,
        time_range=mask_source_time_range,
        standardized_dir=standardized_dir,
        topmodel_raw_path=None,
    )
    try:
        data = _extract_phase4_analysis_dataarray("berkeley_rwawc", dataset)
        mask_slice = _select_phase4_berkeley_mask_slice(data)
        valid_mask = xr.where(mask_slice.notnull(), 1.0, 0.0)
        valid_mask = _ensure_spatial_rio(valid_mask.astype(np.float32))
        valid_mask.name = "shared_mask_fraction"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        valid_mask.to_netcdf(
            cache_path,
            encoding={"shared_mask_fraction": {"zlib": True, "complevel": 4}},
        )
        logger.info("Phase4 cache write: berkeley_valid_mask -> %s", cache_path)
        return valid_mask
    finally:
        closer = getattr(dataset, "close", None)
        if callable(closer):
            closer()


def _select_phase4_berkeley_mask_slice(data: xr.DataArray) -> xr.DataArray:
    """Select one Berkeley time slice for the Phase 4 valid-mask footprint."""

    if "time" not in data.dims:
        return _ensure_spatial_rio(data)

    time_values = pd.to_datetime(data.coords["time"].values)
    if len(time_values) == 0:
        raise ValueError("Berkeley mask source does not contain any time steps")

    selected = data.isel(time=0, drop=True)
    logger.info(
        "Phase4 Berkeley mask slice: using time=%s",
        pd.Timestamp(time_values[0]).date().isoformat(),
    )
    return _ensure_spatial_rio(selected)


def _resolve_phase4_berkeley_mask_source_time_range(
    *,
    standardized_dir: str | Path,
    requested_time_range: tuple[str, str],
) -> tuple[str, str]:
    """Resolve the minimal Berkeley source window needed for the valid-mask footprint.

    The Phase 4 regional valid-mask is a spatial footprint, so on cache miss it only
    needs one real Berkeley time slice rather than the full requested analysis window.
    Narrowing the open-time-series request to the first available timestamp avoids
    concatenating multiple annual standardized Berkeley files during cold start.
    """

    standardized = StandardizedDataLoader(standardized_dir)
    source_paths = standardized.resolve_file_paths(
        "berkeley_rwawc",
        time_range=requested_time_range,
    )
    first_path = source_paths[0]
    with xr.open_dataset(first_path, decode_cf=True) as source:
        if "time" not in source.coords:
            raise ValueError(f"Berkeley mask source file has no time coordinate: {first_path}")
        time_values = pd.to_datetime(source.coords["time"].values)
        if len(time_values) == 0:
            raise ValueError(f"Berkeley mask source file has no time values: {first_path}")
        first_time = pd.Timestamp(time_values[0])

    selected_time = first_time.date().isoformat()
    selected_range = (selected_time, selected_time)
    logger.info(
        "Phase4 Berkeley mask source window: requested=%s selected=%s file=%s",
        requested_time_range,
        selected_range,
        first_path.name,
    )
    return selected_range


def build_phase4_annual_series(monthly: pd.DataFrame) -> pd.DataFrame:
    """Collapse monthly regional series into complete-year annual means."""

    if monthly.empty:
        return monthly.copy()

    annual = (
        monthly.assign(year=lambda frame: frame["time"].dt.year)
        .groupby("year", as_index=False)
        .agg(
            wetland_area_km2=("wetland_area_km2", "mean"),
            valid_area_km2=("valid_area_km2", "mean"),
            wetland_percentage=("wetland_percentage", "mean"),
            monthly_count=("month", "nunique"),
        )
    )
    annual = annual.loc[annual["monthly_count"] == 12].copy()
    if annual.empty:
        return pd.DataFrame(
            columns=[
                "time",
                "year",
                "month",
                "wetland_area_km2",
                "valid_area_km2",
                "wetland_percentage",
                "observation_count",
            ]
        )

    annual["time"] = pd.to_datetime(annual["year"].astype(int).astype(str) + "-01-01")
    annual["month"] = np.nan
    annual["observation_count"] = annual.pop("monthly_count").astype(int)
    return annual[
        [
            "time",
            "year",
            "month",
            "wetland_area_km2",
            "valid_area_km2",
            "wetland_percentage",
            "observation_count",
        ]
    ]


def compute_phase4_monthly_regional_series(
    *,
    monthly_data: xr.DataArray,
    mask_fraction: xr.DataArray,
    dataset_id: str,
    region_id: str,
    spatial_lat_chunk_size: int = 64,
    time_chunk_size: int = 12,
    show_progress: bool = True,
) -> pd.DataFrame:
    """Public wrapper for the chunked monthly regional reduction."""

    return _reduce_monthly_dataarray_to_regional_series(
        monthly_data=monthly_data,
        mask_fraction=mask_fraction,
        dataset_id=dataset_id,
        region_id=region_id,
        spatial_lat_chunk_size=spatial_lat_chunk_size,
        time_chunk_size=time_chunk_size,
        show_progress=show_progress,
    )


def build_phase4_climatology(monthly: pd.DataFrame) -> pd.DataFrame:
    """Collapse monthly regional series into a 12-month climatology."""

    if monthly.empty:
        return monthly.copy()

    climatology = (
        monthly.groupby("month", as_index=False)
        .agg(
            wetland_area_km2=("wetland_area_km2", "mean"),
            valid_area_km2=("valid_area_km2", "mean"),
            wetland_percentage=("wetland_percentage", "mean"),
            observation_count=("month", "size"),
        )
        .sort_values("month")
        .reset_index(drop=True)
    )
    climatology["time"] = pd.to_datetime(
        [f"2000-{int(month):02d}-01" for month in climatology["month"]]
    )
    climatology["year"] = np.nan
    return climatology[
        [
            "time",
            "year",
            "month",
            "wetland_area_km2",
            "valid_area_km2",
            "wetland_percentage",
            "observation_count",
        ]
    ]


def assemble_phase4_series_table(
    *,
    dataset_id: str,
    region_id: str,
    monthly: pd.DataFrame,
    annual: pd.DataFrame,
    climatology: pd.DataFrame,
) -> pd.DataFrame:
    """Combine monthly, annual, and climatology rows into one cache table."""

    monthly_rows = monthly.copy()
    monthly_rows["series_type"] = "monthly"

    annual_rows = annual.copy()
    annual_rows["series_type"] = "annual"

    climatology_rows = climatology.copy()
    climatology_rows["series_type"] = "climatology"

    combined = pd.concat(
        [monthly_rows, annual_rows, climatology_rows],
        ignore_index=True,
        sort=False,
    )
    combined["dataset_id"] = dataset_id
    combined["region_id"] = region_id
    combined["is_auxiliary_dataset"] = dataset_id == "berkeley_rwawc"
    return combined[
        [
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
        ]
    ]


def _open_phase4_dataset(
    dataset_id: str,
    *,
    bbox: BBox,
    time_range: tuple[str, str],
    standardized_dir: str | Path,
    topmodel_raw_path: str | Path | None,
) -> xr.Dataset:
    config = resolve_phase4_dataset_config(
        dataset_id,
        standardized_dir=standardized_dir,
        topmodel_raw_path=topmodel_raw_path,
    )
    loader = get_loader(dataset_id, config)
    open_time_series = getattr(loader, "open_time_series", None)

    if dataset_id == "topmodel" and callable(open_time_series):
        return open_time_series(bbox=bbox, time_range=time_range)
    if dataset_id == "berkeley_rwawc" and callable(open_time_series):
        return open_time_series(bbox=bbox, time_range=time_range)
    if dataset_id in {"giems_mc", "wad2m"} and callable(open_time_series):
        return open_time_series(bbox=bbox, time_range=time_range)
    return loader.load(bbox=bbox, time_range=time_range)


def _extract_phase4_analysis_dataarray(dataset_id: str, dataset: xr.Dataset) -> xr.DataArray:
    if dataset_id == "berkeley_rwawc":
        for variable_name in ("watermask", "water_mask"):
            if variable_name in dataset:
                data = dataset[variable_name]
                break
        else:
            raise KeyError("Berkeley dataset does not expose watermask/water_mask")
    elif "wetland_fraction" in dataset:
        data = dataset["wetland_fraction"]
    else:
        classified = wetland_fraction_from_standardized_classes(dataset_id, dataset)
        if classified is None:
            raise KeyError(
                f"Could not resolve a Phase 4 analysis variable for dataset {dataset_id!r}"
            )
        data = classified

    if dataset_id == "topmodel":
        if "config" in data.dims:
            data = data.mean(dim="config", skipna=True)
        if "forcing" in data.dims:
            data = data.mean(dim="forcing", skipna=True)

    data = data.astype(np.float32).clip(min=0.0, max=1.0)
    return _ensure_spatial_rio(data)


def _to_monthly_dataarray(data: xr.DataArray) -> xr.DataArray:
    if "time" not in data.dims:
        raise ValueError("Phase 4 analysis data must include a time dimension")
    monthly = data.resample(time="MS").mean(skipna=True)
    monthly.name = data.name or "phase4_value"
    return _ensure_spatial_rio(monthly.astype(np.float32))


def _reduce_monthly_dataarray_to_regional_series(
    *,
    monthly_data: xr.DataArray,
    mask_fraction: xr.DataArray,
    dataset_id: str,
    region_id: str,
    spatial_lat_chunk_size: int,
    time_chunk_size: int,
    show_progress: bool,
) -> pd.DataFrame:
    y_dim, x_dim = _spatial_dims(monthly_data)
    times = pd.to_datetime(monthly_data["time"].values)
    wetland_area = np.zeros(len(times), dtype=np.float64)
    valid_area = np.zeros(len(times), dtype=np.float64)

    lat_values = np.asarray(monthly_data.coords[y_dim].values, dtype=np.float64)
    lon_values = np.asarray(monthly_data.coords[x_dim].values, dtype=np.float64)
    lat_area_terms, lon_width_terms = _area_terms_from_coords(
        monthly_data,
        lat_values=lat_values,
        lon_values=lon_values,
    )

    progress = tqdm(
        range(0, len(times), time_chunk_size),
        total=max(1, int(np.ceil(len(times) / max(1, time_chunk_size)))),
        desc=f"Phase4 {dataset_id} {region_id}",
        disable=not show_progress,
    )
    for time_start in progress:
        time_stop = min(len(times), time_start + max(1, time_chunk_size))
        time_chunk = monthly_data.isel(time=slice(time_start, time_stop))
        for row_start in range(0, len(lat_values), max(1, spatial_lat_chunk_size)):
            row_stop = min(len(lat_values), row_start + max(1, spatial_lat_chunk_size))
            data_chunk = (
                time_chunk.isel({y_dim: slice(row_start, row_stop)})
                .transpose("time", y_dim, x_dim)
                .load()
            )
            mask_chunk = mask_fraction.isel({y_dim: slice(row_start, row_stop)}).load()
            values = np.asarray(data_chunk.values, dtype=np.float32)
            mask_values = np.asarray(mask_chunk.values, dtype=np.float64)

            chunk_area = (
                (EARTH_RADIUS_KM**2)
                * lat_area_terms[row_start:row_stop][:, None]
                * lon_width_terms[None, :]
            )
            effective_weights = chunk_area * mask_values
            valid = np.isfinite(values)
            safe_values = np.where(valid, values, 0.0)

            wetland_area[time_start:time_stop] += np.sum(
                safe_values * effective_weights[None, :, :],
                axis=(1, 2),
                dtype=np.float64,
            )
            valid_area[time_start:time_stop] += np.sum(
                valid * effective_weights[None, :, :],
                axis=(1, 2),
                dtype=np.float64,
            )

    percentage = np.full(len(times), np.nan, dtype=np.float64)
    np.divide(
        wetland_area,
        valid_area,
        out=percentage,
        where=valid_area > 0,
    )
    percentage *= 100.0

    frame = pd.DataFrame(
        {
            "time": times,
            "year": times.year.astype(np.int64),
            "month": times.month.astype(np.int64),
            "wetland_area_km2": wetland_area.astype(np.float64),
            "valid_area_km2": valid_area.astype(np.float64),
            "wetland_percentage": percentage.astype(np.float64),
            "observation_count": np.ones(len(times), dtype=np.int64),
        }
    )
    logger.info(
        "Phase4 regional monthly series ready: dataset=%s region=%s rows=%s",
        dataset_id,
        region_id,
        len(frame),
    )
    return frame


def _build_phase4_gwd30_tropical_tile_cache_year(
    *,
    year: int,
    tropical_mask: xr.DataArray,
    standardized_dir: str | Path,
    time_range: tuple[str, str],
    show_progress: bool,
) -> pd.DataFrame:
    staging_root = Path(standardized_dir).expanduser() / "_staging" / f"gwd30_{year}"
    staged_tiles = load_phase4_gwd30_staged_tiles(standardized_dir, year=year)
    logger.info(
        "Phase4 GWD30 tropical tile cache build: year=%s staging_root=%s restored=%s",
        year,
        staging_root,
        len(staged_tiles),
    )
    logger.info(
        "Phase4 GWD30 standardized staging root hit: year=%s no raw staging performed",
        year,
    )
    return build_phase4_gwd30_tropical_tile_cache_for_staged_tiles(
        year=year,
        tropical_mask=tropical_mask,
        staged_tiles=staged_tiles,
        time_range=time_range,
        show_progress=show_progress,
        progress_label=f"Phase4 gwd30 {year} {PHASE4_GWD30_TROPICAL_CACHE_KEY}",
    )


def _spatial_template(data: xr.DataArray) -> xr.DataArray:
    template = data
    for dim in list(template.dims):
        if dim not in {"time", "lat", "lon", "y", "x"}:
            template = template.isel({dim: 0}, drop=True)
    if "time" in template.dims:
        template = template.isel(time=0, drop=True)
    return _ensure_spatial_rio(template)


def _mask_fraction_for_template(
    *,
    base_mask: xr.DataArray,
    template: xr.DataArray,
) -> xr.DataArray:
    """Project one region mask to one target grid without persisting a cache file."""

    target_template = _spatial_template(template)
    source_base = _ensure_spatial_rio(base_mask)
    try:
        source_subset = subset_phase4_mask_to_bbox(
            source_base,
            _bbox_from_spatial_template(target_template),
        )
    except ValueError:
        empty = xr.zeros_like(target_template, dtype=np.float32)
        empty = _ensure_spatial_rio(empty)
        empty.name = "shared_mask_fraction"
        return empty

    source_mask = _ensure_spatial_rio(source_subset.astype(np.float32))
    if _same_spatial_grid(source_mask, target_template):
        return source_mask.copy()

    mask_fraction = reproject_to_grid(
        source_mask,
        _ensure_spatial_rio(target_template),
        resampling=Resampling.average,
    )
    return _ensure_spatial_rio(mask_fraction.astype(np.float32).fillna(0.0))


def _bbox_from_spatial_template(template: xr.DataArray) -> BBox:
    """Return a simple lon/lat bbox from one target spatial template."""

    y_dim, x_dim = _spatial_dims(template)
    lon_values = np.asarray(template.coords[x_dim].values, dtype=np.float64)
    lat_values = np.asarray(template.coords[y_dim].values, dtype=np.float64)
    return (
        float(np.min(lon_values)),
        float(np.min(lat_values)),
        float(np.max(lon_values)),
        float(np.max(lat_values)),
    )


def _ensure_spatial_rio(data: xr.DataArray) -> xr.DataArray:
    result = data
    if result.rio.crs is None:
        result = result.rio.write_crs("EPSG:4326", inplace=False)
    x_dim = "lon" if "lon" in result.dims else "x"
    y_dim = "lat" if "lat" in result.dims else "y"
    return result.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=False)


def _same_spatial_grid(left: xr.DataArray, right: xr.DataArray) -> bool:
    left_y, left_x = _spatial_dims(left)
    right_y, right_x = _spatial_dims(right)
    return (
        left.sizes[left_y] == right.sizes[right_y]
        and left.sizes[left_x] == right.sizes[right_x]
        and np.array_equal(left.coords[left_y].values, right.coords[right_y].values)
        and np.array_equal(left.coords[left_x].values, right.coords[right_x].values)
    )


def _bbox_intersects(left: BBox, right: BBox) -> bool:
    return not (
        left[2] <= right[0]
        or left[0] >= right[2]
        or left[3] <= right[1]
        or left[1] >= right[3]
    )


def _spatial_dims(data: xr.DataArray) -> tuple[str, str]:
    if "lat" in data.dims and "lon" in data.dims:
        return "lat", "lon"
    if "y" in data.dims and "x" in data.dims:
        return "y", "x"
    raise ValueError(f"Could not resolve spatial dims from {data.dims!r}")


def _area_terms_from_coords(
    data: xr.DataArray,
    *,
    lat_values: np.ndarray,
    lon_values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    lat_edges = _coordinate_edges(lat_values, axis="lat", data=data)
    lon_edges = _coordinate_edges(lon_values, axis="lon", data=data)

    lat_lower = np.minimum(lat_edges[:-1], lat_edges[1:])
    lat_upper = np.maximum(lat_edges[:-1], lat_edges[1:])
    lon_lower = np.minimum(lon_edges[:-1], lon_edges[1:])
    lon_upper = np.maximum(lon_edges[:-1], lon_edges[1:])

    lat_term = np.sin(np.deg2rad(lat_upper)) - np.sin(np.deg2rad(lat_lower))
    lon_term = np.deg2rad(lon_upper - lon_lower)
    return lat_term.astype(np.float64), lon_term.astype(np.float64)


def _coordinate_edges(
    values: np.ndarray,
    *,
    axis: str,
    data: xr.DataArray,
) -> np.ndarray:
    if values.size == 0:
        raise ValueError("Cannot derive cell edges from an empty coordinate")
    if values.size == 1:
        try:
            resolution_x, resolution_y = data.rio.resolution()
            resolution = abs(resolution_x if axis == "lon" else resolution_y)
        except Exception:  # noqa: BLE001
            resolution = 1.0
        center = float(values[0])
        return np.array([center - resolution / 2.0, center + resolution / 2.0], dtype=np.float64)

    mids = (values[:-1] + values[1:]) / 2.0
    edges = np.empty(values.size + 1, dtype=np.float64)
    edges[1:-1] = mids
    edges[0] = values[0] - (mids[0] - values[0])
    edges[-1] = values[-1] + (values[-1] - mids[-1])
    return edges


def _read_phase4_table(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "time" in frame.columns:
        frame["time"] = pd.to_datetime(frame["time"])
    return frame


def _empty_phase4_monthly_series() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "time",
            "year",
            "month",
            "wetland_area_km2",
            "valid_area_km2",
            "wetland_percentage",
            "observation_count",
        ]
    )


def _empty_phase4_gwd30_tropical_tile_cache() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "time",
            "year",
            "month",
            "tile_id",
            "stage_path",
            "tile_west",
            "tile_south",
            "tile_east",
            "tile_north",
            "wetland_area_km2",
            "valid_area_km2",
            "wetland_percentage",
            "observation_count",
        ]
    )


def _empty_phase4_gwd30_tropical_tile_index() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "tile_id",
            "stage_path",
            "tile_west",
            "tile_south",
            "tile_east",
            "tile_north",
        ]
    )


def _empty_phase4_gwd30_reduced_tile_index() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "tile_id",
            "reduced_path",
            "tile_west",
            "tile_south",
            "tile_east",
            "tile_north",
        ]
    )


def _coerce_json_bbox(value: object) -> BBox:
    if not isinstance(value, list | tuple) or len(value) != 4:
        raise ValueError(f"Expected bbox list of length 4, got {value!r}")
    west, south, east, north = (float(item) for item in value)
    return (west, south, east, north)


def _collapse_raw_timesteps_to_monthly(raw: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        raw.assign(time=lambda frame: frame["time"].dt.to_period("M").dt.to_timestamp())
        .groupby("time", as_index=False)
        .agg(
            wetland_area_km2=("wetland_area_km2", "mean"),
            valid_area_km2=("valid_area_km2", "mean"),
            wetland_percentage=("wetland_percentage", "mean"),
            observation_count=("wetland_percentage", "size"),
        )
        .sort_values("time")
        .reset_index(drop=True)
    )
    monthly["year"] = monthly["time"].dt.year.astype(np.int64)
    monthly["month"] = monthly["time"].dt.month.astype(np.int64)
    return monthly[
        [
            "time",
            "year",
            "month",
            "wetland_area_km2",
            "valid_area_km2",
            "wetland_percentage",
            "observation_count",
        ]
    ]


def _gwd30_years_for_time_range(
    dataset_config: Mapping[str, Any],
    time_range: tuple[str, str],
) -> list[int]:
    start_year = pd.Timestamp(time_range[0]).year
    end_year = pd.Timestamp(time_range[1]).year
    years = [int(year) for year in dataset_config.get("years", [])]
    return [year for year in years if start_year <= year <= end_year]
