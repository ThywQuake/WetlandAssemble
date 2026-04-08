from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.evidence_contract import load_phase4_evidence_contract
from WA.comparison.percentage_backbone import (
    DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS,
    build_percentage_dataset_key,
    load_contract_percentage_summary,
    load_contract_percentage_surface,
    load_tropical_surface,
    resolve_contract_dataset_ids,
    write_contract_percentage_summary,
    write_contract_percentage_surface,
)


def _sample_surface(values: np.ndarray) -> xr.DataArray:
    return xr.DataArray(
        values.astype(np.float32),
        dims=("lat", "lon"),
        coords={"lat": [1.0, 0.0], "lon": [100.0, 101.0]},
        name="wetland_fraction",
    )


def _sample_summary_rows(dataset_id: str) -> list[dict[str, object]]:
    return [
        {
            "dataset_id": dataset_id,
            "region_id": "amazon",
            "series_type": "annual",
            "time": pd.Timestamp("2016-01-01"),
            "year": 2016,
            "month": None,
            "wetland_area_km2": 100.0,
            "valid_area_km2": 200.0,
            "wetland_percentage": 50.0,
            "observation_count": 12,
            "is_auxiliary_dataset": dataset_id == "berkeley_rwawc",
        },
        {
            "dataset_id": dataset_id,
            "region_id": "amazon",
            "series_type": "climatology",
            "time": pd.Timestamp("2000-01-01"),
            "year": None,
            "month": 1,
            "wetland_area_km2": 90.0,
            "valid_area_km2": 180.0,
            "wetland_percentage": 50.0,
            "observation_count": 3,
            "is_auxiliary_dataset": dataset_id == "berkeley_rwawc",
        },
    ]


def test_resolve_contract_dataset_ids_restores_order_and_dataset_key() -> None:
    dataset_ids = resolve_contract_dataset_ids(["wad2m", "gwd30", "swamps"])

    assert dataset_ids == ("gwd30", "swamps", "wad2m")
    assert build_percentage_dataset_key(dataset_ids) == "gwd30+swamps+wad2m"
    assert build_percentage_dataset_key(DEFAULT_PERCENTAGE_CONTRACT_DATASET_IDS) == "canonical"


def test_write_and_reload_contract_percentage_surface_and_summary(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    dataset_ids = ("gwd30", "wad2m")
    surface_bundle = write_contract_percentage_surface(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        dataset_key="canonical",
        dataset_ids=dataset_ids,
        bbox=(99.5, -0.5, 101.5, 1.5),
        surface_year=2016,
        resolution_deg=0.25,
        actual_years={"gwd30": 2016, "wad2m": 2016},
        surfaces={
            "gwd30": _sample_surface(np.array([[0.2, 0.8], [0.4, 0.6]])),
            "wad2m": _sample_surface(np.array([[0.4, 0.6], [0.2, 0.8]])),
        },
    )
    summary_bundle = write_contract_percentage_summary(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        dataset_key="canonical",
        dataset_ids=dataset_ids,
        table=pd.DataFrame(_sample_summary_rows("gwd30") + _sample_summary_rows("wad2m")),
        time_range=("2016-01-01", "2016-12-31"),
    )

    reloaded_surface = load_contract_percentage_surface(
        contract=contract,
        region_id="amazon",
        dataset_key="canonical",
        expected_dataset_ids=dataset_ids,
    )
    reloaded_summary = load_contract_percentage_summary(
        contract=contract,
        region_id="amazon",
        dataset_key="canonical",
        expected_dataset_ids=dataset_ids,
    )

    assert surface_bundle.surface_path == reloaded_surface.surface_path
    assert reloaded_surface.dataset_ids == dataset_ids
    assert np.allclose(
        reloaded_surface.dataset["mean_wetland_percentage"].values,
        np.array([[30.0, 70.0], [30.0, 70.0]], dtype=np.float32),
    )
    assert json.loads(reloaded_surface.contract_metadata_json)["dataset_key"] == "canonical"

    assert summary_bundle.summary_path == reloaded_summary.summary_path
    assert reloaded_summary.dataset_ids == dataset_ids
    assert set(reloaded_summary.table["dataset_id"]) == {"gwd30", "wad2m"}
    assert set(reloaded_summary.table["dataset_key"]) == {"canonical"}


def test_load_tropical_surface_gwd30_missing_manifest_has_stage_context(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="stage=percentage-surface"):
        load_tropical_surface(
            "gwd30",
            region_id="amazon",
            bbox=(99.5, -0.5, 101.5, 1.5),
            target_year=2016,
            resolution_deg=1.0,
            cache_dir=tmp_path / "cache",
            output_root=tmp_path / "results",
            show_progress=False,
        )
