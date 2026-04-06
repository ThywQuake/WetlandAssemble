from __future__ import annotations

import pytest

from WA.loaders import get_loader, list_loader_types
from WA.loaders.registry import UnsupportedDatasetError


def test_registry_exposes_expected_loader_types() -> None:
    assert list_loader_types() == (
        "berkeley",
        "geotiff",
        "glwd",
        "gwd30",
        "netcdf",
        "standardized_netcdf",
        "swamps",
        "topmodel",
    )


def test_registry_rejects_out_of_scope_dataset() -> None:
    with pytest.raises(UnsupportedDatasetError, match="out of scope"):
        get_loader("lstm_wetland", {"loader_type": "netcdf", "name": "LSTM", "path": "."})
