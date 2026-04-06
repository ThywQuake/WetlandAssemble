#!/usr/bin/env python
"""Standardise all wetland datasets to a WGS84 500 m compressed netCDF grid.

Usage::

    python scripts/standardize_datasets.py \\
        --output-dir output/standardized/ \\
        --datasets g2017 glwd_v2 \\
        --skip-existing
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the project src/ is on the path when running as a script.
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.config import load_dataset_config  # noqa: E402
from WA.standardize import ALL_DATASET_IDS, build_reference_grid, standardize_all  # noqa: E402

logger = logging.getLogger("WA.standardize")

DATASET_ALIASES = {
    "berkeley": "berkeley_rwawc",
    "giems": "giems_mc",
    "glwd": "glwd_v2",
}

_NOISY_LOGGERS = (
    "rasterio",
    "rioxarray",
    "pyproj",
    "fiona",
)


def _normalize_dataset_ids(dataset_ids: list[str]) -> list[str]:
    """Resolve shorthand dataset aliases and preserve user order."""
    normalized: list[str] = []
    seen: set[str] = set()
    for dataset_id in dataset_ids:
        resolved = DATASET_ALIASES.get(dataset_id, dataset_id)
        if resolved not in ALL_DATASET_IDS:
            choices = ", ".join(ALL_DATASET_IDS + sorted(DATASET_ALIASES))
            raise SystemExit(f"Unknown dataset {dataset_id!r}. Valid choices: {choices}")
        if resolved not in seen:
            normalized.append(resolved)
            seen.add(resolved)
    return normalized


def _configure_logging(*, verbose: bool) -> None:
    """Configure concise default logging for HPC runs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("WA").setLevel(logging.DEBUG if verbose else logging.INFO)
    for logger_name in _NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Standardise wetland datasets onto a unified WGS84 500 m grid.",
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=500,
        help="Spatial resolution in metres (default: 500)",
    )
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        default=[-180, -35, 180, 35],
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help="Bounding box (default: [-180, -35, 180, 35])",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/standardized"),
        help="Output directory (default: output/standardized/)",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=ALL_DATASET_IDS,
        help="Dataset IDs to process (default: all 8; aliases: glwd, giems, berkeley)",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        help="Restrict temporal datasets to one or more calendar years",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip output files that already exist (checkpoint/restart)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/datasets.yaml"),
        help="Path to datasets.yaml",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    parser.add_argument(
        "--list-datasets",
        action="store_true",
        help="List supported dataset IDs and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved run configuration and exit",
    )
    parser.add_argument(
        "--metadata-path",
        type=Path,
        help="Write metadata summary to this path instead of output_dir/metadata.json",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Do not write metadata.json for this run",
    )

    args = parser.parse_args(argv)

    if args.list_datasets:
        for dataset_id in ALL_DATASET_IDS:
            print(dataset_id)
        if DATASET_ALIASES:
            print("")
            print("# aliases")
            for alias, target in sorted(DATASET_ALIASES.items()):
                print(f"{alias} -> {target}")
        return

    _configure_logging(verbose=args.verbose)

    bbox = tuple(args.bbox)
    dataset_ids = _normalize_dataset_ids(list(args.datasets))

    if args.dry_run:
        print("standardize_datasets.py dry-run")
        print(f"  config:        {args.config}")
        print(f"  output_dir:    {args.output_dir}")
        print(f"  resolution_m:  {args.resolution}")
        print(f"  bbox:          {bbox}")
        print(f"  datasets:      {' '.join(dataset_ids)}")
        print(f"  years:         {args.years or 'all'}")
        print(f"  skip_existing: {args.skip_existing}")
        print(f"  verbose:       {args.verbose}")
        print(f"  metadata_path: {args.metadata_path or 'output_dir/metadata.json'}")
        print(f"  write_metadata:{not args.no_metadata}")
        return

    logger.info("Building reference grid: resolution=%dm, bbox=%s", args.resolution, bbox)
    reference_grid = build_reference_grid(bbox, resolution_m=args.resolution)
    logger.info(
        "Reference grid: %d lat × %d lon",
        reference_grid.sizes.get("lat", 0),
        reference_grid.sizes.get("lon", 0),
    )

    dataset_document = load_dataset_config(args.config)
    dataset_configs = dataset_document["datasets"]

    results = standardize_all(
        dataset_configs=dataset_configs,
        dataset_ids=dataset_ids,
        bbox=bbox,
        reference_grid=reference_grid,
        output_dir=args.output_dir,
        years=list(args.years) if args.years else None,
        skip_existing=args.skip_existing,
        config_path=str(args.config),
        metadata_path=args.metadata_path,
        write_metadata=not args.no_metadata,
    )

    # Summary
    ok = sum(1 for r in results.values() if r["status"] == "success")
    skip = sum(1 for r in results.values() if r["status"] == "skipped")
    fail = sum(1 for r in results.values() if r["status"] == "error")
    logger.info("Done: %d success, %d skipped, %d failed", ok, skip, fail)
    if fail:
        for ds_id, r in results.items():
            if r["status"] == "error":
                logger.error("  %s: %s", ds_id, r.get("error", "unknown"))
        sys.exit(1)


if __name__ == "__main__":
    main()
