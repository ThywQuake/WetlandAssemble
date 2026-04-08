"""Per-pixel Mann-Kendall trend analysis for dynamic wetland datasets."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
from scipy import stats

from WA.classification import wetland_class_ids
from WA.comparison.evidence_contract import metadata_json, validate_stem_token
from WA.comparison.harmonize import create_comparison_grid, harmonize_binary_dataset
from WA.config import get_dataset_config
from WA.loaders import get_loader
from WA.loaders.base import BBox
from WA.standardize import _load_gwd30_staged_tiles_from_stage_shard_manifests

AggregationLevel = Literal["annual", "seasonal", "monthly"]
PixelStatsAggregation = Literal["native", "annual", "monthly"]
Gwd30PixelStatsTransform = Literal["native", "annual", "monthly"]

# Minimum valid observations required to compute a trend
DEFAULT_MIN_OBSERVATIONS = 5

# Alpha for significance test (p < alpha → significant)
DEFAULT_ALPHA = 0.05

# Season ordering for consistent output
_SEASON_ORDER = ["DJF", "MAM", "JJA", "SON"]
DEFAULT_GWD30_STANDARDIZED_DIR = Path("output/standardized")
PHASE4_GWD30_PIXEL_STATS_TRANSFORM_VERSION = 1

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrendResult:
    """Per-pixel Mann-Kendall + Sen's Slope trend analysis result."""

    dataset_id: str
    aggregation: AggregationLevel
    time_range: tuple[str, str]  # ISO format (start, end)
    observation_count: int
    sens_slope: xr.DataArray  # wetland fraction per time step
    p_value: xr.DataArray
    z_score: xr.DataArray
    significant: xr.DataArray  # bool mask (p < alpha)
    trend_direction: xr.DataArray  # +1 increasing, 0 stable, -1 decreasing
    status: str  # "computed" | "insufficient_observations"


@dataclass(frozen=True)
class TrendCheckpointBundle:
    """One resumable region/dataset/time-window trend checkpoint."""

    checkpoint_path: Path
    region_id: str
    dataset_id: str
    aggregation: AggregationLevel
    requested_time_range: tuple[str, str]
    time_range: tuple[str, str]
    bbox: BBox
    observation_count: int
    status: str
    trend_result: TrendResult
    checkpoint_metadata_json: str
    checkpoint_metadata: dict[str, Any]


TREND_CHECKPOINT_VERSION = 1
TREND_CHECKPOINT_DIRNAME = "trend_checkpoints"
TREND_CHECKPOINT_SUFFIX = "trend_checkpoint"
REQUIRED_TREND_CHECKPOINT_VARS = (
    "sens_slope",
    "p_value",
    "z_score",
    "significant",
    "trend_direction",
)


def trend_checkpoint_output_path(
    output_root: str | Path,
    *,
    region_id: str,
    dataset_id: str,
    aggregation: AggregationLevel,
    time_range: tuple[str, str],
) -> Path:
    """Return the checkpoint path for one region/dataset/time window."""

    dataset_slot = validate_stem_token(dataset_id, label="dataset_id")
    region_slot = validate_stem_token(region_id, label="region_id")
    start_token, end_token = _trend_checkpoint_time_tokens(time_range)
    return (
        Path(output_root)
        / TREND_CHECKPOINT_DIRNAME
        / region_slot
        / (
            f"{dataset_slot}__{region_slot}__{aggregation}"
            f"__{start_token}_{end_token}__{TREND_CHECKPOINT_SUFFIX}.nc"
        )
    )


def materialize_trend_checkpoint(
    *,
    output_root: str | Path,
    region_id: str,
    bbox: BBox,
    dataset_id: str,
    time_range: tuple[str, str],
    aggregation: AggregationLevel,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
    gwd30_standardized_dir: str | Path = DEFAULT_GWD30_STANDARDIZED_DIR,
    show_progress: bool = True,
    skip_existing: bool = True,
) -> TrendCheckpointBundle:
    """Load or compute one region/dataset/time-window trend checkpoint."""

    checkpoint_path = trend_checkpoint_output_path(
        output_root,
        region_id=region_id,
        dataset_id=dataset_id,
        aggregation=aggregation,
        time_range=time_range,
    )
    if skip_existing and checkpoint_path.is_file():
        logger.info(
            "stage=trend-load region=%s dataset_id=%s aggregation=%s "
            "time_range=%s action=reload checkpoint=%s",
            region_id,
            dataset_id,
            aggregation,
            time_range,
            checkpoint_path,
        )
        return load_trend_checkpoint(
            checkpoint_path,
            expected_region_id=region_id,
            expected_dataset_id=dataset_id,
            expected_aggregation=aggregation,
            expected_time_range=time_range,
        )

    logger.info(
        "stage=trend-load region=%s dataset_id=%s aggregation=%s "
        "time_range=%s action=compute checkpoint=%s",
        region_id,
        dataset_id,
        aggregation,
        time_range,
        checkpoint_path,
    )
    reference_grid = create_comparison_grid(bbox)
    surface = load_trend_surface(
        dataset_id,
        bbox=bbox,
        time_range=time_range,
        reference_grid=reference_grid,
        gwd30_standardized_dir=gwd30_standardized_dir,
        show_progress=show_progress,
    )
    trend_result = compute_pixel_trends(
        surface,
        dataset_id=dataset_id,
        aggregation=aggregation,
        min_observations=min_observations,
    )
    return write_trend_checkpoint(
        checkpoint_path,
        region_id=region_id,
        requested_time_range=time_range,
        bbox=bbox,
        trend_result=trend_result,
    )


def write_trend_checkpoint(
    path: str | Path,
    *,
    region_id: str,
    requested_time_range: tuple[str, str],
    bbox: BBox,
    trend_result: TrendResult,
) -> TrendCheckpointBundle:
    """Write one resumable trend checkpoint and reload it semantically."""

    normalized_dataset_id = validate_stem_token(trend_result.dataset_id, label="dataset_id")
    checkpoint_path = Path(path)
    checkpoint_metadata = {
        "checkpoint_kind": TREND_CHECKPOINT_SUFFIX,
        "checkpoint_version": TREND_CHECKPOINT_VERSION,
        "region_id": region_id,
        "dataset_id": normalized_dataset_id,
        "aggregation": trend_result.aggregation,
        "requested_time_range": list(requested_time_range),
        "result_time_range": list(trend_result.time_range),
        "observation_count": int(trend_result.observation_count),
        "status": trend_result.status,
        "bbox": list(bbox),
    }
    checkpoint_metadata_json = metadata_json(checkpoint_metadata)
    dataset = xr.Dataset(
        {
            "sens_slope": trend_result.sens_slope.astype(np.float32),
            "p_value": trend_result.p_value.astype(np.float32),
            "z_score": trend_result.z_score.astype(np.float32),
            "significant": trend_result.significant.astype(np.int8),
            "trend_direction": trend_result.trend_direction.astype(np.int8),
        }
    )
    dataset.attrs.update(
        {
            "checkpoint_kind": TREND_CHECKPOINT_SUFFIX,
            "checkpoint_version": TREND_CHECKPOINT_VERSION,
            "region_id": region_id,
            "dataset_id": normalized_dataset_id,
            "aggregation": trend_result.aggregation,
            "requested_time_range_start": requested_time_range[0],
            "requested_time_range_end": requested_time_range[1],
            "result_time_range_start": trend_result.time_range[0],
            "result_time_range_end": trend_result.time_range[1],
            "observation_count": int(trend_result.observation_count),
            "status": trend_result.status,
            "bbox_json": json.dumps(list(bbox), separators=(",", ":")),
            "checkpoint_metadata_json": checkpoint_metadata_json,
        }
    )
    _write_dataset_atomic(path=checkpoint_path, dataset=dataset)
    return load_trend_checkpoint(
        checkpoint_path,
        expected_region_id=region_id,
        expected_dataset_id=normalized_dataset_id,
        expected_aggregation=trend_result.aggregation,
        expected_time_range=requested_time_range,
    )


def load_trend_checkpoint(
    path: str | Path,
    *,
    expected_region_id: str,
    expected_dataset_id: str,
    expected_aggregation: AggregationLevel,
    expected_time_range: tuple[str, str],
) -> TrendCheckpointBundle:
    """Reload one trend checkpoint with strict metadata validation."""

    checkpoint_path = Path(path)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            f"missing checkpoint path={checkpoint_path}"
        )

    dataset = xr.load_dataset(checkpoint_path)
    missing_vars = [
        name for name in REQUIRED_TREND_CHECKPOINT_VARS if name not in dataset.data_vars
    ]
    if missing_vars:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            "checkpoint is missing required variables: " + ", ".join(missing_vars)
        )

    checkpoint_kind = str(dataset.attrs.get("checkpoint_kind", "")).strip()
    if checkpoint_kind != TREND_CHECKPOINT_SUFFIX:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            f"mixed checkpoint metadata: checkpoint_kind={checkpoint_kind!r}"
        )
    checkpoint_version = int(dataset.attrs.get("checkpoint_version", 0))
    if checkpoint_version != TREND_CHECKPOINT_VERSION:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            f"mixed checkpoint metadata: checkpoint_version={checkpoint_version}"
        )

    actual_region_id = str(dataset.attrs.get("region_id", "")).strip()
    if actual_region_id != expected_region_id:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            f"mixed checkpoint metadata: region_id={actual_region_id!r}"
        )
    actual_dataset_id = str(dataset.attrs.get("dataset_id", "")).strip()
    if actual_dataset_id != expected_dataset_id:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            f"mixed checkpoint metadata: dataset_id={actual_dataset_id!r}"
        )

    aggregation = cast(
        AggregationLevel,
        str(dataset.attrs.get("aggregation", "")).strip(),
    )
    if aggregation not in {"annual", "seasonal", "monthly"}:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            f"mixed checkpoint metadata: aggregation={aggregation!r}"
        )
    if aggregation != expected_aggregation:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            f"mixed checkpoint metadata: aggregation={aggregation!r}"
        )

    requested_time_range = (
        str(dataset.attrs.get("requested_time_range_start", "")).strip(),
        str(dataset.attrs.get("requested_time_range_end", "")).strip(),
    )
    if requested_time_range != expected_time_range:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            f"mixed checkpoint metadata: requested_time_range={requested_time_range!r}"
        )

    result_time_range = (
        str(dataset.attrs.get("result_time_range_start", "")).strip(),
        str(dataset.attrs.get("result_time_range_end", "")).strip(),
    )
    if not result_time_range[0] or not result_time_range[1]:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            "missing result_time_range metadata"
        )

    observation_count = int(dataset.attrs.get("observation_count", 0))
    if observation_count < 0:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            f"invalid observation_count={observation_count}"
        )
    status = str(dataset.attrs.get("status", "")).strip()
    if not status:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} missing status"
        )

    bbox = _parse_bbox_json(
        dataset.attrs.get("bbox_json", ""),
        region_id=expected_region_id,
        dataset_id=expected_dataset_id,
    )
    checkpoint_metadata_json = str(dataset.attrs.get("checkpoint_metadata_json", "")).strip()
    if not checkpoint_metadata_json:
        raise ValueError(
            "stage=trend-load "
            f"region_id={expected_region_id} dataset_id={expected_dataset_id} "
            "missing checkpoint_metadata_json"
        )
    checkpoint_metadata = _parse_checkpoint_metadata_json(
        checkpoint_metadata_json,
        region_id=expected_region_id,
        dataset_id=expected_dataset_id,
    )

    trend_result = TrendResult(
        dataset_id=expected_dataset_id,
        aggregation=aggregation,
        time_range=result_time_range,
        observation_count=observation_count,
        sens_slope=dataset["sens_slope"],
        p_value=dataset["p_value"],
        z_score=dataset["z_score"],
        significant=dataset["significant"].astype(bool),
        trend_direction=dataset["trend_direction"].astype(np.int8),
        status=status,
    )
    return TrendCheckpointBundle(
        checkpoint_path=checkpoint_path.resolve(),
        region_id=expected_region_id,
        dataset_id=expected_dataset_id,
        aggregation=aggregation,
        requested_time_range=requested_time_range,
        time_range=result_time_range,
        bbox=bbox,
        observation_count=observation_count,
        status=status,
        trend_result=trend_result,
        checkpoint_metadata_json=checkpoint_metadata_json,
        checkpoint_metadata=checkpoint_metadata,
    )


def build_gwd30_pixel_statistics(
    *,
    bbox: BBox,
    time_range: tuple[str, str] | None = None,
    aggregation: PixelStatsAggregation = "monthly",
    reference_grid: xr.DataArray | None = None,
    gwd30_standardized_dir: str | Path = DEFAULT_GWD30_STANDARDIZED_DIR,
    show_progress: bool = True,
) -> xr.Dataset:
    """Build trend-ready GWD30 per-pixel statistics without any external mask."""

    stats_grid = reference_grid if reference_grid is not None else create_comparison_grid(bbox)
    surface = load_trend_surface(
        "gwd30",
        bbox=bbox,
        time_range=time_range,
        reference_grid=stats_grid,
        gwd30_standardized_dir=gwd30_standardized_dir,
        show_progress=show_progress,
    )
    if aggregation == "native":
        aggregated = surface
    elif aggregation in {"annual", "monthly"}:
        aggregated = cast(
            xr.DataArray,
            _aggregate_time_series(surface, cast(AggregationLevel, aggregation)),
        )
    else:
        raise ValueError(f"Unsupported GWD30 pixel statistics aggregation: {aggregation!r}")

    if "time" not in aggregated.dims:
        raise ValueError(
            "GWD30 pixel statistics require a time-like dimension after aggregation"
        )

    cell_area = _cell_area_grid_km2(aggregated.isel(time=0, drop=True))
    valid_observation_count = aggregated.notnull().sum(dim="time").astype(np.int32)
    mean_fraction = aggregated.mean(dim="time", skipna=True).astype(np.float32)
    std_fraction = aggregated.std(dim="time", skipna=True).astype(np.float32)

    stats_ds = xr.Dataset(
        {
            "wetland_fraction": aggregated.astype(np.float32),
            "valid_observation_count": valid_observation_count,
            "mean_wetland_fraction": mean_fraction,
            "std_wetland_fraction": std_fraction,
            "cell_area_km2": cell_area.astype(np.float32),
        }
    )
    times = pd.to_datetime(aggregated["time"].values)
    stats_ds.attrs.update(
        {
            "dataset_id": "gwd30",
            "source": "phase4_gwd30_pixel_statistics",
            "aggregation": aggregation,
            "time_range_start": str(times[0].date()) if len(times) else "",
            "time_range_end": str(times[-1].date()) if len(times) else "",
            "gwd30_standardized_dir": str(Path(gwd30_standardized_dir).expanduser()),
            "bbox": [float(value) for value in bbox],
            "comparison_resolution_deg": float(
                stats_grid.attrs.get("comparison_resolution_deg", np.nan)
            ),
        }
    )
    return stats_ds


def phase4_gwd30_pixel_stats_tile_dir(
    *,
    output_root: str | Path,
    year: int,
    aggregation: Gwd30PixelStatsTransform,
) -> Path:
    return (
        Path(output_root)
        / "pixel_stats"
        / "gwd30"
        / f"gwd30_{year}"
        / aggregation
        / "tiles"
    )


def build_gwd30_native_pixel_statistics_tiles(
    *,
    output_root: str | Path,
    standardized_dir: str | Path = DEFAULT_GWD30_STANDARDIZED_DIR,
    years: list[int] | None = None,
    time_range: tuple[str, str] | None = None,
    aggregation: Gwd30PixelStatsTransform = "monthly",
    worker_count: int | None = None,
    show_progress: bool = True,
    skip_existing: bool = True,
) -> dict[int, list[tuple[Path, BBox]]]:
    """Build native staged-grid GWD30 pixel-statistics tiles for Stage 1."""

    dataset_config = get_dataset_config("gwd30")
    loader = get_loader("gwd30", dataset_config)
    transform_tiles = getattr(loader, "transform_staged_time_fraction_tiles", None)
    if not callable(transform_tiles):
        raise TypeError("Configured GWD30 loader does not expose transformed staged-tile helpers")

    selected_years = (
        sorted(int(year) for year in years)
        if years is not None and len(years) > 0
        else _gwd30_years_for_time_range(dataset_config, time_range)
    )
    if not selected_years:
        raise ValueError("No GWD30 years were selected for Stage-1 pixel statistics")

    transform_name = f"phase4_pixel_stats_{aggregation}"
    transform_tile = _gwd30_pixel_stats_transform_for_aggregation(aggregation)
    transformed_by_year: dict[int, list[tuple[Path, BBox]]] = {}
    standardized_root = Path(standardized_dir).expanduser()

    for year in selected_years:
        staged_tiles = _load_gwd30_staged_tiles_from_standardized_dir(
            standardized_root,
            year=year,
        )
        logger.info(
            "Phase4 stage1 native tile stats: year=%s staging_root=%s restored=%s aggregation=%s",
            year,
            standardized_root / "_staging" / f"gwd30_{year}",
            len(staged_tiles),
            aggregation,
        )
        output_dir = phase4_gwd30_pixel_stats_tile_dir(
            output_root=output_root,
            year=year,
            aggregation=aggregation,
        )
        transformed_by_year[year] = transform_tiles(
            staged_tiles=staged_tiles,
            output_dir=output_dir,
            transform_name=transform_name,
            transform_version=PHASE4_GWD30_PIXEL_STATS_TRANSFORM_VERSION,
            transform_tile=transform_tile,
            year=year,
            worker_count=worker_count,
            show_progress=show_progress,
            skip_existing=skip_existing,
        )

    return transformed_by_year


def load_trend_surface(
    dataset_id: str,
    *,
    bbox: BBox,
    time_range: tuple[str, str] | None = None,
    reference_grid: xr.DataArray | None = None,
    gwd30_standardized_dir: str | Path = DEFAULT_GWD30_STANDARDIZED_DIR,
    show_progress: bool = True,
) -> xr.DataArray:
    """Load one dataset as a trend-ready wetland-fraction surface.

    GWD30 uses the staged-tile workflow on the requested trend grid so large
    trend probes avoid materializing the full multi-year 30 m mosaic in memory.
    Other datasets keep the existing loader -> harmonize path.
    """

    trend_grid = reference_grid if reference_grid is not None else create_comparison_grid(bbox)

    if dataset_id == "gwd30":
        dataset = _load_gwd30_trend_dataset_from_staged_tiles(
            bbox=bbox,
            time_range=time_range,
            reference_grid=trend_grid,
            standardized_dir=Path(gwd30_standardized_dir),
            show_progress=show_progress,
        )
    else:
        dataset_config = get_dataset_config(dataset_id)
        loader = get_loader(dataset_id, dataset_config)
        dataset = loader.load(bbox=bbox, time_range=time_range)  # type: ignore[call-arg]

    return harmonize_binary_dataset(
        dataset_id,
        dataset,
        reference_grid=trend_grid,
    )


def compute_pixel_trends(
    harmonized_surface: xr.DataArray,
    *,
    dataset_id: str,
    aggregation: AggregationLevel = "annual",
    confidence_level: float = 0.95,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> TrendResult:
    """Compute per-pixel Mann-Kendall + Sen's Slope trend test.

    Parameters
    ----------
    harmonized_surface:
        Output of harmonize_binary_dataset(), dims (time, lat, lon),
        values are wetland fraction [0, 1].
    dataset_id:
        Dataset identifier for metadata.
    aggregation:
        Time aggregation level: "annual", "seasonal", or "monthly".
    confidence_level:
        Confidence level for significance (default 0.95 → alpha=0.05).
    min_observations:
        Minimum valid time steps required; returns
        status='insufficient_observations' if not met.

    Returns
    -------
    TrendResult with 5 spatial DataArrays + metadata.
    """
    alpha = 1.0 - confidence_level

    # Aggregate time series
    aggregated = _aggregate_time_series(harmonized_surface, aggregation)

    time_dim = "time" if aggregation != "seasonal" else "season"
    n_obs = aggregated.sizes.get(time_dim, 0)

    # Record time range from the *pre-aggregation* data
    times = harmonized_surface["time"].values
    time_range = (
        str(pd.Timestamp(times[0]).date()),
        str(pd.Timestamp(times[-1]).date()),
    )

    if n_obs < min_observations:
        nan_spatial = xr.full_like(
            harmonized_surface.isel(time=0).drop_vars("time", errors="ignore"),
            fill_value=np.nan,
            dtype=float,
        )
        zero_spatial = nan_spatial.fillna(0.0)
        return TrendResult(
            dataset_id=dataset_id,
            aggregation=aggregation,
            time_range=time_range,
            observation_count=n_obs,
            sens_slope=nan_spatial,
            p_value=nan_spatial,
            z_score=nan_spatial,
            significant=zero_spatial.astype(bool),
            trend_direction=zero_spatial.astype(np.int8),
            status="insufficient_observations",
        )

    result_ds = _vectorized_mk_test(aggregated, alpha=alpha, time_dim=time_dim)

    return TrendResult(
        dataset_id=dataset_id,
        aggregation=aggregation,
        time_range=time_range,
        observation_count=n_obs,
        sens_slope=result_ds["sens_slope"],
        p_value=result_ds["p_value"],
        z_score=result_ds["z_score"],
        significant=result_ds["significant"],
        trend_direction=result_ds["trend_direction"],
        status="computed",
    )


def _load_gwd30_trend_dataset_from_staged_tiles(
    *,
    bbox: BBox,
    time_range: tuple[str, str] | None,
    reference_grid: xr.DataArray,
    standardized_dir: Path,
    show_progress: bool,
) -> xr.Dataset:
    """Load GWD30 fractions on the trend grid via staged tiles."""

    dataset_config = get_dataset_config("gwd30")
    loader = get_loader("gwd30", dataset_config)
    merge_staged_time_fraction_tiles = getattr(loader, "merge_staged_time_fraction_tiles", None)
    if not callable(merge_staged_time_fraction_tiles):
        raise TypeError(
            "Configured GWD30 loader does not expose staged tile trend helpers"
        )

    years = _gwd30_years_for_time_range(dataset_config, time_range)
    if not years:
        raise FileNotFoundError(f"No GWD30 years overlap requested time_range {time_range!r}")

    year_datasets: list[xr.Dataset] = []
    for year in years:
        staging_root = standardized_dir.expanduser() / "_staging" / f"gwd30_{year}"
        staged_tiles = _load_gwd30_staged_tiles_from_standardized_dir(
            standardized_dir,
            year=year,
        )
        logger.info(
            "Phase4 GWD30 trend load: year=%s bbox=%s staging_root=%s restored=%s "
            "no raw staging performed",
            year,
            bbox,
            staging_root,
            len(staged_tiles),
        )
        logger.info(
            "Phase4 GWD30 trend merge: year=%s staged_tile_count=%s",
            year,
            len(staged_tiles),
        )
        year_dataset = merge_staged_time_fraction_tiles(
            staged_tiles=staged_tiles,
            reference_grid=reference_grid,
            bbox=bbox,
            year=year,
        )
        year_datasets.append(year_dataset)

    dataset = xr.concat(year_datasets, dim="time").sortby("time")
    if time_range is not None:
        dataset = dataset.sel(time=slice(*time_range))
    dataset.attrs.update(
        {
            "dataset_id": "gwd30",
            "source": "phase4_gwd30_staged_tiles",
            "phase4_gwd30_stage_cache_root": str(standardized_dir.expanduser()),
        }
    )
    return dataset


def _load_gwd30_staged_tiles_from_standardized_dir(
    standardized_dir: Path,
    *,
    year: int,
) -> list[tuple[Path, BBox]]:
    staging_root = standardized_dir.expanduser() / "_staging" / f"gwd30_{year}"
    staged_tiles = _load_gwd30_staged_tiles_from_stage_shard_manifests(staging_root)
    if staged_tiles:
        return staged_tiles
    raise FileNotFoundError(
        "No staged GWD30 tile manifests were found under "
        f"{staging_root}. Expected stage_shard_*.json referencing tile_partials/tile_*.nc."
    )


def compute_year_over_year_change(
    harmonized_surface: xr.DataArray,
    *,
    dataset_id: str,
) -> xr.Dataset:
    """Compute short-term year-over-year wetland fraction change.

    No statistical test — raw annual diffs for short-term monitoring.

    Returns
    -------
    xr.Dataset with variables:
    - ``delta_fraction``: annual diff (year N minus year N-1)
    - ``change_direction``: +1 / 0 / -1
    """
    annual = harmonized_surface.resample(time="YS").mean(skipna=True)

    delta = annual.diff(dim="time")

    direction = xr.where(delta > 0, 1, xr.where(delta < 0, -1, 0)).astype(np.int8)

    ds = xr.Dataset(
        {
            "delta_fraction": delta,
            "change_direction": direction,
        }
    )
    ds.attrs["dataset_id"] = dataset_id
    ds.attrs["description"] = "Year-over-year wetland fraction change"
    return ds


def compute_regional_summary(
    trend_result: TrendResult,
    region_bboxes: Mapping[str, BBox],
) -> pd.DataFrame:
    """Compute regional summary statistics from a TrendResult.

    Parameters
    ----------
    trend_result:
        Output of compute_pixel_trends().
    region_bboxes:
        Dict mapping region slug to (west, south, east, north) BBox.

    Returns
    -------
    pd.DataFrame with one row per region (plus "global" row for full domain).
    Columns: region, total_valid_pixels, mean_slope, median_slope,
    fraction_significant, fraction_increasing, fraction_decreasing,
    fraction_stable.
    """
    rows: list[dict[str, object]] = []

    regions: dict[str, BBox | None] = {**dict(region_bboxes), "global": None}

    for region_slug, bbox in regions.items():
        slope = trend_result.sens_slope
        sig = trend_result.significant
        direction = trend_result.trend_direction

        if bbox is not None:
            west, south, east, north = bbox
            slope = slope.sel(
                lat=slice(north, south),
                lon=slice(west, east),
            )
            sig = sig.sel(
                lat=slice(north, south),
                lon=slice(west, east),
            )
            direction = direction.sel(
                lat=slice(north, south),
                lon=slice(west, east),
            )

        valid_mask = np.isfinite(slope.values)
        total = int(valid_mask.sum())
        if total == 0:
            continue

        rows.append(
            {
                "region": region_slug,
                "dataset_id": trend_result.dataset_id,
                "aggregation": trend_result.aggregation,
                "total_valid_pixels": total,
                "mean_slope": float(np.nanmean(slope.values)),
                "median_slope": float(np.nanmedian(slope.values)),
                "fraction_significant": float(sig.values[valid_mask].mean()),
                "fraction_increasing": float(
                    (direction.values[valid_mask] == 1).mean()
                ),
                "fraction_decreasing": float(
                    (direction.values[valid_mask] == -1).mean()
                ),
                "fraction_stable": float(
                    (direction.values[valid_mask] == 0).mean()
                ),
            }
        )

    return pd.DataFrame(rows)


def _trend_checkpoint_time_tokens(time_range: tuple[str, str]) -> tuple[str, str]:
    start_token = validate_stem_token(time_range[0], label="time_range_start").replace("-", "")
    end_token = validate_stem_token(time_range[1], label="time_range_end").replace("-", "")
    return (start_token, end_token)


def _parse_checkpoint_metadata_json(
    value: object,
    *,
    region_id: str,
    dataset_id: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "stage=trend-load "
            f"region_id={region_id} dataset_id={dataset_id} malformed checkpoint_metadata_json"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(
            "stage=trend-load "
            f"region_id={region_id} dataset_id={dataset_id} "
            "checkpoint_metadata_json must decode to an object"
        )
    return payload


def _parse_bbox_json(
    value: object,
    *,
    region_id: str,
    dataset_id: str,
) -> BBox:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "stage=trend-load "
            f"region_id={region_id} dataset_id={dataset_id} malformed bbox_json"
        ) from exc
    if not isinstance(payload, list) or len(payload) != 4:
        raise ValueError(
            "stage=trend-load "
            f"region_id={region_id} dataset_id={dataset_id} bbox_json must decode to a 4-item list"
        )
    bbox = tuple(float(item) for item in payload)
    west, south, east, north = bbox
    if west >= east or south >= north:
        raise ValueError(
            "stage=trend-load "
            f"region_id={region_id} dataset_id={dataset_id} invalid bbox_json bounds"
        )
    return cast(BBox, bbox)


def _write_dataset_atomic(path: Path, dataset: xr.Dataset) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        dataset.to_netcdf(temp_path)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pixel_mann_kendall(
    values: np.ndarray,
    alpha: float,
) -> tuple[float, float, float, float, float]:
    """Compute MK + Sen's slope for a single pixel time series.

    Returns
    -------
    (sens_slope, p_value, z_score, significant, direction)
    """
    # Remove NaNs
    finite = values[np.isfinite(values)]

    if len(finite) < 4:
        return (np.nan, 1.0, 0.0, 0.0, 0.0)

    if np.ptp(finite) == 0:
        # All values identical — no trend
        return (0.0, 1.0, 0.0, 0.0, 0.0)

    x = np.arange(len(finite), dtype=float)

    # Mann-Kendall via Kendall's tau
    tau, p_value = stats.kendalltau(x, finite, nan_policy="omit")
    if not np.isfinite(tau):
        return (np.nan, 1.0, 0.0, 0.0, 0.0)

    # Sen's slope via Theil-Sen estimator
    slope_val, _, _, _ = stats.theilslopes(finite, x)

    # Convert tau to approximate z-score
    if p_value <= 0.0:
        z_score = float(np.sign(tau) * 8.0)
    elif p_value >= 1.0:
        z_score = 0.0
    else:
        z_score = float(np.sign(tau) * stats.norm.isf(p_value / 2.0))

    significant = float(p_value < alpha)
    if significant and slope_val > 0:
        direction = 1.0
    elif significant and slope_val < 0:
        direction = -1.0
    else:
        direction = 0.0

    return (float(slope_val), float(p_value), z_score, significant, direction)


def _vectorized_mk_test(
    data: xr.DataArray,
    alpha: float,
    time_dim: str = "time",
) -> xr.Dataset:
    """Apply _pixel_mann_kendall across all pixels via xr.apply_ufunc."""

    # apply_ufunc expects the time dimension as core dim
    results = xr.apply_ufunc(
        _pixel_mann_kendall,
        data,
        kwargs={"alpha": alpha},
        input_core_dims=[[time_dim]],
        output_core_dims=[[], [], [], [], []],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[float, float, float, float, float],
    )

    slope_da, pval_da, zscore_da, sig_da, dir_da = results

    return xr.Dataset(
        {
            "sens_slope": slope_da,
            "p_value": pval_da,
            "z_score": zscore_da,
            "significant": sig_da.astype(bool),
            "trend_direction": dir_da.astype(np.int8),
        }
    )


def _aggregate_time_series(
    data: xr.DataArray,
    aggregation: AggregationLevel,
) -> xr.DataArray:
    """Aggregate time series to the specified level.

    For 'seasonal', groups by DJF/MAM/JJA/SON and returns a DataArray
    with dim 'season' (string labels).
    """
    if aggregation == "annual":
        return data.resample(time="YS").mean(skipna=True)

    elif aggregation == "seasonal":
        seasonal = data.groupby("time.season").mean(skipna=True)
        # Reorder to standard DJF/MAM/JJA/SON
        available = [s for s in _SEASON_ORDER if s in seasonal["season"].values]
        if available:
            seasonal = seasonal.sel(season=available)
        return seasonal

    elif aggregation == "monthly":
        return data.resample(time="MS").mean(skipna=True)

    else:
        raise ValueError(f"Unknown aggregation level: {aggregation!r}")


def _gwd30_pixel_stats_transform_for_aggregation(
    aggregation: Gwd30PixelStatsTransform,
):
    if aggregation == "native":
        return phase4_gwd30_pixel_statistics_native_tile
    if aggregation == "monthly":
        return phase4_gwd30_pixel_statistics_monthly_tile
    if aggregation == "annual":
        return phase4_gwd30_pixel_statistics_annual_tile
    raise ValueError(f"Unsupported GWD30 pixel statistics tile aggregation: {aggregation!r}")


def phase4_gwd30_pixel_statistics_native_tile(source: xr.Dataset) -> xr.Dataset:
    return _build_phase4_gwd30_pixel_statistics_tile(source, aggregation="native")


def phase4_gwd30_pixel_statistics_monthly_tile(source: xr.Dataset) -> xr.Dataset:
    return _build_phase4_gwd30_pixel_statistics_tile(source, aggregation="monthly")


def phase4_gwd30_pixel_statistics_annual_tile(source: xr.Dataset) -> xr.Dataset:
    return _build_phase4_gwd30_pixel_statistics_tile(source, aggregation="annual")


def _build_phase4_gwd30_pixel_statistics_tile(
    source: xr.Dataset,
    *,
    aggregation: Gwd30PixelStatsTransform,
) -> xr.Dataset:
    if "weighted" not in source.data_vars or "coverage" not in source.data_vars:
        raise ValueError("Expected staged GWD30 tile dataset with weighted and coverage variables")

    spatial_y, spatial_x = _resolve_spatial_dims(source["coverage"])
    wetland_fraction = _wetland_fraction_from_staged_tile(source)

    if aggregation == "native":
        series = wetland_fraction
    elif aggregation == "monthly":
        series = wetland_fraction.resample(time="MS").mean(skipna=True)
    elif aggregation == "annual":
        series = wetland_fraction.resample(time="YS").mean(skipna=True)
    else:
        raise ValueError(f"Unsupported GWD30 pixel statistics aggregation: {aggregation!r}")

    series = series.transpose("time", spatial_y, spatial_x).astype(np.float32)
    valid_observation_count = series.notnull().sum(dim="time").astype(np.int32)
    mean_fraction = series.mean(dim="time", skipna=True).astype(np.float32)
    std_fraction = series.std(dim="time", skipna=True).astype(np.float32)
    cell_area = _cell_area_grid_km2(series.isel(time=0, drop=True)).astype(np.float32)

    stats_tile = xr.Dataset(
        {
            "wetland_fraction": series,
            "valid_observation_count": valid_observation_count,
            "mean_wetland_fraction": mean_fraction,
            "std_wetland_fraction": std_fraction,
            "cell_area_km2": cell_area,
        },
        attrs={
            "dataset_id": "gwd30",
            "source": "phase4_gwd30_native_pixel_statistics",
            "aggregation": aggregation,
            "year": int(source.attrs.get("year", 0)),
        },
    )
    return stats_tile


def _wetland_fraction_from_staged_tile(source: xr.Dataset) -> xr.DataArray:
    spatial_y, spatial_x = _resolve_spatial_dims(source["coverage"])
    class_ids = np.asarray(source["weighted"].coords["class_id"].values, dtype=np.int16)
    wetland_ids = set(wetland_class_ids("gwd30", include_water=False))
    selected_indices = [
        index for index, class_id in enumerate(class_ids) if int(class_id) in wetland_ids
    ]
    coverage = source["coverage"].transpose("time", spatial_y, spatial_x).astype(np.float32)
    if selected_indices:
        wetland_weighted = (
            source["weighted"]
            .isel(class_id=selected_indices)
            .sum(dim="class_id")
            .transpose("time", spatial_y, spatial_x)
            .astype(np.float32)
        )
    else:
        wetland_weighted = xr.zeros_like(coverage).astype(np.float32)

    fraction = xr.where(coverage > 0, wetland_weighted / coverage, np.nan)
    fraction.name = "wetland_fraction"
    return fraction.astype(np.float32)


def _resolve_spatial_dims(data: xr.DataArray) -> tuple[str, str]:
    if "lat" in data.dims and "lon" in data.dims:
        return "lat", "lon"
    if "y" in data.dims and "x" in data.dims:
        return "y", "x"
    raise ValueError(f"Could not resolve spatial dims from {data.dims!r}")


def _cell_area_grid_km2(template: xr.DataArray) -> xr.DataArray:
    spatial_y, spatial_x = _resolve_spatial_dims(template)
    lat_values = np.asarray(template.coords[spatial_y].values, dtype=np.float64)
    lon_values = np.asarray(template.coords[spatial_x].values, dtype=np.float64)
    lat_edges = _coordinate_edges(lat_values)
    lon_edges = _coordinate_edges(lon_values)

    lat_lower = np.minimum(lat_edges[:-1], lat_edges[1:])
    lat_upper = np.maximum(lat_edges[:-1], lat_edges[1:])
    lon_lower = np.minimum(lon_edges[:-1], lon_edges[1:])
    lon_upper = np.maximum(lon_edges[:-1], lon_edges[1:])

    lat_term = np.sin(np.deg2rad(lat_upper)) - np.sin(np.deg2rad(lat_lower))
    lon_term = np.deg2rad(lon_upper - lon_lower)
    area = (6371.0088**2) * lat_term[:, None] * lon_term[None, :]
    area_da = xr.DataArray(
        area.astype(np.float64),
        dims=(spatial_y, spatial_x),
        coords={
            spatial_y: template.coords[spatial_y].values,
            spatial_x: template.coords[spatial_x].values,
        },
        name="cell_area_km2",
    )
    area_da = area_da.rio.set_spatial_dims(x_dim=spatial_x, y_dim=spatial_y, inplace=False)
    return cast(xr.DataArray, area_da.rio.write_crs("EPSG:4326", inplace=False))


def _coordinate_edges(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        raise ValueError("Cannot derive coordinate edges from an empty axis")
    if values.size == 1:
        center = float(values[0])
        return np.array([center - 0.5, center + 0.5], dtype=np.float64)

    mids = (values[:-1] + values[1:]) / 2.0
    edges = np.empty(values.size + 1, dtype=np.float64)
    edges[1:-1] = mids
    edges[0] = values[0] - (mids[0] - values[0])
    edges[-1] = values[-1] + (values[-1] - mids[-1])
    return edges


def _gwd30_years_for_time_range(
    dataset_config: Mapping[str, object],
    time_range: tuple[str, str] | None,
) -> list[int]:
    configured_years = sorted(int(year) for year in dataset_config.get("years", []))
    if not configured_years:
        raise ValueError("GWD30 config does not define any available years")
    if time_range is None:
        return configured_years

    start = pd.Timestamp(time_range[0])
    end = pd.Timestamp(time_range[1])
    return [
        year
        for year in configured_years
        if pd.Timestamp(f"{year}-12-31") >= start and pd.Timestamp(f"{year}-01-01") <= end
    ]
