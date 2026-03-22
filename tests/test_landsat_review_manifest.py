from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from WA.landsat_review_manifest import build_phase2_landsat_review_manifests


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


def test_build_phase2_landsat_review_manifests_writes_run_and_batch_outputs(
    tmp_path: Path,
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
            ]
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "comparison_time": "2019-07-01T00:00:00",
                "dataset_a": "g2017",
                "dataset_b": "gwd30",
                "iou": 0.25,
                "f1_score": 0.4,
                "kappa": 0.1,
            }
        ]
    ).to_csv(run_dir / "pairwise_metrics.csv", index=False)
    (run_dir / "run_summary.json").write_text(
        json.dumps(
            {
                "status": "completed_with_skips",
                "participant_dataset_ids": ["g2017", "gwd30"],
                "output_files": {
                    "metrics_path": str(run_dir / "pairwise_metrics.csv"),
                    "comparison_grids_path": str(run_dir / "comparison_grids.nc"),
                    "participant_surfaces_path": str(run_dir / "participant_surfaces.nc"),
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "landsat_artifacts.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "original_aoi_id": "rough-201907-brazil-001",
                        "materialized_aoi_id": "amazon_basin__rough-201907-brazil-001",
                        "artifact": {
                            "aoi_id": "amazon_basin__rough-201907-brazil-001",
                            "status": "downloaded",
                            "window_start": "2019-05-01T00:00:00",
                            "window_end": "2019-10-01T00:00:00",
                            "quicklook_path": "results/quicklooks_landsat/brazil/x.jpg",
                            "chip_path": "results/rough_truth_landsat/brazil/x.tif",
                            "download_mode": "synchronous",
                            "message": None,
                            "collection_ids": ["LANDSAT/LC08/C02/T1_L2"],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rows = build_phase2_landsat_review_manifests(phase2_root=phase2_root)

    assert len(rows) == 1
    assert rows[0].region_id == "amazon_basin"
    assert rows[0].image_status == "downloaded"
    assert rows[0].mean_iou == 0.25
    assert rows[0].mean_f1_score == 0.4
    assert rows[0].min_kappa == 0.1

    run_csv = pd.read_csv(run_dir / "landsat_review_manifest.csv")
    assert len(run_csv) == 1
    batch_csv = pd.read_csv(phase2_root / "landsat_review_manifest.csv")
    assert len(batch_csv) == 1
