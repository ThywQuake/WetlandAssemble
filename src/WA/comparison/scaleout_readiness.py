"""Operator-facing readiness inspection for Phase 4 ten-region scale-out."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from WA.comparison.classification_contract import (
    CLASSIFICATION_CONTRACT_DATASET_KEY,
    load_contract_classification_hotspot_table,
)
from WA.comparison.evidence_contract import EvidenceContract, validate_stem_token
from WA.comparison.percentage_hotspots import load_contract_percentage_hotspot_table
from WA.comparison.trend_hotspots import (
    build_participant_set_key,
    load_contract_trend_hotspot_table,
    normalize_participant_ids,
)

ReadinessStatus = Literal["ready", "missing", "partial"]
MetricFamily = Literal["percentage", "classification", "trend"]

DEFAULT_SCALEOUT_PERCENTAGE_KEY = "canonical"
DEFAULT_SCALEOUT_CLASSIFICATION_KEY = CLASSIFICATION_CONTRACT_DATASET_KEY
DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS = (
    "gwd30",
    "giems_mc",
    "topmodel",
    "swamps",
    "wad2m",
)

SCALEOUT_READYNESS_COLUMNS = (
    "region_id",
    "region_label",
    "metric_family",
    "family_key",
    "status",
    "reason",
    "region_ready",
    "manifest_path",
    "table_path",
    "surface_output_path",
    "summary_output_path",
    "manifest_exists",
    "table_exists",
    "surface_output_exists",
    "summary_output_exists",
    "error_type",
    "error_message",
)
_EXPECTED_FAMILY_ORDER: tuple[MetricFamily, ...] = (
    "percentage",
    "classification",
    "trend",
)


@dataclass(frozen=True)
class FamilyArtifactPaths:
    """Expected contract paths for one hotspot family."""

    manifest_path: Path
    table_path: Path
    surface_output_path: Path
    summary_output_path: Path


@dataclass(frozen=True)
class ScaleoutReadinessRow:
    """One machine-readable readiness row for one region × family."""

    region_id: str
    region_label: str
    metric_family: MetricFamily
    family_key: str
    status: ReadinessStatus
    reason: str
    manifest_path: Path
    table_path: Path
    surface_output_path: Path
    summary_output_path: Path
    manifest_exists: bool
    table_exists: bool
    surface_output_exists: bool
    summary_output_exists: bool
    error_type: str | None = None
    error_message: str | None = None

    def to_record(self, *, region_ready: bool) -> dict[str, object]:
        """Convert one row to a CSV/JSON-friendly record."""

        return {
            "region_id": self.region_id,
            "region_label": self.region_label,
            "metric_family": self.metric_family,
            "family_key": self.family_key,
            "status": self.status,
            "reason": self.reason,
            "region_ready": bool(region_ready),
            "manifest_path": str(self.manifest_path),
            "table_path": str(self.table_path),
            "surface_output_path": str(self.surface_output_path),
            "summary_output_path": str(self.summary_output_path),
            "manifest_exists": self.manifest_exists,
            "table_exists": self.table_exists,
            "surface_output_exists": self.surface_output_exists,
            "summary_output_exists": self.summary_output_exists,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class ScaleoutReadinessReport:
    """Structured readiness report plus persisted CSV/JSON paths."""

    generated_at: str
    selector_key: str
    selector_label: str
    subset: str | None
    requested_region_ids: tuple[str, ...]
    resolved_region_ids: tuple[str, ...]
    percentage_key: str
    classification_key: str
    trend_participant_ids: tuple[str, ...]
    trend_participant_set_key: str
    csv_path: Path
    json_path: Path
    rows: tuple[ScaleoutReadinessRow, ...]
    table: pd.DataFrame
    ready_region_ids: tuple[str, ...]
    incomplete_region_ids: tuple[str, ...]

    def to_json_payload(self) -> dict[str, Any]:
        """Return a stable JSON payload for the persisted report."""

        return {
            "generated_at": self.generated_at,
            "selector_key": self.selector_key,
            "selector_label": self.selector_label,
            "subset": self.subset,
            "requested_region_ids": list(self.requested_region_ids),
            "resolved_region_ids": list(self.resolved_region_ids),
            "percentage_key": self.percentage_key,
            "classification_key": self.classification_key,
            "trend_participant_ids": list(self.trend_participant_ids),
            "trend_participant_set_key": self.trend_participant_set_key,
            "csv_path": str(self.csv_path),
            "json_path": str(self.json_path),
            "ready_region_ids": list(self.ready_region_ids),
            "incomplete_region_ids": list(self.incomplete_region_ids),
            "rows": self.table.to_dict(orient="records"),
        }


def scaleout_readiness_csv_output_path(
    output_root: str | Path,
    *,
    subset: str | None = None,
    requested_region_ids: Iterable[str] | None = None,
    percentage_key: str = DEFAULT_SCALEOUT_PERCENTAGE_KEY,
    classification_key: str = DEFAULT_SCALEOUT_CLASSIFICATION_KEY,
    trend_participant_ids: Iterable[str] = DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS,
) -> Path:
    """Return the deterministic CSV path for one readiness report."""

    stem = _scaleout_readiness_report_stem(
        subset=subset,
        requested_region_ids=requested_region_ids,
        percentage_key=percentage_key,
        classification_key=classification_key,
        trend_participant_ids=trend_participant_ids,
    )
    return Path(output_root) / "scaleout_readiness" / f"{stem}.csv"


def scaleout_readiness_json_output_path(
    output_root: str | Path,
    *,
    subset: str | None = None,
    requested_region_ids: Iterable[str] | None = None,
    percentage_key: str = DEFAULT_SCALEOUT_PERCENTAGE_KEY,
    classification_key: str = DEFAULT_SCALEOUT_CLASSIFICATION_KEY,
    trend_participant_ids: Iterable[str] = DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS,
) -> Path:
    """Return the deterministic JSON path for one readiness report."""

    stem = _scaleout_readiness_report_stem(
        subset=subset,
        requested_region_ids=requested_region_ids,
        percentage_key=percentage_key,
        classification_key=classification_key,
        trend_participant_ids=trend_participant_ids,
    )
    return Path(output_root) / "scaleout_readiness" / f"{stem}.json"


def inspect_scaleout_readiness(
    *,
    contract: EvidenceContract,
    subset: str | None = None,
    requested_region_ids: Iterable[str] | None = None,
    percentage_key: str = DEFAULT_SCALEOUT_PERCENTAGE_KEY,
    classification_key: str = DEFAULT_SCALEOUT_CLASSIFICATION_KEY,
    trend_participant_ids: Iterable[str] = DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS,
) -> ScaleoutReadinessReport:
    """Inspect readiness for one region list, the canonical subset, or the ten-region set."""

    normalized_percentage_key = validate_stem_token(
        percentage_key,
        label="percentage_key",
    )
    normalized_classification_key = validate_stem_token(
        classification_key,
        label="classification_key",
    )
    normalized_requested_regions = _normalize_requested_region_ids(requested_region_ids)
    normalized_participant_ids = normalize_participant_ids(trend_participant_ids)
    participant_set_key = build_participant_set_key(normalized_participant_ids)

    regions = contract.resolve_regions(
        subset=subset,
        requested_region_ids=normalized_requested_regions or None,
    )
    resolved_region_ids = tuple(region.region_id for region in regions)
    selector_label, selector_key = _selector_identity(
        subset=subset,
        requested_region_ids=normalized_requested_regions,
        resolved_region_ids=resolved_region_ids,
    )
    csv_path = scaleout_readiness_csv_output_path(
        contract.output_root,
        subset=subset,
        requested_region_ids=resolved_region_ids,
        percentage_key=normalized_percentage_key,
        classification_key=normalized_classification_key,
        trend_participant_ids=normalized_participant_ids,
    )
    json_path = scaleout_readiness_json_output_path(
        contract.output_root,
        subset=subset,
        requested_region_ids=resolved_region_ids,
        percentage_key=normalized_percentage_key,
        classification_key=normalized_classification_key,
        trend_participant_ids=normalized_participant_ids,
    )

    rows: list[ScaleoutReadinessRow] = []
    for region in regions:
        rows.append(
            _inspect_percentage_family(
                contract=contract,
                region_id=region.region_id,
                region_label=region.label,
                dataset_key=normalized_percentage_key,
            )
        )
        rows.append(
            _inspect_classification_family(
                contract=contract,
                region_id=region.region_id,
                region_label=region.label,
                dataset_key=normalized_classification_key,
            )
        )
        rows.append(
            _inspect_trend_family(
                contract=contract,
                region_id=region.region_id,
                region_label=region.label,
                participant_ids=normalized_participant_ids,
            )
        )

    region_ready_map = {
        region_id: all(
            row.status == "ready" for row in rows if row.region_id == region_id
        )
        for region_id in resolved_region_ids
    }
    records = [
        row.to_record(region_ready=region_ready_map[row.region_id]) for row in rows
    ]
    table = pd.DataFrame(records, columns=list(SCALEOUT_READYNESS_COLUMNS))
    ready_region_ids = tuple(
        region_id for region_id in resolved_region_ids if region_ready_map[region_id]
    )
    incomplete_region_ids = tuple(
        region_id for region_id in resolved_region_ids if not region_ready_map[region_id]
    )

    return ScaleoutReadinessReport(
        generated_at=datetime.now(UTC).isoformat(),
        selector_key=selector_key,
        selector_label=selector_label,
        subset=subset,
        requested_region_ids=normalized_requested_regions,
        resolved_region_ids=resolved_region_ids,
        percentage_key=normalized_percentage_key,
        classification_key=normalized_classification_key,
        trend_participant_ids=normalized_participant_ids,
        trend_participant_set_key=participant_set_key,
        csv_path=csv_path,
        json_path=json_path,
        rows=tuple(rows),
        table=table,
        ready_region_ids=ready_region_ids,
        incomplete_region_ids=incomplete_region_ids,
    )


def write_scaleout_readiness_report(
    *,
    contract: EvidenceContract,
    subset: str | None = None,
    requested_region_ids: Iterable[str] | None = None,
    percentage_key: str = DEFAULT_SCALEOUT_PERCENTAGE_KEY,
    classification_key: str = DEFAULT_SCALEOUT_CLASSIFICATION_KEY,
    trend_participant_ids: Iterable[str] = DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS,
) -> ScaleoutReadinessReport:
    """Inspect readiness, then persist deterministic CSV and JSON reports."""

    report = inspect_scaleout_readiness(
        contract=contract,
        subset=subset,
        requested_region_ids=requested_region_ids,
        percentage_key=percentage_key,
        classification_key=classification_key,
        trend_participant_ids=trend_participant_ids,
    )
    _write_text_atomic(
        report.csv_path,
        report.table.to_csv(index=False, lineterminator="\n"),
    )
    _write_text_atomic(
        report.json_path,
        json.dumps(report.to_json_payload(), indent=2, sort_keys=True) + "\n",
    )
    return report


def _inspect_percentage_family(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_label: str,
    dataset_key: str,
) -> ScaleoutReadinessRow:
    paths = FamilyArtifactPaths(
        manifest_path=contract.artifact_output_path(
            kind="hotspot_manifest",
            dataset_or_key=dataset_key,
            region_id=region_id,
        ),
        table_path=contract.artifact_output_path(
            kind="hotspot_manifest",
            dataset_or_key=dataset_key,
            region_id=region_id,
            extension=".csv",
        ),
        surface_output_path=contract.artifact_output_path(
            kind="surface",
            dataset_or_key=dataset_key,
            region_id=region_id,
        ),
        summary_output_path=contract.artifact_output_path(
            kind="regional_summary",
            dataset_or_key=dataset_key,
            region_id=region_id,
        ),
    )
    return _inspect_family(
        region_id=region_id,
        region_label=region_label,
        metric_family="percentage",
        family_key=dataset_key,
        expected_paths=paths,
        load_family=lambda: load_contract_percentage_hotspot_table(
            contract=contract,
            region_id=region_id,
            dataset_key=dataset_key,
        ),
    )


def _inspect_classification_family(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_label: str,
    dataset_key: str,
) -> ScaleoutReadinessRow:
    paths = FamilyArtifactPaths(
        manifest_path=contract.artifact_output_path(
            kind="classification_hotspot_manifest",
            dataset_or_key=dataset_key,
            region_id=region_id,
        ),
        table_path=contract.artifact_output_path(
            kind="classification_hotspot_manifest",
            dataset_or_key=dataset_key,
            region_id=region_id,
            extension=".csv",
        ),
        surface_output_path=contract.artifact_output_path(
            kind="classification_surface",
            dataset_or_key=dataset_key,
            region_id=region_id,
        ),
        summary_output_path=contract.artifact_output_path(
            kind="classification_regional_summary",
            dataset_or_key=dataset_key,
            region_id=region_id,
        ),
    )
    return _inspect_family(
        region_id=region_id,
        region_label=region_label,
        metric_family="classification",
        family_key=dataset_key,
        expected_paths=paths,
        load_family=lambda: load_contract_classification_hotspot_table(
            contract=contract,
            region_id=region_id,
            dataset_key=dataset_key,
        ),
    )


def _inspect_trend_family(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_label: str,
    participant_ids: tuple[str, ...],
) -> ScaleoutReadinessRow:
    participant_set_key = build_participant_set_key(participant_ids)
    paths = FamilyArtifactPaths(
        manifest_path=contract.artifact_output_path(
            kind="trend_hotspot_manifest",
            dataset_or_key=participant_set_key,
            region_id=region_id,
        ),
        table_path=contract.artifact_output_path(
            kind="trend_hotspot_manifest",
            dataset_or_key=participant_set_key,
            region_id=region_id,
            extension=".csv",
        ),
        surface_output_path=contract.artifact_output_path(
            kind="trend_agreement_surface",
            dataset_or_key=participant_set_key,
            region_id=region_id,
        ),
        summary_output_path=contract.artifact_output_path(
            kind="trend_agreement_summary",
            dataset_or_key=participant_set_key,
            region_id=region_id,
        ),
    )
    return _inspect_family(
        region_id=region_id,
        region_label=region_label,
        metric_family="trend",
        family_key=participant_set_key,
        expected_paths=paths,
        load_family=lambda: load_contract_trend_hotspot_table(
            contract=contract,
            region_id=region_id,
            participant_ids=participant_ids,
        ),
    )


def _inspect_family(
    *,
    region_id: str,
    region_label: str,
    metric_family: MetricFamily,
    family_key: str,
    expected_paths: FamilyArtifactPaths,
    load_family: Callable[[], Any],
) -> ScaleoutReadinessRow:
    manifest_exists = expected_paths.manifest_path.is_file()
    table_exists = expected_paths.table_path.is_file()
    surface_exists = expected_paths.surface_output_path.is_file()
    summary_exists = expected_paths.summary_output_path.is_file()

    try:
        bundle = load_family()
    except Exception as exc:
        status, reason = _classify_incomplete_family(
            exc=exc,
            manifest_exists=manifest_exists,
            table_exists=table_exists,
            surface_exists=surface_exists,
            summary_exists=summary_exists,
        )
        return ScaleoutReadinessRow(
            region_id=region_id,
            region_label=region_label,
            metric_family=metric_family,
            family_key=family_key,
            status=status,
            reason=reason,
            manifest_path=expected_paths.manifest_path.resolve(),
            table_path=expected_paths.table_path.resolve(),
            surface_output_path=expected_paths.surface_output_path.resolve(),
            summary_output_path=expected_paths.summary_output_path.resolve(),
            manifest_exists=manifest_exists,
            table_exists=table_exists,
            surface_output_exists=surface_exists,
            summary_output_exists=summary_exists,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

    manifest = bundle.manifest
    return ScaleoutReadinessRow(
        region_id=region_id,
        region_label=region_label,
        metric_family=metric_family,
        family_key=family_key,
        status="ready",
        reason="semantic reload succeeded for manifest/table pair and provenance outputs",
        manifest_path=Path(manifest.manifest_path).resolve(),
        table_path=Path(manifest.table_path).resolve(),
        surface_output_path=Path(manifest.surface_output_path).resolve(),
        summary_output_path=Path(manifest.summary_output_path).resolve(),
        manifest_exists=True,
        table_exists=True,
        surface_output_exists=True,
        summary_output_exists=True,
    )


def _classify_incomplete_family(
    *,
    exc: Exception,
    manifest_exists: bool,
    table_exists: bool,
    surface_exists: bool,
    summary_exists: bool,
) -> tuple[ReadinessStatus, str]:
    if not manifest_exists and not table_exists:
        return (
            "missing",
            "missing hotspot manifest/table pair; "
            f"surface_output_exists={surface_exists} summary_output_exists={summary_exists}",
        )
    if manifest_exists != table_exists:
        return (
            "partial",
            "partial hotspot manifest/table pair; "
            f"manifest_exists={manifest_exists} table_exists={table_exists} "
            f"surface_output_exists={surface_exists} summary_output_exists={summary_exists}",
        )
    return (
        "partial",
        f"semantic reload failed: {type(exc).__name__}: {exc}",
    )


def _normalize_requested_region_ids(
    requested_region_ids: Iterable[str] | None,
) -> tuple[str, ...]:
    if requested_region_ids is None:
        return ()

    normalized: list[str] = []
    for entry in requested_region_ids:
        normalized.extend(
            validate_stem_token(part.strip(), label="region_id")
            for part in str(entry).split(",")
            if part.strip()
        )
    return tuple(normalized)


def _selector_identity(
    *,
    subset: str | None,
    requested_region_ids: tuple[str, ...],
    resolved_region_ids: tuple[str, ...],
) -> tuple[str, str]:
    if subset is not None:
        normalized_subset = validate_stem_token(subset, label="subset")
        return (f"subset={normalized_subset}", f"subset-{normalized_subset}")
    if requested_region_ids:
        joined = "+".join(resolved_region_ids)
        validate_stem_token(joined, label="selector_regions")
        return (f"regions={list(resolved_region_ids)}", f"regions-{joined}")
    return ("subset=canonical", "subset-canonical")


def _scaleout_readiness_report_stem(
    *,
    subset: str | None,
    requested_region_ids: Iterable[str] | None,
    percentage_key: str,
    classification_key: str,
    trend_participant_ids: Iterable[str],
) -> str:
    normalized_percentage_key = validate_stem_token(
        percentage_key,
        label="percentage_key",
    )
    normalized_classification_key = validate_stem_token(
        classification_key,
        label="classification_key",
    )
    normalized_participant_ids = normalize_participant_ids(trend_participant_ids)
    participant_set_key = build_participant_set_key(normalized_participant_ids)
    normalized_regions = _normalize_requested_region_ids(requested_region_ids)

    if subset is not None:
        selector_key = f"subset-{validate_stem_token(subset, label='subset')}"
    elif normalized_regions:
        joined_regions = "+".join(normalized_regions)
        validate_stem_token(joined_regions, label="selector_regions")
        selector_key = f"regions-{joined_regions}"
    else:
        selector_key = "subset-canonical"

    return (
        f"{selector_key}__{normalized_percentage_key}__{normalized_classification_key}__"
        f"{participant_set_key}__scaleout_readiness"
    )


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
