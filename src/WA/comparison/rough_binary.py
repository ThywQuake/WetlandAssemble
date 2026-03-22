"""Rough-scale binary wetland comparison metrics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd
import xarray as xr

from WA.comparison.harmonize import BINARY_WETLAND_THRESHOLD


@dataclass(frozen=True)
class RoughBinaryResult:
    """Pairwise rough-binary metrics and disagreement surfaces."""

    metrics: pd.DataFrame
    disagreement_score: xr.DataArray
    wetland_vote_fraction: xr.DataArray
    participant_count: xr.DataArray


def compute_rough_binary_metrics(
    surfaces: Mapping[str, xr.DataArray],
    *,
    threshold: float = BINARY_WETLAND_THRESHOLD,
) -> RoughBinaryResult:
    """Compute pairwise metrics and a disagreement surface for aligned inputs."""

    if len(surfaces) < 2:
        raise ValueError("At least two surfaces are required for rough binary comparison")

    _validate_shared_grid(surfaces)

    stacked = xr.concat(
        [
            _prepare_surface_for_stack(surface).expand_dims(dataset=[dataset_id])
            for dataset_id, surface in surfaces.items()
        ],
        dim="dataset",
    )
    binary = xr.where(  # type: ignore[no-untyped-call]
        stacked >= threshold,
        1.0,
        0.0,
    ).where(stacked.notnull())

    participant_count = binary.count("dataset").rename("participant_count")
    wetland_vote_fraction = binary.mean("dataset", skipna=True).rename("wetland_vote_fraction")
    disagreement_score = xr.where(  # type: ignore[no-untyped-call]
        participant_count >= 2,
        1.0 - abs((2.0 * wetland_vote_fraction) - 1.0),
        np.nan,
    ).rename("disagreement_score")

    comparison_time = _comparison_time(surfaces)
    rows: list[dict[str, object]] = []
    dataset_ids = sorted(surfaces)
    for index, dataset_a in enumerate(dataset_ids):
        for dataset_b in dataset_ids[index + 1 :]:
            rows.append(
                _pairwise_metric_row(
                    dataset_a,
                    dataset_b,
                    surfaces[dataset_a],
                    surfaces[dataset_b],
                    threshold=threshold,
                    comparison_time=comparison_time,
                )
            )

    metrics = pd.DataFrame(rows).sort_values(["dataset_a", "dataset_b"]).reset_index(drop=True)
    return RoughBinaryResult(
        metrics=metrics,
        disagreement_score=disagreement_score.astype(np.float32),
        wetland_vote_fraction=wetland_vote_fraction.astype(np.float32),
        participant_count=participant_count.astype(np.int32),
    )


def _pairwise_metric_row(
    dataset_a: str,
    dataset_b: str,
    surface_a: xr.DataArray,
    surface_b: xr.DataArray,
    *,
    threshold: float,
    comparison_time: str | None,
) -> dict[str, object]:
    valid = surface_a.notnull() & surface_b.notnull()
    binary_a = xr.where(surface_a >= threshold, 1, 0).where(valid)  # type: ignore[no-untyped-call]
    binary_b = xr.where(surface_b >= threshold, 1, 0).where(valid)  # type: ignore[no-untyped-call]

    tp = int(((binary_a == 1) & (binary_b == 1)).sum(skipna=True).item())
    tn = int(((binary_a == 0) & (binary_b == 0)).sum(skipna=True).item())
    fp = int(((binary_a == 1) & (binary_b == 0)).sum(skipna=True).item())
    fn = int(((binary_a == 0) & (binary_b == 1)).sum(skipna=True).item())
    total = tp + tn + fp + fn

    overall_accuracy = _safe_div(tp + tn, total)
    producer_accuracy = _safe_div(tp, tp + fn)
    user_accuracy = _safe_div(tp, tp + fp)
    iou = _safe_div(tp, tp + fp + fn)
    f1_score = _safe_div(2 * tp, (2 * tp) + fp + fn)
    kappa = _cohen_kappa(tp=tp, tn=tn, fp=fp, fn=fn)

    return {
        "comparison_time": comparison_time,
        "dataset_a": dataset_a,
        "dataset_b": dataset_b,
        "valid_cell_count": total,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "overall_accuracy": overall_accuracy,
        "producer_accuracy": producer_accuracy,
        "user_accuracy": user_accuracy,
        "iou": iou,
        "f1_score": f1_score,
        "kappa": kappa,
    }


def _cohen_kappa(*, tp: int, tn: int, fp: int, fn: int) -> float:
    total = tp + tn + fp + fn
    if total == 0:
        return float("nan")

    observed = (tp + tn) / total
    wetland_expected = ((tp + fp) * (tp + fn)) / (total * total)
    dryland_expected = ((fn + tn) * (fp + tn)) / (total * total)
    expected = wetland_expected + dryland_expected
    if np.isclose(1.0 - expected, 0.0):
        return float("nan")
    return (observed - expected) / (1.0 - expected)


def _safe_div(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return float("nan")
    return numerator / denominator


def _comparison_time(surfaces: Mapping[str, xr.DataArray]) -> str | None:
    for surface in surfaces.values():
        value = surface.attrs.get("comparison_time")
        if isinstance(value, str) and value:
            return value
    return None


def _prepare_surface_for_stack(surface: xr.DataArray) -> xr.DataArray:
    """Drop non-spatial scalar coords before stacking aligned surfaces."""

    drop_names = [
        name for name in surface.coords if name not in surface.dims and name not in {"lat", "lon"}
    ]
    if not drop_names:
        return surface
    return surface.drop_vars(drop_names, errors="ignore")


def _validate_shared_grid(surfaces: Mapping[str, xr.DataArray]) -> None:
    iterator = iter(surfaces.items())
    first_name, first_surface = next(iterator)
    first_lat = np.asarray(first_surface["lat"].values)
    first_lon = np.asarray(first_surface["lon"].values)

    for dataset_id, surface in iterator:
        if not np.array_equal(first_lat, np.asarray(surface["lat"].values)):
            raise ValueError(
                f"{dataset_id} does not share the reference latitude grid with {first_name}"
            )
        if not np.array_equal(first_lon, np.asarray(surface["lon"].values)):
            raise ValueError(
                f"{dataset_id} does not share the reference longitude grid with {first_name}"
            )
