from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from rasterio.transform import from_origin

from tests.test_loaders.conftest import with_common_fields, write_single_band_geotiff
from WA.loaders import get_loader
from WA.loaders.glwd import _combined_raster_priority, _parse_glwd_class_id


def test_parse_glwd_class_id_extracts_correct_id() -> None:
    assert _parse_glwd_class_id("GLWD_v2_0_class_00_ha_x10") == 0
    assert _parse_glwd_class_id("GLWD_v2_0_class_01_pct") == 1
    assert _parse_glwd_class_id("GLWD_v2_0_class_33_pct") == 33

    with pytest.raises(ValueError, match="Cannot extract GLWD class ID"):
        _parse_glwd_class_id("no_class_here")


def test_combined_raster_priority_prefers_main_class() -> None:
    assert _combined_raster_priority(Path("GLWD_v2_0_main_class.tif")) == 0
    assert _combined_raster_priority(Path("GLWD_v2_0_main_class_50pct.tif")) == 1
    assert _combined_raster_priority(Path("GLWD_v2_0_area_ha_x10.tif")) == 99


def test_glwd_loader_stacks_area_products_and_applies_scale_factor(tmp_path: Path) -> None:
    base_path = tmp_path / "glwd"
    transform = from_origin(0.0, 2.0, 1.0, 1.0)
    write_single_band_geotiff(
        base_path / "combined_classes/GLWD_v2_0_main_class.tif",
        np.array([[8, 9]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_ha/GLWD_v2_0_class_00_ha_x10.tif",
        np.array([[1, 1]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_ha/GLWD_v2_0_class_01_ha_x10.tif",
        np.array([[2, 2]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_pct/GLWD_v2_0_class_00_pct.tif",
        np.array([[5, 5]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_pct/GLWD_v2_0_class_01_pct.tif",
        np.array([[6, 6]], dtype=np.uint8),
        transform=transform,
    )

    loader = get_loader(
        "glwd_v2",
        with_common_fields(
            base_path,
            loader_type="glwd",
            subdirectories={
                "combined_classes": "combined_classes",
                "area_by_class_ha": "area_by_class_ha",
                "area_by_class_pct": "area_by_class_pct",
            },
            scale_factor={"ha": 0.1, "pct": 1.0},
        ),
    )

    result = loader.load()

    assert "combined_classes" in result
    assert list(result["area_by_class_ha"]["glwd_class"].values) == [0, 1]
    assert result["area_by_class_ha"].isel(glwd_class=0, lat=0, lon=0).item() == pytest.approx(0.1)


def test_glwd_loader_prefers_combined_raster_with_valid_bbox_data(tmp_path: Path) -> None:
    base_path = tmp_path / "glwd"
    transform = from_origin(0.0, 2.0, 1.0, 1.0)
    write_single_band_geotiff(
        base_path / "combined_classes/GLWD_v2_0_main_class.tif",
        np.array([[255, 255], [255, 255]], dtype=np.uint8),
        transform=transform,
        nodata=255,
    )
    write_single_band_geotiff(
        base_path / "combined_classes/GLWD_v2_0_main_class_50pct.tif",
        np.array([[8, 9], [8, 9]], dtype=np.uint8),
        transform=transform,
        nodata=255,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_ha/GLWD_v2_0_class_00_ha_x10.tif",
        np.array([[1, 1], [1, 1]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_pct/GLWD_v2_0_class_00_pct.tif",
        np.array([[5, 5], [5, 5]], dtype=np.uint8),
        transform=transform,
    )

    loader = get_loader(
        "glwd_v2",
        with_common_fields(
            base_path,
            loader_type="glwd",
            subdirectories={
                "combined_classes": "combined_classes",
                "area_by_class_ha": "area_by_class_ha",
                "area_by_class_pct": "area_by_class_pct",
            },
            scale_factor={"ha": 0.1, "pct": 1.0},
        ),
    )

    result = loader.load(bbox=(0.0, 0.0, 2.0, 2.0))

    np.testing.assert_array_equal(
        result["combined_classes"].values,
        np.array([[8.0, 9.0], [8.0, 9.0]], dtype=np.float32),
    )
    assert result.attrs["glwd_combined_raster"].endswith("GLWD_v2_0_main_class_50pct.tif")
    assert result.attrs["glwd_combined_valid_count"] == 4


def test_glwd_loader_records_empty_combined_selection_diagnostics(tmp_path: Path) -> None:
    base_path = tmp_path / "glwd"
    transform = from_origin(0.0, 2.0, 1.0, 1.0)
    write_single_band_geotiff(
        base_path / "combined_classes/GLWD_v2_0_main_class.tif",
        np.array([[255, 255], [255, 255]], dtype=np.uint8),
        transform=transform,
        nodata=255,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_ha/GLWD_v2_0_class_00_ha_x10.tif",
        np.array([[1, 1], [1, 1]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_pct/GLWD_v2_0_class_00_pct.tif",
        np.array([[5, 5], [5, 5]], dtype=np.uint8),
        transform=transform,
    )

    loader = get_loader(
        "glwd_v2",
        with_common_fields(
            base_path,
            loader_type="glwd",
            subdirectories={
                "combined_classes": "combined_classes",
                "area_by_class_ha": "area_by_class_ha",
                "area_by_class_pct": "area_by_class_pct",
            },
            scale_factor={"ha": 0.1, "pct": 1.0},
        ),
    )

    result = loader.load(bbox=(0.0, 0.0, 2.0, 2.0))

    assert result.attrs["glwd_combined_raster"].endswith("GLWD_v2_0_main_class.tif")
    assert result.attrs["glwd_combined_valid_count"] == 0


def test_glwd_loader_ignores_area_products_in_combined_directory(tmp_path: Path) -> None:
    base_path = tmp_path / "glwd"
    transform = from_origin(0.0, 2.0, 1.0, 1.0)
    write_single_band_geotiff(
        base_path / "combined_classes/GLWD_v2_0_area_ha_x10.tif",
        np.array([[10, 10], [10, 10]], dtype=np.uint8),
        transform=transform,
        nodata=255,
    )
    write_single_band_geotiff(
        base_path / "combined_classes/GLWD_v2_0_area_pct.tif",
        np.array([[20, 20], [20, 20]], dtype=np.uint8),
        transform=transform,
        nodata=255,
    )
    write_single_band_geotiff(
        base_path / "combined_classes/GLWD_v2_0_main_class.tif",
        np.array([[8, 9], [8, 9]], dtype=np.uint8),
        transform=transform,
        nodata=255,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_ha/GLWD_v2_0_class_00_ha_x10.tif",
        np.array([[1, 1], [1, 1]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_pct/GLWD_v2_0_class_00_pct.tif",
        np.array([[5, 5], [5, 5]], dtype=np.uint8),
        transform=transform,
    )

    loader = get_loader(
        "glwd_v2",
        with_common_fields(
            base_path,
            loader_type="glwd",
            subdirectories={
                "combined_classes": "combined_classes",
                "area_by_class_ha": "area_by_class_ha",
                "area_by_class_pct": "area_by_class_pct",
            },
            scale_factor={"ha": 0.1, "pct": 1.0},
        ),
    )

    result = loader.load(bbox=(0.0, 0.0, 2.0, 2.0))

    assert result.attrs["glwd_combined_raster"].endswith("GLWD_v2_0_main_class.tif")
    np.testing.assert_array_equal(
        result["combined_classes"].values,
        np.array([[8.0, 9.0], [8.0, 9.0]], dtype=np.float32),
    )
