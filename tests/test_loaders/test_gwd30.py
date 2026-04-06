from __future__ import annotations

import os
import time
from collections.abc import Callable
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from pytest import MonkeyPatch
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

from tests.test_loaders.conftest import with_common_fields, write_multiband_geotiff
from WA.comparison.harmonize import create_comparison_grid
from WA.loaders import get_loader
from WA.loaders import gwd30 as gwd30_module
from WA.loaders.gwd30 import GWD30Loader
from WA.utils import progress as progress_utils


def test_gwd30_loader_filters_tiles_and_reconstructs_four_day_timestamps(tmp_path: Path) -> None:
    base_path = tmp_path / "gwd30"
    band_count = 92
    tile_a = np.ones((band_count, 2, 2), dtype=np.uint8)
    tile_b = np.full((band_count, 2, 2), 2, dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_a_wetland_2013.tif",
        tile_a,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )
    write_multiband_geotiff(
        base_path / "2013/tile_b_wetland_2013.tif",
        tile_b,
        transform=from_origin(2.0, 2.0, 1.0, 1.0),
    )

    loader = get_loader(
        "gwd30",
        with_common_fields(
            base_path,
            loader_type="gwd30",
            years=[2013],
            pattern="{year}/*_wetland_{year}.tif",
        ),
    )

    result = loader.load(bbox=(0.0, 0.0, 1.9, 2.0), time_range=("2013-01-01", "2013-01-31"))

    assert list(result.data_vars) == ["wetland_class"]
    assert result.sizes["time"] == 8
    assert result["wetland_class"].max().item() == 1
    assert str(result.time.values[1])[:10] == "2013-01-05"


def test_gwd30_loader_filters_projected_tiles_by_lon_lat_bbox(tmp_path: Path) -> None:
    base_path = tmp_path / "gwd30"
    band_count = 92
    tile = np.full((band_count, 2, 2), 3, dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_utm_wetland_2013.tif",
        tile,
        crs="EPSG:32631",
        transform=from_origin(500000.0, 60.0, 30.0, 30.0),
    )

    loader = get_loader(
        "gwd30",
        with_common_fields(
            base_path,
            loader_type="gwd30",
            years=[2013],
            pattern="{year}/*_wetland_{year}.tif",
        ),
    )

    bbox = transform_bounds(
        "EPSG:32631",
        "EPSG:4326",
        500000.0,
        0.0,
        500060.0,
        60.0,
        densify_pts=21,
    )
    result = loader.load(bbox=bbox, time_range=("2013-01-01", "2013-01-31"))

    assert result.sizes["time"] == 8
    assert result["wetland_class"].max().item() == 3


def test_gwd30_loader_time_range_selects_only_requested_band_window(tmp_path: Path) -> None:
    base_path = tmp_path / "gwd30"
    band_count = 92
    tile = np.arange(1, band_count + 1, dtype=np.uint8).reshape(band_count, 1, 1)
    tile = np.broadcast_to(tile, (band_count, 2, 2)).copy()

    write_multiband_geotiff(
        base_path / "2013/tile_wetland_2013.tif",
        tile,
        transform=from_origin(0.0, 1.0, 1.0, 1.0),
    )

    loader = get_loader(
        "gwd30",
        with_common_fields(
            base_path,
            loader_type="gwd30",
            years=[2013],
            pattern="{year}/*_wetland_{year}.tif",
        ),
    )

    result = loader.load(bbox=(0.0, 0.0, 1.0, 1.0), time_range=("2013-02-01", "2013-02-28"))

    assert result.sizes["time"] == 7
    assert str(result.time.values[0])[:10] == "2013-02-02"
    assert str(result.time.values[-1])[:10] == "2013-02-26"
    assert result["wetland_class"].values[:, 0, 0].tolist() == [9, 10, 11, 12, 13, 14, 15]


def test_gwd30_load_fine_classification_grid_returns_dominant_classes_and_fractions(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "gwd30"
    band_count = 4
    tile = np.full((band_count, 2, 2), 8, dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wetland_2013.tif",
        tile,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 2.0, 2.0), resolution_deg=1.0)
    result = loader.load_fine_classification_grid(
        bbox=(0.0, 0.0, 2.0, 2.0),
        reference_grid=reference_grid,
        year=2013,
        worker_count=1,
    )

    assert set(result.data_vars) == {"wetland_class", "class_fractions"}
    assert np.allclose(result["wetland_class"].values, 8.0, equal_nan=False)
    wetland_fraction = result["class_fractions"].sel(class_id=8)
    assert np.allclose(wetland_fraction.values, 1.0, equal_nan=False)


def test_gwd30_load_time_fraction_grid_returns_time_resolved_fractions(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "gwd30"
    band_count = 4
    tile = np.full((band_count, 2, 2), 8, dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wetland_2013.tif",
        tile,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 2.0, 2.0), resolution_deg=1.0)
    result = loader.load_time_fraction_grid(
        bbox=(0.0, 0.0, 2.0, 2.0),
        reference_grid=reference_grid,
        year=2013,
        worker_count=1,
        show_progress=False,
    )

    assert result.sizes["time"] == band_count
    assert len(result.data_vars) == 15
    assert np.allclose(result["frac_8"].values, 1.0, equal_nan=False)
    assert np.allclose(result["frac_0"].values, 0.0, equal_nan=False)
    assert result.attrs["source"] == "low_memory_time_fraction_grid"


def test_gwd30_load_time_fraction_grid_logs_progress_when_progress_bar_disabled(
    tmp_path: Path,
    caplog,
) -> None:
    base_path = tmp_path / "gwd30"
    tile = np.full((2, 2, 2), 8, dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wetland_2013.tif",
        tile,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 2.0, 2.0), resolution_deg=1.0)
    caplog.set_level("INFO", logger="WA.loaders.gwd30")

    loader.load_time_fraction_grid(
        bbox=(0.0, 0.0, 2.0, 2.0),
        reference_grid=reference_grid,
        year=2013,
        worker_count=1,
        show_progress=False,
    )

    assert "matched 1 tile(s)" in caplog.text
    assert "reading tile 1/1 | tile_wetland_2013.tif" in caplog.text


def test_gwd30_stage_and_merge_time_fraction_tiles(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "gwd30"
    tile_wet = np.full((2, 2, 2), 8, dtype=np.uint8)
    tile_dry = np.zeros((2, 2, 2), dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wet_wetland_2013.tif",
        tile_wet,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )
    write_multiband_geotiff(
        base_path / "2013/tile_dry_wetland_2013.tif",
        tile_dry,
        transform=from_origin(2.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 4.0, 2.0), resolution_deg=1.0)
    stage_dir = tmp_path / "staged_tiles"
    staged_tiles = loader.stage_time_fraction_tiles(
        bbox=(0.0, 0.0, 4.0, 2.0),
        reference_grid=reference_grid,
        year=2013,
        staging_dir=stage_dir,
        worker_count=1,
        show_progress=False,
    )

    assert len(staged_tiles) == 2
    assert len(list(stage_dir.glob("tile_*.nc"))) == 2

    result = loader.merge_staged_time_fraction_tiles(
        staged_tiles=staged_tiles,
        reference_grid=reference_grid,
        bbox=(0.0, 0.0, 4.0, 2.0),
        year=2013,
    )

    assert np.allclose(
        np.asarray(result["frac_8"].values[:, :, :2], dtype=np.float32),
        1.0,
        equal_nan=False,
    )
    assert np.allclose(
        np.asarray(result["frac_8"].values[:, :, -1], dtype=np.float32),
        0.0,
        equal_nan=False,
    )
    assert np.allclose(
        np.asarray(result["frac_0"].values[:, :, -1], dtype=np.float32),
        1.0,
        equal_nan=False,
    )


def test_gwd30_merge_time_fraction_tiles_raises_when_no_stage_bbox_matches(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "gwd30"
    tile_wet = np.full((2, 2, 2), 8, dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wet_wetland_2013.tif",
        tile_wet,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 2.0, 2.0), resolution_deg=1.0)
    stage_dir = tmp_path / "staged_tiles"
    staged_tiles = loader.stage_time_fraction_tiles(
        bbox=(0.0, 0.0, 2.0, 2.0),
        reference_grid=reference_grid,
        year=2013,
        staging_dir=stage_dir,
        worker_count=1,
        show_progress=False,
    )

    far_grid = create_comparison_grid((10.0, 10.0, 12.0, 12.0), resolution_deg=1.0)
    with pytest.raises(FileNotFoundError, match="No staged GWD30 coarse tiles intersect"):
        loader.merge_staged_time_fraction_tiles(
            staged_tiles=staged_tiles,
            reference_grid=far_grid,
            bbox=(10.0, 10.0, 12.0, 12.0),
            year=2013,
        )


def test_gwd30_merge_time_fraction_tiles_reuses_cached_spatial_index(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    base_path = tmp_path / "gwd30"
    tile_wet = np.full((2, 2, 2), 8, dtype=np.uint8)
    tile_dry = np.zeros((2, 2, 2), dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wet_wetland_2013.tif",
        tile_wet,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )
    write_multiband_geotiff(
        base_path / "2013/tile_dry_wetland_2013.tif",
        tile_dry,
        transform=from_origin(2.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 4.0, 2.0), resolution_deg=1.0)
    stage_dir = tmp_path / "staged_tiles"
    staged_tiles = loader.stage_time_fraction_tiles(
        bbox=(0.0, 0.0, 4.0, 2.0),
        reference_grid=reference_grid,
        year=2013,
        staging_dir=stage_dir,
        worker_count=1,
        show_progress=False,
    )

    original_build_index = gwd30_module._build_staged_tile_index
    build_calls = 0

    def counting_build_index(staged_tiles_arg):  # type: ignore[no-untyped-def]
        nonlocal build_calls
        build_calls += 1
        return original_build_index(staged_tiles_arg)

    monkeypatch.setattr(gwd30_module, "_build_staged_tile_index", counting_build_index)

    loader.merge_staged_time_fraction_tiles(
        staged_tiles=staged_tiles,
        reference_grid=reference_grid,
        bbox=(0.0, 0.0, 2.0, 2.0),
        year=2013,
    )
    loader.merge_staged_time_fraction_tiles(
        staged_tiles=staged_tiles,
        reference_grid=reference_grid,
        bbox=(2.0, 0.0, 4.0, 2.0),
        year=2013,
    )

    assert build_calls == 1


def test_gwd30_transform_staged_time_fraction_tiles_supports_phase36_reduce(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "gwd30"
    tile_wet = np.full((2, 2, 2), 8, dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wet_wetland_2013.tif",
        tile_wet,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 2.0, 2.0), resolution_deg=1.0)
    stage_dir = tmp_path / "staged_tiles"
    staged_tiles = loader.stage_time_fraction_tiles(
        bbox=(0.0, 0.0, 2.0, 2.0),
        reference_grid=reference_grid,
        year=2013,
        staging_dir=stage_dir,
        worker_count=1,
        show_progress=False,
    )

    transform_dir = tmp_path / "transformed_tiles"
    transformed_tiles = loader.transform_staged_time_fraction_tiles(
        staged_tiles=staged_tiles,
        output_dir=transform_dir,
        transform_name="phase36_annual_unified",
        transform_version=1,
        transform_tile=gwd30_module.phase36_reduce_staged_time_fraction_tile,
        year=2013,
        worker_count=1,
        show_progress=False,
    )

    assert len(transformed_tiles) == 1
    with xr.open_dataset(transformed_tiles[0][0], engine="netcdf4") as transformed:
        assert transformed["annual_source_weighted_sum"].sizes["source_class_id"] == 15
        assert transformed["annual_unified_weighted_sum"].sizes["class_id"] == 8
        np.testing.assert_allclose(
            np.asarray(transformed["annual_coverage_sum"].values, dtype=np.float32),
            2.0,
        )
        np.testing.assert_allclose(
            np.asarray(
                transformed["annual_source_weighted_sum"].sel(source_class_id=8).values,
                dtype=np.float32,
            ),
            2.0,
        )
        np.testing.assert_allclose(
            np.asarray(
                transformed["annual_unified_weighted_sum"].sel(class_id=2).values,
                dtype=np.float32,
            ),
            2.0,
        )
        np.testing.assert_allclose(
            np.asarray(
                transformed["annual_unified_weighted_sum"].sel(class_id=0).values,
                dtype=np.float32,
            ),
            0.0,
        )


def test_gwd30_transform_staged_time_fraction_tiles_refreshes_stale_outputs(
    tmp_path: Path,
) -> None:
    def write_stage_tile(stage_path: Path, *, active_class_id: int) -> None:
        class_ids = np.arange(15, dtype=np.int16)
        weighted = np.zeros((1, len(class_ids), 2, 2), dtype=np.float32)
        weighted[0, active_class_id, :, :] = 1.0
        coverage = np.ones((1, 2, 2), dtype=np.float32)
        xr.Dataset(
            {
                "weighted": xr.DataArray(
                    weighted,
                    dims=("time", "class_id", "lat", "lon"),
                    coords={
                        "time": np.array(["2013-01-01"], dtype="datetime64[ns]"),
                        "class_id": class_ids,
                        "lat": np.array([1.5, 0.5], dtype=np.float32),
                        "lon": np.array([100.5, 101.5], dtype=np.float32),
                    },
                ),
                "coverage": xr.DataArray(
                    coverage,
                    dims=("time", "lat", "lon"),
                    coords={
                        "time": np.array(["2013-01-01"], dtype="datetime64[ns]"),
                        "lat": np.array([1.5, 0.5], dtype=np.float32),
                        "lon": np.array([100.5, 101.5], dtype=np.float32),
                    },
                ),
            },
            attrs={"year": 2013},
        ).to_netcdf(stage_path)

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                tmp_path / "gwd30",
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    stage_dir = tmp_path / "staged_tiles"
    stage_dir.mkdir()
    stage_path = stage_dir / "tile_demo_wetland_2013.nc"
    transform_dir = tmp_path / "transformed_tiles"
    staged_tiles = [(stage_path, (100.0, 0.0, 102.0, 2.0))]

    write_stage_tile(stage_path, active_class_id=8)
    loader.transform_staged_time_fraction_tiles(
        staged_tiles=staged_tiles,
        output_dir=transform_dir,
        transform_name="phase36_annual_unified",
        transform_version=1,
        transform_tile=gwd30_module.phase36_reduce_staged_time_fraction_tile,
        year=2013,
        worker_count=1,
        show_progress=False,
        skip_existing=False,
    )

    output_path = transform_dir / stage_path.name
    with xr.open_dataset(output_path, engine="netcdf4") as transformed:
        np.testing.assert_allclose(
            np.asarray(
                transformed["annual_source_weighted_sum"].sel(source_class_id=8).values,
                dtype=np.float32,
            ),
            1.0,
        )
        np.testing.assert_allclose(
            np.asarray(
                transformed["annual_unified_weighted_sum"].sel(class_id=2).values,
                dtype=np.float32,
            ),
            1.0,
        )

    time.sleep(0.01)
    write_stage_tile(stage_path, active_class_id=0)
    loader.transform_staged_time_fraction_tiles(
        staged_tiles=staged_tiles,
        output_dir=transform_dir,
        transform_name="phase36_annual_unified",
        transform_version=1,
        transform_tile=gwd30_module.phase36_reduce_staged_time_fraction_tile,
        year=2013,
        worker_count=1,
        show_progress=False,
        skip_existing=True,
    )

    with xr.open_dataset(output_path, engine="netcdf4") as transformed:
        np.testing.assert_allclose(
            np.asarray(
                transformed["annual_source_weighted_sum"].sel(source_class_id=0).values,
                dtype=np.float32,
            ),
            1.0,
        )
        np.testing.assert_allclose(
            np.asarray(
                transformed["annual_source_weighted_sum"].sel(source_class_id=8).values,
                dtype=np.float32,
            ),
            0.0,
        )
        np.testing.assert_allclose(
            np.asarray(
                transformed["annual_unified_weighted_sum"].sel(class_id=0).values,
                dtype=np.float32,
            ),
            1.0,
        )
        np.testing.assert_allclose(
            np.asarray(
                transformed["annual_unified_weighted_sum"].sel(class_id=2).values,
                dtype=np.float32,
            ),
            0.0,
        )


def test_process_time_fraction_tile_to_stage_file_writes_partial_netcdf(
    tmp_path: Path,
) -> None:
    base_path = tmp_path / "gwd30"
    tile = np.full((2, 2, 2), 8, dtype=np.uint8)
    tile_path = base_path / "2013/tile_wetland_2013.tif"
    write_multiband_geotiff(
        tile_path,
        tile,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 2.0, 2.0), resolution_deg=1.0)
    reference_crs, reference_transform, width, height = gwd30_module._reference_grid_spec(
        reference_grid
    )
    time_index = pd.DatetimeIndex(["2013-01-01", "2013-01-05"])
    stage_path = tmp_path / "staged_tiles" / "tile_tile_wetland_2013.nc"
    stage_path.parent.mkdir(parents=True, exist_ok=True)

    staged = gwd30_module._process_time_fraction_tile_to_stage_file(
        path=str(tile_path),
        stage_path=str(stage_path),
        manifest_bbox=(0.0, 0.0, 2.0, 2.0),
        stage_bbox=(0.0, 0.0, 2.0, 2.0),
        reference_crs=reference_crs,
        reference_transform=reference_transform,
        width=width,
        height=height,
        y_dim="lat",
        x_dim="lon",
        y_coords=np.asarray(reference_grid.coords["lat"].values),
        x_coords=np.asarray(reference_grid.coords["lon"].values),
        year=2013,
        time_index=time_index,
    )

    assert staged == (stage_path, (0.0, 0.0, 2.0, 2.0))
    with xr.open_dataset(stage_path) as partial:
        assert set(partial.data_vars) == {"weighted", "coverage"}
        assert partial.sizes["time"] == 2
        assert partial.sizes["class_id"] == 15
    assert list(stage_path.parent.glob(f".{stage_path.name}.tmp-*")) == []
    assert not (stage_path.parent / f".{stage_path.name}.lock").exists()


def test_resolve_stage_worker_count_caps_unsafe_parallelism(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(gwd30_module, "_resolve_parallel_worker_count", lambda _worker_count: 32)

    assert gwd30_module._resolve_stage_worker_count(None, 10235) == 4
    assert gwd30_module._resolve_stage_worker_count(None, 1) == 1


def test_resolve_stage_worker_count_allows_explicit_override(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(gwd30_module, "_resolve_parallel_worker_count", lambda _worker_count: 32)

    assert gwd30_module._resolve_stage_worker_count(12, 10235) == 12


def test_try_acquire_stage_lock_reclaims_stale_lock(tmp_path: Path) -> None:
    stage_path = tmp_path / "staged_tiles" / "tile_31NEA_wetland_2013.nc"
    stage_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = gwd30_module._stage_lock_path(stage_path)
    lock_path.write_text("stale\n", encoding="utf-8")
    stale_mtime = time.time() - (gwd30_module._GWD30_STAGE_LOCK_STALE_SECONDS + 60)
    os.utime(lock_path, (stale_mtime, stale_mtime))

    acquired = gwd30_module._try_acquire_stage_lock(stage_path)

    assert acquired == lock_path
    assert lock_path.exists()
    lock_path.unlink()


def test_gwd30_loader_prefers_tile_code_prefilter_before_bounds_scan(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    base_path = tmp_path / "gwd30"
    band_count = 92
    matching_tile = np.full((band_count, 2, 2), 4, dtype=np.uint8)
    other_tile = np.full((band_count, 2, 2), 9, dtype=np.uint8)
    bbox = (2.9, -0.1, 3.1, 0.1)
    tile_code = "31NEA"

    write_multiband_geotiff(
        base_path / f"2013/{tile_code}_wetland_2013.tif",
        matching_tile,
        transform=from_origin(2.5, 0.5, 0.25, 0.25),
    )
    write_multiband_geotiff(
        base_path / "2013/01KAA_wetland_2013.tif",
        other_tile,
        transform=from_origin(100.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    monkeypatch.setattr(
        "WA.loaders.gwd30._filter_files_by_bounds",
        lambda _paths, _bbox: (_ for _ in ()).throw(
            AssertionError("bounds fallback should not run")
        ),
    )

    discovered = loader._discover_tiles(bbox=bbox, time_range=("2013-01-01", "2013-12-31"))

    assert [path.name for path in discovered[2013]] == [f"{tile_code}_wetland_2013.tif"]


def test_gwd30_loader_caches_tile_discovery_for_same_probe_request(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    base_path = tmp_path / "gwd30"
    band_count = 92
    tile = np.full((band_count, 2, 2), 5, dtype=np.uint8)
    bbox = (2.9, -0.1, 3.1, 0.1)
    tile_code = "31NEA"

    write_multiband_geotiff(
        base_path / f"2013/{tile_code}_wetland_2013.tif",
        tile,
        transform=from_origin(2.5, 0.5, 0.25, 0.25),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    calls = {"filter": 0}
    original_filter = loader._filter_tiles_for_bbox

    def counting_filter(
        paths: list[Path],
        query_bbox: tuple[float, float, float, float],
    ) -> list[Path]:
        calls["filter"] += 1
        return original_filter(paths, query_bbox)

    monkeypatch.setattr(loader, "_filter_tiles_for_bbox", counting_filter)

    first = loader._discover_tiles(bbox=bbox, time_range=("2013-01-01", "2013-12-31"))
    second = loader._discover_tiles(bbox=bbox, time_range=("2013-01-01", "2013-12-31"))

    assert calls["filter"] == 1
    assert first == second


def test_gwd30_stage_time_fraction_tiles_prefers_tile_code_bounds_over_raster_scan(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    base_path = tmp_path / "gwd30"
    tile = np.full((2, 2, 2), 8, dtype=np.uint8)
    tile_code = "31NEA"

    write_multiband_geotiff(
        base_path / f"2013/{tile_code}_wetland_2013.tif",
        tile,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    monkeypatch.setattr(loader, "_tile_bbox", lambda code: (0.0, 0.0, 2.0, 2.0))
    monkeypatch.setattr(
        "WA.loaders.gwd30._path_bounds_wgs84",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("stage planning should not scan raster bounds when tile code exists")
        ),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 2.0, 2.0), resolution_deg=1.0)
    staged = loader.stage_time_fraction_tiles(
        bbox=(0.0, 0.0, 2.0, 2.0),
        reference_grid=reference_grid,
        year=2013,
        staging_dir=tmp_path / "staged_tiles",
        worker_count=1,
        show_progress=False,
    )

    assert len(staged) == 1


def test_gwd30_stage_time_fraction_tiles_logs_discovery_and_plan(
    tmp_path: Path,
    caplog,
) -> None:
    base_path = tmp_path / "gwd30"
    tile = np.full((2, 2, 2), 8, dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wetland_2013.tif",
        tile,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 2.0, 2.0), resolution_deg=1.0)
    caplog.set_level("INFO", logger="WA.loaders.gwd30")
    loader.stage_time_fraction_tiles(
        bbox=(0.0, 0.0, 2.0, 2.0),
        reference_grid=reference_grid,
        year=2013,
        staging_dir=tmp_path / "staged_tiles",
        worker_count=1,
        show_progress=False,
    )

    assert "discovering source tiles" in caplog.text
    assert "source tile(s) matched after filtering" in caplog.text
    assert "stage plan prepared" in caplog.text


def test_gwd30_stage_time_fraction_tiles_respects_shard_assignment(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    base_path = tmp_path / "gwd30"
    tile = np.full((2, 2, 2), 8, dtype=np.uint8)

    for tile_code in ("01KAA", "01KAB", "01KAC"):
        write_multiband_geotiff(
            base_path / f"2013/{tile_code}_wetland_2013.tif",
            tile,
            transform=from_origin(0.0, 2.0, 1.0, 1.0),
        )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    monkeypatch.setattr(loader, "_tile_bbox", lambda _code: (0.0, 0.0, 2.0, 2.0))

    reference_grid = create_comparison_grid((0.0, 0.0, 2.0, 2.0), resolution_deg=1.0)
    staged = loader.stage_time_fraction_tiles(
        bbox=(0.0, 0.0, 2.0, 2.0),
        reference_grid=reference_grid,
        year=2013,
        staging_dir=tmp_path / "staged_tiles",
        worker_count=1,
        show_progress=False,
        shard_index=1,
        shard_count=2,
    )

    assert [stage_path.name for stage_path, _bbox in staged] == ["tile_01KAB_wetland_2013.nc"]


def test_gwd30_load_rough_binary_surface_uses_temp_mosaic_and_tqdm(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    base_path = tmp_path / "gwd30"
    tile_wet = np.full((2, 2, 2), 8, dtype=np.uint8)
    tile_dry = np.zeros((2, 2, 2), dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wet_wetland_2013.tif",
        tile_wet,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )
    write_multiband_geotiff(
        base_path / "2013/tile_dry_wetland_2013.tif",
        tile_dry,
        transform=from_origin(2.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    progress_descriptions: list[str | None] = []

    def fake_tqdm(iterable=None, *args, **kwargs):  # type: ignore[no-untyped-def]
        progress_descriptions.append(kwargs.get("desc"))

        class DummyProgress:
            def update(self, _: int = 1) -> None:
                return None

            def close(self) -> None:
                return None

            def set_postfix_str(self, *_args, **_kwargs) -> None:  # type: ignore[no-untyped-def]
                return None

        if iterable is None:
            return DummyProgress()
        return iterable

    monkeypatch.setattr("WA.loaders.gwd30.tqdm", fake_tqdm)

    reference_grid = create_comparison_grid((0.0, 0.0, 4.0, 2.0), resolution_deg=1.0)
    surface, trace = loader.load_rough_binary_surface(
        bbox=(0.0, 0.0, 4.0, 2.0),
        time_range=("2013-01-01", "2013-01-31"),
        reference_grid=reference_grid,
        aggregation="mean",
        target_time=pd.Timestamp("2013-01-01"),
        worker_count=1,
    )

    assert trace["intermediate_storage"] == "temporary_coarse_geotiff_tiles"
    assert trace["processed_temp_tile_count"] == 2
    assert trace["years"][0]["selected_tiles"][0]["processed_temp_written"] is True
    assert trace["years"][0]["selected_tiles"][1]["processed_temp_written"] is True
    assert progress_descriptions == ["GWD30 2013 process", "GWD30 mosaic"]
    assert np.allclose(np.asarray(surface.values[:, :2], dtype=np.float32), 1.0, equal_nan=False)
    assert np.allclose(np.asarray(surface.values[:, -1], dtype=np.float32), 0.0, equal_nan=False)
    assert np.all(
        (np.asarray(surface.values[:, 2], dtype=np.float32) >= 0.0)
        & (np.asarray(surface.values[:, 2], dtype=np.float32) <= 1.0)
    )


def test_gwd30_noop_tqdm_supports_manual_progress_updates() -> None:
    progress_bar = progress_utils.tqdm(total=3, desc="GWD30 2019 parallel")

    progress_bar.update(1)
    progress_bar.close()

    assert list(progress_utils.tqdm([1, 2, 3], desc="GWD30 2019 load")) == [1, 2, 3]


def test_gwd30_load_rough_binary_surface_parallel_reduce_path(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    base_path = tmp_path / "gwd30"
    tile_wet = np.full((2, 2, 2), 8, dtype=np.uint8)
    tile_dry = np.zeros((2, 2, 2), dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wet_wetland_2013.tif",
        tile_wet,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )
    write_multiband_geotiff(
        base_path / "2013/tile_dry_wetland_2013.tif",
        tile_dry,
        transform=from_origin(2.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    progress_descriptions: list[str | None] = []

    def fake_tqdm(iterable=None, *args, **kwargs):  # type: ignore[no-untyped-def]
        desc = kwargs.get("desc")
        progress_descriptions.append(desc)

        class DummyProgress:
            def update(self, value):  # type: ignore[no-untyped-def]
                return None

            def close(self):  # type: ignore[no-untyped-def]
                return None

        if iterable is None:
            return DummyProgress()
        return iterable

    class ImmediateFuture:
        def __init__(self, result: tuple[object | None, object | None, int]) -> None:
            self._result = result

        def result(self) -> tuple[object | None, object | None, int]:
            return self._result

    class ImmediateExecutor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            return None

        def __enter__(self) -> ImmediateExecutor:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def submit(
            self,
            fn: Callable[..., tuple[object | None, object | None, int]],
            *args: object,
            **kwargs: object,
        ) -> ImmediateFuture:
            return ImmediateFuture(fn(*args, **kwargs))

    monkeypatch.setattr("WA.loaders.gwd30.tqdm", fake_tqdm)
    monkeypatch.setattr("WA.loaders.gwd30.ProcessPoolExecutor", ImmediateExecutor)
    monkeypatch.setattr(
        "WA.loaders.gwd30.as_completed",
        lambda futures: list(futures),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 4.0, 2.0), resolution_deg=1.0)
    surface, trace = loader.load_rough_binary_surface(
        bbox=(0.0, 0.0, 4.0, 2.0),
        time_range=("2013-01-01", "2013-01-31"),
        reference_grid=reference_grid,
        aggregation="mean",
        target_time=pd.Timestamp("2013-01-01"),
        worker_count=2,
    )

    assert trace["strategy"] == "parallel_direct_to_reference_grid"
    assert trace["intermediate_storage"] == "in_memory_partial_reduce"
    assert trace["mosaic_strategy"] == "main_process_sum_count_reduce"
    assert trace["worker_count"] == 2
    assert trace["processed_temp_tile_count"] == 0
    assert progress_descriptions == ["GWD30 2013 parallel"]
    assert trace["years"][0]["selected_tiles"][0]["processed_in_memory"] is True
    assert trace["years"][0]["selected_tiles"][1]["processed_in_memory"] is True
    assert np.allclose(np.asarray(surface.values[:, :2], dtype=np.float32), 1.0, equal_nan=False)
    assert np.allclose(np.asarray(surface.values[:, -1], dtype=np.float32), 0.0, equal_nan=False)


def test_gwd30_parallel_reduce_falls_back_to_serial_on_broken_pool(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """When ProcessPoolExecutor workers die (OOM), remaining tiles are processed serially."""

    base_path = tmp_path / "gwd30"
    tile_wet = np.full((2, 2, 2), 8, dtype=np.uint8)
    tile_dry = np.zeros((2, 2, 2), dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wet_wetland_2013.tif",
        tile_wet,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )
    write_multiband_geotiff(
        base_path / "2013/tile_dry_wetland_2013.tif",
        tile_dry,
        transform=from_origin(2.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    # Fake executor: first tile succeeds, second raises BrokenProcessPool
    call_count = 0
    real_fn = None

    class BrokenFuture:
        def result(self) -> object:
            raise BrokenProcessPool("worker killed")

    class PartiallyBrokenExecutor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> PartiallyBrokenExecutor:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def submit(self, fn: Callable[..., object], *args: object, **kwargs: object) -> object:
            nonlocal call_count, real_fn
            real_fn = fn
            call_count += 1
            if call_count == 1:
                # First tile succeeds
                class GoodFuture:
                    def result(self) -> object:
                        return fn(*args, **kwargs)
                return GoodFuture()
            # All subsequent tiles: pool broken
            return BrokenFuture()

    class DummyProgress:
        def update(self, _: int = 1) -> None:
            pass
        def close(self) -> None:
            pass

    def fake_tqdm(iterable: object = None, *args: object, **kwargs: object) -> object:
        if iterable is None:
            return DummyProgress()
        return iterable

    monkeypatch.setattr("WA.loaders.gwd30.tqdm", fake_tqdm)
    monkeypatch.setattr("WA.loaders.gwd30.ProcessPoolExecutor", PartiallyBrokenExecutor)
    monkeypatch.setattr("WA.loaders.gwd30.as_completed", lambda futures: list(futures))

    reference_grid = create_comparison_grid((0.0, 0.0, 4.0, 2.0), resolution_deg=1.0)
    surface, trace = loader.load_rough_binary_surface(
        bbox=(0.0, 0.0, 4.0, 2.0),
        time_range=("2013-01-01", "2013-01-31"),
        reference_grid=reference_grid,
        aggregation="mean",
        target_time=pd.Timestamp("2013-01-01"),
        worker_count=2,
    )

    # Both tiles should have produced data (one parallel, one serial fallback)
    tiles = trace["years"][0]["selected_tiles"]
    assert len(tiles) == 2
    assert all(t["processed_in_memory"] for t in tiles)
    # Surface should have valid data — not all NaN
    assert np.isfinite(surface.values).any()


def test_gwd30_load_time_fraction_grid_parallel_reduce_path(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    base_path = tmp_path / "gwd30"
    tile_wet = np.full((2, 2, 2), 8, dtype=np.uint8)
    tile_dry = np.zeros((2, 2, 2), dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/tile_wet_wetland_2013.tif",
        tile_wet,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )
    write_multiband_geotiff(
        base_path / "2013/tile_dry_wetland_2013.tif",
        tile_dry,
        transform=from_origin(2.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    progress_descriptions: list[str | None] = []

    def fake_tqdm(iterable: object = None, *args: object, **kwargs: object) -> object:
        progress_descriptions.append(cast(str | None, kwargs.get("desc")))

        class DummyProgress:
            def update(self, _: int = 1) -> None:
                return None

            def close(self) -> None:
                return None

            def set_postfix_str(self, *_args: object, **_kwargs: object) -> None:
                return None

        if iterable is None:
            return DummyProgress()
        return iterable

    class ImmediateFuture:
        def __init__(self, result: tuple[np.ndarray | None, np.ndarray | None]) -> None:
            self._result = result

        def result(self) -> tuple[np.ndarray | None, np.ndarray | None]:
            return self._result

    class ImmediateExecutor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            return None

        def __enter__(self) -> ImmediateExecutor:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def submit(
            self,
            fn: Callable[..., tuple[np.ndarray | None, np.ndarray | None]],
            *args: object,
            **kwargs: object,
        ) -> ImmediateFuture:
            return ImmediateFuture(fn(*args, **kwargs))

    monkeypatch.setattr("WA.loaders.gwd30.tqdm", fake_tqdm)
    monkeypatch.setattr("WA.loaders.gwd30.ProcessPoolExecutor", ImmediateExecutor)
    monkeypatch.setattr("WA.loaders.gwd30.as_completed", lambda futures: list(futures))

    reference_grid = create_comparison_grid((0.0, 0.0, 4.0, 2.0), resolution_deg=1.0)
    result = loader.load_time_fraction_grid(
        bbox=(0.0, 0.0, 4.0, 2.0),
        reference_grid=reference_grid,
        year=2013,
        worker_count=2,
        show_progress=True,
    )

    assert progress_descriptions == ["GWD30 2013 time-frac-parallel"]
    assert np.allclose(
        np.asarray(result["frac_8"].values[:, :, :2], dtype=np.float32),
        1.0,
        equal_nan=False,
    )
    assert np.allclose(
        np.asarray(result["frac_8"].values[:, :, -1], dtype=np.float32),
        0.0,
        equal_nan=False,
    )
    assert np.all(
        (np.asarray(result["frac_8"].values[:, :, 2], dtype=np.float32) >= 0.0)
        & (np.asarray(result["frac_8"].values[:, :, 2], dtype=np.float32) <= 1.0)
    )
    assert np.allclose(
        np.asarray(result["frac_0"].values[:, :, -1], dtype=np.float32),
        1.0,
        equal_nan=False,
    )


def test_gwd30_compute_rough_binary_partial_supports_shards(tmp_path: Path) -> None:
    base_path = tmp_path / "gwd30"
    tile_wet = np.full((2, 2, 2), 8, dtype=np.uint8)
    tile_dry = np.zeros((2, 2, 2), dtype=np.uint8)

    write_multiband_geotiff(
        base_path / "2013/a_wetland_2013.tif",
        tile_wet,
        transform=from_origin(0.0, 2.0, 1.0, 1.0),
    )
    write_multiband_geotiff(
        base_path / "2013/b_wetland_2013.tif",
        tile_dry,
        transform=from_origin(2.0, 2.0, 1.0, 1.0),
    )

    loader = cast(
        GWD30Loader,
        get_loader(
            "gwd30",
            with_common_fields(
                base_path,
                loader_type="gwd30",
                years=[2013],
                pattern="{year}/*_wetland_{year}.tif",
            ),
        ),
    )

    reference_grid = create_comparison_grid((0.0, 0.0, 4.0, 2.0), resolution_deg=1.0)
    partial_sum_0, partial_count_0, trace_0 = loader.compute_rough_binary_partial(
        bbox=(0.0, 0.0, 4.0, 2.0),
        time_range=("2013-01-01", "2013-01-31"),
        reference_grid=reference_grid,
        aggregation="mean",
        target_time=pd.Timestamp("2013-01-01"),
        worker_count=1,
        shard_index=0,
        shard_count=2,
    )
    partial_sum_1, partial_count_1, trace_1 = loader.compute_rough_binary_partial(
        bbox=(0.0, 0.0, 4.0, 2.0),
        time_range=("2013-01-01", "2013-01-31"),
        reference_grid=reference_grid,
        aggregation="mean",
        target_time=pd.Timestamp("2013-01-01"),
        worker_count=1,
        shard_index=1,
        shard_count=2,
    )

    merged_surface = loader.build_surface_from_partial(
        partial_sum=partial_sum_0 + partial_sum_1,
        partial_count=partial_count_0 + partial_count_1,
        reference_grid=reference_grid,
        aggregation="mean",
        target_time=pd.Timestamp("2013-01-01"),
    )

    assert trace_0["strategy"] == "sharded_partial_reduce"
    assert trace_1["strategy"] == "sharded_partial_reduce"
    assert trace_0["shard_index"] == 0
    assert trace_1["shard_index"] == 1
    assert trace_0["years"][0]["assigned_tile_count"] == 1
    assert trace_1["years"][0]["assigned_tile_count"] == 1
    assert np.allclose(
        np.asarray(merged_surface.values[:, :2], dtype=np.float32),
        1.0,
        equal_nan=False,
    )
    assert np.allclose(
        np.asarray(merged_surface.values[:, -1], dtype=np.float32),
        0.0,
        equal_nan=False,
    )
