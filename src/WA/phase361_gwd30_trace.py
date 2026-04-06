"""Phase 3.6.1 diagnostics for tracing GWD30 hotspot anomalies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rioxarray  # noqa: F401
import xarray as xr

from WA.classification import unified_class_ids, unified_class_names
from WA.comparison.phase36 import (
    _stage_cache_paths,
    aggregate_source_fractions_to_unified,
    compute_dominant_class,
    compute_gwd30_annual_dominant_class,
    compute_valid_mask,
)
from WA.config import get_dataset_config
from WA.loaders import get_loader
from WA.loaders.base import BBox
from WA.loaders.gwd30 import _extract_tile_code
from WA.standardize import _load_gwd30_staged_tiles_from_stage_shard_manifests


@dataclass(frozen=True)
class Phase361Hotspot:
    """One hotspot selected for GWD30 upstream/downstream tracing."""

    hotspot_id: str
    bbox: BBox
    region_id: str | None = None
    region_label: str | None = None
    region_rank: int | None = None


def load_phase361_hotspots_manifest(path: Path) -> list[Phase361Hotspot]:
    """Load hotspot metadata from a Phase 3.7 hotspot manifest."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_hotspots = payload.get("hotspots", [])
    if not isinstance(raw_hotspots, list):
        raise ValueError("hotspots manifest must contain a 'hotspots' list")

    hotspots: list[Phase361Hotspot] = []
    for row in raw_hotspots:
        if not isinstance(row, dict):
            continue
        hotspot_id = str(row.get("hotspot_id", "")).strip()
        bbox_raw = row.get("bbox")
        if not hotspot_id or not isinstance(bbox_raw, list) or len(bbox_raw) != 4:
            continue
        hotspots.append(
            Phase361Hotspot(
                hotspot_id=hotspot_id,
                bbox=(
                    float(bbox_raw[0]),
                    float(bbox_raw[1]),
                    float(bbox_raw[2]),
                    float(bbox_raw[3]),
                ),
                region_id=_optional_string(row.get("region_slug")),
                region_label=_optional_string(row.get("region_label")),
                region_rank=_optional_int(row.get("region_rank")),
            )
        )
    return hotspots


def select_phase361_hotspots(
    hotspots: list[Phase361Hotspot],
    *,
    hotspot_ids: list[str] | None = None,
    limit: int | None = None,
) -> list[Phase361Hotspot]:
    """Select hotspots in manifest order or by explicit id order."""

    if hotspot_ids:
        by_id = {hotspot.hotspot_id: hotspot for hotspot in hotspots}
        selected: list[Phase361Hotspot] = []
        missing: list[str] = []
        for hotspot_id in hotspot_ids:
            hotspot = by_id.get(hotspot_id)
            if hotspot is None:
                missing.append(hotspot_id)
                continue
            selected.append(hotspot)
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"Requested hotspot id(s) not found in manifest: {missing_text}")
        return selected

    if limit is None:
        return list(hotspots)
    if limit <= 0:
        raise ValueError("limit must be positive when provided")
    return hotspots[:limit]


def run_phase361_hotspot_trace(
    *,
    hotspots_manifest: Path,
    standardized_dir: Path,
    phase36_output_dir: Path,
    phase36_cache_dir: Path,
    output_dir: Path,
    year: int,
    lat_chunk_size: int,
    hotspot_ids: list[str] | None = None,
    limit: int | None = None,
    cache_bbox: BBox | None = None,
    worker_count: int | None = 1,
) -> Path:
    """Trace selected hotspots across raw, staged, reduced, and final Phase 3.6 outputs."""

    hotspots = select_phase361_hotspots(
        load_phase361_hotspots_manifest(hotspots_manifest),
        hotspot_ids=hotspot_ids,
        limit=limit,
    )
    if not hotspots:
        raise ValueError("No hotspot was selected for Phase 3.6.1 tracing")

    metrics_path = phase36_output_dir / f"phase3_6_entropy_global_500m_{year}.nc"
    classes_path = phase36_output_dir / f"phase3_6_unified_classes_global_500m_{year}.nc"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"Phase 3.6 metrics file not found: {metrics_path}")
    if not classes_path.is_file():
        raise FileNotFoundError(f"Phase 3.6 classes file not found: {classes_path}")

    staged_root = standardized_dir / "_staging" / f"gwd30_{year}"
    staged_tiles = _load_gwd30_staged_tiles_from_stage_shard_manifests(staged_root)
    if not staged_tiles:
        raise FileNotFoundError(
            f"No staged GWD30 tile manifests were found under {staged_root}"
        )

    stage_paths = _stage_cache_paths(
        phase36_cache_dir,
        year=year,
        bbox=cache_bbox,
        lat_chunk_size=lat_chunk_size,
    )
    reduced_dir = stage_paths["gwd30_reduced_dir"]
    if not reduced_dir.is_dir():
        raise FileNotFoundError(f"Reduced GWD30 tile directory not found: {reduced_dir}")

    dataset_config = get_dataset_config("gwd30")
    loader = get_loader("gwd30", dataset_config)

    output_dir.mkdir(parents=True, exist_ok=True)
    combined: dict[str, Any] = {
        "phase": "phase3.6.1",
        "year": int(year),
        "hotspots_manifest": str(hotspots_manifest),
        "standardized_dir": str(standardized_dir),
        "phase36_output_dir": str(phase36_output_dir),
        "phase36_cache_dir": str(phase36_cache_dir),
        "lat_chunk_size": int(lat_chunk_size),
        "selected_hotspot_ids": [hotspot.hotspot_id for hotspot in hotspots],
        "hotspots": [],
    }

    with (
        xr.open_dataset(metrics_path, decode_cf=True) as metrics_dataset,
        xr.open_dataset(classes_path, decode_cf=True) as classes_dataset,
    ):
        for hotspot in hotspots:
            trace = trace_one_phase361_hotspot(
                hotspot,
                loader=loader,
                staged_tiles=staged_tiles,
                reduced_dir=reduced_dir,
                metrics_dataset=metrics_dataset,
                classes_dataset=classes_dataset,
                year=year,
                worker_count=worker_count,
            )
            hotspot_path = output_dir / f"{hotspot.hotspot_id}_gwd30_trace.json"
            hotspot_path.write_text(
                json.dumps(trace, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            combined["hotspots"].append(trace)

    combined_path = output_dir / f"phase3_6_1_gwd30_hotspot_traces_{year}.json"
    combined_path.write_text(json.dumps(combined, indent=2, sort_keys=True), encoding="utf-8")
    return combined_path


def run_phase361_hotspot_file_listing(
    *,
    hotspots_manifest: Path,
    standardized_dir: Path,
    phase36_cache_dir: Path,
    output_dir: Path,
    year: int,
    lat_chunk_size: int,
    hotspot_ids: list[str] | None = None,
    limit: int | None = None,
    cache_bbox: BBox | None = None,
) -> Path:
    """List only raw/staged/reduced file paths for selected hotspots."""

    hotspots = select_phase361_hotspots(
        load_phase361_hotspots_manifest(hotspots_manifest),
        hotspot_ids=hotspot_ids,
        limit=limit,
    )
    if not hotspots:
        raise ValueError("No hotspot was selected for Phase 3.6.1 file listing")

    staged_root = standardized_dir / "_staging" / f"gwd30_{year}"
    staged_tiles = _load_gwd30_staged_tiles_from_stage_shard_manifests(staged_root)
    if not staged_tiles:
        raise FileNotFoundError(
            f"No staged GWD30 tile manifests were found under {staged_root}"
        )

    stage_paths = _stage_cache_paths(
        phase36_cache_dir,
        year=year,
        bbox=cache_bbox,
        lat_chunk_size=lat_chunk_size,
    )
    reduced_dir = stage_paths["gwd30_reduced_dir"]
    if not reduced_dir.is_dir():
        raise FileNotFoundError(f"Reduced GWD30 tile directory not found: {reduced_dir}")

    dataset_config = get_dataset_config("gwd30")
    loader = get_loader("gwd30", dataset_config)

    output_dir.mkdir(parents=True, exist_ok=True)
    combined: dict[str, Any] = {
        "phase": "phase3.6.1",
        "mode": "file_listing",
        "year": int(year),
        "hotspots_manifest": str(hotspots_manifest),
        "standardized_dir": str(standardized_dir),
        "phase36_cache_dir": str(phase36_cache_dir),
        "lat_chunk_size": int(lat_chunk_size),
        "selected_hotspot_ids": [hotspot.hotspot_id for hotspot in hotspots],
        "hotspots": [],
    }

    for hotspot in hotspots:
        listing = build_phase361_hotspot_file_listing(
            hotspot,
            loader=loader,
            staged_tiles=staged_tiles,
            reduced_dir=reduced_dir,
            year=year,
        )
        hotspot_path = output_dir / f"{hotspot.hotspot_id}_gwd30_files.json"
        hotspot_path.write_text(
            json.dumps(listing, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        combined["hotspots"].append(listing)

    combined_path = output_dir / f"phase3_6_1_gwd30_hotspot_files_{year}.json"
    combined_path.write_text(json.dumps(combined, indent=2, sort_keys=True), encoding="utf-8")
    return combined_path


def trace_one_phase361_hotspot(
    hotspot: Phase361Hotspot,
    *,
    loader: Any,
    staged_tiles: list[tuple[Path, BBox]],
    reduced_dir: Path,
    metrics_dataset: xr.Dataset,
    classes_dataset: xr.Dataset,
    year: int,
    worker_count: int | None,
) -> dict[str, Any]:
    """Trace one hotspot across raw, staged, reduced, and final Phase 3.6 outputs."""

    reference_grid = subset_phase36_reference_grid(metrics_dataset["entropy"], hotspot.bbox)
    final_metrics_subset = subset_dataset_to_bbox(
        metrics_dataset[["entropy", "majority_class", "agreement_count", "joint_valid_mask"]],
        hotspot.bbox,
    ).load()
    final_classes_subset = subset_dataset_to_bbox(
        classes_dataset[
            [
                "g2017_dominant_class",
                "glwd_v2_dominant_class",
                "gwd30_dominant_class",
            ]
        ],
        hotspot.bbox,
    ).load()

    raw_tile_entries = discover_raw_tiles(loader, bbox=hotspot.bbox, year=year)
    raw_dataset = loader.load_time_fraction_grid(
        bbox=hotspot.bbox,
        reference_grid=reference_grid,
        year=year,
        worker_count=worker_count,
        show_progress=False,
    )
    try:
        raw_summary = summarize_pathway_from_source_dataset(raw_dataset)
    finally:
        raw_dataset.close()

    staged_entries = describe_tile_list(intersecting_tiles(staged_tiles, hotspot.bbox))
    staged_dataset = loader.merge_staged_time_fraction_tiles(
        staged_tiles=staged_tiles,
        reference_grid=reference_grid,
        bbox=hotspot.bbox,
        year=year,
    )
    try:
        staged_summary = summarize_pathway_from_source_dataset(staged_dataset)
    finally:
        staged_dataset.close()

    reduced_tiles = intersecting_reduced_tiles(
        reduced_dir=reduced_dir,
        staged_tiles=staged_tiles,
        bbox=hotspot.bbox,
    )
    reduced_unified = reconstruct_reduced_tiles_to_unified_fraction(
        reduced_tiles=reduced_tiles,
        reference_grid=reference_grid,
    )
    reduced_summary = summarize_unified_pathway(reduced_unified)

    final_gwd30 = final_classes_subset["gwd30_dominant_class"]
    final_joint_valid = (final_metrics_subset["joint_valid_mask"] > 0).astype(bool)
    final_summary = {
        "joint_valid_cells": int(np.asarray(final_joint_valid.values, dtype=bool).sum()),
        "gwd30_dominant": summarize_dominant_classes(final_gwd30),
        "majority_class": summarize_dominant_classes(final_metrics_subset["majority_class"]),
        "agreement_count": summarize_small_integer_surface(final_metrics_subset["agreement_count"]),
        "entropy": summarize_continuous_surface(final_metrics_subset["entropy"]),
    }

    result = {
        "hotspot_id": hotspot.hotspot_id,
        "bbox": [float(value) for value in hotspot.bbox],
        "region_id": hotspot.region_id,
        "region_label": hotspot.region_label,
        "region_rank": hotspot.region_rank,
        "grid_shape": {
            "lat": int(reference_grid.sizes["lat"]),
            "lon": int(reference_grid.sizes["lon"]),
        },
        "raw_tiles": raw_tile_entries,
        "staged_tiles": staged_entries,
        "reduced_tiles": describe_tile_list(reduced_tiles),
        "raw_path": raw_summary,
        "staged_path": staged_summary,
        "reduced_path": reduced_summary,
        "final_phase36_subset": final_summary,
        "comparisons": {
            "raw_vs_staged_unified": compare_unified_fraction_cubes(
                raw_summary["unified_fraction_dataarray"],
                staged_summary["unified_fraction_dataarray"],
            ),
            "staged_vs_reduced_unified": compare_unified_fraction_cubes(
                staged_summary["unified_fraction_dataarray"],
                reduced_summary["unified_fraction_dataarray"],
            ),
            "raw_old_vs_new_dominant": compare_dominant_classes(
                raw_summary["old_dominant_dataarray"],
                raw_summary["new_dominant_dataarray"],
            ),
            "staged_old_vs_new_dominant": compare_dominant_classes(
                staged_summary["old_dominant_dataarray"],
                staged_summary["new_dominant_dataarray"],
            ),
            "reduced_old_vs_new_dominant": compare_dominant_classes(
                reduced_summary["old_dominant_dataarray"],
                reduced_summary["new_dominant_dataarray"],
            ),
            "reduced_new_vs_final_gwd30": compare_dominant_classes(
                reduced_summary["new_dominant_dataarray"],
                final_gwd30,
            ),
        },
    }
    _strip_internal_dataarrays(result)
    return result


def build_phase361_hotspot_file_listing(
    hotspot: Phase361Hotspot,
    *,
    loader: Any,
    staged_tiles: list[tuple[Path, BBox]],
    reduced_dir: Path,
    year: int,
) -> dict[str, Any]:
    """Build a raw/staged/reduced file-path listing for one hotspot."""

    raw_tiles = discover_raw_tiles(loader, bbox=hotspot.bbox, year=year)
    staged_subset = intersecting_tiles(staged_tiles, hotspot.bbox)
    reduced_subset = intersecting_reduced_tiles(
        reduced_dir=reduced_dir,
        staged_tiles=staged_tiles,
        bbox=hotspot.bbox,
    )
    return {
        "hotspot_id": hotspot.hotspot_id,
        "bbox": [float(value) for value in hotspot.bbox],
        "region_id": hotspot.region_id,
        "region_label": hotspot.region_label,
        "region_rank": hotspot.region_rank,
        "raw_tiles": raw_tiles,
        "staged_tiles": describe_tile_list(staged_subset),
        "reduced_tiles": describe_tile_list(reduced_subset),
    }


def summarize_pathway_from_source_dataset(dataset: xr.Dataset) -> dict[str, Any]:
    """Build unified-fraction and dominant summaries from a raw or staged source dataset."""

    unified = aggregate_source_fractions_to_unified("gwd30", dataset).load()
    return summarize_unified_pathway(unified)


def summarize_unified_pathway(unified: xr.DataArray) -> dict[str, Any]:
    """Summarize one annual unified fraction cube plus old/new dominant outputs."""

    valid_mask = compute_valid_mask(unified)
    old_dominant = compute_dominant_class(unified, valid_mask=valid_mask)
    new_dominant = compute_gwd30_annual_dominant_class(unified, valid_mask=valid_mask)
    return {
        "valid_cells": int(np.asarray(valid_mask.values, dtype=bool).sum()),
        "fraction_summary": summarize_unified_fraction(unified, valid_mask=valid_mask),
        "old_dominant": summarize_dominant_classes(old_dominant),
        "new_dominant": summarize_dominant_classes(new_dominant),
        "unified_fraction_dataarray": unified,
        "old_dominant_dataarray": old_dominant,
        "new_dominant_dataarray": new_dominant,
    }


def subset_phase36_reference_grid(source: xr.DataArray, bbox: BBox) -> xr.DataArray:
    """Build a CRS-aware reference grid aligned to one Phase 3.6 hotspot subset."""

    subset = subset_dataset_to_bbox(source.to_dataset(name="source"), bbox)["source"]
    y_dim, x_dim = _spatial_dims(subset)
    grid = xr.DataArray(
        np.zeros((subset.sizes[y_dim], subset.sizes[x_dim]), dtype=np.float32),
        dims=(y_dim, x_dim),
        coords={
            y_dim: subset.coords[y_dim].values,
            x_dim: subset.coords[x_dim].values,
        },
        name="comparison_grid",
    )
    if subset.sizes[x_dim] > 1:
        grid.attrs["comparison_resolution_deg"] = float(
            abs(subset.coords[x_dim].values[1] - subset.coords[x_dim].values[0])
        )
    grid = grid.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=False)
    return grid.rio.write_crs("EPSG:4326", inplace=False)


def subset_dataset_to_bbox(dataset: xr.Dataset, bbox: BBox) -> xr.Dataset:
    """Subset a Phase 3.6 dataset to one hotspot bbox."""

    west, south, east, north = bbox
    y_dim, x_dim = _spatial_dims(dataset)

    lon_values = np.asarray(dataset.coords[x_dim].values)
    lon_slice = slice(west, east) if lon_values[0] <= lon_values[-1] else slice(east, west)
    subset = dataset.sel({x_dim: lon_slice})
    if subset.sizes.get(x_dim, 0) == 0:
        raise ValueError(f"BBox {bbox!r} produced empty lon selection")

    lat_values = np.asarray(subset.coords[y_dim].values)
    lat_slice = slice(south, north) if lat_values[0] <= lat_values[-1] else slice(north, south)
    subset = subset.sel({y_dim: lat_slice})
    if subset.sizes.get(y_dim, 0) == 0 or subset.sizes.get(x_dim, 0) == 0:
        raise ValueError(f"BBox {bbox!r} produced empty lat/lon selection")
    return subset


def discover_raw_tiles(loader: Any, *, bbox: BBox, year: int) -> dict[str, Any]:
    """Describe raw GWD30 source tiles intersecting one hotspot bbox."""

    time_range = (f"{year}-01-01", f"{year}-12-31")
    tiles_by_year = loader._discover_tiles(bbox=bbox, time_range=time_range)
    paths = list(tiles_by_year.get(year, []))
    items: list[dict[str, Any]] = []
    for path in paths:
        tile_code = _extract_tile_code(path)
        tile_bbox = (
            loader._tile_bbox(tile_code)
            if tile_code is not None
            else loader._tile_bounds_for_stage(path)
        )
        items.append(
            {
                "path": str(path),
                "tile_code": tile_code,
                "bbox": [float(value) for value in tile_bbox] if tile_bbox is not None else None,
            }
        )
    return {"count": len(items), "tiles": items}


def intersecting_tiles(
    tiles: list[tuple[Path, BBox]],
    bbox: BBox,
) -> list[tuple[Path, BBox]]:
    """Return staged/reduced tiles whose coarse bbox intersects one hotspot bbox."""

    return [item for item in tiles if _bbox_intersects(item[1], bbox)]


def intersecting_reduced_tiles(
    *,
    reduced_dir: Path,
    staged_tiles: list[tuple[Path, BBox]],
    bbox: BBox,
) -> list[tuple[Path, BBox]]:
    """Map reduced tile paths back onto staged tile bbox metadata."""

    staged_bbox_by_name = {path.name: stage_bbox for path, stage_bbox in staged_tiles}
    reduced_tiles: list[tuple[Path, BBox]] = []
    for path in sorted(reduced_dir.glob("tile_*.nc")):
        stage_bbox = staged_bbox_by_name.get(path.name)
        if stage_bbox is None or not _bbox_intersects(stage_bbox, bbox):
            continue
        reduced_tiles.append((path, stage_bbox))
    return reduced_tiles


def reconstruct_reduced_tiles_to_unified_fraction(
    *,
    reduced_tiles: list[tuple[Path, BBox]],
    reference_grid: xr.DataArray,
) -> xr.DataArray:
    """Rebuild one hotspot's annual unified fraction cube from reduced tiles."""

    if not reduced_tiles:
        raise FileNotFoundError("No reduced tiles intersect the requested hotspot bbox")

    y_dim, x_dim = _spatial_dims(reference_grid)
    y_values = np.asarray(reference_grid.coords[y_dim].values)
    x_values = np.asarray(reference_grid.coords[x_dim].values)
    class_ids = np.asarray(unified_class_ids(), dtype=np.int16)
    weighted_sum = np.zeros((len(class_ids), len(y_values), len(x_values)), dtype=np.float32)
    coverage_sum = np.zeros((len(y_values), len(x_values)), dtype=np.float32)

    for tile_path, _tile_bbox in reduced_tiles:
        with xr.open_dataset(tile_path, engine="netcdf4") as source:
            weighted = source["annual_unified_weighted_sum"].reindex(
                {"class_id": class_ids, y_dim: y_values, x_dim: x_values},
                fill_value=0.0,
            ).transpose("class_id", y_dim, x_dim)
            coverage = source["annual_coverage_sum"].reindex(
                {y_dim: y_values, x_dim: x_values},
                fill_value=0.0,
            ).transpose(y_dim, x_dim)
            weighted_sum += np.asarray(weighted.values, dtype=np.float32)
            coverage_sum += np.asarray(coverage.values, dtype=np.float32)

    fractions = np.full_like(weighted_sum, np.nan, dtype=np.float32)
    np.divide(
        weighted_sum,
        coverage_sum[None, :, :],
        out=fractions,
        where=coverage_sum[None, :, :] > 0,
    )
    np.clip(fractions, 0.0, 1.0, out=fractions)
    return xr.DataArray(
        fractions,
        dims=("class_id", y_dim, x_dim),
        coords={
            "class_id": class_ids,
            y_dim: y_values,
            x_dim: x_values,
        },
        name="unified_fraction",
    )


def describe_tile_list(tiles: list[tuple[Path, BBox]]) -> dict[str, Any]:
    """Convert a tile list into JSON-friendly metadata."""

    return {
        "count": len(tiles),
        "tiles": [
            {
                "path": str(path),
                "bbox": [float(value) for value in bbox],
            }
            for path, bbox in tiles
        ],
    }


def summarize_unified_fraction(
    unified: xr.DataArray,
    *,
    valid_mask: xr.DataArray,
) -> dict[str, Any]:
    """Summarize annual unified fractions over one hotspot AOI."""

    valid = np.asarray(valid_mask.values, dtype=bool)
    summary: dict[str, Any] = {
        "class_names": {str(class_id): name for class_id, name in unified_class_names().items()},
        "classes": {},
    }
    for class_id in np.asarray(unified.coords["class_id"].values, dtype=np.int16):
        plane = np.asarray(unified.sel(class_id=int(class_id)).values, dtype=np.float32)
        finite_valid = np.isfinite(plane) & valid
        if np.any(finite_valid):
            values = plane[finite_valid]
            positive = values > 0.0
            summary["classes"][str(int(class_id))] = {
                "mean_fraction": float(np.mean(values)),
                "max_fraction": float(np.max(values)),
                "positive_cells": int(np.sum(positive)),
                "positive_fraction": float(np.sum(positive) / np.sum(valid)),
            }
        else:
            summary["classes"][str(int(class_id))] = {
                "mean_fraction": 0.0,
                "max_fraction": 0.0,
                "positive_cells": 0,
                "positive_fraction": 0.0,
            }
    return summary


def summarize_dominant_classes(dominant: xr.DataArray) -> dict[str, Any]:
    """Summarize dominant-class counts over one hotspot AOI."""

    values = np.asarray(dominant.values, dtype=np.int16)
    valid = values >= 0
    valid_values = values[valid]
    counts: dict[str, int] = {}
    fractions: dict[str, float] = {}
    if valid_values.size > 0:
        unique, unique_counts = np.unique(valid_values, return_counts=True)
        total = int(unique_counts.sum())
        for class_id, count in zip(unique, unique_counts, strict=True):
            key = str(int(class_id))
            counts[key] = int(count)
            fractions[key] = float(count / total)
    return {
        "valid_cells": int(valid_values.size),
        "counts": counts,
        "fractions": fractions,
    }


def summarize_small_integer_surface(surface: xr.DataArray) -> dict[str, Any]:
    """Summarize one small integer grid such as agreement count."""

    values = np.asarray(surface.values, dtype=np.int16)
    valid = values >= 0
    valid_values = values[valid]
    summary: dict[str, Any] = {"valid_cells": int(valid_values.size), "counts": {}}
    if valid_values.size == 0:
        return summary
    unique, unique_counts = np.unique(valid_values, return_counts=True)
    summary["counts"] = {
        str(int(value)): int(count)
        for value, count in zip(unique, unique_counts, strict=True)
    }
    return summary


def summarize_continuous_surface(surface: xr.DataArray) -> dict[str, Any]:
    """Summarize one continuous grid such as entropy."""

    values = np.asarray(surface.values, dtype=np.float32)
    finite = np.isfinite(values)
    if not np.any(finite):
        return {"valid_cells": 0}
    subset = values[finite]
    return {
        "valid_cells": int(subset.size),
        "min": float(np.min(subset)),
        "mean": float(np.mean(subset)),
        "max": float(np.max(subset)),
    }


def compare_unified_fraction_cubes(left: xr.DataArray, right: xr.DataArray) -> dict[str, Any]:
    """Compare two aligned annual unified fraction cubes."""

    left_values = np.asarray(left.values, dtype=np.float32)
    right_values = np.asarray(right.values, dtype=np.float32)
    diff = np.abs(left_values - right_values)
    finite = np.isfinite(diff)
    if not np.any(finite):
        overall_max = 0.0
        overall_mean = 0.0
    else:
        overall_max = float(np.max(diff[finite]))
        overall_mean = float(np.mean(diff[finite]))
    per_class: dict[str, Any] = {}
    for index, class_id in enumerate(np.asarray(left.coords["class_id"].values, dtype=np.int16)):
        class_diff = diff[index]
        class_finite = np.isfinite(class_diff)
        if np.any(class_finite):
            per_class[str(int(class_id))] = {
                "max_abs_diff": float(np.max(class_diff[class_finite])),
                "mean_abs_diff": float(np.mean(class_diff[class_finite])),
            }
        else:
            per_class[str(int(class_id))] = {"max_abs_diff": 0.0, "mean_abs_diff": 0.0}
    return {
        "max_abs_diff": overall_max,
        "mean_abs_diff": overall_mean,
        "per_class": per_class,
    }


def compare_dominant_classes(left: xr.DataArray, right: xr.DataArray) -> dict[str, Any]:
    """Compare two aligned dominant-class surfaces."""

    left_values = np.asarray(left.values, dtype=np.int16)
    right_values = np.asarray(right.values, dtype=np.int16)
    valid = (left_values >= 0) & (right_values >= 0)
    valid_count = int(np.sum(valid))
    if valid_count == 0:
        return {"valid_cells": 0, "changed_cells": 0, "changed_fraction": 0.0, "transitions": []}

    changed = valid & (left_values != right_values)
    changed_count = int(np.sum(changed))
    transitions: dict[tuple[int, int], int] = {}
    left_changed = left_values[changed]
    right_changed = right_values[changed]
    for from_class, to_class in zip(left_changed, right_changed, strict=True):
        key = (int(from_class), int(to_class))
        transitions[key] = transitions.get(key, 0) + 1

    ranked_transitions = sorted(
        (
            {"from": from_class, "to": to_class, "count": count}
            for (from_class, to_class), count in transitions.items()
        ),
        key=lambda item: (-item["count"], item["from"], item["to"]),
    )
    return {
        "valid_cells": valid_count,
        "changed_cells": changed_count,
        "changed_fraction": float(changed_count / valid_count),
        "transitions": ranked_transitions,
    }


def _bbox_intersects(a: BBox, b: BBox) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _spatial_dims(data: xr.DataArray | xr.Dataset) -> tuple[str, str]:
    dims = tuple(data.dims)
    if "lat" in dims and "lon" in dims:
        return "lat", "lon"
    if "y" in dims and "x" in dims:
        return "y", "x"
    raise ValueError(f"Expected spatial dims to include lat/lon or y/x, got {dims}")


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _strip_internal_dataarrays(payload: dict[str, Any]) -> None:
    for key, value in list(payload.items()):
        if isinstance(value, dict):
            _strip_internal_dataarrays(value)
        elif key.endswith("_dataarray"):
            payload.pop(key, None)
