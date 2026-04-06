from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import xarray as xr

from WA.comparison.phase26 import (
    EXPECTED_COARSE_CACHE_VERSION,
    apply_landmask_to_surfaces,
    build_phase26_stack,
    coarse_cache_path,
    compute_phase26_metrics,
    load_cached_coarse_surfaces,
    select_std_surfaces,
)


def _surface(values: np.ndarray) -> xr.DataArray:
    data = xr.DataArray(
        np.asarray(values, dtype=np.float32),
        dims=("lat", "lon"),
        coords={
            "lat": np.array([10.0, 0.0], dtype=np.float32),
            "lon": np.array([100.0, 110.0], dtype=np.float32),
        },
        name="wetland_fraction",
    )
    data.attrs["wa_stage_cache_version"] = EXPECTED_COARSE_CACHE_VERSION
    data.coords["spatial_ref"] = xr.DataArray(0)
    return data


def _write_cache(
    cache_root: Path,
    dataset_id: str,
    *,
    region_id: str = "global_tropical_subtropical_35",
    target_year: int | None,
    resolution_deg: float = 0.25,
    values: np.ndarray,
    version: int | None = EXPECTED_COARSE_CACHE_VERSION,
) -> None:
    path = coarse_cache_path(
        cache_root,
        dataset_id,
        region_id,
        target_year=target_year,
        resolution_deg=resolution_deg,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    surface = _surface(values)
    if version is None:
        surface.attrs.pop("wa_stage_cache_version", None)
    else:
        surface.attrs["wa_stage_cache_version"] = version
    surface.to_netcdf(path)


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_phase2_6_analysis.py"
    spec = importlib.util.spec_from_file_location("run_phase2_6_analysis", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_cached_coarse_surfaces_uses_expected_cache_layout(tmp_path: Path) -> None:
    _write_cache(
        tmp_path,
        "g2017",
        target_year=None,
        values=np.array([[0.8, 0.2], [0.1, 0.4]], dtype=np.float32),
    )
    _write_cache(
        tmp_path,
        "berkeley_rwawc",
        target_year=2019,
        values=np.array([[0.6, 0.6], [0.3, 0.2]], dtype=np.float32),
    )
    _write_cache(
        tmp_path,
        "swamps",
        target_year=2016,
        values=np.array([[0.7, 0.5], [0.2, 0.9]], dtype=np.float32),
    )

    result = load_cached_coarse_surfaces(
        tmp_path,
        dataset_ids=["g2017", "berkeley_rwawc", "swamps"],
        default_year=2016,
        resolution_deg=0.25,
    )

    assert sorted(result.surfaces) == ["berkeley_rwawc", "g2017", "swamps"]
    assert result.skipped == {}
    assert result.cache_paths["berkeley_rwawc"].as_posix().endswith(
        "berkeley_rwawc/year_2019/res_0p25/05_coarse_surface.nc"
    )


def test_load_cached_coarse_surfaces_skips_stale_cache(tmp_path: Path) -> None:
    _write_cache(
        tmp_path,
        "g2017",
        target_year=None,
        values=np.array([[0.5, 0.2], [0.1, 0.9]], dtype=np.float32),
        version=None,
    )

    result = load_cached_coarse_surfaces(
        tmp_path,
        dataset_ids=["g2017"],
        default_year=2016,
        resolution_deg=0.25,
    )

    assert result.surfaces == {}
    assert "g2017" in result.skipped
    assert "stale cache" in result.skipped["g2017"]


def test_compute_phase26_metrics_produces_mean_vote_and_std() -> None:
    surfaces = {
        "a": _surface(np.array([[0.8, 0.2], [np.nan, 0.7]], dtype=np.float32)),
        "b": _surface(np.array([[0.9, 0.8], [np.nan, 0.4]], dtype=np.float32)),
        "c": _surface(np.array([[0.1, 0.6], [0.3, np.nan]], dtype=np.float32)),
    }

    stack = build_phase26_stack(surfaces)
    metrics = compute_phase26_metrics(surfaces, min_participants=2)

    assert list(stack.coords["dataset"].values) == ["a", "b", "c"]
    np.testing.assert_allclose(
        metrics["mean_wetland_fraction"].values,
        np.array([[0.6, 0.53333336], [0.3, 0.55]], dtype=np.float32),
        rtol=1e-6,
    )
    np.testing.assert_allclose(
        metrics["participant_count"].values,
        np.array([[3, 3], [1, 2]], dtype=np.int16),
    )

    expected_std = np.array(
        [
            [0.3559026, 0.24944383],
            [np.nan, 0.15],
        ],
        dtype=np.float32,
    )
    np.testing.assert_allclose(
        metrics["std_wetland_fraction"].values,
        expected_std,
        rtol=1e-6,
        equal_nan=True,
    )


def test_select_std_surfaces_excludes_berkeley_g2017_glwd() -> None:
    surfaces = {
        "berkeley_rwawc": _surface(np.array([[0.8, 0.8], [0.8, 0.8]], dtype=np.float32)),
        "g2017": _surface(np.array([[0.6, 0.6], [0.6, 0.6]], dtype=np.float32)),
        "glwd_v2": _surface(np.array([[0.5, 0.5], [0.5, 0.5]], dtype=np.float32)),
        "giems_mc": _surface(np.array([[0.3, 0.3], [0.3, 0.3]], dtype=np.float32)),
        "swamps": _surface(np.array([[0.2, 0.2], [0.2, 0.2]], dtype=np.float32)),
    }

    selected = select_std_surfaces(surfaces)

    assert sorted(selected) == ["giems_mc", "swamps"]


def test_compute_phase26_metrics_excludes_berkeley_g2017_glwd_from_std_only() -> None:
    surfaces = {
        "berkeley_rwawc": _surface(np.ones((2, 2), dtype=np.float32)),
        "g2017": _surface(np.ones((2, 2), dtype=np.float32)),
        "glwd_v2": _surface(np.ones((2, 2), dtype=np.float32)),
        "giems_mc": _surface(np.zeros((2, 2), dtype=np.float32)),
        "swamps": _surface(np.ones((2, 2), dtype=np.float32)),
    }

    metrics = compute_phase26_metrics(surfaces, min_participants=2)

    np.testing.assert_allclose(
        metrics["mean_wetland_fraction"].values,
        np.full((2, 2), 0.8, dtype=np.float32),
        rtol=1e-6,
    )
    np.testing.assert_allclose(
        metrics["participant_count"].values,
        np.full((2, 2), 2, dtype=np.int16),
    )
    np.testing.assert_allclose(
        metrics["std_wetland_fraction"].values,
        np.full((2, 2), 0.5, dtype=np.float32),
        rtol=1e-6,
    )
    assert metrics.attrs["std_dataset_count"] == 2


def test_apply_landmask_to_surfaces_uses_glwd_valid_extent() -> None:
    surfaces = {
        "glwd_v2": _surface(np.array([[0.0, np.nan], [0.2, 0.1]], dtype=np.float32)),
        "swamps": _surface(np.array([[0.7, 0.9], [0.4, 0.3]], dtype=np.float32)),
    }

    masked = apply_landmask_to_surfaces(surfaces)

    np.testing.assert_allclose(
        masked["swamps"].values,
        np.array([[0.7, np.nan], [0.4, 0.3]], dtype=np.float32),
        equal_nan=True,
    )
    assert masked["swamps"].attrs["landmask_dataset_id"] == "glwd_v2"


def test_phase2_6_script_writes_stack_and_metrics_outputs(tmp_path: Path) -> None:
    module = _load_script_module()
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "out"

    _write_cache(
        cache_dir,
        "g2017",
        target_year=None,
        values=np.array([[0.8, 0.2], [0.1, 0.4]], dtype=np.float32),
    )
    _write_cache(
        cache_dir,
        "glwd_v2",
        target_year=None,
        values=np.array([[0.0, np.nan], [0.2, 0.1]], dtype=np.float32),
    )
    _write_cache(
        cache_dir,
        "swamps",
        target_year=2016,
        values=np.array([[0.6, 0.7], [0.2, 0.5]], dtype=np.float32),
    )
    _write_cache(
        cache_dir,
        "giems_mc",
        target_year=2016,
        values=np.array([[0.4, 0.3], [0.1, 0.2]], dtype=np.float32),
    )

    exit_code = module.main(
        [
            "--cache-dir",
            str(cache_dir),
            "--output-dir",
            str(output_dir),
            "--datasets",
            "g2017",
            "glwd_v2",
            "swamps",
            "giems_mc",
        ]
    )

    assert exit_code == 0

    stack_path = output_dir / "phase2_6_stack_global_tropical_subtropical_35_0p25deg.nc"
    metrics_path = output_dir / "phase2_6_metrics_global_tropical_subtropical_35_0p25deg.nc"
    assert stack_path.is_file()
    assert metrics_path.is_file()

    metrics = xr.open_dataset(metrics_path)
    try:
        assert set(metrics.data_vars) == {
            "mean_wetland_fraction",
            "std_wetland_fraction",
            "participant_count",
        }
        assert metrics.attrs["landmask_dataset_id"] == "glwd_v2"
        assert metrics.attrs["std_dataset_count"] == 2
        assert np.isnan(metrics["mean_wetland_fraction"].values[0, 1])
        assert metrics["participant_count"].values[0, 1] == 0
    finally:
        metrics.close()
