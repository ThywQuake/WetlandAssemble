#!/usr/bin/env python3
"""Generate contract-backed Phase 4 percentage summaries, surfaces, and hotspots."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.comparison.evidence_contract import (  # noqa: E402
    DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    DEFAULT_PHASE4_REGIONS_FILE,
    SUPPORTED_PHASE4_REGION_SUBSETS,
    load_phase4_evidence_contract,
    validate_stem_token,
)
from WA.comparison.percentage_backbone import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS,
    DEFAULT_RESOLUTION_DEG,
    DEFAULT_STANDARDIZED_DIR,
    DEFAULT_TARGET_YEAR,
    PercentageSummaryBundle,
    PercentageSurfaceBundle,
    build_contract_percentage_surface_bundle,
    build_percentage_dataset_key,
    load_contract_percentage_summary,
    load_contract_percentage_surface,
    resolve_contract_dataset_ids,
    write_contract_percentage_summary,
)
from WA.comparison.percentage_hotspots import (  # noqa: E402
    PercentageHotspotReload,
    load_contract_percentage_hotspot_table,
    percentage_hotspot_manifest_output_path,
    percentage_hotspot_table_output_path,
    write_percentage_hotspot_outputs,
)
from WA.comparison.phase4_regional import (  # noqa: E402
    build_or_load_phase4_berkeley_valid_mask,
    build_phase4_region_table,
    compute_phase4_region_dataset_table,
)

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or reload one contract-backed percentage family: live Phase 4 "
            "regional summaries, a shared 0.25° surface bundle, and a validated "
            "hotspot manifest/CSV pair. Supports one --region, --subset canonical, "
            "or --subset ten."
        )
    )
    parser.add_argument("--regions-file", default=str(DEFAULT_PHASE4_REGIONS_FILE))
    parser.add_argument(
        "--subset",
        choices=SUPPORTED_PHASE4_REGION_SUBSETS,
        default=None,
        help=(
            "Evidence-contract priority-region subset. Use 'canonical' for the "
            "four-region hydro-diverse subset or 'ten' for the full ordered contract "
            "list. Omit --subset to keep the canonical default unless --region is "
            "passed explicitly."
        ),
    )
    parser.add_argument(
        "--region",
        action="append",
        default=[],
        help="Explicit region id override; may be repeated. Cannot be combined with --subset.",
    )
    parser.add_argument(
        "--dataset-id",
        action="append",
        default=[],
        help=(
            "Percentage participant dataset id. Repeat to override the default ordered set "
            f"({', '.join(DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS)})."
        ),
    )
    parser.add_argument(
        "--dataset-key",
        default=None,
        help=(
            "Stable dataset key for the contract family. Defaults to 'canonical' for the "
            "default ordered dataset set; otherwise the ordered ids are joined with '+'."
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    )
    parser.add_argument(
        "--surface-cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Cache root for 0.25° surface staging (default: results/cache/tropical_025deg).",
    )
    parser.add_argument(
        "--standardized-dir",
        type=Path,
        default=DEFAULT_STANDARDIZED_DIR,
        help="Standardized dataset root used by the live Phase 4 regional producer.",
    )
    parser.add_argument(
        "--surface-year",
        type=int,
        default=DEFAULT_TARGET_YEAR,
        help="Target year for dynamic 0.25° surfaces (default: 2016).",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=DEFAULT_TARGET_YEAR,
        help="Start year for regional summaries (default: 2016).",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=DEFAULT_TARGET_YEAR,
        help="End year for regional summaries (default: 2016).",
    )
    parser.add_argument(
        "--resolution-deg",
        type=float,
        default=DEFAULT_RESOLUTION_DEG,
        help="Target surface resolution in degrees (default: 0.25).",
    )
    parser.add_argument(
        "--top-hotspots",
        type=int,
        default=10,
        help="Maximum percentage hotspots to retain per region (default: 10).",
    )
    parser.add_argument(
        "--min-distance-deg",
        type=float,
        default=0.5,
        help="Minimum center distance between retained hotspots (default: 0.5).",
    )
    parser.add_argument(
        "--skip",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reuse existing valid contract outputs when present (default: True).",
    )
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show progress bars where available (default: True).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="[%(levelname)s] %(message)s",
    )

    if args.start_year > args.end_year:
        raise ValueError("start_year must be <= end_year")

    contract = load_phase4_evidence_contract(
        output_root=args.output_root,
        regions_file=args.regions_file,
    )
    contract.output_root.mkdir(parents=True, exist_ok=True)
    dataset_ids = resolve_contract_dataset_ids(args.dataset_id)
    dataset_key = (
        validate_stem_token(args.dataset_key, label="dataset_key")
        if args.dataset_key
        else build_percentage_dataset_key(dataset_ids)
    )
    time_range = (f"{args.start_year}-01-01", f"{args.end_year}-12-31")

    try:
        regions = contract.resolve_regions(
            subset=args.subset,
            requested_region_ids=args.region or None,
        )
    except Exception as exc:
        logger.error(
            "stage=region-selector subset=%s requested_regions=%s dataset_key=%s error=%s",
            args.subset or "<none>",
            args.region,
            dataset_key,
            exc,
        )
        raise

    selector_subset = args.subset or ("explicit-region-list" if args.region else "canonical")
    logger.info(
        "stage=region-selector subset=%s dataset_key=%s region_ids=%s",
        selector_subset,
        dataset_key,
        [region.region_id for region in regions],
    )
    logger.info(
        "stage=dataset-selector dataset_key=%s dataset_ids=%s "
        "surface_year=%s time_range=%s skip=%s",
        dataset_key,
        list(dataset_ids),
        args.surface_year,
        time_range,
        args.skip,
    )

    for region in regions:
        logger.info(
            "stage=percentage-contract region=%s action=start bbox=%s dataset_key=%s",
            region.region_id,
            region.bbox,
            dataset_key,
        )
        summary_bundle = _materialize_percentage_summary(
            contract=contract,
            region=region,
            dataset_ids=dataset_ids,
            dataset_key=dataset_key,
            standardized_dir=args.standardized_dir,
            output_root=args.output_root,
            time_range=time_range,
            skip=args.skip,
            show_progress=args.progress,
        )
        surface_bundle = _materialize_percentage_surface(
            contract=contract,
            region=region,
            dataset_ids=dataset_ids,
            dataset_key=dataset_key,
            surface_year=args.surface_year,
            resolution_deg=args.resolution_deg,
            surface_cache_dir=args.surface_cache_dir,
            output_root=args.output_root,
            standardized_dir=args.standardized_dir,
            skip=args.skip,
            show_progress=args.progress,
        )
        hotspot_bundle = _materialize_percentage_hotspots(
            contract=contract,
            region_id=region.region_id,
            dataset_key=dataset_key,
            dataset_ids=dataset_ids,
            top_hotspots=args.top_hotspots,
            min_distance_deg=args.min_distance_deg,
            skip=args.skip,
        )
        logger.info(
            "stage=percentage-contract region=%s action=ready summary=%s surface=%s hotspots=%s",
            region.region_id,
            summary_bundle.summary_path,
            surface_bundle.surface_path,
            hotspot_bundle.manifest.manifest_path,
        )

    logger.info(
        "Phase4 percentage contract complete: subset=%s dataset_key=%s regions=%s",
        selector_subset,
        dataset_key,
        [region.region_id for region in regions],
    )
    return 0


def _materialize_percentage_summary(
    *,
    contract,
    region,
    dataset_ids: tuple[str, ...],
    dataset_key: str,
    standardized_dir: Path,
    output_root: Path,
    time_range: tuple[str, str],
    skip: bool,
    show_progress: bool,
) -> PercentageSummaryBundle:
    summary_path = contract.artifact_output_path(
        kind="regional_summary",
        dataset_or_key=dataset_key,
        region_id=region.region_id,
    )
    if skip and summary_path.is_file():
        logger.info(
            "stage=percentage-summary region=%s action=reload decision=skip-existing path=%s",
            region.region_id,
            summary_path,
        )
        return load_contract_percentage_summary(
            contract=contract,
            region_id=region.region_id,
            dataset_key=dataset_key,
            expected_dataset_ids=dataset_ids,
        )

    action = "rebuild" if summary_path.exists() else "write"
    logger.info(
        "stage=percentage-summary region=%s action=%s dataset_key=%s path=%s",
        region.region_id,
        action,
        dataset_key,
        summary_path,
    )
    region_mask = build_or_load_phase4_berkeley_valid_mask(
        region=region,
        output_root=output_root,
        standardized_dir=standardized_dir,
        time_range=time_range,
        skip_existing=skip,
    )
    dataset_tables: list[pd.DataFrame] = []
    for dataset_id in dataset_ids:
        dataset_tables.append(
            compute_phase4_region_dataset_table(
                dataset_id,
                region=region,
                base_mask=region_mask,
                output_root=output_root,
                standardized_dir=standardized_dir,
                time_range=time_range,
                skip_existing=skip,
                show_progress=show_progress,
            )
        )
    combined = pd.concat(dataset_tables, ignore_index=True)
    source_region_table_path = build_phase4_region_table(
        region=region,
        dataset_tables=dataset_tables,
        output_root=output_root,
    )
    return write_contract_percentage_summary(
        contract=contract,
        region_id=region.region_id,
        region_label=region.label,
        dataset_key=dataset_key,
        dataset_ids=dataset_ids,
        table=combined,
        time_range=time_range,
        source_region_table_path=source_region_table_path,
    )


def _materialize_percentage_surface(
    *,
    contract,
    region,
    dataset_ids: tuple[str, ...],
    dataset_key: str,
    surface_year: int,
    resolution_deg: float,
    surface_cache_dir: Path,
    output_root: Path,
    standardized_dir: Path,
    skip: bool,
    show_progress: bool,
) -> PercentageSurfaceBundle:
    surface_path = contract.artifact_output_path(
        kind="surface",
        dataset_or_key=dataset_key,
        region_id=region.region_id,
    )
    if skip and surface_path.is_file():
        logger.info(
            "stage=percentage-surface region=%s action=reload decision=skip-existing path=%s",
            region.region_id,
            surface_path,
        )
        return load_contract_percentage_surface(
            contract=contract,
            region_id=region.region_id,
            dataset_key=dataset_key,
            expected_dataset_ids=dataset_ids,
        )

    action = "rebuild" if surface_path.exists() else "write"
    logger.info(
        "stage=percentage-surface region=%s action=%s dataset_key=%s path=%s",
        region.region_id,
        action,
        dataset_key,
        surface_path,
    )
    return build_contract_percentage_surface_bundle(
        contract=contract,
        region_id=region.region_id,
        region_label=region.label,
        bbox=region.bbox,
        dataset_key=dataset_key,
        dataset_ids=dataset_ids,
        surface_year=surface_year,
        resolution_deg=resolution_deg,
        cache_dir=surface_cache_dir,
        output_root=output_root,
        standardized_dir=standardized_dir,
        prefer_cache=skip,
        write_cache=True,
        show_progress=show_progress,
    )


def _materialize_percentage_hotspots(
    *,
    contract,
    region_id: str,
    dataset_key: str,
    dataset_ids: tuple[str, ...],
    top_hotspots: int,
    min_distance_deg: float,
    skip: bool,
) -> PercentageHotspotReload:
    manifest_path = percentage_hotspot_manifest_output_path(
        contract,
        region_id=region_id,
        dataset_key=dataset_key,
    )
    table_path = percentage_hotspot_table_output_path(
        contract,
        region_id=region_id,
        dataset_key=dataset_key,
    )
    if skip and (manifest_path.exists() or table_path.exists()):
        _require_complete_pair(
            label="percentage-hotspots",
            region_id=region_id,
            dataset_key=dataset_key,
            left_path=manifest_path,
            right_path=table_path,
        )
        logger.info(
            "stage=percentage-hotspots region=%s action=reload "
            "decision=skip-existing manifest=%s table=%s",
            region_id,
            manifest_path,
            table_path,
        )
        return load_contract_percentage_hotspot_table(
            contract=contract,
            region_id=region_id,
            dataset_key=dataset_key,
            expected_dataset_ids=dataset_ids,
        )

    logger.info(
        "stage=percentage-hotspots region=%s action=write decision=%s manifest=%s table=%s",
        region_id,
        "rebuild" if manifest_path.exists() or table_path.exists() else "write",
        manifest_path,
        table_path,
    )
    write_percentage_hotspot_outputs(
        contract=contract,
        region_id=region_id,
        dataset_key=dataset_key,
        top_n=top_hotspots,
        min_distance_deg=min_distance_deg,
    )
    return load_contract_percentage_hotspot_table(
        contract=contract,
        region_id=region_id,
        dataset_key=dataset_key,
        expected_dataset_ids=dataset_ids,
    )


def _require_complete_pair(
    *,
    label: str,
    region_id: str,
    dataset_key: str,
    left_path: Path,
    right_path: Path,
) -> None:
    left_exists = left_path.is_file()
    right_exists = right_path.is_file()
    if left_exists and right_exists:
        return
    if left_exists or right_exists:
        raise FileNotFoundError(
            f"stage={label} region={region_id} dataset_key={dataset_key} "
            f"found partial artifact pair: {left_path} exists={left_exists} "
            f"{right_path} exists={right_exists}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
