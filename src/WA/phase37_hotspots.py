"""Phase 3.7 hotspot discovery from global 500 m disagreement outputs."""

from __future__ import annotations

import csv
import json
import logging
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
import yaml
from matplotlib.colors import ListedColormap
from matplotlib.patches import Rectangle
from scipy.ndimage import convolve as ndimage_convolve
from scipy.ndimage import maximum_filter as ndimage_maximum_filter

from WA.utils.progress import tqdm
from WA.visualization.phase37 import (
    DEFAULT_PHASE37_SAMPLE_STEP,
    DEFAULT_PHASE37_SOURCE_LAT_CHUNK_SIZE,
    ENTROPY_CMAP,
    write_phase37_global_plot_cache,
)

logger = logging.getLogger(__name__)

BBox = tuple[float, float, float, float]

DEFAULT_PHASE37_HOTSPOT_YEAR = 2016
DEFAULT_PHASE37_HOTSPOT_BUDGET = 20
DEFAULT_PHASE37_HOTSPOT_PERCENTILE = 95.0
DEFAULT_PHASE37_HOTSPOT_MIN_CLUSTER_CELLS = 16
DEFAULT_PHASE37_HOTSPOT_AOI_SIZE_DEG = 0.5
DEFAULT_PHASE37_HOTSPOT_MIN_DISTANCE_DEG = 0.5
DEFAULT_PHASE37_HOTSPOT_OUTPUT_DIR = Path("results/phase3.7_hotspots")
DEFAULT_PHASE37_HOTSPOT_REGIONS_FILE = Path("config/priority_regions.yaml")
DEFAULT_PHASE37_HOTSPOT_CACHE_DIR = Path("results/cache/phase3_7")
DEFAULT_PHASE37_HOTSPOT_DEBUG_MAX_DIM = 1500
DEFAULT_PHASE37_HOTSPOT_CANDIDATE_MULTIPLIER = 5
SELECTION_RULES_VERSION = "phase3.7-hotspots-v1"


@dataclass(frozen=True)
class Phase37PriorityRegion:
    """One priority region used for Phase 3.7 hotspot selection."""

    region_id: str
    label: str
    bbox: BBox
    priority: int
    area_weight: float


@dataclass(frozen=True)
class Phase37ClusterCandidate:
    """One coarse candidate AOI center inside a region."""

    center_lon: float
    center_lat: float
    mean_entropy: float
    max_entropy: float
    cell_count: int


@dataclass(frozen=True)
class Phase37Hotspot:
    """One selected Phase 3.7 hotspot AOI."""

    hotspot_id: str
    region_id: str
    region_slug: str
    region_label: str
    bbox: BBox
    center_lon: float
    center_lat: float
    mean_entropy: float
    max_entropy: float
    cell_count: int
    region_rank: int
    threshold_percentile: float
    threshold_value: float
    selection_rules_version: str = SELECTION_RULES_VERSION
    source: str = "entropy"
    class_disagreement_summary: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Phase37RegionSummary:
    """Region-level QC and accounting for hotspot selection."""

    region_id: str
    region_label: str
    bbox: BBox
    priority: int
    area_weight: float
    quota: int
    selected_count: int
    shortfall: int
    threshold_percentile: float
    threshold_value: float | None
    valid_wetland_cell_count: int
    candidate_window_count: int
    coarse_candidate_count: int
    refined_candidate_count: int
    status: str
    debug_png_path: Path


@dataclass(frozen=True)
class Phase37HotspotSelectionResult:
    """Outputs from one hotspot-selection run."""

    hotspots: list[Phase37Hotspot]
    region_summaries: list[Phase37RegionSummary]
    manifest_path: Path
    csv_path: Path
    region_csv_path: Path


def load_phase37_priority_regions(
    regions_file: str | Path = DEFAULT_PHASE37_HOTSPOT_REGIONS_FILE,
) -> list[Phase37PriorityRegion]:
    """Load Phase 3.7 priority regions from YAML."""

    path = Path(regions_file)
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    regions = document.get("regions")
    if not isinstance(regions, dict):
        raise ValueError("regions_file must contain a top-level 'regions' mapping")

    ordered: list[Phase37PriorityRegion] = []
    for region_id, payload in regions.items():
        if not isinstance(payload, dict):
            raise ValueError(f"Region {region_id!r} must be a mapping")
        bbox = payload.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"Region {region_id!r} must provide bbox as 4-item list")
        west, south, east, north = (float(value) for value in bbox)
        ordered.append(
            Phase37PriorityRegion(
                region_id=str(region_id),
                label=str(payload.get("label", region_id)),
                bbox=(west, south, east, north),
                priority=int(payload.get("priority", 9999)),
                area_weight=_bbox_area_weight((west, south, east, north)),
            )
        )

    ordered.sort(key=lambda region: (region.priority, region.region_id))
    return ordered


def allocate_phase37_region_quotas(
    regions: list[Phase37PriorityRegion],
    total_budget: int = DEFAULT_PHASE37_HOTSPOT_BUDGET,
) -> dict[str, int]:
    """Allocate hotspot quotas with min-1 and Hamilton largest remainder."""

    if total_budget <= 0:
        raise ValueError("total_budget must be positive")
    if not regions:
        return {}
    if total_budget < len(regions):
        raise ValueError("total_budget must be >= number of regions")

    base = {region.region_id: 1 for region in regions}
    remaining = total_budget - len(regions)
    if remaining == 0:
        return base

    total_area = sum(region.area_weight for region in regions)
    if total_area <= 0:
        total_area = float(len(regions))
        weights = {region.region_id: 1.0 for region in regions}
    else:
        weights = {region.region_id: region.area_weight for region in regions}

    floors: dict[str, int] = {}
    remainders: list[tuple[float, float, int, str]] = []
    assigned = 0
    for region in regions:
        raw_share = remaining * weights[region.region_id] / total_area
        floor_share = int(math.floor(raw_share))
        floors[region.region_id] = floor_share
        assigned += floor_share
        remainders.append(
            (
                raw_share - floor_share,
                region.area_weight,
                -region.priority,
                region.region_id,
            )
        )

    quotas = {
        region.region_id: base[region.region_id] + floors[region.region_id]
        for region in regions
    }
    leftovers = remaining - assigned
    for _remainder, _area_weight, _neg_priority, region_id in sorted(
        remainders,
        key=lambda item: (-item[0], -item[1], -item[2], item[3]),
    )[:leftovers]:
        quotas[region_id] += 1
    return quotas


def run_phase37_hotspot_selection(
    metrics_path: str | Path,
    classes_path: str | Path,
    *,
    output_dir: str | Path = DEFAULT_PHASE37_HOTSPOT_OUTPUT_DIR,
    regions_file: str | Path = DEFAULT_PHASE37_HOTSPOT_REGIONS_FILE,
    cache_dir: str | Path = DEFAULT_PHASE37_HOTSPOT_CACHE_DIR,
    cache_path: str | Path | None = None,
    selected_region_ids: list[str] | None = None,
    year: int = DEFAULT_PHASE37_HOTSPOT_YEAR,
    total_budget: int = DEFAULT_PHASE37_HOTSPOT_BUDGET,
    threshold_percentile: float = DEFAULT_PHASE37_HOTSPOT_PERCENTILE,
    min_cluster_cells: int = DEFAULT_PHASE37_HOTSPOT_MIN_CLUSTER_CELLS,
    aoi_size_deg: float = DEFAULT_PHASE37_HOTSPOT_AOI_SIZE_DEG,
    min_distance_deg: float = DEFAULT_PHASE37_HOTSPOT_MIN_DISTANCE_DEG,
    candidate_sample_step: int = DEFAULT_PHASE37_SAMPLE_STEP,
    source_lat_chunk_size: int = DEFAULT_PHASE37_SOURCE_LAT_CHUNK_SIZE,
    debug_max_dim: int = DEFAULT_PHASE37_HOTSPOT_DEBUG_MAX_DIM,
    write_debug_png: bool = True,
) -> Phase37HotspotSelectionResult:
    """Select Phase 3.7 hotspots and write manifest, CSV, and debug PNGs."""

    if not (0.0 <= threshold_percentile <= 100.0):
        raise ValueError("threshold_percentile must be within [0, 100]")
    if min_cluster_cells <= 0:
        raise ValueError("min_cluster_cells must be positive")
    if aoi_size_deg <= 0:
        raise ValueError("aoi_size_deg must be positive")
    if min_distance_deg < 0:
        raise ValueError("min_distance_deg must be non-negative")
    if candidate_sample_step <= 0:
        raise ValueError("candidate_sample_step must be positive")
    if source_lat_chunk_size <= 0:
        raise ValueError("source_lat_chunk_size must be positive")
    if debug_max_dim <= 0:
        raise ValueError("debug_max_dim must be positive")

    metrics_path = Path(metrics_path)
    classes_path = Path(classes_path)
    output_dir = Path(output_dir)
    cache_dir = Path(cache_dir)
    resolved_cache_path = (
        Path(cache_path)
        if cache_path is not None
        else default_phase37_hotspot_cache_path(
            cache_dir,
            year=year,
            sample_step=candidate_sample_step,
        )
    )
    _validate_phase37_hotspot_inputs(metrics_path, classes_path)

    regions = load_phase37_priority_regions(regions_file)
    if selected_region_ids:
        wanted = set(selected_region_ids)
        regions = [region for region in regions if region.region_id in wanted]
    if not regions:
        raise ValueError("No regions selected for Phase 3.7 hotspot search")

    quotas = allocate_phase37_region_quotas(regions, total_budget=total_budget)
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = output_dir / "debug"
    if write_debug_png:
        debug_dir.mkdir(parents=True, exist_ok=True)

    hotspots: list[Phase37Hotspot] = []
    region_summaries: list[Phase37RegionSummary] = []
    _ensure_phase37_candidate_cache(
        metrics_path,
        classes_path,
        cache_path=resolved_cache_path,
        sample_step=candidate_sample_step,
        source_lat_chunk_size=source_lat_chunk_size,
    )
    with xr.open_dataset(resolved_cache_path, decode_cf=True) as candidate_ds:
        candidate_metrics = candidate_ds[
            ["entropy", "majority_class", "joint_valid_mask"]
        ].load()
    region_progress = tqdm(
        regions,
        total=len(regions),
        desc="Phase3.7 hotspots",
        unit="region",
        dynamic_ncols=True,
    )

    with xr.open_dataset(metrics_path, decode_cf=True) as metrics:
        metrics_vars = metrics[["entropy", "majority_class", "joint_valid_mask"]]
        for region in region_progress:
            quota = quotas[region.region_id]
            region_progress.set_postfix_str(region.region_id, refresh=False)
            logger.info("Phase3.7 hotspot region start: %s quota=%s", region.region_id, quota)
            candidate_subset = _subset_spatial(candidate_metrics, region.bbox)
            summary, selected_hotspots = _select_hotspots_for_region(
                region,
                quota=quota,
                candidate_subset=candidate_subset,
                source_metrics=metrics_vars,
                threshold_percentile=threshold_percentile,
                min_cluster_cells=min_cluster_cells,
                aoi_size_deg=aoi_size_deg,
                min_distance_deg=min_distance_deg,
                debug_png_path=debug_dir / f"{region.region_id}.png",
                debug_max_dim=debug_max_dim,
                write_debug_png=write_debug_png,
            )
            region_summaries.append(summary)
            hotspots.extend(selected_hotspots)
            logger.info(
                "Phase3.7 hotspot region done: %s selected=%s/%s shortfall=%s status=%s",
                region.region_id,
                summary.selected_count,
                summary.quota,
                summary.shortfall,
                summary.status,
            )
    region_progress.close()

    manifest_path = output_dir / f"phase3_7_hotspots_{year}.json"
    csv_path = output_dir / f"phase3_7_hotspots_{year}.csv"
    region_csv_path = output_dir / f"phase3_7_hotspot_regions_{year}.csv"
    _write_phase37_hotspot_manifest(
        manifest_path,
        metrics_path=metrics_path,
        classes_path=classes_path,
        candidate_cache_path=resolved_cache_path,
        regions_file=Path(regions_file),
        year=year,
        total_budget=total_budget,
        threshold_percentile=threshold_percentile,
        min_cluster_cells=min_cluster_cells,
        aoi_size_deg=aoi_size_deg,
        min_distance_deg=min_distance_deg,
        candidate_sample_step=candidate_sample_step,
        hotspots=hotspots,
        region_summaries=region_summaries,
    )
    _write_phase37_hotspot_csv(csv_path, hotspots)
    _write_phase37_region_csv(region_csv_path, region_summaries)

    return Phase37HotspotSelectionResult(
        hotspots=hotspots,
        region_summaries=region_summaries,
        manifest_path=manifest_path,
        csv_path=csv_path,
        region_csv_path=region_csv_path,
    )


def _validate_phase37_hotspot_inputs(metrics_path: Path, classes_path: Path) -> None:
    with xr.open_dataset(metrics_path, decode_cf=True) as metrics, xr.open_dataset(
        classes_path,
        decode_cf=True,
    ) as classes:
        y_dim, x_dim = _spatial_dims(metrics["entropy"])
        if _spatial_dims(classes["g2017_dominant_class"]) != (y_dim, x_dim):
            raise ValueError("metrics and classes files do not share the same spatial dimensions")
        for dim in (y_dim, x_dim):
            metric_values = np.asarray(metrics.coords[dim].values)
            class_values = np.asarray(classes.coords[dim].values)
            if metric_values.shape != class_values.shape or not np.array_equal(
                metric_values,
                class_values,
            ):
                raise ValueError(f"metrics and classes coordinates differ on {dim}")


def _select_hotspots_for_region(
    region: Phase37PriorityRegion,
    *,
    quota: int,
    candidate_subset: xr.Dataset | None,
    source_metrics: xr.Dataset,
    threshold_percentile: float,
    min_cluster_cells: int,
    aoi_size_deg: float,
    min_distance_deg: float,
    debug_png_path: Path,
    debug_max_dim: int,
    write_debug_png: bool,
) -> tuple[Phase37RegionSummary, list[Phase37Hotspot]]:
    if candidate_subset is None:
        summary = Phase37RegionSummary(
            region_id=region.region_id,
            region_label=region.label,
            bbox=region.bbox,
            priority=region.priority,
            area_weight=region.area_weight,
            quota=quota,
            selected_count=0,
            shortfall=quota,
            threshold_percentile=threshold_percentile,
            threshold_value=None,
            valid_wetland_cell_count=0,
            candidate_window_count=0,
            coarse_candidate_count=0,
            refined_candidate_count=0,
            status="no_spatial_overlap",
            debug_png_path=debug_png_path,
        )
        if write_debug_png:
            _plot_phase37_region_debug(
                region=region,
                debug_surface=None,
                candidate_mask=None,
                selected_hotspots=[],
                threshold_value=None,
                quota=quota,
                output_path=debug_png_path,
                debug_max_dim=debug_max_dim,
                status=summary.status,
            )
        return summary, []

    loaded_candidate_subset = candidate_subset.load()
    valid_mask = _wetland_valid_mask(loaded_candidate_subset)
    coarse_scores, coarse_max, coarse_counts = _compute_coarse_window_scores(
        loaded_candidate_subset,
        valid_mask=valid_mask,
        aoi_size_deg=aoi_size_deg,
    )
    valid_values = coarse_scores[valid_mask & np.isfinite(coarse_scores)]

    if valid_values.size == 0:
        summary = Phase37RegionSummary(
            region_id=region.region_id,
            region_label=region.label,
            bbox=region.bbox,
            priority=region.priority,
            area_weight=region.area_weight,
            quota=quota,
            selected_count=0,
            shortfall=quota,
            threshold_percentile=threshold_percentile,
            threshold_value=None,
            valid_wetland_cell_count=0,
            candidate_window_count=0,
            coarse_candidate_count=0,
            refined_candidate_count=0,
            status="no_valid_wetland_cells",
            debug_png_path=debug_png_path,
        )
        if write_debug_png:
            _plot_phase37_region_debug(
                region=region,
                debug_surface=loaded_candidate_subset["entropy"],
                candidate_mask=np.zeros_like(valid_mask, dtype=bool),
                selected_hotspots=[],
                threshold_value=None,
                quota=quota,
                output_path=debug_png_path,
                debug_max_dim=debug_max_dim,
                status=summary.status,
            )
        return summary, []

    threshold_value = float(np.percentile(valid_values, threshold_percentile))
    candidate_mask = valid_mask & np.isfinite(coarse_scores) & (coarse_scores >= threshold_value)
    coarse_candidates = _build_coarse_candidates(
        loaded_candidate_subset,
        candidate_mask=candidate_mask,
        coarse_scores=coarse_scores,
        coarse_max=coarse_max,
        coarse_counts=coarse_counts,
        min_candidate_cells=min_cluster_cells,
    )
    coarse_selected = _select_cluster_candidates(
        coarse_candidates,
        quota=max(quota * DEFAULT_PHASE37_HOTSPOT_CANDIDATE_MULTIPLIER, quota),
        min_distance_deg=min_distance_deg,
    )
    refined_candidates = _refine_phase37_candidates(
        source_metrics,
        coarse_selected,
        aoi_size_deg=aoi_size_deg,
    )
    selected_candidates = _select_cluster_candidates(
        refined_candidates,
        quota=quota,
        min_distance_deg=min_distance_deg,
    )
    hotspots = [
        _build_phase37_hotspot(
            region,
            candidate,
            rank=index,
            threshold_percentile=threshold_percentile,
            threshold_value=threshold_value,
            aoi_size_deg=aoi_size_deg,
        )
        for index, candidate in enumerate(selected_candidates, start=1)
    ]
    status = "ok" if hotspots else "no_eligible_candidates"
    summary = Phase37RegionSummary(
        region_id=region.region_id,
        region_label=region.label,
        bbox=region.bbox,
        priority=region.priority,
        area_weight=region.area_weight,
        quota=quota,
        selected_count=len(hotspots),
        shortfall=max(quota - len(hotspots), 0),
        threshold_percentile=threshold_percentile,
        threshold_value=threshold_value,
        valid_wetland_cell_count=int(valid_mask.sum()),
        candidate_window_count=int(candidate_mask.sum()),
        coarse_candidate_count=len(coarse_candidates),
        refined_candidate_count=len(refined_candidates),
        status=status,
        debug_png_path=debug_png_path,
    )
    if write_debug_png:
        _plot_phase37_region_debug(
            region=region,
            debug_surface=_coarse_score_surface(loaded_candidate_subset, coarse_scores),
            candidate_mask=candidate_mask,
            selected_hotspots=hotspots,
            threshold_value=threshold_value,
            quota=quota,
            output_path=debug_png_path,
            debug_max_dim=debug_max_dim,
            status=status,
        )
    return summary, hotspots


def _build_coarse_candidates(
    candidate_subset: xr.Dataset,
    *,
    candidate_mask: np.ndarray,
    coarse_scores: np.ndarray,
    coarse_max: np.ndarray,
    coarse_counts: np.ndarray,
    min_candidate_cells: int,
) -> list[Phase37ClusterCandidate]:
    y_dim, x_dim = _spatial_dims(candidate_subset["entropy"])
    lat_values = np.asarray(candidate_subset.coords[y_dim].values, dtype=np.float64)
    lon_values = np.asarray(candidate_subset.coords[x_dim].values, dtype=np.float64)
    rows, cols = np.where(candidate_mask)
    candidates: list[Phase37ClusterCandidate] = []
    for row_index, col_index in zip(rows.tolist(), cols.tolist(), strict=True):
        cell_count = int(coarse_counts[row_index, col_index])
        if cell_count < min_candidate_cells:
            continue
        candidates.append(
            Phase37ClusterCandidate(
                center_lon=float(lon_values[col_index]),
                center_lat=float(lat_values[row_index]),
                mean_entropy=float(coarse_scores[row_index, col_index]),
                max_entropy=float(coarse_max[row_index, col_index]),
                cell_count=cell_count,
            )
        )
    return candidates


def _refine_phase37_candidates(
    source_metrics: xr.Dataset,
    coarse_candidates: list[Phase37ClusterCandidate],
    *,
    aoi_size_deg: float,
) -> list[Phase37ClusterCandidate]:
    refined: list[Phase37ClusterCandidate] = []
    candidate_progress = tqdm(
        coarse_candidates,
        total=len(coarse_candidates),
        desc="  refine AOIs",
        unit="aoi",
        dynamic_ncols=True,
    )
    for candidate in candidate_progress:
        candidate_progress.set_postfix_str(
            f"{candidate.center_lon:.2f},{candidate.center_lat:.2f}",
            refresh=False,
        )
        refined_candidate = _refine_phase37_candidate(
            source_metrics,
            candidate,
            aoi_size_deg=aoi_size_deg,
        )
        if refined_candidate is not None:
            refined.append(refined_candidate)
    candidate_progress.close()
    return refined


def _refine_phase37_candidate(
    source_metrics: xr.Dataset,
    candidate: Phase37ClusterCandidate,
    *,
    aoi_size_deg: float,
) -> Phase37ClusterCandidate | None:
    bbox = _build_hotspot_bbox(
        center_lon=candidate.center_lon,
        center_lat=candidate.center_lat,
        aoi_size_deg=aoi_size_deg,
    )
    subset = _subset_spatial(source_metrics, bbox)
    if subset is None:
        return None
    loaded_subset = subset.load()
    valid_mask = _wetland_valid_mask(loaded_subset)
    entropy = np.asarray(loaded_subset["entropy"].values, dtype=np.float32)
    valid_values = entropy[valid_mask]
    if valid_values.size == 0:
        return None
    return Phase37ClusterCandidate(
        center_lon=candidate.center_lon,
        center_lat=candidate.center_lat,
        mean_entropy=float(np.nanmean(valid_values)),
        max_entropy=float(np.nanmax(valid_values)),
        cell_count=int(valid_mask.sum()),
    )


def _select_cluster_candidates(
    candidates: list[Phase37ClusterCandidate],
    *,
    quota: int,
    min_distance_deg: float,
) -> list[Phase37ClusterCandidate]:
    selected: list[Phase37ClusterCandidate] = []
    ordered = sorted(
        candidates,
        key=lambda item: (
            -item.mean_entropy,
            -item.max_entropy,
            -item.cell_count,
            -item.center_lat,
            item.center_lon,
        ),
    )
    for candidate in ordered:
        if len(selected) >= quota:
            break
        if any(_center_distance(candidate, current) < min_distance_deg for current in selected):
            continue
        selected.append(candidate)
    return selected


def _build_phase37_hotspot(
    region: Phase37PriorityRegion,
    candidate: Phase37ClusterCandidate,
    *,
    rank: int,
    threshold_percentile: float,
    threshold_value: float,
    aoi_size_deg: float,
) -> Phase37Hotspot:
    return Phase37Hotspot(
        hotspot_id=f"entropy-{region.region_id}-{rank:03d}",
        region_id=region.region_id,
        region_slug=region.region_id,
        region_label=region.label,
        bbox=_build_hotspot_bbox(
            center_lon=candidate.center_lon,
            center_lat=candidate.center_lat,
            aoi_size_deg=aoi_size_deg,
        ),
        center_lon=candidate.center_lon,
        center_lat=candidate.center_lat,
        mean_entropy=candidate.mean_entropy,
        max_entropy=candidate.max_entropy,
        cell_count=candidate.cell_count,
        region_rank=rank,
        threshold_percentile=threshold_percentile,
        threshold_value=threshold_value,
    )


def _build_hotspot_bbox(*, center_lon: float, center_lat: float, aoi_size_deg: float) -> BBox:
    half = aoi_size_deg / 2.0
    return (
        max(-180.0, center_lon - half),
        max(-90.0, center_lat - half),
        min(180.0, center_lon + half),
        min(90.0, center_lat + half),
    )


def _center_distance(left: Phase37ClusterCandidate, right: Phase37ClusterCandidate) -> float:
    return math.hypot(left.center_lon - right.center_lon, left.center_lat - right.center_lat)


def _wetland_valid_mask(dataset: xr.Dataset) -> np.ndarray:
    entropy = np.asarray(dataset["entropy"].values, dtype=np.float32)
    joint_valid = np.asarray(dataset["joint_valid_mask"].values) > 0
    majority_class = np.asarray(dataset["majority_class"].values)
    return joint_valid & np.isfinite(entropy) & (majority_class != 0)


def _compute_coarse_window_scores(
    candidate_subset: xr.Dataset,
    *,
    valid_mask: np.ndarray,
    aoi_size_deg: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    entropy = np.asarray(candidate_subset["entropy"].values, dtype=np.float32)
    y_dim, x_dim = _spatial_dims(candidate_subset["entropy"])
    lat_values = np.asarray(candidate_subset.coords[y_dim].values, dtype=np.float64)
    lon_values = np.asarray(candidate_subset.coords[x_dim].values, dtype=np.float64)
    window_y = _window_size_from_coords(lat_values, aoi_size_deg)
    window_x = _window_size_from_coords(lon_values, aoi_size_deg)
    kernel = np.ones((window_y, window_x), dtype=np.float32)
    weighted = np.where(valid_mask, entropy, 0.0).astype(np.float32)
    counts = ndimage_convolve(
        valid_mask.astype(np.float32),
        kernel,
        mode="constant",
        cval=0.0,
    )
    totals = ndimage_convolve(weighted, kernel, mode="constant", cval=0.0)
    coarse_scores = np.where(counts > 0, totals / counts, np.nan).astype(np.float32)
    coarse_max = ndimage_maximum_filter(
        np.where(valid_mask, entropy, -np.inf),
        size=(window_y, window_x),
        mode="constant",
        cval=-np.inf,
    ).astype(np.float32)
    coarse_max = np.where(np.isfinite(coarse_max), coarse_max, np.nan).astype(np.float32)
    return coarse_scores, coarse_max, counts.astype(np.int32)


def _window_size_from_coords(values: np.ndarray, aoi_size_deg: float) -> int:
    step = _coord_step(values)
    half_cells = max(0, int(round((aoi_size_deg / 2.0) / step)))
    return max(1, half_cells * 2 + 1)


def _coarse_score_surface(candidate_subset: xr.Dataset, coarse_scores: np.ndarray) -> xr.DataArray:
    entropy_surface = candidate_subset["entropy"]
    y_dim, x_dim = _spatial_dims(entropy_surface)
    return xr.DataArray(
        coarse_scores.astype(np.float32),
        dims=(y_dim, x_dim),
        coords={
            y_dim: entropy_surface.coords[y_dim].values,
            x_dim: entropy_surface.coords[x_dim].values,
        },
        name="coarse_mean_entropy",
    )


def _ensure_phase37_candidate_cache(
    metrics_path: Path,
    classes_path: Path,
    *,
    cache_path: Path,
    sample_step: int,
    source_lat_chunk_size: int,
) -> None:
    if cache_path.is_file():
        logger.info("Phase3.7 hotspot candidate cache hit: %s", cache_path)
        return
    logger.info("Phase3.7 hotspot candidate cache miss: %s", cache_path)
    write_phase37_global_plot_cache(
        metrics_path,
        classes_path,
        cache_path=cache_path,
        sample_step=sample_step,
        source_lat_chunk_size=source_lat_chunk_size,
    )


def default_phase37_hotspot_cache_path(
    cache_dir: Path,
    *,
    year: int,
    sample_step: int,
) -> Path:
    return cache_dir / f"phase3_7_global_plot_cache_global_500m_{year}_sample{sample_step}.nc"


def _subset_spatial(
    data: xr.Dataset | xr.DataArray,
    bbox: BBox,
) -> xr.Dataset | xr.DataArray | None:
    west, south, east, north = bbox
    y_dim, x_dim = _spatial_dims(data)
    lon_values = np.asarray(data.coords[x_dim].values)
    lon_slice = slice(west, east) if lon_values[0] <= lon_values[-1] else slice(east, west)
    lon_subset = data.sel({x_dim: lon_slice})
    if lon_subset.sizes.get(x_dim, 0) == 0:
        return None

    lat_values = np.asarray(lon_subset.coords[y_dim].values)
    lat_slice = slice(south, north) if lat_values[0] <= lat_values[-1] else slice(north, south)
    subset = lon_subset.sel({y_dim: lat_slice})
    if subset.sizes.get(y_dim, 0) == 0 or subset.sizes.get(x_dim, 0) == 0:
        return None
    return subset


def _spatial_dims(data: xr.Dataset | xr.DataArray) -> tuple[str, str]:
    dims = set(data.dims)
    if {"lat", "lon"}.issubset(dims):
        return "lat", "lon"
    if {"y", "x"}.issubset(dims):
        return "y", "x"
    raise ValueError(f"Expected spatial dims lat/lon or y/x, got {sorted(dims)}")


def _bbox_area_weight(bbox: BBox) -> float:
    west, south, east, north = bbox
    return max(0.0, east - west) * max(0.0, north - south)


def _plot_phase37_region_debug(
    *,
    region: Phase37PriorityRegion,
    debug_surface: xr.DataArray | None,
    candidate_mask: np.ndarray | None,
    selected_hotspots: list[Phase37Hotspot],
    threshold_value: float | None,
    quota: int,
    output_path: Path,
    debug_max_dim: int,
    status: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10.5, 6.8))
    try:
        if debug_surface is None:
            ax.text(
                0.5,
                0.5,
                "No overlap with source grid",
                ha="center",
                va="center",
                fontsize=13,
                transform=ax.transAxes,
            )
            ax.set_axis_off()
        else:
            sampled_subset, sampled_mask = _sample_region_debug_inputs(
                debug_surface,
                candidate_mask,
                max_dim=debug_max_dim,
            )
            extent = _surface_extent(sampled_subset)
            origin = _surface_origin(sampled_subset)
            entropy_values = np.ma.masked_invalid(
                np.asarray(sampled_subset.values, dtype=np.float32)
            )
            image = ax.imshow(
                entropy_values,
                cmap=ENTROPY_CMAP,
                vmin=0.0,
                vmax=1.0,
                origin=origin,
                extent=extent,
                interpolation="nearest",
                rasterized=True,
            )
            overlay = np.ma.masked_where(~sampled_mask, sampled_mask.astype(np.int8))
            ax.imshow(
                overlay,
                cmap=ListedColormap([(0.0, 0.0, 0.0, 0.0), (0.0, 1.0, 1.0, 0.28)]),
                origin=origin,
                extent=extent,
                interpolation="nearest",
                vmin=0,
                vmax=1,
            )
            for hotspot in selected_hotspots:
                west, south, east, north = hotspot.bbox
                ax.add_patch(
                    Rectangle(
                        (west, south),
                        east - west,
                        north - south,
                        fill=False,
                        edgecolor="black",
                        linewidth=1.2,
                    )
                )
                ax.text(
                    west,
                    north,
                    f"{hotspot.region_rank}",
                    fontsize=9,
                    fontweight="bold",
                    ha="left",
                    va="bottom",
                    bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none", "pad": 1.5},
                )
            ax.set_xlim(region.bbox[0], region.bbox[2])
            ax.set_ylim(region.bbox[1], region.bbox[3])
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")
            ax.set_aspect("equal")
            colorbar = fig.colorbar(image, ax=ax, orientation="vertical", shrink=0.86)
            colorbar.set_label("Entropy")

        threshold_text = "n/a" if threshold_value is None else f"{threshold_value:.4f}"
        ax.set_title(
            f"{region.label} ({region.region_id})\n"
            f"status={status} quota={len(selected_hotspots)}/{quota} "
            f"threshold(p95)={threshold_text}",
            fontsize=11,
            fontweight="bold",
        )
        fig.tight_layout()
        fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)


def _sample_region_debug_inputs(
    debug_surface: xr.DataArray,
    candidate_mask: np.ndarray | None,
    *,
    max_dim: int,
) -> tuple[xr.DataArray, np.ndarray]:
    y_dim, x_dim = _spatial_dims(debug_surface)
    max_size = max(debug_surface.sizes[y_dim], debug_surface.sizes[x_dim])
    step = max(1, int(math.ceil(max_size / max_dim)))
    sampled_subset = debug_surface.isel(
        {
            y_dim: slice(None, None, step),
            x_dim: slice(None, None, step),
        }
    )
    if candidate_mask is None:
        sampled_mask = np.zeros(
            (sampled_subset.sizes[y_dim], sampled_subset.sizes[x_dim]),
            dtype=bool,
        )
    else:
        sampled_mask = candidate_mask[::step, ::step]
    return sampled_subset, sampled_mask


def _surface_extent(surface: xr.DataArray) -> BBox:
    y_dim, x_dim = _spatial_dims(surface)
    lon_values = np.asarray(surface.coords[x_dim].values, dtype=np.float64)
    lat_values = np.asarray(surface.coords[y_dim].values, dtype=np.float64)
    lon_step = _coord_step(lon_values)
    lat_step = _coord_step(lat_values)
    return (
        float(np.nanmin(lon_values) - lon_step / 2),
        float(np.nanmin(lat_values) - lat_step / 2),
        float(np.nanmax(lon_values) + lon_step / 2),
        float(np.nanmax(lat_values) + lat_step / 2),
    )


def _surface_origin(surface: xr.DataArray) -> str:
    y_dim, _x_dim = _spatial_dims(surface)
    lat_values = np.asarray(surface.coords[y_dim].values, dtype=np.float64)
    return "upper" if lat_values.size <= 1 or lat_values[0] > lat_values[-1] else "lower"


def _coord_step(values: np.ndarray) -> float:
    if values.size <= 1:
        return 1.0
    diffs = np.abs(np.diff(values))
    nonzero = diffs[diffs > 0]
    if nonzero.size == 0:
        return 1.0
    return float(nonzero[0])


def _write_phase37_hotspot_manifest(
    path: Path,
    *,
    metrics_path: Path,
    classes_path: Path,
    candidate_cache_path: Path,
    regions_file: Path,
    year: int,
    total_budget: int,
    threshold_percentile: float,
    min_cluster_cells: int,
    aoi_size_deg: float,
    min_distance_deg: float,
    candidate_sample_step: int,
    hotspots: list[Phase37Hotspot],
    region_summaries: list[Phase37RegionSummary],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status_counts = Counter(summary.status for summary in region_summaries)
    payload = {
        "phase": "phase3.7",
        "year": year,
        "selection_rules_version": SELECTION_RULES_VERSION,
        "metrics_path": str(metrics_path),
        "classes_path": str(classes_path),
        "candidate_cache_path": str(candidate_cache_path),
        "regions_file": str(regions_file),
        "total_hotspot_budget": total_budget,
        "hotspot_count": len(hotspots),
        "unfilled_budget": sum(summary.shortfall for summary in region_summaries),
        "threshold_percentile": threshold_percentile,
        "min_cluster_cells": min_cluster_cells,
        "aoi_size_deg": aoi_size_deg,
        "min_distance_deg": min_distance_deg,
        "candidate_sample_step": candidate_sample_step,
        "status_counts": dict(status_counts),
        "region_summaries": [_region_summary_record(summary) for summary in region_summaries],
        "hotspots": [_hotspot_record(hotspot) for hotspot in hotspots],
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _write_phase37_hotspot_csv(path: Path, hotspots: list[Phase37Hotspot]) -> None:
    fieldnames = [
        "hotspot_id",
        "region_id",
        "region_slug",
        "region_label",
        "bbox",
        "center_lon",
        "center_lat",
        "mean_entropy",
        "max_entropy",
        "cell_count",
        "region_rank",
        "threshold_percentile",
        "threshold_value",
        "selection_rules_version",
        "source",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for hotspot in hotspots:
            writer.writerow(
                {
                    "hotspot_id": hotspot.hotspot_id,
                    "region_id": hotspot.region_id,
                    "region_slug": hotspot.region_slug,
                    "region_label": hotspot.region_label,
                    "bbox": json.dumps(list(hotspot.bbox)),
                    "center_lon": hotspot.center_lon,
                    "center_lat": hotspot.center_lat,
                    "mean_entropy": hotspot.mean_entropy,
                    "max_entropy": hotspot.max_entropy,
                    "cell_count": hotspot.cell_count,
                    "region_rank": hotspot.region_rank,
                    "threshold_percentile": hotspot.threshold_percentile,
                    "threshold_value": hotspot.threshold_value,
                    "selection_rules_version": hotspot.selection_rules_version,
                    "source": hotspot.source,
                }
            )


def _write_phase37_region_csv(path: Path, region_summaries: list[Phase37RegionSummary]) -> None:
    fieldnames = [
        "region_id",
        "region_label",
        "bbox",
        "priority",
        "area_weight",
        "quota",
        "selected_count",
        "shortfall",
        "threshold_percentile",
        "threshold_value",
        "valid_wetland_cell_count",
        "candidate_window_count",
        "coarse_candidate_count",
        "refined_candidate_count",
        "status",
        "debug_png_path",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for summary in region_summaries:
            writer.writerow(
                {
                    "region_id": summary.region_id,
                    "region_label": summary.region_label,
                    "bbox": json.dumps(list(summary.bbox)),
                    "priority": summary.priority,
                    "area_weight": summary.area_weight,
                    "quota": summary.quota,
                    "selected_count": summary.selected_count,
                    "shortfall": summary.shortfall,
                    "threshold_percentile": summary.threshold_percentile,
                    "threshold_value": summary.threshold_value,
                    "valid_wetland_cell_count": summary.valid_wetland_cell_count,
                    "candidate_window_count": summary.candidate_window_count,
                    "coarse_candidate_count": summary.coarse_candidate_count,
                    "refined_candidate_count": summary.refined_candidate_count,
                    "status": summary.status,
                    "debug_png_path": str(summary.debug_png_path),
                }
            )


def _hotspot_record(hotspot: Phase37Hotspot) -> dict[str, object]:
    record = asdict(hotspot)
    record["bbox"] = list(hotspot.bbox)
    return record


def _region_summary_record(summary: Phase37RegionSummary) -> dict[str, object]:
    return {
        "region_id": summary.region_id,
        "region_label": summary.region_label,
        "bbox": list(summary.bbox),
        "priority": summary.priority,
        "area_weight": summary.area_weight,
        "quota": summary.quota,
        "selected_count": summary.selected_count,
        "shortfall": summary.shortfall,
        "threshold_percentile": summary.threshold_percentile,
        "threshold_value": summary.threshold_value,
        "valid_wetland_cell_count": summary.valid_wetland_cell_count,
        "candidate_window_count": summary.candidate_window_count,
        "coarse_candidate_count": summary.coarse_candidate_count,
        "refined_candidate_count": summary.refined_candidate_count,
        "status": summary.status,
        "debug_png_path": str(summary.debug_png_path),
    }
