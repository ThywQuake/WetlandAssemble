"""Contract-backed Phase 4 per-dataset trend surface and summary helpers.

This module restores the missing dataset-scoped trend contract artifacts that
sit underneath the existing agreement/hotspot families:

- one `trend_surface` NetCDF per `dataset_id + region_id`
- one `trend_regional_summary` CSV per `dataset_id + region_id`

Participant-set semantics remain reserved for the downstream agreement and
trend-hotspot families.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import xarray as xr

from WA.comparison.evidence_contract import (
    EvidenceContract,
    metadata_json,
    validate_stem_token,
)
from WA.comparison.trend_agreement import TrendAgreementResult
from WA.comparison.trend_hotspots import build_participant_set_key, normalize_participant_ids
from WA.comparison.trends import AggregationLevel, TrendResult, compute_regional_summary
from WA.loaders.base import BBox

REQUIRED_TREND_SURFACE_VARS = (
    "sens_slope",
    "p_value",
    "z_score",
    "significant",
    "trend_direction",
)
TREND_SUMMARY_COLUMNS = (
    "region",
    "region_id",
    "region_label",
    "dataset_id",
    "aggregation",
    "time_range_start",
    "time_range_end",
    "observation_count",
    "status",
    "total_valid_pixels",
    "mean_slope",
    "median_slope",
    "fraction_significant",
    "fraction_increasing",
    "fraction_decreasing",
    "fraction_stable",
    "bbox_json",
    "contract_metadata_json",
)
REQUIRED_AGREEMENT_VARS = (
    "agreement_ratio",
    "mean_slope",
    "slope_std",
    "robust_increase",
    "robust_decrease",
    "robust_stable",
    "disputed",
)
REQUIRED_AGREEMENT_SUMMARY_COLUMNS = (
    "region",
    "total_valid_pixels",
    "mean_agreement_ratio",
    "fraction_robust_increase",
    "fraction_robust_decrease",
    "fraction_robust_stable",
    "fraction_disputed",
    "mean_slope_across_datasets",
    "region_id",
    "participant_set_key",
    "participant_ids_json",
    "overlap_window_start",
    "overlap_window_end",
    "contract_metadata_json",
)


@dataclass(frozen=True)
class TrendSurfaceBundle:
    """One contract-backed per-dataset trend surface artifact."""

    surface_path: Path
    region_id: str
    region_label: str
    dataset_id: str
    aggregation: AggregationLevel
    time_range: tuple[str, str]
    observation_count: int
    status: str
    bbox: BBox
    dataset: xr.Dataset
    contract_metadata_json: str
    contract_metadata: dict[str, Any]


@dataclass(frozen=True)
class TrendSummaryBundle:
    """One contract-backed per-dataset trend regional summary artifact."""

    summary_path: Path
    region_id: str
    region_label: str
    dataset_id: str
    aggregation: AggregationLevel
    time_range: tuple[str, str]
    observation_count: int
    status: str
    bbox: BBox
    table: pd.DataFrame
    contract_metadata_json: str
    contract_metadata: dict[str, Any]


@dataclass(frozen=True)
class TrendAgreementSurfaceBundle:
    """One contract-backed trend agreement surface artifact."""

    surface_path: Path
    region_id: str
    participant_ids: tuple[str, ...]
    participant_set_key: str
    overlap_window: tuple[str, str]
    status: str
    dataset: xr.Dataset
    contract_metadata_json: str
    contract_metadata: dict[str, Any]


@dataclass(frozen=True)
class TrendAgreementSummaryBundle:
    """One contract-backed trend agreement summary artifact."""

    summary_path: Path
    region_id: str
    participant_ids: tuple[str, ...]
    participant_set_key: str
    overlap_window: tuple[str, str]
    table: pd.DataFrame
    contract_metadata_json: str
    contract_metadata: dict[str, Any]


@dataclass(frozen=True)
class TrendAgreementReload:
    """Reloaded trend agreement surface/summary pair plus reconstructed result."""

    surface: TrendAgreementSurfaceBundle
    summary: TrendAgreementSummaryBundle
    result: TrendAgreementResult


def trend_surface_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_id: str,
) -> Path:
    """Return the contract output path for one per-dataset trend surface."""

    return contract.artifact_output_path(
        kind="trend_surface",
        dataset_or_key=validate_stem_token(dataset_id, label="dataset_id"),
        region_id=region_id,
    )


def trend_summary_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_id: str,
) -> Path:
    """Return the contract output path for one per-dataset trend summary."""

    return contract.artifact_output_path(
        kind="trend_regional_summary",
        dataset_or_key=validate_stem_token(dataset_id, label="dataset_id"),
        region_id=region_id,
    )


def trend_agreement_surface_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    participant_ids: Iterable[str],
) -> Path:
    """Return the contract output path for one trend agreement surface."""

    participant_set_key = build_participant_set_key(participant_ids)
    return contract.artifact_output_path(
        kind="trend_agreement_surface",
        dataset_or_key=participant_set_key,
        region_id=region_id,
    )


def trend_agreement_summary_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    participant_ids: Iterable[str],
) -> Path:
    """Return the contract output path for one trend agreement summary."""

    participant_set_key = build_participant_set_key(participant_ids)
    return contract.artifact_output_path(
        kind="trend_agreement_summary",
        dataset_or_key=participant_set_key,
        region_id=region_id,
    )


def write_contract_trend_surface(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_label: str,
    bbox: BBox,
    trend_result: TrendResult,
) -> TrendSurfaceBundle:
    """Write one contract-backed per-dataset trend surface artifact."""

    dataset_id = validate_stem_token(trend_result.dataset_id, label="dataset_id")
    contract_metadata = {
        "artifact_kind": "trend_surface",
        "region_id": region_id,
        "region_label": region_label,
        "dataset_id": dataset_id,
        "aggregation": trend_result.aggregation,
        "time_range": list(trend_result.time_range),
        "observation_count": int(trend_result.observation_count),
        "status": trend_result.status,
        "bbox": list(bbox),
        "required_variables": list(REQUIRED_TREND_SURFACE_VARS),
    }
    contract_metadata_json = metadata_json(contract_metadata)
    dataset = xr.Dataset(
        {
            "sens_slope": trend_result.sens_slope.astype(np.float32),
            "p_value": trend_result.p_value.astype(np.float32),
            "z_score": trend_result.z_score.astype(np.float32),
            "significant": trend_result.significant.astype(np.int8),
            "trend_direction": trend_result.trend_direction.astype(np.int8),
        }
    )
    dataset.attrs.update(
        {
            "region_id": region_id,
            "region_label": region_label,
            "dataset_id": dataset_id,
            "aggregation": trend_result.aggregation,
            "time_range_start": trend_result.time_range[0],
            "time_range_end": trend_result.time_range[1],
            "observation_count": int(trend_result.observation_count),
            "status": trend_result.status,
            "bbox_json": json.dumps(list(bbox), separators=(",", ":")),
            "contract_metadata_json": contract_metadata_json,
        }
    )

    surface_path = trend_surface_output_path(
        contract,
        region_id=region_id,
        dataset_id=dataset_id,
    )
    _write_dataset_atomic(surface_path, dataset)
    return load_contract_trend_surface(
        contract=contract,
        region_id=region_id,
        dataset_id=dataset_id,
        expected_aggregation=trend_result.aggregation,
        expected_time_range=trend_result.time_range,
    )


def load_contract_trend_surface(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_id: str,
    expected_aggregation: AggregationLevel | None = None,
    expected_time_range: tuple[str, str] | None = None,
) -> TrendSurfaceBundle:
    """Reload one contract-backed per-dataset trend surface by semantics."""

    normalized_dataset_id = validate_stem_token(dataset_id, label="dataset_id")
    surface_path = trend_surface_output_path(
        contract,
        region_id=region_id,
        dataset_id=normalized_dataset_id,
    )
    if not surface_path.is_file():
        raise FileNotFoundError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            f"missing trend_surface path={surface_path}"
        )

    dataset = xr.load_dataset(surface_path)
    missing_vars = [
        name for name in REQUIRED_TREND_SURFACE_VARS if name not in dataset.data_vars
    ]
    if missing_vars:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            "trend surface is missing required variables: "
            + ", ".join(missing_vars)
        )
    if str(dataset.attrs.get("region_id", "")).strip() != region_id:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            "trend surface region_id does not match the requested region"
        )
    surface_dataset_id = str(dataset.attrs.get("dataset_id", "")).strip()
    if surface_dataset_id != normalized_dataset_id:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            "trend surface dataset_id does not match the requested dataset"
        )

    aggregation = cast(
        AggregationLevel,
        str(dataset.attrs.get("aggregation", "")).strip(),
    )
    if aggregation not in {"annual", "seasonal", "monthly"}:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            f"invalid aggregation={aggregation!r}"
        )
    if expected_aggregation is not None and aggregation != expected_aggregation:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            f"aggregation mismatch={aggregation!r}"
        )

    time_range = (
        str(dataset.attrs.get("time_range_start", "")).strip(),
        str(dataset.attrs.get("time_range_end", "")).strip(),
    )
    if not time_range[0] or not time_range[1]:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            "trend surface is missing time_range metadata"
        )
    if expected_time_range is not None and time_range != expected_time_range:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            f"time_range mismatch={time_range!r}"
        )

    observation_count = int(dataset.attrs.get("observation_count", 0))
    if observation_count < 0:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            f"invalid observation_count={observation_count}"
        )
    status = str(dataset.attrs.get("status", "")).strip()
    if not status:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} missing status"
        )

    bbox = _parse_bbox_literal(
        dataset.attrs.get("bbox_json", ""),
        region_id=region_id,
        dataset_id=normalized_dataset_id,
        label="bbox_json",
    )
    contract_metadata_json = str(dataset.attrs.get("contract_metadata_json", "")).strip()
    if not contract_metadata_json:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            "trend surface is missing contract_metadata_json"
        )
    contract_metadata = _parse_json_object(
        contract_metadata_json,
        region_id=region_id,
        dataset_id=normalized_dataset_id,
        label="contract_metadata_json",
    )
    return TrendSurfaceBundle(
        surface_path=surface_path.resolve(),
        region_id=region_id,
        region_label=str(dataset.attrs.get("region_label", region_id)),
        dataset_id=normalized_dataset_id,
        aggregation=aggregation,
        time_range=time_range,
        observation_count=observation_count,
        status=status,
        bbox=bbox,
        dataset=dataset,
        contract_metadata_json=contract_metadata_json,
        contract_metadata=contract_metadata,
    )


def write_contract_trend_summary(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_label: str,
    bbox: BBox,
    trend_result: TrendResult,
    surface_output_path: str | Path | None = None,
) -> TrendSummaryBundle:
    """Write one contract-backed per-dataset trend summary artifact."""

    dataset_id = validate_stem_token(trend_result.dataset_id, label="dataset_id")
    contract_metadata = {
        "artifact_kind": "trend_regional_summary",
        "region_id": region_id,
        "region_label": region_label,
        "dataset_id": dataset_id,
        "aggregation": trend_result.aggregation,
        "time_range": list(trend_result.time_range),
        "observation_count": int(trend_result.observation_count),
        "status": trend_result.status,
        "bbox": list(bbox),
        "surface_output_path": (
            str(Path(surface_output_path).resolve())
            if surface_output_path is not None
            else None
        ),
    }
    contract_metadata_json = metadata_json(contract_metadata)
    row = _build_summary_row(
        region_id=region_id,
        region_label=region_label,
        bbox=bbox,
        trend_result=trend_result,
        contract_metadata_json=contract_metadata_json,
    )
    table = pd.DataFrame([row]).loc[:, list(TREND_SUMMARY_COLUMNS)]

    summary_path = trend_summary_output_path(
        contract,
        region_id=region_id,
        dataset_id=dataset_id,
    )
    _write_text_atomic(summary_path, table.to_csv(index=False, lineterminator="\n"))
    return load_contract_trend_summary(
        contract=contract,
        region_id=region_id,
        dataset_id=dataset_id,
        expected_aggregation=trend_result.aggregation,
        expected_time_range=trend_result.time_range,
    )


def load_contract_trend_summary(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_id: str,
    expected_aggregation: AggregationLevel | None = None,
    expected_time_range: tuple[str, str] | None = None,
) -> TrendSummaryBundle:
    """Reload one contract-backed per-dataset trend summary by semantics."""

    normalized_dataset_id = validate_stem_token(dataset_id, label="dataset_id")
    summary_path = trend_summary_output_path(
        contract,
        region_id=region_id,
        dataset_id=normalized_dataset_id,
    )
    if not summary_path.is_file():
        raise FileNotFoundError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            f"missing trend_regional_summary path={summary_path}"
        )

    table = pd.read_csv(summary_path)
    missing_columns = [
        column for column in TREND_SUMMARY_COLUMNS if column not in table.columns
    ]
    if missing_columns:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            "trend summary is missing required columns: " + ", ".join(missing_columns)
        )
    if len(table) != 1:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            f"trend summary must contain exactly one row, got {len(table)}"
        )
    if any(str(value).strip() != region_id for value in table["region_id"]):
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} mixed region_id values"
        )
    if any(str(value).strip() != region_id for value in table["region"]):
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} mixed region values"
        )
    if any(str(value).strip() != normalized_dataset_id for value in table["dataset_id"]):
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} mixed dataset_id values"
        )

    aggregation = cast(AggregationLevel, str(table["aggregation"].iloc[0]).strip())
    if aggregation not in {"annual", "seasonal", "monthly"}:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            f"invalid aggregation={aggregation!r}"
        )
    if expected_aggregation is not None and aggregation != expected_aggregation:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            f"aggregation mismatch={aggregation!r}"
        )

    time_range = (
        str(table["time_range_start"].iloc[0]).strip(),
        str(table["time_range_end"].iloc[0]).strip(),
    )
    if expected_time_range is not None and time_range != expected_time_range:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            f"time_range mismatch={time_range!r}"
        )

    observation_count = int(table["observation_count"].iloc[0])
    if observation_count < 0:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            f"invalid observation_count={observation_count}"
        )
    status = str(table["status"].iloc[0]).strip()
    if not status:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} missing status"
        )

    bbox = _parse_bbox_literal(
        table["bbox_json"].iloc[0],
        region_id=region_id,
        dataset_id=normalized_dataset_id,
        label="bbox_json",
    )
    metadata_values = {str(value).strip() for value in table["contract_metadata_json"]}
    if len(metadata_values) != 1:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={normalized_dataset_id} "
            "trend summary must contain exactly one contract_metadata_json value"
        )
    contract_metadata_json = metadata_values.pop()
    contract_metadata = _parse_json_object(
        contract_metadata_json,
        region_id=region_id,
        dataset_id=normalized_dataset_id,
        label="contract_metadata_json",
    )
    return TrendSummaryBundle(
        summary_path=summary_path.resolve(),
        region_id=region_id,
        region_label=str(table["region_label"].iloc[0]),
        dataset_id=normalized_dataset_id,
        aggregation=aggregation,
        time_range=time_range,
        observation_count=observation_count,
        status=status,
        bbox=bbox,
        table=table,
        contract_metadata_json=contract_metadata_json,
        contract_metadata=contract_metadata,
    )


def load_contract_trend_agreement_surface(
    *,
    contract: EvidenceContract,
    region_id: str,
    participant_ids: Iterable[str],
    expected_overlap_window: tuple[str, str] | None = None,
) -> TrendAgreementSurfaceBundle:
    """Reload one contract-backed trend agreement surface by semantics."""

    normalized_participant_ids = normalize_participant_ids(participant_ids)
    participant_set_key = build_participant_set_key(normalized_participant_ids)
    surface_path = trend_agreement_surface_output_path(
        contract,
        region_id=region_id,
        participant_ids=normalized_participant_ids,
    )
    if not surface_path.is_file():
        raise FileNotFoundError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            f"missing trend_agreement_surface path={surface_path}"
        )

    dataset = xr.load_dataset(surface_path)
    missing_vars = [
        name for name in REQUIRED_AGREEMENT_VARS if name not in dataset.data_vars
    ]
    if missing_vars:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            f"missing variables={', '.join(missing_vars)}"
        )

    surface_region_id = str(dataset.attrs.get("region_id", "")).strip()
    if surface_region_id != region_id:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            f"surface region mismatch={surface_region_id}"
        )
    surface_participant_set_key = str(dataset.attrs.get("participant_set_key", "")).strip()
    if surface_participant_set_key != participant_set_key:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "surface participant_set_key does not match the requested participant set"
        )
    surface_participant_ids = _parse_participant_ids_json_with_context(
        dataset.attrs.get("participant_ids_json", ""),
        region_id=region_id,
        participant_set_key=participant_set_key,
        label="participant_ids_json",
    )
    if surface_participant_ids != normalized_participant_ids:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "surface participant_ids do not match the requested participant set"
        )

    overlap_window = (
        str(dataset.attrs.get("overlap_window_start", "")).strip(),
        str(dataset.attrs.get("overlap_window_end", "")).strip(),
    )
    if not overlap_window[0] or not overlap_window[1]:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "trend agreement surface is missing overlap_window metadata"
        )
    if expected_overlap_window is not None and overlap_window != expected_overlap_window:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            f"overlap_window mismatch={overlap_window!r}"
        )

    status = str(dataset.attrs.get("status", "")).strip()
    if not status:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} missing status"
        )
    contract_metadata_json = str(dataset.attrs.get("contract_metadata_json", "")).strip()
    if not contract_metadata_json:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "trend agreement surface is missing contract_metadata_json"
        )
    contract_metadata = _parse_json_object_with_context(
        contract_metadata_json,
        stage="agreement",
        region_id=region_id,
        context_label="participant_set_key",
        context_value=participant_set_key,
        label="contract_metadata_json",
    )

    return TrendAgreementSurfaceBundle(
        surface_path=surface_path.resolve(),
        region_id=region_id,
        participant_ids=normalized_participant_ids,
        participant_set_key=participant_set_key,
        overlap_window=overlap_window,
        status=status,
        dataset=dataset,
        contract_metadata_json=contract_metadata_json,
        contract_metadata=contract_metadata,
    )


def load_contract_trend_agreement_summary(
    *,
    contract: EvidenceContract,
    region_id: str,
    participant_ids: Iterable[str],
    expected_overlap_window: tuple[str, str] | None = None,
) -> TrendAgreementSummaryBundle:
    """Reload one contract-backed trend agreement summary by semantics."""

    normalized_participant_ids = normalize_participant_ids(participant_ids)
    participant_set_key = build_participant_set_key(normalized_participant_ids)
    summary_path = trend_agreement_summary_output_path(
        contract,
        region_id=region_id,
        participant_ids=normalized_participant_ids,
    )
    if not summary_path.is_file():
        raise FileNotFoundError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            f"missing trend_agreement_summary path={summary_path}"
        )

    summary = pd.read_csv(summary_path)
    missing_columns = [
        column
        for column in REQUIRED_AGREEMENT_SUMMARY_COLUMNS
        if column not in summary.columns
    ]
    if missing_columns:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            f"missing summary columns={', '.join(missing_columns)}"
        )
    if summary.empty:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "summary must not be empty"
        )
    if any(str(value).strip() != region_id for value in summary["region_id"]):
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "summary contains mixed region_id values"
        )
    if any(
        str(value).strip() != participant_set_key
        for value in summary["participant_set_key"]
    ):
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "summary contains mixed participant_set_key values"
        )
    for value in summary["participant_ids_json"]:
        if _parse_participant_ids_json_with_context(
            value,
            region_id=region_id,
            participant_set_key=participant_set_key,
            label="participant_ids_json",
        ) != normalized_participant_ids:
            raise ValueError(
                "stage=agreement "
                f"region_id={region_id} participant_set_key={participant_set_key} "
                "summary contains mixed participant ids"
            )

    overlap_start_values = {
        str(value).strip() for value in summary["overlap_window_start"]
    }
    overlap_end_values = {
        str(value).strip() for value in summary["overlap_window_end"]
    }
    if len(overlap_start_values) != 1 or len(overlap_end_values) != 1:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "summary must contain exactly one overlap_window value"
        )
    overlap_window = (
        overlap_start_values.pop(),
        overlap_end_values.pop(),
    )
    if not overlap_window[0] or not overlap_window[1]:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "summary is missing overlap_window metadata"
        )
    if expected_overlap_window is not None and overlap_window != expected_overlap_window:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            f"overlap_window mismatch={overlap_window!r}"
        )

    metadata_values = {str(value).strip() for value in summary["contract_metadata_json"]}
    if len(metadata_values) != 1:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "summary must contain exactly one contract_metadata_json value"
        )
    contract_metadata_json = metadata_values.pop()
    contract_metadata = _parse_json_object_with_context(
        contract_metadata_json,
        stage="agreement",
        region_id=region_id,
        context_label="participant_set_key",
        context_value=participant_set_key,
        label="contract_metadata_json",
    )

    return TrendAgreementSummaryBundle(
        summary_path=summary_path.resolve(),
        region_id=region_id,
        participant_ids=normalized_participant_ids,
        participant_set_key=participant_set_key,
        overlap_window=overlap_window,
        table=summary,
        contract_metadata_json=contract_metadata_json,
        contract_metadata=contract_metadata,
    )


def load_contract_trend_agreement_artifacts(
    *,
    contract: EvidenceContract,
    region_id: str,
    participant_ids: Iterable[str],
    expected_overlap_window: tuple[str, str] | None = None,
) -> TrendAgreementReload:
    """Reload one validated trend agreement surface/summary pair by semantics."""

    normalized_participant_ids = normalize_participant_ids(participant_ids)
    participant_set_key = build_participant_set_key(normalized_participant_ids)
    surface_path = trend_agreement_surface_output_path(
        contract,
        region_id=region_id,
        participant_ids=normalized_participant_ids,
    )
    summary_path = trend_agreement_summary_output_path(
        contract,
        region_id=region_id,
        participant_ids=normalized_participant_ids,
    )
    _require_complete_pair(
        label="agreement",
        region_id=region_id,
        family_key=participant_set_key,
        left_path=surface_path,
        right_path=summary_path,
    )

    surface_bundle = load_contract_trend_agreement_surface(
        contract=contract,
        region_id=region_id,
        participant_ids=normalized_participant_ids,
        expected_overlap_window=expected_overlap_window,
    )
    summary_bundle = load_contract_trend_agreement_summary(
        contract=contract,
        region_id=region_id,
        participant_ids=normalized_participant_ids,
        expected_overlap_window=expected_overlap_window,
    )
    if summary_bundle.overlap_window != surface_bundle.overlap_window:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "summary overlap_window does not match surface overlap_window"
        )
    if summary_bundle.contract_metadata_json != surface_bundle.contract_metadata_json:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            "summary contract_metadata_json does not match the surface metadata"
        )

    return TrendAgreementReload(
        surface=surface_bundle,
        summary=summary_bundle,
        result=TrendAgreementResult(
            overlap_window=surface_bundle.overlap_window,
            participant_ids=list(normalized_participant_ids),
            agreement_ratio=surface_bundle.dataset["agreement_ratio"],
            mean_slope=surface_bundle.dataset["mean_slope"],
            slope_std=surface_bundle.dataset["slope_std"],
            robust_increase=surface_bundle.dataset["robust_increase"].astype(bool),
            robust_decrease=surface_bundle.dataset["robust_decrease"].astype(bool),
            robust_stable=surface_bundle.dataset["robust_stable"].astype(bool),
            disputed=surface_bundle.dataset["disputed"].astype(bool),
            regional_summary=summary_bundle.table.copy(),
            status=surface_bundle.status,
        ),
    )


def _build_summary_row(
    *,
    region_id: str,
    region_label: str,
    bbox: BBox,
    trend_result: TrendResult,
    contract_metadata_json: str,
) -> dict[str, object]:
    if trend_result.status == "computed":
        summary = compute_regional_summary(trend_result, {region_id: bbox})
        region_rows = summary.loc[summary["region"].astype(str) == region_id].copy()
        if len(region_rows) != 1:
            raise ValueError(
                "stage=trend-write "
                f"region_id={region_id} dataset_id={trend_result.dataset_id} "
                "expected exactly one regional summary row"
            )
        row = region_rows.iloc[0].to_dict()
    else:
        row = {
            "region": region_id,
            "dataset_id": trend_result.dataset_id,
            "aggregation": trend_result.aggregation,
            "total_valid_pixels": 0,
            "mean_slope": np.nan,
            "median_slope": np.nan,
            "fraction_significant": np.nan,
            "fraction_increasing": np.nan,
            "fraction_decreasing": np.nan,
            "fraction_stable": np.nan,
        }

    row.update(
        {
            "region": region_id,
            "region_id": region_id,
            "region_label": region_label,
            "dataset_id": trend_result.dataset_id,
            "aggregation": trend_result.aggregation,
            "time_range_start": trend_result.time_range[0],
            "time_range_end": trend_result.time_range[1],
            "observation_count": int(trend_result.observation_count),
            "status": trend_result.status,
            "bbox_json": json.dumps(list(bbox), separators=(",", ":")),
            "contract_metadata_json": contract_metadata_json,
        }
    )
    return row


def _parse_json_object(
    value: object,
    *,
    region_id: str,
    dataset_id: str,
    label: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={dataset_id} malformed {label}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={dataset_id} {label} must decode to an object"
        )
    return payload


def _parse_bbox_literal(
    value: object,
    *,
    region_id: str,
    dataset_id: str,
    label: str,
) -> BBox:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={dataset_id} malformed {label}"
        ) from exc
    if not isinstance(payload, list) or len(payload) != 4:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={dataset_id} {label} must decode to a 4-item list"
        )
    bbox = tuple(float(item) for item in payload)
    west, south, east, north = bbox
    if west >= east or south >= north:
        raise ValueError(
            "stage=trend-write "
            f"region_id={region_id} dataset_id={dataset_id} invalid {label} bounds"
        )
    return cast(BBox, bbox)


def _parse_json_object_with_context(
    value: object,
    *,
    stage: str,
    region_id: str,
    context_label: str,
    context_value: str,
    label: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"stage={stage} "
            f"region_id={region_id} {context_label}={context_value} malformed {label}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(
            f"stage={stage} "
            f"region_id={region_id} {context_label}={context_value} "
            f"{label} must decode to an object"
        )
    return payload


def _parse_participant_ids_json_with_context(
    value: object,
    *,
    region_id: str,
    participant_set_key: str,
    label: str,
) -> tuple[str, ...]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} malformed {label}"
        ) from exc
    if not isinstance(payload, list):
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            f"{label} must decode to a list"
        )
    try:
        return normalize_participant_ids(payload)
    except ValueError as exc:
        raise ValueError(
            "stage=agreement "
            f"region_id={region_id} participant_set_key={participant_set_key} "
            f"invalid {label}: {exc}"
        ) from exc


def _require_complete_pair(
    *,
    label: str,
    region_id: str,
    family_key: str,
    left_path: Path,
    right_path: Path,
) -> None:
    left_exists = left_path.is_file()
    right_exists = right_path.is_file()
    if left_exists and right_exists:
        return
    if left_exists or right_exists:
        raise FileNotFoundError(
            f"stage={label} region_id={region_id} "
            f"family_key={family_key} found partial artifact pair: "
            f"{left_path} exists={left_exists} {right_path} exists={right_exists}"
        )


def _write_dataset_atomic(path: Path, dataset: xr.Dataset) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        dataset.to_netcdf(temp_path)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    try:
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
