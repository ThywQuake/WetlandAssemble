"""Focus-AOI selection for rough binary disagreement outputs."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import SupportsFloat, SupportsInt, cast

import pandas as pd
import xarray as xr

from WA.loaders.base import BBox

DEFAULT_FOCUS_REGION_BBOXES: dict[str, BBox] = {
    "brazil": (-75.0, -35.0, -34.0, 6.0),
    "indonesia": (95.0, -11.0, 141.0, 6.0),
    "southeast_asia": (90.0, -11.0, 130.0, 24.0),
    "africa": (-20.0, -35.0, 55.0, 22.0),
}


@dataclass(frozen=True)
class RoughFocusArea:
    """A deterministic rough-scale AOI selected for manual review."""

    aoi_id: str
    region_slug: str
    target_time: pd.Timestamp
    bbox: BBox
    center_lon: float
    center_lat: float
    disagreement_score: float
    participant_count: int
    wetland_vote_fraction: float | None = None


def select_focus_areas(
    disagreement_score: xr.DataArray,
    participant_count: xr.DataArray,
    *,
    target_time: str | pd.Timestamp,
    wetland_vote_fraction: xr.DataArray | None = None,
    top_n: int = 8,
    top_n_per_region: int = 2,
    aoi_size_deg: float = 2.0,
    min_distance_deg: float = 3.0,
    region_bboxes: Mapping[str, BBox] | None = None,
) -> list[RoughFocusArea]:
    """Select stratified, deduplicated focus AOIs from a disagreement surface."""

    if top_n <= 0:
        return []

    region_bboxes = dict(region_bboxes or DEFAULT_FOCUS_REGION_BBOXES)
    comparison_time = pd.Timestamp(target_time)
    candidates = _candidate_rows(
        disagreement_score,
        participant_count,
        wetland_vote_fraction=wetland_vote_fraction,
        region_bboxes=region_bboxes,
    )
    if candidates.empty:
        return []

    selected: list[dict[str, object]] = []
    region_counts: defaultdict[str, int] = defaultdict(int)

    for region_slug in region_bboxes:
        region_candidates = candidates[candidates["region_slug"] == region_slug]
        chosen = _choose_first_eligible(
            region_candidates.to_dict("records"),
            selected,
            min_distance_deg=min_distance_deg,
        )
        if chosen is None:
            continue
        selected.append(chosen)
        region_counts[region_slug] += 1
        if len(selected) >= top_n:
            return _build_focus_areas(
                selected,
                comparison_time=comparison_time,
                aoi_size_deg=aoi_size_deg,
            )

    for candidate in candidates.to_dict("records"):
        region_slug = str(candidate["region_slug"])
        if region_counts[region_slug] >= top_n_per_region:
            continue
        if not _is_far_enough(candidate, selected, min_distance_deg=min_distance_deg):
            continue
        selected.append(candidate)
        region_counts[region_slug] += 1
        if len(selected) >= top_n:
            break

    return _build_focus_areas(
        selected,
        comparison_time=comparison_time,
        aoi_size_deg=aoi_size_deg,
    )


def _candidate_rows(
    disagreement_score: xr.DataArray,
    participant_count: xr.DataArray,
    *,
    wetland_vote_fraction: xr.DataArray | None,
    region_bboxes: Mapping[str, BBox],
) -> pd.DataFrame:
    score_df = disagreement_score.rename("disagreement_score").to_dataframe().reset_index()
    score_df = score_df.dropna(subset=["disagreement_score"])
    score_df = score_df[score_df["disagreement_score"] > 0]
    if score_df.empty:
        return score_df

    participant_df = participant_count.rename("participant_count").to_dataframe().reset_index()
    merged = score_df.merge(participant_df, on=["lat", "lon"], how="left")

    if wetland_vote_fraction is not None:
        vote_df = wetland_vote_fraction.rename("wetland_vote_fraction").to_dataframe().reset_index()
        merged = merged.merge(vote_df, on=["lat", "lon"], how="left")
    else:
        merged["wetland_vote_fraction"] = pd.NA

    merged["region_slug"] = merged.apply(
        lambda row: _assign_region(_as_float(row["lon"]), _as_float(row["lat"]), region_bboxes),
        axis=1,
    )
    return merged.sort_values(
        ["disagreement_score", "participant_count"],
        ascending=[False, False],
    ).reset_index(drop=True)


def _assign_region(
    lon: float,
    lat: float,
    region_bboxes: Mapping[str, BBox],
) -> str:
    for region_slug, bbox in region_bboxes.items():
        west, south, east, north = bbox
        if west <= lon <= east and south <= lat <= north:
            return region_slug
    return "other"


def _choose_first_eligible(
    candidates: list[dict[str, object]],
    selected: list[dict[str, object]],
    *,
    min_distance_deg: float,
) -> dict[str, object] | None:
    for candidate in candidates:
        if _is_far_enough(candidate, selected, min_distance_deg=min_distance_deg):
            return candidate
    return None


def _is_far_enough(
    candidate: Mapping[str, object],
    selected: list[dict[str, object]],
    *,
    min_distance_deg: float,
) -> bool:
    candidate_lon = _as_float(candidate["lon"])
    candidate_lat = _as_float(candidate["lat"])
    for existing in selected:
        delta_lon = candidate_lon - _as_float(existing["lon"])
        delta_lat = candidate_lat - _as_float(existing["lat"])
        if math.hypot(delta_lon, delta_lat) < min_distance_deg:
            return False
    return True


def _build_focus_areas(
    rows: list[dict[str, object]],
    *,
    comparison_time: pd.Timestamp,
    aoi_size_deg: float,
) -> list[RoughFocusArea]:
    focus_areas: list[RoughFocusArea] = []
    for index, row in enumerate(rows, start=1):
        center_lon = _as_float(row["lon"])
        center_lat = _as_float(row["lat"])
        region_slug = str(row["region_slug"])
        aoi_id = f"rough-{comparison_time:%Y%m}-{region_slug}-{index:03d}"
        focus_areas.append(
            RoughFocusArea(
                aoi_id=aoi_id,
                region_slug=region_slug,
                target_time=comparison_time,
                bbox=_buffered_bbox(center_lon, center_lat, size_deg=aoi_size_deg),
                center_lon=center_lon,
                center_lat=center_lat,
                disagreement_score=_as_float(row["disagreement_score"]),
                participant_count=_as_int(row["participant_count"]),
                wetland_vote_fraction=_optional_float(row["wetland_vote_fraction"]),
            )
        )
    return focus_areas


def _buffered_bbox(center_lon: float, center_lat: float, *, size_deg: float) -> BBox:
    half = size_deg / 2.0
    west = max(-180.0, center_lon - half)
    east = min(180.0, center_lon + half)
    south = max(-90.0, center_lat - half)
    north = min(90.0, center_lat + half)
    return (west, south, east, north)


def _optional_float(value: object) -> float | None:
    if value is pd.NA or value is None:
        return None
    try:
        numeric = _as_float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return numeric


def _as_float(value: object) -> float:
    return float(cast(SupportsFloat | str, value))


def _as_int(value: object) -> int:
    return int(cast(SupportsInt | str, value))
