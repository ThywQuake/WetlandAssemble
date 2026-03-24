#!/usr/bin/env python3
"""Generate Phase 2.5 comparison panel figures from Phase 2 rough probe output.

Usage:
    uv run python scripts/plot_comparison_panels.py \\
        --phase2-root results/phase2/rough \\
        --output-dir results/figures \\
        --year 2016 \\
        --region "Tropical"

Reads focus_areas.csv, comparison_grids.nc from each region/YYYYMM
subdirectory under --phase2-root.
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
from pathlib import Path

import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate Phase 2.5 comparison panels")
    p.add_argument(
        "--phase2-root", type=str, default="results/phase2/rough",
        help="Root of Phase 2 rough output (default: results/phase2/rough)",
    )
    p.add_argument(
        "--output-dir", type=str, default="results/figures",
        help="Output directory for PNG files (default: results/figures)",
    )
    p.add_argument(
        "--year", type=int, default=2016,
        help="Reference year for title (default: 2016)",
    )
    p.add_argument(
        "--region", type=str, default="Tropical",
        help="Region label for title (default: Tropical)",
    )
    p.add_argument(
        "--results-root", type=str, default="results",
        help="Root for satellite imagery lookup (default: results)",
    )
    p.add_argument(
        "--dpi", type=int, default=200,
        help="Output DPI (default: 200)",
    )
    return p.parse_args()


def _run() -> int:
    args = _parse_args()

    print("[plot] loading config and imports …", flush=True)
    from WA.comparison.harmonize import EXCLUDED_BINARY_DATASET_IDS
    from WA.config import load_config
    from WA.loaders import get_loader
    from WA.visualization.comparison_panel import (
        load_native_wetland_surface,
        make_dataset_labels,
        plot_comparison_panel,
    )

    config = load_config("config/datasets.yaml", "config/gee_config.yaml")
    phase2_root = Path(args.phase2_root)
    output_dir = Path(args.output_dir)
    results_root = Path(args.results_root)

    # --- Discover focus areas from Phase 2 rough output ---
    focus_area_files = sorted(phase2_root.glob("*/*/focus_areas.csv"))
    if not focus_area_files:
        print(f"[plot] no focus_areas.csv found under {phase2_root}", flush=True)
        return 0

    all_focus_areas: list[dict] = []
    for fa_path in focus_area_files:
        run_dir = fa_path.parent
        grids_path = run_dir / "comparison_grids.nc"
        df = pd.read_csv(fa_path)
        for _, row in df.iterrows():
            all_focus_areas.append({
                "aoi_id": row["aoi_id"],
                "region_slug": row["region_slug"],
                "target_time": pd.Timestamp(str(row["target_time"])).to_period("M").to_timestamp(),
                "bbox": _parse_bbox(row["bbox"]),
                "run_dir": run_dir,
                "grids_path": grids_path,
            })

    print(
        f"[plot] {len(all_focus_areas)} focus area(s) from "
        f"{len(focus_area_files)} region(s)",
        flush=True,
    )

    # --- Determine participating datasets ---
    ds_ids = sorted(
        ds_id for ds_id in config.datasets
        if ds_id not in EXCLUDED_BINARY_DATASET_IDS
    )
    labels = make_dataset_labels(ds_ids)

    for i, fa in enumerate(all_focus_areas):
        aoi_id = fa["aoi_id"]
        region_slug = fa["region_slug"]
        target_time = fa["target_time"]
        bbox = fa["bbox"]

        print(
            f"\n[plot] ({i+1}/{len(all_focus_areas)}) {aoi_id} — {region_slug}",
            flush=True,
        )
        t0 = time.time()

        # --- Load pre-computed disagreement + mean wetland from Phase 2 ---
        grids_path: Path = fa["grids_path"]
        if grids_path.exists():
            grids = xr.open_dataset(grids_path)
            # Subset to focus area bbox
            west, south, east, north = bbox
            disagreement = grids["disagreement_score"].sel(
                lat=slice(north, south), lon=slice(west, east),
            ).load()
            mean_wetland = grids["wetland_vote_fraction"].sel(
                lat=slice(north, south), lon=slice(west, east),
            ).load()
            grids.close()
            disagreement.name = "entropy"
            mean_wetland.name = "mean_wetland"
        else:
            print(f"  no comparison_grids.nc, skipping {aoi_id}", flush=True)
            continue

        # --- Load datasets at native resolution within bbox ---
        dataset_surfaces: dict[str, xr.DataArray] = {}
        for ds_id in ds_ids:
            ds_config = config.datasets.get(ds_id)
            if ds_config is None:
                continue
            try:
                loader = get_loader(ds_id, ds_config)
                surface = load_native_wetland_surface(
                    ds_id,
                    loader,
                    bbox,
                    target_time=target_time,
                )
                if surface is not None and int(surface.count().item()) > 0:
                    dataset_surfaces[ds_id] = surface
                    print(f"  {ds_id}: {surface.shape}", flush=True)
            except Exception as exc:
                print(f"  {ds_id}: SKIP ({exc})", flush=True)

        if not dataset_surfaces:
            print(f"  no datasets loaded, skipping {aoi_id}", flush=True)
            continue

        # --- Find satellite quicklook ---
        sat_path = _find_satellite_image(results_root, region_slug, aoi_id)

        # --- Plot ---
        out_file = output_dir / f"{aoi_id}_panel.png"
        plot_comparison_panel(
            bbox,
            satellite_image_path=sat_path,
            entropy_surface=disagreement,
            mean_wetland_surface=mean_wetland,
            dataset_surfaces=dataset_surfaces,
            dataset_labels=labels,
            year=args.year,
            region_label=args.region,
            hotspot_id=aoi_id,
            output_path=out_file,
            dpi=args.dpi,
        )
        elapsed = time.time() - t0
        print(f"  saved: {out_file} ({elapsed:.1f}s)", flush=True)
        dataset_surfaces.clear()
        del disagreement, mean_wetland
        gc.collect()

    print("\n[plot] done", flush=True)
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_bbox(bbox_value: object) -> tuple[float, float, float, float]:
    """Parse bbox from CSV cell — may be a string repr of a tuple."""
    if isinstance(bbox_value, str):
        # e.g. "(-60.0, -4.0, -58.0, -2.0)"
        cleaned = bbox_value.strip("() ")
        parts = [float(x.strip()) for x in cleaned.split(",")]
        return (parts[0], parts[1], parts[2], parts[3])
    # Already a sequence
    vals = [float(v) for v in bbox_value]  # type: ignore[union-attr]
    return (vals[0], vals[1], vals[2], vals[3])


def _find_satellite_image(
    results_root: Path,
    region_slug: str,
    aoi_id: str,
) -> Path | None:
    """Search for a satellite quicklook in results directories."""
    for pattern in [
        f"phase2/rough/{region_slug}/**/*rgb*.jpg",
        f"phase2/rough/{region_slug}/**/*rgb*.png",
        f"rough_truth/{region_slug}/**/*rgb*.jpg",
    ]:
        matches = sorted(results_root.glob(pattern))
        if matches:
            return matches[0]
    return None


if __name__ == "__main__":
    sys.exit(_run())
