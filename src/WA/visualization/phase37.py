"""Visualization helpers for Phase 3.7 global classification disagreement plots."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap
from matplotlib.patches import Patch
from netCDF4 import Dataset as NetCDFDataset

from WA.classification import (
    dataset_display_name,
    source_class_ids,
    source_class_names,
    unified_class_ids,
    unified_class_names,
)

logger = logging.getLogger(__name__)

DEFAULT_PHASE37_SAMPLE_STEP = 8
DEFAULT_PHASE37_SOURCE_LAT_CHUNK_SIZE = 512
INVALID_CLASS_VALUE = np.int16(-1)
GEO_TICK_STEPS = (30.0, 45.0, 60.0, 90.0, 120.0)

ENTROPY_CMAP = LinearSegmentedColormap.from_list(
    "phase37_entropy",
    ["#ffffff", "#fdd0a2", "#fc8d59", "#b30000"],
)
AGREEMENT_COLORS = ("#d73027", "#fdae61", "#1a9850")
CLASS_COLORS = (
    "#e0e0e0",  # Non-wetland
    "#2b83ba",  # Water
    "#66bd63",  # Inland Herbaceous Wetlands
    "#1b7837",  # Forested Wetlands
    "#7b3294",  # Peatland
    "#fdae61",  # Floodplain Wetlands
    "#1c9099",  # Coastal Wetlands
    "#d53e4f",  # Artificial Wetlands
)


@dataclass(frozen=True)
class DiscreteStyle:
    """Discrete plotting style with colormap, norm, and ticks."""

    cmap: ListedColormap
    norm: BoundaryNorm
    ticks: tuple[int, ...]
    labels: dict[int, str]


def classification_style() -> DiscreteStyle:
    """Return the fixed 8-class style used by Phase 3.7 class maps."""

    ticks = tuple(int(class_id) for class_id in unified_class_ids())
    cmap = ListedColormap(CLASS_COLORS, name="phase37_classes")
    cmap.set_bad((1.0, 1.0, 1.0, 0.0))
    boundaries = np.arange(-0.5, len(ticks) + 0.5, 1.0)
    norm = BoundaryNorm(boundaries, cmap.N)
    return DiscreteStyle(
        cmap=cmap,
        norm=norm,
        ticks=ticks,
        labels={
            int(class_id): _legend_label_with_id(name, int(class_id))
            for class_id, name in unified_class_names().items()
        },
    )


def agreement_count_style() -> DiscreteStyle:
    """Return the 3-bin discrete style used by agreement count."""

    ticks = (1, 2, 3)
    cmap = ListedColormap(AGREEMENT_COLORS, name="phase37_agreement")
    cmap.set_bad((1.0, 1.0, 1.0, 0.0))
    boundaries = np.arange(0.5, 4.5, 1.0)
    norm = BoundaryNorm(boundaries, cmap.N)
    return DiscreteStyle(
        cmap=cmap,
        norm=norm,
        ticks=ticks,
        labels={1: "1 dataset", 2: "2 datasets", 3: "3 datasets"},
    )


def source_class_style(dataset_id: str) -> DiscreteStyle:
    """Return one dataset's fixed raw/source classification style."""

    ticks = tuple(int(class_id) for class_id in source_class_ids(dataset_id))
    labels = source_class_names(dataset_id)
    colors = _dataset_source_colors(dataset_id, len(ticks))
    cmap = ListedColormap(colors, name=f"phase37_{dataset_id}_source_classes")
    cmap.set_bad((1.0, 1.0, 1.0, 0.0))
    boundaries = _discrete_boundaries_for_ticks(ticks)
    norm = BoundaryNorm(boundaries, cmap.N)
    return DiscreteStyle(
        cmap=cmap,
        norm=norm,
        ticks=ticks,
        labels={
            int(class_id): _legend_label_with_id(str(labels[int(class_id)]), int(class_id))
            for class_id in ticks
        },
    )


def _dataset_source_colors(dataset_id: str, count: int) -> list[tuple[float, float, float, float]]:
    """Return a deterministic categorical palette for one dataset's raw classes."""

    if count <= 0:
        return []

    combined: list[tuple[float, float, float, float]] = []
    for cmap_name in ("tab20", "tab20b", "tab20c"):
        cmap = plt.get_cmap(cmap_name)
        combined.extend(cmap.colors)

    normalized_id = dataset_id.lower()
    offset = {"g2017": 0, "glwd_v2": 7, "gwd30": 13}.get(normalized_id, 0)
    return [combined[(offset + index) % len(combined)] for index in range(count)]


def _discrete_boundaries_for_ticks(ticks: tuple[int, ...]) -> np.ndarray:
    """Build BoundaryNorm edges for integer tick values, including sparse codes."""

    if not ticks:
        raise ValueError("Discrete ticks are required")
    if len(ticks) == 1:
        tick = float(ticks[0])
        return np.array([tick - 0.5, tick + 0.5], dtype=np.float64)

    tick_values = np.asarray(ticks, dtype=np.float64)
    midpoints = (tick_values[:-1] + tick_values[1:]) / 2.0
    first_edge = tick_values[0] - (midpoints[0] - tick_values[0])
    last_edge = tick_values[-1] + (tick_values[-1] - midpoints[-1])
    return np.concatenate(
        [
            np.array([first_edge], dtype=np.float64),
            midpoints,
            np.array([last_edge], dtype=np.float64),
        ]
    )


def _legend_label_with_id(name: str, class_id: int) -> str:
    """Format one class legend label as `Name ID`."""

    return f"{name} {class_id}"


def prepare_entropy_for_plot(plot_dataset: xr.Dataset) -> xr.DataArray:
    """Mask non-joint-valid cells for entropy plotting."""

    joint_valid = plot_dataset["joint_valid_mask"] > 0
    return plot_dataset["entropy"].where(joint_valid)


def prepare_agreement_for_plot(plot_dataset: xr.Dataset) -> xr.DataArray:
    """Mask invalid agreement count cells for plotting."""

    prepared = xr.where(
        plot_dataset["agreement_count"] > 0,
        plot_dataset["agreement_count"],
        np.nan,
    )
    return prepared.astype(np.float32)


def prepare_class_for_plot(surface: xr.DataArray) -> xr.DataArray:
    """Mask invalid class cells for plotting."""

    prepared = xr.where(surface >= 0, surface, np.nan)
    return prepared.astype(np.float32)


def build_phase37_global_plot_dataset(
    metrics_path: Path,
    classes_path: Path,
    *,
    sample_step: int = DEFAULT_PHASE37_SAMPLE_STEP,
) -> xr.Dataset:
    """Load a sparse-sampled subset from the original 500m Phase 3.6 outputs."""

    if sample_step <= 0:
        raise ValueError("sample_step must be positive")

    metrics = xr.open_dataset(metrics_path, decode_cf=True)
    classes = xr.open_dataset(classes_path, decode_cf=True)
    try:
        y_dim, x_dim = _spatial_dims(metrics["entropy"])
        if _spatial_dims(classes["g2017_dominant_class"]) != (y_dim, x_dim):
            raise ValueError("metrics and classes files do not share the same spatial dimensions")

        sample_indexers = {
            y_dim: slice(None, None, sample_step),
            x_dim: slice(None, None, sample_step),
        }
        sampled_metrics = metrics[
            ["entropy", "majority_class", "agreement_count", "joint_valid_mask"]
        ].isel(sample_indexers).load()
        sampled_classes = classes[
            [
                "g2017_dominant_class",
                "glwd_v2_dominant_class",
                "gwd30_dominant_class",
            ]
        ].isel(sample_indexers).load()
        plot_dataset = xr.merge([sampled_metrics, sampled_classes])
        plot_dataset.attrs.update(
            {
                "phase": "phase3.7",
                "source_phase": "phase3.6",
                "sample_step": int(sample_step),
                "source_metrics_path": str(metrics_path),
                "source_classes_path": str(classes_path),
                "unified_class_names_json": json.dumps(unified_class_names(), sort_keys=True),
            }
        )
        return plot_dataset
    finally:
        metrics.close()
        classes.close()


def build_phase37_hotspot_plot_dataset(
    metrics_dataset: xr.Dataset,
    classes_dataset: xr.Dataset | None,
    *,
    bbox: tuple[float, float, float, float],
    standardized_dir: str | Path | None = None,
    year: int | None = None,
) -> xr.Dataset:
    """Build one loaded Phase 3.7 AOI dataset directly from Phase 3.6 globals."""

    metrics_subset = subset_phase37_plot_dataset_to_bbox(
        metrics_dataset[
            ["entropy", "majority_class", "agreement_count", "joint_valid_mask"]
        ],
        bbox,
    ).load()
    plot_dataset = metrics_subset
    source_vars = [
        "g2017_source_dominant_class",
        "glwd_v2_source_dominant_class",
        "gwd30_source_dominant_class",
    ]
    source_loaded_from_classes = False
    if classes_dataset is not None:
        y_dim, x_dim = _spatial_dims(metrics_dataset["entropy"])
        if _spatial_dims(classes_dataset["g2017_dominant_class"]) != (y_dim, x_dim):
            raise ValueError("metrics and classes files do not share the same spatial dimensions")
        class_vars = [
            "g2017_dominant_class",
            "glwd_v2_dominant_class",
            "gwd30_dominant_class",
        ]
        if all(variable_name in classes_dataset.data_vars for variable_name in source_vars):
            class_vars.extend(source_vars)
            source_loaded_from_classes = True
        classes_subset = subset_phase37_plot_dataset_to_bbox(
            classes_dataset[class_vars],
            bbox,
        ).load()
        plot_dataset = xr.merge([plot_dataset, classes_subset])
    if not source_loaded_from_classes and standardized_dir is not None:
        if year is None:
            raise ValueError("year is required when building raw hotspot source classes")
        source_subset = _build_phase37_hotspot_source_class_dataset(
            standardized_dir=Path(standardized_dir),
            year=year,
            bbox=bbox,
            reference_surface=metrics_subset["entropy"],
        )
        plot_dataset = xr.merge([plot_dataset, source_subset])
    elif classes_dataset is None:
        raise ValueError("Either standardized_dir or classes_dataset is required")

    plot_dataset.attrs.update(
        {
            "phase": "phase3.7",
            "source_phase": "phase3.6",
            "subset_bbox_json": json.dumps([float(value) for value in bbox]),
            "unified_class_names_json": json.dumps(unified_class_names(), sort_keys=True),
        }
    )
    return plot_dataset


def _build_phase37_hotspot_source_class_dataset(
    *,
    standardized_dir: Path,
    year: int,
    bbox: tuple[float, float, float, float],
    reference_surface: xr.DataArray,
) -> xr.Dataset:
    """Load and annualize per-dataset raw/source dominant classes for one hotspot AOI."""

    outputs: dict[str, xr.DataArray] = {}
    for dataset_id in ("g2017", "glwd_v2", "gwd30"):
        dataset = _open_phase37_standardized_dataset(
            standardized_dir=standardized_dir,
            dataset_id=dataset_id,
            year=year,
            bbox=bbox,
            reference_surface=reference_surface,
        )
        try:
            outputs[f"{dataset_id}_source_dominant_class"] = _compute_source_dominant_class(
                dataset_id,
                dataset,
                reference_surface=reference_surface,
            )
        finally:
            dataset.close()
    return xr.Dataset(outputs)


def _open_phase37_standardized_dataset(
    *,
    standardized_dir: Path,
    dataset_id: str,
    year: int,
    bbox: tuple[float, float, float, float],
    reference_surface: xr.DataArray,
) -> xr.Dataset:
    """Open one standardized dataset directly from disk for hotspot raw plotting."""

    if dataset_id == "gwd30":
        return _open_phase37_gwd30_staged_dataset(
            standardized_dir=standardized_dir,
            year=year,
            bbox=bbox,
            reference_surface=reference_surface,
        )

    path = standardized_dir / f"{dataset_id}.nc"
    if not path.is_file():
        raise FileNotFoundError(f"Standardized dataset not found for hotspot plotting: {path}")

    dataset = xr.open_dataset(path, decode_cf=True)
    try:
        renamed = _normalize_phase37_spatial_dims(dataset)
        subset = subset_phase37_plot_dataset_to_bbox(renamed, bbox).load()
    finally:
        dataset.close()
    return subset


def _open_phase37_gwd30_staged_dataset(
    *,
    standardized_dir: Path,
    year: int,
    bbox: tuple[float, float, float, float],
    reference_surface: xr.DataArray,
) -> xr.Dataset:
    """Restore one hotspot AOI GWD30 raw-fraction dataset from staged tiles."""

    staged_tiles = _load_phase37_gwd30_staged_tiles(standardized_dir, year=year)
    candidate_tiles = [
        (stage_path, manifest_bbox)
        for stage_path, manifest_bbox in staged_tiles
        if _phase37_bbox_intersects(manifest_bbox, bbox)
    ]
    if not candidate_tiles:
        raise FileNotFoundError(
            "No GWD30 staged tiles intersect hotspot bbox "
            f"{bbox!r} under {standardized_dir / '_staging' / f'gwd30_{year}'}"
        )

    y_dim, x_dim = _spatial_dims(reference_surface)
    target_y = reference_surface.coords[y_dim].values
    target_x = reference_surface.coords[x_dim].values
    weighted_sum: np.ndarray | None = None
    coverage_sum: np.ndarray | None = None
    time_coords: np.ndarray | None = None
    class_coords: np.ndarray | None = None

    for stage_path, _manifest_bbox in candidate_tiles:
        with xr.open_dataset(stage_path, decode_cf=True) as source:
            source_y_dim, source_x_dim = _spatial_dims(source)
            weighted = source["weighted"].reindex(
                {source_y_dim: target_y, source_x_dim: target_x},
                fill_value=0.0,
            ).transpose("time", "class_id", source_y_dim, source_x_dim)
            coverage = source["coverage"].reindex(
                {source_y_dim: target_y, source_x_dim: target_x},
                fill_value=0.0,
            ).transpose("time", source_y_dim, source_x_dim)

            if time_coords is None:
                time_coords = np.asarray(weighted.coords["time"].values)
            if class_coords is None:
                class_coords = np.asarray(weighted.coords["class_id"].values, dtype=np.int16)

            weighted_values = np.asarray(weighted.values, dtype=np.float32)
            coverage_values = np.asarray(coverage.values, dtype=np.float32)
            if weighted_sum is None:
                weighted_sum = weighted_values
                coverage_sum = coverage_values
            else:
                weighted_sum = weighted_sum + weighted_values
                coverage_sum = coverage_sum + coverage_values

    if weighted_sum is None or coverage_sum is None or time_coords is None or class_coords is None:
        raise FileNotFoundError(f"Failed to restore staged GWD30 hotspot dataset for {bbox!r}")

    fractions = np.full_like(weighted_sum, np.nan, dtype=np.float32)
    np.divide(
        weighted_sum,
        coverage_sum[:, None, :, :],
        out=fractions,
        where=coverage_sum[:, None, :, :] > 0,
    )
    fractions = np.clip(fractions, 0.0, 1.0)

    coords = {
        "time": time_coords,
        y_dim: target_y,
        x_dim: target_x,
    }
    return xr.Dataset(
        {
            f"frac_{int(class_id)}": xr.DataArray(
                fractions[:, class_index],
                dims=("time", y_dim, x_dim),
                coords=coords,
                attrs={
                    "dataset_id": "gwd30",
                    "year": year,
                    "source": "phase37_hotspot_staged_tiles",
                },
            )
            for class_index, class_id in enumerate(class_coords)
        },
        attrs={
            "dataset_id": "gwd30",
            "year": year,
            "source": "phase37_hotspot_staged_tiles",
        },
    )


def _load_phase37_gwd30_staged_tiles(
    standardized_dir: Path,
    *,
    year: int,
) -> list[tuple[Path, tuple[float, float, float, float]]]:
    """Restore staged GWD30 tile paths and bboxes from shard manifests."""

    staging_root = standardized_dir / "_staging" / f"gwd30_{year}"
    manifest_paths = sorted(staging_root.glob("stage_shard_*.json"))
    if not manifest_paths:
        raise FileNotFoundError(
            f"No GWD30 stage shard manifests found under {staging_root}"
        )

    staged_by_path: dict[Path, tuple[float, float, float, float]] = {}
    for manifest_path in manifest_paths:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in payload.get("staged_tiles", []):
            stage_path = Path(str(item["path"]))
            if not stage_path.exists():
                continue
            bbox_values = tuple(float(value) for value in item["bbox"])
            if len(bbox_values) != 4:
                raise ValueError(f"Invalid staged bbox in {manifest_path}: {item['bbox']!r}")
            staged_by_path[stage_path] = bbox_values

    if not staged_by_path:
        raise FileNotFoundError(
            f"GWD30 stage shard manifests under {staging_root} did not reference existing tiles"
        )

    return sorted(staged_by_path.items(), key=lambda item: str(item[0]))


def _phase37_bbox_intersects(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    """Return whether two lon/lat bboxes intersect."""

    left_min_lon, left_min_lat, left_max_lon, left_max_lat = left
    right_min_lon, right_min_lat, right_max_lon, right_max_lat = right
    return not (
        left_max_lon < right_min_lon
        or right_max_lon < left_min_lon
        or left_max_lat < right_min_lat
        or right_max_lat < left_min_lat
    )


def _normalize_phase37_spatial_dims(dataset: xr.Dataset) -> xr.Dataset:
    """Normalize common spatial coordinate aliases without importing loader packages."""

    rename_map: dict[str, str] = {}
    if "latitude" in dataset.dims or "latitude" in dataset.coords:
        rename_map["latitude"] = "lat"
    if "longitude" in dataset.dims or "longitude" in dataset.coords:
        rename_map["longitude"] = "lon"
    if rename_map:
        dataset = dataset.rename(rename_map)
    return dataset


def _compute_source_dominant_class(
    dataset_id: str,
    dataset: xr.Dataset,
    *,
    reference_surface: xr.DataArray,
) -> xr.DataArray:
    """Collapse standardized raw class fractions to one source-class dominant surface."""

    y_dim, x_dim = _spatial_dims(reference_surface)
    target_y = reference_surface.coords[y_dim].values
    target_x = reference_surface.coords[x_dim].values
    class_ids: list[int] = []
    layers: list[np.ndarray] = []

    for class_id in source_class_ids(dataset_id):
        variable_name = f"frac_{class_id}"
        if variable_name not in dataset.data_vars:
            continue
        surface = dataset[variable_name]
        if "time" in surface.dims:
            surface = surface.mean(dim="time", skipna=True)
        surface = surface.reindex({y_dim: target_y, x_dim: target_x})
        class_ids.append(int(class_id))
        layers.append(np.asarray(surface.values, dtype=np.float32))

    if not layers:
        raise ValueError(f"{dataset_id} has no raw frac_* variables available for hotspot plotting")

    stacked = np.stack(layers, axis=0)
    finite_any = np.isfinite(stacked).any(axis=0)
    totals = np.nansum(stacked, axis=0, dtype=np.float32)
    valid_mask = finite_any & (totals > 0)
    scores = np.where(np.isfinite(stacked), stacked, -np.inf)
    chosen_index = np.argmax(scores, axis=0)
    class_id_array = np.asarray(class_ids, dtype=np.int16)
    dominant = class_id_array[chosen_index].astype(np.int16)
    dominant[~valid_mask] = INVALID_CLASS_VALUE
    return xr.DataArray(
        dominant,
        dims=(y_dim, x_dim),
        coords={
            y_dim: target_y,
            x_dim: target_x,
        },
        name=f"{dataset_id}_source_dominant_class",
        attrs={
            "dataset_id": dataset_id,
            "classification_level": "source",
            "source_class_names_json": json.dumps(source_class_names(dataset_id), sort_keys=True),
            "dataset_display_name": dataset_display_name(dataset_id),
        },
    )


def write_phase37_global_plot_cache(
    metrics_path: Path,
    classes_path: Path,
    *,
    cache_path: Path,
    sample_step: int = DEFAULT_PHASE37_SAMPLE_STEP,
    source_lat_chunk_size: int = DEFAULT_PHASE37_SOURCE_LAT_CHUNK_SIZE,
) -> Path:
    """Write a sparse-sampled Phase 3.7 display cache without reprojection."""

    if sample_step <= 0:
        raise ValueError("sample_step must be positive")
    if source_lat_chunk_size <= 0:
        raise ValueError("source_lat_chunk_size must be positive")

    metrics = xr.open_dataset(metrics_path, decode_cf=True)
    classes = xr.open_dataset(classes_path, decode_cf=True)
    try:
        y_dim, x_dim = _spatial_dims(metrics["entropy"])
        if _spatial_dims(classes["g2017_dominant_class"]) != (y_dim, x_dim):
            raise ValueError("metrics and classes files do not share the same spatial dimensions")

        lat_values = np.asarray(metrics.coords[y_dim].values)
        lon_values = np.asarray(metrics.coords[x_dim].values)
        sampled_lat_indices = np.arange(0, len(lat_values), sample_step, dtype=np.int64)
        sampled_lon_indices = np.arange(0, len(lon_values), sample_step, dtype=np.int64)
        sampled_lat_values = lat_values[sampled_lat_indices]
        sampled_lon_values = lon_values[sampled_lon_indices]

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = _temp_output_path(cache_path)
        row_cursor = 0
        try:
            with NetCDFDataset(temp_path, mode="w", format="NETCDF4") as target:
                _initialize_plot_cache_file(
                    target,
                    y_dim=y_dim,
                    x_dim=x_dim,
                    lat_values=sampled_lat_values,
                    lon_values=sampled_lon_values,
                    sample_step=sample_step,
                    metrics_path=metrics_path,
                    classes_path=classes_path,
                    source_lat_chunk_size=source_lat_chunk_size,
                )
                for row_start in range(0, len(lat_values), source_lat_chunk_size):
                    row_stop = min(len(lat_values), row_start + source_lat_chunk_size)
                    sampled_rows = sampled_lat_indices[
                        (sampled_lat_indices >= row_start) & (sampled_lat_indices < row_stop)
                    ]
                    if sampled_rows.size == 0:
                        continue
                    logger.info(
                        "Phase3.7 plot cache stripe start: rows=%s:%s/%s sampled_rows=%s",
                        row_start,
                        row_stop,
                        len(lat_values),
                        sampled_rows.size,
                    )
                    local_rows = sampled_rows - row_start
                    metric_chunk = metrics.isel(
                        {
                            y_dim: slice(row_start, row_stop),
                            x_dim: sampled_lon_indices,
                        }
                    ).load()
                    class_chunk = classes.isel(
                        {
                            y_dim: slice(row_start, row_stop),
                            x_dim: sampled_lon_indices,
                        }
                    ).load()
                    sampled_metric_chunk = metric_chunk.isel({y_dim: local_rows})
                    sampled_class_chunk = class_chunk.isel({y_dim: local_rows})
                    row_count = sampled_rows.size
                    row_slice = slice(row_cursor, row_cursor + row_count)
                    for variable_name in (
                        "entropy",
                        "majority_class",
                        "agreement_count",
                        "joint_valid_mask",
                    ):
                        target.variables[variable_name][row_slice, :] = np.asarray(
                            sampled_metric_chunk[variable_name].values
                        )
                    for variable_name in (
                        "g2017_dominant_class",
                        "glwd_v2_dominant_class",
                        "gwd30_dominant_class",
                    ):
                        target.variables[variable_name][row_slice, :] = np.asarray(
                            sampled_class_chunk[variable_name].values
                        )
                    row_cursor += row_count
                    logger.info(
                        "Phase3.7 plot cache stripe done: rows=%s:%s/%s",
                        row_start,
                        row_stop,
                        len(lat_values),
                    )
            os.replace(temp_path, cache_path)
        finally:
            temp_path.unlink(missing_ok=True)
    finally:
        metrics.close()
        classes.close()
    return cache_path


def subset_phase37_plot_dataset_to_bbox(
    plot_dataset: xr.Dataset,
    bbox: tuple[float, float, float, float],
) -> xr.Dataset:
    """Subset a Phase 3.7 plot dataset to one region bbox."""

    west, south, east, north = bbox
    y_dim, x_dim = _spatial_dims(plot_dataset)

    lon_values = np.asarray(plot_dataset.coords[x_dim].values)
    lon_slice = slice(west, east) if lon_values[0] <= lon_values[-1] else slice(east, west)
    lon_subset = plot_dataset.sel({x_dim: lon_slice})
    if lon_subset.sizes.get(x_dim, 0) == 0:
        raise ValueError(f"Region bbox {bbox!r} produces empty lon selection")

    lat_values = np.asarray(lon_subset.coords[y_dim].values)
    lat_slice = slice(south, north) if lat_values[0] <= lat_values[-1] else slice(north, south)
    subset = lon_subset.sel({y_dim: lat_slice})
    if subset.sizes.get(y_dim, 0) == 0 or subset.sizes.get(x_dim, 0) == 0:
        raise ValueError(f"Region bbox {bbox!r} produces empty lat/lon subset")

    subset.attrs = dict(plot_dataset.attrs)
    subset.attrs["subset_bbox_json"] = json.dumps([float(value) for value in bbox])
    return subset


def plot_phase37_global_figure(
    plot_dataset: xr.Dataset,
    *,
    output_path: Path,
    dpi: int = 300,
    suptitle: str | None = None,
    wspace: float = 0.06,
    hspace: float = 0.018,
) -> Path:
    """Plot the Phase 3.7 global 2x3 figure plus bottom legends."""

    required = {
        "entropy",
        "agreement_count",
        "majority_class",
        "g2017_dominant_class",
        "glwd_v2_dominant_class",
        "gwd30_dominant_class",
        "joint_valid_mask",
    }
    missing = required.difference(plot_dataset.data_vars)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"plot dataset missing required variables: {missing_text}")

    entropy_surface = prepare_entropy_for_plot(plot_dataset)
    agreement_surface = prepare_agreement_for_plot(plot_dataset)
    majority_surface = prepare_class_for_plot(plot_dataset["majority_class"])
    g2017_surface = prepare_class_for_plot(plot_dataset["g2017_dominant_class"])
    glwd_surface = prepare_class_for_plot(plot_dataset["glwd_v2_dominant_class"])
    gwd30_surface = prepare_class_for_plot(plot_dataset["gwd30_dominant_class"])
    class_style = classification_style()
    agreement_style = agreement_count_style()
    extent = _surface_extent(entropy_surface)

    use_cartopy = False
    transform = None
    try:
        import cartopy.crs as ccrs

        use_cartopy = True
        transform = ccrs.PlateCarree()
    except ImportError:
        pass

    subplot_kwargs = {"projection": transform} if use_cartopy else {}
    fig = plt.figure(figsize=(15.0, 12.8))
    outer = fig.add_gridspec(
        4,
        2,
        height_ratios=[1.0, 1.0, 1.0, 0.26],
        wspace=wspace,
        hspace=hspace,
    )
    axes = [
        fig.add_subplot(outer[row, col], **subplot_kwargs)
        for row in range(3)
        for col in range(2)
    ]

    entropy_mesh = _plot_phase37_surface(
        axes[0],
        entropy_surface,
        title="Entropy",
        cmap=ENTROPY_CMAP,
        extent=extent,
        vmin=0.0,
        vmax=1.0,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=True,
        show_bottom_labels=False,
    )
    _plot_phase37_surface(
        axes[1],
        g2017_surface,
        title="G2017",
        cmap=class_style.cmap,
        norm=class_style.norm,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=False,
        show_bottom_labels=False,
    )
    _plot_phase37_surface(
        axes[2],
        agreement_surface,
        title="Agreement Count",
        cmap=agreement_style.cmap,
        norm=agreement_style.norm,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=True,
        show_bottom_labels=False,
    )
    _plot_phase37_surface(
        axes[3],
        glwd_surface,
        title="GLWD v2",
        cmap=class_style.cmap,
        norm=class_style.norm,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=False,
        show_bottom_labels=False,
    )
    _plot_phase37_surface(
        axes[4],
        majority_surface,
        title="Majority Class",
        cmap=class_style.cmap,
        norm=class_style.norm,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=True,
        show_bottom_labels=True,
    )
    _plot_phase37_surface(
        axes[5],
        gwd30_surface,
        title="GWD30",
        cmap=class_style.cmap,
        norm=class_style.norm,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=False,
        show_bottom_labels=True,
    )

    legend_gs = outer[3, :].subgridspec(1, 3, width_ratios=[2.9, 1.2, 1.0], wspace=0.22)
    class_ax = fig.add_subplot(legend_gs[0, 0])
    entropy_ax = fig.add_subplot(legend_gs[0, 1])
    agreement_ax = fig.add_subplot(legend_gs[0, 2])
    _draw_class_legend(class_ax)
    colorbar = fig.colorbar(entropy_mesh, cax=entropy_ax, orientation="horizontal")
    colorbar.set_label("Entropy", fontsize=11)
    colorbar.ax.tick_params(labelsize=10)
    _draw_agreement_legend(agreement_ax)

    if suptitle:
        fig.suptitle(suptitle, fontsize=14, fontweight="bold", y=0.985)
        top = 0.962
    else:
        top = 0.972
    fig.subplots_adjust(left=0.05, right=0.98, top=top, bottom=0.04)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def plot_phase37_hotspot_panel(
    plot_dataset: xr.Dataset,
    *,
    output_path: Path,
    satellite_image_path: Path | None = None,
    dpi: int = 300,
    suptitle: str | None = None,
    wspace: float = 0.08,
    hspace: float = 0.12,
) -> Path:
    """Plot one Phase 3.7 hotspot 2x3 panel."""

    raw_mode = all(
        variable_name in plot_dataset.data_vars
        for variable_name in (
            "g2017_source_dominant_class",
            "glwd_v2_source_dominant_class",
            "gwd30_source_dominant_class",
        )
    )
    required = {"entropy", "majority_class", "joint_valid_mask"}
    if raw_mode:
        required.update(
            {
                "g2017_source_dominant_class",
                "glwd_v2_source_dominant_class",
                "gwd30_source_dominant_class",
            }
        )
    else:
        required.update(
            {
                "g2017_dominant_class",
                "glwd_v2_dominant_class",
                "gwd30_dominant_class",
            }
        )
    missing = required.difference(plot_dataset.data_vars)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"plot dataset missing required variables: {missing_text}")

    entropy_surface = prepare_entropy_for_plot(plot_dataset)
    majority_surface = prepare_class_for_plot(plot_dataset["majority_class"])
    if raw_mode:
        g2017_surface = prepare_class_for_plot(plot_dataset["g2017_source_dominant_class"])
        glwd_surface = prepare_class_for_plot(plot_dataset["glwd_v2_source_dominant_class"])
        gwd30_surface = prepare_class_for_plot(plot_dataset["gwd30_source_dominant_class"])
    else:
        g2017_surface = prepare_class_for_plot(plot_dataset["g2017_dominant_class"])
        glwd_surface = prepare_class_for_plot(plot_dataset["glwd_v2_dominant_class"])
        gwd30_surface = prepare_class_for_plot(plot_dataset["gwd30_dominant_class"])
    unified_style = classification_style()
    g2017_style = source_class_style("g2017") if raw_mode else unified_style
    glwd_style = source_class_style("glwd_v2") if raw_mode else unified_style
    gwd30_style = source_class_style("gwd30") if raw_mode else unified_style
    extent = _surface_extent(entropy_surface)

    use_cartopy = False
    transform = None
    try:
        import cartopy.crs as ccrs

        use_cartopy = True
        transform = ccrs.PlateCarree()
    except ImportError:
        pass

    subplot_kwargs = {"projection": transform} if use_cartopy else {}
    fig = plt.figure(figsize=(15.0, 13.8 if raw_mode else 10.8))
    outer = fig.add_gridspec(
        4 if raw_mode else 3,
        3,
        height_ratios=[1.0, 1.0, 0.22, 0.34] if raw_mode else [1.0, 1.0, 0.18],
        wspace=wspace,
        hspace=hspace,
    )
    axes = [
        fig.add_subplot(outer[row, col], **subplot_kwargs)
        for row in range(2)
        for col in range(3)
    ]

    _plot_phase37_satellite_panel(
        axes[0],
        image_path=satellite_image_path,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=True,
        show_bottom_labels=False,
    )
    entropy_mesh = _plot_phase37_surface(
        axes[1],
        entropy_surface,
        title="Entropy",
        cmap=ENTROPY_CMAP,
        extent=extent,
        vmin=0.0,
        vmax=1.0,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=False,
        show_bottom_labels=False,
    )
    _plot_phase37_surface(
        axes[2],
        majority_surface,
        title="Unified Majority",
        cmap=unified_style.cmap,
        norm=unified_style.norm,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=False,
        show_bottom_labels=False,
    )
    _plot_phase37_surface(
        axes[3],
        g2017_surface,
        title="G2017 Raw Class" if raw_mode else "G2017",
        cmap=g2017_style.cmap,
        norm=g2017_style.norm,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=True,
        show_bottom_labels=True,
    )
    _plot_phase37_surface(
        axes[4],
        glwd_surface,
        title="GLWD v2 Raw Class" if raw_mode else "GLWD v2",
        cmap=glwd_style.cmap,
        norm=glwd_style.norm,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=False,
        show_bottom_labels=True,
    )
    _plot_phase37_surface(
        axes[5],
        gwd30_surface,
        title="GWD30 Raw Class" if raw_mode else "GWD30",
        cmap=gwd30_style.cmap,
        norm=gwd30_style.norm,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=False,
        show_bottom_labels=True,
    )

    majority_present = _present_class_ids(majority_surface)
    g2017_present = _present_class_ids(g2017_surface)
    glwd_present = _present_class_ids(glwd_surface)
    gwd30_present = _present_class_ids(gwd30_surface)

    if raw_mode:
        top_legend_gs = outer[2, :].subgridspec(1, 3, wspace=0.24)
        bottom_legend_gs = outer[3, :].subgridspec(1, 3, wspace=0.24)
        g2017_ax = fig.add_subplot(top_legend_gs[0, 0])
        glwd_ax = fig.add_subplot(top_legend_gs[0, 1])
        gwd30_ax = fig.add_subplot(top_legend_gs[0, 2])
        majority_ax = fig.add_subplot(bottom_legend_gs[0, 0])
        entropy_ax = fig.add_subplot(bottom_legend_gs[0, 1])
        spacer_ax = fig.add_subplot(bottom_legend_gs[0, 2])
        _draw_discrete_class_legend(
            g2017_ax,
            g2017_style,
            present_class_ids=g2017_present,
            title="G2017 Raw Legend",
        )
        _draw_discrete_class_legend(
            glwd_ax,
            glwd_style,
            present_class_ids=glwd_present,
            title="GLWD v2 Raw Legend",
        )
        _draw_discrete_class_legend(
            gwd30_ax,
            gwd30_style,
            present_class_ids=gwd30_present,
            title="GWD30 Raw Legend",
        )
        _draw_discrete_class_legend(
            majority_ax,
            unified_style,
            present_class_ids=majority_present,
            title="Unified Majority Legend",
        )
        colorbar = fig.colorbar(entropy_mesh, cax=entropy_ax, orientation="horizontal")
        colorbar.set_label("Entropy", fontsize=11)
        colorbar.ax.tick_params(labelsize=10)
        spacer_ax.set_axis_off()
    else:
        legend_gs = outer[2, :].subgridspec(1, 2, width_ratios=[2.8, 1.2], wspace=0.25)
        majority_ax = fig.add_subplot(legend_gs[0, 0])
        entropy_ax = fig.add_subplot(legend_gs[0, 1])
        _draw_discrete_class_legend(
            majority_ax,
            unified_style,
            present_class_ids=majority_present,
            title="Unified Majority Legend",
        )
        colorbar = fig.colorbar(entropy_mesh, cax=entropy_ax, orientation="horizontal")
        colorbar.set_label("Entropy", fontsize=11)
        colorbar.ax.tick_params(labelsize=10)

    if suptitle:
        fig.suptitle(suptitle, fontsize=14, fontweight="bold", y=0.993)
        top = 0.94 if raw_mode else 0.925
    else:
        top = 0.978 if raw_mode else 0.97
    fig.subplots_adjust(left=0.05, right=0.98, top=top, bottom=0.05)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def _initialize_plot_cache_file(
    target: NetCDFDataset,
    *,
    y_dim: str,
    x_dim: str,
    lat_values: np.ndarray,
    lon_values: np.ndarray,
    sample_step: int,
    metrics_path: Path,
    classes_path: Path,
    source_lat_chunk_size: int,
) -> None:
    target.setncattr("phase", "phase3.7")
    target.setncattr("source_phase", "phase3.6")
    target.setncattr("sample_step", int(sample_step))
    target.setncattr("source_metrics_path", str(metrics_path))
    target.setncattr("source_classes_path", str(classes_path))
    target.setncattr("source_lat_chunk_size", int(source_lat_chunk_size))
    target.setncattr("unified_class_names_json", json.dumps(unified_class_names(), sort_keys=True))

    target.createDimension(y_dim, len(lat_values))
    target.createDimension(x_dim, len(lon_values))
    lat_var = target.createVariable(y_dim, lat_values.dtype.str, (y_dim,))
    lon_var = target.createVariable(x_dim, lon_values.dtype.str, (x_dim,))
    lat_var[:] = lat_values
    lon_var[:] = lon_values
    if y_dim == "lat":
        lat_var.setncattr("units", "degrees_north")
        lon_var.setncattr("units", "degrees_east")

    chunksizes = (min(512, len(lat_values)), min(4096, len(lon_values)))
    target.createVariable(
        "entropy",
        "f4",
        (y_dim, x_dim),
        zlib=True,
        complevel=4,
        shuffle=True,
        fill_value=np.float32(np.nan),
        chunksizes=chunksizes,
    )
    for variable_name in (
        "majority_class",
        "agreement_count",
        "g2017_dominant_class",
        "glwd_v2_dominant_class",
        "gwd30_dominant_class",
    ):
        target.createVariable(
            variable_name,
            "i2",
            (y_dim, x_dim),
            zlib=True,
            complevel=4,
            shuffle=True,
            chunksizes=chunksizes,
        )
    target.createVariable(
        "joint_valid_mask",
        "i1",
        (y_dim, x_dim),
        zlib=True,
        complevel=4,
        shuffle=True,
        chunksizes=chunksizes,
    )


def _plot_phase37_surface(
    ax,
    surface: xr.DataArray,
    *,
    title: str,
    cmap,
    extent: tuple[float, float, float, float],
    use_cartopy: bool,
    transform,
    show_left_labels: bool,
    show_bottom_labels: bool,
    vmin: float | None = None,
    vmax: float | None = None,
    norm: BoundaryNorm | None = None,
):
    y_dim, x_dim = _spatial_dims(surface)
    values = np.ma.masked_invalid(np.asarray(surface.values, dtype=np.float32))
    lat_values = np.asarray(surface.coords[y_dim].values, dtype=np.float64)
    origin = "upper" if lat_values.size <= 1 or lat_values[0] > lat_values[-1] else "lower"
    image_kwargs = {
        "origin": origin,
        "extent": extent,
        "cmap": cmap,
        "interpolation": "nearest",
        "rasterized": True,
    }
    if vmin is not None:
        image_kwargs["vmin"] = vmin
    if vmax is not None:
        image_kwargs["vmax"] = vmax
    if norm is not None:
        image_kwargs["norm"] = norm
    if transform is not None:
        image_kwargs["transform"] = transform
    mesh = ax.imshow(values, **image_kwargs)

    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_aspect("equal")
    west, east, south, north = extent
    if use_cartopy:
        ax.set_extent((west, east, south, north), crs=transform)
        ax.coastlines(linewidth=0.5, color="black")
    else:
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)

    _configure_geo_axes(
        ax,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=show_left_labels,
        show_bottom_labels=show_bottom_labels,
    )
    return mesh


def _plot_phase37_satellite_panel(
    ax,
    *,
    image_path: Path | None,
    extent: tuple[float, float, float, float],
    use_cartopy: bool,
    transform,
    show_left_labels: bool,
    show_bottom_labels: bool,
) -> None:
    west, east, south, north = extent
    if image_path is not None and image_path.is_file():
        image = mpimg.imread(str(image_path))
        image_kwargs = {
            "extent": extent,
            "origin": "upper",
            "aspect": "auto",
            "interpolation": "nearest",
            "rasterized": True,
        }
        if transform is not None:
            image_kwargs["transform"] = transform
        ax.imshow(image, **image_kwargs)
    else:
        ax.text(
            0.5,
            0.5,
            "No S2 Image",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=11,
            color="gray",
        )

    ax.set_title("S2 RGB", fontsize=11, fontweight="bold")
    ax.set_aspect("equal")
    if use_cartopy:
        ax.set_extent((west, east, south, north), crs=transform)
        ax.coastlines(linewidth=0.5, color="black")
    else:
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)

    _configure_geo_axes(
        ax,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=show_left_labels,
        show_bottom_labels=show_bottom_labels,
    )


def _present_class_ids(surface: xr.DataArray) -> tuple[int, ...]:
    """Return sorted class ids that actually appear on one plotted surface."""

    values = np.asarray(surface.values, dtype=np.float32)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return ()
    return tuple(sorted({int(value) for value in finite.astype(np.int64)}))


def _draw_discrete_class_legend(
    ax,
    style: DiscreteStyle,
    *,
    present_class_ids: Iterable[int] | None = None,
    title: str | None = None,
) -> None:
    """Draw a filtered categorical legend using one stable class style."""

    if title:
        ax.set_title(title, fontsize=10, fontweight="bold", pad=5)

    selected_source = style.ticks if present_class_ids is None else present_class_ids
    selected = tuple(int(class_id) for class_id in selected_source)
    selected = tuple(class_id for class_id in selected if class_id in style.labels)
    if not selected:
        ax.text(
            0.5,
            0.5,
            "No valid classes",
            ha="center",
            va="center",
            fontsize=9,
            color="#5f6b7a",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
        return

    colors_by_id = {
        int(class_id): style.cmap.colors[index]
        for index, class_id in enumerate(style.ticks)
    }
    handles = [
        Patch(
            facecolor=colors_by_id[int(class_id)],
            edgecolor="none",
            label=style.labels[int(class_id)],
        )
        for class_id in selected
    ]
    ncol = 1 if len(handles) <= 3 else 2 if len(handles) <= 8 else 3
    ax.legend(
        handles=handles,
        loc="center",
        ncol=ncol,
        frameon=False,
        fontsize=8.5,
        handlelength=1.4,
        columnspacing=1.1,
    )
    ax.set_axis_off()


def _draw_class_legend(ax) -> None:
    _draw_discrete_class_legend(ax, classification_style())


def _draw_agreement_legend(ax) -> None:
    handles = [
        Patch(facecolor=AGREEMENT_COLORS[index - 1], edgecolor="none", label=str(index))
        for index in (1, 2, 3)
    ]
    ax.legend(
        handles=handles,
        title="Agreement Count",
        loc="center",
        ncol=3,
        frameon=False,
        fontsize=10,
        title_fontsize=11,
        handlelength=1.5,
        columnspacing=1.5,
    )
    ax.set_axis_off()


def _configure_geo_axes(
    ax,
    *,
    extent: tuple[float, float, float, float],
    use_cartopy: bool,
    transform,
    show_left_labels: bool,
    show_bottom_labels: bool,
) -> None:
    west, east, south, north = extent
    xticks = _geo_tick_values(west, east)
    yticks = _geo_tick_values(south, north)

    if use_cartopy:
        from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter

        ax.set_xticks(xticks, crs=transform)
        ax.set_yticks(yticks, crs=transform)
        ax.xaxis.set_major_formatter(LongitudeFormatter(zero_direction_label=False))
        ax.yaxis.set_major_formatter(LatitudeFormatter())
    else:
        ax.set_xticks(xticks)
        ax.set_yticks(yticks)
        ax.set_xticklabels([_format_longitude(value) for value in xticks])
        ax.set_yticklabels([_format_latitude(value) for value in yticks])

    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.tick_params(
        axis="x",
        bottom=show_bottom_labels,
        labelbottom=show_bottom_labels,
        top=False,
        labeltop=False,
        labelsize=9,
    )
    ax.tick_params(
        axis="y",
        left=show_left_labels,
        labelleft=show_left_labels,
        right=False,
        labelright=False,
        labelsize=9,
    )


def _geo_tick_values(min_value: float, max_value: float, *, target_count: int = 4) -> list[float]:
    lower = float(min(min_value, max_value))
    upper = float(max(min_value, max_value))
    span = upper - lower
    if np.isclose(span, 0.0):
        return [round(lower, 2)]

    chosen_step = GEO_TICK_STEPS[-1]
    preferred_step = span / max(target_count - 1, 1)
    for step in GEO_TICK_STEPS:
        if step >= preferred_step:
            chosen_step = step
            break

    start = np.ceil(lower / chosen_step) * chosen_step
    stop = np.floor(upper / chosen_step) * chosen_step
    if stop < start:
        return [round(lower, 2), round(upper, 2)]

    tick_values = np.arange(start, stop + chosen_step * 0.5, chosen_step)
    return [float(value) for value in np.round(tick_values, 2)]


def _format_longitude(value: float) -> str:
    suffix = "E" if value >= 0 else "W"
    return f"{abs(value):g}°{suffix}"


def _format_latitude(value: float) -> str:
    suffix = "N" if value >= 0 else "S"
    return f"{abs(value):g}°{suffix}"


def _surface_extent(surface: xr.DataArray) -> tuple[float, float, float, float]:
    y_dim, x_dim = _spatial_dims(surface)
    lon_values = np.asarray(surface.coords[x_dim].values, dtype=np.float64)
    lat_values = np.asarray(surface.coords[y_dim].values, dtype=np.float64)
    lon_step = _coord_step(lon_values)
    lat_step = _coord_step(lat_values)
    return (
        float(np.nanmin(lon_values) - lon_step / 2),
        float(np.nanmax(lon_values) + lon_step / 2),
        float(np.nanmin(lat_values) - lat_step / 2),
        float(np.nanmax(lat_values) + lat_step / 2),
    )


def _coord_step(values: np.ndarray) -> float:
    if values.size <= 1:
        return 1.0
    diffs = np.abs(np.diff(values))
    nonzero = diffs[diffs > 0]
    if nonzero.size == 0:
        return 1.0
    return float(nonzero[0])


def _spatial_dims(data: xr.Dataset | xr.DataArray) -> tuple[str, str]:
    dims = set(data.dims)
    if {"lat", "lon"}.issubset(dims):
        return "lat", "lon"
    if {"y", "x"}.issubset(dims):
        return "y", "x"
    raise ValueError(f"Expected spatial dims lat/lon or y/x, got {sorted(dims)}")


def _write_xarray_dataset_atomically(path: Path, dataset: xr.Dataset) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _temp_output_path(path)
    try:
        dataset.to_netcdf(temp_path, format="NETCDF4", engine="netcdf4")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _temp_output_path(path: Path) -> Path:
    return path.parent / f".{path.name}.tmp-{os.getpid()}-{uuid4().hex}"
