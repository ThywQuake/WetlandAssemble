"""Loader for GLWD v2 combined and area-by-class rasters."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import xarray as xr

from WA.loaders._shared import open_single_band_raster, parse_first_integer
from WA.loaders.base import BBox, DatasetLoader, DatasetMetadata, TimeRange
from WA.loaders.registry import register_loader


@register_loader("glwd")
class GLWDLoader(DatasetLoader):
    """Load GLWD v2 combined classes and area-by-class products."""

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
            native_variables=("combined_classes", "area_by_class_ha", "area_by_class_pct"),
            semantic_mapping={
                "combined_classes": "glwd_combined_classification",
                "area_by_class_ha": "class_area_hectares",
                "area_by_class_pct": "class_area_percentage",
            },
        )

    def load(
        self,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
    ) -> xr.Dataset:
        subdirectories = self.config["subdirectories"]
        combined_directory = self.base_path / str(subdirectories["combined_classes"])
        combined_raster = self._first_raster(combined_directory)
        combined = open_single_band_raster(combined_raster).rename("combined_classes").to_dataset()

        area_ha = self._stack_area_rasters(
            self.base_path / str(subdirectories["area_by_class_ha"]),
            "area_by_class_ha",
            float(self.config.get("scale_factor", {}).get("ha", 1.0)),
        )
        area_pct = self._stack_area_rasters(
            self.base_path / str(subdirectories["area_by_class_pct"]),
            "area_by_class_pct",
            float(self.config.get("scale_factor", {}).get("pct", 1.0)),
        )

        dataset = xr.merge([combined, area_ha, area_pct], join="outer", compat="override")
        return self.finalize_dataset(dataset, bbox=bbox, time_range=time_range)

    def _stack_area_rasters(
        self,
        directory: Path,
        variable_name: str,
        scale_factor: float,
    ) -> xr.Dataset:
        members = sorted(directory.glob("*.tif"))
        if not members:
            raise FileNotFoundError(f"No GLWD rasters found in {directory}")

        arrays = []
        class_ids = []
        for path in members:
            arrays.append(open_single_band_raster(path))
            class_ids.append(parse_first_integer(path.stem))

        stacked = xr.concat(arrays, dim=pd.Index(class_ids, name="glwd_class")) * scale_factor
        return stacked.rename(variable_name).to_dataset()

    @staticmethod
    def _first_raster(directory: Path) -> Path:
        matches = sorted(directory.glob("*.tif"))
        if not matches:
            raise FileNotFoundError(f"No GLWD combined-class raster found in {directory}")
        return matches[0]
