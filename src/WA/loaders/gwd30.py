"""Loader for GWD30 tiled multi-band GeoTIFF mosaics."""

from __future__ import annotations

import gc
import logging
import os
import re
import tempfile
from collections import defaultdict
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from rasterio.enums import Resampling
from rasterio.errors import WindowError
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds

from WA.comparison.harmonize import _CLASSIFICATION_BINARY_MAPS, BINARY_WETLAND_THRESHOLD
from WA.loaders._shared import (
    four_day_index_for_year,
    merge_rasters,
    open_multiband_raster,
)
from WA.loaders.base import (
    BBox,
    DatasetLoader,
    DatasetMetadata,
    TimeRange,
    ensure_datetime_index,
)
from WA.loaders.registry import register_loader
from WA.utils.mgrs_tiling import GWD30TilingSystem
from WA.utils.progress import tqdm

logger = logging.getLogger(__name__)
_TILE_CODE_PATTERN = re.compile(r"(?<![A-Z0-9])T?(\d{1,2}[C-HJ-NP-X][A-HJ-NP-Z]{2})(?![A-Z0-9])")
_TEMP_TILE_NODATA = np.float32(-9999.0)
_GWD30_CLASS_COUNT = 15


def _build_binary_lookup(mapping: Mapping[int, float]) -> np.ndarray:
    """Build a fixed-size lookup table for fast class-to-binary conversion."""

    lookup = np.full(256, np.nan, dtype=np.float32)
    for source_value, binary_value in mapping.items():
        if 0 <= int(source_value) < len(lookup):
            lookup[int(source_value)] = np.float32(binary_value)
    return lookup


_GWD30_BINARY_LOOKUP = _build_binary_lookup(_CLASSIFICATION_BINARY_MAPS["gwd30"])


def _bbox_intersects(a: BBox, b: BBox) -> bool:
    """Return whether two lon/lat bounding boxes intersect."""

    a_min_lon, a_min_lat, a_max_lon, a_max_lat = a
    b_min_lon, b_min_lat, b_max_lon, b_max_lat = b
    return not (
        a_max_lon < b_min_lon
        or b_max_lon < a_min_lon
        or a_max_lat < b_min_lat
        or b_max_lat < a_min_lat
    )


def _extract_tile_code(path: Path) -> str | None:
    """Extract a GWD30/MGRS-like tile code from a filename."""

    match = _TILE_CODE_PATTERN.search(path.stem.upper())
    if match is None:
        return None
    zone_text, suffix = match.group(1)[:-3], match.group(1)[-3:]
    return f"{int(zone_text):02d}{suffix}"


def _filter_files_by_bounds(files: list[Path], bbox: BBox) -> list[Path]:
    """Slow-path bbox filter using raster bounds converted to WGS84."""

    matched: list[Path] = []
    for file_path in files:
        try:
            with rasterio.open(file_path) as src:
                if src.crs is None:
                    candidate_bounds = cast(BBox, src.bounds)
                elif str(src.crs) == "EPSG:4326":
                    candidate_bounds = cast(BBox, src.bounds)
                else:
                    candidate_bounds = cast(
                        BBox,
                        transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21),
                    )
        except Exception:
            continue

        if _bbox_intersects(candidate_bounds, bbox):
            matched.append(file_path)
    return matched


def _reference_grid_spec(reference_grid: xr.DataArray) -> tuple[str, Any, int, int]:
    """Extract raster-space metadata from the coarse comparison grid."""

    reference_crs = reference_grid.rio.crs
    if reference_crs is None:
        raise ValueError("reference_grid must define a CRS")
    return (
        str(reference_crs),
        reference_grid.rio.transform(),
        int(reference_grid.sizes["lon"]),
        int(reference_grid.sizes["lat"]),
    )


def _source_window_for_bbox(src: rasterio.io.DatasetReader, bbox: BBox) -> Window | None:
    """Build the smallest source window intersecting the requested lon/lat bbox."""

    if src.crs is None:
        return Window(0, 0, src.width, src.height)

    if str(src.crs) == "EPSG:4326":
        query_bounds = bbox
    else:
        query_bounds = cast(
            BBox,
            transform_bounds("EPSG:4326", src.crs, *bbox, densify_pts=21),
        )

    left = max(float(src.bounds.left), float(query_bounds[0]))
    bottom = max(float(src.bounds.bottom), float(query_bounds[1]))
    right = min(float(src.bounds.right), float(query_bounds[2]))
    top = min(float(src.bounds.top), float(query_bounds[3]))
    if left >= right or bottom >= top:
        return None

    requested = from_bounds(left, bottom, right, top, transform=src.transform)
    requested = requested.round_offsets().round_lengths()
    full_window = Window(0, 0, src.width, src.height)
    try:
        return requested.intersection(full_window)
    except WindowError:
        return None


def _masked_classes_to_binary_fraction(
    data: np.ma.MaskedArray[Any],
    *,
    lookup: np.ndarray,
) -> np.ndarray:
    """Convert masked GWD30 class codes into a float binary-fraction array."""

    mask = np.ma.getmaskarray(data)
    filled = np.asarray(np.ma.filled(data, 0), dtype=np.int16)
    clipped = np.clip(filled, 0, len(lookup) - 1)
    mapped = lookup[clipped].astype(np.float32, copy=True)
    mapped[mask] = np.nan
    return mapped


def _iter_tiles_with_progress(paths: list[Path], *, desc: str) -> Any:
    """Wrap tile iteration with tqdm for long-running HPC loads."""

    return tqdm(
        paths,
        desc=desc,
        unit="tile",
        dynamic_ncols=True,
        mininterval=5.0,
    )


def _resolve_parallel_worker_count(worker_count: int | None) -> int:
    """Resolve the desired GWD30 parallel worker count from args or HPC env."""

    if worker_count is not None and worker_count > 0:
        return worker_count

    for env_name in (
        "WA_GWD30_WORKERS",
        "SLURM_CPUS_PER_TASK",
        "SLURM_CPUS_ON_NODE",
        "OMP_NUM_THREADS",
        "PBS_NUM_PPN",
        "NSLOTS",
    ):
        raw_value = os.environ.get(env_name)
        if raw_value is None:
            continue
        try:
            resolved = int(raw_value.split("(")[0].split(",")[0])
        except ValueError:
            continue
        if resolved > 0:
            return resolved
    try:
        sched_getaffinity = getattr(os, "sched_getaffinity", None)
        affinity_count = len(sched_getaffinity(0)) if sched_getaffinity is not None else 0
    except Exception:
        affinity_count = 0
    if affinity_count > 0:
        return affinity_count
    return max(1, os.cpu_count() or 1)


def _normalize_shard_spec(shard_index: int, shard_count: int) -> tuple[int, int]:
    """Validate and normalize a shard spec."""

    if shard_count < 1:
        raise ValueError("shard_count must be >= 1")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard_index must satisfy 0 <= shard_index < shard_count")
    return shard_index, shard_count


def _select_paths_for_shard(
    paths: list[Path],
    *,
    shard_index: int,
    shard_count: int,
) -> list[Path]:
    """Select the deterministic subset of tile paths assigned to one shard."""

    _normalize_shard_spec(shard_index, shard_count)
    if shard_count == 1:
        return paths
    return [path for index, path in enumerate(paths) if index % shard_count == shard_index]


def _project_rough_tile_to_coarse_array(
    *,
    path: str,
    bbox: BBox,
    band_indexes: list[int],
    aggregation: str,
    reference_crs: str,
    reference_transform: Any,
    width: int,
    height: int,
) -> tuple[np.ndarray | None, int]:
    """Read one GWD30 tile, aggregate it, and project it into the coarse grid."""

    with rasterio.open(path) as src:
        window = _source_window_for_bbox(src, bbox)
        if window is None:
            return None, 0
        source_height = int(window.height)
        source_width = int(window.width)
        if source_height <= 0 or source_width <= 0:
            return None, 0
        source_transform = src.window_transform(window)

        if aggregation == "max":
            source_monthly = np.full((source_height, source_width), np.nan, dtype=np.float32)
        else:
            source_sum = np.zeros((source_height, source_width), dtype=np.float32)
            source_count = np.zeros((source_height, source_width), dtype=np.uint8)

        for band_index in band_indexes:
            band = src.read(band_index + 1, window=window, masked=True)
            if band.size == 0:
                continue
            mapped = _masked_classes_to_binary_fraction(
                band,
                lookup=_GWD30_BINARY_LOOKUP,
            )
            valid = np.isfinite(mapped)
            if aggregation == "max":
                source_monthly = np.where(
                    valid,
                    np.where(
                        np.isnan(source_monthly),
                        mapped,
                        np.maximum(source_monthly, mapped),
                    ),
                    source_monthly,
                )
            else:
                source_sum[valid] = source_sum[valid] + mapped[valid]
                source_count[valid] = source_count[valid] + 1

        if aggregation != "max":
            source_monthly = np.full((source_height, source_width), np.nan, dtype=np.float32)
            valid_counts = source_count > 0
            source_monthly[valid_counts] = source_sum[valid_counts] / source_count[valid_counts]

        if not np.isfinite(source_monthly).any():
            return None, 0

        coarse = np.full((height, width), np.nan, dtype=np.float32)
        reproject(
            source=source_monthly,
            destination=coarse,
            src_transform=source_transform,
            src_crs=src.crs,
            dst_transform=reference_transform,
            dst_crs=reference_crs,
            src_nodata=np.nan,
            dst_nodata=np.nan,
            resampling=Resampling.average,
        )

    coarse_non_null_count = int(np.count_nonzero(np.isfinite(coarse)))
    if coarse_non_null_count == 0:
        return None, 0
    return coarse, coarse_non_null_count


def _process_rough_tile_to_partial(
    *,
    path: str,
    bbox: BBox,
    band_indexes: list[int],
    aggregation: str,
    reference_crs: str,
    reference_transform: Any,
    width: int,
    height: int,
) -> tuple[np.ndarray | None, np.ndarray | None, int]:
    """Project one GWD30 tile and return partial sum/count coarse arrays."""

    coarse, coarse_non_null_count = _project_rough_tile_to_coarse_array(
        path=path,
        bbox=bbox,
        band_indexes=band_indexes,
        aggregation=aggregation,
        reference_crs=reference_crs,
        reference_transform=reference_transform,
        width=width,
        height=height,
    )
    if coarse is None:
        return None, None, 0

    valid = np.isfinite(coarse)
    tile_sum = np.where(valid, coarse, 0.0).astype(np.float32)
    tile_count = valid.astype(np.uint8)
    return tile_sum, tile_count, coarse_non_null_count


def _process_fine_tile_to_fractions(
    *,
    path: str,
    bbox: BBox,
    reference_crs: str,
    reference_transform: Any,
    width: int,
    height: int,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Project one GWD30 tile into coarse-grid class fractions.

    The workflow mirrors the Phase 3 HPC probe:
      1. windowed band-by-band read inside ``bbox``
      2. per-pixel temporal mode at native 30m resolution
      3. per-class binary-mask averaging into ``reference_grid``

    Returns
    -------
    tuple[np.ndarray | None, np.ndarray | None]
        ``(fractions, valid_mask)`` where fractions has shape
        ``(class_id, lat, lon)`` and valid_mask marks coarse cells touched by
        this tile. ``None`` is returned when the tile contributes no data.
    """

    with rasterio.open(path) as src:
        window = _source_window_for_bbox(src, bbox)
        if window is None:
            return None, None

        source_height = int(window.height)
        source_width = int(window.width)
        if source_height <= 0 or source_width <= 0:
            return None, None

        source_transform = src.window_transform(window)
        source_crs = src.crs
        if source_crs is None:
            return None, None

        counts = np.zeros(
            (_GWD30_CLASS_COUNT, source_height, source_width),
            dtype=np.int16,
        )
        has_data = np.zeros((source_height, source_width), dtype=bool)

        for band_index in range(1, src.count + 1):
            band = src.read(band_index, window=window, masked=True)
            if band.size == 0:
                continue

            band_mask = np.ma.getmaskarray(band)
            valid = ~band_mask
            if not np.any(valid):
                continue

            has_data |= valid
            safe = np.clip(
                np.asarray(np.ma.filled(band, 0), dtype=np.int16),
                0,
                _GWD30_CLASS_COUNT - 1,
            )
            for class_id in range(_GWD30_CLASS_COUNT):
                counts[class_id] += safe == class_id

        if not np.any(has_data):
            return None, None

        mode_30m = counts.argmax(axis=0).astype(np.float32)
        mode_30m[~has_data] = np.nan
        del counts

        fractions = np.zeros((_GWD30_CLASS_COUNT, height, width), dtype=np.float32)
        for class_id in range(_GWD30_CLASS_COUNT):
            binary = np.where(mode_30m == class_id, 1.0, 0.0).astype(np.float32)
            binary[~has_data] = np.nan
            coarse = np.full((height, width), np.nan, dtype=np.float32)
            reproject(
                source=binary,
                destination=coarse,
                src_transform=source_transform,
                src_crs=source_crs,
                dst_transform=reference_transform,
                dst_crs=reference_crs,
                src_nodata=np.nan,
                dst_nodata=np.nan,
                resampling=Resampling.average,
            )
            fractions[class_id] = np.where(np.isfinite(coarse), coarse, 0.0)

        valid_mask = fractions.sum(axis=0) > 0
        if not np.any(valid_mask):
            return None, None

        return fractions, valid_mask


@register_loader("gwd30")
class GWD30Loader(DatasetLoader):
    """Load annual GWD30 tiles and merge them into year-wise mosaics."""

    def __init__(self, dataset_id: str, config: dict[str, object]) -> None:
        super().__init__(dataset_id, config)
        self._tiling = GWD30TilingSystem()
        self._discover_tiles_cache: dict[
            tuple[BBox | None, TimeRange | None],
            dict[int, list[Path]],
        ] = {}

    def metadata(self) -> DatasetMetadata:
        return DatasetMetadata(
            dataset_id=self.dataset_id,
            name=self.name,
            source_path=str(self.base_path),
            crs="EPSG:4326",
            spatial_resolution=self.config.get("resolution"),
            temporal_coverage=self.temporal_coverage(),
            time_resolution=self.config.get("time_resolution", "4-day"),
            is_static=False,
            is_classification=True,
            native_variables=("wetland_class",),
            semantic_mapping={"wetland_class": "gwd30_native_class_code"},
        )

    def load(
        self,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
    ) -> xr.Dataset:
        tiles_by_year = self._discover_tiles(bbox=bbox, time_range=time_range)
        if not tiles_by_year:
            raise FileNotFoundError(f"No GWD30 tiles found under {self.base_path}")

        year_datasets: list[xr.Dataset] = []
        for year, paths in sorted(tiles_by_year.items()):
            if not paths:
                continue
            logger.info("GWD30 loading year %s with %s tile(s)", year, len(paths))
            band_indexes: list[int] | None = None
            selected_times: list[pd.Timestamp] | None = None
            if time_range is not None:
                band_indexes, selected_times = self._selected_band_window(
                    year,
                    paths[0],
                    time_range=time_range,
                )
                if not band_indexes:
                    continue
            mosaics = [
                open_multiband_raster(
                    path,
                    reproject_to_wgs84=True,
                    bbox=bbox,
                    band_indexes=band_indexes,
                )
                for path in _iter_tiles_with_progress(paths, desc=f"GWD30 {year} load")
            ]
            merged = merge_rasters(mosaics)
            if selected_times is None:
                time_index = four_day_index_for_year(year, merged.sizes["band"])
            else:
                time_index = pd.DatetimeIndex(selected_times)
            merged = merged.assign_coords(band=time_index).rename({"band": "time"})
            year_datasets.append(merged.rename("wetland_class").to_dataset())

        if not year_datasets:
            raise FileNotFoundError(
                f"No GWD30 tiles found under {self.base_path} for requested time window"
            )

        dataset = xr.concat(year_datasets, dim="time").sortby("time")
        dataset = ensure_datetime_index(dataset)
        return self.finalize_dataset(dataset, bbox=bbox, time_range=time_range)

    def load_fine_classification_grid(
        self,
        *,
        bbox: BBox,
        reference_grid: xr.DataArray,
        year: int,
        worker_count: int | None = None,
    ) -> xr.Dataset:
        """Load one GWD30 year into a coarse classification grid.

        This avoids materializing the full 30m × 92-band annual mosaic in
        memory. The returned dataset contains:
        - ``wetland_class``: dominant raw GWD30 class per coarse cell
        - ``class_fractions``: raw class fractions (0-14) per coarse cell
        """

        time_range = (f"{year}-01-01", f"{year}-12-31")
        tiles_by_year = self._discover_tiles(bbox=bbox, time_range=time_range)
        paths = list(tiles_by_year.get(year, []))
        if not paths:
            raise FileNotFoundError(f"No GWD30 tiles found under {self.base_path} for year {year}")

        reference_crs, reference_transform, width, height = _reference_grid_spec(reference_grid)
        resolved_worker_count = _resolve_parallel_worker_count(worker_count)
        all_fractions = np.zeros((_GWD30_CLASS_COUNT, height, width), dtype=np.float32)
        covered = np.zeros((height, width), dtype=bool)

        def accumulate_tile(tile_path: Path) -> None:
            fractions, valid_mask = _process_fine_tile_to_fractions(
                path=str(tile_path),
                bbox=bbox,
                reference_crs=reference_crs,
                reference_transform=reference_transform,
                width=width,
                height=height,
            )
            if fractions is None or valid_mask is None:
                return
            new = valid_mask & ~covered
            all_fractions[:, new] = fractions[:, new]
            covered[:] = covered | valid_mask

        if resolved_worker_count > 1 and len(paths) > 1:
            fallback_to_serial = False
            processed_indices: set[int] = set()
            progress = tqdm(
                total=len(paths),
                desc=f"GWD30 {year} fine-parallel",
                unit="tile",
                dynamic_ncols=True,
                mininterval=5.0,
            )
            try:
                try:
                    with ProcessPoolExecutor(
                        max_workers=resolved_worker_count,
                        max_tasks_per_child=1,
                    ) as executor:
                        future_to_meta = {
                            executor.submit(
                                _process_fine_tile_to_fractions,
                                path=str(path),
                                bbox=bbox,
                                reference_crs=reference_crs,
                                reference_transform=reference_transform,
                                width=width,
                                height=height,
                            ): (index, path)
                            for index, path in enumerate(paths)
                        }
                        for future in as_completed(future_to_meta):
                            index, _path = future_to_meta[future]
                            try:
                                fractions, valid_mask = future.result()
                                processed_indices.add(index)
                                if fractions is not None and valid_mask is not None:
                                    new = valid_mask & ~covered
                                    all_fractions[:, new] = fractions[:, new]
                                    covered[:] = covered | valid_mask
                                progress.update(1)
                            except BrokenProcessPool:
                                fallback_to_serial = True
                                break
                            except Exception as exc:
                                logger.warning(
                                    "GWD30 tile %s skipped during fine parallel reduction (%s: %s)",
                                    paths[index].name,
                                    type(exc).__name__,
                                    exc,
                                )
                                processed_indices.add(index)
                                progress.update(1)
                except Exception as pool_exc:
                    logger.warning(
                        "GWD30 fine parallel execution failed (%s: %s); will retry serially",
                        type(pool_exc).__name__,
                        pool_exc,
                    )
                    fallback_to_serial = True

                if fallback_to_serial:
                    remaining = [
                        index for index in range(len(paths))
                        if index not in processed_indices
                    ]
                    logger.warning(
                        "GWD30 fine parallel failed after %d/%d tiles; "
                        "falling back to serial for %d remaining",
                        len(processed_indices),
                        len(paths),
                        len(remaining),
                    )
                    for index in remaining:
                        try:
                            accumulate_tile(paths[index])
                        except Exception as exc:
                            logger.warning(
                                "GWD30 tile %s failed during fine serial fallback (%s: %s)",
                                paths[index].name,
                                type(exc).__name__,
                                exc,
                            )
                        progress.update(1)
            finally:
                progress.close()
        else:
            for path in _iter_tiles_with_progress(paths, desc=f"GWD30 {year} fine"):
                accumulate_tile(path)

        dominant = all_fractions.argmax(axis=0).astype(np.float32)
        dominant[~covered] = np.nan

        data_vars = {
            "wetland_class": reference_grid.copy(data=dominant),
            "class_fractions": xr.DataArray(
                all_fractions,
                dims=("class_id", "lat", "lon"),
                coords={
                    "class_id": np.arange(_GWD30_CLASS_COUNT, dtype=np.int16),
                    "lat": reference_grid.coords["lat"].values,
                    "lon": reference_grid.coords["lon"].values,
                },
                attrs={"description": "GWD30 raw class fractions on coarse grid"},
            ),
        }
        dataset = xr.Dataset(data_vars)
        dataset["wetland_class"] = dataset["wetland_class"].rio.write_crs(reference_crs)
        dataset["wetland_class"] = dataset["wetland_class"].rio.set_spatial_dims(
            x_dim="lon",
            y_dim="lat",
        )
        dataset["class_fractions"].attrs.update(
            {"dataset_id": self.dataset_id, "year": year, "source": "low_memory_fine_grid"}
        )
        dataset["wetland_class"].attrs.update(
            {"dataset_id": self.dataset_id, "year": year, "source": "low_memory_fine_grid"}
        )
        return dataset

    def _discover_tiles(
        self,
        *,
        bbox: BBox | None,
        time_range: TimeRange | None,
    ) -> dict[int, list[Path]]:
        cache_key = (bbox, time_range)
        if cache_key in self._discover_tiles_cache:
            return self._discover_tiles_cache[cache_key]

        allowed_years = {int(year) for year in self.config.get("years", [])}
        if time_range is not None:
            start_year = int(time_range[0][:4])
            end_year = int(time_range[1][:4])
            allowed_years &= set(range(start_year, end_year + 1))

        grouped: dict[int, list[Path]] = defaultdict(list)
        for year in sorted(allowed_years):
            pattern = str(self.config["pattern"]).format(year=year)
            paths = sorted(self.base_path.glob(pattern))
            logger.info("GWD30 discovered %s candidate tile(s) for year %s", len(paths), year)
            if bbox is not None:
                paths = self._filter_tiles_for_bbox(paths, bbox)
                logger.info("GWD30 kept %s tile(s) for year %s after bbox filter", len(paths), year)
            for path in paths:
                grouped[year].append(path)
        self._discover_tiles_cache[cache_key] = grouped
        return grouped

    def _filter_tiles_for_bbox(self, paths: list[Path], bbox: BBox) -> list[Path]:
        """Filter candidate tiles for a lon/lat bbox using GWD30 tile codes first."""

        min_lon, min_lat, max_lon, max_lat = bbox
        tile_codes = set(self._tiling.bbox_to_tiles(min_lat, min_lon, max_lat, max_lon))
        if tile_codes:
            matched = [
                path
                for path in paths
                if (tile_code := _extract_tile_code(path)) is not None and tile_code in tile_codes
            ]
            if matched:
                logger.info(
                    "GWD30 tile-code prefilter matched %s/%s tile(s) for bbox %s",
                    len(matched),
                    len(paths),
                    bbox,
                )
                return matched

        logger.info("GWD30 falling back to raster-bounds scan for bbox %s", bbox)
        return _filter_files_by_bounds(paths, bbox)

    def load_rough_binary_surface(
        self,
        *,
        bbox: BBox,
        time_range: TimeRange,
        reference_grid: xr.DataArray,
        aggregation: str,
        target_time: pd.Timestamp,
        worker_count: int | None = None,
    ) -> tuple[xr.DataArray, dict[str, Any]]:
        """Load GWD30 directly into the coarse rough-comparison grid.

        This avoids materializing a full high-resolution annual mosaic, which can
        exceed memory for large tropical basins.
        """

        tiles_by_year = self._discover_tiles(bbox=bbox, time_range=time_range)
        if not tiles_by_year:
            raise FileNotFoundError(f"No GWD30 tiles found under {self.base_path}")

        trace: dict[str, Any] = {
            "strategy": "direct_to_reference_grid",
            "intermediate_storage": "temporary_coarse_geotiff_tiles",
            "mosaic_strategy": "average_of_processed_tiles",
            "bbox": list(bbox),
            "time_range": list(time_range),
            "target_time": target_time.isoformat(),
            "years": [],
        }
        resolved_worker_count = _resolve_parallel_worker_count(worker_count)
        trace["worker_count"] = resolved_worker_count
        with tempfile.TemporaryDirectory(prefix="wa_gwd30_rough_") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            processed_tile_paths: list[Path] = []
            accumulated_sum = np.zeros(reference_grid.shape, dtype=np.float32)
            accumulated_count = np.zeros(reference_grid.shape, dtype=np.int16)

            for year, paths in sorted(tiles_by_year.items()):
                if not paths:
                    continue
                band_indexes, selected_times = self._selected_band_window(
                    year,
                    paths[0],
                    time_range=time_range,
                )
                year_trace: dict[str, Any] = {
                    "year": year,
                    "matched_tile_count": len(paths),
                    "selected_band_indexes": [int(index) for index in band_indexes],
                    "selected_band_timestamps": [
                        timestamp.isoformat() for timestamp in selected_times
                    ],
                    "selected_tiles": [],
                }
                if not band_indexes:
                    trace["years"].append(year_trace)
                    continue

                logger.info(
                    "GWD30 direct rough load year %s with %s tile(s) and %s selected band(s)",
                    year,
                    len(paths),
                    len(band_indexes),
                )

                if resolved_worker_count > 1 and len(paths) > 1:
                    trace["strategy"] = "parallel_direct_to_reference_grid"
                    trace["intermediate_storage"] = "in_memory_partial_reduce"
                    trace["mosaic_strategy"] = "main_process_sum_count_reduce"
                    year_tile_entries, year_sum, year_count = self._reduce_year_tiles_parallel(
                        year=year,
                        paths=paths,
                        bbox=bbox,
                        band_indexes=band_indexes,
                        aggregation=aggregation,
                        reference_grid=reference_grid,
                        worker_count=resolved_worker_count,
                    )
                    year_trace["selected_tiles"].extend(year_tile_entries)
                    accumulated_sum = accumulated_sum + year_sum
                    accumulated_count = accumulated_count + year_count
                else:
                    for tile_index, path in enumerate(
                        _iter_tiles_with_progress(paths, desc=f"GWD30 {year} process"),
                        start=1,
                    ):
                        tile_code = _extract_tile_code(path)
                        tile_bbox = self._tile_bbox(tile_code) if tile_code is not None else None
                        temp_tile_path, coarse_non_null_count = self._process_rough_tile_to_temp(
                            path=path,
                            bbox=bbox,
                            band_indexes=band_indexes,
                            aggregation=aggregation,
                            temp_dir=temp_dir,
                            tile_token=f"{year}_{tile_index:05d}_{path.stem}",
                            reference_grid=reference_grid,
                        )
                        year_trace["selected_tiles"].append(
                            {
                                "path": str(path),
                                "tile_code": tile_code,
                                "tile_bbox": list(tile_bbox) if tile_bbox is not None else None,
                                "coarse_non_null_count": coarse_non_null_count,
                                "processed_temp_written": temp_tile_path is not None,
                            }
                        )
                        if temp_tile_path is not None:
                            processed_tile_paths.append(temp_tile_path)
                        gc.collect()

                trace["years"].append(year_trace)

            if trace["intermediate_storage"] == "in_memory_partial_reduce":
                surface_values = np.full(reference_grid.shape, np.nan, dtype=np.float32)
                valid_counts = accumulated_count > 0
                surface_values[valid_counts] = (
                    accumulated_sum[valid_counts] / accumulated_count[valid_counts]
                )
                surface = reference_grid.copy(data=surface_values.astype(np.float32))
            else:
                surface = self._mosaic_processed_tiles(
                    processed_tile_paths,
                    reference_grid=reference_grid,
                )

        trace["processed_temp_tile_count"] = len(processed_tile_paths)
        surface.name = "wetland_fraction"
        surface.attrs.update(
            {
                "dataset_id": self.dataset_id,
                "comparison_source_variable": "wetland_class",
                "comparison_aggregation": aggregation,
                "comparison_time": target_time.isoformat(),
                "comparison_source_time": target_time.isoformat(),
                "comparison_threshold": BINARY_WETLAND_THRESHOLD,
            }
        )
        return surface, trace

    def compute_rough_binary_partial(
        self,
        *,
        bbox: BBox,
        time_range: TimeRange,
        reference_grid: xr.DataArray,
        aggregation: str,
        target_time: pd.Timestamp,
        worker_count: int | None = None,
        shard_index: int = 0,
        shard_count: int = 1,
    ) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
        """Compute one shard's partial coarse-grid sum/count for GWD30 rough loading."""

        shard_index, shard_count = _normalize_shard_spec(shard_index, shard_count)
        tiles_by_year = self._discover_tiles(bbox=bbox, time_range=time_range)
        if not tiles_by_year:
            raise FileNotFoundError(f"No GWD30 tiles found under {self.base_path}")

        resolved_worker_count = _resolve_parallel_worker_count(worker_count)
        accumulated_sum = np.zeros(reference_grid.shape, dtype=np.float32)
        accumulated_count = np.zeros(reference_grid.shape, dtype=np.int16)
        trace: dict[str, Any] = {
            "strategy": "sharded_partial_reduce",
            "bbox": list(bbox),
            "time_range": list(time_range),
            "target_time": target_time.isoformat(),
            "worker_count": resolved_worker_count,
            "shard_index": shard_index,
            "shard_count": shard_count,
            "years": [],
        }

        for year, paths in sorted(tiles_by_year.items()):
            assigned_paths = _select_paths_for_shard(
                paths,
                shard_index=shard_index,
                shard_count=shard_count,
            )
            band_indexes, selected_times = self._selected_band_window(
                year,
                paths[0],
                time_range=time_range,
            )
            year_trace: dict[str, Any] = {
                "year": year,
                "matched_tile_count": len(paths),
                "assigned_tile_count": len(assigned_paths),
                "selected_band_indexes": [int(index) for index in band_indexes],
                "selected_band_timestamps": [
                    timestamp.isoformat() for timestamp in selected_times
                ],
                "selected_tiles": [],
            }
            if not band_indexes or not assigned_paths:
                trace["years"].append(year_trace)
                continue

            if resolved_worker_count > 1 and len(assigned_paths) > 1:
                year_tile_entries, year_sum, year_count = self._reduce_year_tiles_parallel(
                    year=year,
                    paths=assigned_paths,
                    bbox=bbox,
                    band_indexes=band_indexes,
                    aggregation=aggregation,
                    reference_grid=reference_grid,
                    worker_count=resolved_worker_count,
                )
            else:
                year_tile_entries, year_sum, year_count = self._reduce_year_tiles_serial(
                    year=year,
                    paths=assigned_paths,
                    bbox=bbox,
                    band_indexes=band_indexes,
                    aggregation=aggregation,
                    reference_grid=reference_grid,
                )
            year_trace["selected_tiles"].extend(year_tile_entries)
            accumulated_sum = accumulated_sum + year_sum
            accumulated_count = accumulated_count + year_count
            trace["years"].append(year_trace)

        return accumulated_sum, accumulated_count, trace

    def build_surface_from_partial(
        self,
        *,
        partial_sum: np.ndarray,
        partial_count: np.ndarray,
        reference_grid: xr.DataArray,
        aggregation: str,
        target_time: pd.Timestamp,
    ) -> xr.DataArray:
        """Convert reduced sum/count partial arrays into a final GWD30 coarse surface."""

        surface_values = np.full(reference_grid.shape, np.nan, dtype=np.float32)
        valid_counts = partial_count > 0
        surface_values[valid_counts] = partial_sum[valid_counts] / partial_count[valid_counts]
        surface = reference_grid.copy(data=surface_values.astype(np.float32))
        surface.name = "wetland_fraction"
        surface.attrs.update(
            {
                "dataset_id": self.dataset_id,
                "comparison_source_variable": "wetland_class",
                "comparison_aggregation": aggregation,
                "comparison_time": target_time.isoformat(),
                "comparison_source_time": target_time.isoformat(),
                "comparison_threshold": BINARY_WETLAND_THRESHOLD,
            }
        )
        return surface

    def _reduce_year_tiles_serial(
        self,
        *,
        year: int,
        paths: list[Path],
        bbox: BBox,
        band_indexes: list[int],
        aggregation: str,
        reference_grid: xr.DataArray,
    ) -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray]:
        """Process one year's tiles serially and accumulate coarse sum/count arrays."""

        reference_crs, reference_transform, width, height = _reference_grid_spec(reference_grid)
        accumulated_sum = np.zeros(reference_grid.shape, dtype=np.float32)
        accumulated_count = np.zeros(reference_grid.shape, dtype=np.int16)
        selected_tiles: list[dict[str, Any]] = []

        for path in _iter_tiles_with_progress(paths, desc=f"GWD30 {year} shard"):
            tile_code = _extract_tile_code(path)
            tile_bbox = self._tile_bbox(tile_code) if tile_code is not None else None
            coarse, coarse_non_null_count = _project_rough_tile_to_coarse_array(
                path=str(path),
                bbox=bbox,
                band_indexes=band_indexes,
                aggregation=aggregation,
                reference_crs=reference_crs,
                reference_transform=reference_transform,
                width=width,
                height=height,
            )
            if coarse is not None:
                valid = np.isfinite(coarse)
                accumulated_sum[valid] = accumulated_sum[valid] + coarse[valid]
                accumulated_count[valid] = accumulated_count[valid] + 1
            selected_tiles.append(
                {
                    "path": str(path),
                    "tile_code": tile_code,
                    "tile_bbox": list(tile_bbox) if tile_bbox is not None else None,
                    "coarse_non_null_count": coarse_non_null_count,
                    "processed_temp_written": False,
                    "processed_in_memory": coarse is not None,
                }
            )
        return selected_tiles, accumulated_sum, accumulated_count

    def _reduce_year_tiles_parallel(
        self,
        *,
        year: int,
        paths: list[Path],
        bbox: BBox,
        band_indexes: list[int],
        aggregation: str,
        reference_grid: xr.DataArray,
        worker_count: int,
    ) -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray]:
        """Process one year's GWD30 tiles in parallel and reduce them in memory.

        Falls back to serial processing if the process pool breaks (e.g. OOM).
        """

        reference_crs, reference_transform, width, height = _reference_grid_spec(reference_grid)
        accumulated_sum = np.zeros(reference_grid.shape, dtype=np.float32)
        accumulated_count = np.zeros(reference_grid.shape, dtype=np.int16)
        selected_tiles: list[dict[str, Any] | None] = [None] * len(paths)
        processed_indices: set[int] = set()
        fallback_to_serial = False

        progress = tqdm(
            total=len(paths),
            desc=f"GWD30 {year} parallel",
            unit="tile",
            dynamic_ncols=True,
            mininterval=5.0,
        )
        try:
            try:
                with ProcessPoolExecutor(
                    max_workers=worker_count,
                    max_tasks_per_child=1,
                ) as executor:
                    future_to_meta = {
                        executor.submit(
                            _process_rough_tile_to_partial,
                            path=str(path),
                            bbox=bbox,
                            band_indexes=band_indexes,
                            aggregation=aggregation,
                            reference_crs=reference_crs,
                            reference_transform=reference_transform,
                            width=width,
                            height=height,
                        ): (
                            index,
                            path,
                            _extract_tile_code(path),
                        )
                        for index, path in enumerate(paths)
                    }
                    for future in as_completed(future_to_meta):
                        index, path, tile_code = future_to_meta[future]
                        tile_bbox = self._tile_bbox(tile_code) if tile_code is not None else None
                        try:
                            tile_sum, tile_count, coarse_non_null_count = future.result()
                            processed_indices.add(index)
                            if tile_sum is not None and tile_count is not None:
                                accumulated_sum = accumulated_sum + tile_sum
                                accumulated_count = accumulated_count + tile_count.astype(np.int16)
                            progress.update(1)
                        except BrokenProcessPool:
                            fallback_to_serial = True
                            break
                        except Exception as exc:
                            processed_indices.add(index)
                            logger.warning(
                                "GWD30 tile %s skipped during parallel reduction (%s: %s)",
                                path.name,
                                type(exc).__name__,
                                exc,
                            )
                            tile_sum = None
                            tile_count = None
                            coarse_non_null_count = 0
                            progress.update(1)
                        selected_tiles[index] = {
                            "path": str(path),
                            "tile_code": tile_code,
                            "tile_bbox": list(tile_bbox) if tile_bbox is not None else None,
                            "coarse_non_null_count": coarse_non_null_count,
                            "processed_temp_written": False,
                            "processed_in_memory": tile_sum is not None and tile_count is not None,
                        }
            except Exception as pool_exc:
                if not isinstance(pool_exc, BrokenProcessPool):
                    logger.warning(
                        "GWD30 parallel execution failed (%s: %s); will retry serially",
                        type(pool_exc).__name__,
                        pool_exc,
                    )
                fallback_to_serial = True

            if fallback_to_serial:
                remaining = [i for i in range(len(paths)) if i not in processed_indices]
                logger.warning(
                    "GWD30 parallel failed after %d/%d tiles; "
                    "falling back to serial for %d remaining",
                    len(processed_indices),
                    len(paths),
                    len(remaining),
                )
                for i in remaining:
                    path = paths[i]
                    tile_code = _extract_tile_code(path)
                    tile_bbox = self._tile_bbox(tile_code) if tile_code is not None else None
                    try:
                        tile_sum, tile_count, coarse_non_null_count = (
                            _process_rough_tile_to_partial(
                                path=str(path),
                                bbox=bbox,
                                band_indexes=band_indexes,
                                aggregation=aggregation,
                                reference_crs=reference_crs,
                                reference_transform=reference_transform,
                                width=width,
                                height=height,
                            )
                        )
                        if tile_sum is not None and tile_count is not None:
                            accumulated_sum = accumulated_sum + tile_sum
                            accumulated_count = accumulated_count + tile_count.astype(np.int16)
                    except Exception as exc:
                        logger.warning(
                            "GWD30 tile %s failed during serial fallback (%s: %s)",
                            path.name,
                            type(exc).__name__,
                            exc,
                        )
                        tile_sum = None
                        tile_count = None
                        coarse_non_null_count = 0
                    selected_tiles[i] = {
                        "path": str(path),
                        "tile_code": tile_code,
                        "tile_bbox": list(tile_bbox) if tile_bbox is not None else None,
                        "coarse_non_null_count": coarse_non_null_count,
                        "processed_temp_written": False,
                        "processed_in_memory": tile_sum is not None and tile_count is not None,
                    }
                    progress.update(1)
        finally:
            progress.close()

        return (
            [entry for entry in selected_tiles if entry is not None],
            accumulated_sum,
            accumulated_count,
        )

    def _selected_band_window(
        self,
        year: int,
        sample_path: Path,
        *,
        time_range: TimeRange,
    ) -> tuple[list[int], list[pd.Timestamp]]:
        start_time = pd.Timestamp(time_range[0])
        end_time = pd.Timestamp(time_range[1])
        with rasterio.open(sample_path) as src:
            band_count = int(src.count)
        time_index = four_day_index_for_year(year, band_count)
        selected_indexes = [
            int(index)
            for index, timestamp in enumerate(time_index)
            if start_time <= timestamp <= end_time
        ]
        selected_times = [time_index[index] for index in selected_indexes]
        return selected_indexes, selected_times

    def _tile_bbox(self, tile_code: str | None) -> BBox | None:
        if tile_code is None:
            return None
        try:
            return self._tiling.tile_to_extent(tile_code)
        except Exception:
            return None

    def _process_rough_tile_to_temp(
        self,
        *,
        path: Path,
        bbox: BBox,
        band_indexes: list[int],
        aggregation: str,
        temp_dir: Path,
        tile_token: str,
        reference_grid: xr.DataArray,
    ) -> tuple[Path | None, int]:
        """Project one source tile to the coarse grid and persist it as a temp GeoTIFF."""

        reference_crs, reference_transform, width, height = _reference_grid_spec(reference_grid)
        coarse, coarse_non_null_count = _project_rough_tile_to_coarse_array(
            path=str(path),
            bbox=bbox,
            band_indexes=band_indexes,
            aggregation=aggregation,
            reference_crs=reference_crs,
            reference_transform=reference_transform,
            width=width,
            height=height,
        )
        if coarse is None or coarse_non_null_count == 0:
            return None, 0

        temp_tile_path = temp_dir / f"{tile_token}_coarse.tif"
        with rasterio.open(
            temp_tile_path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype="float32",
            crs=reference_crs,
            transform=reference_transform,
            nodata=float(_TEMP_TILE_NODATA),
            compress="deflate",
        ) as dst:
            temp_data = np.where(np.isfinite(coarse), coarse, _TEMP_TILE_NODATA).astype(np.float32)
            dst.write(temp_data, 1)

        return temp_tile_path, coarse_non_null_count

    def _mosaic_processed_tiles(
        self,
        temp_tile_paths: list[Path],
        *,
        reference_grid: xr.DataArray,
    ) -> xr.DataArray:
        """Average all processed coarse temp tiles into one final comparison surface."""

        accumulated_sum = np.zeros(reference_grid.shape, dtype=np.float32)
        accumulated_count = np.zeros(reference_grid.shape, dtype=np.int16)

        for temp_tile_path in _iter_tiles_with_progress(
            temp_tile_paths,
            desc="GWD30 mosaic",
        ):
            with rasterio.open(temp_tile_path) as src:
                tile = src.read(1, masked=True)
            tile_values = np.asarray(tile.filled(np.nan), dtype=np.float32)
            valid = np.isfinite(tile_values)
            accumulated_sum[valid] = accumulated_sum[valid] + tile_values[valid]
            accumulated_count[valid] = accumulated_count[valid] + 1

        surface_values = np.full(reference_grid.shape, np.nan, dtype=np.float32)
        valid_counts = accumulated_count > 0
        surface_values[valid_counts] = (
            accumulated_sum[valid_counts] / accumulated_count[valid_counts]
        )
        return reference_grid.copy(data=surface_values.astype(np.float32))
