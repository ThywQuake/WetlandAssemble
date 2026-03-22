from __future__ import annotations

import os
from pathlib import Path

import rasterio
from pytest import MonkeyPatch
from rasterio.crs import CRS

from WA._geo_env import configure_geospatial_runtime


def test_package_import_repairs_invalid_proj_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("PROJ_DATA", "/tmp/wa-invalid-proj-data")
    monkeypatch.setenv("PROJ_LIB", "/tmp/wa-invalid-proj-data")

    configure_geospatial_runtime.cache_clear()
    configure_geospatial_runtime()

    assert rasterio.__file__ is not None
    proj_dir = Path(rasterio.__file__).resolve().parent / "proj_data"
    assert Path(os.environ["PROJ_DATA"]).resolve() == proj_dir.resolve()
    assert Path(os.environ["PROJ_LIB"]).resolve() == proj_dir.resolve()
    assert CRS.from_epsg(4326).to_string() == "EPSG:4326"
