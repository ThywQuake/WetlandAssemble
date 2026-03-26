"""Loader for GLWD v2 combined and area-by-class rasters."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import xarray as xr
from rasterio.enums import Resampling

from WA.loaders._shared import open_single_band_raster, reproject_dataset_to_grid
from WA.loaders.base import BBox, DatasetLoader, DatasetMetadata, TimeRange, validate_reference_grid
from WA.loaders.registry import register_loader


def _parse_glwd_class_id(stem: str) -> int:
    """Extract class ID from GLWD filename like 'GLWD_v2_0_class_00_ha_x10'."""
    match = re.search(r"class[_-]?(\d+)", stem, re.IGNORECASE)
    if match is None:
        raise ValueError(f"Cannot extract GLWD class ID from {stem!r}")
    return int(match.group(1))


def _combined_raster_priority(path: Path) -> int:
    """Rank candidate combined-class rasters from most to least preferred."""

    stem = path.stem.lower()
    if "main_class" in stem and "50pct" not in stem:
        return 0
    if "main_class" in stem and "50pct" in stem:
        return 1
    return 99


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
        *,
        reference_grid: xr.DataArray | None = None,
    ) -> xr.Dataset:
        if reference_grid is not None:
            validate_reference_grid(reference_grid)

        subdirectories = self.config["subdirectories"]
        combined_directory = self.base_path / str(subdirectories["combined_classes"])
        combined_raster = self._select_combined_raster(combined_directory, bbox=bbox)
        combined_source = open_single_band_raster(combined_raster, bbox=bbox)
        combined_valid_count = int(combined_source.count().item())
        combined = (
            combined_source.where(lambda array: array != 255)
            .rename("combined_classes")
            .to_dataset()
        )

        area_ha = self._stack_area_rasters(
            self.base_path / str(subdirectories["area_by_class_ha"]),
            "area_by_class_ha",
            float(self.config.get("scale_factor", {}).get("ha", 1.0)),
            bbox=bbox,
        )
        area_pct = self._stack_area_rasters(
            self.base_path / str(subdirectories["area_by_class_pct"]),
            "area_by_class_pct",
            float(self.config.get("scale_factor", {}).get("pct", 1.0)),
            bbox=bbox,
        )

        dataset = xr.merge([combined, area_ha, area_pct], join="outer", compat="override")
        dataset.attrs.update(
            {
                "glwd_combined_raster": str(combined_raster),
                "glwd_combined_valid_count": combined_valid_count,
            }
        )
        if bbox is not None:
            dataset.attrs["glwd_requested_bbox"] = list(bbox)
        if reference_grid is not None:
            dataset = reproject_dataset_to_grid(
                dataset, reference_grid, resampling=Resampling.nearest,
            )
        return self.finalize_dataset(
            dataset, bbox=bbox, time_range=time_range, reference_grid=reference_grid,
        )

    def _stack_area_rasters(
        self,
        directory: Path,
        variable_name: str,
        scale_factor: float,
        *,
        bbox: BBox | None,
    ) -> xr.Dataset:
        members = sorted(directory.glob("*.tif"))
        if not members:
            raise FileNotFoundError(f"No GLWD rasters found in {directory}")

        arrays = []
        class_ids = []
        for path in members:
            arrays.append(open_single_band_raster(path, bbox=bbox))
            class_ids.append(_parse_glwd_class_id(path.stem))

        stacked = xr.concat(arrays, dim=pd.Index(class_ids, name="glwd_class")) * scale_factor
        return stacked.rename(variable_name).to_dataset()

    @staticmethod
    def _first_raster(directory: Path) -> Path:
        matches = sorted(directory.glob("*.tif"))
        if not matches:
            raise FileNotFoundError(f"No GLWD combined-class raster found in {directory}")
        return matches[0]

    def _select_combined_raster(self, directory: Path, *, bbox: BBox | None) -> Path:
        """Select the most usable combined-class raster for the requested bbox."""

        matches = sorted(directory.glob("*.tif"))
        if not matches:
            raise FileNotFoundError(f"No GLWD combined-class raster found in {directory}")

        candidates = sorted(
            (path for path in matches if _combined_raster_priority(path) < 99),
            key=lambda path: (_combined_raster_priority(path), path.name),
        )
        if not candidates:
            raise FileNotFoundError(
                "No GLWD combined-class raster matching 'main_class' was found in "
                f"{directory}"
            )
        if bbox is None:
            return candidates[0]

        grouped_candidates: dict[int, list[Path]] = {}
        for path in candidates:
            grouped_candidates.setdefault(_combined_raster_priority(path), []).append(path)

        for priority in sorted(grouped_candidates):
            best_path: Path | None = None
            best_valid_count = -1
            for path in grouped_candidates[priority]:
                raster = open_single_band_raster(path, bbox=bbox).where(lambda array: array != 255)
                valid_count = int(raster.count().item())
                if valid_count > best_valid_count:
                    best_path = path
                    best_valid_count = valid_count
            if best_path is not None and best_valid_count > 0:
                return best_path

        return candidates[0]
