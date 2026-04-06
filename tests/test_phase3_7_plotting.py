from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import xarray as xr

from WA.visualization.phase37 import (
    build_phase37_global_plot_dataset,
    plot_phase37_global_figure,
    write_phase37_global_plot_cache,
)


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "plot_phase3_7_metrics.py"
    spec = importlib.util.spec_from_file_location("plot_phase3_7_metrics", script_path)
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
    metrics = _sample_phase36_metrics()
    classes = _sample_phase36_classes()
    return xr.merge([metrics, classes])


def test_build_phase37_global_plot_dataset_preserves_values_when_sample_step_is_one(
    tmp_path: Path,
) -> None:
    metrics_path = tmp_path / "phase3_6_entropy_global_500m_2016.nc"
    classes_path = tmp_path / "phase3_6_unified_classes_global_500m_2016.nc"
    _sample_phase36_metrics().to_netcdf(metrics_path)
    _sample_phase36_classes().to_netcdf(classes_path)

    result = build_phase37_global_plot_dataset(
        metrics_path,
        classes_path,
        sample_step=1,
    )
    try:
        np.testing.assert_allclose(
            result["entropy"].values,
            _sample_phase36_metrics()["entropy"].values,
            equal_nan=True,
        )
        np.testing.assert_array_equal(
            result["gwd30_dominant_class"].values,
            _sample_phase36_classes()["gwd30_dominant_class"].values,
        )
    finally:
        result.close()


def test_build_phase37_global_plot_dataset_sparse_samples_without_reprojection(
    tmp_path: Path,
) -> None:
    metrics_path = tmp_path / "phase3_6_entropy_global_500m_2016.nc"
    classes_path = tmp_path / "phase3_6_unified_classes_global_500m_2016.nc"
    _sample_phase36_metrics().to_netcdf(metrics_path)
    _sample_phase36_classes().to_netcdf(classes_path)

    result = build_phase37_global_plot_dataset(
        metrics_path,
        classes_path,
        sample_step=2,
    )
    try:
        np.testing.assert_array_equal(
            result["lat"].values,
            np.array([1.75, 0.75], dtype=np.float32),
        )
        np.testing.assert_array_equal(
            result["lon"].values,
            np.array([100.25, 101.25], dtype=np.float32),
        )
        np.testing.assert_allclose(
            result["entropy"].values,
            np.array([[0.1, 0.3], [0.9, 0.2]], dtype=np.float32),
            equal_nan=True,
        )
        np.testing.assert_array_equal(
            result["agreement_count"].values,
            np.array([[1, 3], [3, 2]], dtype=np.int16),
        )
    finally:
        result.close()


def test_write_phase37_global_plot_cache_writes_sparse_cache(tmp_path: Path) -> None:
    metrics_path = tmp_path / "phase3_6_entropy_global_500m_2016.nc"
    classes_path = tmp_path / "phase3_6_unified_classes_global_500m_2016.nc"
    cache_path = tmp_path / "phase3_7_cache.nc"
    _sample_phase36_metrics().to_netcdf(metrics_path)
    _sample_phase36_classes().to_netcdf(classes_path)

    written = write_phase37_global_plot_cache(
        metrics_path,
        classes_path,
        cache_path=cache_path,
        sample_step=2,
        source_lat_chunk_size=3,
    )

    assert written == cache_path
    assert cache_path.is_file()
    cached = xr.open_dataset(cache_path)
    try:
        assert int(cached.attrs["sample_step"]) == 2
        np.testing.assert_array_equal(
            cached["majority_class"].values,
            np.array([[0, 2], [1, 2]], dtype=np.int16),
        )
    finally:
        cached.close()


def test_plot_phase37_global_figure_writes_png(tmp_path: Path) -> None:
    output_path = tmp_path / "phase3_7_global.png"

    written = plot_phase37_global_figure(
        _sample_phase37_plot_dataset(),
        output_path=output_path,
    )

    assert written == output_path
    assert output_path.is_file()


def test_plot_phase3_7_script_writes_png_from_phase36_files(tmp_path: Path) -> None:
    module = _load_script_module()
    input_dir = tmp_path / "phase3.6"
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "figures"
    input_dir.mkdir(parents=True, exist_ok=True)
    _sample_phase36_metrics().to_netcdf(input_dir / "phase3_6_entropy_global_500m_2016.nc")
    _sample_phase36_classes().to_netcdf(
        input_dir / "phase3_6_unified_classes_global_500m_2016.nc"
    )

    exit_code = module.main(
        [
            "--input-dir",
            str(input_dir),
            "--cache-dir",
            str(cache_dir),
            "--output-dir",
            str(output_dir),
            "--sample-step",
            "2",
            "--source-lat-chunk-size",
            "3",
            "--dpi",
            "300",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "phase3_7_global_overview_global_500m_2016_sample2.png").is_file()
    assert (cache_dir / "phase3_7_global_plot_cache_global_500m_2016_sample2.nc").is_file()
