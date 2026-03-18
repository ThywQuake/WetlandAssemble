"""Loader for the static G2017 GeoTIFF bundle."""

from __future__ import annotations

import xarray as xr

from WA.loaders._shared import open_single_band_raster
from WA.loaders.base import BBox, DatasetLoader, DatasetMetadata, TimeRange
from WA.loaders.registry import register_loader


@register_loader("geotiff")
class G2017Loader(DatasetLoader):
    """Load the G2017 wetland and peatland bundle."""

    def metadata(self) -> DatasetMetadata:
        return DatasetMetadata(
            dataset_id=self.dataset_id,
            name=self.name,
            source_path=str(self.base_path),
            crs="EPSG:4326",
            spatial_resolution=self.config.get("resolution"),
            temporal_coverage=None,
            time_resolution=None,
            is_static=True,
            is_classification=True,
            native_variables=("wetland", "wetland_nolake", "peatland"),
            semantic_mapping={
                "wetland": "wetland_classification",
                "wetland_nolake": "wetland_classification_without_open_lake",
                "peatland": "peatland_presence",
            },
        )

    def load(
        self,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
    ) -> xr.Dataset:
        files = self.config.get("files", {})
        rasters = []
        for variable_name in ("wetland", "wetland_nolake", "peatland"):
            raster = open_single_band_raster(self.base_path / str(files[variable_name]))
            rasters.append(raster.rename(variable_name).to_dataset())

        dataset = xr.merge(rasters, join="outer", compat="override")
        return self.finalize_dataset(dataset, bbox=bbox, time_range=time_range)
