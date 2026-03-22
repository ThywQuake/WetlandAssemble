from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from WA.config import AppConfig
from WA.modis_batch import download_phase2_modis_batch, load_focus_areas_csv
from WA.validation.modis_reference import ModisReferenceArtifact


def _focus_area_csv_line(
    aoi_id: str,
    region_slug: str,
    target_time: str,
    bbox: str,
    center_lon: float,
    center_lat: float,
    disagreement_score: float,
    participant_count: int,
    wetland_vote_fraction: float,
) -> str:
    return ",".join(
        [
            aoi_id,
            region_slug,
            target_time,
            f'"{bbox}"',
            str(center_lon),
            str(center_lat),
            str(disagreement_score),
            str(participant_count),
            str(wetland_vote_fraction),
        ]
    )


def test_load_focus_areas_csv_prefixes_aoi_ids_by_region(tmp_path: Path) -> None:
    csv_path = tmp_path / "focus_areas.csv"
    csv_path.write_text(
        "\n".join(
            [
                "aoi_id,region_slug,target_time,bbox,center_lon,center_lat,disagreement_score,participant_count,wetland_vote_fraction",
                _focus_area_csv_line(
                    "rough-201907-brazil-001",
                    "brazil",
                    "2019-07-01",
                    "(-73.25, 3.75, -71.25, 5.75)",
                    -72.25,
                    4.75,
                    1.0,
                    4,
                    0.5,
                ),
            ]
        ),
        encoding="utf-8",
    )

    records = load_focus_areas_csv(csv_path, region_id="amazon_basin")

    assert len(records) == 1
    assert records[0]["original_aoi_id"] == "rough-201907-brazil-001"
    focus_area = records[0]["focus_area"]
    assert focus_area.aoi_id == "amazon_basin__rough-201907-brazil-001"
    assert focus_area.bbox == (-73.25, 3.75, -71.25, 5.75)


def test_download_phase2_modis_batch_writes_per_run_and_batch_manifests(
    tmp_path: Path,
    monkeypatch,
) -> None:
    phase2_root = tmp_path / "results/phase2/rough"
    run_dir = phase2_root / "amazon_basin" / "201907"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "focus_areas.csv").write_text(
        "\n".join(
            [
                "aoi_id,region_slug,target_time,bbox,center_lon,center_lat,disagreement_score,participant_count,wetland_vote_fraction",
                _focus_area_csv_line(
                    "rough-201907-brazil-001",
                    "brazil",
                    "2019-07-01",
                    "(-73.25, 3.75, -71.25, 5.75)",
                    -72.25,
                    4.75,
                    1.0,
                    4,
                    0.5,
                ),
                _focus_area_csv_line(
                    "rough-201907-other-002",
                    "other",
                    "2019-07-01",
                    "(-76.25, -6.5, -74.25, -4.5)",
                    -75.25,
                    -5.5,
                    1.0,
                    4,
                    0.5,
                ),
            ]
        ),
        encoding="utf-8",
    )

    app_config = AppConfig(
        datasets={},
        regions={},
        analysis={},
        gee={"gee_project_id": "test-project"},
        dataset_config_path=tmp_path / "datasets.yaml",
        gee_config_path=tmp_path / "gee.yaml",
    )

    def fake_download_modis_reference(  # type: ignore[no-untyped-def]
        aoi,
        gee_client,
        *,
        results_root="results",
        allow_interactive_auth=False,
        skip_existing=True,
        scale_meters=500,
    ):
        root = Path(results_root)
        quicklook_path = root / "quicklooks" / aoi.region_slug / "20190701_20190709" / (
            f"{aoi.aoi_id}_modis_rgb.jpg"
        )
        chip_path = root / "rough_truth" / aoi.region_slug / "20190701_20190709" / (
            f"{aoi.aoi_id}_modis_chip.tif"
        )
        return ModisReferenceArtifact(
            aoi_id=aoi.aoi_id,
            region_slug=aoi.region_slug,
            target_time=pd.Timestamp("2019-07-01"),
            window_start=pd.Timestamp("2019-07-01"),
            window_end=pd.Timestamp("2019-07-09"),
            quicklook_path=quicklook_path,
            chip_path=chip_path,
            status="downloaded",
        )

    monkeypatch.setattr(
        "WA.modis_batch.download_modis_reference",
        fake_download_modis_reference,
    )

    outputs = download_phase2_modis_batch(
        app_config,
        phase2_root=phase2_root,
        results_root=tmp_path / "results",
        target_times=["2019-07-01"],
    )

    assert len(outputs) == 1
    assert outputs[0].region_id == "amazon_basin"
    assert outputs[0].aoi_count == 2
    assert outputs[0].status_counts == {"downloaded": 2}

    per_run_manifest = json.loads((run_dir / "modis_artifacts.json").read_text(encoding="utf-8"))
    assert per_run_manifest["region_id"] == "amazon_basin"
    assert per_run_manifest["aoi_count"] == 2
    assert per_run_manifest["artifacts"][0]["materialized_aoi_id"].startswith("amazon_basin__")

    batch_manifest = json.loads(
        (phase2_root / "modis_download_manifest.json").read_text(encoding="utf-8")
    )
    assert len(batch_manifest["runs"]) == 1
    assert batch_manifest["runs"][0]["region_id"] == "amazon_basin"
