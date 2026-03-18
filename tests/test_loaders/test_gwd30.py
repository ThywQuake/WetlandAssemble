from __future__ import annotations

from pathlib import Path

import numpy as np
from rasterio.transform import from_origin

from tests.test_loaders.conftest import with_common_fields, write_multiband_geotiff
from WA.loaders import get_loader


def test_gwd30_loader_filters_tiles_and_reconstructs_four_day_timestamps(tmp_path: Path) -> None:
    base_path = tmp_path / "gwd30"
    band_count = 92
    tile_a = np.ones((band_count, 2, 2), dtype=np.uint8)
    tile_b = np.full((band_count, 2, 2), 2, dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_a_wetland_2013.tif",
        tile_a,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )
    write_multiband_geotiff(
        base_path / "2013/tile_b_wetland_2013.tif",
        tile_b,
        transform=from_origin(2.0, 2.0, 1.0, 1.0),
    )

    loader = get_loader(
        "gwd30",
        with_common_fields(
            base_path,
            loader_type="gwd30",
            years=[2013],
            pattern="{year}/*_wetland_{year}.tif",
        ),
    )

    result = loader.load(bbox=(0.0, 0.0, 1.9, 2.0), time_range=("2013-01-01", "2013-01-31"))

    assert list(result.data_vars) == ["wetland_class"]
    assert result.sizes["time"] == 8
    assert result["wetland_class"].max().item() == 1
    assert str(result.time.values[1])[:10] == "2013-01-05"
