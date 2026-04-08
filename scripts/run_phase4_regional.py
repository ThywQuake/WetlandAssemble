#!/usr/bin/env python3
"""Run Phase 4 regional wetland-percentage data processing."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from WA.comparison.evidence_contract import (
    SUPPORTED_PHASE4_REGION_SUBSETS,
    load_phase4_evidence_contract,
)
from WA.comparison.phase4_regional import (
    DEFAULT_PHASE4_OUTPUT_ROOT,
    DEFAULT_PHASE4_REGIONS_FILE,
    DEFAULT_PHASE4_STANDARDIZED_DIR,
    build_or_load_phase4_berkeley_valid_mask,
    build_phase4_region_table,
    compute_phase4_region_dataset_table,
    load_phase4_regions,
    resolve_phase4_dataset_ids,
    resolve_phase4_region_ids,
)

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Phase 4 regional area-weighted wetland-percentage caches and tables."
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
            "list. Omit both --subset and --region to keep the legacy macro+priority "
            "all-region run."
        ),
    )
    parser.add_argument(
        "--region",
        action="append",
        default=[],
        help="Explicit region id override; may be repeated. Cannot be combined with --subset.",
    )
    parser.add_argument("--dataset-id", action="append", default=[])
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_PHASE4_OUTPUT_ROOT,
    )
    parser.add_argument(
        "--standardized-dir",
        type=Path,
        default=DEFAULT_PHASE4_STANDARDIZED_DIR,
        help="Standardized dataset root for non-GWD30 inputs and any legacy GWD30 paths.",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=1990,
        help="Start year for the requested analysis window (default: 1990).",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2020,
        help="End year for the requested analysis window (default: 2020).",
    )
    parser.add_argument(
        "--topmodel-raw-path",
        type=Path,
        default=None,
        help="Override the raw TOPMODEL root used by the Phase 4 workflow.",
    )
    parser.add_argument(
        "--spatial-lat-chunk-size",
        type=int,
        default=64,
        help="Latitude stripe size used for non-GWD30 regional reduction (default: 64).",
    )
    parser.add_argument(
        "--time-chunk-size",
        type=int,
        default=12,
        help="Time batch size used for non-GWD30 regional reduction (default: 12).",
    )
    parser.add_argument(
        "--skip",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reuse cached masks and regional tables when present (default: True).",
    )
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show tqdm progress output where available (default: True).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser.parse_args(argv)


def _find_duplicate_region_ids(region_ids: Iterable[str]) -> list[str]:
    flattened = list(region_ids)
    return sorted({region_id for region_id in flattened if flattened.count(region_id) > 1})


def resolve_cli_region_ids(
    *,
    regions_file: str | Path,
    requested_subset: str | None,
    requested_region_ids: Iterable[str],
) -> tuple[list[str], str]:
    """Resolve CLI region selection while preserving legacy no-arg behavior."""

    regions = load_phase4_regions(regions_file)
    requested_region_list = list(requested_region_ids)
    explicit_region_ids = (
        resolve_phase4_region_ids(regions, requested_region_list)
        if requested_region_list
        else []
    )

    if requested_subset is None and not explicit_region_ids:
        return ([region.region_id for region in regions], "legacy-all-regions")

    if requested_subset is not None and explicit_region_ids:
        raise ValueError("Ambiguous region selector: pass either --subset or --region, not both")

    if requested_subset is not None:
        contract = load_phase4_evidence_contract(regions_file=regions_file)
        contract_region_ids = contract.resolve_region_ids(subset=requested_subset)
        return (
            resolve_phase4_region_ids(regions, contract_region_ids),
            f"contract-subset:{requested_subset.strip().lower()}",
        )

    duplicates = _find_duplicate_region_ids(explicit_region_ids)
    if duplicates:
        raise ValueError("Duplicate region ids requested: " + ", ".join(duplicates))

    return (explicit_region_ids, "explicit-region-list")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="[%(levelname)s] %(message)s",
    )

    time_range = (f"{args.start_year}-01-01", f"{args.end_year}-12-31")
    logging.info(
        "Phase4 data run start: standardized_dir=%s "
        "gwd30_source=stage1_pixel_stats mask_source=berkeley_valid time_range=%s",
        args.standardized_dir,
        time_range,
    )

    try:
        region_ids, selector_mode = resolve_cli_region_ids(
            regions_file=args.regions_file,
            requested_subset=args.subset,
            requested_region_ids=args.region,
        )
    except Exception as exc:
        logger.error(
            "stage=region-selector subset=%s requested_regions=%s error=%s",
            args.subset or "<none>",
            args.region,
            exc,
        )
        raise

    selector_subset = args.subset or (
        "explicit-region-list" if args.region else "legacy-all-regions"
    )
    logger.info(
        "stage=region-selector subset=%s selector_mode=%s region_ids=%s",
        selector_subset,
        selector_mode,
        region_ids,
    )

    regions = load_phase4_regions(args.regions_file)
    dataset_ids = resolve_phase4_dataset_ids(args.dataset_id)
    region_lookup = {region.region_id: region for region in regions}

    for region_id in region_ids:
        region = region_lookup[region_id]
        logging.info("Phase4 region start: %s bbox=%s", region.region_id, region.bbox)
        region_mask = build_or_load_phase4_berkeley_valid_mask(
            region=region,
            output_root=args.output_root,
            standardized_dir=args.standardized_dir,
            time_range=time_range,
            skip_existing=args.skip,
        )
        dataset_tables: list[pd.DataFrame] = []
        for dataset_id in dataset_ids:
            dataset_tables.append(
                compute_phase4_region_dataset_table(
                    dataset_id,
                    region=region,
                    base_mask=region_mask,
                    output_root=args.output_root,
                    standardized_dir=args.standardized_dir,
                    time_range=time_range,
                    skip_existing=args.skip,
                    topmodel_raw_path=args.topmodel_raw_path,
                    spatial_lat_chunk_size=args.spatial_lat_chunk_size,
                    time_chunk_size=args.time_chunk_size,
                    show_progress=args.progress,
                )
            )
        table_path = build_phase4_region_table(
            region=region,
            dataset_tables=dataset_tables,
            output_root=args.output_root,
        )
        logging.info("Phase4 data write complete: region=%s table=%s", region.region_id, table_path)


if __name__ == "__main__":
    main()
