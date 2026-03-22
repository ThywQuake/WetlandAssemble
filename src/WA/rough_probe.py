"""Detailed HPC diagnostics for the rough binary comparison workflow."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from WA.comparison.focus_areas import RoughFocusArea, select_focus_areas
from WA.comparison.harmonize import (
    BINARY_WETLAND_THRESHOLD,
    BinaryAggregation,
    EmptyBinarySurfaceError,
    create_comparison_grid,
    dataset_supports_binary_comparison,
    harmonize_binary_dataset,
    select_comparison_slice,
)
from WA.comparison.rough_binary import RoughBinaryResult, compute_rough_binary_metrics
from WA.config import AppConfig, load_config
from WA.loader_probe import (
    collect_input_discovery,
    compact_discovery_preview,
    compact_discovery_summary,
    emit_progress,
    expand_dataset_ids,
    format_progress_value,
    indent_block,
    indent_json,
    make_json_safe,
    resolve_probe_bbox,
    summarize_dataset,
)
from WA.loaders import get_loader
from WA.loaders.base import BBox, DatasetLoader, DatasetMetadata, TimeRange
from WA.validation.gee_client import EarthEngineClient
from WA.validation.modis_reference import (
    ModisReferenceArtifact,
    download_modis_reference,
    resolve_modis_composite_window,
)

DEFAULT_MODIS_TARGET_MONTH = pd.Timestamp("2000-03-01")


@dataclass(frozen=True)
class RoughProbeOptions:
    """Options controlling rough comparison probing."""

    bbox: BBox
    bbox_label: str
    target_time: pd.Timestamp
    target_time_label: str
    resolution_deg: float
    aggregation: BinaryAggregation
    top_n: int
    top_n_per_region: int
    aoi_size_deg: float
    min_distance_deg: float
    preview_items: int
    download_modis: bool
    allow_interactive_auth: bool
    results_root: str
    fail_fast: bool
    gwd30_workers: int = 0
    gwd30_surface_path: str | None = None


@dataclass(frozen=True)
class PreparedRoughDataset:
    """Prepared loader + metadata bundle for one dataset."""

    dataset_id: str
    dataset_config: dict[str, Any]
    loader: DatasetLoader
    metadata: DatasetMetadata


@dataclass
class RoughDatasetProbeResult:
    """Per-dataset rough probe outcome."""

    dataset_id: str
    loader_type: str
    status: str
    effective_time_range: TimeRange | None
    metadata: dict[str, Any]
    discovery: dict[str, Any]
    dataset_summary: dict[str, Any] | None
    harmonized_summary: dict[str, Any] | None
    comparison_source_variable: str | None
    error: str | None = None
    traceback_text: str | None = None
    elapsed_seconds: float = 0.0


@dataclass
class RoughProbeRunResult:
    """Overall rough probe outcome."""

    status: str
    target_time: pd.Timestamp
    modis_window: tuple[pd.Timestamp, pd.Timestamp] | None
    reference_grid_summary: dict[str, Any]
    dataset_results: list[RoughDatasetProbeResult]
    participant_dataset_ids: list[str]
    metrics_rows: list[dict[str, Any]] | None
    disagreement_summary: dict[str, Any] | None
    focus_areas: list[dict[str, Any]] | None
    modis_artifacts: list[dict[str, Any]] | None
    warnings: list[str]


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for rough workflow probing."""

    parser = argparse.ArgumentParser(
        description=(
            "Probe the rough binary comparison workflow against the real HPC dataset "
            "paths with detailed diagnostics."
        )
    )
    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help="Dataset id to include. Can be repeated or contain comma-separated ids.",
    )
    parser.add_argument(
        "--bbox",
        help="Bounding box as min_lon,min_lat,max_lon,max_lat. Overrides --region.",
    )
    parser.add_argument(
        "--region",
        help="Region name from config/datasets.yaml regions section.",
    )
    parser.add_argument(
        "--target-time",
        help="Target comparison date. Normalized to the first day of its month.",
    )
    parser.add_argument(
        "--resolution-deg",
        type=float,
        default=0.25,
        help="Comparison grid resolution in degrees.",
    )
    parser.add_argument(
        "--aggregation",
        choices=("mean", "max"),
        default="mean",
        help="Aggregation for daily/4-day products when reduced to monthly comparison.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=8,
        help="Maximum number of focus AOIs to report.",
    )
    parser.add_argument(
        "--top-n-per-region",
        type=int,
        default=2,
        help="Maximum number of focus AOIs per region before spillover selection.",
    )
    parser.add_argument(
        "--aoi-size-deg",
        type=float,
        default=2.0,
        help="Bounding-box size in degrees for each focus AOI.",
    )
    parser.add_argument(
        "--min-distance-deg",
        type=float,
        default=3.0,
        help="Minimum distance in degrees between selected focus AOIs.",
    )
    parser.add_argument(
        "--preview-items",
        type=int,
        default=5,
        help="Number of preview items to include in detailed summaries.",
    )
    parser.add_argument(
        "--download-modis",
        action="store_true",
        help="Also attempt MODIS downloads for the selected focus AOIs.",
    )
    parser.add_argument(
        "--allow-interactive-auth",
        action="store_true",
        help="Allow interactive Earth Engine authentication if credentials are missing.",
    )
    parser.add_argument(
        "--results-root",
        default="results",
        help="Root directory for optional MODIS artifact output.",
    )
    parser.add_argument(
        "--gwd30-workers",
        type=int,
        default=0,
        help=(
            "Parallel worker count for GWD30 rough loading "
            "(0=auto from WA_GWD30_WORKERS or SLURM_CPUS_PER_TASK, else 1)."
        ),
    )
    parser.add_argument(
        "--gwd30-surface-path",
        help="Optional precomputed GWD30 coarse surface NetCDF/DataArray path.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Exit the probe loop after the first dataset failure.",
    )
    parser.add_argument(
        "--json-out",
        help="Optional path for a JSON dump of the rough probe results.",
    )
    parser.add_argument(
        "--dataset-config",
        default="config/datasets.yaml",
        help="Path to the dataset config file.",
    )
    parser.add_argument(
        "--gee-config",
        default="config/gee_config.yaml",
        help="Path to the GEE config file.",
    )
    return parser


def derive_target_time(
    metadata_by_dataset: dict[str, DatasetMetadata],
    requested_target_time: str | None,
) -> tuple[pd.Timestamp, str]:
    """Resolve the target comparison month."""

    if requested_target_time is not None:
        timestamp = normalize_target_time(pd.Timestamp(requested_target_time))
        return timestamp, "cli_target_time"

    dynamic_windows = [
        window
        for dataset_id, metadata in metadata_by_dataset.items()
        if dataset_supports_binary_comparison(dataset_id)
        for window in [_metadata_month_window(metadata)]
        if window is not None
    ]

    if not dynamic_windows:
        return DEFAULT_MODIS_TARGET_MONTH, "derived_default_modis_month"

    candidate_months = sorted({window[0] for window in dynamic_windows})
    scored_candidates = [
        (
            sum(start <= candidate <= end for start, end in dynamic_windows),
            candidate,
        )
        for candidate in candidate_months
    ]
    best_score = max(score for score, _ in scored_candidates)
    best_candidate = min(candidate for score, candidate in scored_candidates if score == best_score)
    return best_candidate, "derived_max_dynamic_participants"


def normalize_target_time(target_time: pd.Timestamp) -> pd.Timestamp:
    """Normalize any timestamp to the first day of its month."""

    return target_time.to_period("M").to_timestamp()


def build_target_time_range(
    metadata: DatasetMetadata,
    target_time: pd.Timestamp,
) -> TimeRange | None:
    """Build the one-month load window for a dataset at the target comparison time."""

    if metadata.is_static:
        return None

    month_window = _metadata_month_window(metadata)
    if month_window is None:
        return None

    month_start, month_end = month_window
    normalized_target = normalize_target_time(target_time)
    if not month_start <= normalized_target <= month_end:
        return None

    target_end = normalized_target + pd.offsets.MonthEnd(0)
    return normalized_target.strftime("%Y-%m-%d"), pd.Timestamp(target_end).strftime("%Y-%m-%d")


def summarize_harmonized_surface(
    surface: xr.DataArray,
    *,
    preview_items: int,
) -> dict[str, Any]:
    """Summarize one harmonized rough-comparison surface."""

    values = np.asarray(surface.values, dtype=float)
    summary: dict[str, Any] = {
        "dims": list(surface.dims),
        "shape": [int(size) for size in surface.shape],
        "dtype": str(surface.dtype),
        "preview": [make_json_safe(value) for value in values.reshape(-1)[:preview_items]],
        "non_null_count": int(np.count_nonzero(~pd.isna(values))),
        "wetland_cell_count": int(
            np.count_nonzero((~pd.isna(values)) & (values >= BINARY_WETLAND_THRESHOLD))
        ),
    }
    if np.all(np.isnan(values)):
        summary["min"] = None
        summary["max"] = None
        summary["mean"] = None
    else:
        summary["min"] = float(np.nanmin(values))
        summary["max"] = float(np.nanmax(values))
        summary["mean"] = float(np.nanmean(values))
    return summary


def summarize_reference_grid(reference_grid: xr.DataArray) -> dict[str, Any]:
    """Summarize the shared comparison grid."""

    return {
        "dims": list(reference_grid.dims),
        "shape": [int(size) for size in reference_grid.shape],
        "lat_range": [
            float(reference_grid["lat"].min().item()),
            float(reference_grid["lat"].max().item()),
        ],
        "lon_range": [
            float(reference_grid["lon"].min().item()),
            float(reference_grid["lon"].max().item()),
        ],
        "crs": str(reference_grid.rio.crs),
    }


def summarize_disagreement(
    rough_result: RoughBinaryResult,
    *,
    preview_items: int,
) -> dict[str, Any]:
    """Summarize the disagreement surface and its highest-scoring cells."""

    score_df = (
        rough_result.disagreement_score.rename("disagreement_score").to_dataframe().reset_index()
    )
    score_df = score_df.dropna(subset=["disagreement_score"])
    if score_df.empty:
        return {"non_null_count": 0, "top_cells": []}

    participant_df = (
        rough_result.participant_count.rename("participant_count").to_dataframe().reset_index()
    )
    vote_df = (
        rough_result.wetland_vote_fraction.rename("wetland_vote_fraction")
        .to_dataframe()
        .reset_index()
    )
    merged = score_df.merge(participant_df, on=["lat", "lon"], how="left").merge(
        vote_df,
        on=["lat", "lon"],
        how="left",
    )
    ordered = merged.sort_values("disagreement_score", ascending=False).head(preview_items)
    top_cells = [
        {
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "disagreement_score": float(row["disagreement_score"]),
            "participant_count": int(row["participant_count"]),
            "wetland_vote_fraction": float(row["wetland_vote_fraction"]),
        }
        for _, row in ordered.iterrows()
    ]

    values = np.asarray(rough_result.disagreement_score.values, dtype=float)
    return {
        "non_null_count": int(np.count_nonzero(~pd.isna(values))),
        "min": float(np.nanmin(values)),
        "max": float(np.nanmax(values)),
        "mean": float(np.nanmean(values)),
        "top_cells": top_cells,
    }


def _load_precomputed_gwd30_surface(surface_path: str) -> xr.DataArray:
    """Load a precomputed GWD30 coarse surface from NetCDF/DataArray storage."""

    path = Path(surface_path)
    if not path.exists():
        raise FileNotFoundError(f"Precomputed GWD30 surface not found: {path}")

    try:
        dataset = xr.open_dataset(path)
    except Exception:
        dataset = None
    if dataset is not None:
        try:
            if "wetland_fraction" in dataset.data_vars:
                surface = dataset["wetland_fraction"].load()
                return surface
        finally:
            dataset.close()

    data_array = xr.open_dataarray(path)
    try:
        return data_array.load()
    finally:
        data_array.close()


def probe_prepared_dataset(
    prepared: PreparedRoughDataset,
    options: RoughProbeOptions,
    reference_grid: xr.DataArray,
) -> tuple[RoughDatasetProbeResult, xr.DataArray | None]:
    """Probe one prepared dataset for rough comparison participation."""

    start_time = perf_counter()
    dataset_id = prepared.dataset_id
    effective_time_range = build_target_time_range(prepared.metadata, options.target_time)

    if not dataset_supports_binary_comparison(dataset_id):
        emit_progress(f"{dataset_id}: collect input discovery")
        discovery = collect_input_discovery(
            prepared.loader,
            options.bbox,
            effective_time_range,
            preview_items=options.preview_items,
        )
        emit_progress(f"{dataset_id}: discovery {compact_discovery_summary(discovery)}")
        preview_text = compact_discovery_preview(discovery)
        if preview_text is not None:
            emit_progress(f"{dataset_id}: discovery preview {preview_text}")
        return (
            RoughDatasetProbeResult(
                dataset_id=dataset_id,
                loader_type=str(prepared.dataset_config["loader_type"]),
                status="skipped_not_eligible",
                effective_time_range=effective_time_range,
                metadata=asdict(prepared.metadata),
                discovery=discovery,
                dataset_summary=None,
                harmonized_summary=None,
                comparison_source_variable=None,
                elapsed_seconds=perf_counter() - start_time,
            ),
            None,
        )

    if not prepared.metadata.is_static and effective_time_range is None:
        return (
            RoughDatasetProbeResult(
                dataset_id=dataset_id,
                loader_type=str(prepared.dataset_config["loader_type"]),
                status="skipped_time_window",
                effective_time_range=None,
                metadata=asdict(prepared.metadata),
                discovery={},
                dataset_summary=None,
                harmonized_summary=None,
                comparison_source_variable=None,
                elapsed_seconds=perf_counter() - start_time,
            ),
            None,
        )

    emit_progress(f"{dataset_id}: collect input discovery")
    discovery = collect_input_discovery(
        prepared.loader,
        options.bbox,
        effective_time_range,
        preview_items=options.preview_items,
    )
    emit_progress(f"{dataset_id}: discovery {compact_discovery_summary(discovery)}")
    preview_text = compact_discovery_preview(discovery)
    if preview_text is not None:
        emit_progress(f"{dataset_id}: discovery preview {preview_text}")

    try:
        emit_progress(f"{dataset_id}: load dataset")
        rough_surface_loader = getattr(prepared.loader, "load_rough_binary_surface", None)
        if dataset_id == "gwd30" and options.gwd30_surface_path is not None:
            selected = _load_precomputed_gwd30_surface(options.gwd30_surface_path)
            selected = selected.astype(np.float32)
            selected.attrs.setdefault("dataset_id", "gwd30")
            selected.attrs.setdefault("comparison_source_variable", "wetland_class")
            selected.attrs.setdefault("comparison_aggregation", options.aggregation)
            selected.attrs.setdefault("comparison_time", options.target_time.isoformat())
            selected.attrs.setdefault("comparison_source_time", options.target_time.isoformat())
            dataset_summary = {
                "strategy": "precomputed_surface",
                "surface_path": options.gwd30_surface_path,
            }
            emit_progress(
                f"{dataset_id}: loaded precomputed surface "
                f"{options.gwd30_surface_path}"
            )
        elif (
            dataset_id == "gwd30"
            and callable(rough_surface_loader)
            and effective_time_range is not None
        ):
            selected, load_trace = rough_surface_loader(
                bbox=options.bbox,
                time_range=effective_time_range,
                reference_grid=reference_grid,
                aggregation=options.aggregation,
                target_time=options.target_time,
                worker_count=options.gwd30_workers,
            )
            dataset_summary = {
                "strategy": "direct_to_reference_grid",
                "load_trace": make_json_safe(load_trace),
            }
            emit_progress(
                f"{dataset_id}: direct rough load produced "
                f"{surface_non_null_count(selected)} coarse cell(s)"
            )
        else:
            dataset = prepared.loader.load(bbox=options.bbox, time_range=effective_time_range)
            dataset_summary = summarize_dataset(dataset, preview_items=options.preview_items)
            emit_progress(
                f"{dataset_id}: dataset sizes {dataset_summary['sizes']} "
                f"approx_nbytes={dataset_summary['approx_nbytes']}"
            )
            emit_progress(f"{dataset_id}: harmonize binary surface")
            harmonized = harmonize_binary_dataset(
                dataset_id,
                dataset,
                reference_grid=reference_grid,
                aggregation=options.aggregation,
            )
            selected = select_comparison_slice(harmonized, options.target_time)
        surface_summary = summarize_harmonized_surface(
            selected,
            preview_items=options.preview_items,
        )
        emit_progress(
            f"{dataset_id}: harmonized non_null={surface_summary['non_null_count']} "
            f"wetland_cells={surface_summary['wetland_cell_count']}"
        )
        result = RoughDatasetProbeResult(
            dataset_id=dataset_id,
            loader_type=str(prepared.dataset_config["loader_type"]),
            status="participating",
            effective_time_range=effective_time_range,
            metadata=asdict(prepared.metadata),
            discovery=discovery,
            dataset_summary=dataset_summary,
            harmonized_summary=surface_summary,
            comparison_source_variable=str(selected.attrs.get("comparison_source_variable")),
            elapsed_seconds=perf_counter() - start_time,
        )
        return result, selected
    except EmptyBinarySurfaceError as exc:
        emit_progress(f"{dataset_id}: empty harmonized surface")
        return (
            RoughDatasetProbeResult(
                dataset_id=dataset_id,
                loader_type=str(prepared.dataset_config["loader_type"]),
                status="failed_empty_harmonized_surface",
                effective_time_range=effective_time_range,
                metadata=asdict(prepared.metadata),
                discovery=discovery,
                dataset_summary=dataset_summary if "dataset_summary" in locals() else None,
                harmonized_summary=None,
                comparison_source_variable=exc.source_variable,
                error=str(exc),
                traceback_text=None,
                elapsed_seconds=perf_counter() - start_time,
            ),
            None,
        )
    except Exception as exc:
        emit_progress(f"{dataset_id}: failed with {type(exc).__name__}")
        return (
            RoughDatasetProbeResult(
                dataset_id=dataset_id,
                loader_type=str(prepared.dataset_config["loader_type"]),
                status="failed",
                effective_time_range=effective_time_range,
                metadata=asdict(prepared.metadata),
                discovery=discovery,
                dataset_summary=None,
                harmonized_summary=None,
                comparison_source_variable=None,
                error=f"{type(exc).__name__}: {exc}",
                traceback_text=traceback.format_exc(),
                elapsed_seconds=perf_counter() - start_time,
            ),
            None,
        )


def surface_non_null_count(surface: xr.DataArray) -> int:
    """Count non-null cells in a 2D coarse comparison surface."""

    return int(surface.notnull().sum().item())


def run_rough_probe(
    app_config: AppConfig,
    dataset_ids: list[str],
    options: RoughProbeOptions,
) -> RoughProbeRunResult:
    """Run the rough workflow probe for the selected datasets."""

    prepared, preparation_results = prepare_datasets(app_config, dataset_ids)
    reference_grid = create_comparison_grid(
        options.bbox,
        resolution_deg=options.resolution_deg,
    )
    dataset_results = list(preparation_results)
    participant_surfaces: dict[str, xr.DataArray] = {}

    for prepared_dataset in prepared:
        emit_progress(f"{prepared_dataset.dataset_id}: rough probe start")
        result, surface = probe_prepared_dataset(prepared_dataset, options, reference_grid)
        dataset_results.append(result)
        if surface is not None:
            participant_surfaces[prepared_dataset.dataset_id] = surface
        emit_progress(
            f"{prepared_dataset.dataset_id}: rough probe done with status={result.status}"
        )
        if result.status == "failed" and options.fail_fast:
            break

    modis_window = resolve_modis_composite_window(options.target_time)
    metrics_rows: list[dict[str, Any]] | None = None
    disagreement_summary: dict[str, Any] | None = None
    focus_area_dicts: list[dict[str, Any]] | None = None
    modis_artifacts: list[dict[str, Any]] | None = None
    warnings: list[str] = []
    status = "insufficient_participants"

    if len(participant_surfaces) >= 2:
        emit_progress("rough: compute pairwise metrics")
        rough_result = compute_rough_binary_metrics(participant_surfaces)
        metrics_rows = rough_result.metrics.to_dict("records")
        zero_overlap_rows = [
            row
            for row in metrics_rows
            if int(row["valid_cell_count"]) == 0
        ]
        if zero_overlap_rows:
            warnings.append(
                f"{len(zero_overlap_rows)} pairwise metric rows have valid_cell_count=0"
            )
        disagreement_summary = summarize_disagreement(
            rough_result,
            preview_items=options.preview_items,
        )
        emit_progress("rough: select focus AOIs")
        focus_areas = select_focus_areas(
            rough_result.disagreement_score,
            rough_result.participant_count,
            target_time=options.target_time,
            wetland_vote_fraction=rough_result.wetland_vote_fraction,
            top_n=options.top_n,
            top_n_per_region=options.top_n_per_region,
            aoi_size_deg=options.aoi_size_deg,
            min_distance_deg=options.min_distance_deg,
        )
        focus_area_dicts = [asdict(focus_area) for focus_area in focus_areas]
        status = "completed"

        if options.download_modis:
            emit_progress("rough: download MODIS artifacts")
            modis_artifacts = [
                asdict(artifact)
                for artifact in run_modis_probe(app_config, focus_areas, options)
            ]

    failed_count = sum(
        result.status.startswith("failed") for result in dataset_results
    )
    skipped_count = sum(
        result.status.startswith("skipped") for result in dataset_results
    )
    if len(participant_surfaces) >= 2:
        if failed_count > 0:
            status = "completed_with_failures"
        elif skipped_count > 0:
            status = "completed_with_skips"
        else:
            status = "completed"
    elif failed_count > 0:
        status = "failed"

    return RoughProbeRunResult(
        status=status,
        target_time=options.target_time,
        modis_window=modis_window,
        reference_grid_summary=summarize_reference_grid(reference_grid),
        dataset_results=dataset_results,
        participant_dataset_ids=sorted(participant_surfaces),
        metrics_rows=metrics_rows,
        disagreement_summary=disagreement_summary,
        focus_areas=focus_area_dicts,
        modis_artifacts=modis_artifacts,
        warnings=warnings,
    )


def prepare_datasets(
    app_config: AppConfig,
    dataset_ids: list[str],
) -> tuple[list[PreparedRoughDataset], list[RoughDatasetProbeResult]]:
    """Instantiate loaders and collect metadata before rough probing."""

    prepared: list[PreparedRoughDataset] = []
    failures: list[RoughDatasetProbeResult] = []
    for dataset_id in dataset_ids:
        dataset_config = app_config.datasets[dataset_id]
        try:
            loader = get_loader(dataset_id, dataset_config)
            metadata = loader.metadata()
            prepared.append(
                PreparedRoughDataset(
                    dataset_id=dataset_id,
                    dataset_config=dataset_config,
                    loader=loader,
                    metadata=metadata,
                )
            )
        except Exception as exc:
            failures.append(
                RoughDatasetProbeResult(
                    dataset_id=dataset_id,
                    loader_type=str(dataset_config.get("loader_type", "unknown")),
                    status="failed_prepare",
                    effective_time_range=None,
                    metadata={},
                    discovery={},
                    dataset_summary=None,
                    harmonized_summary=None,
                    comparison_source_variable=None,
                    error=f"{type(exc).__name__}: {exc}",
                    traceback_text=traceback.format_exc(),
                    elapsed_seconds=0.0,
                )
            )
    return prepared, failures


def run_modis_probe(
    app_config: AppConfig,
    focus_areas: list[RoughFocusArea],
    options: RoughProbeOptions,
) -> list[ModisReferenceArtifact]:
    """Optionally download MODIS reference artifacts for the focus AOIs."""

    client = EarthEngineClient.from_config(app_config.gee)
    artifacts: list[ModisReferenceArtifact] = []
    for focus_area in focus_areas:
        artifacts.append(
            download_modis_reference(
                focus_area,
                client,
                results_root=options.results_root,
                allow_interactive_auth=options.allow_interactive_auth,
            )
        )
    return artifacts


def render_rough_probe_report(
    app_config: AppConfig,
    dataset_ids: list[str],
    options: RoughProbeOptions,
    run_result: RoughProbeRunResult,
) -> str:
    """Render a detailed human-readable rough probe report."""

    lines = [
        "=== WA HPC Rough Probe ===",
        f"Dataset config: {app_config.dataset_config_path}",
        f"GEE config: {app_config.gee_config_path}",
        f"GEE project id: {app_config.gee['gee_project_id']}",
        f"Datasets: {', '.join(dataset_ids)}",
        f"Effective bbox source: {options.bbox_label}",
        f"Effective bbox: {options.bbox}",
        f"Target time source: {options.target_time_label}",
        f"Target time: {options.target_time.isoformat()}",
        f"MODIS window: {run_result.modis_window}",
        f"Resolution (deg): {options.resolution_deg}",
        f"Aggregation: {options.aggregation}",
        f"Download MODIS: {options.download_modis}",
        "",
        "reference_grid:",
        indent_json(run_result.reference_grid_summary),
        "",
    ]

    for index, result in enumerate(run_result.dataset_results, start=1):
        lines.extend(
            [
                f"--- [{index}/{len(run_result.dataset_results)}] "
                f"{result.dataset_id} ({result.loader_type}) ---",
                f"status: {result.status}",
                f"elapsed_seconds: {result.elapsed_seconds:.3f}",
                f"effective_time_range: {result.effective_time_range}",
                f"comparison_source_variable: {result.comparison_source_variable}",
                "metadata:",
                indent_json(result.metadata),
                "discovery:",
                indent_json(result.discovery),
            ]
        )
        if result.dataset_summary is not None:
            lines.extend(["dataset_summary:", indent_json(result.dataset_summary)])
        if result.harmonized_summary is not None:
            lines.extend(["harmonized_summary:", indent_json(result.harmonized_summary)])
        if result.error is not None:
            lines.extend(["error:", f"  {result.error}"])
            if result.traceback_text is not None and result.status in {"failed", "failed_prepare"}:
                lines.extend(["traceback:", indent_block(result.traceback_text.rstrip())])
        lines.append("")

    lines.extend(
        [
            "=== Rough Comparison ===",
            f"overall_status: {run_result.status}",
            f"participant_datasets: {run_result.participant_dataset_ids}",
        ]
    )
    if run_result.metrics_rows is None:
        lines.append("metrics: unavailable (fewer than two participating datasets)")
    else:
        lines.extend(["metrics:", indent_json({"rows": run_result.metrics_rows})])

    if run_result.disagreement_summary is not None:
        lines.extend(["disagreement_summary:", indent_json(run_result.disagreement_summary)])

    if run_result.focus_areas is not None:
        lines.extend(["focus_areas:", indent_json({"items": run_result.focus_areas})])

    if run_result.modis_artifacts is not None:
        lines.extend(["modis_artifacts:", indent_json({"items": run_result.modis_artifacts})])

    if run_result.warnings:
        lines.extend(["warnings:", indent_json({"items": run_result.warnings})])

    status_counts: dict[str, int] = {}
    for result in run_result.dataset_results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1
    failed_count = sum(
        result.status.startswith("failed") for result in run_result.dataset_results
    )
    skipped_count = sum(
        result.status.startswith("skipped") for result in run_result.dataset_results
    )

    lines.extend(
        [
            "",
            "=== Summary ===",
            f"dataset_status_counts: {status_counts}",
            f"failed_dataset_count: {failed_count}",
            f"skipped_dataset_count: {skipped_count}",
            f"participating_dataset_count: {len(run_result.participant_dataset_ids)}",
            f"participant_count: {len(run_result.participant_dataset_ids)}",
            f"metrics_available: {run_result.metrics_rows is not None}",
        ]
    )
    return "\n".join(lines)


def options_from_args(
    args: argparse.Namespace,
    app_config: AppConfig,
    metadata_by_dataset: dict[str, DatasetMetadata],
) -> RoughProbeOptions:
    """Resolve typed rough probe options from parsed args."""

    bbox_value, bbox_label = resolve_probe_bbox(
        app_config,
        bbox_text=args.bbox,
        region_name=args.region,
        unsafe_full_spatial_scan=False,
    )
    if bbox_value is None:
        raise ValueError("Rough probe requires a bounded spatial window")

    target_time, target_time_label = derive_target_time(
        metadata_by_dataset,
        requested_target_time=args.target_time,
    )
    return RoughProbeOptions(
        bbox=bbox_value,
        bbox_label=bbox_label,
        target_time=target_time,
        target_time_label=target_time_label,
        resolution_deg=float(args.resolution_deg),
        aggregation=args.aggregation,
        top_n=int(args.top_n),
        top_n_per_region=int(args.top_n_per_region),
        aoi_size_deg=float(args.aoi_size_deg),
        min_distance_deg=float(args.min_distance_deg),
        preview_items=int(args.preview_items),
        download_modis=bool(args.download_modis),
        allow_interactive_auth=bool(args.allow_interactive_auth),
        results_root=str(args.results_root),
        fail_fast=bool(args.fail_fast),
        gwd30_workers=int(getattr(args, "gwd30_workers", 0)),
        gwd30_surface_path=(
            None
            if getattr(args, "gwd30_surface_path", None) is None
            else str(args.gwd30_surface_path)
        ),
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the rough binary probe."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    emit_progress("load config")
    app_config = load_config(args.dataset_config, args.gee_config)
    emit_progress("resolve dataset selection")
    dataset_ids = expand_dataset_ids(app_config, args.dataset)
    emit_progress("prepare loaders and metadata")
    prepared, preparation_failures = prepare_datasets(app_config, dataset_ids)
    metadata_by_dataset = {
        prepared_dataset.dataset_id: prepared_dataset.metadata for prepared_dataset in prepared
    }
    emit_progress("resolve rough probe options")
    options = options_from_args(args, app_config, metadata_by_dataset)
    emit_progress(
        "rough probe start "
        f"datasets={len(dataset_ids)} bbox={format_progress_value(options.bbox)} "
        f"target_time={options.target_time.isoformat()}"
    )

    run_result = run_rough_probe(app_config, dataset_ids, options)
    if preparation_failures:
        run_result.dataset_results = preparation_failures + run_result.dataset_results
        if run_result.status == "completed":
            run_result.status = "completed_with_prepare_failures"

    report = render_rough_probe_report(app_config, dataset_ids, options, run_result)
    print(report)

    if args.json_out:
        payload = {
            "dataset_config": str(app_config.dataset_config_path),
            "gee_config": str(app_config.gee_config_path),
            "dataset_ids": dataset_ids,
            "options": asdict(options),
            "run_result": asdict(run_result),
        }
        json_path = Path(args.json_out)
        try:
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(
                json.dumps(make_json_safe(payload), indent=2, sort_keys=True, allow_nan=False),
                encoding="utf-8",
            )
        except Exception as exc:
            print(
                f"[error] failed to write rough probe JSON output to {json_path}: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return 1

    dataset_failed = any(
        result.status.startswith("failed") for result in run_result.dataset_results
    )
    modis_failed = any(
        artifact["status"] in {"gee_auth_failed", "download_failed", "download_limit_exceeded"}
        for artifact in (run_result.modis_artifacts or [])
    )
    if dataset_failed or modis_failed or run_result.metrics_rows is None:
        return 1
    return 0


def _metadata_month_window(
    metadata: DatasetMetadata,
) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    if metadata.is_static or metadata.temporal_coverage is None:
        return None

    start_text, end_text = metadata.temporal_coverage
    if start_text is None or end_text is None:
        return None

    start = max(normalize_target_time(pd.Timestamp(start_text)), DEFAULT_MODIS_TARGET_MONTH)
    end = normalize_target_time(pd.Timestamp(end_text))
    if start > end:
        return None
    return start, end
