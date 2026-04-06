from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import xarray as xr

import WA.comparison.phase36 as phase36_module
from WA.classification import source_class_ids_by_unified_id, unified_priority_order
from WA.comparison.phase36 import (
    INVALID_CLASS_VALUE,
    aggregate_source_fractions_to_unified,
    build_joint_dominant_class_dataset,
    compute_dominant_class,
    compute_gwd30_annual_dominant_class,
    compute_joint_valid_mask,
    compute_source_dominant_class,
    compute_source_dominant_class_from_fractions,
    compute_valid_mask,
    compute_vote_entropy,
    run_phase36_analysis,
)


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_phase3_6_global_entropy.py"
    spec = importlib.util.spec_from_file_location("run_phase3_6_global_entropy", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _static_dataset(
    values_by_class: dict[int, np.ndarray],
    *,
    lat: list[float] | None = None,
    lon: list[float] | None = None,
) -> xr.Dataset:
    first_values = np.asarray(next(iter(values_by_class.values())), dtype=np.float32)
    lat = lat or [1.5 - index for index in range(first_values.shape[0])]
    lon = lon or [100.5 + index for index in range(first_values.shape[1])]
    data_vars = {
        f"frac_{class_id}": xr.DataArray(
            np.asarray(values, dtype=np.float32),
            dims=("lat", "lon"),
            coords={"lat": lat, "lon": lon},
        )
        for class_id, values in values_by_class.items()
    }
    return xr.Dataset(data_vars)


def _gwd30_dataset(
    values_by_class: dict[int, np.ndarray],
    *,
    lat: list[float] | None = None,
    lon: list[float] | None = None,
) -> xr.Dataset:
    first_values = np.asarray(next(iter(values_by_class.values())), dtype=np.float32)
    lat = lat or [1.5 - index for index in range(first_values.shape[1])]
    lon = lon or [100.5 + index for index in range(first_values.shape[2])]
    time = ["2016-01-01", "2016-01-05"]
    data_vars = {
        f"frac_{class_id}": xr.DataArray(
            np.asarray(values, dtype=np.float32),
            dims=("time", "lat", "lon"),
            coords={"time": time, "lat": lat, "lon": lon},
        )
        for class_id, values in values_by_class.items()
    }
    return xr.Dataset(data_vars)


def _install_mock_phase36_gwd30_loader(
    monkeypatch,
    dataset: xr.Dataset,
) -> None:
    monkeypatch.setattr(
        phase36_module,
        "_load_phase36_gwd30",
        lambda *, standardized_dir, year, bbox, reference_grid: dataset.copy(deep=True),
    )


def _install_mock_phase36_gwd30_staged_loader(
    monkeypatch,
    dataset: xr.Dataset,
    *,
    staged_tiles: list[tuple[Path, tuple[float, float, float, float]]] | None = None,
) -> None:
    restored_tiles = staged_tiles or [(Path("tile_mock.nc"), (100.0, 1.0, 101.0, 2.0))]

    class _MockGWD30Loader:
        def merge_staged_time_fraction_tiles(
            self,
            *,
            staged_tiles,
            reference_grid,
            bbox,
            year,
            batch_size=100,
        ) -> xr.Dataset:
            assert staged_tiles == restored_tiles
            assert year == 2016
            return dataset.copy(deep=True)

    monkeypatch.setattr(
        phase36_module,
        "_load_phase36_gwd30_staged_tiles",
        lambda standardized_dir, *, year: restored_tiles,
    )
    monkeypatch.setattr(
        phase36_module,
        "get_loader",
        lambda dataset_id, dataset_config: _MockGWD30Loader(),
    )


def _install_mock_phase36_gwd30_cache_builder(
    monkeypatch,
    dataset: xr.Dataset,
    *,
    captured_worker_counts: list[int | None] | None = None,
) -> None:
    def fake_write_global_gwd30_phase36_caches(
        *,
        standardized_dir,
        valid_cache_path,
        dominant_cache_path,
        source_dominant_cache_path,
        reduced_tile_dir,
        grid_template,
        year,
        bbox,
        lat_chunk_size,
        gwd30_worker_count,
        prefer_cache,
    ) -> None:
        del standardized_dir, grid_template, year, bbox, lat_chunk_size, prefer_cache
        if captured_worker_counts is not None:
            captured_worker_counts.append(gwd30_worker_count)
        reduced_tile_dir.mkdir(parents=True, exist_ok=True)
        unified = aggregate_source_fractions_to_unified("gwd30", dataset)
        valid_mask = compute_valid_mask(unified)
        dominant = compute_gwd30_annual_dominant_class(unified, valid_mask=valid_mask)
        source_dominant = compute_source_dominant_class("gwd30", dataset)
        valid_cache_path.parent.mkdir(parents=True, exist_ok=True)
        dominant_cache_path.parent.mkdir(parents=True, exist_ok=True)
        source_dominant_cache_path.parent.mkdir(parents=True, exist_ok=True)
        xr.Dataset(
            {"valid_mask": valid_mask.astype(np.int8)},
            attrs={phase36_module.PHASE36_CACHE_VERSION_ATTR: phase36_module.PHASE36_CACHE_VERSION},
        ).to_netcdf(valid_cache_path)
        xr.Dataset(
            {"dominant_class": dominant.astype(np.int16)},
            attrs={phase36_module.PHASE36_CACHE_VERSION_ATTR: phase36_module.PHASE36_CACHE_VERSION},
        ).to_netcdf(dominant_cache_path)
        xr.Dataset(
            {"dominant_class": source_dominant.astype(np.int16)},
            attrs={phase36_module.PHASE36_CACHE_VERSION_ATTR: phase36_module.PHASE36_CACHE_VERSION},
        ).to_netcdf(source_dominant_cache_path)

    monkeypatch.setattr(
        phase36_module,
        "_write_global_gwd30_phase36_caches",
        fake_write_global_gwd30_phase36_caches,
    )


def test_source_class_ids_by_unified_id_uses_yaml_mapping() -> None:
    grouped = source_class_ids_by_unified_id("gwd30")

    assert grouped[1] == (1, 2, 3, 4, 5, 6, 14)
    assert grouped[7] == (7,)
    assert grouped[2] == (8,)


def test_aggregate_source_fractions_to_unified_for_static_dataset() -> None:
    dataset = _static_dataset(
        {
            0: [[0.2, 0.0], [0.1, np.nan]],
            10: [[0.3, 0.0], [0.0, np.nan]],
            20: [[0.0, 1.0], [0.0, np.nan]],
            30: [[0.5, 0.0], [0.9, np.nan]],
        }
    )

    unified = aggregate_source_fractions_to_unified("g2017", dataset)

    np.testing.assert_allclose(
        unified.sel(class_id=0).values,
        np.array([[0.2, 0.0], [0.1, np.nan]], dtype=np.float32),
        equal_nan=True,
    )
    np.testing.assert_allclose(
        unified.sel(class_id=6).values,
        np.array([[0.0, 1.0], [0.0, np.nan]], dtype=np.float32),
        equal_nan=True,
    )
    np.testing.assert_allclose(
        unified.sel(class_id=4).values,
        np.array([[0.5, 0.0], [0.9, np.nan]], dtype=np.float32),
        equal_nan=True,
    )


def test_aggregate_source_fractions_to_unified_time_averages_gwd30() -> None:
    dataset = _gwd30_dataset(
        {
            8: [
                [[0.7, np.nan], [0.2, 0.0]],
                [[0.5, np.nan], [0.4, 0.0]],
            ],
            9: [
                [[0.1, np.nan], [0.6, 0.0]],
                [[0.3, np.nan], [0.2, 0.0]],
            ],
            0: [
                [[0.2, np.nan], [0.2, 0.0]],
                [[0.2, np.nan], [0.4, 0.0]],
            ],
        }
    )

    unified = aggregate_source_fractions_to_unified("gwd30", dataset)

    np.testing.assert_allclose(
        unified.sel(class_id=2).values,
        np.array([[0.6, np.nan], [0.3, np.nan]], dtype=np.float32),
        equal_nan=True,
    )
    np.testing.assert_allclose(
        unified.sel(class_id=3).values,
        np.array([[0.2, np.nan], [0.4, np.nan]], dtype=np.float32),
        equal_nan=True,
    )


def test_joint_valid_requires_all_three_datasets() -> None:
    g2017 = xr.DataArray(
        np.array(
            [
                [[0.8, np.nan], [0.2, 0.0]],
                [[0.2, np.nan], [0.8, 0.0]],
            ],
            dtype=np.float32,
        ),
        dims=("class_id", "lat", "lon"),
        coords={"class_id": [0, 1], "lat": [1.5, 0.5], "lon": [100.5, 101.5]},
    )
    glwd = g2017.copy(deep=True)
    gwd30 = g2017.copy(deep=True)
    gwd30[:, 1, 1] = np.nan

    joint = compute_joint_valid_mask({"g2017": g2017, "glwd_v2": glwd, "gwd30": gwd30})

    np.testing.assert_array_equal(
        joint.values,
        np.array([[True, False], [True, False]]),
    )


def test_compute_dominant_class_uses_yaml_priority_order_for_ties() -> None:
    priority = unified_priority_order()
    assert priority[0] == 1

    fractions = xr.DataArray(
        np.array(
            [
                [[0.0]],
                [[0.5]],
                [[0.0]],
                [[0.0]],
                [[0.0]],
                [[0.0]],
                [[0.5]],
                [[0.0]],
            ],
            dtype=np.float32,
        ),
        dims=("class_id", "lat", "lon"),
        coords={"class_id": list(range(8)), "lat": [1.5], "lon": [100.5]},
    )

    dominant = compute_dominant_class(fractions)

    assert int(dominant.values[0, 0]) == 1


def test_compute_gwd30_annual_dominant_class_prefers_wetland_over_non_wetland_and_water() -> None:
    fractions = xr.DataArray(
        np.array(
            [
                [[0.70]],
                [[0.20]],
                [[0.00]],
                [[0.10]],
                [[0.00]],
                [[0.00]],
                [[0.00]],
                [[0.00]],
            ],
            dtype=np.float32,
        ),
        dims=("class_id", "lat", "lon"),
        coords={"class_id": list(range(8)), "lat": [1.5], "lon": [100.5]},
    )

    dominant = compute_gwd30_annual_dominant_class(fractions)

    assert int(dominant.values[0, 0]) == 3


def test_compute_gwd30_annual_dominant_class_falls_back_to_water_vs_non_wetland() -> None:
    fractions = xr.DataArray(
        np.array(
            [
                [[0.40]],
                [[0.60]],
                [[0.00]],
                [[0.00]],
                [[0.00]],
                [[0.00]],
                [[0.00]],
                [[0.00]],
            ],
            dtype=np.float32,
        ),
        dims=("class_id", "lat", "lon"),
        coords={"class_id": list(range(8)), "lat": [1.5], "lon": [100.5]},
    )

    dominant = compute_gwd30_annual_dominant_class(fractions)

    assert int(dominant.values[0, 0]) == 1


def test_gwd30_source_dominant_prefers_wetland_over_water_and_non_wetland() -> None:
    dataset = _gwd30_dataset(
        {
            0: [
                [[0.70]],
                [[0.70]],
            ],
            1: [
                [[0.20]],
                [[0.20]],
            ],
            8: [
                [[0.10]],
                [[0.10]],
            ],
        }
    )

    dominant = compute_source_dominant_class("gwd30", dataset)

    assert int(dominant.values[0, 0]) == 8


def test_gwd30_source_dominant_from_fractions_prefers_water_over_non_wetland() -> None:
    fractions = xr.DataArray(
        np.array(
            [
                [[0.70]],
                [[0.30]],
                [[0.00]],
            ],
            dtype=np.float32,
        ),
        dims=("source_class_id", "lat", "lon"),
        coords={"source_class_id": [0, 1, 8], "lat": [1.5], "lon": [100.5]},
    )

    dominant = compute_source_dominant_class_from_fractions("gwd30", fractions)

    assert int(dominant.values[0, 0]) == 1


def test_compute_vote_entropy_zero_when_all_three_agree() -> None:
    joint_valid = xr.DataArray(
        np.array([[True]], dtype=bool),
        dims=("lat", "lon"),
        coords={"lat": [1.5], "lon": [100.5]},
    )
    dominant = xr.DataArray(
        np.array([[2]], dtype=np.int16),
        dims=("lat", "lon"),
        coords=joint_valid.coords,
    )

    result = compute_vote_entropy(
        {"g2017": dominant, "glwd_v2": dominant, "gwd30": dominant},
        joint_valid_mask=joint_valid,
    )

    np.testing.assert_allclose(result["entropy"].values, [[0.0]], atol=1e-6)
    np.testing.assert_array_equal(result["agreement_count"].values, [[3]])


def test_compute_vote_entropy_one_when_all_three_disagree() -> None:
    joint_valid = xr.DataArray(
        np.array([[True]], dtype=bool),
        dims=("lat", "lon"),
        coords={"lat": [1.5], "lon": [100.5]},
    )
    g2017 = xr.DataArray(
        np.array([[0]], dtype=np.int16),
        dims=("lat", "lon"),
        coords=joint_valid.coords,
    )
    glwd_v2 = xr.DataArray(
        np.array([[1]], dtype=np.int16),
        dims=("lat", "lon"),
        coords=joint_valid.coords,
    )
    gwd30 = xr.DataArray(
        np.array([[2]], dtype=np.int16),
        dims=("lat", "lon"),
        coords=joint_valid.coords,
    )
    result = compute_vote_entropy(
        {"g2017": g2017, "glwd_v2": glwd_v2, "gwd30": gwd30},
        joint_valid_mask=joint_valid,
    )

    np.testing.assert_allclose(result["entropy"].values, [[1.0]], atol=1e-6)
    np.testing.assert_array_equal(result["agreement_count"].values, [[1]])


def test_compute_vote_entropy_partial_when_two_agree() -> None:
    joint_valid = xr.DataArray(
        np.array([[True]], dtype=bool),
        dims=("lat", "lon"),
        coords={"lat": [1.5], "lon": [100.5]},
    )
    g2017 = xr.DataArray(
        np.array([[4]], dtype=np.int16),
        dims=("lat", "lon"),
        coords=joint_valid.coords,
    )
    glwd_v2 = xr.DataArray(
        np.array([[4]], dtype=np.int16),
        dims=("lat", "lon"),
        coords=joint_valid.coords,
    )
    gwd30 = xr.DataArray(
        np.array([[6]], dtype=np.int16),
        dims=("lat", "lon"),
        coords=joint_valid.coords,
    )
    result = compute_vote_entropy(
        {"g2017": g2017, "glwd_v2": glwd_v2, "gwd30": gwd30},
        joint_valid_mask=joint_valid,
    )

    value = float(result["entropy"].values[0, 0])
    assert 0.0 < value < 1.0
    np.testing.assert_array_equal(result["agreement_count"].values, [[2]])


def test_compute_vote_entropy_non_joint_valid_becomes_nan() -> None:
    joint_valid = xr.DataArray(
        np.array([[False]], dtype=bool),
        dims=("lat", "lon"),
        coords={"lat": [1.5], "lon": [100.5]},
    )
    dominant = xr.DataArray(
        np.array([[2]], dtype=np.int16),
        dims=("lat", "lon"),
        coords=joint_valid.coords,
    )

    result = compute_vote_entropy(
        {"g2017": dominant, "glwd_v2": dominant, "gwd30": dominant},
        joint_valid_mask=joint_valid,
    )

    assert np.isnan(result["entropy"].values[0, 0])
    assert int(result["majority_class"].values[0, 0]) == INVALID_CLASS_VALUE


def test_build_joint_dominant_class_dataset_masks_non_joint_cells() -> None:
    joint_valid = xr.DataArray(
        np.array([[True, False]], dtype=bool),
        dims=("lat", "lon"),
        coords={"lat": [1.5], "lon": [100.5, 101.5]},
    )
    dominant_classes = {
        dataset_id: xr.DataArray(
            np.array([[2, 3]], dtype=np.int16),
            dims=("lat", "lon"),
            coords=joint_valid.coords,
        )
        for dataset_id in ("g2017", "glwd_v2", "gwd30")
    }
    source_dominant_classes = {
        dataset_id: xr.DataArray(
            np.array([[20, 30]], dtype=np.int16),
            dims=("lat", "lon"),
            coords=joint_valid.coords,
        )
        for dataset_id in ("g2017", "glwd_v2", "gwd30")
    }

    dataset = build_joint_dominant_class_dataset(
        dominant_classes,
        joint_valid_mask=joint_valid,
        source_dominant_classes=source_dominant_classes,
    )

    assert int(dataset["g2017_dominant_class"].values[0, 1]) == INVALID_CLASS_VALUE
    assert int(dataset["g2017_source_dominant_class"].values[0, 1]) == INVALID_CLASS_VALUE


def test_load_phase36_inputs_uses_staged_gwd30_tile_merge(
    monkeypatch,
    tmp_path: Path,
) -> None:
    standardized_dir = tmp_path / "standardized"
    standardized_dir.mkdir()
    _static_dataset({0: [[1.0]]}).to_netcdf(standardized_dir / "g2017.nc")
    _static_dataset({0: [[1.0]]}).to_netcdf(standardized_dir / "glwd_v2.nc")
    _install_mock_phase36_gwd30_staged_loader(
        monkeypatch,
        _gwd30_dataset({0: [[[1.0]], [[1.0]]]}),
    )

    inputs = phase36_module.load_phase36_inputs(standardized_dir, year=2016)
    try:
        assert set(inputs.datasets) == {"g2017", "glwd_v2", "gwd30"}
        assert "frac_0" in inputs.datasets["gwd30"].data_vars
    finally:
        for dataset in inputs.datasets.values():
            dataset.close()


def test_run_phase36_analysis_writes_outputs_and_summary(
    monkeypatch,
    tmp_path: Path,
) -> None:
    standardized_dir = tmp_path / "standardized"
    output_dir = tmp_path / "out"
    cache_dir = tmp_path / "cache"
    standardized_dir.mkdir()

    _static_dataset(
        {
            0: [[0.8, 0.1], [0.0, 0.6]],
            20: [[0.2, 0.9], [1.0, 0.4]],
        }
    ).to_netcdf(standardized_dir / "g2017.nc")
    _static_dataset(
        {
            0: [[0.7, 0.0], [0.0, 0.0]],
            9: [[0.3, 1.0], [1.0, 1.0]],
        }
    ).to_netcdf(standardized_dir / "glwd_v2.nc")
    _install_mock_phase36_gwd30_cache_builder(
        monkeypatch,
        _gwd30_dataset(
            {
                0: [
                    [[0.6, 0.0], [0.0, np.nan]],
                    [[0.6, 0.0], [0.0, np.nan]],
                ],
                8: [
                    [[0.4, 1.0], [1.0, np.nan]],
                    [[0.4, 1.0], [1.0, np.nan]],
                ],
            }
        ),
    )

    outputs = run_phase36_analysis(
        standardized_dir=standardized_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        year=2016,
        lat_chunk_size=1,
    )

    assert outputs.metrics_path.is_file()
    assert outputs.dominant_classes_path.is_file()
    assert outputs.summary_path.is_file()

    metrics = xr.open_dataset(outputs.metrics_path)
    try:
        assert set(metrics.data_vars) == {
            "entropy",
            "majority_class",
            "agreement_count",
            "joint_valid_mask",
        }
        np.testing.assert_array_equal(
            metrics["joint_valid_mask"].values,
            np.array([[1, 1], [1, 0]], dtype=np.int8),
        )
    finally:
        metrics.close()

    dominant = xr.open_dataset(outputs.dominant_classes_path)
    try:
        assert {
            "g2017_dominant_class",
            "glwd_v2_dominant_class",
            "gwd30_dominant_class",
            "g2017_source_dominant_class",
            "glwd_v2_source_dominant_class",
            "gwd30_source_dominant_class",
        }.issubset(set(dominant.data_vars))
    finally:
        dominant.close()

    summary = json.loads(outputs.summary_path.read_text(encoding="utf-8"))
    assert summary["phase"] == "phase3.6"
    assert summary["target_year"] == 2016
    assert summary["joint_valid_cell_count"] == 3


def test_run_phase36_analysis_reuses_global_cache_without_sources(
    monkeypatch,
    tmp_path: Path,
) -> None:
    standardized_dir = tmp_path / "standardized"
    output_dir = tmp_path / "out"
    cache_dir = tmp_path / "cache"
    standardized_dir.mkdir()

    _static_dataset(
        {
            0: [[0.8, 0.1], [0.0, 0.6]],
            20: [[0.2, 0.9], [1.0, 0.4]],
        }
    ).to_netcdf(standardized_dir / "g2017.nc")
    _static_dataset(
        {
            0: [[0.7, 0.0], [0.0, 0.0]],
            9: [[0.3, 1.0], [1.0, 1.0]],
        }
    ).to_netcdf(standardized_dir / "glwd_v2.nc")
    _install_mock_phase36_gwd30_cache_builder(
        monkeypatch,
        _gwd30_dataset(
            {
                0: [
                    [[0.6, 0.0], [0.0, np.nan]],
                    [[0.6, 0.0], [0.0, np.nan]],
                ],
                8: [
                    [[0.4, 1.0], [1.0, np.nan]],
                    [[0.4, 1.0], [1.0, np.nan]],
                ],
            }
        ),
    )

    outputs = run_phase36_analysis(
        standardized_dir=standardized_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        year=2016,
        lat_chunk_size=1,
    )

    cache_run_dir = cache_dir / "global_500m_2016" / "lat_chunk_1"
    assert (cache_run_dir / "00_grid_template.nc").is_file()
    assert (cache_run_dir / "01_g2017_unified_fraction.nc").is_file()
    assert (cache_run_dir / "01_g2017_source_dominant_class.nc").is_file()
    assert (cache_run_dir / "01_glwd_v2_unified_fraction.nc").is_file()
    assert (cache_run_dir / "01_glwd_v2_source_dominant_class.nc").is_file()
    assert (cache_run_dir / "01_gwd30_valid_mask.nc").is_file()
    assert (cache_run_dir / "01_gwd30_dominant_class.nc").is_file()
    assert (cache_run_dir / "01_gwd30_source_dominant_class.nc").is_file()
    assert (cache_run_dir / "02_joint_valid_mask.nc").is_file()
    assert (cache_run_dir / "03_dominant_classes.nc").is_file()
    assert (cache_run_dir / "04_metrics.nc").is_file()
    assert (cache_run_dir / "05_summary.json").is_file()

    outputs.metrics_path.unlink()
    outputs.dominant_classes_path.unlink()
    outputs.summary_path.unlink()
    shutil.rmtree(standardized_dir)

    rerun_outputs = run_phase36_analysis(
        standardized_dir=standardized_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        year=2016,
        lat_chunk_size=1,
    )

    assert rerun_outputs.metrics_path.is_file()
    assert rerun_outputs.dominant_classes_path.is_file()
    assert rerun_outputs.summary_path.is_file()

    metrics = xr.open_dataset(rerun_outputs.metrics_path)
    try:
        np.testing.assert_array_equal(
            metrics["joint_valid_mask"].values,
            np.array([[1, 1], [1, 0]], dtype=np.int8),
        )
    finally:
        metrics.close()


def test_phase36_script_dry_run_reports_grid_and_exits(
    monkeypatch,
    tmp_path: Path,
) -> None:
    standardized_dir = tmp_path / "standardized"
    standardized_dir.mkdir()
    _static_dataset({0: [[1.0]]}).to_netcdf(standardized_dir / "g2017.nc")
    _static_dataset({0: [[1.0]]}).to_netcdf(standardized_dir / "glwd_v2.nc")
    _install_mock_phase36_gwd30_loader(
        monkeypatch,
        _gwd30_dataset({0: [[[1.0]], [[1.0]]]}),
    )

    module = _load_script_module()
    monkeypatch.setattr(module, "load_phase36_inputs", phase36_module.load_phase36_inputs)
    exit_code = module.main(
        [
            "--standardized-dir",
            str(standardized_dir),
            "--dry-run",
        ]
    )

    assert exit_code == 0


def test_run_phase36_analysis_passes_gwd30_worker_count_to_cache_builder(
    monkeypatch,
    tmp_path: Path,
) -> None:
    standardized_dir = tmp_path / "standardized"
    output_dir = tmp_path / "out"
    cache_dir = tmp_path / "cache"
    standardized_dir.mkdir()
    _static_dataset({10: [[1.0]]}).to_netcdf(standardized_dir / "g2017.nc")
    _static_dataset({1: [[1.0]]}).to_netcdf(standardized_dir / "glwd_v2.nc")
    captured: list[int | None] = []
    _install_mock_phase36_gwd30_cache_builder(
        monkeypatch,
        _gwd30_dataset({1: [[[1.0]], [[1.0]]]}),
        captured_worker_counts=captured,
    )

    run_phase36_analysis(
        standardized_dir=standardized_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        year=2016,
        lat_chunk_size=1,
        gwd30_worker_count=8,
    )

    assert captured == [8]


def test_run_phase36_analysis_parallelizes_static_cache_builds(
    monkeypatch,
    tmp_path: Path,
) -> None:
    standardized_dir = tmp_path / "standardized"
    output_dir = tmp_path / "out"
    cache_dir = tmp_path / "cache"
    standardized_dir.mkdir()
    _static_dataset({10: [[1.0]]}).to_netcdf(standardized_dir / "g2017.nc")
    _static_dataset({1: [[1.0]]}).to_netcdf(standardized_dir / "glwd_v2.nc")
    _install_mock_phase36_gwd30_cache_builder(
        monkeypatch,
        _gwd30_dataset({1: [[[1.0]], [[1.0]]]}),
    )

    real_serial_helper = phase36_module._write_global_static_phase36_caches_from_standardized
    captured: dict[str, object] = {}

    def fake_parallel_helper(**kwargs):
        captured["dataset_ids"] = kwargs["dataset_ids"]
        captured["worker_count"] = kwargs["worker_count"]
        for dataset_id in kwargs["dataset_ids"]:
            real_serial_helper(
                standardized_dir=kwargs["standardized_dir"],
                dataset_id=dataset_id,
                cache_path=kwargs["unified_cache_paths"][dataset_id],
                source_dominant_cache_path=kwargs["source_dominant_cache_paths"][dataset_id],
                grid_template=kwargs["grid_template"],
                year=kwargs["year"],
                bbox=kwargs["bbox"],
                lat_chunk_size=kwargs["lat_chunk_size"],
            )

    monkeypatch.setattr(
        phase36_module,
        "_write_global_static_phase36_caches_parallel",
        fake_parallel_helper,
    )

    outputs = run_phase36_analysis(
        standardized_dir=standardized_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        year=2016,
        lat_chunk_size=1,
        static_worker_count=2,
    )

    assert outputs.metrics_path.is_file()
    assert captured["worker_count"] == 2
    assert set(captured["dataset_ids"]) == {"g2017", "glwd_v2"}


def test_run_phase36_analysis_static_parallel_falls_back_to_serial(
    monkeypatch,
    tmp_path: Path,
) -> None:
    standardized_dir = tmp_path / "standardized"
    output_dir = tmp_path / "out"
    cache_dir = tmp_path / "cache"
    standardized_dir.mkdir()
    _static_dataset({10: [[1.0]]}).to_netcdf(standardized_dir / "g2017.nc")
    _static_dataset({1: [[1.0]]}).to_netcdf(standardized_dir / "glwd_v2.nc")
    _install_mock_phase36_gwd30_cache_builder(
        monkeypatch,
        _gwd30_dataset({1: [[[1.0]], [[1.0]]]}),
    )

    real_helper = phase36_module._write_global_static_phase36_caches_from_standardized
    executed: list[str] = []

    def recording_helper(**kwargs):
        executed.append(kwargs["dataset_id"])
        return real_helper(**kwargs)

    monkeypatch.setattr(
        phase36_module,
        "_write_global_static_phase36_caches_from_standardized",
        recording_helper,
    )
    monkeypatch.setattr(
        phase36_module,
        "_write_global_static_phase36_caches_parallel",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic static executor failure")),
    )

    outputs = run_phase36_analysis(
        standardized_dir=standardized_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        year=2016,
        lat_chunk_size=1,
        static_worker_count=2,
    )

    assert outputs.metrics_path.is_file()
    assert executed == ["g2017", "glwd_v2"]


def test_phase36_script_passes_worker_counts_to_analysis(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module()
    captured: dict[str, object] = {}

    def fake_run_phase36_analysis(**kwargs):
        captured.update(kwargs)
        return phase36_module.Phase36OutputPaths(
            metrics_path=tmp_path / "metrics.nc",
            dominant_classes_path=tmp_path / "classes.nc",
            summary_path=tmp_path / "summary.json",
        )

    monkeypatch.setattr(module, "run_phase36_analysis", fake_run_phase36_analysis)

    exit_code = module.main(
        [
            "--standardized-dir",
            str(tmp_path / "standardized"),
            "--output-dir",
            str(tmp_path / "out"),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--year",
            "2016",
            "--lat-chunk-size",
            "256",
            "--static-worker-count",
            "2",
            "--gwd30-worker-count",
            "8",
        ]
    )

    assert exit_code == 0
    assert captured["lat_chunk_size"] == 256
    assert captured["static_worker_count"] == 2
    assert captured["gwd30_worker_count"] == 8
