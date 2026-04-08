from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.classification_contract import (
    CLASSIFICATION_CONTRACT_DATASET_KEY,
    CLASSIFICATION_PARTICIPANT_IDS,
    CLASSIFICATION_PARTICIPANT_SET_KEY,
    classification_hotspot_manifest_output_path,
    classification_hotspot_table_output_path,
    load_contract_classification_hotspot_table,
    load_contract_classification_summary,
    load_contract_classification_surface,
    phase37_source_paths,
    write_contract_classification_hotspot_outputs,
    write_contract_classification_summary,
    write_contract_classification_surface,
)
from WA.comparison.evidence_contract import load_phase4_evidence_contract


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
    variables = {}
    values = np.array([[1, 2], [3, -1]], dtype=np.int16)
    for dataset_id in CLASSIFICATION_PARTICIPANT_IDS:
        variables[f"{dataset_id}_dominant_class"] = xr.DataArray(
            values,
            dims=("lat", "lon"),
            coords=coords,
        )
        variables[f"{dataset_id}_source_dominant_class"] = xr.DataArray(
            values,
            dims=("lat", "lon"),
            coords=coords,
        )
    return xr.Dataset(variables)


def _write_phase36_sources(tmp_path: Path) -> tuple[Path, Path]:
    source_dir = tmp_path / "phase3_6"
    source_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = source_dir / "phase3_6_entropy_global_500m_2016.nc"
    dominant_path = source_dir / "phase3_6_unified_classes_global_500m_2016.nc"
    _sample_phase36_metrics().to_netcdf(metrics_path)
    _sample_phase36_dominant().to_netcdf(dominant_path)
    return (metrics_path, dominant_path)


def _phase37_hotspot_row(region_id: str = "amazon") -> dict[str, object]:
    return {
        "hotspot_id": f"entropy-{region_id}-001",
        "region_id": region_id,
        "region_slug": region_id,
        "region_label": region_id.title(),
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


def _phase37_region_row(region_id: str = "amazon") -> dict[str, object]:
    return {
        "region_id": region_id,
        "region_label": region_id.title(),
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


def _write_phase37_source_trio(
    tmp_path: Path,
    *,
    metrics_path: Path,
    dominant_path: Path,
    region_id: str = "amazon",
) -> tuple[Path, Path, Path]:
    paths = phase37_source_paths(output_dir=tmp_path / "phase3_7", year=2016)
    paths.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    hotspot_row = _phase37_hotspot_row(region_id=region_id)
    region_row = _phase37_region_row(region_id=region_id)

    pd.DataFrame([hotspot_row]).to_csv(paths.hotspot_csv_path, index=False)
    pd.DataFrame([region_row]).to_csv(paths.region_csv_path, index=False)
    payload = {
        "phase": "phase3.7",
        "year": 2016,
        "selection_rules_version": "phase3.7-hotspots-v1",
        "metrics_path": str(metrics_path.resolve()),
        "classes_path": str(dominant_path.resolve()),
        "candidate_cache_path": str((tmp_path / "phase3_7" / "cache.nc").resolve()),
        "regions_file": str((tmp_path / "priority_regions.yaml").resolve()),
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
                "region_label": region_id.title(),
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
    }
    paths.manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return (paths.manifest_path, paths.hotspot_csv_path, paths.region_csv_path)


def test_write_and_reload_classification_contract_family_round_trip(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path / "phase4")
    metrics_path, dominant_path = _write_phase36_sources(tmp_path)
    source_manifest_path, source_hotspot_path, source_region_path = _write_phase37_source_trio(
        tmp_path,
        metrics_path=metrics_path,
        dominant_path=dominant_path,
    )

    surface_bundle = write_contract_classification_surface(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        bbox=(99.5, -0.5, 101.5, 1.5),
        target_year=2016,
        metrics_path=metrics_path,
        dominant_classes_path=dominant_path,
    )
    summary_bundle = write_contract_classification_summary(
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

    reloaded_surface = load_contract_classification_surface(
        contract=contract,
        region_id="amazon",
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
    )
    reloaded_summary = load_contract_classification_summary(
        contract=contract,
        region_id="amazon",
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
    )
    reloaded_hotspots = load_contract_classification_hotspot_table(
        contract=contract,
        region_id="amazon",
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
    )

    assert surface_bundle.surface_path == reloaded_surface.surface_path
    assert summary_bundle.summary_path == reloaded_summary.summary_path
    assert reloaded_surface.participant_set_key == CLASSIFICATION_PARTICIPANT_SET_KEY
    assert reloaded_surface.dataset_key == CLASSIFICATION_CONTRACT_DATASET_KEY
    assert reloaded_surface.dataset["entropy"].shape == (2, 2)
    assert reloaded_surface.dataset.coords["lat"].values.tolist() == [1.0, 0.0]
    assert reloaded_summary.table["hotspot_shortfall"].tolist() == [1]
    assert reloaded_summary.table["mean_entropy"].tolist() == pytest.approx([0.7333333333])
    assert reloaded_hotspots.manifest.dataset_key == CLASSIFICATION_CONTRACT_DATASET_KEY
    assert reloaded_hotspots.table["source_hotspot_id"].tolist() == ["entropy-amazon-001"]
    assert reloaded_hotspots.table["participant_ids"].tolist() == [
        CLASSIFICATION_PARTICIPANT_IDS
    ]
    assert reloaded_hotspots.table["bbox"].tolist() == [
        (99.75, 0.75, 100.25, 1.25)
    ]
    assert classification_hotspot_manifest_output_path(
        contract,
        region_id="amazon",
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
    ).is_file()
    assert classification_hotspot_table_output_path(
        contract,
        region_id="amazon",
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
    ).is_file()


def test_write_contract_classification_surface_rejects_missing_source_dominant_vars(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path / "phase4")
    metrics_path, dominant_path = _write_phase36_sources(tmp_path)

    dominant = xr.load_dataset(dominant_path)
    broken = dominant.drop_vars("gwd30_source_dominant_class")
    broken.to_netcdf(dominant_path, mode="w")

    with pytest.raises(ValueError, match="gwd30_source_dominant_class"):
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


def test_write_contract_classification_hotspots_rejects_mixed_region_source_rows(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path / "phase4")
    metrics_path, dominant_path = _write_phase36_sources(tmp_path)
    source_manifest_path, source_hotspot_path, source_region_path = _write_phase37_source_trio(
        tmp_path,
        metrics_path=metrics_path,
        dominant_path=dominant_path,
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

    hotspot_table = pd.read_csv(source_hotspot_path)
    hotspot_table.loc[0, "region_id"] = "congo"
    hotspot_table.to_csv(source_hotspot_path, index=False)

    with pytest.raises(ValueError, match="mixed-region"):
        write_contract_classification_hotspot_outputs(
            contract=contract,
            region_id="amazon",
            dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
            source_manifest_path=source_manifest_path,
            source_hotspot_table_path=source_hotspot_path,
            source_region_summary_path=source_region_path,
        )


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
