"""Loader for Berkeley-RWAWC monthly NetCDF files."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import xarray as xr

from WA.loaders.base import BBox, DatasetLoader, DatasetMetadata, TimeRange, ensure_datetime_index
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
    ) -> xr.Dataset:
        file_pattern = str(self.config["pattern"])
        candidate_files = sorted(self.base_path.glob(file_pattern))
        if not candidate_files:
            raise FileNotFoundError(
                f"No Berkeley files matched {file_pattern!r} under {self.base_path}"
            )

        variable_name = str(self.config.get("variables", {}).get("watermask", "watermask"))
        slices: list[xr.Dataset] = []
        for path in candidate_files:
            timestamp = _parse_year_month(path)
            source = xr.open_dataset(path, decode_times=False)
            selected = source[variable_name]
            if "time" in selected.dims:
                selected = selected.isel(time=0, drop=True)
            dataset = selected.to_dataset(name="watermask").expand_dims(time=[timestamp])
            slices.append(dataset)

        merged = xr.concat(slices, dim="time").sortby("time")
        merged = ensure_datetime_index(merged)
        return self.finalize_dataset(merged, bbox=bbox, time_range=time_range)


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
