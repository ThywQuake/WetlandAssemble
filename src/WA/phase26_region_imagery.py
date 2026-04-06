"""Phase 2.6 regional satellite quicklook download helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pandas as pd

from WA.loaders.base import BBox
from WA.validation._download_utils import (
    classify_failure,
    collection_size,
    format_date,
)
from WA.validation._download_utils import (
    download_file as _download_file_impl,
)
from WA.validation.gee_client import EarthEngineClient, GeeInitializationError
from WA.validation.modis_reference import (
    MODIS_AVAILABLE_FROM,
    MODIS_COLLECTION_ID,
    MODIS_QA_BANDS,
    MODIS_RGB_BANDS,
    _apply_modis_cloud_mask,
)

DEFAULT_PHASE26_REGION_IMAGERY_DIR = Path("results/phase2.6_region_imagery")
DEFAULT_PHASE26_REGION_IMAGERY_YEAR = 2016
DEFAULT_PHASE26_REGION_IMAGERY_DIMENSIONS = 1536

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Phase26RegionQuicklookArtifact:
    """Materialized or planned MODIS quicklook for one Phase 2.6 region."""

    region_id: str
    target_year: int
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    quicklook_path: Path
    status: str
    collection_id: str = MODIS_COLLECTION_ID
    message: str | None = None


def resolve_phase26_region_window(target_year: int) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Return the annual composite window used for one regional satellite quicklook."""

    window_start = pd.Timestamp(year=target_year, month=1, day=1)
    if window_start < MODIS_AVAILABLE_FROM:
        return None
    return window_start, pd.Timestamp(year=target_year + 1, month=1, day=1)


def phase26_region_quicklook_path(
    output_dir: Path,
    *,
    region_id: str,
    target_year: int,
) -> Path:
    """Return the canonical local path for one region quicklook JPG."""

    return output_dir / str(target_year) / region_id / f"{region_id}_modis_rgb.jpg"


def find_phase26_region_quicklook(
    output_dir: Path,
    *,
    region_id: str,
    target_year: int,
) -> Path | None:
    """Resolve one previously downloaded region quicklook if it exists."""

    path = phase26_region_quicklook_path(
        output_dir,
        region_id=region_id,
        target_year=target_year,
    )
    return path if path.is_file() else None


def download_phase26_region_quicklook(
    region_id: str,
    bbox: BBox,
    gee_client: EarthEngineClient,
    *,
    output_dir: str | Path = DEFAULT_PHASE26_REGION_IMAGERY_DIR,
    target_year: int = DEFAULT_PHASE26_REGION_IMAGERY_YEAR,
    allow_interactive_auth: bool = False,
    download_file=None,
    skip_existing: bool = True,
    dimensions: int = DEFAULT_PHASE26_REGION_IMAGERY_DIMENSIONS,
) -> Phase26RegionQuicklookArtifact:
    """Download one annual MODIS RGB quicklook for a Phase 2.6 region bbox."""

    resolved_window = resolve_phase26_region_window(target_year)
    quicklook_path = phase26_region_quicklook_path(
        Path(output_dir),
        region_id=region_id,
        target_year=target_year,
    )

    if resolved_window is None:
        return Phase26RegionQuicklookArtifact(
            region_id=region_id,
            target_year=target_year,
            window_start=pd.Timestamp(year=target_year, month=1, day=1),
            window_end=pd.Timestamp(year=target_year, month=1, day=1),
            quicklook_path=quicklook_path,
            status="unsupported_time_window",
            message="Target year predates MODIS availability",
        )

    window_start, window_end = resolved_window

    if skip_existing and quicklook_path.exists():
        return Phase26RegionQuicklookArtifact(
            region_id=region_id,
            target_year=target_year,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            status="cached",
        )

    try:
        ee = gee_client.authenticate_and_initialize(
            allow_interactive_auth=allow_interactive_auth
        )
    except GeeInitializationError as exc:
        return Phase26RegionQuicklookArtifact(
            region_id=region_id,
            target_year=target_year,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            status="gee_auth_failed",
            message=str(exc),
        )

    geometry = gee_client.rectangle(bbox)
    collection = (
        ee.ImageCollection(MODIS_COLLECTION_ID)
        .filterBounds(geometry)
        .filterDate(format_date(window_start), format_date(window_end))
        .select(list(MODIS_QA_BANDS))
    )

    if collection_size(collection) == 0:
        return Phase26RegionQuicklookArtifact(
            region_id=region_id,
            target_year=target_year,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            status="empty_collection",
        )

    image = collection.map(_apply_modis_cloud_mask).median().clip(geometry)
    preview = image.visualize(bands=list(MODIS_RGB_BANDS), min=0, max=3000)
    fetch = download_file or _download_file_impl
    last_exc: Exception | None = None
    candidate_dimensions = _quicklook_dimension_candidates(int(dimensions))
    for candidate_dimension in candidate_dimensions:
        quicklook_url = preview.getThumbURL(
            {
                "region": geometry,
                "dimensions": candidate_dimension,
                "format": "jpg",
            }
        )
        try:
            fetch(quicklook_url, quicklook_path)
            if candidate_dimension != int(dimensions):
                logger.warning(
                    "region=%s quicklook dimensions fallback: requested=%s used=%s",
                    region_id,
                    int(dimensions),
                    candidate_dimension,
                )
            return Phase26RegionQuicklookArtifact(
                region_id=region_id,
                target_year=target_year,
                window_start=window_start,
                window_end=window_end,
                quicklook_path=quicklook_path,
                status="downloaded",
                message=(
                    None
                    if candidate_dimension == int(dimensions)
                    else f"quicklook_dimensions_used={candidate_dimension}"
                ),
            )
        except HTTPError as exc:
            last_exc = exc
            if exc.code == 400 and candidate_dimension != candidate_dimensions[-1]:
                logger.warning(
                    "region=%s quicklook 400 at dimensions=%s; retrying smaller size",
                    region_id,
                    candidate_dimension,
                )
                continue
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            break

    assert last_exc is not None
    return Phase26RegionQuicklookArtifact(
        region_id=region_id,
        target_year=target_year,
        window_start=window_start,
        window_end=window_end,
        quicklook_path=quicklook_path,
        status=classify_failure(last_exc),
        message=str(last_exc),
    )


def phase26_region_quicklook_manifest_record(
    artifact: Phase26RegionQuicklookArtifact,
    *,
    region_label: str,
    bbox: BBox,
    ) -> dict[str, Any]:
    """Build one JSON-safe manifest record for a region quicklook."""

    return {
        "region_id": artifact.region_id,
        "region_label": region_label,
        "bbox": list(bbox),
        "target_year": artifact.target_year,
        "window_start": artifact.window_start,
        "window_end": artifact.window_end,
        "quicklook_path": artifact.quicklook_path,
        "status": artifact.status,
        "collection_id": artifact.collection_id,
        "message": artifact.message,
    }


def _quicklook_dimension_candidates(initial_dimension: int) -> list[int]:
    """Return one descending list of quicklook dimensions to try."""

    fallback_dimensions = (1536, 1024, 768, 512, 384)
    candidates = [initial_dimension]
    candidates.extend(
        dimension
        for dimension in fallback_dimensions
        if dimension < initial_dimension and dimension not in candidates
    )
    return candidates
