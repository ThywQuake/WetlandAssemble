"""Derived Phase 4 paper-pack assembly from contract-backed semantic reloads.

This module reopens already-materialized Phase 4 contract artifacts and writes a
paper-facing evidence pack under a dedicated derived-output root. It never
rewrites or mutates the underlying science contract tree under ``results/phase4``.
"""

from __future__ import annotations

import json
import logging
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from WA.comparison.evidence_contract import (
    DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    DEFAULT_PHASE4_REGIONS_FILE,
    EvidenceContract,
    load_phase4_evidence_contract,
    validate_stem_token,
)
from WA.comparison.hotspot_ledger import (
    UNIFIED_HOTSPOT_LEDGER_COLUMNS,
    unified_hotspot_ledger_output_path,
)
from WA.comparison.scaleout_readiness import (
    DEFAULT_SCALEOUT_CLASSIFICATION_KEY,
    DEFAULT_SCALEOUT_PERCENTAGE_KEY,
    DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS,
    write_scaleout_readiness_report,
)
from WA.comparison.trend_hotspots import build_participant_set_key, normalize_participant_ids
from WA.visualization.phase4 import (
    load_phase4_contract_classification_summary,
    load_phase4_contract_percentage_summary,
    load_phase4_contract_percentage_surface,
    load_phase4_contract_trend_agreement_summary,
    load_phase4_contract_trend_agreement_surface,
    load_phase4_unified_hotspot_ledger,
    phase4_climatology_figure_path,
    phase4_interannual_figure_path,
    plot_phase4_climatology,
    plot_phase4_interannual,
)

logger = logging.getLogger(__name__)

DEFAULT_PHASE4_PACK_OUTPUT_ROOT = Path("results/figures/phase4_pack")
PHASE4_PACK_MANIFEST_VERSION = 1
PHASE4_PACK_PROOF_VERSION = 1
_EXPECTED_PROOF_METRIC_FAMILIES = ("percentage", "classification", "trend")


@dataclass(frozen=True)
class Phase4PackRegionArtifacts:
    """Reopened contract inputs plus derived figure outputs for one region."""

    region_id: str
    region_label: str
    percentage_summary_path: Path
    percentage_surface_path: Path
    classification_summary_path: Path
    trend_agreement_summary_path: Path
    trend_agreement_surface_path: Path
    unified_hotspot_ledger_path: Path
    interannual_figure_path: Path
    climatology_figure_path: Path


@dataclass(frozen=True)
class Phase4EvidencePackResult:
    """One completed derived Phase 4 evidence pack."""

    pack_output_root: Path
    manifest_path: Path
    summary_path: Path
    joined_regional_evidence_path: Path
    unified_hotspot_table_path: Path
    resolved_region_ids: tuple[str, ...]
    percentage_key: str
    classification_key: str
    ledger_key: str
    trend_participant_ids: tuple[str, ...]
    trend_participant_set_key: str
    region_artifacts: tuple[Phase4PackRegionArtifacts, ...]
    joined_regional_evidence_table: pd.DataFrame
    unified_hotspot_table: pd.DataFrame
    manifest: dict[str, Any]


@dataclass(frozen=True)
class Phase4EvidencePackProofResult:
    """Strict-completeness proof for one requested Phase 4 evidence pack."""

    pack_output_root: Path
    proof_json_path: Path
    proof_markdown_path: Path
    proof_verdict: str
    resolved_region_ids: tuple[str, ...]
    percentage_key: str
    classification_key: str
    ledger_key: str
    trend_participant_ids: tuple[str, ...]
    trend_participant_set_key: str
    readiness_csv_path: Path
    readiness_json_path: Path
    manifest_path: Path
    summary_path: Path
    joined_regional_evidence_path: Path
    unified_hotspot_table_path: Path
    blocking_reasons: tuple[str, ...]
    pack_build_error: str | None
    pack_result: Phase4EvidencePackResult | None
    proof_payload: dict[str, Any]


def phase4_pack_manifest_output_path(pack_output_root: str | Path) -> Path:
    """Return the deterministic manifest path for one derived pack."""

    return Path(pack_output_root) / "manifest.json"


def phase4_pack_summary_output_path(pack_output_root: str | Path) -> Path:
    """Return the deterministic narrative summary path for one derived pack."""

    return Path(pack_output_root) / "summary.md"


def phase4_pack_joined_regional_evidence_output_path(pack_output_root: str | Path) -> Path:
    """Return the deterministic joined regional evidence CSV path."""

    return Path(pack_output_root) / "tables" / "joined_regional_evidence.csv"


def phase4_pack_unified_hotspot_table_output_path(pack_output_root: str | Path) -> Path:
    """Return the deterministic unified hotspot CSV path."""

    return Path(pack_output_root) / "tables" / "unified_hotspot_table.csv"


def phase4_pack_proof_json_output_path(pack_output_root: str | Path) -> Path:
    """Return the deterministic machine-readable proof artifact path."""

    return Path(pack_output_root) / "proof" / "complete_pack_proof.json"


def phase4_pack_proof_markdown_output_path(pack_output_root: str | Path) -> Path:
    """Return the deterministic Markdown proof artifact path."""

    return Path(pack_output_root) / "proof" / "complete_pack_proof.md"


def build_phase4_evidence_pack(
    *,
    phase4_output_root: str | Path = DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    pack_output_root: str | Path = DEFAULT_PHASE4_PACK_OUTPUT_ROOT,
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
    subset: str | None = None,
    requested_region_ids: Iterable[str] | None = None,
    percentage_key: str = DEFAULT_SCALEOUT_PERCENTAGE_KEY,
    classification_key: str = DEFAULT_SCALEOUT_CLASSIFICATION_KEY,
    ledger_key: str = "canonical",
    trend_participant_ids: Iterable[str] = DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS,
) -> Phase4EvidencePackResult:
    """Assemble one derived paper-facing pack from semantic contract reloads."""

    contract = load_phase4_evidence_contract(
        output_root=phase4_output_root,
        regions_file=regions_file,
    )
    pack_root = _validate_pack_output_root(
        pack_output_root=pack_output_root,
        phase4_output_root=contract.output_root,
    )
    normalized_percentage_key = validate_stem_token(
        percentage_key,
        label="percentage_key",
    )
    normalized_classification_key = validate_stem_token(
        classification_key,
        label="classification_key",
    )
    normalized_ledger_key = validate_stem_token(ledger_key, label="ledger_key")
    normalized_participant_ids = normalize_participant_ids(trend_participant_ids)
    participant_set_key = build_participant_set_key(normalized_participant_ids)
    regions = contract.resolve_regions(
        subset=subset,
        requested_region_ids=requested_region_ids,
    )
    resolved_region_ids = tuple(region.region_id for region in regions)

    manifest_path = phase4_pack_manifest_output_path(pack_root)
    if manifest_path.exists():
        manifest_path.unlink()
        logger.info(
            "stage=pack action=clear-stale-manifest path=%s",
            manifest_path,
        )

    logger.info(
        "stage=pack action=start subset=%s region_ids=%s percentage_key=%s "
        "classification_key=%s ledger_key=%s participant_set_key=%s pack_output_root=%s",
        subset or ("explicit-region-list" if requested_region_ids is not None else "canonical"),
        list(resolved_region_ids),
        normalized_percentage_key,
        normalized_classification_key,
        normalized_ledger_key,
        participant_set_key,
        pack_root,
    )

    joined_rows: list[dict[str, object]] = []
    hotspot_tables: list[pd.DataFrame] = []
    region_artifacts: list[Phase4PackRegionArtifacts] = []

    figures_root = pack_root / "figures"
    for region_order, region in enumerate(regions, start=1):
        logger.info(
            "stage=pack region=%s action=reload-start order=%s label=%s",
            region.region_id,
            region_order,
            region.label,
        )
        percentage_summary = _reload_with_context(
            label="percentage-summary",
            region_id=region.region_id,
            loader=lambda region_id=region.region_id: load_phase4_contract_percentage_summary(
                region_id=region_id,
                dataset_key=normalized_percentage_key,
                output_root=contract.output_root,
                regions_file=contract.regions_file,
            ),
        )
        percentage_surface = _reload_with_context(
            label="percentage-surface",
            region_id=region.region_id,
            loader=lambda region_id=region.region_id: load_phase4_contract_percentage_surface(
                region_id=region_id,
                dataset_key=normalized_percentage_key,
                output_root=contract.output_root,
                regions_file=contract.regions_file,
            ),
        )
        classification_summary = _reload_with_context(
            label="classification-summary",
            region_id=region.region_id,
            loader=lambda region_id=region.region_id: load_phase4_contract_classification_summary(
                region_id=region_id,
                dataset_key=normalized_classification_key,
                output_root=contract.output_root,
                regions_file=contract.regions_file,
            ),
        )
        trend_summary = _reload_with_context(
            label="trend-agreement-summary",
            region_id=region.region_id,
            loader=lambda region_id=region.region_id: load_phase4_contract_trend_agreement_summary(
                region_id=region_id,
                participant_ids=normalized_participant_ids,
                output_root=contract.output_root,
                regions_file=contract.regions_file,
            ),
        )
        trend_surface = _reload_with_context(
            label="trend-agreement-surface",
            region_id=region.region_id,
            loader=lambda region_id=region.region_id: load_phase4_contract_trend_agreement_surface(
                region_id=region_id,
                participant_ids=normalized_participant_ids,
                output_root=contract.output_root,
                regions_file=contract.regions_file,
            ),
        )
        unified_ledger = _reload_with_context(
            label="unified-hotspot-ledger",
            region_id=region.region_id,
            loader=lambda region_id=region.region_id: load_phase4_unified_hotspot_ledger(
                region_id=region_id,
                ledger_key=normalized_ledger_key,
                output_root=contract.output_root,
                regions_file=contract.regions_file,
            ),
        )

        annual_rows, climatology_rows = _validate_percentage_summary_for_pack(
            region_id=region.region_id,
            summary_table=percentage_summary.table,
            expected_dataset_ids=percentage_summary.dataset_ids,
        )
        classification_row = _select_single_summary_row(
            region_id=region.region_id,
            family_label="classification-summary",
            table=classification_summary.table,
        )
        trend_row = _select_trend_region_row(
            region_id=region.region_id,
            table=trend_summary.table,
        )

        interannual_path = phase4_interannual_figure_path(
            figures_root=figures_root,
            region_id=region.region_id,
        )
        climatology_path = phase4_climatology_figure_path(
            figures_root=figures_root,
            region_id=region.region_id,
        )
        logger.info(
            "stage=pack region=%s action=figure-write interannual=%s climatology=%s",
            region.region_id,
            interannual_path,
            climatology_path,
        )
        plot_phase4_interannual(
            percentage_summary.table,
            region_label=region.label,
            output_path=interannual_path,
        )
        plot_phase4_climatology(
            percentage_summary.table,
            region_label=region.label,
            output_path=climatology_path,
        )

        joined_row = _build_joined_regional_evidence_row(
            contract=contract,
            region_id=region.region_id,
            region_label=region.label,
            region_order=region_order,
            percentage_key=normalized_percentage_key,
            classification_key=normalized_classification_key,
            ledger_key=normalized_ledger_key,
            participant_set_key=participant_set_key,
            annual_rows=annual_rows,
            climatology_rows=climatology_rows,
            percentage_summary=percentage_summary,
            percentage_surface=percentage_surface,
            classification_summary=classification_summary,
            classification_row=classification_row,
            trend_summary=trend_summary,
            trend_surface=trend_surface,
            trend_row=trend_row,
            unified_ledger=unified_ledger,
        )
        joined_rows.append(joined_row)
        hotspot_tables.append(
            _build_pack_hotspot_table_rows(
                contract=contract,
                region_id=region.region_id,
                region_order=region_order,
                unified_ledger=unified_ledger.table,
                ledger_path=unified_ledger.ledger_path,
            )
        )
        region_artifacts.append(
            Phase4PackRegionArtifacts(
                region_id=region.region_id,
                region_label=region.label,
                percentage_summary_path=percentage_summary.summary_path,
                percentage_surface_path=percentage_surface.surface_path,
                classification_summary_path=classification_summary.summary_path,
                trend_agreement_summary_path=trend_summary.summary_path,
                trend_agreement_surface_path=trend_surface.surface_path,
                unified_hotspot_ledger_path=unified_ledger.ledger_path,
                interannual_figure_path=interannual_path.resolve(),
                climatology_figure_path=climatology_path.resolve(),
            )
        )
        logger.info(
            "stage=pack region=%s action=ready annual_rows=%s climatology_rows=%s ledger_rows=%s",
            region.region_id,
            len(annual_rows),
            len(climatology_rows),
            len(unified_ledger.table),
        )

    joined_table = pd.DataFrame(joined_rows)
    if hotspot_tables:
        hotspot_table = pd.concat(hotspot_tables, ignore_index=True)
    else:
        hotspot_table = pd.DataFrame()

    joined_regional_evidence_path = phase4_pack_joined_regional_evidence_output_path(pack_root)
    unified_hotspot_table_path = phase4_pack_unified_hotspot_table_output_path(pack_root)
    summary_path = phase4_pack_summary_output_path(pack_root)

    _write_csv_atomic(joined_regional_evidence_path, joined_table)
    _write_csv_atomic(unified_hotspot_table_path, hotspot_table)
    summary_text = _build_pack_summary_markdown(
        pack_root=pack_root,
        contract=contract,
        resolved_region_ids=resolved_region_ids,
        percentage_key=normalized_percentage_key,
        classification_key=normalized_classification_key,
        ledger_key=normalized_ledger_key,
        trend_participant_ids=normalized_participant_ids,
        trend_participant_set_key=participant_set_key,
        joined_table=joined_table,
        hotspot_table=hotspot_table,
        region_artifacts=tuple(region_artifacts),
    )
    _write_text_atomic(summary_path, summary_text)

    manifest = _build_pack_manifest(
        pack_root=pack_root,
        contract=contract,
        resolved_region_ids=resolved_region_ids,
        percentage_key=normalized_percentage_key,
        classification_key=normalized_classification_key,
        ledger_key=normalized_ledger_key,
        trend_participant_ids=normalized_participant_ids,
        trend_participant_set_key=participant_set_key,
        joined_table=joined_table,
        hotspot_table=hotspot_table,
        region_artifacts=tuple(region_artifacts),
        summary_path=summary_path,
        joined_regional_evidence_path=joined_regional_evidence_path,
        unified_hotspot_table_path=unified_hotspot_table_path,
        manifest_path=manifest_path,
    )
    _write_text_atomic(
        manifest_path,
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )

    logger.info(
        "stage=pack action=complete regions=%s figures=%s joined_rows=%s "
        "hotspot_rows=%s manifest=%s",
        list(resolved_region_ids),
        len(region_artifacts) * 2,
        len(joined_table),
        len(hotspot_table),
        manifest_path,
    )
    return Phase4EvidencePackResult(
        pack_output_root=pack_root,
        manifest_path=manifest_path.resolve(),
        summary_path=summary_path.resolve(),
        joined_regional_evidence_path=joined_regional_evidence_path.resolve(),
        unified_hotspot_table_path=unified_hotspot_table_path.resolve(),
        resolved_region_ids=resolved_region_ids,
        percentage_key=normalized_percentage_key,
        classification_key=normalized_classification_key,
        ledger_key=normalized_ledger_key,
        trend_participant_ids=normalized_participant_ids,
        trend_participant_set_key=participant_set_key,
        region_artifacts=tuple(region_artifacts),
        joined_regional_evidence_table=joined_table,
        unified_hotspot_table=hotspot_table,
        manifest=manifest,
    )


def build_phase4_evidence_pack_proof(
    *,
    phase4_output_root: str | Path = DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    pack_output_root: str | Path = DEFAULT_PHASE4_PACK_OUTPUT_ROOT,
    regions_file: str | Path = DEFAULT_PHASE4_REGIONS_FILE,
    subset: str | None = None,
    requested_region_ids: Iterable[str] | None = None,
    percentage_key: str = DEFAULT_SCALEOUT_PERCENTAGE_KEY,
    classification_key: str = DEFAULT_SCALEOUT_CLASSIFICATION_KEY,
    ledger_key: str = "canonical",
    trend_participant_ids: Iterable[str] = DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS,
) -> Phase4EvidencePackProofResult:
    """Write strict-completeness proof artifacts for one requested pack."""

    requested_region_id_tuple = tuple(requested_region_ids or ())
    contract = load_phase4_evidence_contract(
        output_root=phase4_output_root,
        regions_file=regions_file,
    )
    pack_root = _validate_pack_output_root(
        pack_output_root=pack_output_root,
        phase4_output_root=contract.output_root,
    )
    normalized_percentage_key = validate_stem_token(
        percentage_key,
        label="percentage_key",
    )
    normalized_classification_key = validate_stem_token(
        classification_key,
        label="classification_key",
    )
    normalized_ledger_key = validate_stem_token(ledger_key, label="ledger_key")
    normalized_participant_ids = normalize_participant_ids(trend_participant_ids)
    participant_set_key = build_participant_set_key(normalized_participant_ids)
    regions = contract.resolve_regions(
        subset=subset,
        requested_region_ids=requested_region_id_tuple or None,
    )
    resolved_region_ids = tuple(region.region_id for region in regions)
    selector_label = _selector_label(
        subset=subset,
        requested_region_ids=requested_region_id_tuple,
    )

    manifest_path = phase4_pack_manifest_output_path(pack_root)
    summary_path = phase4_pack_summary_output_path(pack_root)
    joined_regional_evidence_path = phase4_pack_joined_regional_evidence_output_path(pack_root)
    unified_hotspot_table_path = phase4_pack_unified_hotspot_table_output_path(pack_root)
    proof_json_path = phase4_pack_proof_json_output_path(pack_root)
    proof_markdown_path = phase4_pack_proof_markdown_output_path(pack_root)

    _clear_stale_file(manifest_path, label="manifest")
    _clear_stale_file(proof_json_path, label="proof-json")
    _clear_stale_file(proof_markdown_path, label="proof-markdown")

    logger.info(
        "stage=pack-proof action=start selector=%s region_ids=%s percentage_key=%s "
        "classification_key=%s ledger_key=%s participant_set_key=%s pack_output_root=%s",
        selector_label,
        list(resolved_region_ids),
        normalized_percentage_key,
        normalized_classification_key,
        normalized_ledger_key,
        participant_set_key,
        pack_root,
    )

    readiness_report = write_scaleout_readiness_report(
        contract=contract,
        subset=subset,
        requested_region_ids=requested_region_id_tuple or None,
        percentage_key=normalized_percentage_key,
        classification_key=normalized_classification_key,
        trend_participant_ids=normalized_participant_ids,
    )

    blocking_reasons: list[str] = []
    if readiness_report.resolved_region_ids != resolved_region_ids:
        blocking_reasons.append(
            "stage=pack-proof proof_stage=readiness-selector "
            f"resolved_region_ids={list(resolved_region_ids)} "
            f"readiness_region_ids={list(readiness_report.resolved_region_ids)}"
        )
    if readiness_report.percentage_key != normalized_percentage_key:
        blocking_reasons.append(
            "stage=pack-proof proof_stage=readiness-selector "
            f"percentage_key={readiness_report.percentage_key} expected={normalized_percentage_key}"
        )
    if readiness_report.classification_key != normalized_classification_key:
        blocking_reasons.append(
            "stage=pack-proof proof_stage=readiness-selector "
            f"classification_key={readiness_report.classification_key} "
            f"expected={normalized_classification_key}"
        )
    if readiness_report.trend_participant_set_key != participant_set_key:
        blocking_reasons.append(
            "stage=pack-proof proof_stage=readiness-selector "
            f"trend_participant_set_key={readiness_report.trend_participant_set_key} "
            f"expected={participant_set_key}"
        )

    region_entries: list[dict[str, Any]] = []
    for region_order, region in enumerate(regions, start=1):
        readiness_entry = _collect_readiness_region_records(
            report_table=readiness_report.table,
            region_id=region.region_id,
        )
        ledger_entry = _reload_ledger_for_proof(
            contract=contract,
            region_id=region.region_id,
            ledger_key=normalized_ledger_key,
            participant_set_key=participant_set_key,
        )
        region_blockers = [
            *readiness_entry.pop("blocking_reasons"),
            *ledger_entry.pop("blocking_reasons"),
        ]
        blocking_reasons.extend(region_blockers)
        region_entries.append(
            {
                "pack_region_order": int(region_order),
                "region_id": region.region_id,
                "region_label": region.label,
                "readiness": readiness_entry,
                "ledger": ledger_entry,
                "blocking_reasons": region_blockers,
            }
        )

    blocking_reasons = _dedupe_preserve_order(blocking_reasons)
    pack_result: Phase4EvidencePackResult | None = None
    pack_build_error: str | None = None
    if not blocking_reasons:
        logger.info(
            "stage=pack-proof action=pack-build-start region_ids=%s manifest=%s",
            list(resolved_region_ids),
            manifest_path,
        )
        try:
            pack_result = build_phase4_evidence_pack(
                phase4_output_root=contract.output_root,
                pack_output_root=pack_root,
                regions_file=contract.regions_file,
                subset=subset,
                requested_region_ids=requested_region_id_tuple or None,
                percentage_key=normalized_percentage_key,
                classification_key=normalized_classification_key,
                ledger_key=normalized_ledger_key,
                trend_participant_ids=normalized_participant_ids,
            )
        except Exception as exc:
            pack_build_error = str(exc)
            blocking_reasons = _dedupe_preserve_order(
                [
                    *blocking_reasons,
                    f"stage=pack-proof proof_stage=pack-build error={exc}",
                ]
            )
            logger.error(
                "stage=pack-proof action=pack-build-failed region_ids=%s error=%s",
                list(resolved_region_ids),
                exc,
            )
        else:
            logger.info(
                "stage=pack-proof action=pack-build-complete manifest=%s summary=%s",
                pack_result.manifest_path,
                pack_result.summary_path,
            )
    else:
        logger.warning(
            "stage=pack-proof action=pack-build-skipped selector=%s blocker_count=%s",
            selector_label,
            len(blocking_reasons),
        )

    proof_verdict = (
        "complete"
        if pack_result is not None and not blocking_reasons and pack_build_error is None
        else "incomplete"
    )
    proof_payload = _build_pack_proof_payload(
        proof_verdict=proof_verdict,
        pack_root=pack_root,
        contract=contract,
        subset=subset,
        requested_region_ids=requested_region_id_tuple,
        resolved_region_ids=resolved_region_ids,
        percentage_key=normalized_percentage_key,
        classification_key=normalized_classification_key,
        ledger_key=normalized_ledger_key,
        trend_participant_ids=normalized_participant_ids,
        trend_participant_set_key=participant_set_key,
        readiness_report=readiness_report,
        region_entries=tuple(region_entries),
        blocking_reasons=tuple(blocking_reasons),
        pack_build_error=pack_build_error,
        manifest_path=manifest_path,
        summary_path=summary_path,
        joined_regional_evidence_path=joined_regional_evidence_path,
        unified_hotspot_table_path=unified_hotspot_table_path,
        pack_result=pack_result,
    )
    _write_text_atomic(
        proof_json_path,
        json.dumps(proof_payload, indent=2, sort_keys=True) + "\n",
    )
    _write_text_atomic(
        proof_markdown_path,
        _build_pack_proof_markdown(proof_payload),
    )

    logger.info(
        "stage=pack-proof action=complete verdict=%s proof_json=%s proof_markdown=%s manifest=%s",
        proof_verdict,
        proof_json_path,
        proof_markdown_path,
        manifest_path,
    )
    return Phase4EvidencePackProofResult(
        pack_output_root=pack_root,
        proof_json_path=proof_json_path.resolve(),
        proof_markdown_path=proof_markdown_path.resolve(),
        proof_verdict=proof_verdict,
        resolved_region_ids=resolved_region_ids,
        percentage_key=normalized_percentage_key,
        classification_key=normalized_classification_key,
        ledger_key=normalized_ledger_key,
        trend_participant_ids=normalized_participant_ids,
        trend_participant_set_key=participant_set_key,
        readiness_csv_path=readiness_report.csv_path.resolve(),
        readiness_json_path=readiness_report.json_path.resolve(),
        manifest_path=manifest_path.resolve(),
        summary_path=summary_path.resolve(),
        joined_regional_evidence_path=joined_regional_evidence_path.resolve(),
        unified_hotspot_table_path=unified_hotspot_table_path.resolve(),
        blocking_reasons=tuple(blocking_reasons),
        pack_build_error=pack_build_error,
        pack_result=pack_result,
        proof_payload=proof_payload,
    )


def _collect_readiness_region_records(
    *,
    report_table: pd.DataFrame,
    region_id: str,
) -> dict[str, Any]:
    region_rows = report_table.loc[
        report_table["region_id"].astype(str).str.strip() == region_id
    ].copy()
    metric_families = {
        str(value).strip() for value in region_rows["metric_family"].astype(str).tolist()
    }
    extra_metric_families = sorted(metric_families - set(_EXPECTED_PROOF_METRIC_FAMILIES))
    rows: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []

    if extra_metric_families:
        blocking_reasons.append(
            "stage=pack-proof region_id="
            f"{region_id} proof_stage=readiness extra_metric_families={extra_metric_families}"
        )

    for metric_family in _EXPECTED_PROOF_METRIC_FAMILIES:
        family_rows = region_rows.loc[
            region_rows["metric_family"].astype(str).str.strip() == metric_family
        ].copy()
        if family_rows.empty:
            rows.append(
                {
                    "region_id": region_id,
                    "metric_family": metric_family,
                    "status": "missing",
                    "reason": "readiness row missing from deterministic report",
                    "region_ready": False,
                }
            )
            blocking_reasons.append(
                "stage=pack-proof region_id="
                f"{region_id} metric_family={metric_family} proof_stage=readiness "
                "error=missing readiness row"
            )
            continue
        if len(family_rows) > 1:
            blocking_reasons.append(
                "stage=pack-proof region_id="
                f"{region_id} metric_family={metric_family} proof_stage=readiness "
                f"error=duplicate readiness rows count={len(family_rows)}"
            )
        row = family_rows.iloc[0]
        record = {
            column: _json_ready_value(row[column])
            for column in report_table.columns
            if column in family_rows.columns
        }
        rows.append(record)
        logger.info(
            "stage=pack-proof region=%s action=readiness-row metric_family=%s status=%s reason=%s",
            region_id,
            metric_family,
            record.get("status"),
            record.get("reason"),
        )
        if record.get("status") != "ready":
            blocking_reasons.append(
                "stage=pack-proof region_id="
                f"{region_id} metric_family={metric_family} proof_stage=readiness "
                f"status={record.get('status')} reason={record.get('reason')}"
            )

    region_ready = not blocking_reasons and all(
        row.get("status") == "ready" for row in rows
    )
    return {
        "region_ready": region_ready,
        "rows": rows,
        "blocking_reasons": blocking_reasons,
    }


def _reload_ledger_for_proof(
    *,
    contract: EvidenceContract,
    region_id: str,
    ledger_key: str,
    participant_set_key: str,
) -> dict[str, Any]:
    expected_ledger_path = unified_hotspot_ledger_output_path(
        contract,
        ledger_key=ledger_key,
        region_id=region_id,
    ).resolve()
    try:
        bundle = load_phase4_unified_hotspot_ledger(
            region_id=region_id,
            ledger_key=ledger_key,
            output_root=contract.output_root,
            regions_file=contract.regions_file,
        )
    except Exception as exc:
        logger.warning(
            "stage=pack-proof region=%s action=ledger-reload-failed ledger_path=%s error=%s",
            region_id,
            expected_ledger_path,
            exc,
        )
        return {
            "ledger_path": str(expected_ledger_path),
            "ledger_relpath": _relative_to_root(
                expected_ledger_path,
                contract.output_root,
                label="unified_hotspot_ledger_path",
            ),
            "ledger_exists": expected_ledger_path.is_file(),
            "row_count": 0,
            "metric_families": [],
            "trend_family_keys": [],
            "trend_line_specific_participant_set_keys": [],
            "error": str(exc),
            "blocking_reasons": [
                "stage=pack-proof region_id="
                f"{region_id} metric_family=unified-hotspot-ledger proof_stage=ledger-reload "
                f"error={exc}"
            ],
        }

    metric_families = tuple(
        sorted({str(value).strip() for value in bundle.table["metric_family"].tolist()})
    )
    trend_rows = bundle.table.loc[
        bundle.table["metric_family"].astype(str).str.strip() == "trend"
    ].copy()
    trend_family_keys = tuple(
        sorted({str(value).strip() for value in trend_rows["family_key"].tolist()})
    )
    trend_line_specific_participant_set_keys = tuple(
        sorted(
            {
                str(value.get("participant_set_key", "")).strip()
                for value in trend_rows["line_specific"].tolist()
                if isinstance(value, dict)
                and str(value.get("participant_set_key", "")).strip()
            }
        )
    )

    blocking_reasons: list[str] = []
    if trend_family_keys != (participant_set_key,):
        blocking_reasons.append(
            "stage=pack-proof region_id="
            f"{region_id} metric_family=trend proof_stage=ledger-selector "
            f"expected_participant_set_key={participant_set_key} "
            f"observed_family_keys={list(trend_family_keys)}"
        )
    if (
        trend_line_specific_participant_set_keys
        and trend_line_specific_participant_set_keys != (participant_set_key,)
    ):
        blocking_reasons.append(
            "stage=pack-proof region_id="
            f"{region_id} metric_family=trend proof_stage=ledger-selector "
            f"expected_participant_set_key={participant_set_key} "
            "observed_line_specific_participant_set_keys="
            f"{list(trend_line_specific_participant_set_keys)}"
        )

    logger.info(
        "stage=pack-proof region=%s action=ledger-ready rows=%s metric_families=%s path=%s",
        region_id,
        len(bundle.table),
        list(metric_families),
        bundle.ledger_path,
    )
    return {
        "ledger_path": str(bundle.ledger_path),
        "ledger_relpath": _relative_to_root(
            bundle.ledger_path,
            contract.output_root,
            label="unified_hotspot_ledger_path",
        ),
        "ledger_exists": True,
        "row_count": int(len(bundle.table)),
        "metric_families": list(metric_families),
        "trend_family_keys": list(trend_family_keys),
        "trend_line_specific_participant_set_keys": list(
            trend_line_specific_participant_set_keys
        ),
        "error": None,
        "blocking_reasons": blocking_reasons,
    }


def _build_pack_proof_payload(
    *,
    proof_verdict: str,
    pack_root: Path,
    contract: EvidenceContract,
    subset: str | None,
    requested_region_ids: tuple[str, ...],
    resolved_region_ids: tuple[str, ...],
    percentage_key: str,
    classification_key: str,
    ledger_key: str,
    trend_participant_ids: tuple[str, ...],
    trend_participant_set_key: str,
    readiness_report,
    region_entries: tuple[dict[str, Any], ...],
    blocking_reasons: tuple[str, ...],
    pack_build_error: str | None,
    manifest_path: Path,
    summary_path: Path,
    joined_regional_evidence_path: Path,
    unified_hotspot_table_path: Path,
    pack_result: Phase4EvidencePackResult | None,
) -> dict[str, Any]:
    figure_count = len(pack_result.region_artifacts) * 2 if pack_result is not None else 0
    joined_row_count = (
        int(len(pack_result.joined_regional_evidence_table)) if pack_result is not None else 0
    )
    hotspot_row_count = (
        int(len(pack_result.unified_hotspot_table)) if pack_result is not None else 0
    )
    return {
        "artifact_kind": "phase4_complete_pack_proof",
        "proof_version": PHASE4_PACK_PROOF_VERSION,
        "proof_verdict": proof_verdict,
        "complete_pack_claim_allowed": proof_verdict == "complete",
        "phase4_output_root": str(contract.output_root.resolve()),
        "pack_output_root": str(pack_root.resolve()),
        "regions_file": str(contract.regions_file.resolve()),
        "selector": {
            "subset": subset,
            "requested_region_ids": list(requested_region_ids),
            "resolved_region_ids": list(resolved_region_ids),
        },
        "keys": {
            "percentage_key": percentage_key,
            "classification_key": classification_key,
            "ledger_key": ledger_key,
            "trend_participant_ids": list(trend_participant_ids),
            "trend_participant_set_key": trend_participant_set_key,
        },
        "readiness_report": {
            "generated_at": readiness_report.generated_at,
            "selector_label": readiness_report.selector_label,
            "selector_key": readiness_report.selector_key,
            "csv_path": str(readiness_report.csv_path.resolve()),
            "json_path": str(readiness_report.json_path.resolve()),
            "ready_region_ids": list(readiness_report.ready_region_ids),
            "incomplete_region_ids": list(readiness_report.incomplete_region_ids),
        },
        "pack_outputs": {
            "manifest_path": str(manifest_path.resolve()),
            "manifest_relpath": _relative_to_root(
                manifest_path,
                pack_root,
                label="manifest_path",
            ),
            "manifest_exists": manifest_path.is_file(),
            "summary_path": str(summary_path.resolve()),
            "summary_relpath": _relative_to_root(
                summary_path,
                pack_root,
                label="summary_path",
            ),
            "summary_exists": summary_path.is_file(),
            "joined_regional_evidence_path": str(joined_regional_evidence_path.resolve()),
            "joined_regional_evidence_relpath": _relative_to_root(
                joined_regional_evidence_path,
                pack_root,
                label="joined_regional_evidence_path",
            ),
            "joined_regional_evidence_exists": joined_regional_evidence_path.is_file(),
            "unified_hotspot_table_path": str(unified_hotspot_table_path.resolve()),
            "unified_hotspot_table_relpath": _relative_to_root(
                unified_hotspot_table_path,
                pack_root,
                label="unified_hotspot_table_path",
            ),
            "unified_hotspot_table_exists": unified_hotspot_table_path.is_file(),
            "output_counts": {
                "resolved_region_count": len(resolved_region_ids),
                "figure_count": figure_count,
                "joined_regional_evidence_rows": joined_row_count,
                "unified_hotspot_rows": hotspot_row_count,
            },
        },
        "regions": list(region_entries),
        "blocking_reasons": list(blocking_reasons),
        "pack_build_error": pack_build_error,
    }


def _build_pack_proof_markdown(proof_payload: dict[str, Any]) -> str:
    selector = proof_payload["selector"]
    keys = proof_payload["keys"]
    readiness_report = proof_payload["readiness_report"]
    pack_outputs = proof_payload["pack_outputs"]
    lines = [
        "# Phase 4 Complete-Pack Proof",
        "",
        "## Proof Verdict",
        "",
        f"- proof_verdict: `{proof_payload['proof_verdict']}`",
        "- complete_pack_claim_allowed: "
        f"`{proof_payload['complete_pack_claim_allowed']}`",
        f"- pack_build_error: `{proof_payload['pack_build_error'] or 'None'}`",
        "",
        "## Selector",
        "",
        f"- subset: `{selector['subset']}`",
        f"- requested_region_ids: `{selector['requested_region_ids']}`",
        f"- resolved_region_ids: `{selector['resolved_region_ids']}`",
        "",
        "## Keys",
        "",
        f"- percentage_key: `{keys['percentage_key']}`",
        f"- classification_key: `{keys['classification_key']}`",
        f"- ledger_key: `{keys['ledger_key']}`",
        f"- trend_participant_ids: `{keys['trend_participant_ids']}`",
        f"- trend_participant_set_key: `{keys['trend_participant_set_key']}`",
        "",
        "## Readiness Report",
        "",
        f"- csv_path: `{readiness_report['csv_path']}`",
        f"- json_path: `{readiness_report['json_path']}`",
        f"- ready_region_ids: `{readiness_report['ready_region_ids']}`",
        f"- incomplete_region_ids: `{readiness_report['incomplete_region_ids']}`",
        "",
        "## Pack Outputs",
        "",
        f"- manifest_path: `{pack_outputs['manifest_path']}`",
        f"- manifest_exists: `{pack_outputs['manifest_exists']}`",
        f"- summary_path: `{pack_outputs['summary_path']}`",
        f"- joined_regional_evidence_path: `{pack_outputs['joined_regional_evidence_path']}`",
        f"- unified_hotspot_table_path: `{pack_outputs['unified_hotspot_table_path']}`",
        f"- output_counts: `{pack_outputs['output_counts']}`",
        "",
        "## Blocking Reasons",
        "",
    ]
    if proof_payload["blocking_reasons"]:
        lines.extend(f"- {reason}" for reason in proof_payload["blocking_reasons"])
    else:
        lines.append("- None.")

    lines.extend(["", "## Region Proof", ""])
    for region_entry in proof_payload["regions"]:
        readiness = region_entry["readiness"]
        ledger = region_entry["ledger"]
        lines.extend(
            [
                "### "
                f"{region_entry['region_label']} (`{region_entry['region_id']}`)",
                "",
                f"- pack_region_order: `{region_entry['pack_region_order']}`",
                f"- readiness_region_ready: `{readiness['region_ready']}`",
                f"- readiness_rows: `{readiness['rows']}`",
                f"- ledger_path: `{ledger['ledger_path']}`",
                f"- ledger_exists: `{ledger['ledger_exists']}`",
                f"- ledger_row_count: `{ledger['row_count']}`",
                f"- ledger_metric_families: `{ledger['metric_families']}`",
                f"- ledger_trend_family_keys: `{ledger['trend_family_keys']}`",
                "- ledger_line_specific_participant_set_keys: "
                f"`{ledger['trend_line_specific_participant_set_keys']}`",
                f"- blocking_reasons: `{region_entry['blocking_reasons'] or 'None'}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _selector_label(*, subset: str | None, requested_region_ids: tuple[str, ...]) -> str:
    if subset is not None:
        return subset
    if requested_region_ids:
        return "explicit-region-list"
    return "canonical"


def _clear_stale_file(path: Path, *, label: str) -> None:
    if path.exists():
        path.unlink()
        logger.info(
            "stage=pack-proof action=clear-stale-%s path=%s",
            label,
            path,
        )


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _json_ready_value(value: object) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready_value(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # pragma: no cover - defensive scalar fallback
            pass
    return str(value)


def _reload_with_context(*, label: str, region_id: str, loader):
    try:
        return loader()
    except Exception as exc:
        raise ValueError(
            f"stage=pack region_id={region_id} family={label} error={exc}"
        ) from exc


def _validate_pack_output_root(
    *,
    pack_output_root: str | Path,
    phase4_output_root: str | Path,
) -> Path:
    pack_root = Path(pack_output_root)
    phase4_root = Path(phase4_output_root)
    pack_resolved = pack_root.resolve(strict=False)
    phase4_resolved = phase4_root.resolve(strict=False)

    if pack_root.exists() and not pack_root.is_dir():
        raise NotADirectoryError(
            f"stage=pack pack_output_root is not a directory: {pack_root}"
        )
    if pack_resolved == phase4_resolved or phase4_resolved in pack_resolved.parents:
        raise ValueError(
            "stage=pack pack_output_root must sit outside the phase4 science contract tree: "
            f"pack_output_root={pack_root} phase4_output_root={phase4_root}"
        )
    pack_root.mkdir(parents=True, exist_ok=True)
    return pack_root.resolve()


def _validate_percentage_summary_for_pack(
    *,
    region_id: str,
    summary_table: pd.DataFrame,
    expected_dataset_ids: tuple[str, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if any(str(value).strip() != region_id for value in summary_table["region_id"]):
        raise ValueError(
            f"stage=pack region_id={region_id} family=percentage-summary mixed region_id values"
        )

    annual_rows = summary_table.loc[
        summary_table["series_type"].astype(str).str.strip() == "annual"
    ].copy()
    climatology_rows = summary_table.loc[
        summary_table["series_type"].astype(str).str.strip() == "climatology"
    ].copy()
    if annual_rows.empty:
        raise ValueError(
            f"stage=pack region_id={region_id} family=percentage-summary missing annual rows"
        )
    if climatology_rows.empty:
        raise ValueError(
            f"stage=pack region_id={region_id} family=percentage-summary missing climatology rows"
        )

    annual_dataset_ids = set(annual_rows["dataset_id"].astype(str))
    climatology_dataset_ids = set(climatology_rows["dataset_id"].astype(str))
    missing_annual = [
        dataset_id
        for dataset_id in expected_dataset_ids
        if dataset_id not in annual_dataset_ids
    ]
    missing_climatology = [
        dataset_id
        for dataset_id in expected_dataset_ids
        if dataset_id not in climatology_dataset_ids
    ]
    if missing_annual:
        raise ValueError(
            "stage=pack "
            f"region_id={region_id} family=percentage-summary missing annual rows for "
            + ", ".join(missing_annual)
        )
    if missing_climatology:
        raise ValueError(
            "stage=pack "
            f"region_id={region_id} family=percentage-summary missing climatology rows for "
            + ", ".join(missing_climatology)
        )
    return (annual_rows, climatology_rows)


def _select_single_summary_row(
    *,
    region_id: str,
    family_label: str,
    table: pd.DataFrame,
) -> pd.Series:
    if len(table) != 1:
        raise ValueError(
            "stage=pack "
            f"region_id={region_id} family={family_label} expected exactly one row, "
            f"got {len(table)}"
        )
    return table.iloc[0]


def _select_trend_region_row(*, region_id: str, table: pd.DataFrame) -> pd.Series:
    region_rows = table.loc[table["region"].astype(str).str.strip() == region_id].copy()
    if len(region_rows) != 1:
        raise ValueError(
            "stage=pack "
            f"region_id={region_id} family=trend-agreement-summary "
            "expected exactly one regional row, "
            f"got {len(region_rows)}"
        )
    return region_rows.iloc[0]


def _build_joined_regional_evidence_row(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_label: str,
    region_order: int,
    percentage_key: str,
    classification_key: str,
    ledger_key: str,
    participant_set_key: str,
    annual_rows: pd.DataFrame,
    climatology_rows: pd.DataFrame,
    percentage_summary,
    percentage_surface,
    classification_summary,
    classification_row: pd.Series,
    trend_summary,
    trend_surface,
    trend_row: pd.Series,
    unified_ledger,
) -> dict[str, object]:
    row: dict[str, object] = {
        "pack_region_order": int(region_order),
        "region_id": region_id,
        "region_label": region_label,
        "percentage_key": percentage_key,
        "classification_key": classification_key,
        "ledger_key": ledger_key,
        "classification_participant_set_key": classification_summary.participant_set_key,
        "trend_participant_set_key": participant_set_key,
        "percentage_dataset_ids_json": json.dumps(
            list(percentage_summary.dataset_ids),
            separators=(",", ":"),
        ),
        "classification_participant_ids_json": json.dumps(
            list(classification_summary.participant_ids),
            separators=(",", ":"),
        ),
        "trend_participant_ids_json": json.dumps(
            list(trend_summary.participant_ids),
            separators=(",", ":"),
        ),
        "percentage_time_range_start": percentage_summary.time_range[0],
        "percentage_time_range_end": percentage_summary.time_range[1],
        "trend_overlap_window_start": trend_summary.overlap_window[0],
        "trend_overlap_window_end": trend_summary.overlap_window[1],
        "percentage_annual_row_count": int(len(annual_rows)),
        "percentage_climatology_row_count": int(len(climatology_rows)),
        "classification_target_year": int(classification_row["target_year"]),
        "classification_joint_valid_cell_count": int(
            classification_row["joint_valid_cell_count"]
        ),
        "classification_mean_entropy": float(classification_row["mean_entropy"]),
        "classification_max_entropy": float(classification_row["max_entropy"]),
        "classification_mean_agreement_count": float(
            classification_row["mean_agreement_count"]
        ),
        "classification_hotspot_selected_count": int(
            classification_row["hotspot_selected_count"]
        ),
        "classification_hotspot_shortfall": int(classification_row["hotspot_shortfall"]),
        "classification_hotspot_status": str(classification_row["hotspot_status"]),
        "trend_total_valid_pixels": int(trend_row["total_valid_pixels"]),
        "trend_mean_agreement_ratio": float(trend_row["mean_agreement_ratio"]),
        "trend_fraction_disputed": float(trend_row["fraction_disputed"]),
        "trend_mean_slope_across_datasets": float(
            trend_row["mean_slope_across_datasets"]
        ),
        "ledger_row_count": int(len(unified_ledger.table)),
        "ledger_metric_family_count": int(unified_ledger.table["metric_family"].nunique()),
        "ledger_hotspots__percentage": int(
            (unified_ledger.table["metric_family"] == "percentage").sum()
        ),
        "ledger_hotspots__classification": int(
            (unified_ledger.table["metric_family"] == "classification").sum()
        ),
        "ledger_hotspots__trend": int(
            (unified_ledger.table["metric_family"] == "trend").sum()
        ),
        "percentage_summary_path": str(percentage_summary.summary_path),
        "percentage_summary_relpath": _relative_to_root(
            percentage_summary.summary_path,
            contract.output_root,
            label="percentage_summary_path",
        ),
        "percentage_surface_path": str(percentage_surface.surface_path),
        "percentage_surface_relpath": _relative_to_root(
            percentage_surface.surface_path,
            contract.output_root,
            label="percentage_surface_path",
        ),
        "classification_summary_path": str(classification_summary.summary_path),
        "classification_summary_relpath": _relative_to_root(
            classification_summary.summary_path,
            contract.output_root,
            label="classification_summary_path",
        ),
        "trend_agreement_summary_path": str(trend_summary.summary_path),
        "trend_agreement_summary_relpath": _relative_to_root(
            trend_summary.summary_path,
            contract.output_root,
            label="trend_agreement_summary_path",
        ),
        "trend_agreement_surface_path": str(trend_surface.surface_path),
        "trend_agreement_surface_relpath": _relative_to_root(
            trend_surface.surface_path,
            contract.output_root,
            label="trend_agreement_surface_path",
        ),
        "unified_hotspot_ledger_path": str(unified_ledger.ledger_path),
        "unified_hotspot_ledger_relpath": _relative_to_root(
            unified_ledger.ledger_path,
            contract.output_root,
            label="unified_hotspot_ledger_path",
        ),
    }

    for dataset_id in percentage_summary.dataset_ids:
        annual_subset = annual_rows.loc[annual_rows["dataset_id"].astype(str) == dataset_id]
        climatology_subset = climatology_rows.loc[
            climatology_rows["dataset_id"].astype(str) == dataset_id
        ]
        row[f"percentage_annual_mean__{dataset_id}"] = float(
            annual_subset["wetland_percentage"].mean()
        )
        row[f"percentage_annual_peak__{dataset_id}"] = float(
            annual_subset["wetland_percentage"].max()
        )
        row[f"percentage_climatology_mean__{dataset_id}"] = float(
            climatology_subset["wetland_percentage"].mean()
        )
        row[f"percentage_climatology_peak__{dataset_id}"] = float(
            climatology_subset["wetland_percentage"].max()
        )
    return row


def _build_pack_hotspot_table_rows(
    *,
    contract: EvidenceContract,
    region_id: str,
    region_order: int,
    unified_ledger: pd.DataFrame,
    ledger_path: Path,
) -> pd.DataFrame:
    ledger_frame = unified_ledger.loc[:, list(UNIFIED_HOTSPOT_LEDGER_COLUMNS)].copy()
    ledger_frame.insert(0, "pack_region_order", int(region_order))
    ledger_frame.insert(1, "source_ledger_path", str(ledger_path))
    ledger_frame.insert(
        2,
        "source_ledger_relpath",
        _relative_to_root(ledger_path, contract.output_root, label="source_ledger_path"),
    )
    if any(str(value).strip() != region_id for value in ledger_frame["region_id"]):
        raise ValueError(
            f"stage=pack region_id={region_id} family=unified-hotspot-ledger mixed region_id values"
        )
    return ledger_frame


def _build_pack_summary_markdown(
    *,
    pack_root: Path,
    contract: EvidenceContract,
    resolved_region_ids: tuple[str, ...],
    percentage_key: str,
    classification_key: str,
    ledger_key: str,
    trend_participant_ids: tuple[str, ...],
    trend_participant_set_key: str,
    joined_table: pd.DataFrame,
    hotspot_table: pd.DataFrame,
    region_artifacts: tuple[Phase4PackRegionArtifacts, ...],
) -> str:
    lines = [
        "# Phase 4 Evidence Pack",
        "",
        "## Pack Configuration",
        "",
        f"- phase4_output_root: `{contract.output_root.resolve()}`",
        f"- pack_output_root: `{pack_root.resolve()}`",
        f"- regions_file: `{contract.regions_file.resolve()}`",
        f"- resolved_region_ids: `{list(resolved_region_ids)}`",
        f"- percentage_key: `{percentage_key}`",
        f"- classification_key: `{classification_key}`",
        f"- ledger_key: `{ledger_key}`",
        f"- trend_participant_ids: `{list(trend_participant_ids)}`",
        f"- trend_participant_set_key: `{trend_participant_set_key}`",
        "",
        "## Output Counts",
        "",
        f"- joined_regional_evidence_rows: `{len(joined_table)}`",
        f"- unified_hotspot_rows: `{len(hotspot_table)}`",
        f"- figure_count: `{len(region_artifacts) * 2}`",
        "",
        "## Region Summaries",
        "",
    ]
    for artifact in region_artifacts:
        row = joined_table.loc[joined_table["region_id"] == artifact.region_id].iloc[0]
        interannual_relpath = _relative_to_root(
            artifact.interannual_figure_path,
            pack_root,
            label="interannual_figure_path",
        )
        climatology_relpath = _relative_to_root(
            artifact.climatology_figure_path,
            pack_root,
            label="climatology_figure_path",
        )
        lines.extend(
            [
                f"### {artifact.region_label} (`{artifact.region_id}`)",
                "",
                f"- interannual_figure: `{interannual_relpath}`",
                f"- climatology_figure: `{climatology_relpath}`",
                f"- classification_mean_entropy: `{row['classification_mean_entropy']:.6f}`",
                f"- classification_hotspot_status: `{row['classification_hotspot_status']}`",
                f"- trend_mean_agreement_ratio: `{row['trend_mean_agreement_ratio']:.6f}`",
                f"- trend_fraction_disputed: `{row['trend_fraction_disputed']:.6f}`",
                f"- ledger_row_count: `{int(row['ledger_row_count'])}`",
                f"- source_percentage_summary: `{row['percentage_summary_relpath']}`",
                f"- source_classification_summary: `{row['classification_summary_relpath']}`",
                f"- source_trend_agreement_summary: `{row['trend_agreement_summary_relpath']}`",
                f"- source_unified_hotspot_ledger: `{row['unified_hotspot_ledger_relpath']}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _build_pack_manifest(
    *,
    pack_root: Path,
    contract: EvidenceContract,
    resolved_region_ids: tuple[str, ...],
    percentage_key: str,
    classification_key: str,
    ledger_key: str,
    trend_participant_ids: tuple[str, ...],
    trend_participant_set_key: str,
    joined_table: pd.DataFrame,
    hotspot_table: pd.DataFrame,
    region_artifacts: tuple[Phase4PackRegionArtifacts, ...],
    summary_path: Path,
    joined_regional_evidence_path: Path,
    unified_hotspot_table_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    return {
        "artifact_kind": "phase4_evidence_pack",
        "manifest_version": PHASE4_PACK_MANIFEST_VERSION,
        "phase4_output_root": str(contract.output_root.resolve()),
        "pack_output_root": str(pack_root.resolve()),
        "regions_file": str(contract.regions_file.resolve()),
        "resolved_region_ids": list(resolved_region_ids),
        "percentage_key": percentage_key,
        "classification_key": classification_key,
        "ledger_key": ledger_key,
        "trend_participant_ids": list(trend_participant_ids),
        "trend_participant_set_key": trend_participant_set_key,
        "joined_regional_evidence_columns": list(joined_table.columns),
        "unified_hotspot_table_columns": list(hotspot_table.columns),
        "output_counts": {
            "region_count": len(resolved_region_ids),
            "figure_count": len(region_artifacts) * 2,
            "joined_regional_evidence_rows": len(joined_table),
            "unified_hotspot_rows": len(hotspot_table),
        },
        "outputs": {
            "manifest": {
                "path": str(manifest_path.resolve()),
                "relpath": _relative_to_root(manifest_path, pack_root, label="manifest_path"),
            },
            "summary": {
                "path": str(summary_path.resolve()),
                "relpath": _relative_to_root(summary_path, pack_root, label="summary_path"),
            },
            "joined_regional_evidence_table": {
                "path": str(joined_regional_evidence_path.resolve()),
                "relpath": _relative_to_root(
                    joined_regional_evidence_path,
                    pack_root,
                    label="joined_regional_evidence_path",
                ),
            },
            "unified_hotspot_table": {
                "path": str(unified_hotspot_table_path.resolve()),
                "relpath": _relative_to_root(
                    unified_hotspot_table_path,
                    pack_root,
                    label="unified_hotspot_table_path",
                ),
            },
            "figures": [
                {
                    "region_id": artifact.region_id,
                    "region_label": artifact.region_label,
                    "interannual_figure_path": str(artifact.interannual_figure_path),
                    "interannual_figure_relpath": _relative_to_root(
                        artifact.interannual_figure_path,
                        pack_root,
                        label="interannual_figure_path",
                    ),
                    "climatology_figure_path": str(artifact.climatology_figure_path),
                    "climatology_figure_relpath": _relative_to_root(
                        artifact.climatology_figure_path,
                        pack_root,
                        label="climatology_figure_path",
                    ),
                }
                for artifact in region_artifacts
            ],
        },
        "sources": [
            {
                "region_id": artifact.region_id,
                "region_label": artifact.region_label,
                "percentage_summary_path": str(artifact.percentage_summary_path),
                "percentage_summary_relpath": _relative_to_root(
                    artifact.percentage_summary_path,
                    contract.output_root,
                    label="percentage_summary_path",
                ),
                "percentage_surface_path": str(artifact.percentage_surface_path),
                "percentage_surface_relpath": _relative_to_root(
                    artifact.percentage_surface_path,
                    contract.output_root,
                    label="percentage_surface_path",
                ),
                "classification_summary_path": str(artifact.classification_summary_path),
                "classification_summary_relpath": _relative_to_root(
                    artifact.classification_summary_path,
                    contract.output_root,
                    label="classification_summary_path",
                ),
                "trend_agreement_summary_path": str(artifact.trend_agreement_summary_path),
                "trend_agreement_summary_relpath": _relative_to_root(
                    artifact.trend_agreement_summary_path,
                    contract.output_root,
                    label="trend_agreement_summary_path",
                ),
                "trend_agreement_surface_path": str(artifact.trend_agreement_surface_path),
                "trend_agreement_surface_relpath": _relative_to_root(
                    artifact.trend_agreement_surface_path,
                    contract.output_root,
                    label="trend_agreement_surface_path",
                ),
                "unified_hotspot_ledger_path": str(artifact.unified_hotspot_ledger_path),
                "unified_hotspot_ledger_relpath": _relative_to_root(
                    artifact.unified_hotspot_ledger_path,
                    contract.output_root,
                    label="unified_hotspot_ledger_path",
                ),
            }
            for artifact in region_artifacts
        ],
    }


def _relative_to_root(path: str | Path, root: str | Path, *, label: str) -> str:
    candidate = Path(path).resolve()
    root_path = Path(root).resolve()
    try:
        return str(candidate.relative_to(root_path))
    except ValueError as exc:
        raise ValueError(
            f"{label} must stay inside root={root_path}, got path={candidate}"
        ) from exc


def _write_csv_atomic(path: Path, table: pd.DataFrame) -> None:
    _write_text_atomic(path, table.to_csv(index=False, lineterminator="\n"))


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
