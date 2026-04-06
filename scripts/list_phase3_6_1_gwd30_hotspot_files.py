#!/usr/bin/env python3
# ruff: noqa: E402
"""List raw/staged/reduced GWD30 file paths for selected hotspots."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from WA.comparison.phase36 import (  # noqa: E402
    DEFAULT_PHASE36_CACHE_DIR,
    DEFAULT_PHASE36_LAT_CHUNK_SIZE,
    DEFAULT_PHASE36_STANDARDIZED_DIR,
    DEFAULT_PHASE36_TARGET_YEAR,
)
from WA.phase361_gwd30_trace import run_phase361_hotspot_file_listing  # noqa: E402
from WA.s2_batch import DEFAULT_PHASE37_HOTSPOTS_MANIFEST  # noqa: E402

DEFAULT_PHASE361_OUTPUT_DIR = Path("results/phase3.6.1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 3.6.1: list raw tif, staged tile, and reduced tile file "
            "paths for selected GWD30 hotspots."
        ),
    )
    parser.add_argument(
        "--hotspots-manifest",
        type=Path,
        default=DEFAULT_PHASE37_HOTSPOTS_MANIFEST,
        help="Phase 3.7 hotspot manifest path",
    )
    parser.add_argument(
        "--hotspots",
        nargs="*",
        help="Optional explicit hotspot ids to inspect; preserves the provided order",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Optional: if --hotspots is omitted, list files for only the first "
            "N hotspots in the manifest; default is all hotspots"
        ),
    )
    parser.add_argument(
        "--standardized-dir",
        type=Path,
        default=DEFAULT_PHASE36_STANDARDIZED_DIR,
        help="Directory containing standardized outputs and GWD30 staged manifests",
    )
    parser.add_argument(
        "--phase36-cache-dir",
        type=Path,
        default=DEFAULT_PHASE36_CACHE_DIR,
        help="Directory containing Phase 3.6 staged caches",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_PHASE361_OUTPUT_DIR,
        help="Directory for JSON file-list outputs",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_PHASE36_TARGET_YEAR,
        help="Target year (default: 2016)",
    )
    parser.add_argument(
        "--lat-chunk-size",
        type=int,
        default=DEFAULT_PHASE36_LAT_CHUNK_SIZE,
        help="Phase 3.6 cache stripe size used to locate the reduced tile directory",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logger.info(
        "Phase3.6.1 file-list args: hotspots_manifest=%s hotspots=%s limit=%s "
        "standardized_dir=%s phase36_cache_dir=%s output_dir=%s year=%s "
        "lat_chunk_size=%s",
        args.hotspots_manifest,
        args.hotspots,
        args.limit,
        args.standardized_dir,
        args.phase36_cache_dir,
        args.output_dir,
        args.year,
        args.lat_chunk_size,
    )

    combined_path = run_phase361_hotspot_file_listing(
        hotspots_manifest=args.hotspots_manifest,
        standardized_dir=args.standardized_dir,
        phase36_cache_dir=args.phase36_cache_dir,
        output_dir=args.output_dir,
        year=args.year,
        lat_chunk_size=args.lat_chunk_size,
        hotspot_ids=args.hotspots,
        limit=args.limit,
    )
    logger.info("Phase 3.6.1 file list -> %s", combined_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
