"""Loader for Berkeley-RWAWC monthly NetCDF files."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import xarray as xr
from rasterio.enums import Resampling

from WA.loaders._shared import reproject_dataset_to_grid
from WA.loaders.base import (
    BBox,
    DatasetLoader,
    DatasetMetadata,
    TimeRange,
    apply_bbox,
    ensure_datetime_index,
    validate_reference_grid,
)
from WA.loaders.registry import register_loader


@register_loader("berkeley")
class BerkeleyLoader(DatasetLoader):
    """Load monthly Berkeley-RWAWC watermask files."""

    def metadata(self) -> DatasetMetadata:
        variable_name = self.config.get("variables", {}).get("watermask", "watermask")
        return DatasetMetadata(
            dataset_id=self.dataset_id,
            name=self.name,
            source_path=str(self.base_path),
            crs="EPSG:4326",
            spatial_resolution=self.config.get("resolution"),
            temporal_coverage=self.temporal_coverage(),
            time_resolution=self.config.get("time_resolution", "monthly"),
            is_static=False,
            is_classification=False,
            native_variables=(str(variable_name),),
            semantic_mapping={"watermask": "auxiliary_open_water_mask"},
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

        merged = self.open_time_series(time_range)
        try:
            merged = apply_bbox(merged, bbox)
            if reference_grid is not None:
                merged = reproject_dataset_to_grid(
                    merged, reference_grid, resampling=Resampling.bilinear,
                )
            return self.finalize_dataset(
                merged, bbox=bbox, time_range=time_range, reference_grid=reference_grid,
            )
        finally:
            merged.close()

    def open_time_series(self, time_range: TimeRange | None = None) -> xr.Dataset:
        """Open the requested monthly files once and expose them as one lazy dataset."""
        candidate_files = self._candidate_files(time_range)
        if not candidate_files:
            raise FileNotFoundError(
                f"No Berkeley files matched the requested time range under {self.base_path}"
            )

        sources: list[xr.Dataset] = []
        slices: list[xr.Dataset] = []
        for path in candidate_files:
            timestamp = _parse_year_month(path)
            source = xr.open_dataset(path, decode_times=False)
            sources.append(source)
            variable_name = self._resolve_variable_name(source)
            selected = source[variable_name]
            if "time" in selected.dims:
                selected = selected.isel(time=0, drop=True)
            dataset = selected.to_dataset(name="watermask").expand_dims(time=[timestamp])
            slices.append(dataset)

        merged = xr.concat(slices, dim="time").sortby("time")
        merged = ensure_datetime_index(merged)

        def _close_sources() -> None:
            for source in sources:
                source.close()

        merged.set_close(_close_sources)
        return merged

    def _candidate_files(self, time_range: TimeRange | None) -> list[Path]:
        file_pattern = str(self.config["pattern"])
        candidate_files = sorted(self.base_path.glob(file_pattern))
        if time_range is None:
            return candidate_files

        start = pd.Timestamp(time_range[0])
        end = pd.Timestamp(time_range[1])
        return [
            path
            for path in candidate_files
            if start <= _parse_year_month(path) <= end
        ]

    def _resolve_variable_name(self, source: xr.Dataset) -> str:
        configured = str(self.config.get("variables", {}).get("watermask", "watermask"))
        candidates = [
            configured,
            configured.replace("_", ""),
            configured.replace("_", "-"),
            "watermask",
            "water_mask",
        ]
        for candidate in candidates:
            if candidate in source.data_vars:
                return candidate

        available = ", ".join(sorted(str(name) for name in source.data_vars))
        raise KeyError(
            f"Could not resolve Berkeley watermask variable. Tried {candidates}. "
            f"Available variables: {available}"
        )


def _parse_year_month(path: Path) -> pd.Timestamp:
    patterns = (
        r"(?<!\d)(?P<year>\d{4})[-_\.]?(?P<month>\d{2})(?!\d)",
        r"(?<!\d)(?P<year>\d{4})m(?P<month>\d{2})(?!\d)",
    )

    for pattern in patterns:
        match = re.search(pattern, path.stem)
        if match is None:
            continue
        year = int(match.group("year"))
        month = int(match.group("month"))
        if 1 <= month <= 12:
            return pd.Timestamp(year=year, month=month, day=1)

    raise ValueError(f"Could not parse a YYYYMM-style token from {path.name}")
