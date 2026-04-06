"""Helpers for browsing and loading standardized netCDF outputs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import xarray as xr

from WA.loaders.base import (
    BBox,
    TimeRange,
    apply_bbox,
    apply_time_range,
    ensure_datetime_index,
    normalize_spatial_dimensions,
)


@dataclass(frozen=True)
class StandardizedDataset:
    """Metadata for one standardized netCDF file on disk."""

    dataset_id: str
    file_path: Path
    is_static: bool
    year: int | None = None
    time_range: tuple[str, str] | None = None


class StandardizedDataLoader:
    """Browse and lazily open standardized dataset outputs."""

    STATIC_DATASETS = {"g2017", "glwd_v2"}
    DYNAMIC_DATASETS = {
        "berkeley_rwawc",
        "giems_mc",
        "swamps",
        "wad2m",
        "gwd30",
        "topmodel",
    }

    def __init__(
        self,
        standardized_dir: str | Path = "output/standardized",
    ) -> None:
        self.standardized_dir = Path(standardized_dir).expanduser()

    def list_available_datasets(self) -> list[StandardizedDataset]:
        """List every standardized netCDF currently present."""

        if not self.standardized_dir.exists():
            return []

        datasets: list[StandardizedDataset] = []
        for nc_file in sorted(self.standardized_dir.glob("*.nc")):
            base_id, year = _split_dataset_id(nc_file.stem)
            datasets.append(
                StandardizedDataset(
                    dataset_id=nc_file.stem,
                    file_path=nc_file,
                    is_static=base_id in self.STATIC_DATASETS,
                    year=year,
                )
            )
        return datasets

    def load(
        self,
        dataset_id: str,
        year: int | None = None,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
    ) -> xr.Dataset:
        """Load one standardized dataset, optionally spanning multiple year files."""

        file_paths = self.resolve_file_paths(
            dataset_id,
            year=year,
            time_range=time_range,
        )
        source_paths = [str(path) for path in file_paths]

        sources: list[xr.Dataset] = []
        try:
            for path in file_paths:
                sources.append(xr.open_dataset(path, decode_cf=True))

            if len(sources) == 1:
                dataset = sources[0]
            else:
                dataset = _concat_time_series(sources)
                dataset.set_close(lambda: _close_sources(sources))

            dataset = normalize_spatial_dimensions(dataset)
            dataset = ensure_datetime_index(dataset)
            dataset = apply_bbox(dataset, bbox)
            dataset = apply_time_range(dataset, time_range)
            dataset.attrs.setdefault("standardized_source_files", source_paths)
            return dataset
        except Exception:
            _close_sources(sources)
            raise

    def resolve_file_paths(
        self,
        dataset_id: str,
        *,
        year: int | None = None,
        time_range: TimeRange | None = None,
    ) -> list[Path]:
        """Resolve the standardized netCDF files required for one request."""

        base_id, dataset_year = _split_dataset_id(dataset_id)
        requested_year = year if year is not None else dataset_year

        if base_id in self.STATIC_DATASETS:
            path = self.standardized_dir / f"{base_id}.nc"
            if not path.exists():
                raise FileNotFoundError(f"File does not exist: {path}")
            return [path]

        matches = self._dynamic_matches(base_id)
        if not matches:
            raise FileNotFoundError(f"No standardized files were found for {base_id}")

        if requested_year is not None:
            try:
                return [matches[requested_year]]
            except KeyError as exc:
                raise FileNotFoundError(
                    f"Did not find standardized file for {base_id} year {requested_year}"
                ) from exc

        if time_range is None:
            return [matches[year_key] for year_key in sorted(matches)]

        start = pd.Timestamp(time_range[0])
        end = pd.Timestamp(time_range[1])
        selected = [
            path
            for year_key, path in sorted(matches.items())
            if start.year <= year_key <= end.year
        ]
        if not selected:
            raise FileNotFoundError(
                f"No standardized files for {base_id} overlap {time_range!r}"
            )
        return selected

    def load_all_for_year(
        self,
        year: int,
        bbox: BBox | None = None,
        exclude: list[str] | None = None,
    ) -> dict[str, xr.Dataset]:
        """Load every available dataset for one analysis year."""

        exclude_set = set(exclude or [])
        results: dict[str, xr.Dataset] = {}

        for ds_info in self.list_available_datasets():
            base_id, _year = _split_dataset_id(ds_info.dataset_id)
            if ds_info.dataset_id in exclude_set or base_id in exclude_set:
                continue

            try:
                if ds_info.is_static:
                    results[ds_info.dataset_id] = self.load(base_id, bbox=bbox)
                elif ds_info.year == year:
                    results[ds_info.dataset_id] = self.load(base_id, year=year, bbox=bbox)
            except Exception:
                continue

        return results

    def get_time_range(self, dataset_id: str, year: int | None = None) -> tuple[str, str] | None:
        """Return the time span exposed by one standardized request."""

        dataset = self.load(dataset_id, year=year)
        try:
            if "time" not in dataset.coords:
                return None

            times = dataset.coords["time"].values
            if len(times) == 0:
                return None

            return (str(times[0])[:10], str(times[-1])[:10])
        finally:
            close = getattr(dataset, "close", None)
            if callable(close):
                close()

    def _dynamic_matches(self, dataset_id: str) -> dict[int, Path]:
        matches: dict[int, Path] = {}
        for path in sorted(self.standardized_dir.glob(f"{dataset_id}_*.nc")):
            base_id, year = _split_dataset_id(path.stem)
            if base_id == dataset_id and year is not None:
                matches[year] = path
        return matches


def _split_dataset_id(dataset_id: str) -> tuple[str, int | None]:
    parts = dataset_id.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0], int(parts[1])
    return dataset_id, None


def _concat_time_series(sources: Iterable[xr.Dataset]) -> xr.Dataset:
    materialized = list(sources)
    first = materialized[0]
    if "time" not in first.dims and "time" not in first.coords:
        raise ValueError("Cannot concatenate standardized datasets without a time dimension")
    return xr.concat(materialized, dim="time").sortby("time")


def _close_sources(sources: Iterable[xr.Dataset]) -> None:
    for source in sources:
        source.close()
