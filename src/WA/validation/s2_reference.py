"""Sentinel-2 Cloud Score+ reference-imagery downloads for entropy hotspot AOIs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from WA.comparison.hotspots import EntropyHotspot
from WA.validation._download_utils import (
    classify_failure,
    collection_size,
    download_file,
    format_date,
)
from WA.validation.gee_client import EarthEngineClient, GeeInitializationError

S2_COLLECTION_ID = "COPERNICUS/S2_SR_HARMONIZED"
S2_CLOUD_SCORE_ID = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
S2_AVAILABLE_FROM = pd.Timestamp("2017-03-28")
S2_CLOUD_THRESHOLD = 0.60
S2_RGB_BANDS = ("B4", "B3", "B2")
S2_SCALE_METERS = 10

DownloadFn = Callable[[str, Path], None]


@dataclass(frozen=True)
class S2ReferenceArtifact:
    """Materialized or planned Sentinel-2 output for one entropy hotspot AOI."""

    hotspot_id: str
    region_slug: str
    target_time: pd.Timestamp
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    quicklook_path: Path
    chip_path: Path
    status: str
    collection_id: str = S2_COLLECTION_ID
    cloud_threshold: float = S2_CLOUD_THRESHOLD
    download_mode: str = "synchronous"
    message: str | None = None


def download_s2_reference(
    hotspot: EntropyHotspot,
    gee_client: EarthEngineClient,
    *,
    target_time: str | pd.Timestamp = "2017-07-01",
    results_root: str | Path = "results",
    allow_interactive_auth: bool = False,
    download_file_fn: DownloadFn | None = None,
    skip_existing: bool = True,
    scale_meters: int = S2_SCALE_METERS,
) -> S2ReferenceArtifact:
    """Download cloud-masked Sentinel-2 composite for one entropy hotspot AOI."""

    timestamp = pd.Timestamp(target_time).normalize()
    # Use ±3 month window: tropical regions have sparse S2 coverage in a single month
    window_start = timestamp - pd.DateOffset(months=3)
    window_end = timestamp + pd.DateOffset(months=3)
    # Clamp to S2 availability
    if window_start < S2_AVAILABLE_FROM:
        window_start = S2_AVAILABLE_FROM
    quicklook_path, chip_path = _output_paths(
        hotspot,
        results_root=Path(results_root),
        window_start=window_start,
        window_end=window_end,
    )

    if window_end <= S2_AVAILABLE_FROM:
        return S2ReferenceArtifact(
            hotspot_id=hotspot.hotspot_id,
            region_slug=hotspot.region_slug,
            target_time=timestamp,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status="unsupported_time_window",
            message="Target time predates Sentinel-2 availability (2017-03-28)",
        )

    if skip_existing and quicklook_path.exists() and chip_path.exists():
        return S2ReferenceArtifact(
            hotspot_id=hotspot.hotspot_id,
            region_slug=hotspot.region_slug,
            target_time=timestamp,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status="cached",
        )

    try:
        ee = gee_client.authenticate_and_initialize(
            allow_interactive_auth=allow_interactive_auth
        )
    except GeeInitializationError as exc:
        return S2ReferenceArtifact(
            hotspot_id=hotspot.hotspot_id,
            region_slug=hotspot.region_slug,
            target_time=timestamp,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status="gee_auth_failed",
            message=str(exc),
        )

    geometry = gee_client.rectangle(hotspot.bbox)
    composite = _build_cloud_masked_composite(
        ee,
        geometry,
        window_start=window_start,
        window_end=window_end,
    )

    if composite is None:
        return S2ReferenceArtifact(
            hotspot_id=hotspot.hotspot_id,
            region_slug=hotspot.region_slug,
            target_time=timestamp,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status="empty_collection",
        )

    preview = composite.visualize(bands=list(S2_RGB_BANDS), min=0, max=3000)
    chip_url = composite.getDownloadURL(
        {
            "region": geometry,
            "scale": scale_meters,
            "crs": "EPSG:4326",
            "format": "GEO_TIFF",
        }
    )
    quicklook_url = preview.getThumbURL(
        {
            "region": geometry,
            "dimensions": 768,
            "format": "jpg",
        }
    )

    fetch = download_file_fn or download_file
    try:
        fetch(chip_url, chip_path)
        fetch(quicklook_url, quicklook_path)
    except Exception as exc:
        return S2ReferenceArtifact(
            hotspot_id=hotspot.hotspot_id,
            region_slug=hotspot.region_slug,
            target_time=timestamp,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status=classify_failure(exc),
            message=str(exc),
        )

    return S2ReferenceArtifact(
        hotspot_id=hotspot.hotspot_id,
        region_slug=hotspot.region_slug,
        target_time=timestamp,
        window_start=window_start,
        window_end=window_end,
        quicklook_path=quicklook_path,
        chip_path=chip_path,
        status="downloaded",
    )


def _build_cloud_masked_composite(
    ee: Any,
    geometry: Any,
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> Any | None:
    """Build a cloud-masked median composite using Cloud Score+.

    1. Load S2_SR_HARMONIZED filtered by geometry + date
    2. Load CLOUD_SCORE_PLUS linked by system:index
    3. Join with ee.Join.saveFirst('cloud_score')
    4. Map: mask pixels where cs_cdf < S2_CLOUD_THRESHOLD
    5. Return median composite over masked collection, or None if empty
    """
    start_str = format_date(window_start)
    end_str = format_date(window_end)

    s2_col = (
        ee.ImageCollection(S2_COLLECTION_ID)
        .filterBounds(geometry)
        .filterDate(start_str, end_str)
    )

    if collection_size(s2_col) == 0:
        return None

    cs_col = ee.ImageCollection(S2_CLOUD_SCORE_ID).filterDate(start_str, end_str)

    joined = ee.Join.saveFirst("cloud_score").apply(
        primary=s2_col,
        secondary=cs_col,
        condition=ee.Filter.equals(leftField="system:index", rightField="system:index"),
    )

    def _apply_cloud_mask(image: Any) -> Any:
        cs_image = ee.Image(image.get("cloud_score"))
        mask = cs_image.select("cs_cdf").gte(S2_CLOUD_THRESHOLD)
        return image.select(list(S2_RGB_BANDS)).updateMask(mask)

    masked = ee.ImageCollection(joined).map(_apply_cloud_mask)
    return masked.median().clip(geometry)


def _output_paths(
    hotspot: EntropyHotspot,
    *,
    results_root: Path,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> tuple[Path, Path]:
    window_slug = f"{window_start:%Y%m%d}_{window_end:%Y%m%d}"
    quicklook_dir = results_root / "fine_truth" / hotspot.region_slug / window_slug
    chip_dir = results_root / "fine_truth" / hotspot.region_slug / window_slug
    quicklook_path = quicklook_dir / f"{hotspot.hotspot_id}_s2_rgb.jpg"
    chip_path = chip_dir / f"{hotspot.hotspot_id}_s2_chip.tif"
    return quicklook_path, chip_path
