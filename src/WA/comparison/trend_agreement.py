"""Cross-dataset trend agreement analysis for dynamic wetland datasets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd
import xarray as xr

from WA.comparison.focus_areas import DEFAULT_FOCUS_REGION_BBOXES
from WA.comparison.trends import TrendResult
from WA.loaders.base import BBox


@dataclass(frozen=True)
class TrendAgreementResult:
    """Cross-dataset trend consistency analysis result."""

    overlap_window: tuple[str, str]  # ISO (start, end) dates
    participant_ids: list[str]
    agreement_ratio: xr.DataArray  # [0, 1] fraction of datasets agreeing
    mean_slope: xr.DataArray  # mean Sen's slope across datasets
    slope_std: xr.DataArray  # std of Sen's slope across datasets
    robust_increase: xr.DataArray  # bool: all datasets agree on increase
    robust_decrease: xr.DataArray  # bool: all datasets agree on decrease
    robust_stable: xr.DataArray  # bool: all datasets agree on stable
    disputed: xr.DataArray  # bool: not all datasets agree
    regional_summary: pd.DataFrame
    status: str  # "computed" | "overlap_window_empty"


def compute_overlap_window(
    trend_results: Mapping[str, TrendResult],
) -> tuple[str, str] | None:
    """Find the maximum common time window across all participant datasets.

    Returns
    -------
    (start_iso, end_iso) or None if no overlap exists.
    """
    if not trend_results:
        return None

    starts = []
    ends = []
    for result in trend_results.values():
        starts.append(pd.Timestamp(result.time_range[0]))
        ends.append(pd.Timestamp(result.time_range[1]))

    overlap_start = max(starts)
    overlap_end = min(ends)

    if overlap_start > overlap_end:
        return None

    return (str(overlap_start.date()), str(overlap_end.date()))


def compute_trend_agreement(
    trend_results: Mapping[str, TrendResult],
    *,
    min_overlap_years: int = 5,
    region_bboxes: Mapping[str, BBox] | None = None,
) -> TrendAgreementResult:
    """Compute cross-dataset trend consistency.

    Uses the trend_direction arrays from each dataset's TrendResult
    (pre-computed over their full time range) and produces pixel-wise
    agreement metrics.

    Parameters
    ----------
    trend_results:
        Mapping from dataset_id to TrendResult (from compute_pixel_trends).
    min_overlap_years:
        Minimum overlap duration in years required; returns
        status='overlap_window_empty' if not met.
    region_bboxes:
        Region definitions (default: DEFAULT_FOCUS_REGION_BBOXES).

    Returns
    -------
    TrendAgreementResult with pixel-wise agreement metrics + regional summary.
    """
    region_bboxes = dict(region_bboxes or DEFAULT_FOCUS_REGION_BBOXES)
    participant_ids = list(trend_results.keys())

    # Determine overlap window
    overlap = compute_overlap_window(trend_results)

    if overlap is None:
        return _empty_agreement_result(
            participant_ids, region_bboxes, reason="overlap_window_empty"
        )

    overlap_start, overlap_end = overlap
    overlap_years = (
        pd.Timestamp(overlap_end) - pd.Timestamp(overlap_start)
    ).days / 365.25

    if overlap_years < min_overlap_years:
        return _empty_agreement_result(
            participant_ids, region_bboxes, reason="overlap_window_empty"
        )

    # Stack trend directions and slopes from all datasets
    direction_arrays = []
    slope_arrays = []

    for ds_id, result in trend_results.items():
        if result.status != "computed":
            continue
        direction_arrays.append(
            result.trend_direction.astype(float).expand_dims(dataset=[ds_id])
        )
        slope_arrays.append(
            result.sens_slope.expand_dims(dataset=[ds_id])
        )

    if not direction_arrays:
        return _empty_agreement_result(
            participant_ids, region_bboxes, reason="overlap_window_empty"
        )

    stacked_directions = xr.concat(direction_arrays, dim="dataset")
    stacked_slopes = xr.concat(slope_arrays, dim="dataset")

    # Compute agreement metrics
    metrics = _compute_agreement_metrics(stacked_directions)
    mean_slope = stacked_slopes.mean(dim="dataset", skipna=True)
    slope_std = stacked_slopes.std(dim="dataset", skipna=True)

    regional_summary = _compute_regional_summary(
        metrics, mean_slope, region_bboxes
    )

    return TrendAgreementResult(
        overlap_window=(overlap_start, overlap_end),
        participant_ids=participant_ids,
        agreement_ratio=metrics["agreement_ratio"],
        mean_slope=mean_slope,
        slope_std=slope_std,
        robust_increase=metrics["robust_increase"],
        robust_decrease=metrics["robust_decrease"],
        robust_stable=metrics["robust_stable"],
        disputed=metrics["disputed"],
        regional_summary=regional_summary,
        status="computed",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_agreement_metrics(
    stacked_directions: xr.DataArray,  # dims: (dataset, lat, lon)
) -> dict[str, xr.DataArray]:
    """Compute pixel-wise agreement metrics from stacked trend directions."""
    n_datasets = stacked_directions.sizes["dataset"]

    count_increase = (stacked_directions == 1).sum(dim="dataset")
    count_decrease = (stacked_directions == -1).sum(dim="dataset")
    count_stable = (stacked_directions == 0).sum(dim="dataset")

    # Agreement ratio = fraction agreeing on the majority direction
    max_count = xr.concat(
        [count_increase, count_decrease, count_stable], dim="dir"
    ).max(dim="dir")
    agreement_ratio = max_count / n_datasets

    robust_increase = count_increase == n_datasets
    robust_decrease = count_decrease == n_datasets
    robust_stable = count_stable == n_datasets
    disputed = agreement_ratio < 1.0

    return {
        "agreement_ratio": agreement_ratio,
        "robust_increase": robust_increase,
        "robust_decrease": robust_decrease,
        "robust_stable": robust_stable,
        "disputed": disputed,
    }


def _compute_regional_summary(
    metrics: dict[str, xr.DataArray],
    mean_slope: xr.DataArray,
    region_bboxes: Mapping[str, BBox],
) -> pd.DataFrame:
    """Compute per-region summary statistics."""
    rows: list[dict[str, object]] = []

    regions: dict[str, BBox | None] = {**dict(region_bboxes), "global": None}

    for region_slug, bbox in regions.items():
        if bbox is not None:
            west, south, east, north = bbox
            sel = {
                key: arr.sel(lat=slice(north, south), lon=slice(west, east))
                for key, arr in metrics.items()
            }
            slope_region = mean_slope.sel(
                lat=slice(north, south), lon=slice(west, east)
            )
        else:
            sel = dict(metrics)
            slope_region = mean_slope

        total = int(sel["agreement_ratio"].count().item())
        if total == 0:
            continue

        rows.append(
            {
                "region": region_slug,
                "total_valid_pixels": total,
                "mean_agreement_ratio": float(
                    sel["agreement_ratio"].mean().item()
                ),
                "fraction_robust_increase": float(
                    sel["robust_increase"].sum().item() / total
                ),
                "fraction_robust_decrease": float(
                    sel["robust_decrease"].sum().item() / total
                ),
                "fraction_robust_stable": float(
                    sel["robust_stable"].sum().item() / total
                ),
                "fraction_disputed": float(
                    sel["disputed"].sum().item() / total
                ),
                "mean_slope_across_datasets": float(
                    np.nanmean(slope_region.values)
                ),
            }
        )

    return pd.DataFrame(rows)


def _empty_agreement_result(
    participant_ids: list[str],
    region_bboxes: Mapping[str, BBox],
    *,
    reason: str,
) -> TrendAgreementResult:
    """Return a TrendAgreementResult with empty/NaN arrays and given status."""
    # Need a spatial template; create a minimal 2x2 NaN array
    nan_da = xr.DataArray(
        np.full((2, 2), np.nan),
        dims=["lat", "lon"],
        coords={"lat": [1.0, 0.0], "lon": [0.0, 1.0]},
    )
    false_da = xr.zeros_like(nan_da, dtype=bool)

    return TrendAgreementResult(
        overlap_window=("", ""),
        participant_ids=participant_ids,
        agreement_ratio=nan_da,
        mean_slope=nan_da,
        slope_std=nan_da,
        robust_increase=false_da,
        robust_decrease=false_da,
        robust_stable=false_da,
        disputed=false_da,
        regional_summary=pd.DataFrame(),
        status=reason,
    )
