"""Semantic reload and long-form normalization for unified Phase 4 hotspot ledgers."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd

from WA.comparison.evidence_contract import (
    EvidenceContract,
    metadata_json,
    validate_stem_token,
)
from WA.comparison.trend_hotspots import (
    build_participant_set_key,
    load_contract_trend_hotspot_table,
    normalize_participant_ids,
)
from WA.loaders.base import BBox

logger = logging.getLogger(__name__)

MetricFamily = Literal["percentage", "classification", "trend"]
ArtifactKind = Literal[
    "hotspot_manifest",
    "classification_hotspot_manifest",
    "trend_hotspot_manifest",
]

PERCENTAGE_SCORE_COLUMN = "wetland_percentage"
CLASSIFICATION_SCORE_COLUMN = "mean_entropy"
TREND_SCORE_COLUMN = "disagreement_score"

COMMON_HOTSPOT_COLUMNS = (
    "hotspot_id",
    "hotspot_rank",
    "region_id",
    "center_lat",
    "center_lon",
    "bbox",
)
UNIFIED_HOTSPOT_LEDGER_COLUMNS = (
    "analysis_object_id",
    "ledger_key",
    "region_id",
    "metric_family",
    "artifact_kind",
    "family_key",
    "hotspot_id",
    "hotspot_rank",
    "family_percentile",
    "primary_score_name",
    "primary_score_value",
    "center_lat",
    "center_lon",
    "bbox",
    "manifest_path",
    "table_path",
    "surface_output_path",
    "summary_output_path",
    "manifest_relpath",
    "table_relpath",
    "surface_output_relpath",
    "summary_output_relpath",
    "contract_metadata_json",
    "line_specific_json",
)
EXPECTED_METRIC_FAMILIES: tuple[MetricFamily, ...] = (
    "percentage",
    "classification",
    "trend",
)


@dataclass(frozen=True)
class HotspotFamilyReload:
    """One contract-backed hotspot family reopened by semantics."""

    metric_family: MetricFamily
    artifact_kind: ArtifactKind
    family_key: str
    family_key_field: str
    primary_score_name: str
    region_id: str
    manifest_path: Path
    table_path: Path
    surface_output_path: Path
    summary_output_path: Path
    contract_metadata_json: str
    contract_metadata: dict[str, Any]
    manifest_relpath: str
    table_relpath: str
    surface_output_relpath: str | None
    summary_output_relpath: str | None
    table: pd.DataFrame


@dataclass(frozen=True)
class UnifiedHotspotLedgerReload:
    """Reloaded unified hotspot ledger CSV."""

    ledger_path: Path
    ledger_key: str
    region_id: str
    table: pd.DataFrame


_FAMILY_ORDER = {family: index for index, family in enumerate(EXPECTED_METRIC_FAMILIES)}
_FAMILY_CONFIG: dict[MetricFamily, dict[str, str]] = {
    "percentage": {
        "artifact_kind": "hotspot_manifest",
        "family_key_field": "dataset_key",
        "primary_score_name": PERCENTAGE_SCORE_COLUMN,
    },
    "classification": {
        "artifact_kind": "classification_hotspot_manifest",
        "family_key_field": "dataset_key",
        "primary_score_name": CLASSIFICATION_SCORE_COLUMN,
    },
    "trend": {
        "artifact_kind": "trend_hotspot_manifest",
        "family_key_field": "participant_set_key",
        "primary_score_name": TREND_SCORE_COLUMN,
    },
}


def hotspot_family_manifest_output_path(
    contract: EvidenceContract,
    *,
    metric_family: MetricFamily,
    family_key: str,
    region_id: str,
) -> Path:
    """Return the semantic manifest path for one hotspot family."""

    artifact_kind = cast(ArtifactKind, _FAMILY_CONFIG[metric_family]["artifact_kind"])
    return contract.artifact_output_path(
        kind=artifact_kind,
        dataset_or_key=family_key,
        region_id=region_id,
    )


def hotspot_family_table_output_path(
    contract: EvidenceContract,
    *,
    metric_family: MetricFamily,
    family_key: str,
    region_id: str,
) -> Path:
    """Return the semantic CSV companion path for one hotspot family."""

    return hotspot_family_manifest_output_path(
        contract,
        metric_family=metric_family,
        family_key=family_key,
        region_id=region_id,
    ).with_suffix(".csv")


def unified_hotspot_ledger_output_path(
    contract: EvidenceContract,
    *,
    ledger_key: str,
    region_id: str,
) -> Path:
    """Return the semantic CSV path for one unified hotspot ledger."""

    normalized_ledger_key = validate_stem_token(ledger_key, label="ledger_key")
    return contract.artifact_output_path(
        kind="unified_hotspot_ledger",
        dataset_or_key=normalized_ledger_key,
        region_id=region_id,
    )


def load_contract_percentage_hotspot_table(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_key: str,
) -> HotspotFamilyReload:
    """Reload the percentage hotspot family by semantics."""

    return _load_generic_hotspot_family_table(
        contract=contract,
        metric_family="percentage",
        region_id=region_id,
        family_key=dataset_key,
    )


def load_contract_classification_hotspot_table(
    *,
    contract: EvidenceContract,
    region_id: str,
    dataset_key: str,
) -> HotspotFamilyReload:
    """Reload the classification hotspot family by semantics."""

    return _load_generic_hotspot_family_table(
        contract=contract,
        metric_family="classification",
        region_id=region_id,
        family_key=dataset_key,
    )


def load_contract_trend_hotspot_family(
    *,
    contract: EvidenceContract,
    region_id: str,
    participant_ids: Iterable[str],
) -> HotspotFamilyReload:
    """Reload the trend hotspot family by semantics."""

    normalized_participants = normalize_participant_ids(participant_ids)
    trend_bundle = load_contract_trend_hotspot_table(
        contract=contract,
        region_id=region_id,
        participant_ids=normalized_participants,
    )
    manifest = trend_bundle.manifest
    return HotspotFamilyReload(
        metric_family="trend",
        artifact_kind="trend_hotspot_manifest",
        family_key=manifest.participant_set_key,
        family_key_field="participant_set_key",
        primary_score_name=TREND_SCORE_COLUMN,
        region_id=manifest.region_id,
        manifest_path=manifest.manifest_path,
        table_path=manifest.table_path,
        surface_output_path=manifest.surface_output_path,
        summary_output_path=manifest.summary_output_path,
        contract_metadata_json=manifest.contract_metadata_json,
        contract_metadata=manifest.contract_metadata,
        manifest_relpath=manifest.manifest_relpath,
        table_relpath=manifest.table_relpath,
        surface_output_relpath=manifest.surface_output_relpath,
        summary_output_relpath=manifest.summary_output_relpath,
        table=trend_bundle.table.copy(),
    )


def build_unified_hotspot_ledger(
    *,
    contract: EvidenceContract,
    region_id: str,
    ledger_key: str,
    percentage_key: str,
    classification_key: str,
    trend_participant_ids: Iterable[str],
) -> pd.DataFrame:
    """Reload all required hotspot families and normalize one long-form ledger."""

    normalized_ledger_key = validate_stem_token(ledger_key, label="ledger_key")
    normalized_percentage_key = validate_stem_token(
        percentage_key,
        label="percentage_key",
    )
    normalized_classification_key = validate_stem_token(
        classification_key,
        label="classification_key",
    )
    normalized_trend_participants = normalize_participant_ids(trend_participant_ids)
    participant_set_key = build_participant_set_key(normalized_trend_participants)

    family_reloads = [
        load_contract_percentage_hotspot_table(
            contract=contract,
            region_id=region_id,
            dataset_key=normalized_percentage_key,
        ),
        load_contract_classification_hotspot_table(
            contract=contract,
            region_id=region_id,
            dataset_key=normalized_classification_key,
        ),
        load_contract_trend_hotspot_family(
            contract=contract,
            region_id=region_id,
            participant_ids=normalized_trend_participants,
        ),
    ]

    logger.info(
        "stage=ledger region=%s action=families-validated families=%s "
        "percentage_key=%s classification_key=%s participant_set_key=%s",
        region_id,
        [family.metric_family for family in family_reloads],
        normalized_percentage_key,
        normalized_classification_key,
        participant_set_key,
    )

    ledger_parts = [
        _normalize_hotspot_family(
            family_reload=family_reload,
            ledger_key=normalized_ledger_key,
        )
        for family_reload in family_reloads
    ]
    ledger = pd.concat(ledger_parts, ignore_index=True)
    ledger["_metric_family_order"] = ledger["metric_family"].map(_FAMILY_ORDER)
    ledger = ledger.sort_values(
        ["_metric_family_order", "hotspot_rank", "analysis_object_id"],
        kind="mergesort",
    ).drop(columns="_metric_family_order")
    ledger = ledger.reset_index(drop=True)

    duplicate_ids = ledger["analysis_object_id"][
        ledger["analysis_object_id"].duplicated(keep=False)
    ].tolist()
    if duplicate_ids:
        unique_duplicates = sorted({str(value) for value in duplicate_ids})
        raise ValueError(
            "Unified hotspot ledger contains duplicate analysis_object_id candidates: "
            + ", ".join(unique_duplicates)
        )

    if set(ledger["metric_family"]) != set(EXPECTED_METRIC_FAMILIES):
        raise ValueError(
            "Unified hotspot ledger requires percentage, classification, and trend families"
        )

    return ledger.loc[:, list(UNIFIED_HOTSPOT_LEDGER_COLUMNS)]


def write_unified_hotspot_ledger(
    *,
    contract: EvidenceContract,
    region_id: str,
    ledger_key: str,
    percentage_key: str,
    classification_key: str,
    trend_participant_ids: Iterable[str],
) -> UnifiedHotspotLedgerReload:
    """Write one unified hotspot ledger only after all families validate."""

    ledger = build_unified_hotspot_ledger(
        contract=contract,
        region_id=region_id,
        ledger_key=ledger_key,
        percentage_key=percentage_key,
        classification_key=classification_key,
        trend_participant_ids=trend_participant_ids,
    )
    ledger_path = unified_hotspot_ledger_output_path(
        contract,
        ledger_key=ledger_key,
        region_id=region_id,
    )
    serializable = ledger.copy()
    serializable["bbox"] = serializable["bbox"].map(_format_bbox_for_csv)
    _write_text_atomic(ledger_path, serializable.to_csv(index=False, lineterminator="\n"))
    logger.info(
        "stage=ledger region=%s action=write-complete rows=%s path=%s",
        region_id,
        len(ledger),
        ledger_path,
    )
    return load_contract_unified_hotspot_ledger(
        contract=contract,
        region_id=region_id,
        ledger_key=ledger_key,
    )


def load_contract_unified_hotspot_ledger(
    *,
    contract: EvidenceContract,
    region_id: str,
    ledger_key: str,
) -> UnifiedHotspotLedgerReload:
    """Reload one unified hotspot ledger CSV by contract semantics."""

    normalized_ledger_key = validate_stem_token(ledger_key, label="ledger_key")
    ledger_path = unified_hotspot_ledger_output_path(
        contract,
        ledger_key=normalized_ledger_key,
        region_id=region_id,
    )
    if not ledger_path.is_file():
        raise FileNotFoundError(
            "Unified hotspot ledger is missing: "
            f"region_id={region_id} ledger_key={normalized_ledger_key} path={ledger_path}"
        )

    ledger = pd.read_csv(ledger_path)
    _validate_unified_hotspot_ledger(
        ledger,
        expected_region_id=region_id,
        expected_ledger_key=normalized_ledger_key,
    )
    parsed = ledger.copy()
    parsed["bbox"] = parsed["bbox"].map(_parse_bbox_literal)
    parsed["contract_metadata"] = parsed["contract_metadata_json"].map(
        lambda value: _parse_json_object(value, label="contract_metadata_json")
    )
    parsed["line_specific"] = parsed["line_specific_json"].map(
        lambda value: _parse_json_object(value, label="line_specific_json")
    )
    return UnifiedHotspotLedgerReload(
        ledger_path=ledger_path.resolve(),
        ledger_key=normalized_ledger_key,
        region_id=region_id,
        table=parsed,
    )


def _load_generic_hotspot_family_table(
    *,
    contract: EvidenceContract,
    metric_family: MetricFamily,
    region_id: str,
    family_key: str,
) -> HotspotFamilyReload:
    config = _FAMILY_CONFIG[metric_family]
    family_key_field = config["family_key_field"]
    primary_score_name = config["primary_score_name"]
    artifact_kind = cast(ArtifactKind, config["artifact_kind"])
    normalized_family_key = validate_stem_token(
        family_key,
        label=family_key_field,
    )

    manifest_path = hotspot_family_manifest_output_path(
        contract,
        metric_family=metric_family,
        family_key=normalized_family_key,
        region_id=region_id,
    )
    expected_table_path = hotspot_family_table_output_path(
        contract,
        metric_family=metric_family,
        family_key=normalized_family_key,
        region_id=region_id,
    ).resolve()
    manifest = _load_generic_hotspot_manifest(
        path=manifest_path,
        artifact_kind=artifact_kind,
        family_key_field=family_key_field,
    )
    if manifest.region_id != region_id:
        raise ValueError(
            f"{metric_family} hotspot manifest region mismatch: "
            f"expected {region_id!r}, got {manifest.region_id!r}"
        )
    if manifest.family_key != normalized_family_key:
        raise ValueError(
            f"{metric_family} hotspot manifest {family_key_field} does not match the requested key"
        )
    if manifest.table_path != expected_table_path:
        raise ValueError(
            f"{metric_family} hotspot manifest table_output_path does not match contract semantics"
        )

    table_text = manifest.table_path.read_text(encoding="utf-8")
    table_sha256 = hashlib.sha256(table_text.encode("utf-8")).hexdigest()
    if table_sha256 != manifest.table_sha256:
        raise ValueError(
            f"{metric_family} hotspot table SHA mismatch; refusing to reuse a partial "
            "or stale JSON/CSV pair"
        )

    table = pd.read_csv(manifest.table_path)
    _validate_generic_hotspot_table(
        table,
        metric_family=metric_family,
        expected_region_id=region_id,
        family_key_field=family_key_field,
        expected_family_key=normalized_family_key,
        primary_score_name=primary_score_name,
        hotspot_count=manifest.hotspot_count,
    )
    table = table.copy()
    table["bbox"] = table["bbox"].map(_parse_bbox_literal)

    logger.info(
        "stage=ledger region=%s action=family-ready metric_family=%s rows=%s family_key=%s",
        region_id,
        metric_family,
        len(table),
        normalized_family_key,
    )

    return HotspotFamilyReload(
        metric_family=metric_family,
        artifact_kind=artifact_kind,
        family_key=normalized_family_key,
        family_key_field=family_key_field,
        primary_score_name=primary_score_name,
        region_id=manifest.region_id,
        manifest_path=manifest.manifest_path,
        table_path=manifest.table_path,
        surface_output_path=manifest.surface_output_path,
        summary_output_path=manifest.summary_output_path,
        contract_metadata_json=manifest.contract_metadata_json,
        contract_metadata=manifest.contract_metadata,
        manifest_relpath=manifest.manifest_relpath,
        table_relpath=manifest.table_relpath,
        surface_output_relpath=manifest.surface_output_relpath,
        summary_output_relpath=manifest.summary_output_relpath,
        table=table,
    )


@dataclass(frozen=True)
class _GenericHotspotManifest:
    manifest_path: Path
    table_path: Path
    region_id: str
    family_key: str
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


def _load_generic_hotspot_manifest(
    *,
    path: str | Path,
    artifact_kind: ArtifactKind,
    family_key_field: str,
) -> _GenericHotspotManifest:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{artifact_kind} manifest must be a JSON object: {manifest_path}")
    if payload.get("artifact_kind") != artifact_kind:
        raise ValueError(
            f"Expected artifact_kind={artifact_kind!r}, got {payload.get('artifact_kind')!r}"
        )

    region_id = validate_stem_token(str(payload.get("region_id", "")), label="region_id")
    family_key = validate_stem_token(
        str(payload.get(family_key_field, "")),
        label=family_key_field,
    )
    hotspot_count = int(payload.get("hotspot_count", 0))
    if hotspot_count <= 0:
        raise ValueError(f"{artifact_kind} hotspot_count must be positive")

    table_sha256 = str(payload.get("table_sha256", "")).strip()
    if len(table_sha256) != 64:
        raise ValueError(f"{artifact_kind} table_sha256 must be a SHA-256 hex digest")

    manifest_output_path = Path(str(payload.get("manifest_output_path", manifest_path)))
    if manifest_output_path.resolve() != manifest_path.resolve():
        raise ValueError(f"{artifact_kind} manifest_output_path does not match the loaded path")

    table_path = Path(str(payload.get("table_output_path", "")))
    surface_output_path = Path(str(payload.get("surface_output_path", "")))
    summary_output_path = Path(str(payload.get("summary_output_path", "")))
    for label, candidate in (
        ("table_output_path", table_path),
        ("surface_output_path", surface_output_path),
        ("summary_output_path", summary_output_path),
    ):
        if not str(candidate).strip():
            raise ValueError(f"{artifact_kind} manifest is missing {label}")
        if not candidate.is_file():
            raise FileNotFoundError(
                f"{artifact_kind} manifest references missing {label}: {candidate}"
            )

    contract_metadata_json = str(payload.get("contract_metadata_json", "")).strip()
    if not contract_metadata_json:
        raise ValueError(f"{artifact_kind} manifest is missing contract_metadata_json")
    contract_metadata = _parse_json_object(
        contract_metadata_json,
        label="contract_metadata_json",
    )

    manifest_relpath = str(payload.get("manifest_relpath", "")).strip()
    table_relpath = str(payload.get("table_relpath", "")).strip()
    if not manifest_relpath or not table_relpath:
        raise ValueError(
            f"{artifact_kind} manifest must contain manifest_relpath and table_relpath"
        )

    return _GenericHotspotManifest(
        manifest_path=manifest_path.resolve(),
        table_path=table_path.resolve(),
        region_id=region_id,
        family_key=family_key,
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


def _validate_generic_hotspot_table(
    table: pd.DataFrame,
    *,
    metric_family: MetricFamily,
    expected_region_id: str,
    family_key_field: str,
    expected_family_key: str,
    primary_score_name: str,
    hotspot_count: int,
) -> None:
    required_columns = [
        *COMMON_HOTSPOT_COLUMNS,
        family_key_field,
        primary_score_name,
    ]
    missing_columns = [column for column in required_columns if column not in table.columns]
    if missing_columns:
        raise ValueError(
            f"{metric_family} hotspot table is missing required columns: "
            + ", ".join(missing_columns)
        )
    if len(table) != hotspot_count:
        raise ValueError(
            f"{metric_family} hotspot table row count {len(table)} does not match "
            f"manifest.hotspot_count {hotspot_count}"
        )

    expected_ranks = list(range(1, len(table) + 1))
    if table["hotspot_rank"].astype(int).tolist() != expected_ranks:
        raise ValueError(
            f"{metric_family} hotspot table hotspot_rank must be sequential starting at 1"
        )

    for index, row in table.iterrows():
        hotspot_id = str(row["hotspot_id"]).strip()
        if not hotspot_id:
            raise ValueError(f"{metric_family} hotspot row {index} is missing hotspot_id")
        if str(row["region_id"]).strip() != expected_region_id:
            raise ValueError(f"{metric_family} hotspot row {index} has a mixed region_id")
        if str(row[family_key_field]).strip() != expected_family_key:
            raise ValueError(
                f"{metric_family} hotspot row {index} has a mixed {family_key_field}"
            )
        _parse_bbox_literal(row["bbox"])
        center_lat = float(row["center_lat"])
        center_lon = float(row["center_lon"])
        primary_score = float(row[primary_score_name])
        if not math.isfinite(center_lat) or not math.isfinite(center_lon):
            raise ValueError(
                f"{metric_family} hotspot row {index} center coordinates must be finite"
            )
        if not math.isfinite(primary_score):
            raise ValueError(
                f"{metric_family} hotspot row {index} {primary_score_name} must be finite"
            )


def _normalize_hotspot_family(
    *,
    family_reload: HotspotFamilyReload,
    ledger_key: str,
) -> pd.DataFrame:
    table = family_reload.table.copy()
    family_size = len(table)
    percentiles = _rank_percentiles(family_size)
    records: list[dict[str, object]] = []
    excluded_columns = set(COMMON_HOTSPOT_COLUMNS)

    for row_index, row in enumerate(table.to_dict(orient="records"), start=1):
        hotspot_id = str(row["hotspot_id"]).strip()
        analysis_object_id = (
            f"{family_reload.region_id}::{family_reload.metric_family}::{hotspot_id}"
        )
        line_specific = {
            key: _json_ready_value(value)
            for key, value in row.items()
            if key not in excluded_columns
        }
        records.append(
            {
                "analysis_object_id": analysis_object_id,
                "ledger_key": ledger_key,
                "region_id": family_reload.region_id,
                "metric_family": family_reload.metric_family,
                "artifact_kind": family_reload.artifact_kind,
                "family_key": family_reload.family_key,
                "hotspot_id": hotspot_id,
                "hotspot_rank": int(row["hotspot_rank"]),
                "family_percentile": float(percentiles[row_index - 1]),
                "primary_score_name": family_reload.primary_score_name,
                "primary_score_value": float(row[family_reload.primary_score_name]),
                "center_lat": float(row["center_lat"]),
                "center_lon": float(row["center_lon"]),
                "bbox": cast(BBox, row["bbox"]),
                "manifest_path": str(family_reload.manifest_path),
                "table_path": str(family_reload.table_path),
                "surface_output_path": str(family_reload.surface_output_path),
                "summary_output_path": str(family_reload.summary_output_path),
                "manifest_relpath": family_reload.manifest_relpath,
                "table_relpath": family_reload.table_relpath,
                "surface_output_relpath": family_reload.surface_output_relpath,
                "summary_output_relpath": family_reload.summary_output_relpath,
                "contract_metadata_json": family_reload.contract_metadata_json,
                "line_specific_json": metadata_json(line_specific),
            }
        )

    normalized = pd.DataFrame(records)
    logger.info(
        "stage=ledger region=%s action=family-normalized metric_family=%s rows=%s",
        family_reload.region_id,
        family_reload.metric_family,
        len(normalized),
    )
    return normalized.loc[:, list(UNIFIED_HOTSPOT_LEDGER_COLUMNS)]


def _rank_percentiles(family_size: int) -> np.ndarray:
    if family_size <= 0:
        raise ValueError("family_size must be positive")
    if family_size == 1:
        return np.array([1.0], dtype=np.float64)
    ranks = np.arange(family_size, dtype=np.float64)
    return 1.0 - (ranks / float(family_size - 1))


def _validate_unified_hotspot_ledger(
    table: pd.DataFrame,
    *,
    expected_region_id: str,
    expected_ledger_key: str,
) -> None:
    missing_columns = [
        column for column in UNIFIED_HOTSPOT_LEDGER_COLUMNS if column not in table.columns
    ]
    if missing_columns:
        raise ValueError(
            "Unified hotspot ledger is missing required columns: "
            + ", ".join(missing_columns)
        )
    if table.empty:
        raise ValueError("Unified hotspot ledger must not be empty")

    families = {str(value).strip() for value in table["metric_family"]}
    missing_families = sorted(set(EXPECTED_METRIC_FAMILIES) - families)
    extra_families = sorted(families - set(EXPECTED_METRIC_FAMILIES))
    if missing_families or extra_families:
        details: list[str] = []
        if missing_families:
            details.append("missing=" + ", ".join(missing_families))
        if extra_families:
            details.append("unexpected=" + ", ".join(extra_families))
        raise ValueError(
            "Unified hotspot ledger has incomplete metric families: "
            + "; ".join(details)
        )

    duplicate_ids = table["analysis_object_id"][
        table["analysis_object_id"].duplicated(keep=False)
    ].tolist()
    if duplicate_ids:
        unique_duplicates = sorted({str(value) for value in duplicate_ids})
        raise ValueError(
            "Unified hotspot ledger contains duplicate analysis_object_id values: "
            + ", ".join(unique_duplicates)
        )

    for index, row in table.iterrows():
        if str(row["region_id"]).strip() != expected_region_id:
            raise ValueError(f"Unified hotspot ledger row {index} has a mixed region_id")
        if str(row["ledger_key"]).strip() != expected_ledger_key:
            raise ValueError(f"Unified hotspot ledger row {index} has a mixed ledger_key")
        metric_family = str(row["metric_family"]).strip()
        if metric_family not in _FAMILY_CONFIG:
            raise ValueError(
                f"Unified hotspot ledger row {index} has an unknown metric_family={metric_family!r}"
            )
        primary_score_name = str(row["primary_score_name"]).strip()
        expected_score_name = _FAMILY_CONFIG[cast(MetricFamily, metric_family)][
            "primary_score_name"
        ]
        if primary_score_name != expected_score_name:
            raise ValueError(
                f"Unified hotspot ledger row {index} primary_score_name does not "
                "match metric_family"
            )
        primary_score_value = float(row["primary_score_value"])
        if not math.isfinite(primary_score_value):
            raise ValueError(
                f"Unified hotspot ledger row {index} primary_score_value must be finite"
            )
        family_percentile = float(row["family_percentile"])
        if not (0.0 <= family_percentile <= 1.0):
            raise ValueError(
                f"Unified hotspot ledger row {index} family_percentile must be within [0, 1]"
            )
        _parse_bbox_literal(row["bbox"])
        if not math.isfinite(float(row["center_lat"])) or not math.isfinite(
            float(row["center_lon"])
        ):
            raise ValueError(
                f"Unified hotspot ledger row {index} center coordinates must be finite"
            )
        _parse_json_object(row["contract_metadata_json"], label="contract_metadata_json")
        _parse_json_object(row["line_specific_json"], label="line_specific_json")


def _format_bbox_for_csv(bbox: BBox) -> str:
    return json.dumps([float(value) for value in bbox], separators=(",", ":"))


def _parse_bbox_literal(value: object) -> BBox:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid hotspot bbox JSON: {value!r}") from exc
    if not isinstance(parsed, list) or len(parsed) != 4:
        raise ValueError(f"Hotspot bbox must be a 4-item JSON list, got {value!r}")
    bbox = tuple(float(item) for item in parsed)
    if not all(math.isfinite(item) for item in bbox):
        raise ValueError(f"Hotspot bbox must contain finite values, got {value!r}")
    west, south, east, north = bbox
    if west >= east or south >= north:
        raise ValueError(f"Hotspot bbox bounds are invalid: {value!r}")
    return cast(BBox, bbox)


def _parse_json_object(value: object, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed {label}: {value!r}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must decode to an object")
    return parsed


def _json_ready_value(value: object) -> Any:
    if isinstance(value, tuple) and len(value) == 4:
        return [float(item) for item in value]
    return value


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
    temp_path.replace(path)
