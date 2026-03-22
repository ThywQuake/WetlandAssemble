"""Wetland Assemble package."""

from WA._geo_env import configure_geospatial_runtime
from WA.config import AppConfig, load_config, load_dataset_config, load_gee_config

configure_geospatial_runtime()

__all__ = [
    "AppConfig",
    "load_config",
    "load_dataset_config",
    "load_gee_config",
]
