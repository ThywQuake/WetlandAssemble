#!/usr/bin/env python3
"""Phase 3.6: global 500m classification disagreement analysis."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

# ruff: noqa: E402
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from WA.comparison.phase36 import (
    DEFAULT_PHASE36_CACHE_DIR,
    DEFAULT_PHASE36_LAT_CHUNK_SIZE,
    DEFAULT_PHASE36_OUTPUT_DIR,
    DEFAULT_PHASE36_STANDARDIZED_DIR,
    DEFAULT_PHASE36_TARGET_YEAR,
    load_phase36_inputs,
    run_phase36_analysis,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 3.6: compute global 500m classification disagreement "
            "between G2017, GLWD v2, and GWD30 on the strict three-way overlap"
        ),
    )
    parser.add_argument(
        "--standardized-dir",
        type=Path,
        default=DEFAULT_PHASE36_STANDARDIZED_DIR,
        help="Directory containing standardized 500m NetCDF products",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_PHASE36_OUTPUT_DIR,
        help="Directory for Phase 3.6 outputs",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_PHASE36_CACHE_DIR,
        help="Directory for global staged caches",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_PHASE36_TARGET_YEAR,
        help="Target year for GWD30 (default: 2016)",
    )
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="Optional lon/lat bounding box to subset before comparison",
    )
    parser.add_argument(
        "--lat-chunk-size",
        type=int,
        default=DEFAULT_PHASE36_LAT_CHUNK_SIZE,
        help="Number of latitude rows to process per stripe",
    )
    parser.add_argument(
        "--static-worker-count",
        type=int,
        help=(
            "Optional explicit worker count for Phase 3.6 static dataset cache generation. "
            "Set to 2 to process G2017 and GLWD v2 in parallel."
        ),
    )
    parser.add_argument(
        "--gwd30-worker-count",
        type=int,
        help=(
            "Optional explicit worker count for GWD30 staged/reduced tile transforms. "
            "If set, this may exceed the default automatic safe cap of 4."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate inputs and report grid shape; do not write outputs",
    )
    parser.add_argument(
        "--no-prefer-cache",
        action="store_false",
        dest="prefer_cache",
        help="Recompute stages even if global cache files already exist",
    )
    parser.add_argument(
        "--no-write-cache",
        action="store_false",
        dest="write_cache",
        help="Do not write global staged cache files during this run",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    bbox = tuple(args.bbox) if args.bbox is not None else None
    logger.info(
        "Phase3.6 CLI args: standardized_dir=%s output_dir=%s cache_dir=%s year=%s bbox=%s "
        "lat_chunk_size=%s static_worker_count=%s gwd30_worker_count=%s dry_run=%s "
        "prefer_cache=%s write_cache=%s",
        args.standardized_dir,
        args.output_dir,
        args.cache_dir,
        args.year,
        bbox,
        args.lat_chunk_size,
        args.static_worker_count,
        args.gwd30_worker_count,
        args.dry_run,
        args.prefer_cache,
        args.write_cache,
    )

    if args.dry_run:
        logger.info("Phase3.6 dry-run start")
        inputs = load_phase36_inputs(
            args.standardized_dir,
            year=args.year,
            bbox=bbox,
        )
        try:
            template = inputs.datasets["g2017"]
            lat_dim = "lat" if "lat" in template.dims else "y"
            lon_dim = "lon" if "lon" in template.dims else "x"
            logger.info(
                "dry-run ok: grid=%s x %s, year=%s, bbox=%s",
                template.sizes[lat_dim],
                template.sizes[lon_dim],
                args.year,
                bbox,
            )
        finally:
            for dataset in inputs.datasets.values():
                dataset.close()
        logger.info("Phase3.6 dry-run complete")
        return 0

    outputs = run_phase36_analysis(
        standardized_dir=args.standardized_dir,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        year=args.year,
        bbox=bbox,
        lat_chunk_size=args.lat_chunk_size,
        static_worker_count=args.static_worker_count,
        gwd30_worker_count=args.gwd30_worker_count,
        prefer_cache=args.prefer_cache,
        write_cache=args.write_cache,
    )
    logger.info("Phase 3.6 complete")
    logger.info("  metrics   -> %s", outputs.metrics_path)
    logger.info("  classes   -> %s", outputs.dominant_classes_path)
    logger.info("  summary   -> %s", outputs.summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
