"""Generic NetCDF loaders for GIEMS-MC and WAD2M."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import xarray as xr
from rasterio.enums import Resampling

from WA.loaders._shared import reproject_dataset_to_grid
from WA.loaders.base import (
    BBox,
    DatasetLoader,
    DatasetMetadata,
    TimeRange,
    ensure_datetime_index,
    validate_reference_grid,
)
from WA.loaders.registry import register_loader

SUPPORTED_NETCDF_DATASETS: dict[str, Mapping[str, Any]] = {
    "giems_mc": {
        "source_variable": "inund_sat_wetland_frac",
        "target_variable": "wetland_fraction",
        "semantic_mapping": {"wetland_fraction": "satellite_inundation_fraction"},
        "mask_values": (-999, -998, -997),
    },
    "wad2m": {
        "source_variable": "Fw",
        "target_variable": "wetland_fraction",
        "semantic_mapping": {"wetland_fraction": "vegetated_wetland_fraction"},
        "mask_values": (),
    },
}


@register_loader("netcdf")
class GenericNetCDFLoader(DatasetLoader):
    """Load a supported single-file NetCDF dataset into a shared representation."""

    def metadata(self) -> DatasetMetadata:
        spec = self._spec()
        return DatasetMetadata(
            dataset_id=self.dataset_id,
            name=self.name,
            source_path=str(self.base_path / str(self.config["file"])),
            crs="EPSG:4326",
            spatial_resolution=self.config.get("resolution"),
            temporal_coverage=self.temporal_coverage(),
            time_resolution=self.config.get("time_resolution", "monthly"),
            is_static=False,
            is_classification=bool(self.config.get("classification", False)),
            native_variables=(str(spec["source_variable"]),),
            semantic_mapping=spec["semantic_mapping"],
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

        source = xr.open_dataset(self.base_path / str(self.config["file"]))
        spec = self._spec()
        source_variable = str(spec["source_variable"])
        target_variable = str(spec["target_variable"])

        if source_variable not in source:
            raise KeyError(f"{source_variable!r} was not found in {self.dataset_id}")

        dataset = source[[source_variable]].rename({source_variable: target_variable})
        for mask_value in spec["mask_values"]:
            dataset[target_variable] = dataset[target_variable].where(
                dataset[target_variable] != mask_value, np.nan
            )

        dataset = ensure_datetime_index(dataset)
        if reference_grid is not None:
            is_classification = bool(self.config.get("classification", False))
            resampling = Resampling.nearest if is_classification else Resampling.bilinear
            dataset = reproject_dataset_to_grid(
                dataset, reference_grid, resampling=resampling,
            )
        return self.finalize_dataset(
            dataset, bbox=bbox, time_range=time_range, reference_grid=reference_grid,
        )

    def open_time_series(
        self,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
    ) -> xr.Dataset:
        """Open one lazily-backed time-series window for repeated chunk access."""

        source = xr.open_dataset(self.base_path / str(self.config["file"]))
        try:
            spec = self._spec()
            source_variable = str(spec["source_variable"])
            target_variable = str(spec["target_variable"])

            if source_variable not in source:
                raise KeyError(f"{source_variable!r} was not found in {self.dataset_id}")

            dataset = source[[source_variable]].rename({source_variable: target_variable})
            for mask_value in spec["mask_values"]:
                dataset[target_variable] = dataset[target_variable].where(
                    dataset[target_variable] != mask_value, np.nan
                )

            dataset = ensure_datetime_index(dataset)
            dataset = self.finalize_dataset(dataset, bbox=bbox, time_range=time_range)
        except Exception:
            source.close()
            raise

        dataset.set_close(source.close)
        return dataset

    def _spec(self) -> Mapping[str, Any]:
        try:
            return SUPPORTED_NETCDF_DATASETS[self.dataset_id]
        except KeyError as exc:
            raise NotImplementedError(
                f"{self.dataset_id} is not supported by the generic NetCDF loader."
            ) from exc
