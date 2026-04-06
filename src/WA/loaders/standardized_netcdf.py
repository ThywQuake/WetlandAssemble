"""Loader for standardized netCDF outputs stored under one directory."""

from __future__ import annotations

import xarray as xr
from rasterio.enums import Resampling

from WA.loaders._shared import reproject_dataset_to_grid
from WA.loaders.base import (
    BBox,
    DatasetLoader,
    DatasetMetadata,
    TimeRange,
    validate_reference_grid,
)
from WA.loaders.registry import register_loader
from WA.standardized_loader import StandardizedDataLoader


@register_loader("standardized_netcdf")
class StandardizedNetCDFLoader(DatasetLoader):
    """Load pre-standardized annual or static netCDF products."""

    def __init__(self, dataset_id: str, config: dict[str, object]) -> None:
        super().__init__(dataset_id, config)
        self._standardized = StandardizedDataLoader(self.base_path)

    def metadata(self) -> DatasetMetadata:
        temporal_coverage = self.temporal_coverage()
        if temporal_coverage is None and not self._is_static():
            valid_years = [
                dataset.year
                for dataset in self._standardized.list_available_datasets()
                if dataset.dataset_id.startswith(f"{self.dataset_id}_") and dataset.year is not None
            ]
            if valid_years:
                temporal_coverage = (str(min(valid_years)), str(max(valid_years)))

        file_pattern = self.config.get("file") or self.config.get("annual_pattern")
        source_path = str(
            self.base_path if file_pattern is None else self.base_path / str(file_pattern)
        )
        return DatasetMetadata(
            dataset_id=self.dataset_id,
            name=self.name,
            source_path=source_path,
            crs="EPSG:4326",
            spatial_resolution=self.config.get("resolution"),
            temporal_coverage=temporal_coverage,
            time_resolution=self.config.get("time_resolution"),
            is_static=self._is_static(),
            is_classification=bool(self.config.get("is_classification", False)),
            native_variables=tuple(self.config.get("native_variables", ())),
            semantic_mapping=dict(self.config.get("semantic_mapping", {})),
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

        dataset = self._standardized.load(
            self.dataset_id,
            bbox=bbox,
            time_range=time_range,
        )
        if reference_grid is not None:
            resampling = (
                Resampling.nearest
                if bool(self.config.get("is_classification", False))
                else Resampling.bilinear
            )
            dataset = reproject_dataset_to_grid(dataset, reference_grid, resampling=resampling)
        dataset = self.finalize_dataset(
            dataset,
            bbox=bbox,
            time_range=time_range,
            reference_grid=reference_grid,
        )
        dataset.attrs.update(self.metadata().to_attrs())
        return dataset

    def open_time_series(
        self,
        time_range: TimeRange | None = None,
        *,
        bbox: BBox | None = None,
    ) -> xr.Dataset:
        """Expose a lazily-backed standardized time window for reuse."""

        dataset = self._standardized.load(
            self.dataset_id,
            bbox=bbox,
            time_range=time_range,
        )
        dataset = self.finalize_dataset(dataset, bbox=bbox, time_range=time_range)
        dataset.attrs.update(self.metadata().to_attrs())
        return dataset

    def _is_static(self) -> bool:
        return bool(self.config.get("is_static", False))
