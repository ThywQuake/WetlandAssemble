#!/usr/bin/env python
"""Stack TOPMODEL config/forcing/year files into unified netCDF (no reprojection).

Usage::

    python scripts/stack_topmodel.py \\
        --output-dir output/standardized/ \\
        --years 2016 2017 \\
        --skip-existing
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.config import load_dataset_config
from WA.loaders.topmodel import TopmodelLoader
from WA.utils.progress import tqdm

logger = logging.getLogger("WA.stack_topmodel")

_ENCODING_DEFAULTS: dict[str, Any] = {
    "zlib": True,
    "complevel": 4,
    "shuffle": True,
}


def discover_topmodel_years(topmodel_path: Path | None = None) -> list[int]:
    """Discover available years from TOPMODEL config/files."""
    import re

    # Default HPC path
    if topmodel_path is None:
        topmodel_path = Path("/lustre/home/2200013429/Wetland_Assemble/data/TOPMODEL/")

    # Direct file discovery
    years = set()
    pattern = re.compile(r"_(\d{4})\.nc$")

    if topmodel_path.exists():
        for nc_file in topmodel_path.rglob("fwet_*_reso025_*.nc"):
            match = pattern.search(nc_file.name)
            if match:
                years.add(int(match.group(1)))

    years_list = sorted(years)

    if not years_list:
        logger.warning("TOPMODEL path: %s", topmodel_path)
        logger.warning("TOPMODEL base_path exists: %s", topmodel_path.exists())
        if topmodel_path.exists():
            # List subdirectories
            subdirs = list(topmodel_path.iterdir())[:10]
            logger.warning("TOPMODEL subdirs (first 10): %s", [d.name for d in subdirs])
            # Try to find any .nc files
            nc_files = list(topmodel_path.rglob("*.nc"))[:5]
            if nc_files:
                logger.warning("TOPMODEL .nc files found (first 5): %s", [f.name for f in nc_files])
            else:
                logger.warning("TOPMODEL: No .nc files found recursively")

            # Try alternative pattern
            alt_files = list(topmodel_path.rglob("fwet*.nc"))[:5]
            if alt_files:
                logger.warning("TOPMODEL fwet*.nc files found (first 5): %s", [f.name for f in alt_files])

    return years_list


def stack_topmodel(
    output_dir: Path,
    *,
    years: list[int] | None = None,
    skip_existing: bool = False,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[Path]:
    """Stack TOPMODEL files without reprojection.

    Output retains native 0.25° grid with (config, forcing, time, lat, lon) dims.
    """
    # Hardcoded HPC path - no more passing around
    TOPMODEL_PATH = Path("/lustre/home/2200013429/Wetland_Assemble/data/TOPMODEL/")

    output_paths: list[Path] = []

    if years is None:
        years = discover_topmodel_years(TOPMODEL_PATH)

    if not years:
        logger.warning("No TOPMODEL years found")
        return []

    logger.info("Stacking TOPMODEL for %d year(s): %s", len(years), years)

    for year in tqdm(years, desc="TOPMODEL years"):
        output_path = output_dir / f"topmodel_{year}.nc"

        if skip_existing and output_path.exists():
            logger.info("  skipping %s (exists)", output_path.name)
            output_paths.append(output_path)
            continue

        logger.info("Stacking year %d...", year)

        # Direct file discovery for this year
        import re
        year_pattern = re.compile(rf"_(\d{4})\.nc$")
        year_files: list[Path] = []

        # Hardcoded HPC path
        TOPMODEL_PATH = Path("/lustre/home/2200013429/Wetland_Assemble/data/TOPMODEL/")

        if TOPMODEL_PATH.exists():
            # Count all matching files
            all_count = 0
            for nc_file in TOPMODEL_PATH.rglob("fwet_*_reso025_*.nc"):
                all_count += 1
                match = year_pattern.search(nc_file.name)
                if match:
                    file_year = int(match.group(1))
                    if file_year == year:
                        year_files.append(nc_file)
            logger.info("  Scanned %d files, found %d for year %d", all_count, len(year_files), year)

            if all_count == 0:
                logger.warning("  No fwet_*_reso025_*.nc files found at all")
                # Try broader pattern
                broad_count = 0
                for nc_file in TOPMODEL_PATH.rglob("*.nc"):
                    broad_count += 1
                    if broad_count <= 3:
                        logger.warning("    Found: %s", nc_file.relative_to(TOPMODEL_PATH))
                logger.warning("  Total .nc files: %d", broad_count)

            # Show sample files for debugging
            if year_files and len(year_files) <= 3:
                for f in year_files[:3]:
                    logger.info("    Found: %s", f.relative_to(TOPMODEL_PATH))

        if not year_files:
            logger.warning("  no files found for year %d", year)
            continue

        # Group by config/forcing
        grouped: dict[tuple[str, str], list[Path]] = defaultdict(list)
        for path in year_files:
            parts = path.relative_to(TOPMODEL_PATH).parts
            if len(parts) >= 3:
                config_name = parts[0]
                forcing_name = parts[1]
                grouped[(config_name, forcing_name)].append(path)

        by_config: dict[str, list[xr.Dataset]] = defaultdict(list)

        for (config_name, forcing_name), paths in grouped.items():
            logger.info("  config=%s forcing=%s (%d file(s))", config_name, forcing_name, len(paths))

            year_datasets: list[xr.Dataset] = []
            for path in paths:
                try:
                    with xr.open_dataset(path) as source:
                        data = source["fwet"].rename("wetland_fraction")
                        month_numbers = [int(v) for v in data["time"].values]

                        from WA.loaders._shared import monthly_index_for_year
                        data = data.assign_coords(time=monthly_index_for_year(year, month_numbers))

                        dataset = data.to_dataset()

                        if bbox is not None:
                            from WA.loaders.base import apply_bbox
                            dataset = apply_bbox(dataset, bbox)

                        year_datasets.append(dataset.load())

                except Exception as e:
                    logger.warning("    failed to load %s: %s", path.name, e)
                    continue

            if not year_datasets:
                continue

            merged_years = xr.concat(year_datasets, dim="time").sortby("time")
            by_config[config_name].append(merged_years.expand_dims(forcing=[forcing_name]))

        if not by_config:
            logger.warning("  no valid data stacked for year %d", year)
            continue

        config_datasets: list[xr.Dataset] = []
        for config_name, forcing_datasets in sorted(by_config.items()):
            ordered_forcings = sorted(
                forcing_datasets,
                key=lambda item: str(item["forcing"].values[0]),
            )
            forcing_merged = xr.concat(ordered_forcings, dim="forcing")
            config_datasets.append(forcing_merged.expand_dims(config=[config_name]))

        if not config_datasets:
            continue

        final = xr.concat(config_datasets, dim="config", join="outer")

        final["time"] = xr.to_datetime(final["time"])

        final.attrs.update({
            "dataset_id": "topmodel",
            "dataset_name": "TOPMODEL",
            "is_static": False,
            "is_classification": False,
            "native_variables": ("wetland_fraction",),
            "standardized_resolution": "native_0.25deg",
            "processing": "stacked_no_reprojection",
        })

        encoding = {"wetland_fraction": dict(_ENCODING_DEFAULTS)}

        final.to_netcdf(output_path, encoding=encoding)
        output_paths.append(output_path)
        logger.info("  wrote %s", output_path.name)

    return output_paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Stack TOPMODEL files without reprojection."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/standardized"),
        help="Output directory",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        help="Years to stack",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip existing files",
    )
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        metavar=("W", "S", "E", "N"),
        help="Optional bbox to subset during stacking",
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
        "--dry-run",
        action="store_true",
        help="Print configuration and exit",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    if args.verbose:
        logging.getLogger("WA").setLevel(logging.DEBUG)

    if args.dry_run:
        print("stack_topmodel.py dry-run")
        print(f"  config:       {args.config}")
        print(f"  output_dir:   {args.output_dir}")
        print(f"  years:        {args.years or 'all'}")
        print(f"  skip_existing:{args.skip_existing}")
        print(f"  bbox:         {args.bbox or 'full'}")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)

    dataset_config = load_dataset_config(args.config)
    topmodel_config = dataset_config["datasets"]["topmodel"]

    loader = TopmodelLoader("topmodel", topmodel_config)

    # Use hardcoded HPC path for discovery
    hpc_topmodel_path = Path("/lustre/home/2200013429/Wetland_Assemble/data/TOPMODEL/")
    logger.info("TOPMODEL path: %s", hpc_topmodel_path)

    # Discover years first
    available_years = discover_topmodel_years(hpc_topmodel_path)
    logger.info("Available years: %s", available_years)

    # Filter by user-specified years if provided
    if args.years:
        available_years = [y for y in available_years if y in args.years]

    if not available_years:
        logger.error("No TOPMODEL years to process")
        return

    results = stack_topmodel(
        output_dir=args.output_dir,
        topmodel_path=hpc_topmodel_path,
        years=available_years,
        skip_existing=args.skip_existing,
        bbox=tuple(args.bbox) if args.bbox else None,
    )

    logger.info("Done: stacked %d file(s)", len(results))


if __name__ == "__main__":
    main()
