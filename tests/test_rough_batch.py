from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import xarray as xr
import yaml
from pytest import MonkeyPatch

import WA.rough_batch as rough_batch
from WA.config import AppConfig
from WA.loaders.base import DatasetLoader, DatasetMetadata
from WA.rough_batch import (
    PriorityRegion,
    load_priority_regions,
    run_rough_region_batch,
)
from WA.rough_probe import PreparedRoughDataset, RoughDatasetProbeResult


def build_app_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        datasets={
            "g2017": {"loader_type": "geotiff", "name": "G2017", "path": str(tmp_path)},
            "swamps": {"loader_type": "swamps", "name": "SWAMPS", "path": str(tmp_path)},
            "glwd_v2": {"loader_type": "glwd", "name": "GLWD v2", "path": str(tmp_path)},
        },
        regions={"tropical": {"bbox": [-180, -23.5, 180, 23.5]}},
        analysis={},
        gee={"gee_project_id": "demo-project"},
        dataset_config_path=tmp_path / "datasets.yaml",
        gee_config_path=tmp_path / "gee.yaml",
    )


def test_load_priority_regions_reads_region_catalog(tmp_path: Path) -> None:
    path = tmp_path / "regions.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "regions": {
                    "amazon_basin": {
                        "label": "Amazon Basin",
                        "kind": "river_basin",
                        "priority": 1,
                        "continent": "South America",
                        "bbox": [-80.0, -20.0, -45.0, 7.0],
                        "rationale": "test",
                        "bbox_basis": "test",
                        "source_urls": ["https://example.com"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    regions = load_priority_regions(path)

    assert list(regions) == ["amazon_basin"]
    assert regions["amazon_basin"] == PriorityRegion(
        region_id="amazon_basin",
        label="Amazon Basin",
        kind="river_basin",
        priority=1,
        continent="South America",
        bbox=(-80.0, -20.0, -45.0, 7.0),
        rationale="test",
        bbox_basis="test",
        source_urls=("https://example.com",),
    )


def test_load_priority_regions_falls_back_to_embedded_default_when_default_file_missing(
    monkeypatch: MonkeyPatch,
) -> None:
    original_exists = Path.exists

    def fake_exists(path: Path) -> bool:
        if path == rough_batch.DEFAULT_PRIORITY_REGIONS_PATH:
            return False
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", fake_exists)

    regions = load_priority_regions(rough_batch.DEFAULT_PRIORITY_REGIONS_PATH)

    assert "amazon_basin" in regions
    assert "mekong_delta" in regions
    assert len(regions) == 9


def test_load_priority_regions_raises_for_missing_custom_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing-regions.yaml"

    try:
        load_priority_regions(missing_path)
    except FileNotFoundError as exc:
        assert "Priority region file not found" in str(exc)
    else:
        raise AssertionError("Expected missing custom region file to raise FileNotFoundError")


def test_run_rough_region_batch_writes_outputs_for_multiple_windows(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app_config = build_app_config(tmp_path)
    regions_path = tmp_path / "regions.yaml"
    regions_path.write_text(
        yaml.safe_dump(
            {
                "regions": {
                    "amazon_basin": {
                        "label": "Amazon Basin",
                        "kind": "river_basin",
                        "priority": 1,
                        "continent": "South America",
                        "bbox": [-80.0, -20.0, -45.0, 7.0],
                        "rationale": "test",
                        "bbox_basis": "test",
                        "source_urls": ["https://example.com"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    dummy_loader = cast(DatasetLoader, object())
    dummy_metadata = cast(DatasetMetadata, object())
    prepared = [
        PreparedRoughDataset("g2017", {"loader_type": "geotiff"}, dummy_loader, dummy_metadata),
        PreparedRoughDataset("gwd30", {"loader_type": "gwd30"}, dummy_loader, dummy_metadata),
        PreparedRoughDataset("glwd_v2", {"loader_type": "glwd"}, dummy_loader, dummy_metadata),
    ]

    monkeypatch.setattr(
        "WA.rough_batch.prepare_datasets",
        lambda app_config, dataset_ids: (prepared, []),
    )

    coords = {"lat": [0.5, -0.5], "lon": [100.5, 101.5]}

    def fake_probe(
        prepared_dataset: PreparedRoughDataset,
        options: Any,
        reference_grid: xr.DataArray,
    ) -> tuple[RoughDatasetProbeResult, xr.DataArray | None]:
        if prepared_dataset.dataset_id == "glwd_v2":
            return (
                RoughDatasetProbeResult(
                    dataset_id="glwd_v2",
                    loader_type="glwd",
                    status="failed_empty_harmonized_surface",
                    effective_time_range=None,
                    metadata={},
                    discovery={},
                    dataset_summary=None,
                    harmonized_summary=None,
                    comparison_source_variable="combined_classes",
                    error="glwd_v2 produced an empty binary surface from combined_classes",
                    traceback_text=None,
                    elapsed_seconds=0.1,
                ),
                None,
            )
        values = (
            np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
            if prepared_dataset.dataset_id == "g2017"
            else np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32)
        )
        dataset_summary = None
        if prepared_dataset.dataset_id == "gwd30":
            dataset_summary = {
                "strategy": "direct_to_reference_grid",
                "load_trace": {
                    "strategy": "direct_to_reference_grid",
                    "years": [
                        {
                            "year": 2019,
                            "selected_band_indexes": [0, 1],
                            "selected_tiles": [
                                {
                                    "path": "/tmp/31NEA_wetland_2019.tif",
                                    "tile_code": "31NEA",
                                    "tile_bbox": [100.0, 0.0, 101.0, 1.0],
                                }
                            ],
                        }
                    ],
                },
            }
        return (
            RoughDatasetProbeResult(
                dataset_id=prepared_dataset.dataset_id,
                loader_type=str(prepared_dataset.dataset_config["loader_type"]),
                status="participating",
                effective_time_range=None,
                metadata={},
                discovery={},
                dataset_summary=dataset_summary,
                harmonized_summary={"non_null_count": 4, "wetland_cell_count": 2},
                comparison_source_variable="wetland_fraction",
                elapsed_seconds=0.1,
            ),
            xr.DataArray(
                values,
                coords=coords,
                dims=("lat", "lon"),
                attrs={"comparison_time": options.target_time.isoformat()},
            ),
        )

    monkeypatch.setattr("WA.rough_batch.probe_prepared_dataset", fake_probe)

    outputs = run_rough_region_batch(
        app_config,
        regions_path=regions_path,
        region_ids=["amazon_basin"],
        target_times=["2000-03-01", "2019-07-01"],
        dataset_ids=["g2017", "gwd30", "glwd_v2"],
        results_root=tmp_path / "results",
        top_n=2,
        top_n_per_region=1,
    )

    assert len(outputs) == 2
    for output in outputs:
        assert output.status == "completed_with_failures"
        assert output.metrics_path is not None and output.metrics_path.exists()
        assert output.comparison_grids_path is not None and output.comparison_grids_path.exists()
        assert (
            output.participant_surfaces_path is not None
            and output.participant_surfaces_path.exists()
        )
        assert output.focus_areas_path is not None and output.focus_areas_path.exists()
        summary = json.loads(output.summary_path.read_text(encoding="utf-8"))
        assert summary["status"] == "completed_with_failures"
        statuses = {
            result["dataset_id"]: result["status"] for result in summary["dataset_results"]
        }
        assert statuses["glwd_v2"] == "failed_empty_harmonized_surface"
        assert set(summary["participant_dataset_ids"]) == {"g2017", "gwd30"}
        assert summary["output_files"]["gwd30_trace_path"] is not None
        assert summary["output_files"]["gwd30_tiles_geojson_path"] is not None

    manifest = json.loads(
        (tmp_path / "results" / "batch_manifest.json").read_text(encoding="utf-8")
    )
    assert len(manifest["runs"]) == 2


def test_run_rough_region_batch_resolves_precomputed_gwd30_surface_root(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    app_config = build_app_config(tmp_path)
    regions_path = tmp_path / "regions.yaml"
    regions_path.write_text(
        yaml.safe_dump(
            {
                "regions": {
                    "amazon_basin": {
                        "label": "Amazon Basin",
                        "kind": "river_basin",
                        "priority": 1,
                        "continent": "South America",
                        "bbox": [-80.0, -20.0, -45.0, 7.0],
                        "rationale": "test",
                        "bbox_basis": "test",
                        "source_urls": ["https://example.com"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    precomputed_root = tmp_path / "precomputed"
    surface_dir = precomputed_root / "amazon_basin" / "201907"
    surface_dir.mkdir(parents=True, exist_ok=True)
    xr.Dataset(
        {"wetland_fraction": (("lat", "lon"), np.ones((2, 2), dtype=np.float32))},
        coords={"lat": [0.5, -0.5], "lon": [100.5, 101.5]},
    ).to_netcdf(surface_dir / "gwd30_surface.nc")

    dummy_loader = cast(DatasetLoader, object())
    dummy_metadata = cast(DatasetMetadata, object())
    prepared = [
        PreparedRoughDataset("gwd30", {"loader_type": "gwd30"}, dummy_loader, dummy_metadata),
        PreparedRoughDataset("g2017", {"loader_type": "geotiff"}, dummy_loader, dummy_metadata),
    ]
    monkeypatch.setattr(
        "WA.rough_batch.prepare_datasets",
        lambda app_config, dataset_ids: (prepared, []),
    )

    seen_surface_paths: list[str | None] = []

    def fake_probe(
        prepared_dataset: PreparedRoughDataset,
        options: Any,
        reference_grid: xr.DataArray,
    ) -> tuple[RoughDatasetProbeResult, xr.DataArray | None]:
        if prepared_dataset.dataset_id == "gwd30":
            seen_surface_paths.append(options.gwd30_surface_path)
        return (
            RoughDatasetProbeResult(
                dataset_id=prepared_dataset.dataset_id,
                loader_type=str(prepared_dataset.dataset_config["loader_type"]),
                status="participating",
                effective_time_range=None,
                metadata={},
                discovery={},
                dataset_summary={},
                harmonized_summary={"non_null_count": 4, "wetland_cell_count": 2},
                comparison_source_variable="wetland_fraction",
                elapsed_seconds=0.1,
            ),
            xr.DataArray(
                np.ones((2, 2), dtype=np.float32),
                coords={"lat": [0.5, -0.5], "lon": [100.5, 101.5]},
                dims=("lat", "lon"),
            ),
        )

    monkeypatch.setattr("WA.rough_batch.probe_prepared_dataset", fake_probe)

    outputs = run_rough_region_batch(
        app_config,
        regions_path=regions_path,
        region_ids=["amazon_basin"],
        target_times=["2019-07-01"],
        dataset_ids=["gwd30", "g2017"],
        results_root=tmp_path / "results",
        gwd30_surface_root=precomputed_root,
    )

    assert len(outputs) == 1
    assert seen_surface_paths == [str(surface_dir / "gwd30_surface.nc")]
