"""Loader for TOPMODEL ensemble monthly NetCDF outputs."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path

import xarray as xr

from WA.loaders._shared import monthly_index_for_year
from WA.loaders.base import (
    BBox,
    DatasetLoader,
    DatasetMetadata,
    TimeRange,
    apply_bbox,
    apply_time_range,
    ensure_datetime_index,
)
from WA.loaders.registry import register_loader

logger = logging.getLogger(__name__)


@register_loader("topmodel")
class TopmodelLoader(DatasetLoader):
    """Load dynamically discovered TOPMODEL config/forcing combinations."""

    def __init__(self, dataset_id: str, config: dict[str, object]) -> None:
        super().__init__(dataset_id, config)
        self._discover_files_cache: dict[
            tuple[str | None, str | None],
            dict[tuple[str, str], list[tuple[int, Path]]],
        ] = {}

    def metadata(self) -> DatasetMetadata:
        temporal_coverage = self._discovered_temporal_coverage()
        return DatasetMetadata(
            dataset_id=self.dataset_id,
            name=self.name,
            source_path=str(self.base_path),
            crs="EPSG:4326",
            spatial_resolution=self.config.get("resolution"),
            temporal_coverage=temporal_coverage,
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
        discovered = self._discover_files(time_range)
        if not discovered:
            raise FileNotFoundError(f"No TOPMODEL files found under {self.base_path}")

        file_count = sum(len(entries) for entries in discovered.values())
        logger.info(
            "TOPMODEL discovered %s config/forcing combination(s), %s file(s)",
            len(discovered),
            file_count,
        )

        by_config: dict[str, list[xr.Dataset]] = defaultdict(list)
        for (config_name, forcing_name), entries in discovered.items():
            logger.info(
                "TOPMODEL loading config=%s forcing=%s with %s year file(s)",
                config_name,
                forcing_name,
                len(entries),
            )
            year_datasets: list[xr.Dataset] = []
            for year, path in sorted(entries, key=lambda item: item[0]):
                with xr.open_dataset(path) as source:
                    data = source["fwet"].rename("wetland_fraction")
                    month_numbers = [int(value) for value in data["time"].values]
                    data = data.assign_coords(time=monthly_index_for_year(year, month_numbers))
                    dataset = data.to_dataset()
                    dataset = apply_bbox(dataset, bbox)
                    dataset = apply_time_range(dataset, time_range)
                    year_datasets.append(dataset.load())

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

    def _discover_files(
        self,
        time_range: TimeRange | None = None,
    ) -> dict[tuple[str, str], list[tuple[int, Path]]]:
        cache_key = time_range if time_range is not None else (None, None)
        if cache_key in self._discover_files_cache:
            return self._discover_files_cache[cache_key]

        start_year: int | None = None
        end_year: int | None = None
        if time_range is not None:
            start_year = int(time_range[0][:4])
            end_year = int(time_range[1][:4])

        grouped: dict[tuple[str, str], list[tuple[int, Path]]] = defaultdict(list)
        for path in self.base_path.rglob("fwet_*_reso025_*.nc"):
            if len(path.parents) < 2:
                continue
            forcing_name = path.parent.name
            config_name = path.parent.parent.name
            match = re.search(r"_(\d{4})\.nc$", path.name)
            if match is None:
                continue
            year = int(match.group(1))
            if (
                start_year is not None
                and end_year is not None
                and not (start_year <= year <= end_year)
            ):
                continue
            grouped[(config_name, forcing_name)].append((year, path))
        self._discover_files_cache[cache_key] = grouped
        return grouped

    def _discovered_temporal_coverage(self) -> tuple[str | None, str | None] | None:
        discovered = self._discover_files()
        years = [year for entries in discovered.values() for year, _ in entries]
        if not years:
            return self.temporal_coverage()
        return (str(min(years)), str(max(years)))
