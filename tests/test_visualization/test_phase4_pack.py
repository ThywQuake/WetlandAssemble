from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
import pytest
import xarray as xr

matplotlib.use("Agg")

from tests.test_comparison.test_scaleout_readiness import (
    _write_classification_family as _write_readiness_classification_family,
)
from WA.comparison.classification_contract import (  # noqa: E402
    CLASSIFICATION_PARTICIPANT_IDS,
    CLASSIFICATION_PARTICIPANT_SET_KEY,
    CLASSIFICATION_SUMMARY_COLUMNS,
    classification_summary_output_path,
)
from WA.comparison.evidence_contract import load_phase4_evidence_contract, metadata_json
from WA.comparison.hotspot_ledger import unified_hotspot_ledger_output_path
from WA.comparison.percentage_backbone import (  # noqa: E402
    DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS,
    build_percentage_dataset_key,
    write_contract_percentage_summary,
    write_contract_percentage_surface,
)
from WA.comparison.percentage_hotspots import write_percentage_hotspot_outputs
from WA.comparison.scaleout_readiness import DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS
from WA.comparison.trend_agreement import TrendAgreementResult
from WA.comparison.trend_contract import (  # noqa: E402
    trend_agreement_summary_output_path,
    trend_agreement_surface_output_path,
)
from WA.comparison.trend_hotspots import (
    build_participant_set_key,
    normalize_participant_ids,
    write_trend_hotspot_outputs,
)
from WA.visualization.phase4_pack import (  # noqa: E402
    build_phase4_evidence_pack,
    build_phase4_evidence_pack_proof,
    phase4_pack_joined_regional_evidence_output_path,
    phase4_pack_manifest_output_path,
    phase4_pack_proof_json_output_path,
    phase4_pack_proof_markdown_output_path,
    phase4_pack_unified_hotspot_table_output_path,
)

TREND_PARTICIPANT_IDS = normalize_participant_ids(DEFAULT_SCALEOUT_TREND_PARTICIPANT_IDS)
TREND_PARTICIPANT_SET_KEY = build_participant_set_key(TREND_PARTICIPANT_IDS)
PERCENTAGE_DATASET_KEY = build_percentage_dataset_key(DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS)


def _surface_coords_for_bbox(bbox: tuple[float, float, float, float]) -> dict[str, list[float]]:
    west, south, east, north = bbox
    lat_step = max((north - south) / 4.0, 0.1)
    lon_step = max((east - west) / 4.0, 0.1)
    return {
        "lat": [north - lat_step, south + lat_step],
        "lon": [west + lon_step, east - lon_step],
    }


def _write_percentage_contract_inputs(
    contract,
    *,
    region,
    omit_climatology: bool = False,
) -> None:
    coords = _surface_coords_for_bbox(region.bbox)
    surfaces = {
        dataset_id: xr.DataArray(
            np.full((2, 2), 0.1 + (index * 0.02), dtype=np.float32),
            dims=("lat", "lon"),
            coords=coords,
        )
        for index, dataset_id in enumerate(DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS)
    }
    actual_years = dict.fromkeys(DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS, 2016)
    write_contract_percentage_surface(
        contract=contract,
        region_id=region.region_id,
        region_label=region.label,
        dataset_key=PERCENTAGE_DATASET_KEY,
        dataset_ids=DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS,
        bbox=region.bbox,
        surface_year=2016,
        resolution_deg=0.25,
        actual_years=actual_years,
        surfaces=surfaces,
    )

    rows: list[dict[str, Any]] = []
    for dataset_index, dataset_id in enumerate(DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS):
        base = 20.0 + dataset_index
        for year in (2015, 2016):
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "region_id": region.region_id,
                    "series_type": "annual",
                    "time": pd.Timestamp(f"{year}-01-01"),
                    "year": year,
                    "month": None,
                    "wetland_area_km2": 100.0 + dataset_index,
                    "valid_area_km2": 200.0,
                    "wetland_percentage": base + (year - 2015),
                    "observation_count": 12,
                    "is_auxiliary_dataset": dataset_id == "berkeley_rwawc",
                }
            )
        if not omit_climatology:
            for month in range(1, 13):
                rows.append(
                    {
                        "dataset_id": dataset_id,
                        "region_id": region.region_id,
                        "series_type": "climatology",
                        "time": pd.Timestamp(f"2000-{month:02d}-01"),
                        "year": None,
                        "month": month,
                        "wetland_area_km2": 80.0 + dataset_index,
                        "valid_area_km2": 190.0,
                        "wetland_percentage": base + (month / 10.0),
                        "observation_count": 6,
                        "is_auxiliary_dataset": dataset_id == "berkeley_rwawc",
                    }
                )
    write_contract_percentage_summary(
        contract=contract,
        region_id=region.region_id,
        region_label=region.label,
        dataset_key=PERCENTAGE_DATASET_KEY,
        dataset_ids=DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS,
        table=pd.DataFrame(rows),
        time_range=("2015-01-01", "2016-12-31"),
    )


def _write_classification_summary(contract, *, region, order: int) -> None:
    summary_path = classification_summary_output_path(
        contract,
        region_id=region.region_id,
        dataset_key="canonical",
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    contract_metadata_json = metadata_json(
        {
            "artifact_kind": "classification_regional_summary",
            "dataset_key": "canonical",
            "participant_ids": list(CLASSIFICATION_PARTICIPANT_IDS),
            "participant_set_key": CLASSIFICATION_PARTICIPANT_SET_KEY,
            "region_id": region.region_id,
            "region_label": region.label,
            "target_year": 2016,
            "bbox": list(region.bbox),
        }
    )
    row = {
        "region_id": region.region_id,
        "region_label": region.label,
        "dataset_key": "canonical",
        "participant_set_key": CLASSIFICATION_PARTICIPANT_SET_KEY,
        "participant_ids_json": json.dumps(
            list(CLASSIFICATION_PARTICIPANT_IDS),
            separators=(",", ":"),
        ),
        "target_year": 2016,
        "joint_valid_cell_count": 100 + order,
        "mean_entropy": 0.40 + (order / 100.0),
        "max_entropy": 0.90 + (order / 1000.0),
        "mean_agreement_count": 2.10,
        "agreement_count_1": 10,
        "agreement_count_2": 20,
        "agreement_count_3": 70,
        "hotspot_selected_count": 5,
        "hotspot_quota": 6,
        "hotspot_shortfall": 1,
        "hotspot_threshold_percentile": 95.0,
        "hotspot_threshold_value": 0.8,
        "hotspot_status": "shortfall",
        "contract_metadata_json": contract_metadata_json,
    }
    pd.DataFrame([row]).loc[:, list(CLASSIFICATION_SUMMARY_COLUMNS)].to_csv(
        summary_path,
        index=False,
    )


def _write_trend_agreement_inputs(contract, *, region, order: int) -> None:
    surface_path = trend_agreement_surface_output_path(
        contract,
        region_id=region.region_id,
        participant_ids=TREND_PARTICIPANT_IDS,
    )
    summary_path = trend_agreement_summary_output_path(
        contract,
        region_id=region.region_id,
        participant_ids=TREND_PARTICIPANT_IDS,
    )
    surface_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    contract_metadata_json = metadata_json(
        {
            "artifact_kind": "trend_agreement_surface",
            "region_id": region.region_id,
            "participant_ids": list(TREND_PARTICIPANT_IDS),
            "participant_set_key": TREND_PARTICIPANT_SET_KEY,
            "surface_relpath": str(surface_path.relative_to(contract.output_root)),
            "summary_relpath": str(summary_path.relative_to(contract.output_root)),
        }
    )
    coords = _surface_coords_for_bbox(region.bbox)
    dataset = xr.Dataset(
        {
            "agreement_ratio": xr.DataArray(
                np.array([[0.5, 0.75], [1.0, 1.0]], dtype=np.float32),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "mean_slope": xr.DataArray(
                np.array([[0.01, 0.02], [0.03, 0.04]], dtype=np.float32),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "slope_std": xr.DataArray(
                np.array([[0.2, 0.3], [0.1, 0.1]], dtype=np.float32),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "robust_increase": xr.DataArray(
                np.array([[False, False], [True, True]], dtype=bool),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "robust_decrease": xr.DataArray(
                np.array([[False, False], [False, False]], dtype=bool),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "robust_stable": xr.DataArray(
                np.array([[False, False], [False, False]], dtype=bool),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "disputed": xr.DataArray(
                np.array([[True, True], [False, False]], dtype=bool),
                dims=("lat", "lon"),
                coords=coords,
            ),
        }
    )
    dataset.attrs.update(
        {
            "region_id": region.region_id,
            "participant_ids_json": json.dumps(
                list(TREND_PARTICIPANT_IDS),
                separators=(",", ":"),
            ),
            "participant_set_key": TREND_PARTICIPANT_SET_KEY,
            "overlap_window_start": "2001-01-01",
            "overlap_window_end": "2010-12-31",
            "status": "computed",
            "contract_metadata_json": contract_metadata_json,
        }
    )
    dataset.to_netcdf(surface_path)
    summary = pd.DataFrame(
        {
            "region": [region.region_id, "global"],
            "total_valid_pixels": [10 + order, 10 + order],
            "mean_agreement_ratio": [0.60 + (order / 1000.0), 0.60 + (order / 1000.0)],
            "fraction_robust_increase": [0.2, 0.2],
            "fraction_robust_decrease": [0.1, 0.1],
            "fraction_robust_stable": [0.2, 0.2],
            "fraction_disputed": [0.5, 0.5],
            "mean_slope_across_datasets": [0.02, 0.02],
            "region_id": [region.region_id, region.region_id],
            "participant_set_key": [TREND_PARTICIPANT_SET_KEY, TREND_PARTICIPANT_SET_KEY],
            "participant_ids_json": [
                json.dumps(list(TREND_PARTICIPANT_IDS), separators=(",", ":")),
                json.dumps(list(TREND_PARTICIPANT_IDS), separators=(",", ":")),
            ],
            "overlap_window_start": ["2001-01-01", "2001-01-01"],
            "overlap_window_end": ["2010-12-31", "2010-12-31"],
            "contract_metadata_json": [contract_metadata_json, contract_metadata_json],
        }
    )
    summary.to_csv(summary_path, index=False)


def _write_unified_ledger(
    contract,
    *,
    region,
    order: int,
    malformed_json: bool = False,
    trend_family_key_override: str | None = None,
) -> None:
    ledger_path = unified_hotspot_ledger_output_path(
        contract,
        ledger_key="canonical",
        region_id=region.region_id,
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    percentage_surface_path = contract.artifact_output_path(
        kind="surface",
        dataset_or_key="canonical",
        region_id=region.region_id,
    )
    percentage_summary_path = contract.artifact_output_path(
        kind="regional_summary",
        dataset_or_key="canonical",
        region_id=region.region_id,
    )
    classification_summary_path = classification_summary_output_path(
        contract,
        region_id=region.region_id,
        dataset_key="canonical",
    )
    trend_surface_path = trend_agreement_surface_output_path(
        contract,
        region_id=region.region_id,
        participant_ids=TREND_PARTICIPANT_IDS,
    )
    trend_summary_path = trend_agreement_summary_output_path(
        contract,
        region_id=region.region_id,
        participant_ids=TREND_PARTICIPANT_IDS,
    )
    trend_family_key = trend_family_key_override or TREND_PARTICIPANT_SET_KEY
    rows = [
        {
            "analysis_object_id": f"{region.region_id}::percentage::pct-{order:03d}",
            "ledger_key": "canonical",
            "region_id": region.region_id,
            "metric_family": "percentage",
            "artifact_kind": "hotspot_manifest",
            "family_key": "canonical",
            "hotspot_id": f"pct-{region.region_id}-001",
            "hotspot_rank": 1,
            "family_percentile": 1.0,
            "primary_score_name": "wetland_percentage",
            "primary_score_value": 80.0 + order,
            "center_lat": float((region.bbox[1] + region.bbox[3]) / 2.0),
            "center_lon": float((region.bbox[0] + region.bbox[2]) / 2.0),
            "bbox": json.dumps(list(region.bbox), separators=(",", ":")),
            "manifest_path": str(
                contract.artifact_output_path(
                    kind="hotspot_manifest",
                    dataset_or_key="canonical",
                    region_id=region.region_id,
                ).resolve()
            ),
            "table_path": str(
                contract.artifact_output_path(
                    kind="hotspot_manifest",
                    dataset_or_key="canonical",
                    region_id=region.region_id,
                    extension=".csv",
                ).resolve()
            ),
            "surface_output_path": str(percentage_surface_path.resolve()),
            "summary_output_path": str(percentage_summary_path.resolve()),
            "manifest_relpath": str(
                contract.artifact_output_path(
                    kind="hotspot_manifest",
                    dataset_or_key="canonical",
                    region_id=region.region_id,
                ).resolve().relative_to(contract.output_root.resolve())
            ),
            "table_relpath": str(
                contract.artifact_output_path(
                    kind="hotspot_manifest",
                    dataset_or_key="canonical",
                    region_id=region.region_id,
                    extension=".csv",
                ).resolve().relative_to(contract.output_root.resolve())
            ),
            "surface_output_relpath": str(
                percentage_surface_path.resolve().relative_to(contract.output_root.resolve())
            ),
            "summary_output_relpath": str(
                percentage_summary_path.resolve().relative_to(contract.output_root.resolve())
            ),
            "contract_metadata_json": "{" if malformed_json else metadata_json(
                {
                    "metric_family": "percentage",
                    "family_key": "canonical",
                    "region_id": region.region_id,
                }
            ),
            "line_specific_json": metadata_json({"dataset_key": "canonical"}),
        },
        {
            "analysis_object_id": f"{region.region_id}::classification::cls-{order:03d}",
            "ledger_key": "canonical",
            "region_id": region.region_id,
            "metric_family": "classification",
            "artifact_kind": "classification_hotspot_manifest",
            "family_key": "canonical",
            "hotspot_id": f"cls-{region.region_id}-001",
            "hotspot_rank": 1,
            "family_percentile": 1.0,
            "primary_score_name": "mean_entropy",
            "primary_score_value": 0.91,
            "center_lat": float((region.bbox[1] + region.bbox[3]) / 2.0),
            "center_lon": float((region.bbox[0] + region.bbox[2]) / 2.0),
            "bbox": json.dumps(list(region.bbox), separators=(",", ":")),
            "manifest_path": str(
                contract.artifact_output_path(
                    kind="classification_hotspot_manifest",
                    dataset_or_key="canonical",
                    region_id=region.region_id,
                ).resolve()
            ),
            "table_path": str(
                contract.artifact_output_path(
                    kind="classification_hotspot_manifest",
                    dataset_or_key="canonical",
                    region_id=region.region_id,
                    extension=".csv",
                ).resolve()
            ),
            "surface_output_path": str(
                contract.artifact_output_path(
                    kind="classification_surface",
                    dataset_or_key="canonical",
                    region_id=region.region_id,
                ).resolve()
            ),
            "summary_output_path": str(classification_summary_path.resolve()),
            "manifest_relpath": str(
                contract.artifact_output_path(
                    kind="classification_hotspot_manifest",
                    dataset_or_key="canonical",
                    region_id=region.region_id,
                ).resolve().relative_to(contract.output_root.resolve())
            ),
            "table_relpath": str(
                contract.artifact_output_path(
                    kind="classification_hotspot_manifest",
                    dataset_or_key="canonical",
                    region_id=region.region_id,
                    extension=".csv",
                ).resolve().relative_to(contract.output_root.resolve())
            ),
            "surface_output_relpath": str(
                contract.artifact_output_path(
                    kind="classification_surface",
                    dataset_or_key="canonical",
                    region_id=region.region_id,
                ).resolve().relative_to(contract.output_root.resolve())
            ),
            "summary_output_relpath": str(
                classification_summary_path.resolve().relative_to(contract.output_root.resolve())
            ),
            "contract_metadata_json": metadata_json(
                {
                    "metric_family": "classification",
                    "family_key": "canonical",
                    "region_id": region.region_id,
                }
            ),
            "line_specific_json": metadata_json({"dataset_key": "canonical"}),
        },
        {
            "analysis_object_id": f"{region.region_id}::trend::trd-{order:03d}",
            "ledger_key": "canonical",
            "region_id": region.region_id,
            "metric_family": "trend",
            "artifact_kind": "trend_hotspot_manifest",
            "family_key": trend_family_key,
            "hotspot_id": f"trd-{region.region_id}-001",
            "hotspot_rank": 1,
            "family_percentile": 1.0,
            "primary_score_name": "disagreement_score",
            "primary_score_value": 0.50,
            "center_lat": float((region.bbox[1] + region.bbox[3]) / 2.0),
            "center_lon": float((region.bbox[0] + region.bbox[2]) / 2.0),
            "bbox": json.dumps(list(region.bbox), separators=(",", ":")),
            "manifest_path": str(
                contract.artifact_output_path(
                    kind="trend_hotspot_manifest",
                    dataset_or_key=TREND_PARTICIPANT_SET_KEY,
                    region_id=region.region_id,
                ).resolve()
            ),
            "table_path": str(
                contract.artifact_output_path(
                    kind="trend_hotspot_manifest",
                    dataset_or_key=TREND_PARTICIPANT_SET_KEY,
                    region_id=region.region_id,
                    extension=".csv",
                ).resolve()
            ),
            "surface_output_path": str(trend_surface_path.resolve()),
            "summary_output_path": str(trend_summary_path.resolve()),
            "manifest_relpath": str(
                contract.artifact_output_path(
                    kind="trend_hotspot_manifest",
                    dataset_or_key=TREND_PARTICIPANT_SET_KEY,
                    region_id=region.region_id,
                ).resolve().relative_to(contract.output_root.resolve())
            ),
            "table_relpath": str(
                contract.artifact_output_path(
                    kind="trend_hotspot_manifest",
                    dataset_or_key=TREND_PARTICIPANT_SET_KEY,
                    region_id=region.region_id,
                    extension=".csv",
                ).resolve().relative_to(contract.output_root.resolve())
            ),
            "surface_output_relpath": str(
                trend_surface_path.resolve().relative_to(contract.output_root.resolve())
            ),
            "summary_output_relpath": str(
                trend_summary_path.resolve().relative_to(contract.output_root.resolve())
            ),
            "contract_metadata_json": metadata_json(
                {
                    "metric_family": "trend",
                    "family_key": trend_family_key,
                    "region_id": region.region_id,
                }
            ),
            "line_specific_json": metadata_json(
                {"participant_set_key": trend_family_key}
            ),
        },
    ]
    pd.DataFrame(rows).to_csv(ledger_path, index=False)


def _write_pack_fixture(
    contract,
    *,
    region_ids: list[str],
    omit_climatology: bool = False,
    malformed_ledger_json: bool = False,
    omit_ledger: bool = False,
    trend_family_key_override: str | None = None,
) -> None:
    regions = contract.resolve_regions(requested_region_ids=region_ids)
    for order, region in enumerate(regions, start=1):
        _write_percentage_contract_inputs(
            contract,
            region=region,
            omit_climatology=omit_climatology,
        )
        _write_classification_summary(contract, region=region, order=order)
        _write_trend_agreement_inputs(contract, region=region, order=order)
        _write_unified_ledger(
            contract,
            region=region,
            order=order,
            malformed_json=malformed_ledger_json,
            trend_family_key_override=trend_family_key_override,
        )
        if omit_ledger:
            unified_hotspot_ledger_output_path(
                contract,
                ledger_key="canonical",
                region_id=region.region_id,
            ).unlink()


def _make_trend_agreement_result_for_pack(region) -> TrendAgreementResult:
    coords = _surface_coords_for_bbox(region.bbox)
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
        participant_ids=TREND_PARTICIPANT_IDS,
        agreement_ratio=agreement_ratio,
        mean_slope=mean_slope,
        slope_std=slope_std,
        robust_increase=false_mask,
        robust_decrease=false_mask,
        robust_stable=false_mask,
        disputed=disputed,
        regional_summary=pd.DataFrame(
            {
                "region": [region.region_id, "global"],
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


def _write_strict_proof_ready_inputs(contract, *, region_id: str) -> None:
    region = contract.regions_by_id[region_id]
    write_percentage_hotspot_outputs(
        contract=contract,
        region_id=region_id,
        dataset_key="canonical",
        top_n=1,
        min_distance_deg=0.0,
    )
    _write_readiness_classification_family(contract, region_id)
    write_trend_hotspot_outputs(
        contract=contract,
        agreement_result=_make_trend_agreement_result_for_pack(region),
        region_id=region_id,
        participant_ids=TREND_PARTICIPANT_IDS,
        surface_output_path=trend_agreement_surface_output_path(
            contract,
            region_id=region_id,
            participant_ids=TREND_PARTICIPANT_IDS,
        ),
        summary_output_path=trend_agreement_summary_output_path(
            contract,
            region_id=region_id,
            participant_ids=TREND_PARTICIPANT_IDS,
        ),
        top_n=1,
    )


def _phase4_files(root: Path) -> set[str]:
    return {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file()
    }


def test_build_phase4_evidence_pack_writes_outputs_and_keeps_phase4_inputs_unchanged(
    tmp_path: Path,
) -> None:
    phase4_root = tmp_path / "phase4"
    pack_root = tmp_path / "pack"
    contract = load_phase4_evidence_contract(output_root=phase4_root)
    _write_pack_fixture(contract, region_ids=["amazon"])
    before_files = _phase4_files(phase4_root)

    result = build_phase4_evidence_pack(
        phase4_output_root=phase4_root,
        pack_output_root=pack_root,
        requested_region_ids=["amazon"],
        percentage_key="canonical",
        classification_key="canonical",
        ledger_key="canonical",
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )

    assert result.resolved_region_ids == ("amazon",)
    assert result.manifest_path == phase4_pack_manifest_output_path(pack_root).resolve()
    assert (
        result.joined_regional_evidence_path
        == phase4_pack_joined_regional_evidence_output_path(pack_root).resolve()
    )
    assert (
        result.unified_hotspot_table_path
        == phase4_pack_unified_hotspot_table_output_path(pack_root).resolve()
    )
    assert result.summary_path.is_file()
    assert result.manifest_path.is_file()
    assert result.joined_regional_evidence_path.is_file()
    assert result.unified_hotspot_table_path.is_file()
    assert _phase4_files(phase4_root) == before_files

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["resolved_region_ids"] == ["amazon"]
    assert manifest["percentage_key"] == "canonical"
    assert manifest["trend_participant_set_key"] == TREND_PARTICIPANT_SET_KEY
    assert (
        manifest["outputs"]["joined_regional_evidence_table"]["relpath"]
        == "tables/joined_regional_evidence.csv"
    )
    assert manifest["outputs"]["summary"]["relpath"] == "summary.md"
    assert (
        manifest["outputs"]["figures"][0]["interannual_figure_relpath"]
        == "figures/interannual/amazon.png"
    )
    assert (
        manifest["outputs"]["figures"][0]["climatology_figure_relpath"]
        == "figures/climatology/amazon.png"
    )
    assert manifest["sources"][0]["percentage_summary_path"] == str(
        contract.artifact_output_path(
            kind="regional_summary",
            dataset_or_key="canonical",
            region_id="amazon",
        ).resolve()
    )

    joined = pd.read_csv(result.joined_regional_evidence_path)
    expected_columns = {
        "pack_region_order",
        "region_id",
        "region_label",
        "percentage_key",
        "classification_key",
        "ledger_key",
        "classification_mean_entropy",
        "trend_mean_agreement_ratio",
        "ledger_row_count",
        "percentage_summary_path",
        "trend_agreement_surface_path",
        "unified_hotspot_ledger_path",
        "percentage_annual_mean__gwd30",
        "percentage_climatology_peak__berkeley_rwawc",
    }
    assert expected_columns.issubset(set(joined.columns))
    assert joined["region_id"].tolist() == ["amazon"]
    assert joined["pack_region_order"].tolist() == [1]


def test_build_phase4_evidence_pack_ten_subset_keeps_order_and_relpaths(tmp_path: Path) -> None:
    phase4_root = tmp_path / "phase4"
    pack_root = tmp_path / "pack"
    contract = load_phase4_evidence_contract(output_root=phase4_root)
    region_ids = contract.resolve_region_ids(subset="ten")
    _write_pack_fixture(contract, region_ids=region_ids)

    result = build_phase4_evidence_pack(
        phase4_output_root=phase4_root,
        pack_output_root=pack_root,
        subset="ten",
        percentage_key="canonical",
        classification_key="canonical",
        ledger_key="canonical",
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )

    joined = pd.read_csv(result.joined_regional_evidence_path)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert list(result.resolved_region_ids) == region_ids
    assert joined["region_id"].tolist() == region_ids
    assert joined["pack_region_order"].tolist() == list(range(1, len(region_ids) + 1))
    assert manifest["resolved_region_ids"] == region_ids
    assert len(manifest["outputs"]["figures"]) == len(region_ids)
    assert (
        manifest["outputs"]["figures"][0]["interannual_figure_relpath"]
        == f"figures/interannual/{region_ids[0]}.png"
    )
    assert (
        manifest["outputs"]["figures"][-1]["climatology_figure_relpath"]
        == f"figures/climatology/{region_ids[-1]}.png"
    )


def test_build_phase4_evidence_pack_rejects_empty_region_selection(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="At least one region id is required"):
        build_phase4_evidence_pack(
            phase4_output_root=tmp_path / "phase4",
            pack_output_root=tmp_path / "pack",
            requested_region_ids=[],
        )


@pytest.mark.parametrize(
    ("pack_root_factory", "expected_error"),
    [
        (
            lambda phase4_root, tmp_path: phase4_root / "derived",
            "must sit outside the phase4 science contract tree",
        ),
        (
            lambda phase4_root, tmp_path: tmp_path / "pack-file",
            "pack_output_root is not a directory",
        ),
    ],
)
def test_build_phase4_evidence_pack_rejects_invalid_pack_roots(
    tmp_path: Path,
    pack_root_factory,
    expected_error: str,
) -> None:
    phase4_root = tmp_path / "phase4"
    pack_root = pack_root_factory(phase4_root, tmp_path)
    if pack_root.name == "pack-file":
        pack_root.write_text("not-a-directory", encoding="utf-8")

    with pytest.raises((ValueError, NotADirectoryError), match=expected_error):
        build_phase4_evidence_pack(
            phase4_output_root=phase4_root,
            pack_output_root=pack_root,
            requested_region_ids=["amazon"],
        )


def test_build_phase4_evidence_pack_rejects_missing_climatology_rows(tmp_path: Path) -> None:
    phase4_root = tmp_path / "phase4"
    pack_root = tmp_path / "pack"
    contract = load_phase4_evidence_contract(output_root=phase4_root)
    _write_pack_fixture(contract, region_ids=["amazon"], omit_climatology=True)

    with pytest.raises(ValueError, match="missing climatology rows"):
        build_phase4_evidence_pack(
            phase4_output_root=phase4_root,
            pack_output_root=pack_root,
            requested_region_ids=["amazon"],
            trend_participant_ids=TREND_PARTICIPANT_IDS,
        )

    assert not phase4_pack_manifest_output_path(pack_root).exists()


def test_build_phase4_evidence_pack_rejects_malformed_ledger_json(tmp_path: Path) -> None:
    phase4_root = tmp_path / "phase4"
    pack_root = tmp_path / "pack"
    contract = load_phase4_evidence_contract(output_root=phase4_root)
    _write_pack_fixture(contract, region_ids=["amazon"], malformed_ledger_json=True)

    with pytest.raises(ValueError, match="family=unified-hotspot-ledger"):
        build_phase4_evidence_pack(
            phase4_output_root=phase4_root,
            pack_output_root=pack_root,
            requested_region_ids=["amazon"],
            trend_participant_ids=TREND_PARTICIPANT_IDS,
        )

    assert not phase4_pack_manifest_output_path(pack_root).exists()


def test_build_phase4_evidence_pack_proof_writes_complete_artifacts(tmp_path: Path) -> None:
    phase4_root = tmp_path / "phase4"
    pack_root = tmp_path / "pack"
    contract = load_phase4_evidence_contract(output_root=phase4_root)
    _write_pack_fixture(contract, region_ids=["amazon"])
    _write_strict_proof_ready_inputs(contract, region_id="amazon")

    proof = build_phase4_evidence_pack_proof(
        phase4_output_root=phase4_root,
        pack_output_root=pack_root,
        requested_region_ids=["amazon"],
        percentage_key="canonical",
        classification_key="canonical",
        ledger_key="canonical",
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )

    assert proof.proof_verdict == "complete"
    assert proof.pack_result is not None
    assert proof.proof_json_path == phase4_pack_proof_json_output_path(pack_root).resolve()
    assert proof.proof_markdown_path == phase4_pack_proof_markdown_output_path(pack_root).resolve()

    payload = json.loads(proof.proof_json_path.read_text(encoding="utf-8"))
    assert payload["proof_verdict"] == "complete"
    assert payload["complete_pack_claim_allowed"] is True
    assert payload["readiness_report"]["ready_region_ids"] == ["amazon"]
    assert payload["pack_outputs"]["manifest_exists"] is True
    assert payload["pack_outputs"]["output_counts"]["figure_count"] == 2
    assert payload["regions"][0]["ledger"]["trend_family_keys"] == [
        TREND_PARTICIPANT_SET_KEY
    ]
    assert payload["pack_outputs"]["manifest_path"] == str(
        phase4_pack_manifest_output_path(pack_root).resolve()
    )

    markdown = proof.proof_markdown_path.read_text(encoding="utf-8")
    assert "Phase 4 Complete-Pack Proof" in markdown
    assert "amazon" in markdown
    assert "complete_pack_claim_allowed" in markdown


def test_build_phase4_evidence_pack_proof_reports_incomplete_readiness_and_ledger(
    tmp_path: Path,
) -> None:
    phase4_root = tmp_path / "phase4"
    pack_root = tmp_path / "pack"
    contract = load_phase4_evidence_contract(output_root=phase4_root)
    region = contract.regions_by_id["amazon"]
    _write_percentage_contract_inputs(contract, region=region)

    proof = build_phase4_evidence_pack_proof(
        phase4_output_root=phase4_root,
        pack_output_root=pack_root,
        requested_region_ids=["amazon"],
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )

    assert proof.proof_verdict == "incomplete"
    assert proof.pack_result is None
    assert not phase4_pack_manifest_output_path(pack_root).exists()
    assert proof.proof_json_path.is_file()
    assert proof.proof_markdown_path.is_file()

    payload = json.loads(proof.proof_json_path.read_text(encoding="utf-8"))
    assert payload["complete_pack_claim_allowed"] is False
    assert payload["pack_outputs"]["manifest_exists"] is False
    assert any(
        "metric_family=classification" in reason for reason in payload["blocking_reasons"]
    )
    assert any(
        "metric_family=unified-hotspot-ledger" in reason
        for reason in payload["blocking_reasons"]
    )
    assert payload["regions"][0]["readiness"]["rows"][1]["status"] == "missing"
    assert payload["regions"][0]["ledger"]["ledger_exists"] is False


def test_build_phase4_evidence_pack_proof_rejects_ledger_participant_mismatch(
    tmp_path: Path,
) -> None:
    phase4_root = tmp_path / "phase4"
    pack_root = tmp_path / "pack"
    contract = load_phase4_evidence_contract(output_root=phase4_root)
    _write_pack_fixture(
        contract,
        region_ids=["amazon"],
        trend_family_key_override="gwd30+wad2m",
    )
    _write_strict_proof_ready_inputs(contract, region_id="amazon")

    proof = build_phase4_evidence_pack_proof(
        phase4_output_root=phase4_root,
        pack_output_root=pack_root,
        requested_region_ids=["amazon"],
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )

    assert proof.proof_verdict == "incomplete"
    assert proof.pack_result is None
    assert any(
        "proof_stage=ledger-selector" in reason for reason in proof.blocking_reasons
    )

    payload = json.loads(proof.proof_json_path.read_text(encoding="utf-8"))
    assert payload["regions"][0]["ledger"]["trend_family_keys"] == ["gwd30+wad2m"]


def test_run_phase4_evidence_pack_help_mentions_subset_pack_root_and_strict() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/run_phase4_evidence_pack.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "--subset" in completed.stdout
    assert "ten" in completed.stdout
    assert "--pack-output-root" in completed.stdout
    assert "--phase4-output-root" in completed.stdout
    assert "--strict" in completed.stdout


def test_run_phase4_evidence_pack_cli_writes_incomplete_proof_without_strict(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    phase4_root = tmp_path / "phase4"
    pack_root = tmp_path / "pack"
    contract = load_phase4_evidence_contract(output_root=phase4_root)
    _write_pack_fixture(contract, region_ids=["amazon"], malformed_ledger_json=True)
    _write_strict_proof_ready_inputs(contract, region_id="amazon")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase4_evidence_pack.py",
            "--region",
            "amazon",
            "--phase4-output-root",
            str(phase4_root),
            "--pack-output-root",
            str(pack_root),
            "--ledger-key",
            "canonical",
            "--percentage-key",
            "canonical",
            "--classification-key",
            "canonical",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert not phase4_pack_manifest_output_path(pack_root).exists()
    assert phase4_pack_proof_json_output_path(pack_root).is_file()
    combined = completed.stdout + completed.stderr
    assert "stage=pack-proof action=incomplete" in combined
    assert "unified-hotspot-ledger" in combined


def test_run_phase4_evidence_pack_cli_strict_fails_on_incomplete_proof(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    phase4_root = tmp_path / "phase4"
    pack_root = tmp_path / "pack"
    contract = load_phase4_evidence_contract(output_root=phase4_root)
    _write_pack_fixture(contract, region_ids=["amazon"], malformed_ledger_json=True)
    _write_strict_proof_ready_inputs(contract, region_id="amazon")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase4_evidence_pack.py",
            "--region",
            "amazon",
            "--phase4-output-root",
            str(phase4_root),
            "--pack-output-root",
            str(pack_root),
            "--ledger-key",
            "canonical",
            "--percentage-key",
            "canonical",
            "--classification-key",
            "canonical",
            "--strict",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert not phase4_pack_manifest_output_path(pack_root).exists()
    assert phase4_pack_proof_markdown_output_path(pack_root).is_file()
    combined = completed.stdout + completed.stderr
    assert "stage=pack-proof action=incomplete" in combined
    assert "strict=True" in combined
