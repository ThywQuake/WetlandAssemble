#!/usr/bin/env python3
"""Generate comparison panel figures for hotspots / focus areas.

Usage:
    uv run python scripts/plot_comparison_panels.py \\
        --manifest results/phase3/fine/probe/fine_grained_probe.json \\
        --output-dir results/figures \\
        --year 2016 \\
        --region "SE Asia"
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate comparison panel figures")
    p.add_argument(
        "--manifest", type=str, required=True,
        help="Path to fine_grained_probe.json or rough probe JSON",
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
    from WA.config import load_config
    from WA.loaders import get_loader
    from WA.visualization.comparison_panel import (
        make_dataset_labels,
        plot_comparison_panel,
    )

    config = load_config("config/datasets.yaml", "config/gee_config.yaml")
    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    results_root = Path(args.results_root)

    # --- Load manifest ---
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_hotspots = data.get("hotspots", [])
    if not raw_hotspots:
        print("[plot] no hotspots in manifest, nothing to plot", flush=True)
        return 0

    print(f"[plot] {len(raw_hotspots)} hotspot(s) from {manifest_path.name}", flush=True)

    # --- Determine participating datasets ---
    from WA.comparison.harmonize import EXCLUDED_BINARY_DATASET_IDS

    ds_ids = sorted(
        ds_id for ds_id in config.datasets
        if ds_id not in EXCLUDED_BINARY_DATASET_IDS
    )
    labels = make_dataset_labels(ds_ids)

    for i, raw in enumerate(raw_hotspots):
        hotspot_id = raw["hotspot_id"]
        bbox_raw = raw["bbox"]
        if isinstance(bbox_raw, dict):
            bbox = (bbox_raw["left"], bbox_raw["bottom"], bbox_raw["right"], bbox_raw["top"])
        else:
            bbox = tuple(float(v) for v in bbox_raw)

        region_slug = raw.get("region_slug", "unknown")

        print(
            f"\n[plot] ({i+1}/{len(raw_hotspots)}) {hotspot_id} — {region_slug}",
            flush=True,
        )
        t0 = time.time()

        # --- Load datasets at native resolution within bbox ---
        dataset_surfaces: dict[str, xr.DataArray] = {}
        for ds_id in ds_ids:
            ds_config = config.datasets.get(ds_id)
            if ds_config is None:
                continue
            try:
                loader = get_loader(ds_id, ds_config)
                ds = loader.load(bbox=bbox)

                # Extract binary wetland fraction at native resolution
                surface = _extract_native_wetland_surface(ds_id, ds)
                if surface is not None and int(surface.count().item()) > 0:
                    dataset_surfaces[ds_id] = surface
                    print(f"  {ds_id}: {surface.shape}", flush=True)
            except Exception as exc:
                print(f"  {ds_id}: SKIP ({exc})", flush=True)

        if not dataset_surfaces:
            print(f"  no datasets loaded, skipping {hotspot_id}", flush=True)
            continue

        # --- Compute entropy + mean wetland from loaded surfaces ---
        # Use simple disagreement: 1 - |2*mean - 1|
        binary_stack = []
        for _ds_id, surf in dataset_surfaces.items():
            # Resample to common grid for the summary panels
            common_res = 0.01  # ~1km for summary
            common_lats = np.arange(bbox[3], bbox[1], -common_res)
            common_lons = np.arange(bbox[0], bbox[2], common_res)
            interped = surf.interp(
                lat=common_lats, lon=common_lons, method="nearest",
            )
            binary_stack.append(interped)

        if binary_stack:
            stacked = xr.concat(binary_stack, dim="dataset")
            mean_wetland = stacked.mean(dim="dataset", skipna=True).astype(np.float32)
            # Simple disagreement as entropy proxy
            entropy = (1.0 - np.abs(2.0 * mean_wetland - 1.0)).astype(np.float32)
            entropy.name = "entropy"
            mean_wetland.name = "mean_wetland"
        else:
            print(f"  cannot compute summary, skipping {hotspot_id}", flush=True)
            continue

        # --- Find satellite quicklook ---
        sat_path = _find_satellite_image(results_root, region_slug, hotspot_id)

        # --- Plot ---
        out_file = output_dir / f"{hotspot_id}_panel.png"
        plot_comparison_panel(
            bbox,
            satellite_image_path=sat_path,
            entropy_surface=entropy,
            mean_wetland_surface=mean_wetland,
            dataset_surfaces=dataset_surfaces,
            dataset_labels=labels,
            year=args.year,
            region_label=args.region,
            hotspot_id=hotspot_id,
            output_path=out_file,
            dpi=args.dpi,
        )
        elapsed = time.time() - t0
        print(f"  saved: {out_file} ({elapsed:.1f}s)", flush=True)

    print("\n[plot] done", flush=True)
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_native_wetland_surface(
    dataset_id: str,
    dataset: xr.Dataset,
) -> xr.DataArray | None:
    """Extract binary wetland fraction from a loaded dataset at native res."""
    from WA.comparison.harmonize import (
        _CLASSIFICATION_BINARY_MAPS,
    )

    # Continuous fraction datasets
    if "wetland_fraction" in dataset:
        source = dataset["wetland_fraction"]
        # Collapse time if present: take mean
        if "time" in source.dims:
            source = source.mean(dim="time", skipna=True)
        # Collapse ensemble dims for topmodel
        for dim in ("config", "forcing"):
            if dim in source.dims:
                source = source.mean(dim=dim, skipna=True)
        return source.clip(0, 1).astype(np.float32)

    # Classification datasets → binary mapping
    if dataset_id == "g2017":
        if "wetland_nolake" in dataset:
            return dataset["wetland_nolake"].clip(0, 1).astype(np.float32)
        if "wetland" in dataset:
            return _map_to_binary(
                dataset["wetland"], _CLASSIFICATION_BINARY_MAPS["g2017"],
            )

    if dataset_id == "glwd_v2" and "combined_classes" in dataset:
        return _map_to_binary(
            dataset["combined_classes"], _CLASSIFICATION_BINARY_MAPS["glwd_v2"],
        )

    if dataset_id == "gwd30" and "wetland_class" in dataset:
        source = dataset["wetland_class"]
        if "time" in source.dims:
            source = source.isel(time=0)
        return _map_to_binary(source, _CLASSIFICATION_BINARY_MAPS["gwd30"])

    return None


def _map_to_binary(
    data: xr.DataArray,
    mapping: dict[int, float],
) -> xr.DataArray:
    """Map classification values to binary wetland fraction."""
    result = xr.full_like(data, np.nan, dtype=np.float32)
    for source_val, target_val in mapping.items():
        result = xr.where(data == source_val, np.float32(target_val), result)
    return result.where(data.notnull()).astype(np.float32)


def _find_satellite_image(
    results_root: Path,
    region_slug: str,
    hotspot_id: str,
) -> Path | None:
    """Search for a satellite quicklook in results directories."""
    # Try S2 fine_truth
    for pattern in [
        f"fine_truth/{region_slug}/**/*{hotspot_id}*rgb*.jpg",
        f"fine_truth/{region_slug}/**/*{hotspot_id}*rgb*.png",
        f"rough_truth/{region_slug}/**/*rgb*.jpg",
    ]:
        matches = sorted(results_root.glob(pattern))
        if matches:
            return matches[0]
    return None


if __name__ == "__main__":
    sys.exit(_run())
