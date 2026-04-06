#!/usr/bin/env python3
# ruff: noqa: E402
"""Plot regional wetland fraction maps on a 0.25 degree grid.

Rules:
- Target year defaults to 2016
- Static datasets are used directly
- Berkeley is forced to 2019
- GWD30 is excluded
- Fine-resolution fractions are aggregated with cosine-latitude area weighting
- Region bbox is resolved from the priority region catalog
- Staged NetCDF caches are written for debugging and reused when available
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
import yaml
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from WA._geo_env import configure_geospatial_runtime
from WA.config import load_config
from WA.loaders import get_loader
from WA.visualization.coarse_scale import (
    DATASET_DISPLAY_NAMES,
    _aggregate_non_spatial,
    _clip_to_bbox,
    _get_wetland_variable,
    area_weighted_mean_to_regular_grid,
)

configure_geospatial_runtime()

DEFAULT_TARGET_YEAR = 2016
BERKELEY_TARGET_YEAR = 2019
DEFAULT_RESOLUTION_DEG = 0.25
DEFAULT_CACHE_DIR = Path("results/cache/tropical_025deg")
DEFAULT_REGIONS_FILE = Path("config/priority_regions.yaml")
DEFAULT_REGION_ID = "global_tropical_subtropical_35"
DEFAULT_DATASETS = (
    "berkeley_rwawc",
    "g2017",
    "giems_mc",
    "glwd_v2",
    "swamps",
    "topmodel",
    "wad2m",
)

STAGE_LOADED = "01_loaded_dataset"
STAGE_WETLAND = "02_wetland_surface"
STAGE_AGGREGATED = "03_aggregated_surface"
STAGE_CLIPPED = "04_clipped_surface"
STAGE_COARSE = "05_coarse_surface"

STAGE_LABELS = {
    STAGE_LOADED: "loaded dataset",
    STAGE_WETLAND: "wetland surface",
    STAGE_AGGREGATED: "aggregated surface",
    STAGE_CLIPPED: "clipped surface",
    STAGE_COARSE: "coarse 0.25deg surface",
}
STAGE_CACHE_VERSIONS = {
    STAGE_COARSE: 2,
}
CACHE_VERSION_ATTR = "wa_stage_cache_version"

BBox = tuple[float, float, float, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot regional wetland fraction maps on a 0.25 degree grid",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/figures/tropical_025deg"),
        help="Directory for PNG and NetCDF outputs",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_TARGET_YEAR,
        help="Default target year for dynamic datasets (default: 2016)",
    )
    parser.add_argument(
        "--resolution-deg",
        type=float,
        default=DEFAULT_RESOLUTION_DEG,
        help="Target output resolution in degrees (default: 0.25)",
    )
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=list(DEFAULT_DATASETS),
        help="Dataset ids to process; GWD30 is intentionally excluded here",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Directory for staged processed caches (default: results/cache/tropical_025deg)",
    )
    parser.add_argument(
        "--regions-file",
        type=Path,
        default=DEFAULT_REGIONS_FILE,
        help="Region catalog YAML (default: config/priority_regions.yaml)",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION_ID,
        help="Region id from the region catalog (default: global_tropical_subtropical_35)",
    )
    parser.add_argument(
        "--no-prefer-cache",
        action="store_false",
        dest="prefer_cache",
        help="Recompute from source even if staged processed caches already exist",
    )
    parser.add_argument(
        "--no-write-cache",
        action="store_false",
        dest="write_cache",
        help="Do not write staged processed caches for this run",
    )
    return parser.parse_args()


def resolved_target_year(dataset_id: str, default_year: int) -> int | None:
    if dataset_id == "berkeley_rwawc":
        return BERKELEY_TARGET_YEAR
    if dataset_id in {"g2017", "glwd_v2"}:
        return None
    return default_year


def requested_time_range(dataset_id: str, target_year: int | None) -> tuple[str, str] | None:
    if target_year is None:
        return None
    return (f"{target_year}-01-01", f"{target_year}-12-31")


def _year_key(target_year: int | None) -> str:
    return f"year_{target_year}" if target_year is not None else "static"


def _resolution_key(resolution_deg: float) -> str:
    text = f"{resolution_deg:.6f}".rstrip("0").rstrip(".")
    return f"res_{text.replace('.', 'p')}"


def stage_cache_dir(
    cache_root: Path,
    dataset_id: str,
    region_id: str,
    *,
    target_year: int | None,
    resolution_deg: float,
) -> Path:
    return (
        cache_root
        / region_id
        / dataset_id
        / _year_key(target_year)
        / _resolution_key(resolution_deg)
    )


def stage_cache_path(
    cache_root: Path,
    dataset_id: str,
    region_id: str,
    *,
    target_year: int | None,
    resolution_deg: float,
    stage_name: str,
) -> Path:
    return stage_cache_dir(
        cache_root,
        dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
    ) / f"{stage_name}.nc"


def _log(dataset_id: str, message: str) -> None:
    print(f"[{dataset_id}] {message}", flush=True)


def _write_netcdf_atomically(path: Path, write_fn) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp-{os.getpid()}-{uuid4().hex}"
    try:
        write_fn(tmp_path)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _sanitize_attr_value(value: Any) -> Any:
    if isinstance(value, bool | np.bool_):
        return int(value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    if isinstance(value, list | tuple):
        if any(isinstance(item, dict | list | tuple) for item in value):
            return json.dumps(value)
        return list(value)
    return value


def _sanitize_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _sanitize_attr_value(value)
        for key, value in attrs.items()
        if value is not None
    }


def _sanitize_dataset_for_netcdf(dataset: xr.Dataset) -> xr.Dataset:
    clean = dataset.copy(deep=False)
    clean.attrs = _sanitize_attrs(dict(clean.attrs))
    for var_name in clean.data_vars:
        clean[var_name].attrs = _sanitize_attrs(dict(clean[var_name].attrs))
    for coord_name in clean.coords:
        clean[coord_name].attrs = _sanitize_attrs(dict(clean[coord_name].attrs))
        clean[coord_name].encoding = {}
    return clean


def _sanitize_dataarray_for_netcdf(data: xr.DataArray) -> xr.DataArray:
    clean = data.copy(deep=False)
    clean.attrs = _sanitize_attrs(dict(clean.attrs))
    for coord_name in clean.coords:
        clean[coord_name].attrs = _sanitize_attrs(dict(clean[coord_name].attrs))
        clean[coord_name].encoding = {}
    return clean


def _save_cached_dataset(
    path: Path,
    dataset: xr.Dataset,
    *,
    dataset_id: str,
    stage_name: str,
) -> None:
    clean = _sanitize_dataset_for_netcdf(dataset)
    _log(dataset_id, f"writing cache: {STAGE_LABELS[stage_name]} -> {path}")
    _write_netcdf_atomically(path, clean.to_netcdf)
    _log(dataset_id, f"cache ready: {STAGE_LABELS[stage_name]}")


def _save_cached_dataarray(
    path: Path,
    data: xr.DataArray,
    *,
    dataset_id: str,
    stage_name: str,
) -> None:
    clean = _sanitize_dataarray_for_netcdf(data)
    expected_version = STAGE_CACHE_VERSIONS.get(stage_name)
    if expected_version is not None:
        clean.attrs[CACHE_VERSION_ATTR] = expected_version
    _log(dataset_id, f"writing cache: {STAGE_LABELS[stage_name]} -> {path}")
    _write_netcdf_atomically(path, clean.to_netcdf)
    _log(dataset_id, f"cache ready: {STAGE_LABELS[stage_name]}")


def _load_cached_dataset(
    path: Path,
    *,
    dataset_id: str,
    stage_name: str,
) -> xr.Dataset | None:
    if not path.is_file():
        _log(dataset_id, f"cache miss: {STAGE_LABELS[stage_name]}")
        return None
    try:
        cached = xr.open_dataset(path)
        try:
            loaded = cached.load()
        finally:
            cached.close()
        _log(dataset_id, f"cache hit: {STAGE_LABELS[stage_name]} <- {path}")
        return loaded
    except Exception as exc:  # noqa: BLE001
        _log(
            dataset_id,
            f"ignoring unreadable cache for {STAGE_LABELS[stage_name]}: "
            f"{type(exc).__name__}: {exc}",
        )
        return None


def _load_cached_dataarray(
    path: Path,
    *,
    dataset_id: str,
    stage_name: str,
) -> xr.DataArray | None:
    if not path.is_file():
        _log(dataset_id, f"cache miss: {STAGE_LABELS[stage_name]}")
        return None
    try:
        cached = xr.open_dataarray(path)
        try:
            loaded = cached.load()
        finally:
            cached.close()
        expected_version = STAGE_CACHE_VERSIONS.get(stage_name)
        if expected_version is not None:
            actual_version = loaded.attrs.get(CACHE_VERSION_ATTR)
            if actual_version != expected_version:
                _log(
                    dataset_id,
                    f"ignoring stale cache for {STAGE_LABELS[stage_name]}: "
                    f"expected {CACHE_VERSION_ATTR}={expected_version}, got {actual_version!r}",
                )
                return None
        _log(dataset_id, f"cache hit: {STAGE_LABELS[stage_name]} <- {path}")
        return loaded
    except Exception as exc:  # noqa: BLE001
        _log(
            dataset_id,
            f"ignoring unreadable cache for {STAGE_LABELS[stage_name]}: "
            f"{type(exc).__name__}: {exc}",
        )
        return None


def _as_dataset(data: xr.Dataset | xr.DataArray) -> xr.Dataset:
    if isinstance(data, xr.Dataset):
        return data

    name = data.name or "wetland_fraction"
    return data.to_dataset(name=name)


def _bbox_to_cartopy_extent(
    bbox: BBox,
) -> BBox:
    west, south, east, north = bbox
    return (west, east, south, north)


def load_plot_regions(path: Path) -> dict[str, dict[str, object]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict) or not isinstance(document.get("regions"), dict):
        raise ValueError("Region document must contain a top-level 'regions' mapping")

    loaded: dict[str, dict[str, object]] = {}
    for region_id, payload in document["regions"].items():
        if not isinstance(payload, dict):
            raise ValueError(f"Region {region_id!r} must be a mapping")
        bbox = payload.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"Region {region_id!r} must define bbox as 4-item list")
        loaded[str(region_id)] = {
            "label": str(payload.get("label", region_id)),
            "bbox": (
                float(bbox[0]),
                float(bbox[1]),
                float(bbox[2]),
                float(bbox[3]),
            ),
        }
    return loaded


def resolve_plot_region(
    region_id: str,
    *,
    regions_file: Path,
) -> tuple[str, BBox]:
    regions = load_plot_regions(regions_file)
    if region_id not in regions:
        available = ", ".join(sorted(regions))
        raise KeyError(f"Unknown region {region_id!r}; available regions: {available}")
    region = regions[region_id]
    label = str(region["label"])
    bbox_values = region["bbox"]
    bbox: BBox = (
        float(bbox_values[0]),
        float(bbox_values[1]),
        float(bbox_values[2]),
        float(bbox_values[3]),
    )
    return label, bbox


def load_tropical_surface(
    dataset_id: str,
    *,
    region_id: str,
    bbox: BBox,
    target_year: int | None,
    resolution_deg: float,
    cache_dir: Path,
    prefer_cache: bool = True,
    write_cache: bool = True,
) -> tuple[int | None, xr.DataArray]:
    cache_stage_dir = stage_cache_dir(
        cache_dir,
        dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
    )
    loaded_cache_path = stage_cache_path(
        cache_dir,
        dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
        stage_name=STAGE_LOADED,
    )
    wetland_cache_path = stage_cache_path(
        cache_dir,
        dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
        stage_name=STAGE_WETLAND,
    )
    aggregated_cache_path = stage_cache_path(
        cache_dir,
        dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
        stage_name=STAGE_AGGREGATED,
    )
    clipped_cache_path = stage_cache_path(
        cache_dir,
        dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
        stage_name=STAGE_CLIPPED,
    )
    coarse_cache_path = stage_cache_path(
        cache_dir,
        dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
        stage_name=STAGE_COARSE,
    )
    time_range = requested_time_range(dataset_id, target_year)

    dataset: xr.Dataset | None = None
    try:
        _log(dataset_id, f"pipeline start: cache root = {cache_stage_dir}")
        if prefer_cache:
            _log(dataset_id, "stage 5/5: checking coarse surface cache")
            coarse = _load_cached_dataarray(
                coarse_cache_path,
                dataset_id=dataset_id,
                stage_name=STAGE_COARSE,
            )
        else:
            _log(dataset_id, "stage cache reads disabled, recomputing from source")
            coarse = None
        if coarse is None:
            if prefer_cache:
                _log(dataset_id, "stage 4/5: checking clipped surface cache")
                clipped = _load_cached_dataarray(
                    clipped_cache_path,
                    dataset_id=dataset_id,
                    stage_name=STAGE_CLIPPED,
                )
            else:
                clipped = None
            if clipped is None:
                if prefer_cache:
                    _log(dataset_id, "stage 3/5: checking aggregated surface cache")
                    aggregated = _load_cached_dataarray(
                        aggregated_cache_path,
                        dataset_id=dataset_id,
                        stage_name=STAGE_AGGREGATED,
                    )
                else:
                    aggregated = None
                if aggregated is None:
                    if prefer_cache:
                        _log(dataset_id, "stage 2/5: checking wetland surface cache")
                        wetland = _load_cached_dataarray(
                            wetland_cache_path,
                            dataset_id=dataset_id,
                            stage_name=STAGE_WETLAND,
                        )
                    else:
                        wetland = None
                    if wetland is None:
                        if prefer_cache:
                            _log(dataset_id, "stage 1/5: checking loaded dataset cache")
                            dataset = _load_cached_dataset(
                                loaded_cache_path,
                                dataset_id=dataset_id,
                                stage_name=STAGE_LOADED,
                            )
                        else:
                            dataset = None
                        if dataset is None:
                            _log(dataset_id, "loading source dataset from configured loader")
                            config = load_config("config/datasets.yaml", "config/gee_config.yaml")
                            dataset_config = config.datasets[dataset_id]
                            loader = get_loader(dataset_id, dataset_config)
                            dataset = _as_dataset(loader.load(bbox=bbox, time_range=time_range))
                            if write_cache:
                                _save_cached_dataset(
                                    loaded_cache_path,
                                    dataset,
                                    dataset_id=dataset_id,
                                    stage_name=STAGE_LOADED,
                                )

                        _log(dataset_id, "extracting wetland variable")
                        wetland = _get_wetland_variable(dataset, dataset_id)
                        if wetland is None:
                            raise ValueError(f"{dataset_id} has no wetland variable")

                        if target_year is not None and "time" in wetland.dims:
                            _log(dataset_id, f"filtering time axis to target year {target_year}")
                            time_coord = wetland.coords["time"]
                            if hasattr(time_coord.dt, "year"):
                                wetland = wetland.sel(time=time_coord.dt.year == target_year)

                        if write_cache:
                            _save_cached_dataarray(
                                wetland_cache_path,
                                wetland,
                                dataset_id=dataset_id,
                                stage_name=STAGE_WETLAND,
                            )

                    _log(dataset_id, "aggregating non-spatial dimensions")
                    aggregated = _aggregate_non_spatial(wetland, aggregation="mean")
                    if write_cache:
                        _save_cached_dataarray(
                            aggregated_cache_path,
                            aggregated,
                            dataset_id=dataset_id,
                            stage_name=STAGE_AGGREGATED,
                        )

                _log(dataset_id, "clipping surface to tropical bbox")
                clipped = _clip_to_bbox(aggregated, bbox)
                if int(clipped.count().item()) == 0:
                    raise ValueError(f"{dataset_id} produced no valid cells for target year")
                if write_cache:
                    _save_cached_dataarray(
                        clipped_cache_path,
                        clipped,
                        dataset_id=dataset_id,
                        stage_name=STAGE_CLIPPED,
                    )

            _log(dataset_id, f"aggregating to regular {resolution_deg}deg grid")
            coarse = area_weighted_mean_to_regular_grid(
                clipped,
                bbox,
                resolution_deg=resolution_deg,
            )
            if int(coarse.count().item()) == 0:
                raise ValueError(f"{dataset_id} produced an empty 0.25 degree tropical surface")
            if write_cache:
                _save_cached_dataarray(
                    coarse_cache_path,
                    coarse,
                    dataset_id=dataset_id,
                    stage_name=STAGE_COARSE,
                )

        actual_year = target_year
        if dataset is not None and target_year is None and "time" in dataset.coords:
            actual_year = int(dataset["time"].dt.year.values[0])
        _log(
            dataset_id,
            f"pipeline complete: resolved output year = "
            f"{actual_year if actual_year is not None else 'static'}",
        )
        return actual_year, coarse
    finally:
        close = getattr(dataset, "close", None)
        if callable(close):
            close()


def save_surface_plot(
    surface: xr.DataArray,
    dataset_id: str,
    *,
    region_id: str,
    region_label: str,
    bbox: BBox,
    output_dir: Path,
    actual_year: int | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"{dataset_id}_{region_id}_025deg.png"
    nc_path = output_dir / f"{dataset_id}_{region_id}_025deg.nc"

    display_name = DATASET_DISPLAY_NAMES.get(dataset_id, dataset_id)
    cmap = LinearSegmentedColormap.from_list("wetland_wb", ["#ffffff", "#1f77b4"])
    output_dataset = _sanitize_dataset_for_netcdf(surface.to_dataset(name="wetland_fraction"))

    _log(dataset_id, f"writing final NetCDF output -> {nc_path}")
    _write_netcdf_atomically(nc_path, output_dataset.to_netcdf)
    _log(dataset_id, "final NetCDF saved")

    use_cartopy = False
    transform = None
    try:
        import cartopy.crs as ccrs

        use_cartopy = True
        transform = ccrs.PlateCarree()
        _log(dataset_id, "cartopy detected, coastlines enabled")
    except ImportError:
        _log(dataset_id, "cartopy unavailable, falling back to plain matplotlib")

    if use_cartopy:
        fig = plt.figure(figsize=(12, 4.8))
        ax = fig.add_subplot(1, 1, 1, projection=transform)
    else:
        fig, ax = plt.subplots(figsize=(12, 4.8))

    plot_kwargs = {
        "ax": ax,
        "x": "lon",
        "y": "lat",
        "cmap": cmap,
        "vmin": 0.0,
        "vmax": 1.0,
        "add_colorbar": False,
        "rasterized": True,
    }
    if transform is not None:
        plot_kwargs["transform"] = transform

    try:
        _log(dataset_id, f"rendering PNG figure -> {png_path}")
        mesh = surface.plot.pcolormesh(**plot_kwargs)
        ax.set_title(display_name, fontsize=13, fontweight="bold")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect("equal")
        if use_cartopy:
            ax.set_extent(_bbox_to_cartopy_extent(bbox), crs=transform)
            ax.coastlines(linewidth=0.5, color="black")
        else:
            ax.set_xlim(bbox[0], bbox[2])
            ax.set_ylim(bbox[1], bbox[3])

        colorbar = fig.colorbar(mesh, ax=ax, pad=0.02)
        colorbar.set_label("Wetland Fraction")
        fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)

    _log(dataset_id, "PNG figure saved")


def save_overview_plot(
    surfaces: list[tuple[str, xr.DataArray]],
    *,
    region_id: str,
    region_label: str,
    bbox: BBox,
    output_dir: Path,
) -> Path | None:
    if not surfaces:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"overview_{region_id}_025deg.png"
    cmap = LinearSegmentedColormap.from_list("wetland_wb", ["#ffffff", "#1f77b4"])

    use_cartopy = False
    transform = None
    try:
        import cartopy.crs as ccrs

        use_cartopy = True
        transform = ccrs.PlateCarree()
        print("[overview] cartopy detected, coastlines enabled", flush=True)
    except ImportError:
        print("[overview] cartopy unavailable, falling back to plain matplotlib", flush=True)

    nrows = len(surfaces)
    figsize = (12, max(3.2 * nrows, 4.8))
    subplot_kwargs = {"projection": transform} if use_cartopy else {}
    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=1,
        figsize=figsize,
        squeeze=False,
        subplot_kw=subplot_kwargs,
    )
    axes_list = list(axes[:, 0])

    mesh = None
    try:
        print(f"[overview] rendering overview PNG -> {png_path}", flush=True)
        for index, ((dataset_id, surface), ax) in enumerate(zip(surfaces, axes_list, strict=False)):
            plot_kwargs = {
                "ax": ax,
                "x": "lon",
                "y": "lat",
                "cmap": cmap,
                "vmin": 0.0,
                "vmax": 1.0,
                "add_colorbar": False,
                "rasterized": True,
            }
            if transform is not None:
                plot_kwargs["transform"] = transform

            mesh = surface.plot.pcolormesh(**plot_kwargs)
            ax.set_title(
                DATASET_DISPLAY_NAMES.get(dataset_id, dataset_id),
                fontsize=12,
                fontweight="bold",
            )
            ax.set_ylabel("Latitude")
            ax.set_aspect("equal")
            if index == nrows - 1:
                ax.set_xlabel("Longitude")
            else:
                ax.set_xlabel("")

            if use_cartopy:
                ax.set_extent(_bbox_to_cartopy_extent(bbox), crs=transform)
                ax.coastlines(linewidth=0.5, color="black")
            else:
                ax.set_xlim(bbox[0], bbox[2])
                ax.set_ylim(bbox[1], bbox[3])

        if mesh is None:
            return None

        fig.suptitle(region_label, fontsize=14, fontweight="bold")
        colorbar = fig.colorbar(mesh, ax=axes_list, pad=0.02, fraction=0.025)
        colorbar.set_label("Wetland Fraction")
        fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)

    print("[overview] overview PNG saved", flush=True)
    return png_path


def main() -> None:
    args = parse_args()
    region_label, region_bbox = resolve_plot_region(
        args.region,
        regions_file=args.regions_file,
    )
    print(
        f"[run] output_dir={args.output_dir} cache_dir={args.cache_dir} "
        f"region={args.region} region_label={region_label} region_bbox={region_bbox} "
        f"resolution_deg={args.resolution_deg} prefer_cache={args.prefer_cache} "
        f"write_cache={args.write_cache}",
        flush=True,
    )

    successful_surfaces: list[tuple[str, xr.DataArray]] = []
    for dataset_id in args.datasets:
        if dataset_id == "gwd30":
            print("[gwd30] skipped by design in this script")
            continue

        target_year = resolved_target_year(dataset_id, args.year)
        target_label = target_year if target_year is not None else "static"
        _log(dataset_id, f"target year = {target_label}")
        _log(dataset_id, f"selected region = {args.region} ({region_label}) bbox={region_bbox}")
        try:
            actual_year, surface = load_tropical_surface(
                dataset_id,
                region_id=args.region,
                bbox=region_bbox,
                target_year=target_year,
                resolution_deg=args.resolution_deg,
                cache_dir=args.cache_dir,
                prefer_cache=args.prefer_cache,
                write_cache=args.write_cache,
            )
            save_surface_plot(
                surface,
                dataset_id,
                region_id=args.region,
                region_label=region_label,
                bbox=region_bbox,
                output_dir=args.output_dir,
                actual_year=actual_year,
            )
            successful_surfaces.append((dataset_id, surface))
        except Exception as exc:  # noqa: BLE001
            print(f"[{dataset_id}] skipped: {type(exc).__name__}: {exc}")

    save_overview_plot(
        successful_surfaces,
        region_id=args.region,
        region_label=region_label,
        bbox=region_bbox,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
