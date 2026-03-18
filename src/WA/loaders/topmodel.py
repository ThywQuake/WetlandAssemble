"""Loader for TOPMODEL ensemble monthly NetCDF outputs."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import xarray as xr

from WA.loaders._shared import monthly_index_for_year
from WA.loaders.base import BBox, DatasetLoader, DatasetMetadata, TimeRange, ensure_datetime_index
from WA.loaders.registry import register_loader


@register_loader("topmodel")
class TopmodelLoader(DatasetLoader):
    """Load dynamically discovered TOPMODEL config/forcing combinations."""

    def metadata(self) -> DatasetMetadata:
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
            native_variables=("fwet",),
            semantic_mapping={"wetland_fraction": "topmodel_simulated_wetland_fraction"},
        )

    def load(
        self,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
    ) -> xr.Dataset:
        discovered = self._discover_files()
        if not discovered:
            raise FileNotFoundError(f"No TOPMODEL files found under {self.base_path}")

        by_config: dict[str, list[xr.Dataset]] = defaultdict(list)
        for (config_name, forcing_name), entries in discovered.items():
            year_datasets: list[xr.Dataset] = []
            for year, path in sorted(entries, key=lambda item: item[0]):
                source = xr.open_dataset(path)
                data = source["fwet"].rename("wetland_fraction")
                month_numbers = [int(value) for value in data["time"].values]
                data = data.assign_coords(time=monthly_index_for_year(year, month_numbers))
                year_datasets.append(data.to_dataset())

            merged_years = xr.concat(year_datasets, dim="time").sortby("time")
            by_config[config_name].append(merged_years.expand_dims(forcing=[forcing_name]))

        config_datasets: list[xr.Dataset] = []
        for config_name, forcing_datasets in sorted(by_config.items()):
            ordered_forcings = sorted(
                forcing_datasets,
                key=lambda item: str(item["forcing"].item()),
            )
            forcing_merged = xr.concat(ordered_forcings, dim="forcing")
            config_datasets.append(forcing_merged.expand_dims(config=[config_name]))

        dataset = xr.concat(config_datasets, dim="config", join="outer")
        dataset = ensure_datetime_index(dataset)
        return self.finalize_dataset(dataset, bbox=bbox, time_range=time_range)

    def _discover_files(self) -> dict[tuple[str, str], list[tuple[int, Path]]]:
        grouped: dict[tuple[str, str], list[tuple[int, Path]]] = defaultdict(list)
        for path in self.base_path.rglob("fwet_*_reso025_*.nc"):
            if len(path.parents) < 2:
                continue
            forcing_name = path.parent.name
            config_name = path.parent.parent.name
            match = re.search(r"_(\d{4})\.nc$", path.name)
            if match is None:
                continue
            grouped[(config_name, forcing_name)].append((int(match.group(1)), path))
        return grouped
