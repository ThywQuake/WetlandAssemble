"""MODIS reference-imagery downloads for rough comparison AOIs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from WA.comparison.focus_areas import RoughFocusArea
from WA.validation._download_utils import (
    classify_failure,
    collection_size,
    format_date,
    month_window,
)
from WA.validation._download_utils import (
    download_file as _download_file_impl,
)
from WA.validation.gee_client import EarthEngineClient, GeeInitializationError

MODIS_COLLECTION_ID = "MODIS/061/MOD09A1"
MODIS_AVAILABLE_FROM = pd.Timestamp("2000-02-18")
MODIS_RGB_BANDS = ("sur_refl_b01", "sur_refl_b04", "sur_refl_b03")
MODIS_QA_BANDS = MODIS_RGB_BANDS + ("QA", "StateQA")
MODIS_FUSION_PADDING_MONTHS = 2

DownloadFn = Callable[[str, Path], None]


@dataclass(frozen=True)
class ModisReferenceArtifact:
    """Materialized or planned MODIS output for one rough-scale AOI."""

    aoi_id: str
    region_slug: str
    target_time: pd.Timestamp
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    quicklook_path: Path
    chip_path: Path
    status: str
    collection_id: str = MODIS_COLLECTION_ID
    download_mode: str = "synchronous"
    message: str | None = None


def resolve_modis_composite_window(
    target_time: str | pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Resolve the canonical 8-day MODIS composite window containing target_time."""

    timestamp = pd.Timestamp(target_time).normalize()
    if timestamp < MODIS_AVAILABLE_FROM:
        return None

    year_start = pd.Timestamp(year=timestamp.year, month=1, day=1)
    bucket_index = (timestamp - year_start).days // 8
    window_start = year_start + pd.Timedelta(days=8 * bucket_index)
    if window_start < MODIS_AVAILABLE_FROM:
        window_start = MODIS_AVAILABLE_FROM
    window_end = window_start + pd.Timedelta(days=8)
    return window_start, window_end


def resolve_modis_fusion_window(
    target_time: str | pd.Timestamp,
    *,
    padding_months: int = MODIS_FUSION_PADDING_MONTHS,
) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Resolve a multi-composite fusion window around the target month."""

    canonical_window = resolve_modis_composite_window(target_time)
    if canonical_window is None:
        return None

    month_start, month_end = month_window(pd.Timestamp(target_time))
    window_start = max(
        MODIS_AVAILABLE_FROM,
        month_start - pd.DateOffset(months=padding_months),
    )
    window_end = month_end + pd.DateOffset(months=padding_months)
    return pd.Timestamp(window_start), pd.Timestamp(window_end)


def download_modis_reference(
    aoi: RoughFocusArea,
    gee_client: EarthEngineClient,
    *,
    results_root: str | Path = "results",
    allow_interactive_auth: bool = False,
    download_file: DownloadFn | None = None,
    skip_existing: bool = True,
    scale_meters: int = 500,
) -> ModisReferenceArtifact:
    """Download cloud-masked, multi-temporal MODIS rough-truth artifacts for one AOI."""

    fallback_window = month_window(aoi.target_time)
    fusion_window = resolve_modis_fusion_window(aoi.target_time)
    window_start, window_end = fusion_window or fallback_window
    quicklook_path, chip_path = _output_paths(
        aoi,
        results_root=Path(results_root),
        window_start=window_start,
        window_end=window_end,
    )

    if fusion_window is None:
        return ModisReferenceArtifact(
            aoi_id=aoi.aoi_id,
            region_slug=aoi.region_slug,
            target_time=aoi.target_time,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status="unsupported_time_window",
            message="Target AOI predates MODIS availability",
        )

    if skip_existing and quicklook_path.exists() and chip_path.exists():
        return ModisReferenceArtifact(
            aoi_id=aoi.aoi_id,
            region_slug=aoi.region_slug,
            target_time=aoi.target_time,
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
        return ModisReferenceArtifact(
            aoi_id=aoi.aoi_id,
            region_slug=aoi.region_slug,
            target_time=aoi.target_time,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status="gee_auth_failed",
            message=str(exc),
        )

    geometry = gee_client.rectangle(aoi.bbox)
    collection = (
        ee.ImageCollection(MODIS_COLLECTION_ID)
        .filterBounds(geometry)
        .filterDate(format_date(window_start), format_date(window_end))
        .select(list(MODIS_QA_BANDS))
    )

    if collection_size(collection) == 0:
        return ModisReferenceArtifact(
            aoi_id=aoi.aoi_id,
            region_slug=aoi.region_slug,
            target_time=aoi.target_time,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status="empty_collection",
        )

    image = collection.map(_apply_modis_cloud_mask).median().clip(geometry)
    preview = image.visualize(bands=list(MODIS_RGB_BANDS), min=0, max=3000)
    chip_url = image.getDownloadURL(
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

    fetch = download_file or _download_file_impl
    try:
        fetch(chip_url, chip_path)
        fetch(quicklook_url, quicklook_path)
    except Exception as exc:
        return ModisReferenceArtifact(
            aoi_id=aoi.aoi_id,
            region_slug=aoi.region_slug,
            target_time=aoi.target_time,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status=classify_failure(exc),
            message=str(exc),
        )

    return ModisReferenceArtifact(
        aoi_id=aoi.aoi_id,
        region_slug=aoi.region_slug,
        target_time=aoi.target_time,
        window_start=window_start,
        window_end=window_end,
        quicklook_path=quicklook_path,
        chip_path=chip_path,
        status="downloaded",
    )


def _apply_modis_cloud_mask(image: Any) -> Any:
    """Mask cloudy / shadowed / snowy pixels before multi-temporal fusion."""

    qa = image.select("QA")
    state_qa = image.select("StateQA")

    # Keep only highest-quality MODLAND pixels.
    modland_quality_ok = qa.bitwiseAnd(0b11).eq(0)

    cloud_state = state_qa.bitwiseAnd(0b11)
    cloud_state_ok = cloud_state.eq(0)
    cloud_shadow_ok = state_qa.rightShift(2).bitwiseAnd(0b1).eq(0)
    aerosol_ok = state_qa.rightShift(6).bitwiseAnd(0b11).lte(1)
    cirrus_ok = state_qa.rightShift(8).bitwiseAnd(0b11).eq(0)
    internal_cloud_ok = state_qa.rightShift(10).bitwiseAnd(0b1).eq(0)
    snow_ice_ok = state_qa.rightShift(12).bitwiseAnd(0b1).eq(0)
    adjacent_cloud_ok = state_qa.rightShift(13).bitwiseAnd(0b1).eq(0)
    internal_snow_ok = state_qa.rightShift(15).bitwiseAnd(0b1).eq(0)

    mask = (
        modland_quality_ok.And(cloud_state_ok)
        .And(cloud_shadow_ok)
        .And(aerosol_ok)
        .And(cirrus_ok)
        .And(internal_cloud_ok)
        .And(snow_ice_ok)
        .And(adjacent_cloud_ok)
        .And(internal_snow_ok)
    )

    return image.select(list(MODIS_RGB_BANDS)).updateMask(mask)


def _output_paths(
    aoi: RoughFocusArea,
    *,
    results_root: Path,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> tuple[Path, Path]:
    window_slug = f"{window_start:%Y%m%d}_{window_end:%Y%m%d}"
    quicklook_dir = results_root / "quicklooks" / aoi.region_slug / window_slug
    chip_dir = results_root / "rough_truth" / aoi.region_slug / window_slug
    quicklook_path = quicklook_dir / f"{aoi.aoi_id}_modis_rgb.jpg"
    chip_path = chip_dir / f"{aoi.aoi_id}_modis_chip.tif"
    return quicklook_path, chip_path
