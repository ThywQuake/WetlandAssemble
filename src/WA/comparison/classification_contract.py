"""Contract-backed Phase 4 classification surface, summary, and hotspot helpers.

This module is a thin adapter over the real Phase 3.6 and Phase 3.7 producers:

- Phase 3.6 (`WA.comparison.phase36`) remains the only owner of the
  classification disagreement science and the full diagnostic surfaces.
- Phase 3.7 (`WA.phase37_hotspots`) remains the only owner of the hotspot
  selection logic and source manifest/CSV outputs.

The adapter here only:
- subsets one region from the global Phase 3.6 outputs
- rewrites one region-scoped contract surface and summary family
- rewrites one region-scoped hotspot manifest/CSV pair from the Phase 3.7
  source trio
- reloads those contract artifacts by semantics instead of guessed filenames
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from WA.comparison.evidence_contract import (
    EvidenceContract,
    metadata_json,
    validate_stem_token,
)
from WA.comparison.phase36 import PHASE36_DATASET_IDS
from WA.loaders.base import BBox

logger = logging.getLogger(__name__)

CLASSIFICATION_CONTRACT_DATASET_KEY = "canonical"
CLASSIFICATION_PARTICIPANT_IDS = PHASE36_DATASET_IDS
CLASSIFICATION_PARTICIPANT_SET_KEY = "+".join(CLASSIFICATION_PARTICIPANT_IDS)
CLASSIFICATION_HOTSPOT_MANIFEST_VERSION = 1

REQUIRED_PHASE36_METRICS_VARS = (
    "entropy",
    "majority_class",
    "agreement_count",
    "joint_valid_mask",
)
REQUIRED_PHASE36_DOMINANT_VARS = (
    "g2017_dominant_class",
    "glwd_v2_dominant_class",
    "gwd30_dominant_class",
    "g2017_source_dominant_class",
    "glwd_v2_source_dominant_class",
    "gwd30_source_dominant_class",
)
REQUIRED_CLASSIFICATION_SURFACE_VARS = (
    *REQUIRED_PHASE36_METRICS_VARS,
    *REQUIRED_PHASE36_DOMINANT_VARS,
)
CLASSIFICATION_SUMMARY_COLUMNS = (
    "region_id",
    "region_label",
    "dataset_key",
    "participant_set_key",
    "participant_ids_json",
    "target_year",
    "joint_valid_cell_count",
    "mean_entropy",
    "max_entropy",
    "mean_agreement_count",
    "agreement_count_1",
    "agreement_count_2",
    "agreement_count_3",
    "hotspot_selected_count",
    "hotspot_quota",
    "hotspot_shortfall",
    "hotspot_threshold_percentile",
    "hotspot_threshold_value",
    "hotspot_status",
    "contract_metadata_json",
)
CLASSIFICATION_HOTSPOT_TABLE_COLUMNS = (
    "hotspot_id",
    "hotspot_rank",
    "region_id",
    "dataset_key",
    "participant_set_key",
    "participant_ids_json",
    "center_lat",
    "center_lon",
    "bbox",
    "mean_entropy",
    "max_entropy",
    "cell_count",
    "region_rank",
    "threshold_percentile",
    "threshold_value",
    "selection_rules_version",
    "source_hotspot_id",
)
REQUIRED_PHASE37_HOTSPOT_COLUMNS = (
    "hotspot_id",
    "region_id",
    "bbox",
    "center_lon",
    "center_lat",
    "mean_entropy",
    "max_entropy",
    "cell_count",
    "region_rank",
    "threshold_percentile",
    "threshold_value",
    "selection_rules_version",
    "source",
)
REQUIRED_PHASE37_REGION_COLUMNS = (
    "region_id",
    "region_label",
    "bbox",
    "quota",
    "selected_count",
    "shortfall",
    "threshold_percentile",
    "threshold_value",
    "status",
)


@dataclass(frozen=True)
class ClassificationSurfaceBundle:
    """One contract-backed region-scoped classification surface artifact."""

    surface_path: Path
    region_id: str
    region_label: str
    dataset_key: str
    participant_ids: tuple[str, ...]
    participant_set_key: str
    bbox: BBox
    target_year: int
    dataset: xr.Dataset
    contract_metadata_json: str
    contract_metadata: dict[str, Any]


@dataclass(frozen=True)
class ClassificationSummaryBundle:
    """One contract-backed region-scoped classification summary artifact."""

    summary_path: Path
    region_id: str
    region_label: str
    dataset_key: str
    participant_ids: tuple[str, ...]
    participant_set_key: str
    target_year: int
    table: pd.DataFrame
    contract_metadata_json: str
    contract_metadata: dict[str, Any]


@dataclass(frozen=True)
class ClassificationHotspotManifest:
    """Validated metadata for one classification hotspot JSON/CSV pair."""

    manifest_path: Path
    table_path: Path
    region_id: str
    dataset_key: str
    participant_ids: tuple[str, ...]
    participant_set_key: str
    hotspot_count: int
    surface_output_path: Path
    summary_output_path: Path
    contract_metadata_json: str
    contract_metadata: dict[str, Any]
    table_sha256: str
    manifest_relpath: str
    table_relpath: str
    surface_output_relpath: str | None
    summary_output_relpath: str | None


@dataclass(frozen=True)
class ClassificationHotspotReload:
    """Reloaded classification hotspot manifest plus validated hotspot table."""

    manifest: ClassificationHotspotManifest
    table: pd.DataFrame


@dataclass(frozen=True)
class Phase37RegionSummaryRecord:
    """Validated Phase 3.7 region summary row for one contract region."""

    region_id: str
    region_label: str
    bbox: BBox
    quota: int
    selected_count: int
    shortfall: int
    threshold_percentile: float
    threshold_value: float | None
    status: str


@dataclass(frozen=True)
class Phase37SourcePaths:
    """On-disk Phase 3.7 source trio paths."""

    manifest_path: Path
    hotspot_csv_path: Path
    region_csv_path: Path


def classification_surface_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_key: str = CLASSIFICATION_CONTRACT_DATASET_KEY,
) -> Path:
    """Return the contract output path for one classification surface."""

    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    return contract.artifact_output_path(
        kind="classification_surface",
        dataset_or_key=normalized_key,
        region_id=region_id,
    )


def classification_summary_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_key: str = CLASSIFICATION_CONTRACT_DATASET_KEY,
) -> Path:
    """Return the contract output path for one classification summary."""

    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    return contract.artifact_output_path(
        kind="classification_regional_summary",
        dataset_or_key=normalized_key,
        region_id=region_id,
    )


def classification_hotspot_manifest_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_key: str = CLASSIFICATION_CONTRACT_DATASET_KEY,
) -> Path:
    """Return the contract output path for one classification hotspot manifest."""

    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    return contract.artifact_output_path(
        kind="classification_hotspot_manifest",
        dataset_or_key=normalized_key,
        region_id=region_id,
    )


def classification_hotspot_table_output_path(
    contract: EvidenceContract,
    *,
    region_id: str,
    dataset_key: str = CLASSIFICATION_CONTRACT_DATASET_KEY,
) -> Path:
    """Return the contract output path for one classification hotspot table."""

    return classification_hotspot_manifest_output_path(
        contract,
        region_id=region_id,
        dataset_key=dataset_key,
    ).with_suffix(".csv")


def phase37_source_paths(
    *,
    output_dir: str | Path,
    year: int,
) -> Phase37SourcePaths:
    """Return the canonical Phase 3.7 source trio paths for one year."""

    root = Path(output_dir)
    return Phase37SourcePaths(
        manifest_path=root / f"phase3_7_hotspots_{year}.json",
        hotspot_csv_path=root / f"phase3_7_hotspots_{year}.csv",
        region_csv_path=root / f"phase3_7_hotspot_regions_{year}.csv",
    )


def write_contract_classification_surface(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_label: str,
    dataset_key: str,
    bbox: BBox,
    target_year: int,
    metrics_path: str | Path,
    dominant_classes_path: str | Path,
) -> ClassificationSurfaceBundle:
    """Subset one region from the global Phase 3.6 outputs and write it.

    Raises with ``region_id``, ``participant_set_key``, and source paths in the
    message so a broken global input does not look like a valid contract output.
    """

    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    source_metrics_path = Path(metrics_path)
    source_dominant_path = Path(dominant_classes_path)
    _require_existing_source_file(
        source_metrics_path,
        region_id=region_id,
        label="metrics_path",
    )
    _require_existing_source_file(
        source_dominant_path,
        region_id=region_id,
        label="dominant_classes_path",
    )

    metrics_dataset = xr.load_dataset(source_metrics_path)
    dominant_dataset = xr.load_dataset(source_dominant_path)
    try:
        _validate_phase36_metrics_dataset(
            metrics_dataset,
            region_id=region_id,
            source_path=source_metrics_path,
        )
        _validate_phase36_dominant_dataset(
            dominant_dataset,
            region_id=region_id,
            source_path=source_dominant_path,
            reference=metrics_dataset,
        )
        metrics_subset = _subset_dataset_to_bbox(
            metrics_dataset,
            bbox=bbox,
            region_id=region_id,
            label="metrics",
            source_path=source_metrics_path,
        )
        dominant_subset = _subset_dataset_to_bbox(
            dominant_dataset,
            bbox=bbox,
            region_id=region_id,
            label="dominant_classes",
            source_path=source_dominant_path,
            reference=metrics_subset,
        )
    finally:
        close_metrics = getattr(metrics_dataset, "close", None)
        if callable(close_metrics):
            close_metrics()
        close_dominant = getattr(dominant_dataset, "close", None)
        if callable(close_dominant):
            close_dominant()

    dataset = xr.Dataset(
        {
            name: metrics_subset[name]
            for name in REQUIRED_PHASE36_METRICS_VARS
        }
        | {
            name: dominant_subset[name]
            for name in REQUIRED_PHASE36_DOMINANT_VARS
        }
    )
    joint_valid_cells = int((dataset["joint_valid_mask"] > 0).sum().item())
    if joint_valid_cells <= 0:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "refusing to write an empty joint-valid classification surface"
        )

    contract_metadata = {
        "artifact_kind": "classification_surface",
        "dataset_key": normalized_key,
        "participant_ids": list(CLASSIFICATION_PARTICIPANT_IDS),
        "participant_set_key": CLASSIFICATION_PARTICIPANT_SET_KEY,
        "region_id": region_id,
        "region_label": region_label,
        "bbox": list(bbox),
        "target_year": int(target_year),
        "source_metrics_path": str(source_metrics_path.resolve()),
        "source_dominant_classes_path": str(source_dominant_path.resolve()),
        "required_variables": list(REQUIRED_CLASSIFICATION_SURFACE_VARS),
    }
    contract_metadata_json = metadata_json(contract_metadata)
    dataset.attrs.update(
        {
            "region_id": region_id,
            "region_label": region_label,
            "dataset_key": normalized_key,
            "participant_set_key": CLASSIFICATION_PARTICIPANT_SET_KEY,
            "participant_ids_json": json.dumps(
                list(CLASSIFICATION_PARTICIPANT_IDS),
                separators=(",", ":"),
            ),
            "bbox_json": json.dumps(list(bbox), separators=(",", ":")),
            "target_year": int(target_year),
            "source_metrics_path": str(source_metrics_path.resolve()),
            "source_dominant_classes_path": str(source_dominant_path.resolve()),
            "contract_metadata_json": contract_metadata_json,
        }
    )

    surface_path = classification_surface_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    _write_dataset_atomic(surface_path, dataset)
    logger.info(
        "stage=classification_contract_write region=%s participant_set_key=%s "
        "action=surface-write-complete dataset_key=%s path=%s",
        region_id,
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        normalized_key,
        surface_path,
    )
    return load_contract_classification_surface(
        contract=contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )


def load_contract_classification_surface(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_key: str = CLASSIFICATION_CONTRACT_DATASET_KEY,
) -> ClassificationSurfaceBundle:
    """Reload one contract-backed classification surface by semantics."""

    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    surface_path = classification_surface_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    if not surface_path.is_file():
        raise FileNotFoundError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"missing classification_surface path={surface_path}"
        )

    dataset = xr.load_dataset(surface_path)
    missing_vars = [
        name for name in REQUIRED_CLASSIFICATION_SURFACE_VARS if name not in dataset.data_vars
    ]
    if missing_vars:
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "classification surface is missing required variables: "
            + ", ".join(missing_vars)
        )
    if str(dataset.attrs.get("region_id", "")).strip() != region_id:
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "classification surface region_id does not match the requested region"
        )
    if str(dataset.attrs.get("dataset_key", "")).strip() != normalized_key:
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "classification surface dataset_key does not match the requested key"
        )
    if (
        str(dataset.attrs.get("participant_set_key", "")).strip()
        != CLASSIFICATION_PARTICIPANT_SET_KEY
    ):
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "classification surface participant_set_key does not match"
        )

    participant_ids = _parse_participant_ids_json(
        dataset.attrs.get("participant_ids_json", ""),
    )
    if participant_ids != CLASSIFICATION_PARTICIPANT_IDS:
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} participant_ids mismatch"
        )

    bbox = _parse_bbox_literal(
        dataset.attrs.get("bbox_json", ""),
        region_id=region_id,
        label="bbox_json",
    )
    joint_valid_cells = int((dataset["joint_valid_mask"] > 0).sum().item())
    if joint_valid_cells <= 0:
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "classification surface is empty on the joint-valid domain"
        )

    contract_metadata_json = str(dataset.attrs.get("contract_metadata_json", "")).strip()
    if not contract_metadata_json:
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "classification surface is missing contract_metadata_json"
        )
    contract_metadata = _parse_json_object(
        contract_metadata_json,
        label="contract_metadata_json",
        region_id=region_id,
    )

    logger.info(
        "stage=classification_reload region=%s participant_set_key=%s "
        "action=surface-ready dataset_key=%s path=%s",
        region_id,
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        normalized_key,
        surface_path,
    )
    return ClassificationSurfaceBundle(
        surface_path=surface_path.resolve(),
        region_id=region_id,
        region_label=str(dataset.attrs.get("region_label", region_id)),
        dataset_key=normalized_key,
        participant_ids=participant_ids,
        participant_set_key=CLASSIFICATION_PARTICIPANT_SET_KEY,
        bbox=bbox,
        target_year=int(dataset.attrs.get("target_year", 0)),
        dataset=dataset,
        contract_metadata_json=contract_metadata_json,
        contract_metadata=contract_metadata,
    )


def write_contract_classification_summary(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_label: str,
    dataset_key: str,
    target_year: int,
    source_region_summary_path: str | Path,
) -> ClassificationSummaryBundle:
    """Write one region-scoped classification summary from contract semantics."""

    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    surface_bundle = load_contract_classification_surface(
        contract=contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    region_summary = load_phase37_region_summary_record(
        source_region_summary_path,
        region_id=region_id,
    )

    joint_valid = np.asarray(surface_bundle.dataset["joint_valid_mask"].values) > 0
    entropy = np.asarray(surface_bundle.dataset["entropy"].values, dtype=np.float64)
    agreement_count = np.asarray(
        surface_bundle.dataset["agreement_count"].values,
        dtype=np.int16,
    )
    valid_entropy = entropy[joint_valid]
    valid_agreement = agreement_count[joint_valid]
    if valid_entropy.size == 0 or valid_agreement.size == 0:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "summary cannot be written because the region has no joint-valid cells"
        )

    contract_metadata = {
        "artifact_kind": "classification_regional_summary",
        "dataset_key": normalized_key,
        "participant_ids": list(CLASSIFICATION_PARTICIPANT_IDS),
        "participant_set_key": CLASSIFICATION_PARTICIPANT_SET_KEY,
        "region_id": region_id,
        "region_label": region_label,
        "bbox": list(surface_bundle.bbox),
        "target_year": int(target_year),
        "surface_output_path": str(surface_bundle.surface_path),
        "surface_output_relpath": _relative_to_root(
            surface_bundle.surface_path,
            contract.output_root,
        ),
        "source_region_summary_path": str(Path(source_region_summary_path).resolve()),
    }
    contract_metadata_json = metadata_json(contract_metadata)

    table = pd.DataFrame(
        [
            {
                "region_id": region_id,
                "region_label": region_label,
                "dataset_key": normalized_key,
                "participant_set_key": CLASSIFICATION_PARTICIPANT_SET_KEY,
                "participant_ids_json": json.dumps(
                    list(CLASSIFICATION_PARTICIPANT_IDS),
                    separators=(",", ":"),
                ),
                "target_year": int(target_year),
                "joint_valid_cell_count": int(joint_valid.sum()),
                "mean_entropy": float(np.nanmean(valid_entropy)),
                "max_entropy": float(np.nanmax(valid_entropy)),
                "mean_agreement_count": float(np.nanmean(valid_agreement)),
                "agreement_count_1": int(np.sum(valid_agreement == 1)),
                "agreement_count_2": int(np.sum(valid_agreement == 2)),
                "agreement_count_3": int(np.sum(valid_agreement == 3)),
                "hotspot_selected_count": int(region_summary.selected_count),
                "hotspot_quota": int(region_summary.quota),
                "hotspot_shortfall": int(region_summary.shortfall),
                "hotspot_threshold_percentile": float(
                    region_summary.threshold_percentile
                ),
                "hotspot_threshold_value": region_summary.threshold_value,
                "hotspot_status": region_summary.status,
                "contract_metadata_json": contract_metadata_json,
            }
        ]
    ).loc[:, list(CLASSIFICATION_SUMMARY_COLUMNS)]

    summary_path = classification_summary_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    _write_text_atomic(summary_path, table.to_csv(index=False, lineterminator="\n"))
    logger.info(
        "stage=classification_contract_write region=%s participant_set_key=%s "
        "action=summary-write-complete dataset_key=%s path=%s",
        region_id,
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        normalized_key,
        summary_path,
    )
    return load_contract_classification_summary(
        contract=contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )


def load_contract_classification_summary(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_key: str = CLASSIFICATION_CONTRACT_DATASET_KEY,
) -> ClassificationSummaryBundle:
    """Reload one contract-backed classification summary by semantics."""

    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    summary_path = classification_summary_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    if not summary_path.is_file():
        raise FileNotFoundError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"missing classification_regional_summary path={summary_path}"
        )

    table = pd.read_csv(summary_path)
    missing_columns = [
        column for column in CLASSIFICATION_SUMMARY_COLUMNS if column not in table.columns
    ]
    if missing_columns:
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "classification summary is missing required columns: "
            + ", ".join(missing_columns)
        )
    if table.empty:
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "classification summary must not be empty"
        )
    if any(str(value).strip() != region_id for value in table["region_id"]):
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} summary contains mixed region_id values"
        )
    if any(str(value).strip() != normalized_key for value in table["dataset_key"]):
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} summary contains mixed dataset_key values"
        )
    if any(
        str(value).strip() != CLASSIFICATION_PARTICIPANT_SET_KEY
        for value in table["participant_set_key"]
    ):
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "summary contains mixed participant_set_key values"
        )
    for value in table["participant_ids_json"]:
        if _parse_participant_ids_json(value) != CLASSIFICATION_PARTICIPANT_IDS:
            raise ValueError(
                "stage=classification_reload "
                f"region_id={region_id} participant_set_key="
                f"{CLASSIFICATION_PARTICIPANT_SET_KEY} summary contains mixed participant ids"
            )

    metadata_values = {str(value).strip() for value in table["contract_metadata_json"]}
    if len(metadata_values) != 1:
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "summary must contain exactly one contract_metadata_json value"
        )
    contract_metadata_json = metadata_values.pop()
    contract_metadata = _parse_json_object(
        contract_metadata_json,
        label="contract_metadata_json",
        region_id=region_id,
    )

    logger.info(
        "stage=classification_reload region=%s participant_set_key=%s "
        "action=summary-ready dataset_key=%s path=%s",
        region_id,
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        normalized_key,
        summary_path,
    )
    return ClassificationSummaryBundle(
        summary_path=summary_path.resolve(),
        region_id=region_id,
        region_label=str(table["region_label"].iloc[0]),
        dataset_key=normalized_key,
        participant_ids=CLASSIFICATION_PARTICIPANT_IDS,
        participant_set_key=CLASSIFICATION_PARTICIPANT_SET_KEY,
        target_year=int(table["target_year"].iloc[0]),
        table=table,
        contract_metadata_json=contract_metadata_json,
        contract_metadata=contract_metadata,
    )


def write_contract_classification_hotspot_outputs(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_key: str,
    source_manifest_path: str | Path,
    source_hotspot_table_path: str | Path,
    source_region_summary_path: str | Path,
) -> ClassificationHotspotManifest:
    """Rewrite one region-scoped classification hotspot family.

    The selection itself still comes from the Phase 3.7 source trio. This
    function only validates and rewrites that source into stable Phase 4
    contract semantics.
    """

    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    surface_bundle = load_contract_classification_surface(
        contract=contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    summary_bundle = load_contract_classification_summary(
        contract=contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    source_rows, region_summary, source_metadata = _load_phase37_source_rows_for_region(
        region_id=region_id,
        manifest_path=source_manifest_path,
        hotspot_table_path=source_hotspot_table_path,
        region_summary_path=source_region_summary_path,
    )

    surface_metrics_path = Path(
        str(surface_bundle.contract_metadata.get("source_metrics_path", "")).strip()
    )
    surface_dominant_path = Path(
        str(
            surface_bundle.contract_metadata.get(
                "source_dominant_classes_path",
                "",
            )
        ).strip()
    )
    source_metrics_path = Path(str(source_metadata["metrics_path"])).resolve()
    source_classes_path = Path(str(source_metadata["classes_path"])).resolve()
    if surface_metrics_path.resolve() != source_metrics_path:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "surface source_metrics_path does not match the Phase 3.7 manifest"
        )
    if surface_dominant_path.resolve() != source_classes_path:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "surface source_dominant_classes_path does not match the Phase 3.7 manifest"
        )

    participant_ids_json = json.dumps(
        list(CLASSIFICATION_PARTICIPANT_IDS),
        separators=(",", ":"),
    )
    rows: list[dict[str, object]] = []
    ordered_source_rows = source_rows.sort_values(
        ["region_rank", "center_lat", "center_lon"],
        ascending=[True, False, True],
    )
    for rank, (_, row) in enumerate(ordered_source_rows.iterrows(), start=1):
        rows.append(
            {
                "hotspot_id": f"cls-{region_id}-{normalized_key}-{rank:03d}",
                "hotspot_rank": rank,
                "region_id": region_id,
                "dataset_key": normalized_key,
                "participant_set_key": CLASSIFICATION_PARTICIPANT_SET_KEY,
                "participant_ids_json": participant_ids_json,
                "center_lat": float(row["center_lat"]),
                "center_lon": float(row["center_lon"]),
                "bbox": _parse_bbox_literal(
                    row["bbox"],
                    region_id=region_id,
                    label="source hotspot bbox",
                ),
                "mean_entropy": float(row["mean_entropy"]),
                "max_entropy": float(row["max_entropy"]),
                "cell_count": int(row["cell_count"]),
                "region_rank": int(row["region_rank"]),
                "threshold_percentile": float(row["threshold_percentile"]),
                "threshold_value": float(row["threshold_value"]),
                "selection_rules_version": str(row["selection_rules_version"]).strip(),
                "source_hotspot_id": str(row["hotspot_id"]).strip(),
            }
        )
    table = pd.DataFrame(rows).loc[:, list(CLASSIFICATION_HOTSPOT_TABLE_COLUMNS)]
    if table.empty:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "no Phase 3.7 source hotspot rows remained after validation"
        )

    manifest_path = classification_hotspot_manifest_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    table_path = classification_hotspot_table_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    serializable = table.copy()
    serializable["bbox"] = serializable["bbox"].map(
        lambda value: json.dumps(list(value), separators=(",", ":"))
    )
    table_text = serializable.to_csv(index=False, lineterminator="\n")
    table_sha256 = hashlib.sha256(table_text.encode("utf-8")).hexdigest()

    manifest_relpath = str(
        manifest_path.resolve().relative_to(contract.output_root.resolve())
    )
    table_relpath = str(
        table_path.resolve().relative_to(contract.output_root.resolve())
    )
    surface_relpath = _relative_to_root(surface_bundle.surface_path, contract.output_root)
    summary_relpath = _relative_to_root(summary_bundle.summary_path, contract.output_root)
    contract_metadata = {
        "artifact_kind": "classification_hotspot_manifest",
        "dataset_key": normalized_key,
        "participant_ids": list(CLASSIFICATION_PARTICIPANT_IDS),
        "participant_set_key": CLASSIFICATION_PARTICIPANT_SET_KEY,
        "region_id": region_id,
        "region_label": surface_bundle.region_label,
        "surface_output_path": str(surface_bundle.surface_path),
        "surface_output_relpath": surface_relpath,
        "summary_output_path": str(summary_bundle.summary_path),
        "summary_output_relpath": summary_relpath,
        "source_manifest_path": str(Path(source_manifest_path).resolve()),
        "source_hotspot_table_path": str(Path(source_hotspot_table_path).resolve()),
        "source_region_summary_path": str(Path(source_region_summary_path).resolve()),
        "source_selection_rules_version": str(
            source_metadata["selection_rules_version"]
        ),
        "hotspot_ranking": ["phase37 region_rank asc"],
        "region_hotspot_quota": int(region_summary.quota),
        "region_hotspot_selected_count": int(region_summary.selected_count),
        "region_hotspot_shortfall": int(region_summary.shortfall),
        "table_sha256": table_sha256,
    }
    manifest_payload = {
        "artifact_kind": "classification_hotspot_manifest",
        "manifest_version": CLASSIFICATION_HOTSPOT_MANIFEST_VERSION,
        "region_id": region_id,
        "dataset_key": normalized_key,
        "participant_ids": list(CLASSIFICATION_PARTICIPANT_IDS),
        "participant_set_key": CLASSIFICATION_PARTICIPANT_SET_KEY,
        "hotspot_count": int(len(table)),
        "manifest_output_path": str(manifest_path.resolve()),
        "manifest_relpath": manifest_relpath,
        "table_output_path": str(table_path.resolve()),
        "table_relpath": table_relpath,
        "surface_output_path": str(surface_bundle.surface_path),
        "surface_output_relpath": surface_relpath,
        "summary_output_path": str(summary_bundle.summary_path),
        "summary_output_relpath": summary_relpath,
        "table_columns": list(CLASSIFICATION_HOTSPOT_TABLE_COLUMNS),
        "table_sha256": table_sha256,
        "contract_metadata_json": metadata_json(contract_metadata),
    }
    manifest_text = json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n"

    _write_text_atomic(table_path, table_text)
    _write_text_atomic(manifest_path, manifest_text)
    logger.info(
        "stage=classification_contract_write region=%s participant_set_key=%s "
        "action=hotspots-write-complete dataset_key=%s hotspots=%s manifest=%s table=%s",
        region_id,
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        normalized_key,
        len(table),
        manifest_path,
        table_path,
    )
    return load_classification_hotspot_manifest(manifest_path)


def load_classification_hotspot_manifest(
    path: str | Path,
) -> ClassificationHotspotManifest:
    """Load and validate one classification hotspot manifest JSON file."""

    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(
            f"Classification hotspot manifest must be a JSON object: {manifest_path}"
        )
    if payload.get("artifact_kind") != "classification_hotspot_manifest":
        raise ValueError(
            "Expected artifact_kind='classification_hotspot_manifest', got "
            f"{payload.get('artifact_kind')!r}"
        )

    dataset_key = validate_stem_token(str(payload.get("dataset_key", "")), label="dataset_key")
    region_id = validate_stem_token(str(payload.get("region_id", "")), label="region_id")
    participant_ids = _parse_participant_ids_json(payload.get("participant_ids", []))
    participant_set_key = str(payload.get("participant_set_key", "")).strip()
    if participant_ids != CLASSIFICATION_PARTICIPANT_IDS:
        raise ValueError(
            "Classification hotspot manifest participant_ids do not match the fixed "
            "classification participant set"
        )
    if participant_set_key != CLASSIFICATION_PARTICIPANT_SET_KEY:
        raise ValueError(
            "Classification hotspot manifest participant_set_key does not match the "
            "fixed classification participant set"
        )

    hotspot_count = int(payload.get("hotspot_count", 0))
    if hotspot_count <= 0:
        raise ValueError("Classification hotspot manifest hotspot_count must be positive")

    table_sha256 = str(payload.get("table_sha256", "")).strip()
    if len(table_sha256) != 64:
        raise ValueError(
            "Classification hotspot manifest table_sha256 must be a SHA-256 hex digest"
        )

    manifest_output_path = Path(str(payload.get("manifest_output_path", manifest_path)))
    if manifest_output_path.resolve() != manifest_path.resolve():
        raise ValueError(
            "Classification hotspot manifest_output_path does not match the loaded path"
        )

    table_path = Path(str(payload.get("table_output_path", "")))
    surface_output_path = Path(str(payload.get("surface_output_path", "")))
    summary_output_path = Path(str(payload.get("summary_output_path", "")))
    for label, candidate in (
        ("table_output_path", table_path),
        ("surface_output_path", surface_output_path),
        ("summary_output_path", summary_output_path),
    ):
        if not str(candidate).strip():
            raise ValueError(f"Classification hotspot manifest is missing {label}")
        if not candidate.is_file():
            raise FileNotFoundError(
                f"Classification hotspot manifest references missing {label}: {candidate}"
            )

    contract_metadata_json = str(payload.get("contract_metadata_json", "")).strip()
    if not contract_metadata_json:
        raise ValueError(
            "Classification hotspot manifest is missing contract_metadata_json"
        )
    contract_metadata = _parse_json_object(
        contract_metadata_json,
        label="contract_metadata_json",
        region_id=region_id,
    )

    manifest_relpath = str(payload.get("manifest_relpath", "")).strip()
    table_relpath = str(payload.get("table_relpath", "")).strip()
    if not manifest_relpath or not table_relpath:
        raise ValueError(
            "Classification hotspot manifest must contain manifest_relpath and table_relpath"
        )

    return ClassificationHotspotManifest(
        manifest_path=manifest_path.resolve(),
        table_path=table_path.resolve(),
        region_id=region_id,
        dataset_key=dataset_key,
        participant_ids=participant_ids,
        participant_set_key=participant_set_key,
        hotspot_count=hotspot_count,
        surface_output_path=surface_output_path.resolve(),
        summary_output_path=summary_output_path.resolve(),
        contract_metadata_json=contract_metadata_json,
        contract_metadata=contract_metadata,
        table_sha256=table_sha256,
        manifest_relpath=manifest_relpath,
        table_relpath=table_relpath,
        surface_output_relpath=_optional_string(payload.get("surface_output_relpath")),
        summary_output_relpath=_optional_string(payload.get("summary_output_relpath")),
    )


def load_contract_classification_hotspot_table(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_key: str = CLASSIFICATION_CONTRACT_DATASET_KEY,
) -> ClassificationHotspotReload:
    """Load one classification hotspot JSON/CSV pair by contract semantics."""

    normalized_key = validate_stem_token(dataset_key, label="dataset_key")
    surface_bundle = load_contract_classification_surface(
        contract=contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    summary_bundle = load_contract_classification_summary(
        contract=contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    manifest_path = classification_hotspot_manifest_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    )
    expected_table_path = classification_hotspot_table_output_path(
        contract,
        region_id=region_id,
        dataset_key=normalized_key,
    ).resolve()
    manifest = load_classification_hotspot_manifest(manifest_path)
    if manifest.region_id != region_id:
        raise ValueError(
            "Classification hotspot manifest region mismatch: "
            f"expected {region_id!r}, got {manifest.region_id!r}"
        )
    if manifest.dataset_key != normalized_key:
        raise ValueError(
            "Classification hotspot manifest dataset_key does not match the request"
        )
    if manifest.participant_ids != CLASSIFICATION_PARTICIPANT_IDS:
        raise ValueError(
            "Classification hotspot manifest participant_ids do not match the fixed set"
        )
    if manifest.table_path != expected_table_path:
        raise ValueError(
            "Classification hotspot manifest table_output_path does not match contract semantics"
        )
    if manifest.surface_output_path != surface_bundle.surface_path:
        raise ValueError(
            "Classification hotspot manifest surface_output_path does not match contract semantics"
        )
    if manifest.summary_output_path != summary_bundle.summary_path:
        raise ValueError(
            "Classification hotspot manifest summary_output_path does not match contract semantics"
        )

    table_text = manifest.table_path.read_text(encoding="utf-8")
    table_sha256 = hashlib.sha256(table_text.encode("utf-8")).hexdigest()
    if table_sha256 != manifest.table_sha256:
        raise ValueError(
            "Classification hotspot table SHA mismatch; refusing to reuse a partial "
            "or stale JSON/CSV pair"
        )

    table = pd.read_csv(manifest.table_path)
    _validate_classification_hotspot_table(
        table,
        region_id=region_id,
        dataset_key=normalized_key,
        hotspot_count=manifest.hotspot_count,
    )
    parsed = table.copy()
    parsed["bbox"] = parsed["bbox"].map(
        lambda value: _parse_bbox_literal(
            value,
            region_id=region_id,
            label="classification hotspot bbox",
        )
    )
    parsed["participant_ids"] = parsed["participant_ids_json"].map(
        _parse_participant_ids_json
    )
    logger.info(
        "stage=classification_reload region=%s participant_set_key=%s "
        "action=hotspots-ready dataset_key=%s hotspots=%s",
        region_id,
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        normalized_key,
        len(parsed),
    )
    return ClassificationHotspotReload(manifest=manifest, table=parsed)


def load_phase37_region_summary_record(
    source_region_summary_path: str | Path,
    *,
    region_id: str,
) -> Phase37RegionSummaryRecord:
    """Reload one Phase 3.7 region summary row with strict validation."""

    path = Path(source_region_summary_path)
    if not path.is_file():
        raise FileNotFoundError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"missing phase37 region summary path={path}"
        )
    table = pd.read_csv(path)
    missing_columns = [
        column for column in REQUIRED_PHASE37_REGION_COLUMNS if column not in table.columns
    ]
    if missing_columns:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "phase37 region summary is missing required columns: "
            + ", ".join(missing_columns)
        )
    region_rows = table.loc[table["region_id"].astype(str).str.strip() == region_id].copy()
    if len(region_rows) != 1:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "phase37 region summary must contain exactly one row for the requested region"
        )

    row = region_rows.iloc[0]
    bbox = _parse_bbox_literal(row["bbox"], region_id=region_id, label="phase37 region bbox")
    quota = int(row["quota"])
    selected_count = int(row["selected_count"])
    shortfall = int(row["shortfall"])
    if quota <= 0:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} phase37 quota must be positive"
        )
    if selected_count < 0 or shortfall < 0:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} phase37 selected_count/shortfall must be >= 0"
        )

    threshold_value_raw = row["threshold_value"]
    threshold_value = None if pd.isna(threshold_value_raw) else float(threshold_value_raw)
    return Phase37RegionSummaryRecord(
        region_id=region_id,
        region_label=str(row["region_label"]),
        bbox=bbox,
        quota=quota,
        selected_count=selected_count,
        shortfall=shortfall,
        threshold_percentile=float(row["threshold_percentile"]),
        threshold_value=threshold_value,
        status=str(row["status"]).strip(),
    )


def _validate_phase36_metrics_dataset(
    dataset: xr.Dataset,
    *,
    region_id: str,
    source_path: Path,
) -> None:
    missing_vars = [
        name for name in REQUIRED_PHASE36_METRICS_VARS if name not in dataset.data_vars
    ]
    if missing_vars:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} source_path={source_path} "
            "phase36 metrics dataset is missing required variables: "
            + ", ".join(missing_vars)
        )
    _spatial_dims(dataset["entropy"])


def _validate_phase36_dominant_dataset(
    dataset: xr.Dataset,
    *,
    region_id: str,
    source_path: Path,
    reference: xr.Dataset,
) -> None:
    missing_vars = [
        name for name in REQUIRED_PHASE36_DOMINANT_VARS if name not in dataset.data_vars
    ]
    if missing_vars:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} source_path={source_path} "
            "phase36 dominant dataset is missing required variables: "
            + ", ".join(missing_vars)
        )
    reference_y_dim, reference_x_dim = _spatial_dims(reference["entropy"])
    dominant_y_dim, dominant_x_dim = _spatial_dims(dataset["g2017_dominant_class"])
    if (dominant_y_dim, dominant_x_dim) != (reference_y_dim, reference_x_dim):
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"source_path={source_path} dominant spatial dims do not match metrics"
        )
    if not np.array_equal(
        dataset.coords[dominant_y_dim].values,
        reference.coords[reference_y_dim].values,
    ):
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"source_path={source_path} dominant y coordinates do not match metrics"
        )
    if not np.array_equal(
        dataset.coords[dominant_x_dim].values,
        reference.coords[reference_x_dim].values,
    ):
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"source_path={source_path} dominant x coordinates do not match metrics"
        )


def _load_phase37_source_rows_for_region(
    *,
    region_id: str,
    manifest_path: str | Path,
    hotspot_table_path: str | Path,
    region_summary_path: str | Path,
) -> tuple[pd.DataFrame, Phase37RegionSummaryRecord, dict[str, Any]]:
    manifest_file = Path(manifest_path)
    hotspot_file = Path(hotspot_table_path)
    region_file = Path(region_summary_path)
    _require_existing_source_file(manifest_file, region_id=region_id, label="phase37_manifest")
    _require_existing_source_file(hotspot_file, region_id=region_id, label="phase37_hotspot_csv")
    _require_existing_source_file(region_file, region_id=region_id, label="phase37_region_csv")

    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"phase37 manifest is not a JSON object path={manifest_file}"
        )
    if str(payload.get("phase", "")).strip() != "phase3.7":
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"phase37 manifest has unexpected phase={payload.get('phase')!r}"
        )

    metrics_path = Path(str(payload.get("metrics_path", "")))
    classes_path = Path(str(payload.get("classes_path", "")))
    if not metrics_path.is_file():
        raise FileNotFoundError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"phase37 manifest references missing metrics_path={metrics_path}"
        )
    if not classes_path.is_file():
        raise FileNotFoundError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"phase37 manifest references missing classes_path={classes_path}"
        )

    hotspots_payload = payload.get("hotspots")
    if not isinstance(hotspots_payload, list):
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "phase37 manifest must contain a hotspots list"
        )
    source_hotspot_ids = [
        str(item.get("hotspot_id", "")).strip()
        for item in hotspots_payload
        if isinstance(item, dict)
        and str(item.get("region_id", "")).strip() == region_id
    ]
    if not source_hotspot_ids:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"phase37 manifest contains no hotspots for region path={manifest_file}"
        )

    hotspot_table = pd.read_csv(hotspot_file)
    missing_hotspot_columns = [
        column
        for column in REQUIRED_PHASE37_HOTSPOT_COLUMNS
        if column not in hotspot_table.columns
    ]
    if missing_hotspot_columns:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "phase37 hotspot csv is missing required columns: "
            + ", ".join(missing_hotspot_columns)
        )

    region_rows = hotspot_table.loc[
        hotspot_table["hotspot_id"].astype(str).isin(source_hotspot_ids)
    ].copy()
    if len(region_rows) != len(source_hotspot_ids):
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"phase37 hotspot csv does not match manifest hotspot ids path={hotspot_file}"
        )
    if any(str(value).strip() != region_id for value in region_rows["region_id"]):
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"phase37 hotspot csv contains mixed-region rows path={hotspot_file}"
        )

    expected_region_ranks = list(range(1, len(region_rows) + 1))
    actual_region_ranks = sorted(region_rows["region_rank"].astype(int).tolist())
    if actual_region_ranks != expected_region_ranks:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "phase37 hotspot csv region_rank values must be sequential starting at 1"
        )
    selection_rules_version = str(payload.get("selection_rules_version", "")).strip()
    if not selection_rules_version:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "phase37 manifest is missing selection_rules_version"
        )

    for index, row in region_rows.iterrows():
        _parse_bbox_literal(
            row["bbox"],
            region_id=region_id,
            label=f"phase37 hotspot bbox row={index}",
        )
        if str(row["selection_rules_version"]).strip() != selection_rules_version:
            raise ValueError(
                "stage=classification_contract_write "
                f"region_id={region_id} participant_set_key="
                f"{CLASSIFICATION_PARTICIPANT_SET_KEY} phase37 hotspot csv contains "
                "mixed selection_rules_version values"
            )
        if str(row["source"]).strip() != "entropy":
            raise ValueError(
                "stage=classification_contract_write "
                f"region_id={region_id} participant_set_key="
                f"{CLASSIFICATION_PARTICIPANT_SET_KEY} phase37 hotspot csv source must be entropy"
            )
        for column in (
            "center_lat",
            "center_lon",
            "mean_entropy",
            "max_entropy",
            "threshold_percentile",
        ):
            if not math.isfinite(float(row[column])):
                raise ValueError(
                    "stage=classification_contract_write "
                    f"region_id={region_id} participant_set_key="
                    f"{CLASSIFICATION_PARTICIPANT_SET_KEY} phase37 hotspot csv "
                    f"column {column} must be finite"
                )
        threshold_value = float(row["threshold_value"])
        if not math.isfinite(threshold_value):
            raise ValueError(
                "stage=classification_contract_write "
                f"region_id={region_id} participant_set_key="
                f"{CLASSIFICATION_PARTICIPANT_SET_KEY} phase37 hotspot csv "
                "threshold_value must be finite for selected hotspots"
            )
        if int(row["cell_count"]) <= 0:
            raise ValueError(
                "stage=classification_contract_write "
                f"region_id={region_id} participant_set_key="
                f"{CLASSIFICATION_PARTICIPANT_SET_KEY} phase37 hotspot csv cell_count must be > 0"
            )

    region_summary = load_phase37_region_summary_record(
        region_file,
        region_id=region_id,
    )
    if region_summary.selected_count != len(region_rows):
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            "phase37 region summary selected_count does not match hotspot rows"
        )

    metadata = {
        "selection_rules_version": selection_rules_version,
        "metrics_path": str(metrics_path.resolve()),
        "classes_path": str(classes_path.resolve()),
        "manifest_path": str(manifest_file.resolve()),
        "hotspot_table_path": str(hotspot_file.resolve()),
        "region_summary_path": str(region_file.resolve()),
    }
    return (region_rows, region_summary, metadata)


def _validate_classification_hotspot_table(
    table: pd.DataFrame,
    *,
    region_id: str,
    dataset_key: str,
    hotspot_count: int,
) -> None:
    missing_columns = [
        column
        for column in CLASSIFICATION_HOTSPOT_TABLE_COLUMNS
        if column not in table.columns
    ]
    if missing_columns:
        raise ValueError(
            "Classification hotspot table is missing required columns: "
            + ", ".join(missing_columns)
        )
    if len(table) != hotspot_count:
        raise ValueError(
            "Classification hotspot table row count "
            f"{len(table)} does not match manifest.hotspot_count {hotspot_count}"
        )

    expected_ranks = list(range(1, len(table) + 1))
    if table["hotspot_rank"].astype(int).tolist() != expected_ranks:
        raise ValueError(
            "Classification hotspot table hotspot_rank must be sequential starting at 1"
        )

    hotspot_ids = table["hotspot_id"].astype(str).tolist()
    if len(set(hotspot_ids)) != len(hotspot_ids):
        raise ValueError("Classification hotspot table hotspot_id values must be unique")

    for index, row in table.iterrows():
        if str(row["region_id"]).strip() != region_id:
            raise ValueError(f"Classification hotspot row {index} has a mixed region_id")
        if str(row["dataset_key"]).strip() != dataset_key:
            raise ValueError(f"Classification hotspot row {index} has a mixed dataset_key")
        if str(row["participant_set_key"]).strip() != CLASSIFICATION_PARTICIPANT_SET_KEY:
            raise ValueError(
                f"Classification hotspot row {index} has a mixed participant_set_key"
            )
        parsed_participant_ids = _parse_participant_ids_json(
            row["participant_ids_json"]
        )
        if parsed_participant_ids != CLASSIFICATION_PARTICIPANT_IDS:
            raise ValueError(
                f"Classification hotspot row {index} has mixed participant ids"
            )
        _parse_bbox_literal(
            row["bbox"],
            region_id=region_id,
            label=f"classification hotspot bbox row={index}",
        )
        for column in (
            "center_lat",
            "center_lon",
            "mean_entropy",
            "max_entropy",
            "threshold_percentile",
            "threshold_value",
        ):
            if not math.isfinite(float(row[column])):
                raise ValueError(
                    f"Classification hotspot row {index} {column} must be finite"
                )
        if float(row["max_entropy"]) < float(row["mean_entropy"]):
            raise ValueError(
                f"Classification hotspot row {index} max_entropy must be >= mean_entropy"
            )
        if int(row["cell_count"]) <= 0:
            raise ValueError(
                f"Classification hotspot row {index} cell_count must be positive"
            )
        if int(row["region_rank"]) <= 0:
            raise ValueError(
                f"Classification hotspot row {index} region_rank must be positive"
            )
        if not str(row["selection_rules_version"]).strip():
            raise ValueError(
                f"Classification hotspot row {index} selection_rules_version must not be empty"
            )
        if not str(row["source_hotspot_id"]).strip():
            raise ValueError(
                f"Classification hotspot row {index} source_hotspot_id must not be empty"
            )


def _subset_dataset_to_bbox(
    dataset: xr.Dataset,
    *,
    bbox: BBox,
    region_id: str,
    label: str,
    source_path: Path,
    reference: xr.Dataset | None = None,
) -> xr.Dataset:
    y_dim, x_dim = _spatial_dims(_first_spatial_dataarray(dataset))
    y_values = np.asarray(dataset.coords[y_dim].values, dtype=np.float64)
    x_values = np.asarray(dataset.coords[x_dim].values, dtype=np.float64)
    lat_slice = _coordinate_slice(y_values, lower=bbox[1], upper=bbox[3])
    lon_slice = _coordinate_slice(x_values, lower=bbox[0], upper=bbox[2])
    subset = dataset.sel({y_dim: lat_slice, x_dim: lon_slice}).load()
    if subset.sizes.get(y_dim, 0) == 0 or subset.sizes.get(x_dim, 0) == 0:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"source_path={source_path} {label} subset is empty for bbox={bbox!r}"
        )
    if reference is not None:
        ref_y_dim, ref_x_dim = _spatial_dims(_first_spatial_dataarray(reference))
        if (y_dim, x_dim) != (ref_y_dim, ref_x_dim):
            raise ValueError(
                "stage=classification_contract_write "
                f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
                f"source_path={source_path} {label} spatial dims do not match reference"
            )
        if not np.array_equal(subset.coords[y_dim].values, reference.coords[ref_y_dim].values):
            raise ValueError(
                "stage=classification_contract_write "
                f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
                f"source_path={source_path} {label} y coordinates do not match reference"
            )
        if not np.array_equal(subset.coords[x_dim].values, reference.coords[ref_x_dim].values):
            raise ValueError(
                "stage=classification_contract_write "
                f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
                f"source_path={source_path} {label} x coordinates do not match reference"
            )
    return subset


def _spatial_dims(data: xr.DataArray) -> tuple[str, str]:
    if "lat" in data.dims and "lon" in data.dims:
        return ("lat", "lon")
    if "y" in data.dims and "x" in data.dims:
        return ("y", "x")
    raise ValueError(f"Expected spatial dims lat/lon or y/x, got {data.dims!r}")


def _first_spatial_dataarray(dataset: xr.Dataset) -> xr.DataArray:
    for data in dataset.data_vars.values():
        dims = set(data.dims)
        if {"lat", "lon"}.issubset(dims) or {"y", "x"}.issubset(dims):
            return data
    raise ValueError("Dataset does not contain a spatial data variable")


def _coordinate_slice(values: np.ndarray, *, lower: float, upper: float) -> slice:
    if values.size == 0:
        raise ValueError("Cannot subset an empty coordinate axis")
    first = float(values[0])
    last = float(values[-1])
    if first <= last:
        return slice(lower, upper)
    return slice(upper, lower)


def _require_existing_source_file(path: Path, *, region_id: str, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"missing {label} path={path}"
        )


def _parse_participant_ids_json(value: object) -> tuple[str, ...]:
    payload = value
    if not isinstance(payload, list):
        try:
            payload = json.loads(str(value))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed participant_ids_json: {value!r}") from exc
    if not isinstance(payload, list):
        raise ValueError("participant_ids_json must decode to a list")
    participant_ids = tuple(
        validate_stem_token(str(item), label="participant_id") for item in payload
    )
    if participant_ids != CLASSIFICATION_PARTICIPANT_IDS:
        raise ValueError(
            "participant_ids_json does not match the fixed classification participant set"
        )
    return participant_ids


def _parse_json_object(
    value: object,
    *,
    label: str,
    region_id: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"Malformed {label}: {value!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(
            "stage=classification_reload "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"{label} must decode to an object"
        )
    return payload


def _parse_bbox_literal(value: object, *, region_id: str, label: str) -> BBox:
    payload = value
    if not isinstance(payload, list):
        try:
            payload = json.loads(str(value))
        except json.JSONDecodeError as exc:
            raise ValueError(
                "stage=classification_contract_write "
                f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
                f"malformed {label}: {value!r}"
            ) from exc
    if not isinstance(payload, list) or len(payload) != 4:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"{label} must be a 4-item JSON list, got {value!r}"
        )
    bbox = tuple(float(item) for item in payload)
    if not all(math.isfinite(item) for item in bbox):
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"{label} must contain finite values, got {value!r}"
        )
    west, south, east, north = bbox
    if west >= east or south >= north:
        raise ValueError(
            "stage=classification_contract_write "
            f"region_id={region_id} participant_set_key={CLASSIFICATION_PARTICIPANT_SET_KEY} "
            f"{label} bounds are invalid: {value!r}"
        )
    return bbox  # type: ignore[return-value]


def _relative_to_root(path: Path, root: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return None


def _optional_string(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


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
