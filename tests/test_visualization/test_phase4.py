from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.evidence_contract import load_phase4_evidence_contract
from WA.comparison.trend_agreement import TrendAgreementResult
from WA.comparison.trend_hotspots import write_trend_hotspot_outputs
from WA.visualization.phase4 import (
    load_phase4_contract_trend_hotspot_table,
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
