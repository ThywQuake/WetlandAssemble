from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.evidence_contract import load_phase4_evidence_contract
from WA.comparison.trend_agreement import TrendAgreementResult
from WA.comparison.trend_hotspots import (
    build_trend_hotspot_table,
    load_contract_trend_hotspot_table,
    trend_hotspot_manifest_output_path,
    trend_hotspot_table_output_path,
    write_trend_hotspot_outputs,
)


def _make_agreement_result(*, disputed: bool = True) -> TrendAgreementResult:
    coords = {"lat": [1.0, 0.0], "lon": [100.0, 101.0]}
    agreement_ratio_values = np.array(
        [[0.5, 0.5], [2.0 / 3.0, 1.0 if disputed else 1.0]],
        dtype=np.float64,
    )
    if not disputed:
        agreement_ratio_values[:] = 1.0
    agreement_ratio = xr.DataArray(
        agreement_ratio_values,
        dims=("lat", "lon"),
        coords=coords,
    )
    slope_std = xr.DataArray(
        np.array([[0.1, 0.3], [0.9, 0.2]], dtype=np.float64),
        dims=("lat", "lon"),
        coords=coords,
    )
    mean_slope = xr.DataArray(
        np.array([[0.01, 0.02], [0.03, 0.04]], dtype=np.float64),
        dims=("lat", "lon"),
        coords=coords,
    )
    disputed_mask = xr.DataArray(
        agreement_ratio_values < 1.0,
        dims=("lat", "lon"),
        coords=coords,
    )
    false_mask = xr.zeros_like(disputed_mask, dtype=bool)
    return TrendAgreementResult(
        overlap_window=("2001-01-01", "2010-12-31"),
        participant_ids=["wad2m", "gwd30"],
        agreement_ratio=agreement_ratio,
        mean_slope=mean_slope,
        slope_std=slope_std,
        robust_increase=false_mask,
        robust_decrease=false_mask,
        robust_stable=false_mask,
        disputed=disputed_mask,
        regional_summary=pd.DataFrame(
            {
                "region": ["amazon", "global"],
                "total_valid_pixels": [3, 3],
                "mean_agreement_ratio": [0.55, 0.55],
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
    *,
    contract,
    region_id: str,
    participant_ids: list[str],
) -> tuple[Path, Path]:
    participant_set_key = "gwd30+wad2m"
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
    surface_path.write_text("placeholder-surface", encoding="utf-8")
    summary_path.write_text("placeholder,summary\n", encoding="utf-8")
    return (surface_path, summary_path)


def test_trend_hotspot_paths_use_sorted_participant_ids(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)

    manifest_a = trend_hotspot_manifest_output_path(
        contract,
        region_id="amazon",
        participant_ids=["wad2m", "gwd30"],
    )
    manifest_b = trend_hotspot_manifest_output_path(
        contract,
        region_id="amazon",
        participant_ids=["gwd30", "wad2m"],
    )
    table_a = trend_hotspot_table_output_path(
        contract,
        region_id="amazon",
        participant_ids=["wad2m", "gwd30"],
    )

    assert manifest_a == manifest_b
    assert manifest_a.name == "gwd30+wad2m__amazon__trend_hotspot_manifest.json"
    assert table_a.name == "gwd30+wad2m__amazon__trend_hotspot_manifest.csv"


def test_build_trend_hotspot_table_ranks_disagreement_first_then_slope_std() -> None:
    agreement = _make_agreement_result()

    table = build_trend_hotspot_table(
        agreement,
        region_id="amazon",
        top_n=3,
    )

    assert table["hotspot_rank"].tolist() == [1, 2, 3]
    assert table["center_lon"].tolist() == [101.0, 100.0, 100.0]
    assert table["center_lat"].tolist() == [1.0, 1.0, 0.0]
    assert table["disagreement_score"].tolist() == pytest.approx([0.5, 0.5, 1.0 / 3.0])
    assert table["slope_std"].tolist() == pytest.approx([0.3, 0.1, 0.9])


def test_write_and_reload_trend_hotspot_outputs_round_trip(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    agreement = _make_agreement_result()
    participant_ids = ["wad2m", "gwd30"]
    surface_path, summary_path = _write_dummy_agreement_inputs(
        contract=contract,
        region_id="amazon",
        participant_ids=participant_ids,
    )

    manifest = write_trend_hotspot_outputs(
        contract=contract,
        agreement_result=agreement,
        region_id="amazon",
        participant_ids=participant_ids,
        surface_output_path=surface_path,
        summary_output_path=summary_path,
        top_n=2,
    )
    bundle = load_contract_trend_hotspot_table(
        contract=contract,
        region_id="amazon",
        participant_ids=participant_ids,
    )

    assert manifest.participant_ids == ("gwd30", "wad2m")
    assert manifest.participant_set_key == "gwd30+wad2m"
    assert manifest.surface_output_path == surface_path.resolve()
    assert manifest.summary_output_path == summary_path.resolve()
    assert bundle.manifest.contract_metadata["candidate_mask"] == "disputed"
    assert bundle.table["hotspot_id"].tolist() == [
        "trend-amazon-gwd30+wad2m-001",
        "trend-amazon-gwd30+wad2m-002",
    ]
    assert bundle.table["participant_ids"].tolist() == [
        ("gwd30", "wad2m"),
        ("gwd30", "wad2m"),
    ]
    assert bundle.table["bbox"].iloc[0] == (100.5, 0.5, 101.5, 1.5)


def test_load_contract_trend_hotspot_table_rejects_mixed_participant_ids(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    participant_ids = ["wad2m", "gwd30"]
    surface_path, summary_path = _write_dummy_agreement_inputs(
        contract=contract,
        region_id="amazon",
        participant_ids=participant_ids,
    )
    write_trend_hotspot_outputs(
        contract=contract,
        agreement_result=_make_agreement_result(),
        region_id="amazon",
        participant_ids=participant_ids,
        surface_output_path=surface_path,
        summary_output_path=summary_path,
        top_n=2,
    )
    table_path = trend_hotspot_table_output_path(
        contract,
        region_id="amazon",
        participant_ids=participant_ids,
    )
    manifest_path = trend_hotspot_manifest_output_path(
        contract,
        region_id="amazon",
        participant_ids=participant_ids,
    )

    table = pd.read_csv(table_path)
    table.loc[0, "participant_ids_json"] = json.dumps(["gwd30", "swamps"])
    table_text = table.to_csv(index=False, lineterminator="\n")
    table_path.write_text(table_text, encoding="utf-8")
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_payload["table_sha256"] = hashlib.sha256(
        table_text.encode("utf-8")
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="mixed participant ids"):
        load_contract_trend_hotspot_table(
            contract=contract,
            region_id="amazon",
            participant_ids=participant_ids,
        )


def test_load_contract_trend_hotspot_table_rejects_malformed_bbox(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    participant_ids = ["wad2m", "gwd30"]
    surface_path, summary_path = _write_dummy_agreement_inputs(
        contract=contract,
        region_id="amazon",
        participant_ids=participant_ids,
    )
    write_trend_hotspot_outputs(
        contract=contract,
        agreement_result=_make_agreement_result(),
        region_id="amazon",
        participant_ids=participant_ids,
        surface_output_path=surface_path,
        summary_output_path=summary_path,
        top_n=2,
    )
    table_path = trend_hotspot_table_output_path(
        contract,
        region_id="amazon",
        participant_ids=participant_ids,
    )
    manifest_path = trend_hotspot_manifest_output_path(
        contract,
        region_id="amazon",
        participant_ids=participant_ids,
    )

    table = pd.read_csv(table_path)
    table.loc[0, "bbox"] = "[100.0, 0.0, 101.0]"
    table_text = table.to_csv(index=False, lineterminator="\n")
    table_path.write_text(table_text, encoding="utf-8")
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_payload["table_sha256"] = hashlib.sha256(
        table_text.encode("utf-8")
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="bbox"):
        load_contract_trend_hotspot_table(
            contract=contract,
            region_id="amazon",
            participant_ids=participant_ids,
        )


def test_load_contract_trend_hotspot_table_rejects_malformed_contract_metadata(
    tmp_path: Path,
) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)
    participant_ids = ["wad2m", "gwd30"]
    surface_path, summary_path = _write_dummy_agreement_inputs(
        contract=contract,
        region_id="amazon",
        participant_ids=participant_ids,
    )
    write_trend_hotspot_outputs(
        contract=contract,
        agreement_result=_make_agreement_result(),
        region_id="amazon",
        participant_ids=participant_ids,
        surface_output_path=surface_path,
        summary_output_path=summary_path,
        top_n=2,
    )
    manifest_path = trend_hotspot_manifest_output_path(
        contract,
        region_id="amazon",
        participant_ids=participant_ids,
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["contract_metadata_json"] = "{bad-json"
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="contract_metadata_json"):
        load_contract_trend_hotspot_table(
            contract=contract,
            region_id="amazon",
            participant_ids=participant_ids,
        )


def test_build_trend_hotspot_table_rejects_zero_disputed_candidates() -> None:
    with pytest.raises(ValueError, match="zero-candidate"):
        build_trend_hotspot_table(
            _make_agreement_result(disputed=False),
            region_id="amazon",
            top_n=3,
        )


def test_write_trend_hotspot_outputs_requires_agreement_inputs(tmp_path: Path) -> None:
    contract = load_phase4_evidence_contract(output_root=tmp_path)

    with pytest.raises(FileNotFoundError, match="Missing trend agreement surface"):
        write_trend_hotspot_outputs(
            contract=contract,
            agreement_result=_make_agreement_result(),
            region_id="amazon",
            participant_ids=["wad2m", "gwd30"],
            surface_output_path=tmp_path / "missing_surface.nc",
            summary_output_path=tmp_path / "missing_summary.csv",
            top_n=2,
        )
