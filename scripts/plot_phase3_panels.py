#!/usr/bin/env python3
"""Generate Phase 3.5 classification comparison panels for all hotspots.

Reads the fine-grained probe manifest, loads classification datasets for each
hotspot bbox, computes Shannon entropy + vote classification, and renders a
2×3 PNG panel per hotspot.

Usage (local):
    uv run python scripts/plot_phase3_panels.py \
        --phase3-root results/phase3/fine/probe

Usage (HPC):
    uv run python scripts/plot_phase3_panels.py \
        --phase3-root results/phase3/fine/probe \
        --output-dir results/figures/phase3
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 3.5 classification panel generator")
    p.add_argument(
        "--phase3-root",
        type=Path,
        default=Path("results/phase3/fine/probe"),
        help="directory containing fine_grained_probe.json",
    )
    p.add_argument(
        "--results-root",
        type=Path,
        default=Path("results"),
        help="root for S2 quicklook lookup (fine_truth/)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/figures/phase3"),
        help="directory for output PNGs",
    )
    p.add_argument(
        "--class-scheme",
        choices=["4class"],
        default="4class",
        help="classification scheme for visualization (currently only 4class supported)",
    )
    p.add_argument(
        "--vote-resolution",
        type=int,
        default=500,
        help="vote grid cell size in meters (default: 500)",
    )
    p.add_argument(
        "--gwd30-year",
        type=int,
        default=0,
        help="GWD30 reference year (0 = auto-select closest to G2017 reference year)",
    )
    p.add_argument(
        "--gwd30-workers",
        type=int,
        default=1,
        help="GWD30 worker count for low-memory tile reduction (default: 1)",
    )
    return p.parse_args()


def _resolve_gwd30_year(requested: int, config) -> int:
    """Select the GWD30 year closest to the classification reference year."""
    available_years = sorted(int(year) for year in config.datasets["gwd30"].get("years", []))
    if not available_years:
        raise FileNotFoundError("No GWD30 years configured")

    if requested > 0:
        return min(available_years, key=lambda year: abs(year - requested))

    reference_year = None
    g2017_cfg = config.datasets.get("g2017")
    if g2017_cfg is not None:
        import re

        files = g2017_cfg.get("files", {})
        for value in files.values() if isinstance(files, dict) else []:
            match = re.search(r"(\d{4})", str(value))
            if match:
                reference_year = int(match.group(1))
                break

    if reference_year is None:
        return available_years[-1]
    return min(available_years, key=lambda year: abs(year - reference_year))


def _close_loaded_datasets(datasets: dict[str, object]) -> None:
    """Close xarray-backed datasets opened during one hotspot loop."""
    for dataset in datasets.values():
        close = getattr(dataset, "close", None)
        if callable(close):
            close()


def _find_s2_quicklook(results_root: Path, hotspot_id: str, region_slug: str) -> Path | None:
    """Search for a S2 quicklook JPG under results/fine_truth/{region}/."""
    fine_truth = results_root / "fine_truth" / region_slug
    if not fine_truth.exists():
        return None
    for window_dir in sorted(fine_truth.iterdir()):
        if not window_dir.is_dir():
            continue
        candidate = window_dir / f"{hotspot_id}_s2_rgb.jpg"
        if candidate.exists():
            return candidate
    return None


def _run() -> int:
    args = _parse_args()

    manifest_path = args.phase3_root / "fine_grained_probe.json"
    if not manifest_path.exists():
        print(f"[error] manifest not found: {manifest_path}", flush=True)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    hotspots = manifest.get("hotspots", [])
    if not hotspots:
        print("[error] no hotspots in manifest", flush=True)
        return 1

    print(f"[panel] {len(hotspots)} hotspot(s) from {manifest_path}", flush=True)

    # Lazy imports (heavy)
    from WA._geo_env import configure_geospatial_runtime

    configure_geospatial_runtime()

    from WA.comparison.fine_grained import CLASSIFICATION_DATASET_IDS
    from WA.comparison.harmonize import create_comparison_grid
    from WA.comparison.hotspots import compute_shannon_entropy
    from WA.config import load_config
    from WA.loaders import get_loader
    from WA.visualization.panel import (
        compute_vote_classification,
        load_native_classification,
        plot_classification_panel,
    )

    config = load_config("config/datasets.yaml", "config/gee_config.yaml")
    vote_res_deg = args.vote_resolution / 111_000.0  # meters → approx degrees
    gwd30_year = _resolve_gwd30_year(args.gwd30_year, config)

    ok = 0
    fail = 0
    t_total = time.time()

    print(
        f"[panel] GWD30 year={gwd30_year}, workers={args.gwd30_workers}",
        flush=True,
    )

    for i, h in enumerate(hotspots, 1):
        hid = h["hotspot_id"]
        region = h["region_slug"]
        bbox = tuple(h["bbox"])
        print(f"\n[{i}/{len(hotspots)}] {hid} (region={region})", flush=True)
        entropy = None
        vote = None
        native: dict[str, object] = {}

        # Load classification datasets for this bbox
        datasets: dict[str, object] = {}
        try:
            grid = create_comparison_grid(bbox, resolution_deg=vote_res_deg)
            for ds_id in sorted(CLASSIFICATION_DATASET_IDS):
                ds_config = config.datasets.get(ds_id)
                if ds_config is None:
                    continue
                try:
                    loader = get_loader(ds_id, ds_config)
                    if ds_id == "gwd30" and hasattr(loader, "load_fine_classification_grid"):
                        datasets[ds_id] = loader.load_fine_classification_grid(
                            bbox=bbox,
                            reference_grid=grid,
                            year=gwd30_year,
                            worker_count=args.gwd30_workers if args.gwd30_workers > 0 else None,
                        )
                    else:
                        datasets[ds_id] = loader.load(bbox=bbox)
                    print(f"  loaded {ds_id}", flush=True)
                except Exception as exc:
                    print(f"  skip {ds_id}: {exc}", flush=True)

            if not datasets:
                print(f"  [skip] no datasets loaded for {hid}", flush=True)
                fail += 1
                continue

            # Shannon entropy
            from WA.comparison.fine_grained import harmonize_fine_collection

            harmonized = harmonize_fine_collection(datasets, grid, class_scheme=args.class_scheme)
            entropy = compute_shannon_entropy(harmonized, num_classes=4)

            # Vote classification
            vote = compute_vote_classification(
                datasets, bbox,
                class_scheme=args.class_scheme,
                vote_resolution_deg=vote_res_deg,
            )

            # Native classifications
            for ds_id, ds in datasets.items():
                try:
                    native[ds_id] = load_native_classification(
                        ds_id, ds, bbox,
                        class_scheme=args.class_scheme,
                    )
                except Exception as exc:
                    print(f"  native {ds_id} failed: {exc}", flush=True)

            # S2 quicklook
            s2_path = _find_s2_quicklook(args.results_root, hid, region)
            if s2_path:
                print(f"  S2 quicklook: {s2_path.name}", flush=True)

            # Plot
            out = args.output_dir / f"{hid}_panel.png"
            plot_classification_panel(
                hid, region, bbox,
                satellite_image_path=s2_path,
                entropy_surface=entropy,
                vote_classification=vote,
                native_classifications=native,
                output_path=out,
            )
            print(f"  saved: {out}", flush=True)
            ok += 1
        except Exception as exc:
            dims_info: list[str] = []
            if entropy is not None:
                dims_info.append(f"entropy={getattr(entropy, 'dims', None)}")
            if vote is not None:
                dims_info.append(f"vote={getattr(vote, 'dims', None)}")
            for ds_id, data in native.items():
                dims_info.append(f"{ds_id}={getattr(data, 'dims', None)}")
            suffix = f" ({', '.join(dims_info)})" if dims_info else ""
            print(f"  [error] hotspot failed: {exc}{suffix}", flush=True)
            fail += 1
        finally:
            _close_loaded_datasets(datasets)
            datasets.clear()
            gc.collect()

    elapsed = time.time() - t_total
    print(
        f"\n[panel] done — {ok} ok, {fail} failed, "
        f"{elapsed:.0f}s ({elapsed / 60:.1f}m)",
        flush=True,
    )
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(_run())
