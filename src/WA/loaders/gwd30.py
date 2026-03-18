"""Loader for GWD30 tiled multi-band GeoTIFF mosaics."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import xarray as xr

from WA.loaders._shared import (
    four_day_index_for_year,
    intersects_bbox,
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


@register_loader("gwd30")
class GWD30Loader(DatasetLoader):
    """Load annual GWD30 tiles and merge them into year-wise mosaics."""

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
            mosaics = [open_multiband_raster(path, reproject_to_wgs84=True) for path in paths]
            merged = merge_rasters(mosaics)
            time_index = four_day_index_for_year(year, merged.sizes["band"])
            merged = merged.assign_coords(band=time_index).rename({"band": "time"})
            year_datasets.append(merged.rename("wetland_class").to_dataset())

        dataset = xr.concat(year_datasets, dim="time").sortby("time")
        dataset = ensure_datetime_index(dataset)
        return self.finalize_dataset(dataset, bbox=bbox, time_range=time_range)

    def _discover_tiles(
        self,
        *,
        bbox: BBox | None,
        time_range: TimeRange | None,
    ) -> dict[int, list[Path]]:
        allowed_years = {int(year) for year in self.config.get("years", [])}
        if time_range is not None:
            start_year = int(time_range[0][:4])
            end_year = int(time_range[1][:4])
            allowed_years &= set(range(start_year, end_year + 1))

        grouped: dict[int, list[Path]] = defaultdict(list)
        for year in sorted(allowed_years):
            pattern = str(self.config["pattern"]).format(year=year)
            for path in sorted(self.base_path.glob(pattern)):
                if bbox is not None and not intersects_bbox(path, bbox):
                    continue
                grouped[year].append(path)
        return grouped
