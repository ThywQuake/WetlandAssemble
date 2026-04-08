from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from WA.comparison.classification_contract import (
    CLASSIFICATION_CONTRACT_DATASET_KEY,
    write_contract_classification_hotspot_outputs,
    write_contract_classification_summary,
    write_contract_classification_surface,
)
from WA.comparison.evidence_contract import load_phase4_evidence_contract
from WA.comparison.percentage_backbone import (
    write_contract_percentage_summary,
    write_contract_percentage_surface,
)
from WA.comparison.percentage_hotspots import write_percentage_hotspot_outputs
from WA.comparison.scaleout_readiness import (
    SCALEOUT_READYNESS_COLUMNS,
    inspect_scaleout_readiness,
    scaleout_readiness_csv_output_path,
    scaleout_readiness_json_output_path,
    write_scaleout_readiness_report,
)
from WA.comparison.trend_agreement import TrendAgreementResult
from WA.comparison.trend_hotspots import (
    build_participant_set_key,
    write_trend_hotspot_outputs,
)

PERCENTAGE_DATASET_IDS = ("gwd30", "wad2m")
TREND_PARTICIPANT_IDS = ("gwd30", "wad2m")


def _region_coords(bbox: tuple[float, float, float, float]) -> dict[str, list[float]]:
    west, south, east, north = bbox
    lat_span = max(north - south, 1.0)
    lon_span = max(east - west, 1.0)
    return {
        "lat": [north - (lat_span * 0.25), south + (lat_span * 0.25)],
        "lon": [west + (lon_span * 0.25), west + (lon_span * 0.75)],
    }


def _cell_bbox(
    bbox: tuple[float, float, float, float],
    *,
    center_lat: float,
    center_lon: float,
) -> list[float]:
    west, south, east, north = bbox
    lat_half = max((north - south) * 0.1, 0.1)
    lon_half = max((east - west) * 0.1, 0.1)
    return [
        max(west, center_lon - lon_half),
        max(south, center_lat - lat_half),
        min(east, center_lon + lon_half),
        min(north, center_lat + lat_half),
    ]


def _percentage_summary_table(region_id: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index, dataset_id in enumerate(PERCENTAGE_DATASET_IDS, start=1):
        rows.append(
            {
                "dataset_id": dataset_id,
                "region_id": region_id,
                "series_type": "annual",
                "time": pd.Timestamp("2016-01-01"),
                "year": 2016,
                "month": None,
                "wetland_area_km2": 80.0 + (10.0 * index),
                "valid_area_km2": 200.0,
                "wetland_percentage": 40.0 + (5.0 * index),
                "observation_count": 12,
                "is_auxiliary_dataset": False,
            }
        )
    return pd.DataFrame(rows)


def _write_percentage_family(contract, region_id: str) -> None:
    region = contract.regions_by_id[region_id]
    coords = _region_coords(region.bbox)
    surfaces = {
        "gwd30": xr.DataArray(
            np.array([[0.80, 0.60], [0.30, 0.10]], dtype=np.float32),
            dims=("lat", "lon"),
            coords=coords,
        ),
        "wad2m": xr.DataArray(
            np.array([[0.70, 0.50], [0.20, 0.15]], dtype=np.float32),
            dims=("lat", "lon"),
            coords=coords,
        ),
    }
    write_contract_percentage_surface(
        contract=contract,
        region_id=region_id,
        region_label=region.label,
        dataset_key="canonical",
        dataset_ids=PERCENTAGE_DATASET_IDS,
        bbox=region.bbox,
        surface_year=2016,
        resolution_deg=0.25,
        actual_years=dict.fromkeys(PERCENTAGE_DATASET_IDS, 2016),
        surfaces=surfaces,
    )
    write_contract_percentage_summary(
        contract=contract,
        region_id=region_id,
        region_label=region.label,
        dataset_key="canonical",
        dataset_ids=PERCENTAGE_DATASET_IDS,
        table=_percentage_summary_table(region_id),
        time_range=("2016-01-01", "2016-12-31"),
    )
    write_percentage_hotspot_outputs(
        contract=contract,
        region_id=region_id,
        dataset_key="canonical",
        top_n=1,
        min_distance_deg=0.0,
    )


def _sample_phase36_metrics(bbox: tuple[float, float, float, float]) -> xr.Dataset:
    coords = _region_coords(bbox)
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


def _sample_phase36_dominant(bbox: tuple[float, float, float, float]) -> xr.Dataset:
    coords = _region_coords(bbox)
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


def _write_classification_family(contract, region_id: str) -> None:
    region = contract.regions_by_id[region_id]
    phase36_dir = contract.output_root / "phase36_sources" / region_id
    phase36_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = phase36_dir / "phase3_6_entropy_global_500m_2016.nc"
    dominant_path = phase36_dir / "phase3_6_unified_classes_global_500m_2016.nc"
    _sample_phase36_metrics(region.bbox).to_netcdf(metrics_path)
    _sample_phase36_dominant(region.bbox).to_netcdf(dominant_path)

    coords = _region_coords(region.bbox)
    center_lat = float(coords["lat"][0])
    center_lon = float(coords["lon"][0])
    hotspot_bbox = _cell_bbox(region.bbox, center_lat=center_lat, center_lon=center_lon)

    phase37_dir = contract.output_root / "phase37_sources" / region_id
    phase37_dir.mkdir(parents=True, exist_ok=True)
    source_manifest_path = phase37_dir / "phase3_7_hotspots_2016.json"
    source_hotspot_path = phase37_dir / "phase3_7_hotspots_2016.csv"
    source_region_path = phase37_dir / "phase3_7_hotspot_regions_2016.csv"

    hotspot_row = {
        "hotspot_id": f"entropy-{region_id}-001",
        "region_id": region_id,
        "region_slug": region_id,
        "region_label": region.label,
        "bbox": hotspot_bbox,
        "center_lon": center_lon,
        "center_lat": center_lat,
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
                "region_id": region_id,
                "region_label": region.label,
                "bbox": json.dumps(list(region.bbox)),
                "priority": region.priority,
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
                "debug_png_path": f"debug/{region_id}.png",
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
                "regions_file": str(contract.regions_file.resolve()),
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
                        "region_id": region_id,
                        "region_label": region.label,
                        "bbox": list(region.bbox),
                        "priority": region.priority,
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
                        "debug_png_path": f"debug/{region_id}.png",
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
        region_id=region_id,
        region_label=region.label,
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        bbox=region.bbox,
        target_year=2016,
        metrics_path=metrics_path,
        dominant_classes_path=dominant_path,
    )
    write_contract_classification_summary(
        contract=contract,
        region_id=region_id,
        region_label=region.label,
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        target_year=2016,
        source_region_summary_path=source_region_path,
    )
    write_contract_classification_hotspot_outputs(
        contract=contract,
        region_id=region_id,
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        source_manifest_path=source_manifest_path,
        source_hotspot_table_path=source_hotspot_path,
        source_region_summary_path=source_region_path,
    )


def _make_agreement_result(bbox: tuple[float, float, float, float]) -> TrendAgreementResult:
    coords = _region_coords(bbox)
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
        participant_ids=list(TREND_PARTICIPANT_IDS),
        agreement_ratio=agreement_ratio,
        mean_slope=mean_slope,
        slope_std=slope_std,
        robust_increase=false_mask,
        robust_decrease=false_mask,
        robust_stable=false_mask,
        disputed=disputed,
        regional_summary=pd.DataFrame(
            {
                "region": ["placeholder", "global"],
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


def _write_trend_family(contract, region_id: str) -> None:
    participant_set_key = build_participant_set_key(TREND_PARTICIPANT_IDS)
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
    write_trend_hotspot_outputs(
        contract=contract,
        agreement_result=_make_agreement_result(contract.regions_by_id[region_id].bbox),
        region_id=region_id,
        participant_ids=TREND_PARTICIPANT_IDS,
        surface_output_path=surface_path,
        summary_output_path=summary_path,
        top_n=2,
    )


def _readiness_row(report, *, region_id: str, metric_family: str) -> pd.Series:
    rows = report.table.loc[
        (report.table["region_id"] == region_id)
        & (report.table["metric_family"] == metric_family)
    ]
    assert len(rows) == 1
    return rows.iloc[0]


def test_inspect_scaleout_readiness_reports_ready_missing_and_partial_statuses(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_percentage_family(contract, "amazon")
    _write_classification_family(contract, "amazon")
    _write_trend_family(contract, "amazon")
    _write_percentage_family(contract, "sudd")

    malformed_manifest = contract.artifact_output_path(
        kind="hotspot_manifest",
        dataset_or_key="canonical",
        region_id="sudd",
    )
    payload = json.loads(malformed_manifest.read_text(encoding="utf-8"))
    payload["contract_metadata_json"] = "{"
    malformed_manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = inspect_scaleout_readiness(
        contract=contract,
        requested_region_ids=["amazon", "pantanal", "sudd"],
        percentage_key="canonical",
        classification_key="canonical",
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )

    assert list(report.table.columns) == list(SCALEOUT_READYNESS_COLUMNS)
    assert report.ready_region_ids == ("amazon",)
    assert report.incomplete_region_ids == ("pantanal", "sudd")

    amazon_percentage = _readiness_row(report, region_id="amazon", metric_family="percentage")
    assert amazon_percentage["status"] == "ready"
    assert bool(amazon_percentage["region_ready"]) is True

    pantanal_classification = _readiness_row(
        report,
        region_id="pantanal",
        metric_family="classification",
    )
    assert pantanal_classification["status"] == "missing"
    assert "manifest/table pair" in pantanal_classification["reason"]
    assert bool(pantanal_classification["region_ready"]) is False

    sudd_percentage = _readiness_row(report, region_id="sudd", metric_family="percentage")
    assert sudd_percentage["status"] == "partial"
    assert "Malformed contract_metadata_json" in str(sudd_percentage["error_message"])
    assert sudd_percentage["manifest_path"].endswith(
        "hotspot_manifests/sudd/canonical__sudd__hotspot_manifest.json"
    )
    assert bool(sudd_percentage["region_ready"]) is False

    sudd_trend = _readiness_row(report, region_id="sudd", metric_family="trend")
    assert sudd_trend["status"] == "missing"


def test_inspect_scaleout_readiness_marks_partial_pairs_as_partial(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_trend_family(contract, "amazon")
    participant_set_key = build_participant_set_key(TREND_PARTICIPANT_IDS)
    trend_table_path = contract.artifact_output_path(
        kind="trend_hotspot_manifest",
        dataset_or_key=participant_set_key,
        region_id="amazon",
        extension=".csv",
    )
    trend_table_path.unlink()

    report = inspect_scaleout_readiness(
        contract=contract,
        requested_region_ids=["amazon"],
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )

    trend_row = _readiness_row(report, region_id="amazon", metric_family="trend")
    assert trend_row["status"] == "partial"
    assert "manifest_exists=True table_exists=False" in trend_row["reason"]


def test_write_scaleout_readiness_report_writes_csv_and_json_for_ten_subset(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)

    report = write_scaleout_readiness_report(
        contract=contract,
        subset="ten",
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )

    assert report.csv_path == scaleout_readiness_csv_output_path(
        tmp_path,
        subset="ten",
        percentage_key="canonical",
        classification_key="canonical",
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )
    assert report.json_path == scaleout_readiness_json_output_path(
        tmp_path,
        subset="ten",
        percentage_key="canonical",
        classification_key="canonical",
        trend_participant_ids=TREND_PARTICIPANT_IDS,
    )
    assert report.csv_path.is_file()
    assert report.json_path.is_file()

    csv_table = pd.read_csv(report.csv_path)
    payload = json.loads(report.json_path.read_text(encoding="utf-8"))

    assert len(csv_table) == len(contract.ordered_ten_region_ids) * 3
    assert set(csv_table["status"]) == {"missing"}
    assert payload["resolved_region_ids"] == list(contract.ordered_ten_region_ids)
    assert payload["ready_region_ids"] == []
    assert payload["rows"][0]["metric_family"] == "percentage"


def test_run_phase4_scaleout_readiness_help_mentions_statuses_and_subset() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/run_phase4_scaleout_readiness.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "ready/missing/partial" in completed.stdout
    assert "--subset" in completed.stdout
    assert "canonical" in completed.stdout
    assert "ten" in completed.stdout
