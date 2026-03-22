"""Landsat reference-imagery downloads for rough comparison AOIs."""

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

LANDSAT_COLLECTION_IDS = (
    "LANDSAT/LT05/C02/T1_L2",
    "LANDSAT/LE07/C02/T1_L2",
    "LANDSAT/LC08/C02/T1_L2",
    "LANDSAT/LC09/C02/T1_L2",
)
LANDSAT_AVAILABLE_FROM = pd.Timestamp("1984-03-16")
LANDSAT_FUSION_PADDING_MONTHS = 2
LANDSAT_PREVIEW_BANDS = ("red", "green", "blue")

DownloadFn = Callable[[str, Path], None]


@dataclass(frozen=True)
class LandsatReferenceArtifact:
    """Materialized or planned Landsat output for one rough-scale AOI."""

    aoi_id: str
    region_slug: str
    target_time: pd.Timestamp
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    quicklook_path: Path
    chip_path: Path
    status: str
    collection_ids: tuple[str, ...] = LANDSAT_COLLECTION_IDS
    download_mode: str = "synchronous"
    message: str | None = None


def resolve_landsat_fusion_window(
    target_time: str | pd.Timestamp,
    *,
    padding_months: int = LANDSAT_FUSION_PADDING_MONTHS,
) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Resolve the Landsat fusion window around a target month."""

    timestamp = pd.Timestamp(target_time).normalize()
    if timestamp < LANDSAT_AVAILABLE_FROM:
        return None

    month_start = timestamp.replace(day=1)
    month_end = month_start + pd.offsets.MonthBegin(1)
    window_start = max(
        LANDSAT_AVAILABLE_FROM,
        month_start - pd.DateOffset(months=padding_months),
    )
    window_end = month_end + pd.DateOffset(months=padding_months)
    return pd.Timestamp(window_start), pd.Timestamp(window_end)


def download_landsat_reference(
    aoi: RoughFocusArea,
    gee_client: EarthEngineClient,
    *,
    results_root: str | Path = "results",
    allow_interactive_auth: bool = False,
    download_file: DownloadFn | None = None,
    skip_existing: bool = True,
    scale_meters: int = 250,
) -> LandsatReferenceArtifact:
    """Download cloud-masked, multi-sensor Landsat rough-truth artifacts for one AOI."""

    fallback_window = month_window(aoi.target_time)
    fusion_window = resolve_landsat_fusion_window(aoi.target_time)
    window_start, window_end = fusion_window or fallback_window
    quicklook_path, chip_path = _output_paths(
        aoi,
        results_root=Path(results_root),
        window_start=window_start,
        window_end=window_end,
    )

    if fusion_window is None:
        return LandsatReferenceArtifact(
            aoi_id=aoi.aoi_id,
            region_slug=aoi.region_slug,
            target_time=aoi.target_time,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status="unsupported_time_window",
            message="Target AOI predates Landsat Collection 2 Level 2 availability",
        )

    if skip_existing and quicklook_path.exists() and chip_path.exists():
        return LandsatReferenceArtifact(
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
        return LandsatReferenceArtifact(
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
    collection = _build_landsat_collection(
        ee,
        geometry=geometry,
        window_start=window_start,
        window_end=window_end,
    )
    if collection_size(collection) == 0:
        return LandsatReferenceArtifact(
            aoi_id=aoi.aoi_id,
            region_slug=aoi.region_slug,
            target_time=aoi.target_time,
            window_start=window_start,
            window_end=window_end,
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status="empty_collection",
        )

    image = collection.median().clip(geometry)
    preview = image.visualize(
        bands=list(LANDSAT_PREVIEW_BANDS),
        min=0.02,
        max=0.3,
        gamma=1.1,
    )
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
            "dimensions": 1024,
            "format": "jpg",
        }
    )

    fetch = download_file or _download_file_impl
    try:
        fetch(chip_url, chip_path)
        fetch(quicklook_url, quicklook_path)
    except Exception as exc:
        return LandsatReferenceArtifact(
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

    return LandsatReferenceArtifact(
        aoi_id=aoi.aoi_id,
        region_slug=aoi.region_slug,
        target_time=aoi.target_time,
        window_start=window_start,
        window_end=window_end,
        quicklook_path=quicklook_path,
        chip_path=chip_path,
        status="downloaded",
    )


def _build_landsat_collection(
    ee: Any,
    *,
    geometry: Any,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> Any:
    preprocessors = {
        "LANDSAT/LT05/C02/T1_L2": _prepare_landsat_tm_image,
        "LANDSAT/LE07/C02/T1_L2": _prepare_landsat_tm_image,
        "LANDSAT/LC08/C02/T1_L2": _prepare_landsat_oli_image,
        "LANDSAT/LC09/C02/T1_L2": _prepare_landsat_oli_image,
    }
    collections = [
        ee.ImageCollection(collection_id)
        .filterBounds(geometry)
        .filterDate(format_date(window_start), format_date(window_end))
        .map(preprocessors[collection_id])
        for collection_id in LANDSAT_COLLECTION_IDS
    ]
    merged = collections[0]
    for collection in collections[1:]:
        merged = merged.merge(collection)
    return merged


def _prepare_landsat_tm_image(image: Any) -> Any:
    """Prepare Landsat 5/7 TM/ETM+ imagery for RGB compositing."""

    return _prepare_landsat_image(
        image,
        source_bands=("SR_B3", "SR_B2", "SR_B1"),
    )


def _prepare_landsat_oli_image(image: Any) -> Any:
    """Prepare Landsat 8/9 OLI imagery for RGB compositing."""

    return _prepare_landsat_image(
        image,
        source_bands=("SR_B4", "SR_B3", "SR_B2"),
    )


def _prepare_landsat_image(
    image: Any,
    *,
    source_bands: tuple[str, str, str],
) -> Any:
    """Scale Landsat SR bands, harmonize RGB names, and apply cloud mask."""

    qa_pixel = image.select("QA_PIXEL")
    qa_radsat = image.select("QA_RADSAT")

    fill_ok = qa_pixel.bitwiseAnd(1 << 0).eq(0)
    dilated_cloud_ok = qa_pixel.bitwiseAnd(1 << 1).eq(0)
    cirrus_ok = qa_pixel.bitwiseAnd(1 << 2).eq(0)
    cloud_ok = qa_pixel.bitwiseAnd(1 << 3).eq(0)
    shadow_ok = qa_pixel.bitwiseAnd(1 << 4).eq(0)
    snow_ok = qa_pixel.bitwiseAnd(1 << 5).eq(0)
    saturation_ok = qa_radsat.eq(0)

    optical = image.select("SR_B.*").multiply(0.0000275).add(-0.2)
    rgb = optical.select(list(source_bands), list(LANDSAT_PREVIEW_BANDS))

    mask = (
        fill_ok.And(dilated_cloud_ok)
        .And(cirrus_ok)
        .And(cloud_ok)
        .And(shadow_ok)
        .And(snow_ok)
        .And(saturation_ok)
    )
    return rgb.updateMask(mask)


def _output_paths(
    aoi: RoughFocusArea,
    *,
    results_root: Path,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> tuple[Path, Path]:
    window_slug = f"{window_start:%Y%m%d}_{window_end:%Y%m%d}"
    quicklook_dir = results_root / "quicklooks_landsat" / aoi.region_slug / window_slug
    chip_dir = results_root / "rough_truth_landsat" / aoi.region_slug / window_slug
    quicklook_path = quicklook_dir / f"{aoi.aoi_id}_landsat_rgb.jpg"
    chip_path = chip_dir / f"{aoi.aoi_id}_landsat_chip.tif"
    return quicklook_path, chip_path
