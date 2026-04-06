#!/usr/bin/env python3
"""Generate coarse-scale wetland percentage distribution visualizations.

Reads standardized datasets and generates:
  1. Single dataset distribution maps
  2. Multi-dataset side-by-side comparisons
  3. Temporal evolution comparisons
  4. Statistical bar charts

Usage (single dataset):
    python scripts/plot_coarse_scale.py \
        --dataset berkeley_rwawc \
        --year 2020 \
        --region all

Usage (multi-dataset comparison):
    python scripts/plot_coarse_scale.py \
        --compare \
        --year 2016 \
        --region tropical_subtropical

Usage (temporal comparison):
    python scripts/plot_coarse_scale.py \
        --temporal \
        --region all
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Coarse-scale wetland percentage distribution visualization"
    )

    # Input data
    p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory containing standardized netCDF files (default: auto-detect HPC vs local)",
    )

    # Output
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/figures/phase16"),
        help="Directory for output PNGs",
    )

    # Region
    p.add_argument(
        "--region",
        choices=["tropical", "subtropical", "tropical_subtropical", "all"],
        default="all",
        help="Geographic region to visualize",
    )

    # Year
    p.add_argument(
        "--year",
        type=int,
        default=None,
        help="Specific year to plot (for multi-year datasets)",
    )

    # Mode selection
    mode_group = p.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--dataset",
        type=str,
        help="Single dataset ID to visualize (e.g., g2017, swamps)",
    )
    mode_group.add_argument(
        "--compare",
        action="store_true",
        help="Generate multi-dataset side-by-side comparison",
    )
    mode_group.add_argument(
        "--temporal",
        action="store_true",
        help="Generate temporal evolution comparison",
    )
    mode_group.add_argument(
        "--statistics",
        action="store_true",
        help="Generate statistical bar charts",
    )

    # Dataset filtering for multi-dataset modes
    p.add_argument(
        "--datasets",
        type=str,
        nargs="+",
        default=None,
        help="Specific datasets to include in comparison (default: all available)",
    )

    # Output options
    p.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Output DPI (default: 150)",
    )

    # Progress display
    p.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bars during data processing and plotting",
    )
        help="Output DPI (default: 150)",
    )

    return p.parse_args()


def _load_dataset(data_dir: Path, dataset_id: str, year: int | None = None) -> object | None:
    """Load a standardized dataset, handling both static and time-series files."""
    import xarray as xr

    # Static datasets (single file)
    static_datasets = ["g2017", "glwd_v2"]

    if dataset_id in static_datasets:
        file_path = data_dir / f"{dataset_id}.nc"
        if not file_path.exists():
            print(f"  [warn] static file not found: {file_path}", flush=True)
            return None
        return xr.open_dataset(file_path)

    # Time-series datasets (one file per year)
    if year is not None:
        file_path = data_dir / f"{dataset_id}_{year}.nc"
        if file_path.exists():
            return xr.open_dataset(file_path)
        print(f"  [warn] file not found: {file_path}", flush=True)
        return None

    # If no year specified, try to load all years and concatenate
    pattern = data_dir / f"{dataset_id}_*.nc"
    files = sorted(data_dir.glob(f"{dataset_id}_*.nc"))

    if not files:
        print(f"  [warn] no files found for {dataset_id}", flush=True)
        return None

    # Load and concatenate all years
    datasets = []
    for f in files:
        try:
            ds = xr.open_dataset(f)
            datasets.append(ds)
        except Exception as e:
            print(f"  [warn] failed to load {f}: {e}", flush=True)

    if not datasets:
        return None

    # Concatenate along time dimension if multiple files
    if len(datasets) == 1:
        return datasets[0]

    # Try to concatenate
    try:
        combined = xr.concat(datasets, dim="time", coords="minimal", compat="override")
        return combined
    except Exception as e:
        print(f"  [warn] failed to concatenate {dataset_id}: {e}", flush=True)
        # Return first available as fallback
        return datasets[0]


def _discover_available_datasets(data_dir: Path) -> list[str]:
    """Discover which datasets have standardized files available."""
    available = []

    # Check for static datasets
    for static_id in ["g2017", "glwd_v2"]:
        if (data_dir / f"{static_id}.nc").exists():
            available.append(static_id)

    # Check for time-series datasets (look for at least one year file)
    known_datasets = [
        "berkeley_rwawc", "giems_mc", "swamps", "topmodel", "wad2m"
    ]
    for ds_id in known_datasets:
        pattern = f"{ds_id}_*.nc"
        if list(data_dir.glob(pattern)):
            available.append(ds_id)

    return available


def _get_default_data_dir() -> Path:
    """Auto-detect data directory based on environment."""
    # Check if running on HPC (by hostname or environment variable)
    import os
    import socket

    # HPC environment detection
    hostname = socket.gethostname()
    if "wm2" in hostname or "data" in hostname:
        # Running on PKU HPC
        hpc_path = Path(os.path.expanduser("~/Wetland_Assemble/data/standardized"))
        if hpc_path.exists():
            return hpc_path

    # Local development
    local_path = Path("data/standardized")
    if local_path.exists():
        return local_path

    # Fallback to HPC path if local doesn't exist
    return Path(os.path.expanduser("~/Wetland_Assemble/data/standardized"))


def _run() -> int:
    args = _parse_args()

    # Auto-detect data directory if not specified
    if args.data_dir is None:
        args.data_dir = _get_default_data_dir()

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Lazy imports (heavy dependencies)
    from WA._geo_env import configure_geospatial_runtime
    configure_geospatial_runtime()

    from WA.visualization.coarse_scale import (
        plot_multi_dataset_comparison,
        plot_single_dataset_distribution,
        plot_temporal_comparison,
        plot_wetland_area_statistics,
    )

    t_total = time.time()

    # Single dataset mode
    if args.dataset:
        print(f"[single] dataset={args.dataset}, year={args.year}, region={args.region}", flush=True)

        dataset = _load_dataset(args.data_dir, args.dataset, args.year)
        if dataset is None:
            print(f"  [error] failed to load dataset: {args.dataset}", flush=True)
            return 1

        # Create progress callback if enabled
        def make_progress_callback(desc: str):
            if not args.progress:
                return None
            pbar = tqdm(total=100, desc=desc, leave=False)
            last_progress = 0

            def callback(current: int, total: int, message: str):
                nonlocal last_progress
                progress = int((current / total) * 100) if total > 0 else 100
                if progress > last_progress or current == total:
                    pbar.n = progress
                    pbar.set_postfix_str(message)
                    pbar.refresh()
                    last_progress = progress
                if current == total:
                    pbar.close()
            return callback

        try:
            progress_cb = make_progress_callback("Plotting")
            output_path = plot_single_dataset_distribution(
                dataset=dataset,
                dataset_id=args.dataset,
                region=args.region,
                year=args.year,
                output_path=args.output_dir / f"{args.dataset}_wetland_{args.region}.png",
                dpi=args.dpi,
                progress_callback=progress_cb,
            )
            print(f"  saved: {output_path}", flush=True)
        finally:
            dataset.close()

        elapsed = time.time() - t_total
        print(f"[single] done in {elapsed:.1f}s", flush=True)
        return 0

    # Multi-dataset modes
    # Discover available datasets
    available = _discover_available_datasets(args.data_dir)
    print(f"[info] available datasets: {available}", flush=True)

    # Filter by user request if specified
    if args.datasets:
        available = [ds for ds in args.datasets if ds in available]
        if not available:
            print("[error] no requested datasets available", flush=True)
            return 1

    if not available:
        print("[error] no datasets found in data directory", flush=True)
        return 1

    # Load datasets with progress bar
    from tqdm import tqdm

    datasets: dict[str, object] = {}
    print(f"  Loading {len(available)} dataset(s)...", flush=True)
    for ds_id in tqdm(available, desc="Loading datasets", disable=not args.progress):
        ds = _load_dataset(args.data_dir, ds_id, args.year)
        if ds is not None:
            datasets[ds_id] = ds

    if not datasets:
        print("[error] failed to load any datasets", flush=True)
        return 1

    try:
        # Create progress callback if enabled
        def make_progress_callback(desc: str):
            if not args.progress:
                return None
            pbar = tqdm(total=100, desc=desc, leave=False)
            last_progress = 0

            def callback(current: int, total: int, message: str):
                nonlocal last_progress
                progress = int((current / total) * 100) if total > 0 else 100
                if progress > last_progress or current == total:
                    pbar.n = progress
                    pbar.set_postfix_str(message)
                    pbar.refresh()
                    last_progress = progress
                if current == total:
                    pbar.close()
            return callback

        # Multi-dataset comparison mode
        if args.compare:
            print(f"[compare] {len(datasets)} datasets, year={args.year}, region={args.region}", flush=True)
            progress_cb = make_progress_callback("Plotting")

            output_path = plot_multi_dataset_comparison(
                datasets=datasets,
                region=args.region,
                year=args.year,
                output_path=args.output_dir / f"multi_comparison_{args.region}.png",
                dpi=args.dpi,
                progress_callback=progress_cb,
            )
            print(f"  saved: {output_path}", flush=True)

        # Temporal comparison mode
        elif args.temporal:
            print(f"[temporal] {len(datasets)} datasets, region={args.region}", flush=True)
            progress_cb = make_progress_callback("Plotting")

            output_path = plot_temporal_comparison(
                datasets=datasets,
                region=args.region,
                output_path=args.output_dir / f"temporal_comparison_{args.region}.png",
                dpi=args.dpi,
                progress_callback=progress_cb,
            )
            print(f"  saved: {output_path}", flush=True)

        # Statistics mode
        elif args.statistics:
            print(f"[statistics] {len(datasets)} datasets, year={args.year}, region={args.region}", flush=True)
            progress_cb = make_progress_callback("Plotting")

            output_path = plot_wetland_area_statistics(
                datasets=datasets,
                region=args.region,
                year=args.year,
                output_path=args.output_dir / f"wetland_statistics_{args.region}.png",
                dpi=args.dpi,
                progress_callback=progress_cb,
            )
            print(f"  saved: {output_path}", flush=True)

    finally:
        # Close all datasets
        for ds in datasets.values():
            close = getattr(ds, "close", None)
            if callable(close):
                close()

    elapsed = time.time() - t_total
    print(f"[done] completed in {elapsed:.1f}s ({elapsed / 60:.1f}m)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(_run())
