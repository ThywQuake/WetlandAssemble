from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

import WA.visualization.phase37 as phase37_module
from WA.visualization.phase37 import (
    build_phase37_hotspot_plot_dataset,
    plot_phase37_hotspot_panel,
)


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "plot_phase3_7_hotspot_panels.py"
    )
    spec = importlib.util.spec_from_file_location("plot_phase3_7_hotspot_panels", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_phase36_metrics() -> xr.Dataset:
    coords = {
        "lat": np.array([1.75, 1.25, 0.75, 0.25], dtype=np.float32),
        "lon": np.array([100.25, 100.75, 101.25, 101.75], dtype=np.float32),
    }
    return xr.Dataset(
        {
            "entropy": xr.DataArray(
                np.array(
                    [
                        [0.1, 0.2, 0.3, 0.4],
                        [0.5, 0.6, np.nan, 0.8],
                        [0.9, 0.4, 0.2, 0.1],
                        [0.3, 0.5, 0.7, 0.9],
                    ],
                    dtype=np.float32,
                ),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "majority_class": xr.DataArray(
                np.array(
                    [
                        [0, 1, 2, 3],
                        [4, 5, -1, 7],
                        [1, 1, 2, 2],
                        [3, 3, 4, 4],
                    ],
                    dtype=np.int16,
                ),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "agreement_count": xr.DataArray(
                np.array(
                    [
                        [1, 2, 3, 1],
                        [2, 3, -1, 1],
                        [3, 2, 2, 1],
                        [1, 1, 2, 3],
                    ],
                    dtype=np.int16,
                ),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "joint_valid_mask": xr.DataArray(
                np.array(
                    [
                        [1, 1, 1, 1],
                        [1, 1, 0, 1],
                        [1, 1, 1, 1],
                        [1, 1, 1, 1],
                    ],
                    dtype=np.int8,
                ),
                dims=("lat", "lon"),
                coords=coords,
            ),
        }
    )


def _sample_phase36_classes() -> xr.Dataset:
    coords = {
        "lat": np.array([1.75, 1.25, 0.75, 0.25], dtype=np.float32),
        "lon": np.array([100.25, 100.75, 101.25, 101.75], dtype=np.float32),
    }
    return xr.Dataset(
        {
            "g2017_dominant_class": xr.DataArray(
                np.array(
                    [
                        [0, 1, 2, 3],
                        [4, 5, -1, 7],
                        [1, 1, 2, 2],
                        [3, 3, 4, 4],
                    ],
                    dtype=np.int16,
                ),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "glwd_v2_dominant_class": xr.DataArray(
                np.array(
                    [
                        [0, 1, 1, 3],
                        [4, 5, -1, 7],
                        [1, 2, 2, 2],
                        [3, 4, 4, 4],
                    ],
                    dtype=np.int16,
                ),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "gwd30_dominant_class": xr.DataArray(
                np.array(
                    [
                        [1, 1, 2, 3],
                        [4, 6, -1, 7],
                        [1, 1, 2, 6],
                        [3, 3, 4, 4],
                    ],
                    dtype=np.int16,
                ),
                dims=("lat", "lon"),
                coords=coords,
            ),
        }
    )


def _sample_phase36_classes_with_source() -> xr.Dataset:
    dataset = _sample_phase36_classes()
    coords = {
        "lat": dataset.coords["lat"].values,
        "lon": dataset.coords["lon"].values,
    }
    dataset["g2017_source_dominant_class"] = xr.DataArray(
        np.array(
            [
                [10, 10, 80, 80],
                [10, 10, 80, 80],
                [10, 80, 10, 80],
                [10, 10, 80, 80],
            ],
            dtype=np.int16,
        ),
        dims=("lat", "lon"),
        coords=coords,
    )
    dataset["glwd_v2_source_dominant_class"] = xr.DataArray(
        np.array(
            [
                [1, 1, 29, 29],
                [1, 1, 29, 29],
                [1, 29, 1, 29],
                [1, 1, 29, 29],
            ],
            dtype=np.int16,
        ),
        dims=("lat", "lon"),
        coords=coords,
    )
    dataset["gwd30_source_dominant_class"] = xr.DataArray(
        np.array(
            [
                [1, 1, 11, 11],
                [1, 1, 11, 11],
                [1, 11, 1, 11],
                [1, 1, 11, 11],
            ],
            dtype=np.int16,
        ),
        dims=("lat", "lon"),
        coords=coords,
    )
    return dataset


def _write_sample_standardized_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    coords = {
        "lat": np.array([1.75, 1.25, 0.75, 0.25], dtype=np.float32),
        "lon": np.array([100.25, 100.75, 101.25, 101.75], dtype=np.float32),
    }

    frac_g2017_10 = np.zeros((4, 4), dtype=np.float32)
    frac_g2017_80 = np.zeros((4, 4), dtype=np.float32)
    frac_g2017_10[1, 1] = 1.0
    frac_g2017_80[1, 2] = 1.0
    frac_g2017_80[2, 1] = 1.0
    frac_g2017_10[2, 2] = 1.0
    xr.Dataset(
        {
            "frac_10": xr.DataArray(frac_g2017_10, dims=("lat", "lon"), coords=coords),
            "frac_80": xr.DataArray(frac_g2017_80, dims=("lat", "lon"), coords=coords),
        }
    ).to_netcdf(root / "g2017.nc")

    frac_glwd_1 = np.zeros((4, 4), dtype=np.float32)
    frac_glwd_29 = np.zeros((4, 4), dtype=np.float32)
    frac_glwd_1[1, 1] = 1.0
    frac_glwd_29[1, 2] = 1.0
    frac_glwd_29[2, 1] = 1.0
    frac_glwd_1[2, 2] = 1.0
    xr.Dataset(
        {
            "frac_1": xr.DataArray(frac_glwd_1, dims=("lat", "lon"), coords=coords),
            "frac_29": xr.DataArray(frac_glwd_29, dims=("lat", "lon"), coords=coords),
        }
    ).to_netcdf(root / "glwd_v2.nc")

    gwd30_root = root / "_staging" / "gwd30_2016"
    tile_partials = gwd30_root / "tile_partials"
    tile_partials.mkdir(parents=True, exist_ok=True)
    stage_tile_path = tile_partials / "tile_sample.nc"
    time_coords = np.array(["2016-01-16", "2016-07-16"], dtype="datetime64[ns]")
    gwd30_class_ids = np.array([1, 11], dtype=np.int16)
    weighted = np.zeros((2, 2, 4, 4), dtype=np.float32)
    coverage = np.ones((2, 4, 4), dtype=np.float32)
    weighted[:, 0, 1, 1] = 1.0
    weighted[:, 1, 1, 2] = 1.0
    weighted[:, 1, 2, 1] = 1.0
    weighted[:, 0, 2, 2] = 1.0
    xr.Dataset(
        {
            "weighted": xr.DataArray(
                weighted,
                dims=("time", "class_id", "lat", "lon"),
                coords={
                    "time": time_coords,
                    "class_id": gwd30_class_ids,
                    **coords,
                },
            ),
            "coverage": xr.DataArray(
                coverage,
                dims=("time", "lat", "lon"),
                coords={
                    "time": time_coords,
                    **coords,
                },
            ),
        },
        attrs={"dataset_id": "gwd30", "year": 2016},
    ).to_netcdf(stage_tile_path)
    (gwd30_root / "stage_shard_0000_of_0001.json").write_text(
        json.dumps(
            {
                "staged_tiles": [
                    {
                        "path": str(stage_tile_path),
                        "bbox": [100.25, 0.25, 101.75, 1.75],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return root


def test_build_phase37_hotspot_plot_dataset_crops_bbox(tmp_path: Path) -> None:
    standardized_dir = _write_sample_standardized_dir(tmp_path / "standardized")
    plot_dataset = build_phase37_hotspot_plot_dataset(
        _sample_phase36_metrics(),
        _sample_phase36_classes(),
        bbox=(100.5, 0.5, 101.5, 1.5),
        standardized_dir=standardized_dir,
        year=2016,
    )
    try:
        assert plot_dataset.sizes["lat"] == 2
        assert plot_dataset.sizes["lon"] == 2
        np.testing.assert_array_equal(
            plot_dataset["majority_class"].values,
            np.array([[5, -1], [1, 2]], dtype=np.int16),
        )
        np.testing.assert_array_equal(
            plot_dataset["g2017_source_dominant_class"].values,
            np.array([[10, 80], [80, 10]], dtype=np.int16),
        )
        np.testing.assert_array_equal(
            plot_dataset["glwd_v2_source_dominant_class"].values,
            np.array([[1, 29], [29, 1]], dtype=np.int16),
        )
        np.testing.assert_array_equal(
            plot_dataset["gwd30_source_dominant_class"].values,
            np.array([[1, 11], [11, 1]], dtype=np.int16),
        )
    finally:
        plot_dataset.close()


def test_plot_phase37_hotspot_panel_writes_png_without_s2(tmp_path: Path) -> None:
    standardized_dir = _write_sample_standardized_dir(tmp_path / "standardized")
    plot_dataset = build_phase37_hotspot_plot_dataset(
        _sample_phase36_metrics(),
        _sample_phase36_classes(),
        bbox=(100.5, 0.5, 101.5, 1.5),
        standardized_dir=standardized_dir,
        year=2016,
    )
    output_path = tmp_path / "hotspot_panel.png"
    try:
        written = plot_phase37_hotspot_panel(
            plot_dataset,
            output_path=output_path,
            satellite_image_path=None,
            suptitle="Amazon Basin (entropy-amazon_basin-001)",
        )
    finally:
        plot_dataset.close()

    assert written == output_path
    assert output_path.is_file()


def test_plot_phase37_hotspot_panel_draws_four_independent_class_legends_in_raw_mode(
    monkeypatch,
    tmp_path: Path,
) -> None:
    standardized_dir = _write_sample_standardized_dir(tmp_path / "standardized")
    plot_dataset = build_phase37_hotspot_plot_dataset(
        _sample_phase36_metrics(),
        _sample_phase36_classes(),
        bbox=(100.5, 0.5, 101.5, 1.5),
        standardized_dir=standardized_dir,
        year=2016,
    )
    legend_titles: list[str | None] = []

    def _capture_legend(ax, style, *, present_class_ids=None, title=None):
        del ax, style, present_class_ids
        legend_titles.append(title)

    monkeypatch.setattr(phase37_module, "_draw_discrete_class_legend", _capture_legend)
    output_path = tmp_path / "hotspot_panel_legends.png"
    try:
        plot_phase37_hotspot_panel(
            plot_dataset,
            output_path=output_path,
            satellite_image_path=None,
            suptitle="Legend Layout Test",
        )
    finally:
        plot_dataset.close()

    assert legend_titles == [
        "G2017 Raw Legend",
        "GLWD v2 Raw Legend",
        "GWD30 Raw Legend",
        "Unified Majority Legend",
    ]


def test_phase37_class_styles_include_class_ids_in_legend_labels() -> None:
    unified_style = phase37_module.classification_style()
    gwd30_style = phase37_module.source_class_style("gwd30")

    assert unified_style.labels[1] == "Water 1"
    assert gwd30_style.labels[11] == "Coastal Marsh 11"


def test_build_phase37_hotspot_plot_dataset_prefers_precomputed_source_classes() -> None:
    plot_dataset = build_phase37_hotspot_plot_dataset(
        _sample_phase36_metrics(),
        _sample_phase36_classes_with_source(),
        bbox=(100.5, 0.5, 101.5, 1.5),
        standardized_dir=None,
        year=2016,
    )
    try:
        np.testing.assert_array_equal(
            plot_dataset["g2017_source_dominant_class"].values,
            np.array([[10, 80], [80, 10]], dtype=np.int16),
        )
        np.testing.assert_array_equal(
            plot_dataset["glwd_v2_source_dominant_class"].values,
            np.array([[1, 29], [29, 1]], dtype=np.int16),
        )
        np.testing.assert_array_equal(
            plot_dataset["gwd30_source_dominant_class"].values,
            np.array([[1, 11], [11, 1]], dtype=np.int16),
        )
    finally:
        plot_dataset.close()


def test_load_phase37_s2_quicklook_index_ignores_failed_artifacts(tmp_path: Path) -> None:
    module = _load_script_module()
    ok_image = tmp_path / "ok.jpg"
    plt.imsave(ok_image, np.zeros((10, 12, 3), dtype=np.float32))
    artifact_manifest = tmp_path / "phase3_7_s2_artifacts_2016_20160701.json"
    artifact_manifest.write_text(
        json.dumps(
            {
                "target_time": "2016-07-01T00:00:00",
                "artifacts": [
                    {
                        "hotspot_id": "entropy-a-001",
                        "artifact": {
                            "status": "downloaded",
                            "quicklook_path": str(ok_image),
                        },
                    },
                    {
                        "hotspot_id": "entropy-a-002",
                        "artifact": {
                            "status": "empty_collection",
                            "quicklook_path": str(tmp_path / "missing.jpg"),
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    index, timestamp = module.load_phase37_s2_quicklook_index(artifact_manifest)

    assert timestamp == pd.Timestamp("2016-07-01")
    assert index["entropy-a-001"] == ok_image
    assert index["entropy-a-002"] is None


def test_format_phase37_hotspot_title_uses_region_label_and_rank() -> None:
    module = _load_script_module()

    title = module.format_phase37_hotspot_title(
        {
            "hotspot_id": "entropy-kakaku_wetlands-001",
            "region_label": "Kakaku Wetlands",
            "region_rank": 1,
        }
    )

    assert title == "Kakaku Wetlands 001"


def test_plot_phase3_7_hotspot_panels_script_writes_pngs(tmp_path: Path) -> None:
    module = _load_script_module()
    input_dir = tmp_path / "phase3.6"
    output_dir = tmp_path / "figures"
    standardized_dir = _write_sample_standardized_dir(tmp_path / "standardized")
    hotspots_manifest = tmp_path / "phase3_7_hotspots_2016.json"
    s2_artifacts_manifest = tmp_path / "phase3_7_s2_artifacts_2016_20160701.json"
    input_dir.mkdir(parents=True, exist_ok=True)
    _sample_phase36_metrics().to_netcdf(input_dir / "phase3_6_entropy_global_500m_2016.nc")
    _sample_phase36_classes().to_netcdf(
        input_dir / "phase3_6_unified_classes_global_500m_2016.nc"
    )

    hotspots_manifest.write_text(
        json.dumps(
            {
                "year": 2016,
                "hotspots": [
                    {
                        "hotspot_id": "entropy-amazon_basin-001",
                        "region_slug": "amazon_basin",
                        "region_label": "Amazon Basin",
                        "bbox": [100.0, 0.0, 101.0, 1.5],
                    },
                    {
                        "hotspot_id": "entropy-sudd-001",
                        "region_slug": "sudd",
                        "region_label": "Sudd Wetland",
                        "bbox": [100.5, 0.5, 101.5, 1.5],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    s2_quicklook = tmp_path / "entropy-amazon_basin-001_s2_rgb.jpg"
    plt.imsave(s2_quicklook, np.zeros((10, 12, 3), dtype=np.float32))
    s2_artifacts_manifest.write_text(
        json.dumps(
            {
                "target_time": "2016-07-01T00:00:00",
                "artifacts": [
                    {
                        "hotspot_id": "entropy-amazon_basin-001",
                        "artifact": {
                            "status": "downloaded",
                            "quicklook_path": str(s2_quicklook),
                        },
                    },
                    {
                        "hotspot_id": "entropy-sudd-001",
                        "artifact": {
                            "status": "empty_collection",
                            "quicklook_path": str(tmp_path / "missing.jpg"),
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = module.main(
        [
            "--hotspots-manifest",
            str(hotspots_manifest),
            "--s2-artifacts-manifest",
            str(s2_artifacts_manifest),
            "--input-dir",
            str(input_dir),
            "--standardized-dir",
            str(standardized_dir),
            "--output-dir",
            str(output_dir),
            "--dpi",
            "300",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "entropy-amazon_basin-001_panel.png").is_file()
    assert (output_dir / "entropy-sudd-001_panel.png").is_file()


def test_plot_phase3_7_hotspot_panels_script_uses_precomputed_source_vars_without_standardized(
    tmp_path: Path,
) -> None:
    module = _load_script_module()
    input_dir = tmp_path / "phase3.6"
    output_dir = tmp_path / "figures"
    hotspots_manifest = tmp_path / "phase3_7_hotspots_2016.json"
    s2_artifacts_manifest = tmp_path / "phase3_7_s2_artifacts_2016_20160701.json"
    input_dir.mkdir(parents=True, exist_ok=True)
    _sample_phase36_metrics().to_netcdf(input_dir / "phase3_6_entropy_global_500m_2016.nc")
    _sample_phase36_classes_with_source().to_netcdf(
        input_dir / "phase3_6_unified_classes_global_500m_2016.nc"
    )

    hotspots_manifest.write_text(
        json.dumps(
            {
                "year": 2016,
                "hotspots": [
                    {
                        "hotspot_id": "entropy-sudd-001",
                        "region_slug": "sudd",
                        "region_label": "Sudd Wetland",
                        "bbox": [100.5, 0.5, 101.5, 1.5],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    s2_artifacts_manifest.write_text(
        json.dumps({"target_time": "2016-07-01T00:00:00", "artifacts": []}),
        encoding="utf-8",
    )

    exit_code = module.main(
        [
            "--hotspots-manifest",
            str(hotspots_manifest),
            "--s2-artifacts-manifest",
            str(s2_artifacts_manifest),
            "--input-dir",
            str(input_dir),
            "--standardized-dir",
            str(tmp_path / "missing_standardized"),
            "--output-dir",
            str(output_dir),
            "--dpi",
            "200",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "entropy-sudd-001_panel.png").is_file()
