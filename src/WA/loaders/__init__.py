"""Loader registry exports."""

from WA.loaders import (
    berkeley,
    g2017,
    glwd,
    gwd30,
    netcdf_generic,
    standardized_netcdf,
    swamps,
    topmodel,
)
from WA.loaders.registry import (
    UnsupportedDatasetError,
    get_loader,
    list_loader_types,
    register_loader,
)

__all__ = [
    "UnsupportedDatasetError",
    "get_loader",
    "list_loader_types",
    "register_loader",
    "berkeley",
    "g2017",
    "glwd",
    "gwd30",
    "netcdf_generic",
    "standardized_netcdf",
    "swamps",
    "topmodel",
]
