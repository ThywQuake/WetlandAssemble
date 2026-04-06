#!/usr/bin/env python
"""Merge GWD30 staged tiles into regional blocks using tree-reduce.

After running stage_time_fraction_tiles(), this script reduces the large
number of tile files (~10000) into a smaller set of regional files (~30)
for faster final merging.

Usage:
    python scripts/merge_gwd30_regions.py \
        --staging-dir output/standardized/_staging/gwd30_2016/tile_partials \
        --target-count 30 \
        --workers 8

The script will:
1. Find all tile_*.nc files in the staging directory
2. Perform tree-structured pairwise merging
3. Output ~30 regional_*.nc files
4. Optionally clean up original tile files (with --cleanup)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.loaders.base import BBox
from WA.utils.tree_reduce import merge_gwd30_staged_tiles, tree_reduce

logger = logging.getLogger(__name__)

_NOISY_LOGGERS = ("rasterio", "rioxarray", "pyproj", "fiona", "xarray")


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("WA").setLevel(logging.DEBUG if verbose else logging.INFO)
    for logger_name in _NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def _load_tile_manifest(staging_dir: Path) -> list[tuple[Path, BBox]]:
    """Load staged tiles from manifest or discover from filesystem."""
    manifest_path = staging_dir.parent / "manifest.json"

    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        return [(Path(item["path"]), tuple(item["bbox"])) for item in manifest["staged_tiles"]]

    # Discover tile_*.nc files
    tiles = sorted(staging_dir.glob("tile_*.nc"))
    logger.info("Discovered %d tile files in %s", len(tiles), staging_dir)
    return [(path, (0.0, 0.0, 0.0, 0.0)) for path in tiles]  # Placeholder bbox


def _save_regional_manifest(regional_tiles: list[tuple[Path, BBox]], output_path: Path) -> None:
    """Save manifest of regional files."""
    manifest = {
        "regional_tile_count": len(regional_tiles),
        "regional_tiles": [
            {"path": str(path), "bbox": list(bbox)} for path, bbox in regional_tiles
        ],
    }
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    logger.info("Saved regional manifest: %s", output_path)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge GWD30 staged tiles into regional blocks.",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        required=True,
        help="Directory containing tile_*.nc files",
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=30,
        help="Target number of regional files (default: 30)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete original tile_*.nc files after successful merge",
    )
    parser.add_argument(
        "--no-cleanup-rounds",
        action="store_true",
        help="Do not delete intermediate round files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually merging",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    _configure_logging(verbose=args.verbose)

    staging_dir = args.staging_dir
    if not staging_dir.exists():
        logger.error("Staging directory does not exist: %s", staging_dir)
        return 1

    # Load staged tiles
    staged_tiles = _load_tile_manifest(staging_dir)
    if not staged_tiles:
        logger.error("No staged tiles found in %s", staging_dir)
        return 1

    logger.info(
        "Starting tree-reduce: %d tiles -> ~%d regional files",
        len(staged_tiles),
        args.target_count,
    )

    if args.dry_run:
        logger.info("[DRY RUN] Would merge %d tiles in ~%d rounds", len(staged_tiles), int(len(staged_tiles).bit_length()))
        logger.info("[DRY RUN] Output directory: %s", staging_dir)
        return 0

    # Perform tree-reduce
    regional_tiles = tree_reduce(
        inputs=staged_tiles,
        output_dir=staging_dir,
        merge_func=merge_gwd30_staged_tiles,
        target_count=args.target_count,
        worker_count=args.workers,
        show_progress=True,
        cleanup_rounds=not args.no_cleanup_rounds,
    )

    # Save manifest
    _save_regional_manifest(regional_tiles, staging_dir / "regional_manifest.json")

    # Clean up original tile files if requested
    if args.cleanup:
        logger.info("Cleaning up %d original tile files...", len(staged_tiles))
        for path, _ in staged_tiles:
            path.unlink(missing_ok=True)
        logger.info("Cleaned up %d tile files", len(staged_tiles))

    logger.info(
        "Merge complete: %d regional files in %s",
        len(regional_tiles),
        staging_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
