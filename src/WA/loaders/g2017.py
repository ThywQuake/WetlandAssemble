"""Loader for the static G2017 GeoTIFF bundle."""

from __future__ import annotations

import xarray as xr
from rasterio.enums import Resampling

from WA.loaders._shared import open_single_band_raster, reproject_dataset_to_grid
from WA.loaders.base import BBox, DatasetLoader, DatasetMetadata, TimeRange, validate_reference_grid
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
        *,
        reference_grid: xr.DataArray | None = None,
    ) -> xr.Dataset:
        if reference_grid is not None:
            validate_reference_grid(reference_grid)

        files = self.config.get("files", {})
        ref_raster = open_single_band_raster(self.base_path / str(files["wetland"]), bbox=bbox)
        rasters = [ref_raster.rename("wetland").to_dataset()]

        for variable_name in ("wetland_nolake", "peatland"):
            raster = open_single_band_raster(self.base_path / str(files[variable_name]), bbox=bbox)
            aligned = raster.rio.reproject_match(ref_raster, resampling=Resampling.nearest)
            rasters.append(aligned.rename(variable_name).to_dataset())

        dataset = xr.merge(rasters, join="inner", compat="override")
        if reference_grid is not None:
            dataset = reproject_dataset_to_grid(
                dataset, reference_grid, resampling=Resampling.nearest,
            )
        return self.finalize_dataset(
            dataset, bbox=bbox, time_range=time_range, reference_grid=reference_grid,
        )
