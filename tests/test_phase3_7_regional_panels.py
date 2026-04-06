from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import xarray as xr

from WA.visualization.phase37 import subset_phase37_plot_dataset_to_bbox


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "plot_phase3_7_regional_panels.py"
    )
    spec = importlib.util.spec_from_file_location("plot_phase3_7_regional_panels", script_path)
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


def _sample_phase37_plot_dataset() -> xr.Dataset:
    return xr.merge([_sample_phase36_metrics(), _sample_phase36_classes()])


def test_subset_phase37_plot_dataset_to_bbox_handles_descending_lat() -> None:
    subset = subset_phase37_plot_dataset_to_bbox(
        _sample_phase37_plot_dataset(),
        (100.5, 0.5, 101.5, 1.5),
    )

    assert subset.sizes["lat"] == 2
    assert subset.sizes["lon"] == 2
    np.testing.assert_array_equal(subset["lat"].values, np.array([1.25, 0.75], dtype=np.float32))
    np.testing.assert_array_equal(
        subset["lon"].values,
        np.array([100.75, 101.25], dtype=np.float32),
    )


def test_plot_phase3_7_regional_panels_script_writes_pngs(tmp_path: Path) -> None:
    module = _load_script_module()
    input_dir = tmp_path / "phase3.6"
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "figures"
    input_dir.mkdir(parents=True, exist_ok=True)
    _sample_phase36_metrics().to_netcdf(input_dir / "phase3_6_entropy_global_500m_2016.nc")
    _sample_phase36_classes().to_netcdf(
        input_dir / "phase3_6_unified_classes_global_500m_2016.nc"
    )

    regions_file = tmp_path / "regions.yaml"
    regions_file.write_text(
        """
regions:
  amazon_basin:
    label: "Amazon Basin"
    priority: 1
    bbox: [100.0, 0.0, 102.0, 2.0]
  sudd:
    label: "Sudd Wetland"
    priority: 2
    bbox: [100.5, 0.5, 101.5, 1.5]
""".strip(),
        encoding="utf-8",
    )

    exit_code = module.main(
        [
            "--input-dir",
            str(input_dir),
            "--cache-dir",
            str(cache_dir),
            "--output-dir",
            str(output_dir),
            "--regions-file",
            str(regions_file),
            "--sample-step",
            "2",
            "--source-lat-chunk-size",
            "3",
            "--dpi",
            "300",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "phase3_7_region_amazon_basin_global_500m_2016_sample2.png").is_file()
    assert (output_dir / "phase3_7_region_sudd_global_500m_2016_sample2.png").is_file()
    assert (cache_dir / "phase3_7_global_plot_cache_global_500m_2016_sample2.nc").is_file()
