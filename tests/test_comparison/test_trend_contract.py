from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.evidence_contract import load_phase4_evidence_contract
from WA.comparison.trend_contract import (
    load_contract_trend_summary,
    load_contract_trend_surface,
    trend_summary_output_path,
    trend_surface_output_path,
    write_contract_trend_summary,
    write_contract_trend_surface,
)
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
