"""Geospatial runtime guards for PROJ-dependent libraries."""

from __future__ import annotations

import os
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path


@lru_cache(maxsize=1)
def configure_geospatial_runtime() -> None:
    """Pin Rasterio and pyproj to the PROJ data shipped with this environment.

    HPC shells sometimes leak ``PROJ_DATA``/``PROJ_LIB`` from a different
    Conda installation. That breaks CRS lookups inside Rasterio even when the
    current virtualenv already ships a compatible ``proj.db``. Re-point both
    libraries at their own bundled data directories once per process.
    """

    proj_dir = _resolve_rasterio_proj_dir()
    if proj_dir is not None:
        os.environ["PROJ_DATA"] = str(proj_dir)
        os.environ["PROJ_LIB"] = str(proj_dir)

    _configure_pyproj_data(proj_dir)
    _configure_rasterio_proj_data(proj_dir)


def _resolve_rasterio_proj_dir() -> Path | None:
    spec = find_spec("rasterio")
    if spec is None or spec.origin is None:
        return None

    proj_dir = Path(spec.origin).resolve().parent / "proj_data"
    if (proj_dir / "proj.db").exists():
        return proj_dir
    return None


def _configure_rasterio_proj_data(proj_dir: Path | None) -> None:
    try:
        from rasterio.env import set_proj_data_search_path
    except ImportError:
        return

    if proj_dir is not None:
        set_proj_data_search_path(str(proj_dir))


def _configure_pyproj_data(proj_dir: Path | None) -> None:
    try:
        from pyproj import datadir
    except ImportError:
        return

    if proj_dir is not None:
        datadir.set_data_dir(str(proj_dir))
