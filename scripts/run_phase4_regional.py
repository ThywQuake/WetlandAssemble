#!/usr/bin/env python3
"""Run Phase 4 regional wetland-percentage data processing."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Phase 4 regional area-weighted wetland-percentage caches and tables."
        )
    )
    parser.add_argument("--regions-file", default=str(DEFAULT_PHASE4_REGIONS_FILE))
    parser.add_argument("--region", action="append", default=[])
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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

    regions = load_phase4_regions(args.regions_file)
    region_ids = resolve_phase4_region_ids(regions, args.region)
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
