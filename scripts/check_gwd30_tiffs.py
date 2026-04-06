#!/usr/bin/env python3
"""Audit GWD30 GeoTIFF integrity and report corrupt tiles for re-download."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import shutil
import sys
import time
import traceback
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import rasterio

try:
    import tifffile
except Exception:  # pragma: no cover - optional runtime dependency
    tifffile = None

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.config import get_dataset_config  # noqa: E402
from WA.utils.progress import tqdm  # noqa: E402

logger = logging.getLogger("WA.gwd30.tiff_audit")

_NOISY_LOGGERS = (
    "rasterio",
    "rioxarray",
    "pyproj",
    "fiona",
)

_GWD30_EXPECTED_COUNT = 92
_GWD30_EXPECTED_WIDTH = 3661
_GWD30_EXPECTED_HEIGHT = 3661
_GWD30_EXPECTED_DTYPE = "uint8"
_GWD30_EXPECTED_NODATA = 255.0
_GWD30_EXPECTED_DRIVER = "GTiff"
_GWD30_AUDIT_MAX_WORKERS = 16
_GWD30_READ_MODES = ("footprint", "sampled", "full")


class TiffStructureError(RuntimeError):
    """Raised when TIFF structural metadata is inconsistent with file contents."""


class TiffReadError(RuntimeError):
    """Raised when TIFF data reads fail or return unexpected shapes."""


@dataclass(frozen=True)
class TiffAuditResult:
    """Structured result for one audited TIFF."""

    path: str
    relative_path: str
    file_name: str
    tile_id: str | None
    year: int | None
    ok: bool
    status: str
    size_bytes: int | None
    width: int | None
    height: int | None
    band_count: int | None
    dtype: str | None
    nodata: float | None
    error_type: str | None = None
    error_message: str | None = None
    detail: str | None = None


def _announce(message: str) -> None:
    """Emit one unbuffered stage message for interactive and batch logs."""

    print(f"[gwd30-audit] {message}", flush=True)


def _configure_logging(*, verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("WA").setLevel(logging.DEBUG if verbose else logging.INFO)
    for logger_name in _NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit GWD30 raw GeoTIFF integrity from yearly manifest JSON files."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="GWD30 root directory. Defaults to datasets.gwd30.path from config/datasets.yaml.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/datasets.yaml"),
        help="Path to datasets.yaml used when --root is omitted.",
    )
    parser.add_argument(
        "--manifest-json",
        type=Path,
        help=(
            "Optional explicit manifest JSON. If omitted, the script loads "
            "GWD30_file_list_YYYY.json files directly under --root."
        ),
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="*",
        help="Optional subset of years to scan (default: all discovered years).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/maintenance/gwd30_tiff_audit"),
        help="Directory for summary/report files.",
    )
    parser.add_argument(
        "--quarantine-dir",
        type=Path,
        help=(
            "Optional directory where bad TIFFs are moved after detection, preserving "
            "their paths relative to --root."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help=(
            "Parallel worker count for per-file auditing "
            "(default: 0 = auto from HPC/local CPU, capped)."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of TIFFs to inspect (default: all).",
    )
    parser.add_argument(
        "--strict-profile",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Require the canonical GWD30 profile (GTiff, uint8, 92 bands, 3661x3661, "
            "nodata 255). Disable to only check readability."
        ),
    )
    parser.add_argument(
        "--read-mode",
        choices=_GWD30_READ_MODES,
        default="footprint",
        help=(
            "Integrity depth. 'footprint' checks TIFF segment offsets/bytecounts against "
            "the actual file size and is optimized for truncated downloads; 'sampled' "
            "adds a few representative block reads; 'full' reads every block."
        ),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    parser.add_argument(
        "--allow-disk-scan",
        action="store_true",
        help=(
            "Fall back to scanning year directories on disk when no usable manifest JSON "
            "is found. Disabled by default."
        ),
    )
    return parser


def resolve_gwd30_root(root: Path | None, *, dataset_config_path: Path) -> Path:
    """Resolve the GWD30 root either from CLI or datasets.yaml."""

    if root is not None:
        return root.expanduser().resolve()

    dataset_config = get_dataset_config("gwd30", dataset_config_path=dataset_config_path)
    raw_path = dataset_config.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("datasets.gwd30.path must be a non-empty string")
    return Path(raw_path).expanduser().resolve()


def _looks_like_tiff_path(value: object) -> bool:
    return isinstance(value, str) and value.lower().endswith((".tif", ".tiff"))


def _extract_tiff_paths_from_json(payload: object) -> list[str]:
    """Recursively extract TIFF path strings from an arbitrary JSON payload."""

    paths: list[str] = []
    if isinstance(payload, dict):
        for value in payload.values():
            paths.extend(_extract_tiff_paths_from_json(value))
    elif isinstance(payload, list):
        for value in payload:
            paths.extend(_extract_tiff_paths_from_json(value))
    elif _looks_like_tiff_path(payload):
        paths.append(str(payload))
    return paths


def _manifest_year_from_path(path: Path) -> int | None:
    stem = path.stem
    prefix = "GWD30_file_list_"
    if not stem.startswith(prefix):
        return None
    try:
        return int(stem[len(prefix) :])
    except ValueError:
        return None


def _normalize_years(years: Sequence[int] | None) -> list[int]:
    if not years:
        return []
    return sorted({int(value) for value in years})


def _resolve_manifest_jsons(
    root: Path,
    manifest_json: Path | None,
    *,
    years: Sequence[int] | None = None,
) -> list[Path]:
    """Resolve explicit or yearly GWD30 manifest JSON files under the dataset root."""

    if manifest_json is not None:
        resolved = manifest_json.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"GWD30 manifest JSON does not exist: {resolved}")
        return [resolved]

    requested_years = _normalize_years(years)
    if requested_years:
        return [
            candidate.resolve()
            for year in requested_years
            for candidate in [root / f"GWD30_file_list_{year}.json"]
            if candidate.is_file()
        ]

    return sorted(
        path.resolve()
        for path in root.glob("GWD30_file_list_*.json")
        if path.is_file()
    )


def _resolve_manifest_paths(
    root: Path,
    manifest_path: Path,
    *,
    default_year: int | None = None,
) -> list[Path]:
    """Load one manifest JSON and resolve all TIFF paths listed inside it."""

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_paths = _extract_tiff_paths_from_json(payload)
    year_hint = _manifest_year_from_path(manifest_path)
    if year_hint is None:
        year_hint = default_year
    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw_path in raw_paths:
        path_obj = Path(raw_path).expanduser()
        if not path_obj.is_absolute():
            if len(path_obj.parts) == 1 and year_hint is not None:
                path_obj = (root / str(year_hint) / path_obj.name).resolve()
            else:
                path_obj = (root / path_obj).resolve()
        else:
            path_obj = path_obj.resolve()
        if path_obj in seen:
            continue
        seen.add(path_obj)
        resolved.append(path_obj)
    return resolved


def _year_from_tiff_path(path: Path) -> int | None:
    stem = path.stem
    if "_wetland_" not in stem:
        return None
    try:
        return int(stem.rsplit("_wetland_", maxsplit=1)[1])
    except ValueError:
        return None


def _discover_gwd30_tiffs_by_disk_scan(
    root: Path,
    *,
    years: Sequence[int] | None = None,
) -> list[Path]:
    """Discover raw GWD30 TIFF files by scanning year directories on disk."""

    paths: list[Path] = []
    if years:
        candidate_years = sorted({int(value) for value in years})
    else:
        candidate_years = sorted(
            int(path.name)
            for path in root.iterdir()
            if path.is_dir() and len(path.name) == 4 and path.name.isdigit()
        )

    if candidate_years:
        _announce(
            "discovery plan: scanning year directories "
            + ", ".join(str(year) for year in candidate_years)
        )
        for year in candidate_years:
            year_dir = root / str(year)
            if not year_dir.exists():
                _announce(f"discovery: year {year} directory missing, skipping")
                continue
            _announce(f"discovery: scanning year {year}")
            year_paths = sorted(
                path.resolve()
                for path in year_dir.glob(f"*_wetland_{year}.tif")
                if path.is_file()
            )
            _announce(f"discovery: year {year} found {len(year_paths)} TIFF file(s)")
            paths.extend(year_paths)
    else:
        _announce("discovery fallback: no year directories found, using recursive search")
        for path in root.rglob("*_wetland_*.tif"):
            if path.is_file() and path.suffix.lower() == ".tif":
                paths.append(path.resolve())

        _announce(f"discovery fallback: found {len(paths)} TIFF file(s)")
    return sorted(path.resolve() for path in paths)


def discover_gwd30_tiffs(
    root: Path,
    *,
    years: Sequence[int] | None = None,
    manifest_json: Path | None = None,
    allow_disk_scan: bool = False,
) -> list[Path]:
    """Discover raw GWD30 TIFF files from a manifest JSON or, optionally, disk."""

    requested_years = _normalize_years(years)
    manifest_paths = _resolve_manifest_jsons(root, manifest_json, years=requested_years)
    if manifest_paths:
        found_manifest_years = sorted(
            year
            for manifest_path in manifest_paths
            for year in [_manifest_year_from_path(manifest_path)]
            if year is not None
        )
        if manifest_json is None and found_manifest_years:
            _announce(
                "discovery plan: loading manifest files "
                + ", ".join(str(year) for year in found_manifest_years)
            )

        if manifest_json is None and requested_years:
            missing_manifest_years = [
                year for year in requested_years if year not in set(found_manifest_years)
            ]
            for year in missing_manifest_years:
                _announce(f"discovery: manifest for year {year} missing, skipping")

        default_year = requested_years[0] if len(requested_years) == 1 else None
        paths: list[Path] = []
        seen: set[Path] = set()
        for manifest_path in manifest_paths:
            _announce(f"discovery: loading manifest {manifest_path.name}")
            manifest_paths_for_year = _resolve_manifest_paths(
                root,
                manifest_path,
                default_year=default_year,
            )
            if requested_years and manifest_json is not None:
                allowed_years = set(requested_years)
                manifest_paths_for_year = [
                    path
                    for path in manifest_paths_for_year
                    if _year_from_tiff_path(path) in allowed_years
                ]
            _announce(
                f"discovery: manifest {manifest_path.name} yielded "
                f"{len(manifest_paths_for_year)} TIFF file(s)"
            )
            for path in manifest_paths_for_year:
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                paths.append(resolved)

        _announce(f"discovery: combined manifest list yielded {len(paths)} TIFF file(s)")
        return sorted(paths)

    if not allow_disk_scan:
        raise FileNotFoundError(
            "No GWD30 yearly manifest JSON found under the root. Pass --manifest-json or "
            "explicitly allow fallback scanning with --allow-disk-scan."
        )

    _announce("discovery: no manifest found, falling back to disk scan")
    return _discover_gwd30_tiffs_by_disk_scan(root, years=years)


def _resolve_audit_worker_count(worker_count: int | None) -> int:
    """Resolve a safe audit worker count from CLI, HPC env, or local CPU."""

    if worker_count is not None and worker_count > 0:
        requested = int(worker_count)
    else:
        requested = 0
        for env_name in (
            "WA_GWD30_AUDIT_WORKERS",
            "SLURM_CPUS_PER_TASK",
            "OMP_NUM_THREADS",
            "PBS_NUM_PPN",
            "NSLOTS",
        ):
            raw_value = os.environ.get(env_name)
            if raw_value is None:
                continue
            try:
                requested = int(raw_value.split("(")[0].split(",")[0])
            except ValueError:
                continue
            if requested > 0:
                break

        if requested <= 0:
            try:
                sched_getaffinity = getattr(os, "sched_getaffinity", None)
                affinity_count = len(sched_getaffinity(0)) if sched_getaffinity is not None else 0
            except Exception:
                affinity_count = 0
            requested = affinity_count if affinity_count > 0 else (os.cpu_count() or 1)

    resolved = max(1, min(int(requested), _GWD30_AUDIT_MAX_WORKERS))
    if resolved < int(requested):
        logger.info(
            "GWD30 TIFF audit worker count capped at %d (requested %d)",
            resolved,
            requested,
        )
    return resolved


def _resolve_effective_read_mode(read_mode: str) -> str:
    """Resolve the actual integrity mode after optional-dependency fallbacks."""

    if read_mode == "footprint" and tifffile is None:
        logger.warning("tifffile unavailable; falling back from footprint mode to sampled")
        return "sampled"
    return read_mode


def _parse_tile_metadata(path: Path, *, root: Path) -> tuple[str, str, str | None, int | None]:
    relative_path = str(path.resolve().relative_to(root.resolve()))
    stem = path.stem
    if "_wetland_" not in stem:
        return relative_path, path.name, None, None
    tile_text, year_text = stem.rsplit("_wetland_", maxsplit=1)
    try:
        year = int(year_text)
    except ValueError:
        year = None
    return relative_path, path.name, tile_text, year


def _profile_mismatches(dataset: rasterio.io.DatasetReader) -> list[str]:
    mismatches: list[str] = []
    if dataset.driver != _GWD30_EXPECTED_DRIVER:
        mismatches.append(f"driver={dataset.driver!r}")
    if dataset.count != _GWD30_EXPECTED_COUNT:
        mismatches.append(f"band_count={dataset.count}")
    if dataset.width != _GWD30_EXPECTED_WIDTH:
        mismatches.append(f"width={dataset.width}")
    if dataset.height != _GWD30_EXPECTED_HEIGHT:
        mismatches.append(f"height={dataset.height}")
    dtypes = {str(dtype) for dtype in dataset.dtypes}
    if dtypes != {_GWD30_EXPECTED_DTYPE}:
        mismatches.append(f"dtypes={sorted(dtypes)!r}")
    if dataset.nodata is None or float(dataset.nodata) != _GWD30_EXPECTED_NODATA:
        mismatches.append(f"nodata={dataset.nodata!r}")
    if dataset.crs is None:
        mismatches.append("crs=None")
    return mismatches


def _read_all_blocks(dataset: rasterio.io.DatasetReader) -> None:
    windows = list(dataset.block_windows(1))
    if not windows:
        dataset.read(masked=False)
        return

    for window_index, (_ji, window) in enumerate(windows):
        block = dataset.read(window=window, masked=False)
        expected_shape = (dataset.count, int(window.height), int(window.width))
        if block.shape != expected_shape:
            raise TiffReadError(
                "window "
                f"{window_index} shape mismatch: expected {expected_shape}, "
                f"got {block.shape}"
            )


def _read_sampled_blocks(dataset: rasterio.io.DatasetReader) -> None:
    """Read a few representative blocks across the TIFF for a faster decode check."""

    windows = [window for _ji, window in dataset.block_windows(1)]
    if not windows:
        dataset.read(masked=False)
        return

    sampled_indices = sorted({0, len(windows) // 2, len(windows) - 1})
    for window_index in sampled_indices:
        window = windows[window_index]
        block = dataset.read(window=window, masked=False)
        expected_shape = (dataset.count, int(window.height), int(window.width))
        if block.shape != expected_shape:
            raise TiffReadError(
                "sample window "
                f"{window_index} shape mismatch: expected {expected_shape}, "
                f"got {block.shape}"
            )


def _validate_tiff_segment_footprint(path: Path, *, file_size_bytes: int | None) -> None:
    """Validate that every TIFF data segment lies within the actual file size."""

    if tifffile is None:
        raise TiffStructureError("tifffile is unavailable for footprint validation")
    if file_size_bytes is None:
        raise TiffStructureError("file size is unavailable")

    with tifffile.TiffFile(path) as tiff_file:
        segment_count = 0
        for page_index, page in enumerate(tiff_file.pages):
            offsets = tuple(int(value) for value in page.dataoffsets)
            bytecounts = tuple(int(value) for value in page.databytecounts)
            if len(offsets) != len(bytecounts):
                raise TiffStructureError(
                    f"page {page_index} offset/count length mismatch: "
                    f"{len(offsets)} vs {len(bytecounts)}"
                )
            if not offsets:
                continue
            for segment_index, (offset, bytecount) in enumerate(
                zip(offsets, bytecounts, strict=False)
            ):
                if offset < 0 or bytecount < 0:
                    raise TiffStructureError(
                        f"page {page_index} segment {segment_index} has negative metadata"
                    )
                segment_end = offset + bytecount
                if segment_end > file_size_bytes:
                    raise TiffStructureError(
                        f"page {page_index} segment {segment_index} exceeds file size: "
                        f"end={segment_end}, file_size={file_size_bytes}"
                    )
                segment_count += 1
        if segment_count == 0:
            raise TiffStructureError("no TIFF data segments found")


def _execute_integrity_check(
    dataset: rasterio.io.DatasetReader,
    *,
    path: Path,
    file_size_bytes: int | None,
    read_mode: str,
) -> None:
    if read_mode == "footprint":
        _validate_tiff_segment_footprint(path, file_size_bytes=file_size_bytes)
        return
    if read_mode == "sampled":
        if tifffile is not None:
            _validate_tiff_segment_footprint(path, file_size_bytes=file_size_bytes)
        _read_sampled_blocks(dataset)
        return
    if read_mode == "full":
        _read_all_blocks(dataset)
        return
    raise ValueError(f"Unsupported read_mode: {read_mode}")


def inspect_gwd30_tiff(
    path: Path,
    *,
    root: Path,
    strict_profile: bool = True,
    read_mode: str = "footprint",
) -> TiffAuditResult:
    """Inspect one TIFF by validating metadata and running the selected integrity check."""

    resolved = path.resolve()
    relative_path, file_name, tile_id, year = _parse_tile_metadata(resolved, root=root)
    size_bytes = resolved.stat().st_size if resolved.exists() else None

    try:
        with rasterio.open(resolved) as dataset:
            base_result = {
                "path": str(resolved),
                "relative_path": relative_path,
                "file_name": file_name,
                "tile_id": tile_id,
                "year": year,
                "size_bytes": size_bytes,
                "width": int(dataset.width),
                "height": int(dataset.height),
                "band_count": int(dataset.count),
                "dtype": str(dataset.dtypes[0]) if dataset.dtypes else None,
                "nodata": (float(dataset.nodata) if dataset.nodata is not None else None),
            }

            if strict_profile:
                mismatches = _profile_mismatches(dataset)
                if mismatches:
                    return TiffAuditResult(
                        ok=False,
                        status="metadata_mismatch",
                        error_type="MetadataMismatch",
                        error_message="; ".join(mismatches),
                        detail="profile validation failed",
                        **base_result,
                    )

            try:
                _execute_integrity_check(
                    dataset,
                    path=resolved,
                    file_size_bytes=size_bytes,
                    read_mode=read_mode,
                )
                return TiffAuditResult(
                    ok=True,
                    status="ok",
                    **base_result,
                )
            except TiffStructureError as exc:
                return TiffAuditResult(
                    ok=False,
                    status="structure_failed",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    detail="failed while validating TIFF segment footprint",
                    **base_result,
                )
            except Exception as exc:
                detail = (
                    "failed while reading sampled TIFF blocks"
                    if read_mode == "sampled"
                    else "failed while opening or reading TIFF blocks"
                )
                return TiffAuditResult(
                    ok=False,
                    status="read_failed",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    detail=detail,
                    **base_result,
                )
    except Exception as exc:
        return TiffAuditResult(
            path=str(resolved),
            relative_path=relative_path,
            file_name=file_name,
            tile_id=tile_id,
            year=year,
            ok=False,
            status="read_failed",
            size_bytes=size_bytes,
            width=None,
            height=None,
            band_count=None,
            dtype=None,
            nodata=None,
            error_type=type(exc).__name__,
            error_message=str(exc),
            detail="failed while opening or reading TIFF blocks",
        )


def audit_gwd30_tiffs(
    root: Path,
    *,
    years: Sequence[int] | None = None,
    manifest_json: Path | None = None,
    allow_disk_scan: bool = False,
    workers: int = 0,
    limit: int = 0,
    strict_profile: bool = True,
    read_mode: str = "footprint",
) -> dict[str, Any]:
    """Audit all matching GWD30 TIFF files under one root."""

    started_at = time.time()
    _announce(f"discovering TIFF files under {root}")
    paths = discover_gwd30_tiffs(
        root,
        years=years,
        manifest_json=manifest_json,
        allow_disk_scan=allow_disk_scan,
    )
    if limit > 0:
        paths = paths[:limit]
    if not paths:
        raise FileNotFoundError(f"No GWD30 TIFF files found under {root}")

    effective_read_mode = _resolve_effective_read_mode(read_mode)
    bad_results: list[TiffAuditResult] = []
    ok_count = 0
    failed_by_status: dict[str, int] = {}
    resolved_workers = _resolve_audit_worker_count(workers)
    _announce(
        "audit configuration: "
        f"files={len(paths)}, workers={resolved_workers}, "
        f"strict_profile={strict_profile}, read_mode={effective_read_mode}"
    )

    progress = tqdm(
        total=len(paths),
        desc="GWD30 TIFF audit",
        unit="file",
        dynamic_ncols=True,
        mininterval=5.0,
    )
    try:
        if resolved_workers == 1:
            _announce("starting serial TIFF scan")
            for path in paths:
                progress.set_postfix_str(path.name, refresh=False)
                result = inspect_gwd30_tiff(
                    path,
                    root=root,
                    strict_profile=strict_profile,
                    read_mode=effective_read_mode,
                )
                if result.ok:
                    ok_count += 1
                else:
                    bad_results.append(result)
                    failed_by_status[result.status] = failed_by_status.get(result.status, 0) + 1
                progress.update(1)
        else:
            try:
                with ThreadPoolExecutor(max_workers=resolved_workers) as executor:
                    futures = {
                        executor.submit(
                            inspect_gwd30_tiff,
                            path,
                            root=root,
                            strict_profile=strict_profile,
                            read_mode=effective_read_mode,
                        ): path
                        for path in paths
                    }
                    _announce(f"starting parallel TIFF scan with {resolved_workers} workers")
                    for future in as_completed(futures):
                        path = futures[future]
                        progress.set_postfix_str(path.name, refresh=False)
                        result = future.result()
                        if result.ok:
                            ok_count += 1
                        else:
                            bad_results.append(result)
                            failed_by_status[result.status] = (
                                failed_by_status.get(result.status, 0) + 1
                            )
                        progress.update(1)
            except Exception as exc:
                _announce(
                    "parallel scan failed, retrying serially: "
                    f"{type(exc).__name__}: {exc}"
                )
                progress.close()
                return audit_gwd30_tiffs(
                    root,
                    years=years,
                    manifest_json=manifest_json,
                    allow_disk_scan=allow_disk_scan,
                    workers=1,
                    limit=limit,
                    strict_profile=strict_profile,
                    read_mode=effective_read_mode,
                )
    finally:
        progress.close()

    bad_results.sort(key=lambda result: result.relative_path)
    elapsed_seconds = time.time() - started_at
    _announce(
        "scan complete: "
        f"ok={ok_count}, bad={len(bad_results)}, elapsed_seconds={elapsed_seconds:.1f}"
    )
    return {
        "root": str(root),
        "manifest_json": str(manifest_json.resolve()) if manifest_json is not None else None,
        "years": sorted({int(value) for value in years}) if years else None,
        "strict_profile": bool(strict_profile),
        "read_mode": effective_read_mode,
        "workers": resolved_workers,
        "limit": int(limit),
        "total_files": len(paths),
        "ok_files": ok_count,
        "bad_files": len(bad_results),
        "failed_by_status": failed_by_status,
        "elapsed_seconds": elapsed_seconds,
        "bad_results": [asdict(result) for result in bad_results],
    }


def write_audit_reports(summary: dict[str, Any], *, output_dir: Path) -> dict[str, Path]:
    """Write JSON, CSV, and redownload target reports for one audit run."""

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    bad_csv_path = output_dir / "bad_files.csv"
    redownload_path = output_dir / "redownload_targets.txt"

    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )

    bad_results = list(summary.get("bad_results", []))
    fieldnames = [
        "relative_path",
        "file_name",
        "tile_id",
        "year",
        "status",
        "size_bytes",
        "width",
        "height",
        "band_count",
        "dtype",
        "nodata",
        "error_type",
        "error_message",
        "detail",
        "path",
    ]
    with bad_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in bad_results:
            writer.writerow({key: row.get(key) for key in fieldnames})

    redownload_path.write_text(
        "".join(f"{row['relative_path']}\n" for row in bad_results),
        encoding="utf-8",
    )

    return {
        "summary_json": summary_path,
        "bad_csv": bad_csv_path,
        "redownload_targets": redownload_path,
    }


def quarantine_bad_files(
    summary: dict[str, Any],
    *,
    root: Path,
    quarantine_dir: Path,
) -> list[dict[str, str]]:
    """Move bad TIFFs to a quarantine tree to unblock re-download."""

    moves: list[dict[str, str]] = []
    for row in summary.get("bad_results", []):
        source = Path(str(row["path"]))
        if not source.exists():
            continue
        destination = quarantine_dir / str(row["relative_path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moves.append({"from": str(source), "to": str(destination)})
    return moves


def render_audit_summary(summary: dict[str, Any], *, report_paths: dict[str, Path]) -> str:
    """Render a concise terminal summary."""

    lines = [
        f"root: {summary['root']}",
        f"total_files: {summary['total_files']}",
        f"ok_files: {summary['ok_files']}",
        f"bad_files: {summary['bad_files']}",
        f"elapsed_seconds: {summary['elapsed_seconds']:.1f}",
        f"read_mode: {summary['read_mode']}",
        f"summary_json: {report_paths['summary_json']}",
        f"bad_csv: {report_paths['bad_csv']}",
        f"redownload_targets: {report_paths['redownload_targets']}",
    ]
    failed_by_status = summary.get("failed_by_status", {})
    if failed_by_status:
        lines.append("failed_by_status:")
        for status, count in sorted(failed_by_status.items()):
            lines.append(f"  - {status}: {count}")
    return "\n".join(lines)


def _run(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    _configure_logging(verbose=args.verbose)

    _announce("resolving GWD30 root")
    root = resolve_gwd30_root(args.root, dataset_config_path=args.config)
    if not root.exists():
        raise FileNotFoundError(f"GWD30 root does not exist: {root}")
    _announce(f"using root={root}")
    if args.manifest_json is not None:
        _announce(f"using manifest_json={args.manifest_json.expanduser().resolve()}")

    summary = audit_gwd30_tiffs(
        root,
        years=args.years,
        manifest_json=args.manifest_json,
        allow_disk_scan=args.allow_disk_scan,
        workers=args.workers,
        limit=args.limit,
        strict_profile=args.strict_profile,
        read_mode=args.read_mode,
    )
    _announce(f"writing reports to {args.output_dir}")
    report_paths = write_audit_reports(summary, output_dir=args.output_dir)
    _announce("report files written")

    if args.quarantine_dir is not None and summary["bad_files"] > 0:
        _announce(f"moving bad files into quarantine: {args.quarantine_dir}")
        moves = quarantine_bad_files(summary, root=root, quarantine_dir=args.quarantine_dir)
        quarantine_manifest = args.output_dir / "quarantine_moves.json"
        quarantine_manifest.write_text(
            json.dumps(moves, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        report_paths["quarantine_moves"] = quarantine_manifest
        _announce(f"quarantine complete: moved {len(moves)} file(s)")

    print(render_audit_summary(summary, report_paths=report_paths))
    _announce("audit finished")
    return 2 if int(summary["bad_files"]) > 0 else 0


def _coerce_exit_code(code: object) -> int:
    if code is None:
        return 0
    if isinstance(code, bool):
        return int(code)
    if isinstance(code, int):
        return code
    return 1


def _main(argv: Sequence[str] | None = None) -> int:
    try:
        return _coerce_exit_code(_run(argv))
    except SystemExit as exc:
        return _coerce_exit_code(exc.code)
    except BaseException as exc:
        traceback.print_exception(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = _main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
