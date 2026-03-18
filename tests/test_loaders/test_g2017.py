from __future__ import annotations

from pathlib import Path

import numpy as np
from rasterio.transform import from_origin

from tests.test_loaders.conftest import with_common_fields, write_single_band_geotiff
from WA.loaders import get_loader


def test_g2017_loader_reads_bundle_members(tmp_path: Path) -> None:
    base_path = tmp_path / "g2017"
    transform = from_origin(0.0, 2.0, 1.0, 1.0)
    write_single_band_geotiff(
        base_path / "wetland/wetland.tif",
        np.array([[10, 20]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "wetland/fwet05deg_nolake.tif",
        np.array([[1, 1]], dtype=np.uint8),
        transform=transform,
    )
    write_single_band_geotiff(
        base_path / "peatland/peatland.tif",
        np.array([[0, 1]], dtype=np.uint8),
        transform=transform,
    )

    loader = get_loader(
        "g2017",
        with_common_fields(
            base_path,
            loader_type="geotiff",
            files={
                "wetland": "wetland/wetland.tif",
                "wetland_nolake": "wetland/fwet05deg_nolake.tif",
                "peatland": "peatland/peatland.tif",
            },
        ),
    )

    result = loader.load()

    assert set(result.data_vars) == {"peatland", "wetland", "wetland_nolake"}
    assert "lat" in result.coords
    assert "lon" in result.coords
