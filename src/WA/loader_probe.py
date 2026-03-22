"""Helpers for probing real dataset loaders on HPC with verbose diagnostics."""

from __future__ import annotations

import argparse
import json
import math
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from WA.config import AppConfig, load_config
from WA.loaders import get_loader
from WA.loaders.base import BBox, DatasetLoader, TimeRange
from WA.loaders.registry import OUT_OF_SCOPE_DATASET_IDS

DEFAULT_PROBE_BBOX: BBox = (-61.0, -5.0, -60.0, -4.0)
DEFAULT_PROBE_BBOX_LABEL = "default_amazon_probe"


@dataclass(frozen=True)
class ProbeOptions:
    """Options controlling loader probe behavior."""

    bbox: BBox | None
    bbox_label: str
    time_range: TimeRange | None
    compute_sample: bool
    metadata_only: bool
    sample_size: int
    preview_items: int
    fail_fast: bool


@dataclass
class ProbeResult:
    """Per-dataset probe outcome."""

    dataset_id: str
    loader_type: str
    status: str
    effective_bbox: BBox | None
    effective_time_range: TimeRange | None
    metadata: dict[str, Any]
    discovery: dict[str, Any]
    dataset_summary: dict[str, Any] | None
    sample_summary: dict[str, Any] | None
    elapsed_seconds: float
    error: str | None = None
    traceback_text: str | None = None


def emit_progress(message: str) -> None:
    """Print a timestamped progress line immediately."""

    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}", flush=True)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the HPC probe script."""

    parser = argparse.ArgumentParser(
        description=(
            "Probe every in-scope wetland loader against real HPC data and print "
            "rich diagnostics."
        )
    )
    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help="Dataset id to probe. Can be repeated or contain comma-separated ids.",
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
        "--time-range",
        help="Time range as start,end. If omitted, a safe probe window is derived per dataset.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only print metadata and input-discovery diagnostics; skip loader.load().",
    )
    parser.add_argument(
        "--skip-compute",
        action="store_true",
        help="Skip tiny sample materialization after loader.load().",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=2,
        help="Per-dimension item count for the tiny sample compute.",
    )
    parser.add_argument(
        "--preview-items",
        type=int,
        default=5,
        help="Number of preview coordinate/sample values to print.",
    )
    parser.add_argument(
        "--unsafe-full-spatial-scan",
        action="store_true",
        help="Disable the default safe bbox and let loaders use their full spatial domain.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Exit after the first dataset failure.",
    )
    parser.add_argument(
        "--json-out",
        help="Optional path for a JSON dump of all probe results.",
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


def parse_bbox(text: str) -> BBox:
    """Parse a bbox string into a typed tuple."""

    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 4:
        raise ValueError("Expected bbox as min_lon,min_lat,max_lon,max_lat")

    bbox: BBox = (
        float(parts[0]),
        float(parts[1]),
        float(parts[2]),
        float(parts[3]),
    )
    min_lon, min_lat, max_lon, max_lat = bbox
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError("Invalid bbox: minimums must be smaller than maximums")
    return bbox


def parse_time_range(text: str) -> TimeRange:
    """Parse a time range string into a typed tuple."""

    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        raise ValueError("Expected time range as start,end")
    start, end = parts
    if pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError("Invalid time range: start is after end")
    return start, end


def expand_dataset_ids(app_config: AppConfig, requested: list[str]) -> list[str]:
    """Resolve requested dataset ids or return all in-scope datasets."""

    ordered_dataset_ids = list(app_config.datasets.keys())
    if not requested:
        return [
            dataset_id
            for dataset_id in ordered_dataset_ids
            if dataset_id not in OUT_OF_SCOPE_DATASET_IDS
        ]

    flattened: list[str] = []
    for entry in requested:
        flattened.extend([part.strip() for part in entry.split(",") if part.strip()])

    unknown = sorted(set(flattened) - set(ordered_dataset_ids))
    if unknown:
        raise KeyError(f"Unknown dataset ids: {', '.join(unknown)}")

    return flattened


def resolve_probe_bbox(
    app_config: AppConfig,
    *,
    bbox_text: str | None,
    region_name: str | None,
    unsafe_full_spatial_scan: bool,
) -> tuple[BBox | None, str]:
    """Resolve the effective bbox and describe where it came from."""

    if bbox_text is not None:
        return parse_bbox(bbox_text), "cli_bbox"

    if region_name is not None:
        try:
            region_bbox = app_config.regions[region_name]["bbox"]
        except KeyError as exc:
            available_regions = ", ".join(sorted(app_config.regions))
            raise KeyError(
                f"Unknown region {region_name!r}. Available regions: {available_regions}"
            ) from exc
        region_bbox_text = ",".join(str(value) for value in region_bbox)
        return parse_bbox(region_bbox_text), f"config_region:{region_name}"

    if unsafe_full_spatial_scan:
        return None, "full_spatial_domain"

    return DEFAULT_PROBE_BBOX, DEFAULT_PROBE_BBOX_LABEL


def derive_probe_time_range(
    loader: DatasetLoader,
    *,
    requested_time_range: TimeRange | None,
) -> TimeRange | None:
    """Resolve a safe time range for probing one dataset."""

    if requested_time_range is not None:
        return requested_time_range

    metadata = loader.metadata()
    if metadata.is_static or metadata.temporal_coverage is None:
        return None

    start_text, _ = metadata.temporal_coverage
    if start_text is None:
        return None

    start = pd.Timestamp(start_text)
    end = start + pd.offsets.MonthEnd(0)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def collect_input_discovery(
    loader: DatasetLoader,
    bbox: BBox | None,
    time_range: TimeRange | None,
    *,
    preview_items: int,
) -> dict[str, Any]:
    """Collect file-system level discovery hints before loading a dataset."""

    discovery: dict[str, Any] = {
        "base_path": str(loader.base_path),
        "path_exists": loader.base_path.exists(),
        "loader_type": loader.config["loader_type"],
    }

    file_value = loader.config.get("file")
    if isinstance(file_value, str):
        target = loader.base_path / file_value
        discovery["target_file"] = str(target)
        discovery["target_file_exists"] = target.exists()

    files_value = loader.config.get("files")
    if isinstance(files_value, dict):
        discovery["named_files"] = {
            name: {
                "path": str(loader.base_path / relative_path),
                "exists": (loader.base_path / relative_path).exists(),
            }
            for name, relative_path in files_value.items()
        }

    subdirectories = loader.config.get("subdirectories")
    if isinstance(subdirectories, dict):
        discovery["subdirectories"] = {
            name: {
                "path": str(loader.base_path / relative_path),
                "tif_count": len(list((loader.base_path / relative_path).glob("*.tif"))),
            }
            for name, relative_path in subdirectories.items()
        }

    pattern_value = loader.config.get("pattern")
    if isinstance(pattern_value, str):
        discovery["pattern"] = pattern_value

    candidate_files_method = getattr(loader, "_candidate_files", None)
    discover_tiles_method = getattr(loader, "_discover_tiles", None)
    discover_files_method = getattr(loader, "_discover_files", None)

    if callable(candidate_files_method):
        files = list(candidate_files_method(time_range))
        discovery["matched_files"] = len(files)
        discovery["matched_file_preview"] = [str(path) for path in files[:preview_items]]
    elif callable(discover_tiles_method):
        tiles_by_year = discover_tiles_method(bbox=bbox, time_range=time_range)
        flattened = [str(path) for paths in tiles_by_year.values() for path in paths]
        discovery["matched_years"] = sorted(tiles_by_year)
        discovery["matched_tiles"] = len(flattened)
        discovery["matched_tile_preview"] = flattened[:preview_items]
    elif callable(discover_files_method):
        discovered = discover_files_method(time_range)
        flattened = [str(path) for entries in discovered.values() for _, path in entries]
        discovery["matched_groups"] = len(discovered)
        discovery["matched_files"] = len(flattened)
        discovery["matched_group_preview"] = [
            {
                "group": list(group),
                "years": [year for year, _ in entries[:preview_items]],
            }
            for group, entries in list(discovered.items())[:preview_items]
        ]
        discovery["matched_file_preview"] = flattened[:preview_items]
    elif isinstance(pattern_value, str):
        matched = sorted(loader.base_path.glob(pattern_value))
        discovery["matched_files"] = len(matched)
        discovery["matched_file_preview"] = [str(path) for path in matched[:preview_items]]

    return discovery


def summarize_dataset(dataset: xr.Dataset, *, preview_items: int) -> dict[str, Any]:
    """Summarize a loaded dataset without forcing full materialization."""

    return {
        "sizes": {name: int(size) for name, size in dataset.sizes.items()},
        "coords": {
            name: summarize_data_array(dataset.coords[name], preview_items=preview_items)
            for name in dataset.coords
        },
        "data_vars": {
            name: summarize_data_array(
                dataset[name],
                preview_items=preview_items,
                preview_values=False,
            )
            for name in dataset.data_vars
        },
        "attrs": {key: make_json_safe(value) for key, value in dataset.attrs.items()},
        "approx_nbytes": int(dataset.nbytes),
    }


def summarize_data_array(
    array: xr.DataArray,
    *,
    preview_items: int,
    preview_values: bool = True,
) -> dict[str, Any]:
    """Summarize a coordinate or variable."""

    preview: list[Any] = []
    if preview_values:
        preview = preview_array_values(array, preview_items=preview_items)

    chunk_info = getattr(array.data, "chunks", None)
    return {
        "dims": list(array.dims),
        "shape": [int(size) for size in array.shape],
        "dtype": str(array.dtype),
        "dask_backed": chunk_info is not None,
        "chunks": make_json_safe(chunk_info),
        "preview": preview,
    }


def preview_array_values(array: xr.DataArray, *, preview_items: int) -> list[Any]:
    """Build a small preview of array values without loading the full variable."""

    indexers = {dim: slice(0, min(preview_items, array.sizes[dim])) for dim in array.dims}
    subset = array.isel(indexers)
    values = np.asarray(subset.values).reshape(-1)
    limited = values[:preview_items]
    return [make_json_safe(value) for value in limited]


def summarize_sample(
    dataset: xr.Dataset,
    *,
    sample_size: int,
    preview_items: int,
) -> dict[str, Any]:
    """Materialize a tiny sample and compute compact diagnostics."""

    indexers = {dim: slice(0, min(sample_size, dataset.sizes[dim])) for dim in dataset.dims}
    sample = dataset.isel(indexers).load()

    variables: dict[str, Any] = {}
    for name, array in sample.data_vars.items():
        values = np.asarray(array.values)
        summary: dict[str, Any] = {
            "shape": [int(size) for size in values.shape],
            "dtype": str(values.dtype),
            "preview": [make_json_safe(value) for value in values.reshape(-1)[:preview_items]],
            "non_null_count": int(np.count_nonzero(~pd.isna(values))),
        }
        if np.issubdtype(values.dtype, np.number):
            numeric_values = values.astype(float, copy=False)
            if np.all(np.isnan(numeric_values)):
                summary["min"] = None
                summary["max"] = None
                summary["mean"] = None
            else:
                summary["min"] = float(np.nanmin(numeric_values))
                summary["max"] = float(np.nanmax(numeric_values))
                summary["mean"] = float(np.nanmean(numeric_values))
        variables[str(name)] = summary

    return {
        "sizes": {str(name): int(size) for name, size in sample.sizes.items()},
        "variables": variables,
    }


def probe_dataset(
    dataset_id: str,
    dataset_config: dict[str, Any],
    options: ProbeOptions,
) -> ProbeResult:
    """Probe one configured dataset loader."""

    start_time = perf_counter()
    emit_progress(f"{dataset_id}: instantiate loader")
    loader = get_loader(dataset_id, dataset_config)
    emit_progress(f"{dataset_id}: collect metadata")
    metadata = loader.metadata()
    effective_time_range = derive_probe_time_range(loader, requested_time_range=options.time_range)
    emit_progress(
        f"{dataset_id}: effective bbox={format_progress_value(options.bbox)} "
        f"time_range={format_progress_value(effective_time_range)}"
    )
    emit_progress(
        f"{dataset_id}: metadata static={metadata.is_static} "
        f"temporal={format_progress_value(metadata.temporal_coverage)} crs={metadata.crs}"
    )
    emit_progress(f"{dataset_id}: collect input discovery")
    discovery = collect_input_discovery(
        loader,
        options.bbox,
        effective_time_range,
        preview_items=options.preview_items,
    )
    emit_progress(f"{dataset_id}: discovery {compact_discovery_summary(discovery)}")
    preview_text = compact_discovery_preview(discovery)
    if preview_text is not None:
        emit_progress(f"{dataset_id}: discovery preview {preview_text}")

    result = ProbeResult(
        dataset_id=dataset_id,
        loader_type=str(dataset_config["loader_type"]),
        status="metadata_only",
        effective_bbox=options.bbox,
        effective_time_range=effective_time_range,
        metadata=asdict(metadata),
        discovery=discovery,
        dataset_summary=None,
        sample_summary=None,
        elapsed_seconds=0.0,
    )

    if options.metadata_only:
        emit_progress(f"{dataset_id}: metadata-only probe finished")
        result.elapsed_seconds = perf_counter() - start_time
        return result

    try:
        emit_progress(f"{dataset_id}: load dataset")
        dataset = loader.load(bbox=options.bbox, time_range=effective_time_range)
        emit_progress(f"{dataset_id}: summarize dataset")
        result.dataset_summary = summarize_dataset(dataset, preview_items=options.preview_items)
        emit_progress(
            f"{dataset_id}: dataset sizes {result.dataset_summary['sizes']} "
            f"approx_nbytes={result.dataset_summary['approx_nbytes']}"
        )
        result.status = "loaded"

        if options.compute_sample:
            emit_progress(f"{dataset_id}: materialize tiny sample")
            result.sample_summary = summarize_sample(
                dataset,
                sample_size=options.sample_size,
                preview_items=options.preview_items,
            )
            result.status = "sampled"
            emit_progress(
                f"{dataset_id}: sample vars {list(result.sample_summary['variables'].keys())}"
            )
            emit_progress(f"{dataset_id}: tiny sample finished")
    except Exception as exc:
        result.status = "failed"
        result.error = f"{type(exc).__name__}: {exc}"
        result.traceback_text = traceback.format_exc()
        emit_progress(f"{dataset_id}: failed with {type(exc).__name__}")
    finally:
        result.elapsed_seconds = perf_counter() - start_time

    return result


def run_probe(
    app_config: AppConfig,
    dataset_ids: list[str],
    options: ProbeOptions,
) -> list[ProbeResult]:
    """Run the probe across the selected dataset ids."""

    results: list[ProbeResult] = []
    for dataset_id in dataset_ids:
        emit_progress(f"{dataset_id}: probe start")
        dataset_config = app_config.datasets[dataset_id]
        result = probe_dataset(dataset_id, dataset_config, options)
        results.append(result)
        emit_progress(f"{dataset_id}: probe done with status={result.status}")
        if result.status == "failed" and options.fail_fast:
            break
    return results


def make_json_safe(value: Any) -> Any:
    """Convert common scientific Python values into JSON-safe objects."""

    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return make_json_safe(value.item())
    if isinstance(value, np.ndarray):
        return [make_json_safe(item) for item in value.tolist()]
    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    return str(value)


def compact_discovery_summary(discovery: dict[str, Any]) -> dict[str, Any]:
    """Extract a short progress-friendly subset of discovery metadata."""

    keys = (
        "path_exists",
        "matched_files",
        "matched_tiles",
        "matched_groups",
        "matched_years",
        "target_file_exists",
    )
    return {key: discovery[key] for key in keys if key in discovery}


def compact_discovery_preview(discovery: dict[str, Any]) -> str | None:
    """Build a short one-line preview for discovery progress output."""

    if "matched_group_preview" in discovery:
        groups = discovery["matched_group_preview"]
        if groups:
            first_group = groups[0]
            group_name = "/".join(str(part) for part in first_group["group"])
            return f"group={group_name} years={first_group['years']}"

    for key in ("matched_file_preview", "matched_tile_preview"):
        if key in discovery:
            preview = discovery[key]
            if preview:
                return f"first={preview[0]}"

    return None


def format_progress_value(value: Any) -> str:
    """Render compact values for single-line progress logs."""

    if value is None:
        return "None"
    return str(value)


def render_probe_report(
    app_config: AppConfig,
    dataset_ids: list[str],
    options: ProbeOptions,
    results: list[ProbeResult],
) -> str:
    """Render a human-readable multiline report."""

    lines = [
        "=== WA HPC Loader Probe ===",
        f"Dataset config: {app_config.dataset_config_path}",
        f"GEE config: {app_config.gee_config_path}",
        f"GEE project id: {app_config.gee['gee_project_id']}",
        f"Datasets: {', '.join(dataset_ids)}",
        f"Effective bbox source: {options.bbox_label}",
        f"Effective bbox: {options.bbox}",
        f"Metadata only: {options.metadata_only}",
        f"Compute sample: {options.compute_sample}",
        "",
    ]

    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"--- [{index}/{len(results)}] {result.dataset_id} ({result.loader_type}) ---",
                f"status: {result.status}",
                f"elapsed_seconds: {result.elapsed_seconds:.3f}",
                f"effective_time_range: {result.effective_time_range}",
                "metadata:",
                indent_json(result.metadata),
                "discovery:",
                indent_json(result.discovery),
            ]
        )

        if result.dataset_summary is not None:
            lines.extend(["dataset_summary:", indent_json(result.dataset_summary)])

        if result.sample_summary is not None:
            lines.extend(["sample_summary:", indent_json(result.sample_summary)])

        if result.error is not None:
            lines.extend(["error:", f"  {result.error}"])
            if result.traceback_text is not None:
                lines.extend(["traceback:", indent_block(result.traceback_text.rstrip())])

        lines.append("")

    passed = sum(result.status != "failed" for result in results)
    failed = len(results) - passed
    lines.extend(
        [
            "=== Summary ===",
            f"passed: {passed}",
            f"failed: {failed}",
            f"total: {len(results)}",
        ]
    )
    return "\n".join(lines)


def indent_json(payload: dict[str, Any]) -> str:
    """Pretty-print a JSON-like payload with indentation."""

    return indent_block(json.dumps(make_json_safe(payload), indent=2, sort_keys=True))


def indent_block(text: str, prefix: str = "  ") -> str:
    """Indent a block of text for terminal output."""

    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def options_from_args(args: argparse.Namespace, app_config: AppConfig) -> ProbeOptions:
    """Convert parsed args into typed probe options."""

    bbox, bbox_label = resolve_probe_bbox(
        app_config,
        bbox_text=args.bbox,
        region_name=args.region,
        unsafe_full_spatial_scan=args.unsafe_full_spatial_scan,
    )
    time_range = parse_time_range(args.time_range) if args.time_range else None
    compute_sample = not args.skip_compute and not args.metadata_only
    return ProbeOptions(
        bbox=bbox,
        bbox_label=bbox_label,
        time_range=time_range,
        compute_sample=compute_sample,
        metadata_only=args.metadata_only,
        sample_size=args.sample_size,
        preview_items=args.preview_items,
        fail_fast=args.fail_fast,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the loader probe helpers."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    emit_progress("load config")
    app_config = load_config(args.dataset_config, args.gee_config)
    emit_progress("resolve dataset selection")
    dataset_ids = expand_dataset_ids(app_config, args.dataset)
    emit_progress("resolve probe options")
    options = options_from_args(args, app_config)
    emit_progress(f"start probe for {len(dataset_ids)} dataset(s)")
    results = run_probe(app_config, dataset_ids, options)

    report = render_probe_report(app_config, dataset_ids, options, results)
    print(report)

    if args.json_out:
        payload = {
            "dataset_config": str(app_config.dataset_config_path),
            "gee_config": str(app_config.gee_config_path),
            "dataset_ids": dataset_ids,
            "options": asdict(options),
            "results": [asdict(result) for result in results],
        }
        json_path = Path(args.json_out)
        json_path.write_text(
            json.dumps(make_json_safe(payload), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return 1 if any(result.status == "failed" for result in results) else 0
