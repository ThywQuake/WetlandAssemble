from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.evidence_contract import load_phase4_evidence_contract
from WA.comparison.percentage_backbone import (
    write_contract_percentage_summary,
    write_contract_percentage_surface,
)
from WA.comparison.percentage_hotspots import (
    build_percentage_hotspot_table,
    load_contract_percentage_hotspot_table,
    percentage_hotspot_manifest_output_path,
    percentage_hotspot_table_output_path,
    write_percentage_hotspot_outputs,
)


def _sample_surface(values: np.ndarray) -> xr.DataArray:
    return xr.DataArray(
        values.astype(np.float32),
        dims=("lat", "lon"),
        coords={"lat": [1.0, 0.0], "lon": [100.0, 101.0]},
        name="wetland_fraction",
    )


def _write_contract_inputs(contract) -> None:
    write_contract_percentage_surface(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        dataset_key="canonical",
        dataset_ids=("gwd30", "wad2m"),
        bbox=(99.5, -0.5, 101.5, 1.5),
        surface_year=2016,
        resolution_deg=0.25,
        actual_years={"gwd30": 2016, "wad2m": 2016},
        surfaces={
            "gwd30": _sample_surface(np.array([[0.2, 0.8], [0.4, 0.6]])),
            "wad2m": _sample_surface(np.array([[0.4, 0.6], [0.2, 0.8]])),
        },
    )
    summary = pd.DataFrame(
        [
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
                "is_auxiliary_dataset": False,
            }
            for dataset_id in ("gwd30", "wad2m")
        ]
    )
    write_contract_percentage_summary(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        dataset_key="canonical",
        dataset_ids=("gwd30", "wad2m"),
        table=summary,
        time_range=("2016-01-01", "2016-12-31"),
    )


def _rewrite_table_and_manifest(manifest_path: Path, table_path: Path, table: pd.DataFrame) -> None:
    serializable = table.copy()
    serializable["bbox"] = serializable["bbox"].map(
        lambda value: value if isinstance(value, str) else json.dumps(list(value))
    )
    table_text = serializable.to_csv(index=False, lineterminator="\n")
    table_path.write_text(table_text, encoding="utf-8")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["hotspot_count"] = int(len(table))
    payload["table_sha256"] = hashlib.sha256(table_text.encode("utf-8")).hexdigest()
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_build_percentage_hotspot_table_ranks_mean_percentage_first(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_contract_inputs(contract)
    surface_bundle = write_contract_percentage_surface(
        contract=contract,
        region_id="amazon",
        region_label="Amazon",
        dataset_key="custom",
        dataset_ids=("gwd30",),
        bbox=(99.5, -0.5, 101.5, 1.5),
        surface_year=2016,
        resolution_deg=0.25,
        actual_years={"gwd30": 2016},
        surfaces={"gwd30": _sample_surface(np.array([[0.1, 0.9], [0.4, 0.6]]))},
    )

    table = build_percentage_hotspot_table(
        surface_bundle,
        top_n=3,
        min_distance_deg=0.0,
    )

    assert table["hotspot_rank"].tolist() == [1]
    assert table["wetland_percentage"].tolist() == pytest.approx([90.0])
    assert table["center_lon"].tolist() == [101.0]
    assert table["center_lat"].tolist() == pytest.approx([1.0])


def test_write_and_reload_percentage_hotspot_outputs_round_trip(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_contract_inputs(contract)

    manifest = write_percentage_hotspot_outputs(
        contract=contract,
        region_id="amazon",
        dataset_key="canonical",
        top_n=2,
        min_distance_deg=0.0,
    )
    bundle = load_contract_percentage_hotspot_table(
        contract=contract,
        region_id="amazon",
        dataset_key="canonical",
        expected_dataset_ids=("gwd30", "wad2m"),
    )

    assert manifest.dataset_key == "canonical"
    assert manifest.dataset_ids == ("gwd30", "wad2m")
    assert bundle.table["hotspot_id"].tolist() == [
        "pct-amazon-canonical-001",
        "pct-amazon-canonical-002",
    ]
    assert bundle.table["dataset_ids"].tolist() == [
        ("gwd30", "wad2m"),
        ("gwd30", "wad2m"),
    ]
    assert bundle.table["wetland_percentage"].tolist() == pytest.approx([70.0, 70.0])
    assert {tuple(value) for value in bundle.table["bbox"]} == {
        (100.5, -0.5, 101.5, 0.5),
        (100.5, 0.5, 101.5, 1.5),
    }


def test_load_contract_percentage_hotspot_table_rejects_malformed_bbox(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_contract_inputs(contract)
    write_percentage_hotspot_outputs(
        contract=contract,
        region_id="amazon",
        dataset_key="canonical",
        top_n=2,
        min_distance_deg=0.0,
    )

    manifest_path = percentage_hotspot_manifest_output_path(
        contract,
        region_id="amazon",
        dataset_key="canonical",
    )
    table_path = percentage_hotspot_table_output_path(
        contract,
        region_id="amazon",
        dataset_key="canonical",
    )
    table = pd.read_csv(table_path)
    table.loc[0, "bbox"] = "[100.0, 0.0, 101.0]"
    _rewrite_table_and_manifest(manifest_path, table_path, table)

    with pytest.raises(ValueError, match="bbox"):
        load_contract_percentage_hotspot_table(
            contract=contract,
            region_id="amazon",
            dataset_key="canonical",
            expected_dataset_ids=("gwd30", "wad2m"),
        )


def test_load_contract_percentage_hotspot_table_rejects_duplicate_hotspot_ids(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    _write_contract_inputs(contract)
    write_percentage_hotspot_outputs(
        contract=contract,
        region_id="amazon",
        dataset_key="canonical",
        top_n=2,
        min_distance_deg=0.0,
    )

    manifest_path = percentage_hotspot_manifest_output_path(
        contract,
        region_id="amazon",
        dataset_key="canonical",
    )
    table_path = percentage_hotspot_table_output_path(
        contract,
        region_id="amazon",
        dataset_key="canonical",
    )
    table = pd.read_csv(table_path)
    table.loc[1, "hotspot_id"] = table.loc[0, "hotspot_id"]
    _rewrite_table_and_manifest(manifest_path, table_path, table)

    with pytest.raises(ValueError, match="hotspot_id"):
        load_contract_percentage_hotspot_table(
            contract=contract,
            region_id="amazon",
            dataset_key="canonical",
            expected_dataset_ids=("gwd30", "wad2m"),
        )


def test_run_phase4_percentage_contract_help_mentions_subset_and_skip() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/run_phase4_percentage_contract.py", "--help"],
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


def test_run_phase4_percentage_contract_rejects_subset_and_region_together(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase4_percentage_contract.py",
            "--output-root",
            str(tmp_path),
            "--subset",
            "ten",
            "--region",
            "amazon",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "Ambiguous region selector" in (completed.stderr + completed.stdout)
