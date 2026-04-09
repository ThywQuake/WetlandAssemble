from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.evidence_contract import load_phase4_evidence_contract, metadata_json
from WA.comparison.hotspot_ledger import (
    UNIFIED_HOTSPOT_LEDGER_COLUMNS,
    build_unified_hotspot_ledger,
    hotspot_family_manifest_output_path,
    hotspot_family_table_output_path,
    load_contract_unified_hotspot_ledger,
    unified_hotspot_ledger_output_path,
    write_unified_hotspot_ledger,
)
from WA.comparison.scaleout_readiness import (
    scaleout_readiness_csv_output_path,
    scaleout_readiness_json_output_path,
)
from WA.comparison.trend_agreement import TrendAgreementResult
from WA.comparison.trend_hotspots import write_trend_hotspot_outputs

TREND_PARTICIPANT_IDS = ["wad2m", "gwd30"]
FULL_CONTRACT_TREND_PARTICIPANT_IDS = [
    "gwd30",
    "giems_mc",
    "topmodel",
    "swamps",
    "wad2m",
]


def _make_agreement_result(
    *,
    region_id: str,
    participant_ids: list[str],
) -> TrendAgreementResult:
    coords = {"lat": [1.0, 0.0], "lon": [100.0, 101.0]}
    agreement_ratio = xr.DataArray(
        np.array([[0.5, 0.75], [1.0, 1.0]], dtype=np.float64),
        dims=("lat", "lon"),
        coords=coords,
    )
    mean_slope = xr.DataArray(
        np.array([[0.01, 0.02], [0.03, 0.04]], dtype=np.float64),
        dims=("lat", "lon"),
        coords=coords,
    )
    slope_std = xr.DataArray(
        np.array([[0.2, 0.4], [0.1, 0.1]], dtype=np.float64),
        dims=("lat", "lon"),
        coords=coords,
    )
    disputed = xr.DataArray(
        agreement_ratio.values < 1.0,
        dims=("lat", "lon"),
        coords=coords,
    )
    false_mask = xr.zeros_like(disputed, dtype=bool)
    return TrendAgreementResult(
        overlap_window=("2001-01-01", "2010-12-31"),
        participant_ids=list(participant_ids),
        agreement_ratio=agreement_ratio,
        mean_slope=mean_slope,
        slope_std=slope_std,
        robust_increase=false_mask,
        robust_decrease=false_mask,
        robust_stable=false_mask,
        disputed=disputed,
        regional_summary=pd.DataFrame(
            {
                "region": [region_id, "global"],
                "total_valid_pixels": [2, 2],
                "mean_agreement_ratio": [0.625, 0.625],
                "fraction_robust_increase": [0.0, 0.0],
                "fraction_robust_decrease": [0.0, 0.0],
                "fraction_robust_stable": [0.0, 0.0],
                "fraction_disputed": [1.0, 1.0],
                "mean_slope_across_datasets": [0.02, 0.02],
            }
        ),
        status="computed",
    )


def _write_dummy_agreement_inputs(
    contract,
    *,
    region_id: str,
    participant_ids: list[str],
) -> tuple[Path, Path]:
    participant_set_key = "+".join(sorted(participant_ids))
    surface_path = contract.artifact_output_path(
        kind="trend_agreement_surface",
        dataset_or_key=participant_set_key,
        region_id=region_id,
    )
    summary_path = contract.artifact_output_path(
        kind="trend_agreement_summary",
        dataset_or_key=participant_set_key,
        region_id=region_id,
    )
    surface_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    surface_path.write_text("agreement-surface", encoding="utf-8")
    summary_path.write_text("agreement,summary\n", encoding="utf-8")
    return (surface_path, summary_path)


def _write_generic_hotspot_family(
    contract,
    *,
    metric_family: str,
    region_id: str,
    dataset_key: str,
    rows: list[dict[str, Any]],
) -> tuple[Path, Path]:
    manifest_path = hotspot_family_manifest_output_path(
        contract,
        metric_family=metric_family,  # type: ignore[arg-type]
        family_key=dataset_key,
        region_id=region_id,
    )
    table_path = hotspot_family_table_output_path(
        contract,
        metric_family=metric_family,  # type: ignore[arg-type]
        family_key=dataset_key,
        region_id=region_id,
    )
    if metric_family == "percentage":
        surface_kind = "surface"
        summary_kind = "regional_summary"
        artifact_kind = "hotspot_manifest"
        score_field = "wetland_percentage"
    elif metric_family == "classification":
        surface_kind = "classification_surface"
        summary_kind = "classification_regional_summary"
        artifact_kind = "classification_hotspot_manifest"
        score_field = "mean_entropy"
    else:
        raise AssertionError(metric_family)

    surface_path = contract.artifact_output_path(
        kind=surface_kind,  # type: ignore[arg-type]
        dataset_or_key=dataset_key,
        region_id=region_id,
    )
    summary_path = contract.artifact_output_path(
        kind=summary_kind,  # type: ignore[arg-type]
        dataset_or_key=dataset_key,
        region_id=region_id,
    )
    surface_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    surface_path.write_text(f"{metric_family}-surface", encoding="utf-8")
    summary_path.write_text(f"{metric_family},summary\n", encoding="utf-8")

    table = pd.DataFrame(rows)
    serializable = table.copy()
    serializable["bbox"] = serializable["bbox"].map(json.dumps)
    table_text = serializable.to_csv(index=False, lineterminator="\n")
    table_sha256 = hashlib.sha256(table_text.encode("utf-8")).hexdigest()
    table_path.parent.mkdir(parents=True, exist_ok=True)
    table_path.write_text(table_text, encoding="utf-8")

    manifest_payload = {
        "artifact_kind": artifact_kind,
        "manifest_version": 1,
        "region_id": region_id,
        "dataset_key": dataset_key,
        "hotspot_count": int(len(table)),
        "manifest_output_path": str(manifest_path.resolve()),
        "manifest_relpath": str(manifest_path.relative_to(contract.output_root)),
        "table_output_path": str(table_path.resolve()),
        "table_relpath": str(table_path.relative_to(contract.output_root)),
        "surface_output_path": str(surface_path.resolve()),
        "surface_output_relpath": str(surface_path.relative_to(contract.output_root)),
        "summary_output_path": str(summary_path.resolve()),
        "summary_output_relpath": str(summary_path.relative_to(contract.output_root)),
        "table_sha256": table_sha256,
        "contract_metadata_json": metadata_json(
            {
                "artifact_kind": artifact_kind,
                "dataset_key": dataset_key,
                "manifest_relpath": str(manifest_path.relative_to(contract.output_root)),
                "table_relpath": str(table_path.relative_to(contract.output_root)),
                "region_id": region_id,
                "surface_output_path": str(surface_path.resolve()),
                "summary_output_path": str(summary_path.resolve()),
                "primary_score_name": score_field,
            }
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path, table_path


def _base_percentage_rows(*, region_id: str) -> list[dict[str, Any]]:
    return [
        {
            "hotspot_id": f"pct-{region_id}-001",
            "hotspot_rank": 1,
            "region_id": region_id,
            "dataset_key": "canonical",
            "center_lat": 0.8,
            "center_lon": 100.2,
            "bbox": [99.9, 0.5, 100.5, 1.1],
            "wetland_percentage": 81.5,
            "wetland_area_km2": 125.0,
        },
        {
            "hotspot_id": f"pct-{region_id}-002",
            "hotspot_rank": 2,
            "region_id": region_id,
            "dataset_key": "canonical",
            "center_lat": 0.4,
            "center_lon": 100.8,
            "bbox": [100.5, 0.1, 101.1, 0.7],
            "wetland_percentage": 70.0,
            "wetland_area_km2": 95.0,
        },
    ]


def _base_classification_rows(*, region_id: str) -> list[dict[str, Any]]:
    return [
        {
            "hotspot_id": f"cls-{region_id}-001",
            "hotspot_rank": 1,
            "region_id": region_id,
            "dataset_key": "canonical",
            "center_lat": 0.9,
            "center_lon": 100.1,
            "bbox": [99.8, 0.6, 100.4, 1.2],
            "mean_entropy": 0.91,
            "max_entropy": 0.97,
            "cell_count": 16,
        }
    ]


def _write_source_families(
    contract,
    *,
    region_id: str = "amazon",
    trend_participant_ids: list[str] = TREND_PARTICIPANT_IDS,
) -> None:
    _write_generic_hotspot_family(
        contract,
        metric_family="percentage",
        region_id=region_id,
        dataset_key="canonical",
        rows=_base_percentage_rows(region_id=region_id),
    )
    _write_generic_hotspot_family(
        contract,
        metric_family="classification",
        region_id=region_id,
        dataset_key="canonical",
        rows=_base_classification_rows(region_id=region_id),
    )
    surface_path, summary_path = _write_dummy_agreement_inputs(
        contract,
        region_id=region_id,
        participant_ids=trend_participant_ids,
    )
    write_trend_hotspot_outputs(
        contract=contract,
        agreement_result=_make_agreement_result(
            region_id=region_id,
            participant_ids=trend_participant_ids,
        ),
        region_id=region_id,
        participant_ids=trend_participant_ids,
        surface_output_path=surface_path,
        summary_output_path=summary_path,
        top_n=2,
    )


def _rewrite_table_and_manifest(
    manifest_path: Path,
    table_path: Path,
    table: pd.DataFrame,
    *,
    mutate_manifest: callable | None = None,
) -> None:
    serializable = table.copy()
    serializable["bbox"] = serializable["bbox"].map(
        lambda value: value if isinstance(value, str) else json.dumps(list(value))
    )
    table_text = serializable.to_csv(index=False, lineterminator="\n")
    table_path.write_text(table_text, encoding="utf-8")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["hotspot_count"] = int(len(table))
    payload["table_sha256"] = hashlib.sha256(table_text.encode("utf-8")).hexdigest()
    if mutate_manifest is not None:
        mutate_manifest(payload)
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_build_unified_hotspot_ledger_normalizes_three_families(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_source_families(contract)

    ledger = build_unified_hotspot_ledger(
        contract=contract,
        region_id="amazon",
        ledger_key="canonical",
        percentage_key="canonical",
        classification_key="canonical",
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )

    assert list(ledger.columns) == list(UNIFIED_HOTSPOT_LEDGER_COLUMNS)
    assert ledger["metric_family"].tolist() == [
        "percentage",
        "percentage",
        "classification",
        "trend",
        "trend",
    ]
    assert ledger["analysis_object_id"].is_unique
    assert set(ledger["primary_score_name"]) == {
        "wetland_percentage",
        "mean_entropy",
        "disagreement_score",
    }

    family_percentiles = {
        family: subset["family_percentile"].tolist()
        for family, subset in ledger.groupby("metric_family")
    }
    assert family_percentiles["percentage"] == pytest.approx([1.0, 0.0])
    assert family_percentiles["classification"] == pytest.approx([1.0])
    assert family_percentiles["trend"] == pytest.approx([1.0, 0.0])

    percentage_row = ledger.loc[ledger["metric_family"] == "percentage"].iloc[0]
    percentage_payload = json.loads(percentage_row["line_specific_json"])
    assert percentage_payload["dataset_key"] == "canonical"
    assert percentage_payload["wetland_percentage"] == pytest.approx(81.5)

    trend_row = ledger.loc[ledger["metric_family"] == "trend"].iloc[0]
    trend_payload = json.loads(trend_row["line_specific_json"])
    assert trend_payload["participant_set_key"] == "gwd30+wad2m"
    assert trend_payload["disagreement_score"] == pytest.approx(0.5)


def test_write_and_reload_unified_hotspot_ledger_round_trip(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_source_families(contract)

    bundle = write_unified_hotspot_ledger(
        contract=contract,
        region_id="amazon",
        ledger_key="canonical",
        percentage_key="canonical",
        classification_key="canonical",
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )

    expected_path = unified_hotspot_ledger_output_path(
        contract,
        ledger_key="canonical",
        region_id="amazon",
    )
    assert bundle.ledger_path == expected_path.resolve()
    assert bundle.table["bbox"].tolist()[0] == pytest.approx((99.9, 0.5, 100.5, 1.1))
    assert {tuple(sorted(value.keys())) for value in bundle.table["line_specific"]} >= {
        ("dataset_key", "wetland_area_km2", "wetland_percentage"),
        ("cell_count", "dataset_key", "max_entropy", "mean_entropy"),
    }

    reloaded = load_contract_unified_hotspot_ledger(
        contract=contract,
        region_id="amazon",
        ledger_key="canonical",
    )
    assert reloaded.table["metric_family"].tolist() == bundle.table["metric_family"].tolist()
    assert reloaded.table["surface_output_path"].str.contains("amazon").all()


def test_build_unified_hotspot_ledger_requires_all_families(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_generic_hotspot_family(
        contract,
        metric_family="percentage",
        region_id="amazon",
        dataset_key="canonical",
        rows=_base_percentage_rows(region_id="amazon"),
    )
    surface_path, summary_path = _write_dummy_agreement_inputs(
        contract,
        region_id="amazon",
        participant_ids=TREND_PARTICIPANT_IDS,
    )
    write_trend_hotspot_outputs(
        contract=contract,
        agreement_result=_make_agreement_result(
            region_id="amazon",
            participant_ids=TREND_PARTICIPANT_IDS,
        ),
        region_id="amazon",
        participant_ids=TREND_PARTICIPANT_IDS,
        surface_output_path=surface_path,
        summary_output_path=summary_path,
        top_n=2,
    )

    with pytest.raises(FileNotFoundError, match="classification_hotspot_manifest"):
        build_unified_hotspot_ledger(
            contract=contract,
            region_id="amazon",
            ledger_key="canonical",
            percentage_key="canonical",
            classification_key="canonical",
            trend_participant_ids=TREND_PARTICIPANT_IDS,
        )

    ledger_path = unified_hotspot_ledger_output_path(
        contract,
        ledger_key="canonical",
        region_id="amazon",
    )
    assert not ledger_path.exists()


def test_build_unified_hotspot_ledger_rejects_mixed_region_rows(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_source_families(contract)
    manifest_path = hotspot_family_manifest_output_path(
        contract,
        metric_family="classification",
        family_key="canonical",
        region_id="amazon",
    )
    table_path = hotspot_family_table_output_path(
        contract,
        metric_family="classification",
        family_key="canonical",
        region_id="amazon",
    )
    table = pd.read_csv(table_path)
    table.loc[0, "region_id"] = "sudd"
    _rewrite_table_and_manifest(manifest_path, table_path, table)

    with pytest.raises(ValueError, match="mixed region_id"):
        build_unified_hotspot_ledger(
            contract=contract,
            region_id="amazon",
            ledger_key="canonical",
            percentage_key="canonical",
            classification_key="canonical",
            trend_participant_ids=TREND_PARTICIPANT_IDS,
        )


def test_build_unified_hotspot_ledger_rejects_malformed_manifest_metadata(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_source_families(contract)
    manifest_path = hotspot_family_manifest_output_path(
        contract,
        metric_family="percentage",
        family_key="canonical",
        region_id="amazon",
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["contract_metadata_json"] = "{"
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Malformed contract_metadata_json"):
        build_unified_hotspot_ledger(
            contract=contract,
            region_id="amazon",
            ledger_key="canonical",
            percentage_key="canonical",
            classification_key="canonical",
            trend_participant_ids=TREND_PARTICIPANT_IDS,
        )


def test_build_unified_hotspot_ledger_rejects_duplicate_analysis_object_candidates(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_source_families(contract)
    manifest_path = hotspot_family_manifest_output_path(
        contract,
        metric_family="percentage",
        family_key="canonical",
        region_id="amazon",
    )
    table_path = hotspot_family_table_output_path(
        contract,
        metric_family="percentage",
        family_key="canonical",
        region_id="amazon",
    )
    table = pd.read_csv(table_path)
    table.loc[1, "hotspot_id"] = table.loc[0, "hotspot_id"]
    _rewrite_table_and_manifest(manifest_path, table_path, table)

    with pytest.raises(ValueError, match="duplicate analysis_object_id"):
        build_unified_hotspot_ledger(
            contract=contract,
            region_id="amazon",
            ledger_key="canonical",
            percentage_key="canonical",
            classification_key="canonical",
            trend_participant_ids=TREND_PARTICIPANT_IDS,
        )


def test_run_phase4_hotspot_ledger_writes_ten_subset_representative_ledgers(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    for region_id in contract.ordered_ten_region_ids:
        _write_source_families(
            contract,
            region_id=region_id,
            trend_participant_ids=FULL_CONTRACT_TREND_PARTICIPANT_IDS,
        )

    repo_root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        "scripts/run_phase4_hotspot_ledger.py",
        "--output-root",
        str(tmp_path),
        "--subset",
        "ten",
        "--ledger-key",
        "canonical",
        "--percentage-key",
        "canonical",
        "--classification-key",
        "canonical",
        "--no-skip",
    ]
    for dataset_id in FULL_CONTRACT_TREND_PARTICIPANT_IDS:
        command.extend(["--trend-dataset-id", dataset_id])

    completed = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    combined_output = completed.stderr + completed.stdout
    assert "stage=ledger region=amazon action=ready" in combined_output
    assert "stage=ledger region=northernaus action=ready" in combined_output

    amazon_ledger = unified_hotspot_ledger_output_path(
        contract,
        ledger_key="canonical",
        region_id="amazon",
    )
    northernaus_ledger = unified_hotspot_ledger_output_path(
        contract,
        ledger_key="canonical",
        region_id="northernaus",
    )
    assert amazon_ledger.is_file()
    assert northernaus_ledger.is_file()
    ledger_paths = list(
        (tmp_path / "unified_hotspot_ledgers").rglob("*_unified_hotspot_ledger.csv")
    )
    assert len(ledger_paths) == len(contract.ordered_ten_region_ids)

    amazon_bundle = load_contract_unified_hotspot_ledger(
        contract=contract,
        region_id="amazon",
        ledger_key="canonical",
    )
    northernaus_bundle = load_contract_unified_hotspot_ledger(
        contract=contract,
        region_id="northernaus",
        ledger_key="canonical",
    )
    for bundle in (amazon_bundle, northernaus_bundle):
        assert set(bundle.table["metric_family"]) == {
            "percentage",
            "classification",
            "trend",
        }


def test_run_phase4_hotspot_ledger_help_mentions_skip_ledger_and_readiness() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/run_phase4_hotspot_ledger.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "unified hotspot ledger" in completed.stdout
    assert "run_phase4_scaleout_readiness.py" in completed.stdout
    assert "--ledger-key" in completed.stdout
    assert "--skip" in completed.stdout
    assert "--no-skip" in completed.stdout


def test_run_phase4_hotspot_ledger_fails_closed_on_missing_family(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_generic_hotspot_family(
        contract,
        metric_family="percentage",
        region_id="amazon",
        dataset_key="canonical",
        rows=_base_percentage_rows(region_id="amazon"),
    )
    surface_path, summary_path = _write_dummy_agreement_inputs(
        contract,
        region_id="amazon",
        participant_ids=TREND_PARTICIPANT_IDS,
    )
    write_trend_hotspot_outputs(
        contract=contract,
        agreement_result=_make_agreement_result(
            region_id="amazon",
            participant_ids=TREND_PARTICIPANT_IDS,
        ),
        region_id="amazon",
        participant_ids=TREND_PARTICIPANT_IDS,
        surface_output_path=surface_path,
        summary_output_path=summary_path,
        top_n=2,
    )

    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase4_hotspot_ledger.py",
            "--output-root",
            str(tmp_path),
            "--region",
            "amazon",
            "--percentage-key",
            "canonical",
            "--classification-key",
            "canonical",
            "--trend-dataset-id",
            "gwd30",
            "--trend-dataset-id",
            "wad2m",
            "--no-skip",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    combined_output = completed.stderr + completed.stdout
    assert "classification_hotspot_manifest" in combined_output
    assert "metric_family=classification" in combined_output
    assert "status=missing" in combined_output
    assert "run_phase4_scaleout_readiness.py" in combined_output
    ledger_path = unified_hotspot_ledger_output_path(
        contract,
        ledger_key="canonical",
        region_id="amazon",
    )
    assert not ledger_path.exists()

    readiness_csv = scaleout_readiness_csv_output_path(
        tmp_path,
        requested_region_ids=["amazon"],
        percentage_key="canonical",
        classification_key="canonical",
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )
    readiness_json = scaleout_readiness_json_output_path(
        tmp_path,
        requested_region_ids=["amazon"],
        percentage_key="canonical",
        classification_key="canonical",
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )
    assert readiness_csv.is_file()
    assert readiness_json.is_file()
