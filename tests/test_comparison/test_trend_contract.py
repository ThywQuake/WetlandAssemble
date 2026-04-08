from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.evidence_contract import load_phase4_evidence_contract, metadata_json
from WA.comparison.trend_contract import (
    load_contract_trend_agreement_artifacts,
    load_contract_trend_summary,
    load_contract_trend_surface,
    trend_agreement_summary_output_path,
    trend_agreement_surface_output_path,
    trend_summary_output_path,
    trend_surface_output_path,
    write_contract_trend_summary,
    write_contract_trend_surface,
)
from WA.comparison.trend_hotspots import build_participant_set_key, normalize_participant_ids
from WA.comparison.trends import TrendResult


def _make_trend_result(dataset_id: str = "wad2m") -> TrendResult:
    coords = {"lat": [1.0, 0.0], "lon": [100.0, 101.0]}
    sens_slope = xr.DataArray(
        np.array([[0.01, 0.02], [0.03, 0.04]], dtype=np.float32),
        dims=("lat", "lon"),
        coords=coords,
    )
    return TrendResult(
        dataset_id=dataset_id,
        aggregation="annual",
        time_range=("2000-01-01", "2004-12-01"),
        observation_count=5,
        sens_slope=sens_slope,
        p_value=xr.full_like(sens_slope, 0.01, dtype=np.float32),
        z_score=xr.full_like(sens_slope, 2.5, dtype=np.float32),
        significant=xr.full_like(sens_slope, True, dtype=bool),
        trend_direction=xr.full_like(sens_slope, 1, dtype=np.int8),
        status="computed",
    )


def _write_contract_trend_agreement_pair(
    contract,
    *,
    region_id: str = "amazon",
    participant_ids: tuple[str, ...] = ("wad2m", "gwd30"),
    overlap_window: tuple[str, str] = ("2001-01-01", "2010-12-31"),
) -> tuple[Path, Path]:
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
    contract_metadata_json = metadata_json(
        {
            "artifact_kind": "trend_agreement_surface",
            "region_id": region_id,
            "participant_ids": list(normalized_participant_ids),
            "participant_set_key": participant_set_key,
            "surface_relpath": str(surface_path.relative_to(contract.output_root)),
            "summary_relpath": str(summary_path.relative_to(contract.output_root)),
        }
    )
    coords = {"lat": [1.0, 0.0], "lon": [100.0, 101.0]}
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
                np.array([[0.2, 0.4], [0.1, 0.1]], dtype=np.float32),
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
            "region_id": region_id,
            "participant_ids_json": json.dumps(
                list(normalized_participant_ids),
                separators=(",", ":"),
            ),
            "participant_set_key": participant_set_key,
            "overlap_window_start": overlap_window[0],
            "overlap_window_end": overlap_window[1],
            "status": "computed",
            "contract_metadata_json": contract_metadata_json,
        }
    )
    summary = pd.DataFrame(
        {
            "region": [region_id, "global"],
            "total_valid_pixels": [2, 2],
            "mean_agreement_ratio": [0.625, 0.625],
            "fraction_robust_increase": [0.5, 0.5],
            "fraction_robust_decrease": [0.0, 0.0],
            "fraction_robust_stable": [0.0, 0.0],
            "fraction_disputed": [0.5, 0.5],
            "mean_slope_across_datasets": [0.02, 0.02],
            "region_id": [region_id, region_id],
            "participant_set_key": [participant_set_key, participant_set_key],
            "participant_ids_json": [
                json.dumps(list(normalized_participant_ids), separators=(",", ":")),
                json.dumps(list(normalized_participant_ids), separators=(",", ":")),
            ],
            "overlap_window_start": [overlap_window[0], overlap_window[0]],
            "overlap_window_end": [overlap_window[1], overlap_window[1]],
            "contract_metadata_json": [contract_metadata_json, contract_metadata_json],
        }
    )
    surface_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_netcdf(surface_path)
    summary.to_csv(summary_path, index=False)
    return surface_path, summary_path


def test_write_and_reload_contract_trend_surface_and_summary(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    trend_result = _make_trend_result()

    surface_bundle = write_contract_trend_surface(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        bbox=(99.5, -0.5, 101.5, 1.5),
        trend_result=trend_result,
    )
    summary_bundle = write_contract_trend_summary(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        bbox=(99.5, -0.5, 101.5, 1.5),
        trend_result=trend_result,
        surface_output_path=surface_bundle.surface_path,
    )

    reloaded_surface = load_contract_trend_surface(
        contract=contract,
        region_id="amazon",
        dataset_id="wad2m",
        expected_aggregation="annual",
        expected_time_range=("2000-01-01", "2004-12-01"),
    )
    reloaded_summary = load_contract_trend_summary(
        contract=contract,
        region_id="amazon",
        dataset_id="wad2m",
        expected_aggregation="annual",
        expected_time_range=("2000-01-01", "2004-12-01"),
    )

    assert surface_bundle.surface_path == reloaded_surface.surface_path
    assert summary_bundle.summary_path == reloaded_summary.summary_path
    assert reloaded_surface.dataset_id == "wad2m"
    assert set(reloaded_surface.dataset.data_vars) == {
        "sens_slope",
        "p_value",
        "z_score",
        "significant",
        "trend_direction",
    }
    assert reloaded_summary.table["region_id"].tolist() == ["amazon"]
    assert reloaded_summary.table["dataset_id"].tolist() == ["wad2m"]
    assert reloaded_summary.table["total_valid_pixels"].tolist() == [4]
    assert reloaded_summary.table["mean_slope"].tolist() == pytest.approx([0.025])
    assert trend_surface_output_path(
        contract,
        region_id="amazon",
        dataset_id="wad2m",
    ).is_file()
    assert trend_summary_output_path(
        contract,
        region_id="amazon",
        dataset_id="wad2m",
    ).is_file()


def test_load_contract_trend_summary_rejects_mixed_dataset_id(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    trend_result = _make_trend_result()
    write_contract_trend_surface(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        bbox=(99.5, -0.5, 101.5, 1.5),
        trend_result=trend_result,
    )
    write_contract_trend_summary(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        bbox=(99.5, -0.5, 101.5, 1.5),
        trend_result=trend_result,
    )

    summary_path = trend_summary_output_path(
        contract,
        region_id="amazon",
        dataset_id="wad2m",
    )
    table = pd.read_csv(summary_path)
    table.loc[0, "dataset_id"] = "swamps"
    table.to_csv(summary_path, index=False)

    with pytest.raises(ValueError, match="mixed dataset_id values"):
        load_contract_trend_summary(
            contract=contract,
            region_id="amazon",
            dataset_id="wad2m",
        )


def test_load_contract_trend_agreement_artifacts_reloads_semantically(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_contract_trend_agreement_pair(contract)

    bundle = load_contract_trend_agreement_artifacts(
        contract=contract,
        region_id="amazon",
        participant_ids=("wad2m", "gwd30"),
        expected_overlap_window=("2001-01-01", "2010-12-31"),
    )

    assert bundle.surface.participant_set_key == "gwd30+wad2m"
    assert bundle.summary.participant_set_key == "gwd30+wad2m"
    assert bundle.result.participant_ids == ["gwd30", "wad2m"]
    assert bundle.result.overlap_window == ("2001-01-01", "2010-12-31")
    assert bundle.summary.table["region"].tolist() == ["amazon", "global"]
    assert bundle.surface.surface_path.is_file()
    assert bundle.summary.summary_path.is_file()


def test_load_contract_trend_agreement_artifacts_rejects_partial_pairs(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    surface_path, _summary_path = _write_contract_trend_agreement_pair(contract)
    trend_agreement_summary_output_path(
        contract,
        region_id="amazon",
        participant_ids=("wad2m", "gwd30"),
    ).unlink()

    with pytest.raises(
        FileNotFoundError,
        match=(
            "stage=agreement region_id=amazon family_key=gwd30\\+wad2m "
            "found partial artifact pair"
        ),
    ):
        load_contract_trend_agreement_artifacts(
            contract=contract,
            region_id="amazon",
            participant_ids=("wad2m", "gwd30"),
        )

    assert surface_path.is_file()


def test_load_contract_trend_agreement_artifacts_rejects_mixed_participant_ids(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_contract_trend_agreement_pair(contract)
    summary_path = trend_agreement_summary_output_path(
        contract,
        region_id="amazon",
        participant_ids=("wad2m", "gwd30"),
    )
    summary = pd.read_csv(summary_path)
    summary.loc[0, "participant_ids_json"] = json.dumps(["gwd30", "swamps"])
    summary.to_csv(summary_path, index=False)

    with pytest.raises(
        ValueError,
        match=(
            "stage=agreement region_id=amazon participant_set_key=gwd30\\+wad2m "
            "summary contains mixed participant ids"
        ),
    ):
        load_contract_trend_agreement_artifacts(
            contract=contract,
            region_id="amazon",
            participant_ids=("wad2m", "gwd30"),
        )


def test_load_contract_trend_agreement_artifacts_rejects_malformed_contract_metadata(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    surface_path, _summary_path = _write_contract_trend_agreement_pair(contract)
    dataset = xr.load_dataset(surface_path)
    dataset.attrs["contract_metadata_json"] = "{"
    dataset.to_netcdf(surface_path, mode="w")

    with pytest.raises(
        ValueError,
        match=(
            "stage=agreement region_id=amazon participant_set_key=gwd30\\+wad2m "
            "malformed contract_metadata_json"
        ),
    ):
        load_contract_trend_agreement_artifacts(
            contract=contract,
            region_id="amazon",
            participant_ids=("wad2m", "gwd30"),
        )


def test_run_phase4_trend_contract_rejects_duplicate_participant_ids() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase4_trend_contract.py",
            "--dataset-id",
            "gwd30",
            "--dataset-id",
            "gwd30",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "participant_ids must not contain duplicates" in (
        completed.stderr + completed.stdout
    )
