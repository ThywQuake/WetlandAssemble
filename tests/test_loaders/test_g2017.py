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


def test_g2017_loader_aligns_mismatched_grids(tmp_path: Path) -> None:
    """Rasters with slightly different pixel registrations should align without NaN explosion."""
    base_path = tmp_path / "g2017"

    # wetland: 4x4 at 0.5 deg resolution, origin (0, 2)
    ref_transform = from_origin(0.0, 2.0, 0.5, 0.5)
    wetland_data = np.arange(10, 170, 10, dtype=np.uint8).reshape(4, 4)
    write_single_band_geotiff(
        base_path / "wetland.tif",
        wetland_data,
        transform=ref_transform,
    )

    # wetland_nolake: same extent but slightly different origin (offset by 1e-7 deg)
    offset_transform = from_origin(1e-7, 2.0 + 1e-7, 0.5, 0.5)
    write_single_band_geotiff(
        base_path / "fwet05deg_nolake.tif",
        np.array([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]], dtype=np.uint8),
        transform=offset_transform,
    )

    # peatland: coarser grid (1.0 deg resolution, 2x2)
    coarse_transform = from_origin(0.0, 2.0, 1.0, 1.0)
    write_single_band_geotiff(
        base_path / "peatland.tif",
        np.array([[0, 1], [1, 0]], dtype=np.uint8),
        transform=coarse_transform,
    )

    loader = get_loader(
        "g2017",
        with_common_fields(
            base_path,
            loader_type="geotiff",
            files={
                "wetland": "wetland.tif",
                "wetland_nolake": "fwet05deg_nolake.tif",
                "peatland": "peatland.tif",
            },
        ),
    )

    result = loader.load()

    assert set(result.data_vars) == {"peatland", "wetland", "wetland_nolake"}
    # All variables should share the same coordinate grid (wetland's grid)
    assert result.sizes["lat"] == 4
    assert result.sizes["lon"] == 4
    # No NaN explosion — all variables should have data
    assert int(result["wetland"].count()) == 16
    assert int(result["wetland_nolake"].count()) > 0
    assert int(result["peatland"].count()) > 0
