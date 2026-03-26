"""Loader for SWAMPS daily inundation fraction files."""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from rasterio.enums import Resampling

from WA.loaders._shared import parse_compact_date, reproject_dataset_to_grid
from WA.loaders.base import (
    BBox,
    DatasetLoader,
    DatasetMetadata,
    TimeRange,
    ensure_datetime_index,
    validate_reference_grid,
)
from WA.loaders.registry import register_loader


@register_loader("swamps")
class SwampsLoader(DatasetLoader):
    """Load SWAMPS daily tiles into a continuous time series."""

    def metadata(self) -> DatasetMetadata:
        return DatasetMetadata(
            dataset_id=self.dataset_id,
            name=self.name,
            source_path=str(self.base_path),
            crs="EPSG:4326",
            spatial_resolution=self.config.get("resolution"),
            temporal_coverage=self.temporal_coverage(),
            time_resolution=self.config.get("time_resolution", "daily"),
            is_static=False,
            is_classification=False,
            native_variables=("fw", "flag"),
            semantic_mapping={
                "wetland_fraction": "surface_water_fraction",
                "flag": "quality_screening_flag",
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

        files = self._candidate_files(time_range)
        if not files:
            raise FileNotFoundError(f"No SWAMPS files found under {self.base_path}")

        slices: list[xr.Dataset] = []
        for path in files:
            source = xr.open_dataset(path)
            data_vars = {"fw": "wetland_fraction"}
            if "flag" in source:
                data_vars["flag"] = "flag"
            dataset = source[list(data_vars)].rename(data_vars)
            dataset["wetland_fraction"] = dataset["wetland_fraction"].where(
                dataset["wetland_fraction"] != -9999.0, np.nan
            )
            if "time" not in dataset.dims:
                dataset = dataset.expand_dims(time=[parse_compact_date(path)])
            slices.append(dataset)

        merged = xr.concat(slices, dim="time").sortby("time")
        merged = ensure_datetime_index(merged)
        merged.attrs["sensor_shift_year"] = self.config.get("sensor_shift_year")
        if reference_grid is not None:
            merged = reproject_dataset_to_grid(
                merged, reference_grid, resampling=Resampling.bilinear,
            )
        return self.finalize_dataset(
            merged, bbox=bbox, time_range=time_range, reference_grid=reference_grid,
        )

    def _candidate_files(self, time_range: TimeRange | None) -> list[Path]:
        if time_range is None:
            return sorted(self.base_path.rglob("*.nc"))

        start = pd.Timestamp(time_range[0])
        end = pd.Timestamp(time_range[1])
        months = pd.period_range(start=start, end=end, freq="M")
        patterns = (
            self.base_path
            / str(self.config["pattern"]).format(
                year=period.year,
                month=f"{period.month:02d}",
            )
            for period in months
        )
        files = [sorted(path.parent.glob(path.name)) for path in patterns]
        return sorted(itertools.chain.from_iterable(files))
