from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from rasterio.transform import from_origin

from tests.test_loaders.conftest import with_common_fields, write_single_band_geotiff
from WA.loaders import get_loader


def test_glwd_loader_stacks_area_products_and_applies_scale_factor(tmp_path: Path) -> None:
    base_path = tmp_path / "glwd"
    transform = from_origin(0.0, 2.0, 1.0, 1.0)
    write_single_band_geotiff(
        base_path / "combined_classes/combined.tif",
        np.array([[8, 9]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_ha/class01.tif",
        np.array([[1, 1]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_ha/class02.tif",
        np.array([[2, 2]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_pct/class01.tif",
        np.array([[5, 5]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "area_by_class_pct/class02.tif",
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
    assert list(result["area_by_class_ha"]["glwd_class"].values) == [1, 2]
    assert result["area_by_class_ha"].isel(glwd_class=0, lat=0, lon=0).item() == pytest.approx(0.1)
