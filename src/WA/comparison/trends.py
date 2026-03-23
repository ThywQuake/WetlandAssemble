"""Per-pixel Mann-Kendall trend analysis for dynamic wetland datasets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats

from WA.loaders.base import BBox

AggregationLevel = Literal["annual", "seasonal", "monthly"]

# Minimum valid observations required to compute a trend
DEFAULT_MIN_OBSERVATIONS = 5

# Alpha for significance test (p < alpha → significant)
DEFAULT_ALPHA = 0.05

# Season ordering for consistent output
_SEASON_ORDER = ["DJF", "MAM", "JJA", "SON"]


@dataclass(frozen=True)
class TrendResult:
    """Per-pixel Mann-Kendall + Sen's Slope trend analysis result."""

    dataset_id: str
    aggregation: AggregationLevel
    time_range: tuple[str, str]  # ISO format (start, end)
    observation_count: int
    sens_slope: xr.DataArray  # wetland fraction per time step
    p_value: xr.DataArray
    z_score: xr.DataArray
    significant: xr.DataArray  # bool mask (p < alpha)
    trend_direction: xr.DataArray  # +1 increasing, 0 stable, -1 decreasing
    status: str  # "computed" | "insufficient_observations"


def compute_pixel_trends(
    harmonized_surface: xr.DataArray,
    *,
    dataset_id: str,
    aggregation: AggregationLevel = "annual",
    confidence_level: float = 0.95,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> TrendResult:
    """Compute per-pixel Mann-Kendall + Sen's Slope trend test.

    Parameters
    ----------
    harmonized_surface:
        Output of harmonize_binary_dataset(), dims (time, lat, lon),
        values are wetland fraction [0, 1].
    dataset_id:
        Dataset identifier for metadata.
    aggregation:
        Time aggregation level: "annual", "seasonal", or "monthly".
    confidence_level:
        Confidence level for significance (default 0.95 → alpha=0.05).
    min_observations:
        Minimum valid time steps required; returns
        status='insufficient_observations' if not met.

    Returns
    -------
    TrendResult with 5 spatial DataArrays + metadata.
    """
    alpha = 1.0 - confidence_level

    # Aggregate time series
    aggregated = _aggregate_time_series(harmonized_surface, aggregation)

    time_dim = "time" if aggregation != "seasonal" else "season"
    n_obs = aggregated.sizes.get(time_dim, 0)

    # Record time range from the *pre-aggregation* data
    times = harmonized_surface["time"].values
    time_range = (
        str(pd.Timestamp(times[0]).date()),
        str(pd.Timestamp(times[-1]).date()),
    )

    if n_obs < min_observations:
        nan_spatial = xr.full_like(
            harmonized_surface.isel(time=0).drop_vars("time", errors="ignore"),
            fill_value=np.nan,
            dtype=float,
        )
        zero_spatial = nan_spatial.fillna(0.0)
        return TrendResult(
            dataset_id=dataset_id,
            aggregation=aggregation,
            time_range=time_range,
            observation_count=n_obs,
            sens_slope=nan_spatial,
            p_value=nan_spatial,
            z_score=nan_spatial,
            significant=zero_spatial.astype(bool),
            trend_direction=zero_spatial.astype(np.int8),
            status="insufficient_observations",
        )

    result_ds = _vectorized_mk_test(aggregated, alpha=alpha, time_dim=time_dim)

    return TrendResult(
        dataset_id=dataset_id,
        aggregation=aggregation,
        time_range=time_range,
        observation_count=n_obs,
        sens_slope=result_ds["sens_slope"],
        p_value=result_ds["p_value"],
        z_score=result_ds["z_score"],
        significant=result_ds["significant"],
        trend_direction=result_ds["trend_direction"],
        status="computed",
    )


def compute_year_over_year_change(
    harmonized_surface: xr.DataArray,
    *,
    dataset_id: str,
) -> xr.Dataset:
    """Compute short-term year-over-year wetland fraction change.

    No statistical test — raw annual diffs for short-term monitoring.

    Returns
    -------
    xr.Dataset with variables:
    - ``delta_fraction``: annual diff (year N minus year N-1)
    - ``change_direction``: +1 / 0 / -1
    """
    annual = harmonized_surface.resample(time="YS").mean(skipna=True)

    delta = annual.diff(dim="time")

    direction = xr.where(delta > 0, 1, xr.where(delta < 0, -1, 0)).astype(np.int8)

    ds = xr.Dataset(
        {
            "delta_fraction": delta,
            "change_direction": direction,
        }
    )
    ds.attrs["dataset_id"] = dataset_id
    ds.attrs["description"] = "Year-over-year wetland fraction change"
    return ds


def compute_regional_summary(
    trend_result: TrendResult,
    region_bboxes: Mapping[str, BBox],
) -> pd.DataFrame:
    """Compute regional summary statistics from a TrendResult.

    Parameters
    ----------
    trend_result:
        Output of compute_pixel_trends().
    region_bboxes:
        Dict mapping region slug to (west, south, east, north) BBox.

    Returns
    -------
    pd.DataFrame with one row per region (plus "global" row for full domain).
    Columns: region, total_valid_pixels, mean_slope, median_slope,
    fraction_significant, fraction_increasing, fraction_decreasing,
    fraction_stable.
    """
    rows: list[dict[str, object]] = []

    regions: dict[str, BBox | None] = {**dict(region_bboxes), "global": None}

    for region_slug, bbox in regions.items():
        slope = trend_result.sens_slope
        sig = trend_result.significant
        direction = trend_result.trend_direction

        if bbox is not None:
            west, south, east, north = bbox
            slope = slope.sel(
                lat=slice(north, south),
                lon=slice(west, east),
            )
            sig = sig.sel(
                lat=slice(north, south),
                lon=slice(west, east),
            )
            direction = direction.sel(
                lat=slice(north, south),
                lon=slice(west, east),
            )

        valid_mask = np.isfinite(slope.values)
        total = int(valid_mask.sum())
        if total == 0:
            continue

        rows.append(
            {
                "region": region_slug,
                "dataset_id": trend_result.dataset_id,
                "aggregation": trend_result.aggregation,
                "total_valid_pixels": total,
                "mean_slope": float(np.nanmean(slope.values)),
                "median_slope": float(np.nanmedian(slope.values)),
                "fraction_significant": float(sig.values[valid_mask].mean()),
                "fraction_increasing": float(
                    (direction.values[valid_mask] == 1).mean()
                ),
                "fraction_decreasing": float(
                    (direction.values[valid_mask] == -1).mean()
                ),
                "fraction_stable": float(
                    (direction.values[valid_mask] == 0).mean()
                ),
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pixel_mann_kendall(
    values: np.ndarray,
    alpha: float,
) -> tuple[float, float, float, float, float]:
    """Compute MK + Sen's slope for a single pixel time series.

    Returns
    -------
    (sens_slope, p_value, z_score, significant, direction)
    """
    # Remove NaNs
    finite = values[np.isfinite(values)]

    if len(finite) < 4:
        return (np.nan, 1.0, 0.0, 0.0, 0.0)

    if np.ptp(finite) == 0:
        # All values identical — no trend
        return (0.0, 1.0, 0.0, 0.0, 0.0)

    x = np.arange(len(finite), dtype=float)

    # Mann-Kendall via Kendall's tau
    tau, p_value = stats.kendalltau(x, finite, nan_policy="omit")
    if not np.isfinite(tau):
        return (np.nan, 1.0, 0.0, 0.0, 0.0)

    # Sen's slope via Theil-Sen estimator
    slope_val, _, _, _ = stats.theilslopes(finite, x)

    # Convert tau to approximate z-score
    if p_value <= 0.0:
        z_score = float(np.sign(tau) * 8.0)
    elif p_value >= 1.0:
        z_score = 0.0
    else:
        z_score = float(np.sign(tau) * stats.norm.isf(p_value / 2.0))

    significant = float(p_value < alpha)
    if significant and slope_val > 0:
        direction = 1.0
    elif significant and slope_val < 0:
        direction = -1.0
    else:
        direction = 0.0

    return (float(slope_val), float(p_value), z_score, significant, direction)


def _vectorized_mk_test(
    data: xr.DataArray,
    alpha: float,
    time_dim: str = "time",
) -> xr.Dataset:
    """Apply _pixel_mann_kendall across all pixels via xr.apply_ufunc."""

    # apply_ufunc expects the time dimension as core dim
    results = xr.apply_ufunc(
        _pixel_mann_kendall,
        data,
        kwargs={"alpha": alpha},
        input_core_dims=[[time_dim]],
        output_core_dims=[[], [], [], [], []],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[float, float, float, float, float],
    )

    slope_da, pval_da, zscore_da, sig_da, dir_da = results

    return xr.Dataset(
        {
            "sens_slope": slope_da,
            "p_value": pval_da,
            "z_score": zscore_da,
            "significant": sig_da.astype(bool),
            "trend_direction": dir_da.astype(np.int8),
        }
    )


def _aggregate_time_series(
    data: xr.DataArray,
    aggregation: AggregationLevel,
) -> xr.DataArray:
    """Aggregate time series to the specified level.

    For 'seasonal', groups by DJF/MAM/JJA/SON and returns a DataArray
    with dim 'season' (string labels).
    """
    if aggregation == "annual":
        return data.resample(time="YS").mean(skipna=True)

    elif aggregation == "seasonal":
        seasonal = data.groupby("time.season").mean(skipna=True)
        # Reorder to standard DJF/MAM/JJA/SON
        available = [s for s in _SEASON_ORDER if s in seasonal["season"].values]
        if available:
            seasonal = seasonal.sel(season=available)
        return seasonal

    elif aggregation == "monthly":
        return data.resample(time="MS").mean(skipna=True)

    else:
        raise ValueError(f"Unknown aggregation level: {aggregation!r}")
