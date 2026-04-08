from __future__ import annotations

import hashlib
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

from WA.comparison.classification_contract import (
    CLASSIFICATION_CONTRACT_DATASET_KEY,
    write_contract_classification_hotspot_outputs,
    write_contract_classification_summary,
    write_contract_classification_surface,
)
from WA.comparison.evidence_contract import load_phase4_evidence_contract, metadata_json
from WA.comparison.hotspot_ledger import (
    hotspot_family_manifest_output_path,
    hotspot_family_table_output_path,
    write_unified_hotspot_ledger,
)
from WA.comparison.trend_agreement import TrendAgreementResult
from WA.comparison.trend_hotspots import write_trend_hotspot_outputs
from WA.visualization.phase4 import (
    load_phase4_contract_classification_hotspot_table,
    load_phase4_contract_classification_summary,
    load_phase4_contract_trend_hotspot_table,
    load_phase4_unified_hotspot_ledger,
    plot_phase4_climatology,
    plot_phase4_interannual,
)

matplotlib.use("Agg")


def _sample_phase4_table() -> pd.DataFrame:
    annual_rows = [
        {
            "dataset_id": "gwd30",
            "region_id": "amazon",
            "series_type": "annual",
            "time": pd.Timestamp("2019-01-01"),
            "year": 2019,
            "month": None,
            "wetland_area_km2": 100.0,
            "valid_area_km2": 200.0,
            "wetland_percentage": 50.0,
            "observation_count": 12,
            "is_auxiliary_dataset": False,
        },
        {
            "dataset_id": "berkeley_rwawc",
            "region_id": "amazon",
            "series_type": "annual",
            "time": pd.Timestamp("2019-01-01"),
            "year": 2019,
            "month": None,
            "wetland_area_km2": 20.0,
            "valid_area_km2": 100.0,
            "wetland_percentage": 20.0,
            "observation_count": 12,
            "is_auxiliary_dataset": True,
        },
    ]
    climatology_rows = [
        {
            "dataset_id": "gwd30",
            "region_id": "amazon",
            "series_type": "climatology",
            "time": pd.Timestamp("2000-01-01"),
            "year": None,
            "month": 1,
            "wetland_area_km2": 90.0,
            "valid_area_km2": 180.0,
            "wetland_percentage": 50.0,
            "observation_count": 3,
            "is_auxiliary_dataset": False,
        },
        {
            "dataset_id": "berkeley_rwawc",
            "region_id": "amazon",
            "series_type": "climatology",
            "time": pd.Timestamp("2000-01-01"),
            "year": None,
            "month": 1,
            "wetland_area_km2": 25.0,
            "valid_area_km2": 100.0,
            "wetland_percentage": 25.0,
            "observation_count": 3,
            "is_auxiliary_dataset": True,
        },
    ]
    return pd.DataFrame(annual_rows + climatology_rows)


def _make_agreement_result() -> TrendAgreementResult:
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
        participant_ids=["wad2m", "gwd30"],
        agreement_ratio=agreement_ratio,
        mean_slope=mean_slope,
        slope_std=slope_std,
        robust_increase=false_mask,
        robust_decrease=false_mask,
        robust_stable=false_mask,
        disputed=disputed,
        regional_summary=pd.DataFrame(
            {
                "region": ["amazon", "global"],
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


def _write_dummy_agreement_inputs(contract) -> tuple[Path, Path]:
    participant_set_key = "gwd30+wad2m"
    surface_path = contract.artifact_output_path(
        kind="trend_agreement_surface",
        dataset_or_key=participant_set_key,
        region_id="amazon",
    )
    summary_path = contract.artifact_output_path(
        kind="trend_agreement_summary",
        dataset_or_key=participant_set_key,
        region_id="amazon",
    )
    surface_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    surface_path.write_text("agreement-surface", encoding="utf-8")
    summary_path.write_text("agreement,summary\n", encoding="utf-8")
    return (surface_path, summary_path)


def _sample_phase36_metrics() -> xr.Dataset:
    coords = {"lat": [1.0, 0.0], "lon": [100.0, 101.0]}
    return xr.Dataset(
        {
            "entropy": xr.DataArray(
                np.array([[0.9, 0.7], [0.6, np.nan]], dtype=np.float32),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "majority_class": xr.DataArray(
                np.array([[1, 2], [3, -1]], dtype=np.int16),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "agreement_count": xr.DataArray(
                np.array([[1, 2], [3, -1]], dtype=np.int16),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "joint_valid_mask": xr.DataArray(
                np.array([[1, 1], [1, 0]], dtype=np.int8),
                dims=("lat", "lon"),
                coords=coords,
            ),
        }
    )


def _sample_phase36_dominant() -> xr.Dataset:
    coords = {"lat": [1.0, 0.0], "lon": [100.0, 101.0]}
    values = np.array([[1, 2], [3, -1]], dtype=np.int16)
    return xr.Dataset(
        {
            name: xr.DataArray(values, dims=("lat", "lon"), coords=coords)
            for name in (
                "g2017_dominant_class",
                "glwd_v2_dominant_class",
                "gwd30_dominant_class",
                "g2017_source_dominant_class",
                "glwd_v2_source_dominant_class",
                "gwd30_source_dominant_class",
            )
        }
    )


def _write_classification_contract_inputs(contract) -> None:
    phase36_dir = contract.output_root / "phase36_sources"
    phase36_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = phase36_dir / "phase3_6_entropy_global_500m_2016.nc"
    dominant_path = phase36_dir / "phase3_6_unified_classes_global_500m_2016.nc"
    _sample_phase36_metrics().to_netcdf(metrics_path)
    _sample_phase36_dominant().to_netcdf(dominant_path)

    phase37_dir = contract.output_root / "phase37_sources"
    phase37_dir.mkdir(parents=True, exist_ok=True)
    source_manifest_path = phase37_dir / "phase3_7_hotspots_2016.json"
    source_hotspot_path = phase37_dir / "phase3_7_hotspots_2016.csv"
    source_region_path = phase37_dir / "phase3_7_hotspot_regions_2016.csv"

    hotspot_row = {
        "hotspot_id": "entropy-amazon-001",
        "region_id": "amazon",
        "region_slug": "amazon",
        "region_label": "Amazon",
        "bbox": [99.75, 0.75, 100.25, 1.25],
        "center_lon": 100.0,
        "center_lat": 1.0,
        "mean_entropy": 0.9,
        "max_entropy": 0.9,
        "cell_count": 1,
        "region_rank": 1,
        "threshold_percentile": 95.0,
        "threshold_value": 0.8,
        "selection_rules_version": "phase3.7-hotspots-v1",
        "source": "entropy",
    }
    pd.DataFrame([hotspot_row]).to_csv(source_hotspot_path, index=False)
    pd.DataFrame(
        [
            {
                "region_id": "amazon",
                "region_label": "Amazon",
                "bbox": json.dumps([99.5, -0.5, 101.5, 1.5]),
                "priority": 1,
                "area_weight": 1.0,
                "quota": 2,
                "selected_count": 1,
                "shortfall": 1,
                "threshold_percentile": 95.0,
                "threshold_value": 0.8,
                "valid_wetland_cell_count": 3,
                "candidate_window_count": 3,
                "coarse_candidate_count": 2,
                "refined_candidate_count": 1,
                "status": "shortfall",
                "debug_png_path": "debug/amazon.png",
            }
        ]
    ).to_csv(source_region_path, index=False)
    source_manifest_path.write_text(
        json.dumps(
            {
                "phase": "phase3.7",
                "year": 2016,
                "selection_rules_version": "phase3.7-hotspots-v1",
                "metrics_path": str(metrics_path.resolve()),
                "classes_path": str(dominant_path.resolve()),
                "candidate_cache_path": str((phase37_dir / "cache.nc").resolve()),
                "regions_file": str((contract.output_root / "priority_regions.yaml").resolve()),
                "total_hotspot_budget": 2,
                "hotspot_count": 1,
                "unfilled_budget": 1,
                "threshold_percentile": 95.0,
                "min_cluster_cells": 1,
                "aoi_size_deg": 0.5,
                "min_distance_deg": 0.5,
                "candidate_sample_step": 4,
                "status_counts": {"shortfall": 1},
                "region_summaries": [
                    {
                        "region_id": "amazon",
                        "region_label": "Amazon",
                        "bbox": [99.5, -0.5, 101.5, 1.5],
                        "priority": 1,
                        "area_weight": 1.0,
                        "quota": 2,
                        "selected_count": 1,
                        "shortfall": 1,
                        "threshold_percentile": 95.0,
                        "threshold_value": 0.8,
                        "valid_wetland_cell_count": 3,
                        "candidate_window_count": 3,
                        "coarse_candidate_count": 2,
                        "refined_candidate_count": 1,
                        "status": "shortfall",
                        "debug_png_path": "debug/amazon.png",
                    }
                ],
                "hotspots": [hotspot_row],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    write_contract_classification_surface(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        bbox=(99.5, -0.5, 101.5, 1.5),
        target_year=2016,
        metrics_path=metrics_path,
        dominant_classes_path=dominant_path,
    )
    write_contract_classification_summary(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        target_year=2016,
        source_region_summary_path=source_region_path,
    )
    write_contract_classification_hotspot_outputs(
        contract=contract,
        region_id="amazon",
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        source_manifest_path=source_manifest_path,
        source_hotspot_table_path=source_hotspot_path,
        source_region_summary_path=source_region_path,
    )


def _write_generic_hotspot_family(
    contract,
    *,
    metric_family: str,
    region_id: str,
    dataset_key: str,
    rows: list[dict[str, Any]],
) -> None:
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
        score_name = "wetland_percentage"
    else:
        surface_kind = "classification_surface"
        summary_kind = "classification_regional_summary"
        artifact_kind = "classification_hotspot_manifest"
        score_name = "mean_entropy"

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
        "table_sha256": hashlib.sha256(table_text.encode("utf-8")).hexdigest(),
        "contract_metadata_json": metadata_json(
            {
                "artifact_kind": artifact_kind,
                "dataset_key": dataset_key,
                "region_id": region_id,
                "surface_output_path": str(surface_path.resolve()),
                "summary_output_path": str(summary_path.resolve()),
                "primary_score_name": score_name,
            }
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_unified_ledger_sources(contract) -> None:
    _write_generic_hotspot_family(
        contract,
        metric_family="percentage",
        region_id="amazon",
        dataset_key="canonical",
        rows=[
            {
                "hotspot_id": "pct-amazon-001",
                "hotspot_rank": 1,
                "region_id": "amazon",
                "dataset_key": "canonical",
                "center_lat": 0.8,
                "center_lon": 100.2,
                "bbox": [99.9, 0.5, 100.5, 1.1],
                "wetland_percentage": 81.5,
            }
        ],
    )
    _write_generic_hotspot_family(
        contract,
        metric_family="classification",
        region_id="amazon",
        dataset_key="canonical",
        rows=[
            {
                "hotspot_id": "cls-amazon-001",
                "hotspot_rank": 1,
                "region_id": "amazon",
                "dataset_key": "canonical",
                "center_lat": 0.9,
                "center_lon": 100.1,
                "bbox": [99.8, 0.6, 100.4, 1.2],
                "mean_entropy": 0.91,
                "max_entropy": 0.97,
            }
        ],
    )
    surface_path, summary_path = _write_dummy_agreement_inputs(contract)
    write_trend_hotspot_outputs(
        contract=contract,
        agreement_result=_make_agreement_result(),
        region_id="amazon",
        participant_ids=["wad2m", "gwd30"],
        surface_output_path=surface_path,
        summary_output_path=summary_path,
        top_n=2,
    )


def test_plot_phase4_interannual_writes_png(tmp_path: Path) -> None:
    output_path = tmp_path / "interannual.png"

    result = plot_phase4_interannual(
        _sample_phase4_table(),
        region_label="Amazon",
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.is_file()
    assert output_path.stat().st_size > 0


def test_plot_phase4_climatology_writes_png(tmp_path: Path) -> None:
    output_path = tmp_path / "climatology.png"

    result = plot_phase4_climatology(
        _sample_phase4_table(),
        region_label="Amazon",
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.is_file()
    assert output_path.stat().st_size > 0


def test_load_phase4_contract_trend_hotspot_table_reloads_semantically(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    surface_path, summary_path = _write_dummy_agreement_inputs(contract)
    write_trend_hotspot_outputs(
        contract=contract,
        agreement_result=_make_agreement_result(),
        region_id="amazon",
        participant_ids=["wad2m", "gwd30"],
        surface_output_path=surface_path,
        summary_output_path=summary_path,
        top_n=2,
    )

    bundle = load_phase4_contract_trend_hotspot_table(
        region_id="amazon",
        participant_ids=["wad2m", "gwd30"],
        output_root=tmp_path,
    )

    assert bundle.manifest.participant_set_key == "gwd30+wad2m"
    assert bundle.table["hotspot_rank"].tolist() == [1, 2]
    assert bundle.table["participant_ids"].tolist() == [
        ("gwd30", "wad2m"),
        ("gwd30", "wad2m"),
    ]


def test_load_phase4_contract_trend_hotspot_table_wraps_reload_errors(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="Phase4 semantic reload failed"):
        load_phase4_contract_trend_hotspot_table(
            region_id="amazon",
            participant_ids=["wad2m", "gwd30"],
            output_root=tmp_path,
        )


def test_load_phase4_contract_classification_summary_reloads_semantically(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_classification_contract_inputs(contract)

    bundle = load_phase4_contract_classification_summary(
        region_id="amazon",
        dataset_key="canonical",
        output_root=tmp_path,
    )

    assert bundle.dataset_key == "canonical"
    assert bundle.participant_set_key == "g2017+glwd_v2+gwd30"
    assert bundle.table["hotspot_shortfall"].tolist() == [1]


def test_load_phase4_contract_classification_hotspot_table_reloads_semantically(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_classification_contract_inputs(contract)

    bundle = load_phase4_contract_classification_hotspot_table(
        region_id="amazon",
        dataset_key="canonical",
        output_root=tmp_path,
    )

    assert bundle.manifest.participant_set_key == "g2017+glwd_v2+gwd30"
    assert bundle.table["hotspot_rank"].tolist() == [1]
    assert bundle.table["participant_ids"].tolist() == [
        ("g2017", "glwd_v2", "gwd30")
    ]


def test_load_phase4_contract_classification_hotspot_table_wraps_reload_errors(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="Phase4 semantic reload failed"):
        load_phase4_contract_classification_hotspot_table(
            region_id="amazon",
            dataset_key="canonical",
            output_root=tmp_path,
        )


def test_load_phase4_unified_hotspot_ledger_reloads_semantically(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_unified_ledger_sources(contract)
    write_unified_hotspot_ledger(
        contract=contract,
        region_id="amazon",
        ledger_key="canonical",
        percentage_key="canonical",
        classification_key="canonical",
        trend_participant_ids=["wad2m", "gwd30"],
    )

    bundle = load_phase4_unified_hotspot_ledger(
        region_id="amazon",
        ledger_key="canonical",
        output_root=tmp_path,
    )

    assert bundle.ledger_key == "canonical"
    assert set(bundle.table["metric_family"]) == {"percentage", "classification", "trend"}
    assert bundle.table["analysis_object_id"].is_unique
    assert bundle.table["line_specific"].iloc[0]["dataset_key"] == "canonical"


def test_load_phase4_unified_hotspot_ledger_wraps_reload_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Phase4 semantic reload failed"):
        load_phase4_unified_hotspot_ledger(
            region_id="amazon",
            ledger_key="canonical",
            output_root=tmp_path,
        )


def test_run_phase4_trend_contract_help_mentions_trend_hotspots() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/run_phase4_trend_contract.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "trend-hotspots" in completed.stdout
    assert "--top-hotspots" in completed.stdout
    assert "--skip" in completed.stdout
    assert "--no-skip" in completed.stdout


def test_run_phase4_classification_contract_help_mentions_subset_and_skip() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/run_phase4_classification_contract.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "--subset" in completed.stdout
    assert "canonical" in completed.stdout
    assert "ten" in completed.stdout
    assert "--no-skip" in completed.stdout
