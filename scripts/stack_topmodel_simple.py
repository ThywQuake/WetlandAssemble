#!/usr/bin/env python
"""Stack TOPMODEL config/forcing/year files into unified netCDF (no reprojection).

Simple version: directly traverse config/forcing/year directory structure.

Usage::

    python scripts/stack_topmodel_simple.py --output-dir output/standardized/ --years 2016 2017
    python scripts/stack_topmodel_simple.py --output-dir output/standardized/ --skip-existing
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import xarray as xr

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.utils.progress import tqdm

logger = logging.getLogger("WA.stack_topmodel")


def stack_topmodel_simple(
    topmodel_dir: Path,
    output_dir: Path,
    *,
    years: list[int] | None = None,
    skip_existing: bool = False,
) -> list[Path]:
    """Stack TOPMODEL files: config/forcing/year -> output/topmodel_{year}.nc"""
    output_paths: list[Path] = []

    # Discover years from directory structure
    available_years = set()
    for config_dir in topmodel_dir.iterdir():
        if not config_dir.is_dir():
            continue
        for forcing_dir in config_dir.iterdir():
            if not forcing_dir.is_dir():
                continue
            for nc_file in forcing_dir.glob("*.nc"):
                try:
                    # Pattern: fwet_{config}_{forcing}_reso025_{year}.nc
                    year = int(nc_file.stem.split("_")[-1])
                    available_years.add(year)
                except (ValueError, IndexError):
                    continue

    all_years = sorted(available_years)
    if not all_years:
        logger.error("No TOPMODEL years found in %s", topmodel_dir)
        return []

    if years is None:
        years = all_years
    else:
        years = [y for y in years if y in all_years]

    if not years:
        logger.error("No matching years to process")
        return []

    logger.info("Stacking TOPMODEL for years: %s", years)

    for year in tqdm(years, desc="TOPMODEL"):
        output_path = output_dir / f"topmodel_{year}.nc"

        if skip_existing and output_path.exists():
            logger.info("  skipping %s (exists)", output_path.name)
            output_paths.append(output_path)
            continue

        datasets_by_config: dict[str, list[xr.Dataset]] = {}

        for config_dir in tqdm(topmodel_dir.iterdir(), desc="  configs", leave=False):
            if not config_dir.is_dir():
                continue
            config_name = config_dir.name

            for forcing_dir in tqdm(config_dir.iterdir(), desc="  forcings", leave=False):
                if not forcing_dir.is_dir():
                    continue
                forcing_name = forcing_dir.name

                # Find file for this year
                nc_file = next(
                    forcing_dir.glob(f"*_{year}.nc"),
                    None
                )
                if nc_file is None:
                    continue

                try:
                    ds = xr.open_dataset(nc_file)
                    data = ds["fwet"].rename("wetland_fraction")

                    # Build month index for this year
                    month_nums = [int(v) for v in data["time"].values]
                    from WA.loaders._shared import monthly_index_for_year
                    time_idx = monthly_index_for_year(year, month_nums)

                    dataset = data.to_dataset().assign_coords(time=time_idx)
                    dataset = dataset.expand_dims(forcing=[forcing_name])

                    if config_name not in datasets_by_config:
                        datasets_by_config[config_name] = []
                    datasets_by_config[config_name].append(dataset)

                except Exception as e:
                    logger.warning("    failed %s: %s", nc_file.name, e)

        if not datasets_by_config:
            logger.warning("  no data for year %d", year)
            continue

        # Stack: forcings -> configs -> final
        config_datasets = []
        for config_name in sorted(datasets_by_config.keys()):
            forcing_ds = xr.concat(
                sorted(datasets_by_config[config_name], key=lambda x: str(x["forcing"].values[0])),
                dim="forcing"
            ).expand_dims(config=[config_name])
            config_datasets.append(forcing_ds)

        if not config_datasets:
            continue

        final = xr.concat(config_datasets, dim="config")
        # time is already DatetimeIndex from monthly_index_for_year

        final.attrs.update({
            "dataset_id": "topmodel",
            "is_static": "false",
            "is_classification": "false",
            "processing": "stacked_no_reprojection",
        })

        final.to_netcdf(output_path, encoding={"wetland_fraction": {
            "zlib": True,
            "complevel": 4,
            "shuffle": True,
        }})

        output_paths.append(output_path)
        logger.info("  wrote %s", output_path.name)

    return output_paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Stack TOPMODEL config/forcing/year files")
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
        help="Skip existing output files",
    )
    parser.add_argument(
        "--topmodel-dir",
        type=Path,
        default=Path("/lustre/home/2200013429/Wetland_Assemble/data/TOPMODEL/"),
        help="TOPMODEL data directory",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    results = stack_topmodel_simple(
        topmodel_dir=args.topmodel_dir,
        output_dir=args.output_dir,
        years=args.years,
        skip_existing=args.skip_existing,
    )

    logger.info("Done: %d file(s)", len(results))


if __name__ == "__main__":
    main()
