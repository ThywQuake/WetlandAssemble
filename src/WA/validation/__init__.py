"""Validation helpers for GEE-backed truth imagery workflows."""

from WA.validation.gee_client import EarthEngineClient, GeeInitializationError
from WA.validation.landsat_reference import (
    LANDSAT_AVAILABLE_FROM,
    LANDSAT_COLLECTION_IDS,
    LandsatReferenceArtifact,
    download_landsat_reference,
    resolve_landsat_fusion_window,
)
from WA.validation.modis_reference import (
    MODIS_AVAILABLE_FROM,
    MODIS_COLLECTION_ID,
    ModisReferenceArtifact,
    download_modis_reference,
    resolve_modis_composite_window,
)
from WA.validation.s2_reference import (
    S2_AVAILABLE_FROM,
    S2_CLOUD_SCORE_ID,
    S2_CLOUD_THRESHOLD,
    S2_COLLECTION_ID,
    S2ReferenceArtifact,
    download_s2_reference,
)

__all__ = [
    "EarthEngineClient",
    "GeeInitializationError",
    "LANDSAT_AVAILABLE_FROM",
    "LANDSAT_COLLECTION_IDS",
    "LandsatReferenceArtifact",
    "download_landsat_reference",
    "resolve_landsat_fusion_window",
    "MODIS_AVAILABLE_FROM",
    "MODIS_COLLECTION_ID",
    "ModisReferenceArtifact",
    "download_modis_reference",
    "resolve_modis_composite_window",
    "S2_AVAILABLE_FROM",
    "S2_CLOUD_SCORE_ID",
    "S2_CLOUD_THRESHOLD",
    "S2_COLLECTION_ID",
    "S2ReferenceArtifact",
    "download_s2_reference",
]
