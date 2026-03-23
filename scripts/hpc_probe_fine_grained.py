#!/usr/bin/env python3
"""Phase 3 fine-grained probe — parallel, memory-efficient, class-fraction preserving.

GWD30 processing strategy (class-fraction resampling):
  1. Band-by-band windowed read → accumulate per-class counts at native 30 m.
  2. Temporal mode at 30 m: argmax(counts) per pixel.
  3. For each class k: binary mask (mode == k) → Resampling.average → fraction
     of class k in each 0.25° cell.  This is equivalent to spatial mode but
     ~100× faster (GDAL average is hardware-accelerated; mode is not).
  4. argmax(fractions) → dominant class per coarse cell.
  5. Class fractions are saved as NetCDF for downstream analysis.

Memory budget per worker: ~430 MB peak (counts array at 30 m).
Two workers fit comfortably in 32 GB (16 GB/core).
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MAX_CLS = 15  # GWD30 classes 0-14


# ---------------------------------------------------------------------------
# Log-based progress (works in HPC log files, no tqdm dependency)
# ---------------------------------------------------------------------------

class LogProgress:
    """Line-based progress reporter that prints to stdout.

    Unlike tqdm (which uses \\r carriage returns), this prints a new line at
    each update interval.  Output is visible in:
      - SLURM .out files
      - ``tail -f`` monitoring
      - interactive terminals
    """

    def __init__(
        self,
        iterable=None,
        *,
        total: int | None = None,
        desc: str = "",
        interval: float = 15.0,
    ) -> None:
        self._iterable = iterable
        self.total = total if total is not None else (
            len(iterable) if iterable is not None and hasattr(iterable, "__len__") else 0
        )
        self.desc = desc
        self.interval = interval
        self.n = 0
        self.t0 = time.time()
        self._last_print = 0.0  # force first update to print

    def __iter__(self):
        if self._iterable is None:
            return
        for item in self._iterable:
            yield item
            self.update(1)
        self.close()

    def update(self, count: int = 1) -> None:
        self.n += count
        now = time.time()
        if now - self._last_print >= self.interval or self.n >= self.total:
            self._print_status(now)
            self._last_print = now

    def close(self) -> None:
        elapsed = time.time() - self.t0
        rate = self.n / elapsed if elapsed > 0 else 0
        print(
            f"  [{self.desc}] done {self.n}/{self.total} "
            f"in {_fmt_duration(elapsed)} ({rate:.1f}/s)",
            flush=True,
        )

    def _print_status(self, now: float) -> None:
        elapsed = now - self.t0
        pct = self.n / self.total * 100 if self.total else 0
        rate = self.n / elapsed if elapsed > 0 else 0
        if rate > 0 and self.n < self.total:
            eta = (self.total - self.n) / rate
            eta_str = f"ETA {_fmt_duration(eta)}"
        else:
            eta_str = ""
        print(
            f"  [{self.desc}] {self.n}/{self.total} ({pct:.0f}%) "
            f"— {rate:.1f}/s {eta_str}",
            flush=True,
        )


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m{seconds % 60:.0f}s"
    return f"{seconds / 3600:.1f}h"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase 3 fine-grained classification probe (parallelized)",
    )
    p.add_argument(
        "--workers", type=int, default=0,
        help="parallel worker count (0 = auto-detect from HPC env, default: 0)",
    )
    p.add_argument(
        "--year", type=int, default=0,
        help="GWD30 year (0 = auto-select closest to other datasets, default: 0)",
    )
    p.add_argument(
        "--bounds", type=float, nargs=4, default=[95.0, -11.0, 141.0, 6.0],
        metavar=("W", "S", "E", "N"),
        help="study area bounding box (default: SE Asia)",
    )
    p.add_argument(
        "--resolution", type=float, default=0,
        help="grid resolution in degrees (0 = auto from coarsest dataset, default: 0)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Auto-detection helpers
# ---------------------------------------------------------------------------

def _resolve_workers(requested: int) -> int:
    """Auto-detect worker count from HPC environment, or use explicit value."""
    if requested > 0:
        return requested

    # Reuse the detection logic from GWD30 loader
    for env_name in (
        "WA_GWD30_WORKERS",
        "SLURM_CPUS_PER_TASK",
        "SLURM_CPUS_ON_NODE",
        "OMP_NUM_THREADS",
        "PBS_NUM_PPN",
        "NSLOTS",
    ):
        raw = os.environ.get(env_name)
        if raw is None:
            continue
        try:
            val = int(raw.split("(")[0].split(",")[0])
        except ValueError:
            continue
        if val > 0:
            return val

    try:
        ga = getattr(os, "sched_getaffinity", None)
        if ga is not None:
            n = len(ga(0))
            if n > 0:
                return n
    except Exception:
        pass

    return max(1, os.cpu_count() or 1)


def _resolve_gwd30_year(requested: int, config) -> int:
    """Pick the GWD30 year closest to the other classification datasets.

    G2017 represents ~2016 (filename: WetlandV3b_2016_CIFOR.tif).
    GLWD v2 is undated; we ignore it for year selection.
    If no reference year can be inferred, fall back to the latest available.
    """
    available_years = sorted(int(y) for y in config.datasets["gwd30"].get("years", []))
    if not available_years:
        raise FileNotFoundError("No GWD30 years configured")

    if requested > 0:
        # Use the closest available year to the explicit request
        return min(available_years, key=lambda y: abs(y - requested))

    # Try to infer a reference year from G2017 config
    reference_year = None
    g2017_cfg = config.datasets.get("g2017")
    if g2017_cfg is not None:
        # Extract year from known filename pattern (*_YYYY_*)
        import re
        files = g2017_cfg.get("files", {})
        for v in files.values() if isinstance(files, dict) else []:
            m = re.search(r"(\d{4})", str(v))
            if m:
                reference_year = int(m.group(1))
                break

    if reference_year is None:
        # Default: latest available year
        chosen = available_years[-1]
        print(f"[auto-year] no reference year found, using latest: {chosen}", flush=True)
        return chosen

    chosen = min(available_years, key=lambda y: abs(y - reference_year))
    print(
        f"[auto-year] reference={reference_year} (G2017), "
        f"closest GWD30 year={chosen}",
        flush=True,
    )
    return chosen


def _resolve_resolution(requested: float, config) -> float:
    """Use the coarsest classification dataset's resolution as the comparison grid.

    Classification datasets and their configured resolutions:
      G2017:   0.05° (~5 km)
      GLWD v2: 30s (~1 km) = 0.00833°
      GWD30:   30 m ≈ 0.00028°

    The comparison grid should match the coarsest to avoid false precision.
    """
    if requested > 0:
        return requested


    classification_ids = ("g2017", "glwd_v2", "gwd30")
    coarsest_deg = 0.0

    for ds_id in classification_ids:
        ds_cfg = config.datasets.get(ds_id)
        if ds_cfg is None:
            continue
        raw = str(ds_cfg.get("resolution", ""))
        if not raw:
            continue

        deg = _parse_resolution_deg(raw)
        if deg is not None and deg > coarsest_deg:
            coarsest_deg = deg
            coarsest_id = ds_id

    if coarsest_deg > 0:
        print(
            f"[auto-res] coarsest classification dataset: "
            f"{coarsest_id} → {coarsest_deg}°",
            flush=True,
        )
        return coarsest_deg

    fallback = 0.05
    print(f"[auto-res] could not parse resolutions, fallback: {fallback}°", flush=True)
    return fallback


def _parse_resolution_deg(raw: str) -> float | None:
    """Parse a resolution string from config into degrees.

    Handles formats like:
      "0.05° (~5km)"  →  0.05
      "0.25° (~25km)" →  0.25
      "30s (~1km)"    →  0.00833  (30 arcseconds)
      "30m"           →  0.00028  (30 meters ≈ 30/111000)
    """
    import re

    # Try degrees: "0.05°" or "0.25°"
    m = re.search(r"([\d.]+)\s*°", raw)
    if m:
        return float(m.group(1))

    # Try arcseconds: "30s"
    m = re.search(r"(\d+)\s*s\b", raw)
    if m:
        return float(m.group(1)) / 3600.0

    # Try meters: "30m"
    m = re.search(r"(\d+)\s*m\b", raw)
    if m:
        return float(m.group(1)) / 111_000.0

    return None


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    for name in ("rasterio", "rioxarray", "pyproj"):
        logging.getLogger(name).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# GWD30 tile worker  (module-level for ProcessPoolExecutor pickling)
# ---------------------------------------------------------------------------

def _process_fine_tile(args: tuple) -> tuple[np.ndarray, np.ndarray] | None:
    """Process one GWD30 tile → coarse-grid class fractions.

    Returns (class_fractions, valid_mask) where:
      - class_fractions: (MAX_CLS, ref_h, ref_w) float32 — fraction [0,1]
        of each class in each coarse cell (via Resampling.average on binary masks)
      - valid_mask: (ref_h, ref_w) bool — cells with any data from this tile

    Peak memory: ~430 MB (counts at 30 m) + ~54 MB (one binary mask).
    """
    path_str, bbox, ref_crs, ref_tf_tuple, ref_w, ref_h = args

    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import Affine
    from rasterio.warp import reproject, transform_bounds
    from rasterio.windows import Window, from_bounds

    try:
        with rasterio.open(path_str) as src:
            if src.crs is None:
                return None

            # ── source window for bbox ──
            if str(src.crs) == "EPSG:4326":
                qb = bbox
            else:
                qb = transform_bounds(
                    "EPSG:4326", src.crs, *bbox, densify_pts=21,
                )

            left = max(src.bounds.left, qb[0])
            bottom = max(src.bounds.bottom, qb[1])
            right = min(src.bounds.right, qb[2])
            top = min(src.bounds.top, qb[3])
            if left >= right or bottom >= top:
                return None

            window = from_bounds(
                left, bottom, right, top, transform=src.transform,
            )
            window = window.round_offsets().round_lengths()
            try:
                window = window.intersection(
                    Window(0, 0, src.width, src.height),
                )
            except Exception:
                return None

            h, w = int(window.height), int(window.width)
            if h <= 0 or w <= 0:
                return None

            src_transform = src.window_transform(window)
            src_crs = src.crs          # save before exiting context
            nodata = src.nodata
            band_count = src.count

            # ── Step 1: band-by-band class counting at 30 m ──
            # Memory: MAX_CLS × h × w × 2 bytes ≈ 403 MB for full MGRS tile
            counts = np.zeros((MAX_CLS, h, w), dtype=np.int16)
            has_data = np.zeros((h, w), dtype=bool)

            for band_idx in range(1, band_count + 1):
                band = src.read(band_idx, window=window)
                if nodata is not None:
                    valid = band != nodata
                else:
                    valid = np.ones((h, w), dtype=bool)
                has_data |= valid
                safe = np.where(
                    valid, np.clip(band, 0, MAX_CLS - 1), -1,
                ).astype(np.int8)
                for cls in range(MAX_CLS):
                    counts[cls] += safe == cls   # bool → int16 broadcast
                del band, valid, safe

        # ── Step 2: temporal mode at 30 m ──
        if not has_data.any():
            return None

        mode_30m = counts.argmax(axis=0).astype(np.float32)
        mode_30m[~has_data] = np.nan
        del counts
        gc.collect()

        # ── Step 3: class-fraction resampling (average of binary masks) ──
        dst_transform = Affine(*ref_tf_tuple[:6])
        fractions = np.zeros((MAX_CLS, ref_h, ref_w), dtype=np.float32)

        for cls in range(MAX_CLS):
            binary = np.where(mode_30m == cls, 1.0, 0.0).astype(np.float32)
            binary[~has_data] = np.nan  # nodata → excluded from average

            coarse = np.full((ref_h, ref_w), np.nan, dtype=np.float32)
            reproject(
                source=binary,
                destination=coarse,
                src_transform=src_transform,
                src_crs=src_crs,
                dst_transform=dst_transform,
                dst_crs=ref_crs,
                src_nodata=np.nan,
                dst_nodata=np.nan,
                resampling=Resampling.average,
            )
            fractions[cls] = np.where(np.isfinite(coarse), coarse, 0.0)
            del binary, coarse

        del mode_30m, has_data
        gc.collect()

        valid_mask = fractions.sum(axis=0) > 0
        if not valid_mask.any():
            return None

        return fractions, valid_mask

    except Exception:
        return None


# ---------------------------------------------------------------------------
# GWD30 parallel loader
# ---------------------------------------------------------------------------

def _load_gwd30_parallel(config, bounds, grid, *, year: int, workers: int):
    """Load GWD30 via parallel tile processing with class-fraction resampling.

    Returns (xr.Dataset with dominant wetland_class, class_fractions DataArray).
    """
    import xarray as xr

    from WA.loaders import get_loader

    ds_config = config.datasets["gwd30"]
    loader = get_loader("gwd30", ds_config)

    time_range = (f"{year}-01-01", f"{year}-12-31")
    tiles_by_year = loader._discover_tiles(bbox=bounds, time_range=time_range)
    all_paths: list[Path] = []
    for _yr, paths in sorted(tiles_by_year.items()):
        all_paths.extend(paths)

    if not all_paths:
        raise FileNotFoundError(f"No GWD30 tiles for year {year} in bbox {bounds}")

    # Reference grid parameters
    ref_crs = str(grid.rio.crs)
    ref_transform = grid.rio.transform()
    ref_w = int(grid.sizes.get("lon", grid.sizes.get("x")))
    ref_h = int(grid.sizes.get("lat", grid.sizes.get("y")))
    tf_tuple = tuple(ref_transform)[:6]

    print(
        f"[gwd30] {len(all_paths)} tile(s), {workers} worker(s), "
        f"coarse grid {ref_h}×{ref_w}",
        flush=True,
    )

    task_args = [
        (str(p), bounds, ref_crs, tf_tuple, ref_w, ref_h)
        for p in all_paths
    ]

    # Accumulate class fractions across tiles
    all_fractions = np.zeros((MAX_CLS, ref_h, ref_w), dtype=np.float32)
    covered = np.zeros((ref_h, ref_w), dtype=bool)
    ok = 0
    fail = 0
    t0 = time.time()

    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_fine_tile, a): i
                for i, a in enumerate(task_args)
            }
            pbar = LogProgress(total=len(futures), desc="GWD30 tiles")
            for future in as_completed(futures):
                try:
                    out = future.result()
                except Exception:
                    fail += 1
                    pbar.update(1)
                    continue
                if out is None:
                    fail += 1
                    pbar.update(1)
                    continue
                tile_frac, tile_valid = out
                # MGRS tiles don't overlap — first-write fills each cell
                new = tile_valid & ~covered
                all_fractions[:, new] = tile_frac[:, new]
                covered |= tile_valid
                ok += 1
                pbar.update(1)
            pbar.close()
    else:
        pbar = LogProgress(total=len(task_args), desc="GWD30 tiles")
        for a in task_args:
            out = _process_fine_tile(a)
            if out is None:
                fail += 1
                pbar.update(1)
                continue
            tile_frac, tile_valid = out
            new = tile_valid & ~covered
            all_fractions[:, new] = tile_frac[:, new]
            covered |= tile_valid
            ok += 1
            pbar.update(1)
        pbar.close()

    elapsed = time.time() - t0
    filled = int(covered.sum())
    print(
        f"[gwd30] done: {ok} ok, {fail} skipped, "
        f"{filled} cells filled, {elapsed:.0f}s ({elapsed/60:.1f}m)",
        flush=True,
    )

    # Dominant class = argmax of class fractions
    dominant = all_fractions.argmax(axis=0).astype(np.float32)
    dominant[~covered] = np.nan

    lats = grid.coords["lat"].values
    lons = grid.coords["lon"].values

    # Dataset for the pipeline (dominant class)
    da = xr.DataArray(
        dominant,
        dims=("lat", "lon"),
        coords={"lat": lats, "lon": lons},
    )
    da = da.rio.write_crs("EPSG:4326")
    da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    ds = da.rename("wetland_class").to_dataset()
    ds["wetland_class"].attrs["source"] = "gwd30"

    # Class fractions DataArray for saving
    frac_da = xr.DataArray(
        all_fractions,
        dims=("class_id", "lat", "lon"),
        coords={
            "class_id": np.arange(MAX_CLS),
            "lat": lats,
            "lon": lons,
        },
        attrs={"description": "GWD30 class fractions via Resampling.average"},
    )

    return ds, frac_da


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def _run() -> int:
    args = _parse_args()
    _configure_logging()

    print("[bootstrap] configure WA geospatial runtime", flush=True)
    from WA._geo_env import configure_geospatial_runtime

    configure_geospatial_runtime()

    from WA.comparison.fine_grained import (
        CLASSIFICATION_DATASET_IDS,
        compute_class_agreement,
        harmonize_fine_collection,
    )
    from WA.comparison.harmonize import create_comparison_grid
    from WA.comparison.hotspots import (
        compute_shannon_entropy,
        extract_hotspots,
        get_representative_sites,
    )
    from WA.config import load_config
    from WA.loader_probe import make_json_safe
    bounds = tuple(args.bounds)

    t_total = time.time()

    config = load_config("config/datasets.yaml", "config/gee_config.yaml")

    workers = _resolve_workers(args.workers)
    year = _resolve_gwd30_year(args.year, config)
    resolution = _resolve_resolution(args.resolution, config)

    print(
        f"[probe] workers={workers}, year={year}, "
        f"resolution={resolution}\u00b0, bounds={bounds}",
        flush=True,
    )

    grid = create_comparison_grid(bounds, resolution_deg=resolution)
    print(f"[probe] grid shape: {grid.shape}", flush=True)

    # ── Load datasets ──
    print("[probe] loading datasets \u2026", flush=True)
    datasets = {}
    gwd30_fractions = None
    ds_ids = sorted(CLASSIFICATION_DATASET_IDS)

    for ds_id in ds_ids:
        t0 = time.time()
        ds_config = config.datasets.get(ds_id)
        if ds_config is None:
            print(f"  SKIP {ds_id}: not in config", flush=True)
            continue
        try:
            if ds_id == "gwd30":
                ds_result, gwd30_fractions = _load_gwd30_parallel(
                    config, bounds, grid, year=year, workers=workers,
                )
                datasets[ds_id] = ds_result
            else:
                from WA.loaders import get_loader

                loader = get_loader(ds_id, ds_config)
                datasets[ds_id] = loader.load(bbox=bounds)
            elapsed = time.time() - t0
            print(
                f"  {ds_id}: {list(datasets[ds_id].data_vars)} ({elapsed:.0f}s)",
                flush=True,
            )
        except Exception as exc:
            print(f"  FAIL {ds_id}: {exc}", flush=True)

    if not datasets:
        print("[probe] no datasets loaded, aborting", flush=True)
        return 1

    # ── Save class fractions ──
    output_dir = Path("results/phase3/fine/probe")
    output_dir.mkdir(parents=True, exist_ok=True)

    if gwd30_fractions is not None:
        frac_path = output_dir / "gwd30_class_fractions.nc"
        gwd30_fractions.to_netcdf(frac_path)
        print(f"[probe] saved class fractions: {frac_path}", flush=True)

    # ── Harmonize ──
    t0 = time.time()
    print("[probe] harmonizing to 4-class scheme \u2026", flush=True)
    harmonized_4 = harmonize_fine_collection(datasets, grid, class_scheme="4class")
    print(
        f"[probe] 4-class participants: {list(harmonized_4)} "
        f"({time.time()-t0:.0f}s)",
        flush=True,
    )

    # ── Class agreement ──
    t0 = time.time()
    print("[probe] computing class agreement \u2026", flush=True)
    agreement = compute_class_agreement(harmonized_4, num_classes=4)
    mc = agreement["majority_class"].values
    print(
        f"[probe] majority_class range: "
        f"{float(np.nanmin(mc)):.0f} - {float(np.nanmax(mc)):.0f} "
        f"({time.time()-t0:.0f}s)",
        flush=True,
    )

    # ── Shannon entropy ──
    t0 = time.time()
    print("[probe] computing Shannon entropy \u2026", flush=True)
    entropy = compute_shannon_entropy(harmonized_4, num_classes=4)
    e_vals = entropy.values[np.isfinite(entropy.values)]
    print(
        f"[probe] entropy: mean={float(np.mean(e_vals)):.4f}, "
        f"max={float(np.max(e_vals)):.4f}, "
        f"pct>0.5="
        f"{float((e_vals > 0.5).sum() / max(1, len(e_vals)) * 100):.1f}% "
        f"({time.time()-t0:.0f}s)",
        flush=True,
    )

    # ── Entropy hotspots ──
    t0 = time.time()
    print("[probe] extracting entropy hotspots \u2026", flush=True)
    entropy_hotspots = extract_hotspots(entropy, harmonized_4, top_n=5)
    print(
        f"[probe] found {len(entropy_hotspots)} entropy hotspot(s) ({time.time()-t0:.0f}s)",
        flush=True,
    )

    # ── Representative sites (curated, cross-basin coverage) ──
    rep_sites = get_representative_sites(existing_hotspots=entropy_hotspots)
    print(
        f"[probe] adding {len(rep_sites)} representative site(s) "
        f"(total: {len(entropy_hotspots) + len(rep_sites)})",
        flush=True,
    )
    hotspots = list(entropy_hotspots) + list(rep_sites)

    # ── Manifest ──
    if hotspots:
        from dataclasses import asdict

        manifest = {
            "bounds": bounds,
            "class_scheme": "4class",
            "num_datasets": len(harmonized_4),
            "hotspot_count": len(hotspots),
            "entropy_hotspot_count": len(entropy_hotspots),
            "representative_site_count": len(rep_sites),
            "hotspots": [asdict(h) for h in hotspots],
        }
        manifest_path = output_dir / "fine_grained_probe.json"
        manifest_path.write_text(
            json.dumps(
                make_json_safe(manifest),
                indent=2, sort_keys=True, allow_nan=False,
            ),
            encoding="utf-8",
        )
        print(f"[probe] wrote manifest: {manifest_path}", flush=True)

    total = time.time() - t_total
    print(
        f"[probe] done \u2014 total {total:.0f}s ({total/60:.1f}m)",
        flush=True,
    )
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _main() -> int:
    try:
        code = _run()
        return code if isinstance(code, int) else 0
    except SystemExit as exc:
        c = exc.code
        if c is None:
            return 0
        return int(c) if isinstance(c, int) else 1
    except BaseException as exc:
        traceback.print_exception(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = _main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
