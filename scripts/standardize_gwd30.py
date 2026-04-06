#!/usr/bin/env python
"""Standardize GWD30 to annual netCDF files.

Usage:
    # Full run
    python scripts/standardize_gwd30.py --year 2016 --output-dir output/standardized

    # Skip stage if tiles already exist
    python scripts/standardize_gwd30.py --year 2016 --skip-stage --output-dir output/standardized

"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import xarray as xr

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.config import load_dataset_config  # noqa: E402
from WA.loaders import get_loader  # noqa: E402
from WA.loaders.base import BBox  # noqa: E402
from WA.standardize import (  # noqa: E402
    _build_gwd30_output_from_staged_tiles,
    _load_gwd30_staged_tiles_from_stage_shard_manifests,
    _reference_grid_resolution_m,
    build_reference_grid,
)

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


def standardize_gwd30_year(
    loader: Any,
    reference_grid: xr.DataArray,
    bbox: BBox,
    output_dir: Path,
    year: int,
    *,
    skip_stage: bool = False,
    skip_existing: bool = False,
) -> Path:
    """Standardize one GWD30 year."""
    output_path = output_dir / f"gwd30_{year}.nc"
    logger.info("GWD30 %s: standardizing %s", year, output_path.name)

    if skip_existing and output_path.exists():
        logger.info("  skipping %s (exists)", output_path.name)
        return output_path

    staging_root = output_dir / "_staging" / f"gwd30_{year}"

    # Step 1: Stage tiles (or reuse existing)
    tile_stage_dir = staging_root / "tile_partials"
    tile_stage_dir.mkdir(parents=True, exist_ok=True)

    if skip_stage:
        staged_tiles = _load_gwd30_staged_tiles_from_stage_shard_manifests(staging_root)
        if not staged_tiles:
            raise RuntimeError(
                f"--skip-stage specified but no staged tile metadata found under {staging_root}"
            )
        logger.info(
            "GWD30 %s: skipping stage, reusing %d existing tiles", year, len(staged_tiles)
        )
    else:
        # Clean stale tiles
        stale = list(tile_stage_dir.glob("tile_*.nc"))
        for f in stale:
            f.unlink()
        if stale:
            logger.info("cleared %d stale tile files", len(stale))

        staged_tiles = loader.stage_time_fraction_tiles(
            bbox=bbox,
            reference_grid=reference_grid,
            year=year,
            staging_dir=tile_stage_dir,
            worker_count=4,
            show_progress=True,
            skip_existing=skip_existing,
        )

        if not staged_tiles:
            raise RuntimeError(f"No GWD30 tiles staged for {year}")

    logger.info("GWD30 %s: staged %d tiles", year, len(staged_tiles))
    _build_gwd30_output_from_staged_tiles(
        loader=loader,
        output_path=output_path,
        reference_grid=reference_grid,
        staged_tiles=staged_tiles,
        year=year,
        resolution_m=_reference_grid_resolution_m(reference_grid),
        skip_existing=skip_existing,
    )

    logger.info("GWD30 %s: complete -> %s", year, output_path)

    logger.info(
        "GWD30 %s: staged files preserved for verification:", year
    )
    logger.info(
        "  - tile_partials: %d files in %s",
        len(staged_tiles), tile_stage_dir,
    )
    logger.info(
        "To reclaim disk space, manually delete after verification."
    )
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standardize GWD30 to annual netCDF.",
    )
    parser.add_argument("--year", type=int, help="Year to process")
    parser.add_argument("--years", type=int, nargs="+", help="Years to process")
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        default=[-180, -35, 180, 35],
        help="Bounding box (default: -180 -35 180 35)",
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=500,
        help="Spatial resolution in meters (default: 500)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/standardized"),
        help="Output directory",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/datasets.yaml"),
        help="Path to datasets.yaml",
    )
    parser.add_argument(
        "--skip-stage",
        action="store_true",
        help="Skip stage phase, reuse existing tile_*.nc files",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip if output exists",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Debug logging"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    _configure_logging(verbose=args.verbose)

    if not args.year and not args.years:
        parser.error("--year or --years required")

    years = [args.year] if args.year else args.years

    # Build reference grid
    bbox = tuple(args.bbox)
    logger.info("Building reference grid: resolution=%sm, bbox=%s", args.resolution, bbox)
    reference_grid = build_reference_grid(bbox, resolution_m=args.resolution)
    logger.info(
        "Reference grid: %d lat x %d lon",
        reference_grid.sizes["lat" if "lat" in reference_grid.sizes else "y"],
        reference_grid.sizes["lon" if "lon" in reference_grid.coords else "x"],
    )

    # Load config and loader
    dataset_doc = load_dataset_config(args.config)
    loader = get_loader("gwd30", dataset_doc["datasets"]["gwd30"])

    args.output_dir.mkdir(parents=True, exist_ok=True)

    output_paths = []
    for year in years:
        output_path = standardize_gwd30_year(
            loader=loader,
            reference_grid=reference_grid,
            bbox=bbox,
            output_dir=args.output_dir,
            year=year,
            skip_stage=args.skip_stage,
            skip_existing=args.skip_existing,
        )
        output_paths.append(output_path)

    logger.info("GWD30 standardization complete: %d output(s)", len(output_paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
