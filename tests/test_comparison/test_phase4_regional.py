from __future__ import annotations

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

import WA.comparison.phase4_regional as phase4_regional_module
from WA.comparison.phase4_regional import (
    Phase4Region,
    build_or_load_phase4_berkeley_valid_mask,
    build_or_load_phase4_gwd30_tropical_tile_cache,
    build_or_load_phase4_mask_fraction,
    build_phase4_annual_series,
    build_phase4_gwd30_monthly_series_from_pixel_stats_tiles,
    build_phase4_gwd30_monthly_series_from_tropical_tile_cache,
    build_phase4_gwd30_monthly_tile_from_pixel_stats_file,
    build_phase4_gwd30_reduced_tile_index_for_staged_tiles,
    build_phase4_gwd30_tropical_monthly_tile_from_reduced_file,
    build_phase4_gwd30_tropical_monthly_tile_from_stage_file,
    build_phase4_gwd30_tropical_tile_index_for_staged_tiles,
    compute_phase4_monthly_regional_series,
    compute_phase4_region_dataset_table,
    list_phase4_gwd30_stage_shard_manifests,
    load_phase4_gwd30_staged_tiles,
    load_phase4_gwd30_staged_tiles_from_manifest_paths,
    load_phase4_regions,
    phase4_gwd30_pixel_stats_manifest_path,
    phase4_gwd30_tropical_tile_cache_path,
    resolve_phase4_dataset_config,
)

EXPECTED_TEN_REGION_IDS = [
    "amazon",
    "orinoco",
    "pantanal",
    "indogangetic",
    "mekong",
    "sudd",
    "congo",
    "okavango",
    "borneo",
    "northernaus",
]


def test_load_phase4_regions_includes_macro_and_priority_regions(tmp_path: Path) -> None:
    regions_file = tmp_path / "priority_regions.yaml"
    regions_file.write_text(
        """
regions:
  demo_region:
    label: "Demo"
    label_zh: "示例区域"
    kind: "priority_region"
    priority: 10
    bbox: [100.0, -5.0, 105.0, 5.0]
""".strip(),
        encoding="utf-8",
    )

    regions = load_phase4_regions(regions_file)

    assert regions[0].region_id == "pan_trop_subtrop"
    assert regions[-1].region_id == "demo_region"
    assert regions[-1].display_label == "示例区域"
    assert len(regions) == 7


def test_resolve_phase4_dataset_config_uses_standardized_berkeley_and_raw_topmodel(
    tmp_path: Path,
) -> None:
    topmodel_path = tmp_path / "topmodel_raw"
    standardized_dir = tmp_path / "standardized"

    topmodel = resolve_phase4_dataset_config(
        "topmodel",
        standardized_dir=standardized_dir,
        topmodel_raw_path=topmodel_path,
    )
    berkeley = resolve_phase4_dataset_config(
        "berkeley_rwawc",
        standardized_dir=standardized_dir,
    )

    assert topmodel["loader_type"] == "topmodel"
    assert topmodel["path"] == str(topmodel_path)
    assert berkeley["loader_type"] == "standardized_netcdf"
    assert berkeley["path"] == str(standardized_dir)


def test_build_phase4_annual_series_requires_complete_years() -> None:
    full_year = pd.date_range("2020-01-01", periods=12, freq="MS")
    partial_year = pd.date_range("2021-01-01", periods=11, freq="MS")
    monthly = pd.DataFrame(
        {
            "time": list(full_year) + list(partial_year),
            "year": [time.year for time in full_year] + [time.year for time in partial_year],
            "month": [time.month for time in full_year]
            + [time.month for time in partial_year],
            "wetland_area_km2": 10.0,
            "valid_area_km2": 20.0,
            "wetland_percentage": 50.0,
            "observation_count": 1,
        }
    )

    annual = build_phase4_annual_series(monthly)

    assert annual["year"].tolist() == [2020]
    assert annual["observation_count"].tolist() == [12]


def test_compute_phase4_monthly_regional_series_applies_mask_weights() -> None:
    monthly = xr.DataArray(
        np.array(
            [
                [[0.2, 0.8]],
                [[0.4, np.nan]],
            ],
            dtype=np.float32,
        ),
        coords={
            "time": pd.to_datetime(["2020-01-01", "2020-02-01"]),
            "lat": [0.0],
            "lon": [100.0, 101.0],
        },
        dims=("time", "lat", "lon"),
        name="wetland_fraction",
    )
    monthly = monthly.rio.write_crs("EPSG:4326", inplace=False)
    monthly = monthly.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)

    mask = xr.DataArray(
        np.array([[1.0, 0.5]], dtype=np.float32),
        coords={"lat": [0.0], "lon": [100.0, 101.0]},
        dims=("lat", "lon"),
        name="shared_mask_fraction",
    )
    mask = mask.rio.write_crs("EPSG:4326", inplace=False)
    mask = mask.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)

    frame = compute_phase4_monthly_regional_series(
        monthly_data=monthly,
        mask_fraction=mask,
        dataset_id="wad2m",
        region_id="demo",
        spatial_lat_chunk_size=1,
        time_chunk_size=1,
        show_progress=False,
    )

    assert frame["month"].tolist() == [1, 2]
    assert np.allclose(frame["wetland_percentage"].to_numpy(dtype=float), [40.0, 40.0])


def test_build_or_load_phase4_mask_fraction_writes_same_grid_cache(tmp_path: Path) -> None:
    base_mask = xr.DataArray(
        np.array([[1.0, 0.0], [0.5, 1.0]], dtype=np.float32),
        coords={"lat": [1.0, 0.0], "lon": [100.0, 101.0]},
        dims=("lat", "lon"),
        name="shared_mask_fraction",
    )
    base_mask = base_mask.rio.write_crs("EPSG:4326", inplace=False)
    base_mask = base_mask.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)

    template = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        coords={"lat": [1.0, 0.0], "lon": [100.0, 101.0]},
        dims=("lat", "lon"),
        name="template",
    )
    template = template.rio.write_crs("EPSG:4326", inplace=False)
    template = template.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)

    cache_path = tmp_path / "mask.nc"
    mask = build_or_load_phase4_mask_fraction(
        base_mask=base_mask,
        template=template,
        cache_path=cache_path,
        skip_existing=False,
    )

    assert cache_path.is_file()
    assert np.allclose(mask.values, base_mask.values)


def test_mask_fraction_for_template_subsets_large_mask_before_reproject(monkeypatch) -> None:
    base_mask = xr.DataArray(
        np.arange(16, dtype=np.float32).reshape(4, 4),
        coords={"lat": [3.0, 2.0, 1.0, 0.0], "lon": [100.0, 101.0, 102.0, 103.0]},
        dims=("lat", "lon"),
        name="shared_mask_fraction",
    )
    base_mask = base_mask.rio.write_crs("EPSG:4326", inplace=False)
    base_mask = base_mask.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)

    template = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        coords={"lat": [1.8, 1.2], "lon": [101.2, 101.8]},
        dims=("lat", "lon"),
        name="template",
    )
    template = template.rio.write_crs("EPSG:4326", inplace=False)
    template = template.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)

    recorded: dict[str, object] = {}

    def fake_subset_phase4_mask_to_bbox(mask, bbox):
        recorded["bbox"] = bbox
        subset = xr.DataArray(
            np.ones((2, 2), dtype=np.float32),
            coords={"lat": [2.0, 1.0], "lon": [101.0, 102.0]},
            dims=("lat", "lon"),
            name="shared_mask_fraction",
        )
        subset = subset.rio.write_crs("EPSG:4326", inplace=False)
        subset = subset.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
        return subset

    def fake_reproject_to_grid(source_mask, reference_grid, *, resampling):
        recorded["source_shape"] = source_mask.shape
        recorded["target_shape"] = reference_grid.shape
        return xr.zeros_like(reference_grid, dtype=np.float32)

    monkeypatch.setattr(
        phase4_regional_module,
        "subset_phase4_mask_to_bbox",
        fake_subset_phase4_mask_to_bbox,
    )
    monkeypatch.setattr(phase4_regional_module, "reproject_to_grid", fake_reproject_to_grid)

    phase4_regional_module._mask_fraction_for_template(
        base_mask=base_mask,
        template=template,
    )

    assert recorded["bbox"] == (101.2, 1.2, 101.8, 1.8)
    assert recorded["source_shape"] == (2, 2)
    assert recorded["target_shape"] == (2, 2)


def test_build_or_load_phase4_berkeley_valid_mask_uses_finite_extent(
    tmp_path: Path,
) -> None:
    standardized_dir = tmp_path / "standardized"
    standardized_dir.mkdir()
    xr.Dataset(
        {
            "watermask": xr.DataArray(
                np.array(
                    [
                        [[1.0, np.nan], [np.nan, 0.0]],
                        [[np.nan, np.nan], [np.nan, 0.5]],
                    ],
                    dtype=np.float32,
                ),
                dims=("time", "lat", "lon"),
                coords={
                    "time": pd.to_datetime(["2016-01-01", "2016-02-01"]),
                    "lat": [1.0, 0.0],
                    "lon": [100.0, 101.0],
                },
            )
        }
    ).to_netcdf(standardized_dir / "berkeley_rwawc_2016.nc")

    region = Phase4Region(
        region_id="demo_region",
        label="Demo",
        label_zh="示例",
        bbox=(99.5, -0.5, 101.5, 1.5),
        kind="priority_region",
        priority=1,
        is_priority_region=True,
    )
    mask = build_or_load_phase4_berkeley_valid_mask(
        region=region,
        output_root=tmp_path / "results",
        standardized_dir=standardized_dir,
        time_range=("2016-01-01", "2016-12-31"),
        skip_existing=False,
    )

    assert np.array_equal(mask.values, np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32))


def test_build_or_load_phase4_berkeley_valid_mask_uses_single_time_slice(
    tmp_path: Path,
) -> None:
    standardized_dir = tmp_path / "standardized"
    standardized_dir.mkdir()
    xr.Dataset(
        {
            "watermask": xr.DataArray(
                np.array(
                    [
                        [[1.0, np.nan], [np.nan, np.nan]],
                        [[np.nan, 0.5], [0.5, 0.5]],
                    ],
                    dtype=np.float32,
                ),
                dims=("time", "lat", "lon"),
                coords={
                    "time": pd.to_datetime(["2016-01-01", "2016-02-01"]),
                    "lat": [1.0, 0.0],
                    "lon": [100.0, 101.0],
                },
            )
        }
    ).to_netcdf(standardized_dir / "berkeley_rwawc_2016.nc")

    region = Phase4Region(
        region_id="demo_region",
        label="Demo",
        label_zh="示例",
        bbox=(99.5, -0.5, 101.5, 1.5),
        kind="priority_region",
        priority=1,
        is_priority_region=True,
    )
    mask = build_or_load_phase4_berkeley_valid_mask(
        region=region,
        output_root=tmp_path / "results",
        standardized_dir=standardized_dir,
        time_range=("2016-01-01", "2016-12-31"),
        skip_existing=False,
    )

    assert np.array_equal(mask.values, np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.float32))


def test_build_or_load_phase4_berkeley_valid_mask_uses_first_available_source_window(
    tmp_path: Path,
    monkeypatch,
) -> None:
    standardized_dir = tmp_path / "standardized"
    standardized_dir.mkdir()
    for year, times in (
        (2018, ["2018-08-01", "2018-09-01"]),
        (2019, ["2019-01-01", "2019-02-01"]),
    ):
        xr.Dataset(
            {
                "watermask": xr.DataArray(
                    np.ones((len(times), 1, 1), dtype=np.float32),
                    dims=("time", "lat", "lon"),
                    coords={"time": pd.to_datetime(times), "lat": [0.5], "lon": [100.5]},
                )
            }
        ).to_netcdf(standardized_dir / f"berkeley_rwawc_{year}.nc")

    recorded: dict[str, object] = {}

    def fake_open_phase4_dataset(
        dataset_id,
        *,
        bbox,
        time_range,
        standardized_dir,
        topmodel_raw_path,
    ):
        recorded["dataset_id"] = dataset_id
        recorded["bbox"] = bbox
        recorded["time_range"] = time_range
        dataset = xr.Dataset(
            {
                "watermask": xr.DataArray(
                    np.array([[[1.0]]], dtype=np.float32),
                    dims=("time", "lat", "lon"),
                    coords={
                        "time": pd.to_datetime([time_range[0]]),
                        "lat": [0.5],
                        "lon": [100.5],
                    },
                )
            }
        )
        dataset = dataset.rio.write_crs("EPSG:4326", inplace=False)
        dataset = dataset.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
        return dataset

    monkeypatch.setattr(phase4_regional_module, "_open_phase4_dataset", fake_open_phase4_dataset)

    region = Phase4Region(
        region_id="amazon",
        label="Amazon",
        label_zh="亚马孙",
        bbox=(99.5, -0.5, 101.5, 1.5),
        kind="priority_region",
        priority=1,
        is_priority_region=True,
    )
    mask = build_or_load_phase4_berkeley_valid_mask(
        region=region,
        output_root=tmp_path / "results",
        standardized_dir=standardized_dir,
        time_range=("2013-01-01", "2022-12-31"),
        skip_existing=False,
    )

    assert recorded["dataset_id"] == "berkeley_rwawc"
    assert recorded["bbox"] == region.bbox
    assert recorded["time_range"] == ("2018-08-01", "2018-08-01")
    assert np.array_equal(mask.values, np.array([[1.0]], dtype=np.float32))


def test_build_or_load_phase4_berkeley_valid_mask_falls_back_to_earliest_available_source_window(
    tmp_path: Path,
    monkeypatch,
) -> None:
    standardized_dir = tmp_path / "standardized"
    standardized_dir.mkdir()
    for year, times in (
        (2018, ["2018-08-01", "2018-09-01"]),
        (2019, ["2019-01-01", "2019-02-01"]),
    ):
        xr.Dataset(
            {
                "watermask": xr.DataArray(
                    np.ones((len(times), 1, 1), dtype=np.float32),
                    dims=("time", "lat", "lon"),
                    coords={"time": pd.to_datetime(times), "lat": [0.5], "lon": [100.5]},
                )
            }
        ).to_netcdf(standardized_dir / f"berkeley_rwawc_{year}.nc")

    recorded: dict[str, object] = {}

    def fake_open_phase4_dataset(
        dataset_id,
        *,
        bbox,
        time_range,
        standardized_dir,
        topmodel_raw_path,
    ):
        recorded["dataset_id"] = dataset_id
        recorded["bbox"] = bbox
        recorded["time_range"] = time_range
        dataset = xr.Dataset(
            {
                "watermask": xr.DataArray(
                    np.array([[[1.0]]], dtype=np.float32),
                    dims=("time", "lat", "lon"),
                    coords={
                        "time": pd.to_datetime([time_range[0]]),
                        "lat": [0.5],
                        "lon": [100.5],
                    },
                )
            }
        )
        dataset = dataset.rio.write_crs("EPSG:4326", inplace=False)
        dataset = dataset.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
        return dataset

    monkeypatch.setattr(phase4_regional_module, "_open_phase4_dataset", fake_open_phase4_dataset)

    region = Phase4Region(
        region_id="amazon",
        label="Amazon",
        label_zh="亚马孙",
        bbox=(99.5, -0.5, 101.5, 1.5),
        kind="priority_region",
        priority=1,
        is_priority_region=True,
    )
    mask = build_or_load_phase4_berkeley_valid_mask(
        region=region,
        output_root=tmp_path / "results",
        standardized_dir=standardized_dir,
        time_range=("2017-01-01", "2017-12-31"),
        skip_existing=False,
    )

    assert recorded["dataset_id"] == "berkeley_rwawc"
    assert recorded["bbox"] == region.bbox
    assert recorded["time_range"] == ("2018-08-01", "2018-08-01")
    assert np.array_equal(mask.values, np.array([[1.0]], dtype=np.float32))


def test_open_phase4_dataset_passes_bbox_to_berkeley_open_time_series(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    class DummyLoader:
        def open_time_series(self, *, bbox=None, time_range=None):
            recorded["bbox"] = bbox
            recorded["time_range"] = time_range
            dataset = xr.Dataset(
                {
                    "watermask": xr.DataArray(
                        np.array([[[1.0]]], dtype=np.float32),
                        dims=("time", "lat", "lon"),
                        coords={
                            "time": pd.to_datetime(["2016-01-01"]),
                            "lat": [0.5],
                            "lon": [100.5],
                        },
                    )
                }
            )
            dataset = dataset.rio.write_crs("EPSG:4326", inplace=False)
            dataset = dataset.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
            return dataset

    monkeypatch.setattr(
        phase4_regional_module,
        "resolve_phase4_dataset_config",
        lambda *args, **kwargs: {"loader_type": "standardized_netcdf"},
    )
    monkeypatch.setattr(
        phase4_regional_module,
        "get_loader",
        lambda dataset_id, config: DummyLoader(),
    )

    bbox = (100.0, 0.0, 101.0, 1.0)
    dataset = phase4_regional_module._open_phase4_dataset(
        "berkeley_rwawc",
        bbox=bbox,
        time_range=("2016-01-01", "2016-12-31"),
        standardized_dir=Path("/tmp/standardized"),
        topmodel_raw_path=None,
    )
    try:
        assert recorded["bbox"] == bbox
        assert recorded["time_range"] == ("2016-01-01", "2016-12-31")
        assert "watermask" in dataset
    finally:
        close = getattr(dataset, "close", None)
        if callable(close):
            close()


def test_load_phase4_gwd30_staged_tiles_restores_manifest_entries(tmp_path: Path) -> None:
    standardized_dir = tmp_path / "standardized"
    staging_root = standardized_dir / "_staging" / "gwd30_2013"
    tile_dir = staging_root / "tile_partials"
    tile_dir.mkdir(parents=True)
    tile_path = tile_dir / "tile_demo.nc"
    tile_path.touch()
    (staging_root / "stage_shard_0000_of_0064.json").write_text(
        (
            '{\n'
            '  "staged_tiles": [\n'
            f'    {{"path": "{tile_path}", "bbox": [100.0, 0.0, 101.0, 1.0]}}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    restored = load_phase4_gwd30_staged_tiles(standardized_dir, year=2013)

    assert restored == [(tile_path, (100.0, 0.0, 101.0, 1.0))]


def test_load_phase4_gwd30_staged_tiles_from_manifest_paths_deduplicates(tmp_path: Path) -> None:
    standardized_dir = tmp_path / "standardized"
    staging_root = standardized_dir / "_staging" / "gwd30_2013"
    tile_dir = staging_root / "tile_partials"
    tile_dir.mkdir(parents=True)
    tile_path = tile_dir / "tile_demo.nc"
    tile_path.touch()
    manifest_a = staging_root / "stage_shard_0000_of_0002.json"
    manifest_b = staging_root / "stage_shard_0001_of_0002.json"
    payload = (
        '{\n'
        '  "staged_tiles": [\n'
        f'    {{"path": "{tile_path}", "bbox": [100.0, 0.0, 101.0, 1.0]}}\n'
        "  ]\n"
        "}\n"
    )
    manifest_a.write_text(payload, encoding="utf-8")
    manifest_b.write_text(payload, encoding="utf-8")

    manifest_paths = list_phase4_gwd30_stage_shard_manifests(standardized_dir, year=2013)
    restored = load_phase4_gwd30_staged_tiles_from_manifest_paths(manifest_paths)

    assert manifest_paths == [manifest_a, manifest_b]
    assert restored == [(tile_path, (100.0, 0.0, 101.0, 1.0))]


def test_build_phase4_gwd30_tropical_tile_index_for_staged_tiles_filters_tropics(
    tmp_path: Path,
) -> None:
    in_tropics = tmp_path / "tile_a.nc"
    out_of_tropics = tmp_path / "tile_b.nc"
    in_tropics.touch()
    out_of_tropics.touch()

    tile_index = build_phase4_gwd30_tropical_tile_index_for_staged_tiles(
        year=2013,
        staged_tiles=[
            (in_tropics, (100.0, 0.0, 101.0, 1.0)),
            (out_of_tropics, (100.0, 40.0, 101.0, 41.0)),
        ],
    )

    assert tile_index["tile_id"].tolist() == ["tile_a"]
    assert tile_index["stage_path"].tolist() == [str(in_tropics)]


def test_build_phase4_gwd30_tropical_monthly_tile_from_stage_file_uses_mask_subset(
    tmp_path: Path,
) -> None:
    tile_path = tmp_path / "tile_demo.nc"
    mask_path = tmp_path / "joint_valid_mask.nc"

    times = pd.date_range("2013-01-01", periods=12, freq="MS")
    weighted = xr.DataArray(
        np.full((12, 1, 1, 2), 0.5, dtype=np.float32),
        dims=("time", "class_id", "lat", "lon"),
        coords={"time": times, "class_id": [8], "lat": [0.5], "lon": [100.5, 101.5]},
        name="weighted",
    )
    coverage = xr.DataArray(
        np.ones((12, 1, 2), dtype=np.float32),
        dims=("time", "lat", "lon"),
        coords={"time": times, "lat": [0.5], "lon": [100.5, 101.5]},
        name="coverage",
    )
    xr.Dataset({"weighted": weighted, "coverage": coverage}).to_netcdf(tile_path)

    mask = xr.DataArray(
        np.array([[1.0, 0.0]], dtype=np.float32),
        coords={"lat": [0.5], "lon": [100.5, 101.5]},
        dims=("lat", "lon"),
        name="joint_valid_mask",
    )
    xr.Dataset({"joint_valid_mask": mask}).to_netcdf(mask_path)

    monthly = build_phase4_gwd30_tropical_monthly_tile_from_stage_file(
        stage_path=tile_path,
        stage_bbox=(100.0, 0.0, 102.0, 1.0),
        time_range=("2013-01-01", "2013-12-31"),
        phase36_mask_path=mask_path,
    )

    assert len(monthly) == 12
    assert np.allclose(monthly["wetland_percentage"].to_numpy(dtype=float), 50.0)


def test_build_phase4_gwd30_reduced_tile_index_for_staged_tiles_writes_reduced_tiles(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tile_path = tmp_path / "tile_demo.nc"
    times = pd.date_range("2013-01-01", periods=2, freq="4D")
    weighted = xr.DataArray(
        np.full((2, 2, 1, 1), 0.25, dtype=np.float32),
        dims=("time", "class_id", "lat", "lon"),
        coords={"time": times, "class_id": [0, 8], "lat": [0.5], "lon": [100.5]},
        name="weighted",
    )
    coverage = xr.DataArray(
        np.ones((2, 1, 1), dtype=np.float32),
        dims=("time", "lat", "lon"),
        coords={"time": times, "lat": [0.5], "lon": [100.5]},
        name="coverage",
    )
    xr.Dataset({"weighted": weighted, "coverage": coverage}).to_netcdf(tile_path)

    monkeypatch.setattr(
        "WA.comparison.phase4_regional.get_dataset_config",
        lambda _dataset: {
            "name": "GWD30",
            "loader_type": "gwd30",
            "path": str(tmp_path),
        },
    )

    output_dir = tmp_path / "reduced"
    reduced_index = build_phase4_gwd30_reduced_tile_index_for_staged_tiles(
        year=2013,
        staged_tiles=[(tile_path, (100.0, 0.0, 101.0, 1.0))],
        output_dir=output_dir,
        skip_existing=False,
        worker_count=1,
        show_progress=False,
    )

    assert reduced_index["tile_id"].tolist() == ["tile_demo"]
    reduced_path = Path(reduced_index.loc[0, "reduced_path"])
    assert reduced_path.is_file()
    reduced = xr.open_dataset(reduced_path)
    try:
        assert set(reduced.data_vars) == {"wetland_weighted", "coverage"}
        assert reduced["wetland_weighted"].shape == (2, 1, 1)
    finally:
        reduced.close()


def test_build_phase4_gwd30_tropical_monthly_tile_from_reduced_file_uses_mask_subset(
    tmp_path: Path,
) -> None:
    reduced_path = tmp_path / "tile_demo.nc"
    mask_path = tmp_path / "joint_valid_mask.nc"

    times = pd.date_range("2013-01-01", periods=12, freq="MS")
    xr.Dataset(
        {
            "wetland_weighted": xr.DataArray(
                np.full((12, 1, 2), 0.5, dtype=np.float32),
                dims=("time", "lat", "lon"),
                coords={"time": times, "lat": [0.5], "lon": [100.5, 101.5]},
            ),
            "coverage": xr.DataArray(
                np.ones((12, 1, 2), dtype=np.float32),
                dims=("time", "lat", "lon"),
                coords={"time": times, "lat": [0.5], "lon": [100.5, 101.5]},
            ),
        }
    ).to_netcdf(reduced_path)

    mask = xr.DataArray(
        np.array([[1.0, 0.0]], dtype=np.float32),
        coords={"lat": [0.5], "lon": [100.5, 101.5]},
        dims=("lat", "lon"),
        name="joint_valid_mask",
    )
    xr.Dataset({"joint_valid_mask": mask}).to_netcdf(mask_path)

    monthly = build_phase4_gwd30_tropical_monthly_tile_from_reduced_file(
        reduced_path=reduced_path,
        tile_bbox=(100.0, 0.0, 102.0, 1.0),
        time_range=("2013-01-01", "2013-12-31"),
        phase36_mask_path=mask_path,
    )

    assert len(monthly) == 12
    assert np.allclose(monthly["wetland_percentage"].to_numpy(dtype=float), 50.0)


def test_build_or_load_phase4_gwd30_tropical_tile_cache_writes_year_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    standardized_dir = tmp_path / "standardized"
    staging_root = standardized_dir / "_staging" / "gwd30_2013"
    tile_dir = staging_root / "tile_partials"
    tile_dir.mkdir(parents=True)
    tile_path = tile_dir / "tile_demo.nc"

    times = pd.date_range("2013-01-01", periods=12, freq="MS")
    weighted = xr.DataArray(
        np.full((12, 1, 1, 1), 0.25, dtype=np.float32),
        dims=("time", "class_id", "lat", "lon"),
        coords={"time": times, "class_id": [8], "lat": [0.5], "lon": [100.5]},
        name="weighted",
    )
    coverage = xr.DataArray(
        np.ones((12, 1, 1), dtype=np.float32),
        dims=("time", "lat", "lon"),
        coords={"time": times, "lat": [0.5], "lon": [100.5]},
        name="coverage",
    )
    xr.Dataset({"weighted": weighted, "coverage": coverage}).to_netcdf(tile_path)
    (staging_root / "stage_shard_0000_of_0064.json").write_text(
        (
            '{\n'
            '  "staged_tiles": [\n'
            f'    {{"path": "{tile_path}", "bbox": [100.0, 0.0, 101.0, 1.0]}}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "WA.comparison.phase4_regional.get_dataset_config",
        lambda _dataset: {"years": [2013]},
    )

    base_mask = xr.DataArray(
        np.array([[1.0]], dtype=np.float32),
        coords={"lat": [0.5], "lon": [100.5]},
        dims=("lat", "lon"),
        name="shared_mask_fraction",
    )
    base_mask = base_mask.rio.write_crs("EPSG:4326", inplace=False)
    base_mask = base_mask.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)

    cache = build_or_load_phase4_gwd30_tropical_tile_cache(
        base_mask=base_mask,
        output_root=tmp_path / "results",
        standardized_dir=standardized_dir,
        time_range=("2013-01-01", "2013-12-31"),
        skip_existing=False,
        show_progress=False,
    )

    cache_path = phase4_gwd30_tropical_tile_cache_path(
        output_root=tmp_path / "results",
        year=2013,
    )
    assert cache_path.is_file()
    assert cache["tile_id"].tolist() == ["tile_demo"] * 12
    assert np.allclose(cache["wetland_percentage"].to_numpy(dtype=float), 25.0)


def test_build_phase4_gwd30_monthly_series_from_tropical_tile_cache_filters_tiles() -> None:
    tile_cache = pd.DataFrame(
        {
            "time": pd.to_datetime(["2013-01-01", "2013-01-01", "2013-02-01", "2013-02-01"]),
            "year": [2013, 2013, 2013, 2013],
            "month": [1, 1, 2, 2],
            "tile_id": ["tile_a", "tile_b", "tile_a", "tile_b"],
            "stage_path": ["a.nc", "b.nc", "a.nc", "b.nc"],
            "tile_west": [100.0, 120.0, 100.0, 120.0],
            "tile_south": [0.0, 0.0, 0.0, 0.0],
            "tile_east": [101.0, 121.0, 101.0, 121.0],
            "tile_north": [1.0, 1.0, 1.0, 1.0],
            "wetland_area_km2": [10.0, 999.0, 20.0, 999.0],
            "valid_area_km2": [20.0, 999.0, 40.0, 999.0],
            "wetland_percentage": [50.0, 100.0, 50.0, 100.0],
            "observation_count": [1, 1, 1, 1],
        }
    )
    region = Phase4Region(
        region_id="demo_region",
        label="Demo",
        label_zh="示例",
        bbox=(99.5, -0.5, 101.5, 1.5),
        kind="priority_region",
        priority=1,
        is_priority_region=True,
    )

    monthly = build_phase4_gwd30_monthly_series_from_tropical_tile_cache(
        tropical_tile_cache=tile_cache,
        region=region,
    )

    assert monthly["month"].tolist() == [1, 2]
    assert np.allclose(monthly["wetland_percentage"].to_numpy(dtype=float), [50.0, 50.0])
    assert monthly["observation_count"].tolist() == [1, 1]


def test_build_phase4_gwd30_monthly_tile_from_pixel_stats_file_uses_mask_subset(
    tmp_path: Path,
) -> None:
    tile_path = tmp_path / "tile_demo.nc"

    wetland_fraction = xr.DataArray(
        np.array(
            [
                [[0.25]],
                [[0.75]],
            ],
            dtype=np.float32,
        ),
        dims=("time", "lat", "lon"),
        coords={
            "time": pd.to_datetime(["2013-01-01", "2013-02-01"]),
            "lat": [0.5],
            "lon": [100.5],
        },
        name="wetland_fraction",
    )
    cell_area = xr.DataArray(
        np.array([[10.0]], dtype=np.float32),
        coords={"lat": [0.5], "lon": [100.5]},
        dims=("lat", "lon"),
        name="cell_area_km2",
    )
    xr.Dataset(
        {
            "wetland_fraction": wetland_fraction,
            "cell_area_km2": cell_area,
        }
    ).to_netcdf(tile_path)

    region_mask = xr.DataArray(
        np.array([[0.5]], dtype=np.float32),
        coords={"lat": [0.5], "lon": [100.5]},
        dims=("lat", "lon"),
        name="shared_mask_fraction",
    )
    region_mask = region_mask.rio.write_crs("EPSG:4326", inplace=False)
    region_mask = region_mask.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)

    monthly_tile = build_phase4_gwd30_monthly_tile_from_pixel_stats_file(
        tile_path=tile_path,
        tile_bbox=(100.0, 0.0, 101.0, 1.0),
        time_range=("2013-01-01", "2013-12-31"),
        region_mask=region_mask,
    )

    assert monthly_tile["month"].tolist() == [1, 2]
    assert np.allclose(
        monthly_tile["wetland_area_km2"].to_numpy(dtype=float),
        [1.25, 3.75],
    )
    assert np.allclose(
        monthly_tile["valid_area_km2"].to_numpy(dtype=float),
        [5.0, 5.0],
    )
    assert np.allclose(
        monthly_tile["wetland_percentage"].to_numpy(dtype=float),
        [25.0, 75.0],
    )


def test_build_phase4_gwd30_monthly_series_from_pixel_stats_tiles(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "results"
    tiles_dir = output_root / "pixel_stats" / "gwd30" / "gwd30_2013" / "monthly" / "tiles"
    tiles_dir.mkdir(parents=True)
    tile_path = tiles_dir / "tile_demo.nc"

    wetland_fraction = xr.DataArray(
        np.array(
            [
                [[0.25]],
                [[0.75]],
            ],
            dtype=np.float32,
        ),
        dims=("time", "lat", "lon"),
        coords={
            "time": pd.to_datetime(["2013-01-01", "2013-02-01"]),
            "lat": [0.5],
            "lon": [100.5],
        },
        name="wetland_fraction",
    )
    cell_area = xr.DataArray(
        np.array([[10.0]], dtype=np.float32),
        coords={"lat": [0.5], "lon": [100.5]},
        dims=("lat", "lon"),
        name="cell_area_km2",
    )
    xr.Dataset(
        {
            "wetland_fraction": wetland_fraction,
            "cell_area_km2": cell_area,
        }
    ).to_netcdf(tile_path)
    manifest_path = phase4_gwd30_pixel_stats_manifest_path(output_root=output_root, year=2013)
    manifest_path.write_text(
        (
            "{\n"
            '  "year": 2013,\n'
            '  "aggregation": "monthly",\n'
            '  "tile_count": 1,\n'
            f'  "output_dir": "{tiles_dir}",\n'
            '  "tiles": [\n'
            f'    {{"path": "{tile_path}", "bbox": [100.0, 0.0, 101.0, 1.0]}}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "WA.comparison.phase4_regional.get_dataset_config",
        lambda _dataset: {"years": [2013]},
    )

    base_mask = xr.DataArray(
        np.array([[1.0]], dtype=np.float32),
        coords={"lat": [0.5], "lon": [100.5]},
        dims=("lat", "lon"),
        name="shared_mask_fraction",
    )
    base_mask = base_mask.rio.write_crs("EPSG:4326", inplace=False)
    base_mask = base_mask.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    region = Phase4Region(
        region_id="demo_region",
        label="Demo",
        label_zh="示例",
        bbox=(100.0, 0.0, 101.0, 1.0),
        kind="priority_region",
        priority=1,
        is_priority_region=True,
    )

    monthly = build_phase4_gwd30_monthly_series_from_pixel_stats_tiles(
        region=region,
        region_mask=base_mask,
        output_root=output_root,
        time_range=("2013-01-01", "2013-12-31"),
        skip_existing=False,
        show_progress=False,
    )

    assert monthly["month"].tolist() == [1, 2]
    assert np.allclose(monthly["wetland_percentage"].to_numpy(dtype=float), [25.0, 75.0])
    assert (
        output_root
        / "cache"
        / "gwd30"
        / "demo_region"
        / "years"
        / "regional_series_2013.csv"
    ).is_file()


def test_compute_phase4_region_dataset_table_gwd30_uses_pixel_stats_tiles(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "results"
    tiles_dir = output_root / "pixel_stats" / "gwd30" / "gwd30_2013" / "monthly" / "tiles"
    tiles_dir.mkdir(parents=True)
    tile_path = tiles_dir / "tile_demo.nc"

    wetland_fraction = xr.DataArray(
        np.full((12, 1, 1), 0.5, dtype=np.float32),
        dims=("time", "lat", "lon"),
        coords={
            "time": pd.date_range("2013-01-01", periods=12, freq="MS"),
            "lat": [0.5],
            "lon": [100.5],
        },
        name="wetland_fraction",
    )
    cell_area = xr.DataArray(
        np.array([[10.0]], dtype=np.float32),
        coords={"lat": [0.5], "lon": [100.5]},
        dims=("lat", "lon"),
        name="cell_area_km2",
    )
    xr.Dataset(
        {
            "wetland_fraction": wetland_fraction,
            "cell_area_km2": cell_area,
        }
    ).to_netcdf(tile_path)
    manifest_path = phase4_gwd30_pixel_stats_manifest_path(output_root=output_root, year=2013)
    manifest_path.write_text(
        (
            "{\n"
            '  "year": 2013,\n'
            '  "aggregation": "monthly",\n'
            '  "tile_count": 1,\n'
            f'  "output_dir": "{tiles_dir}",\n'
            '  "tiles": [\n'
            f'    {{"path": "{tile_path}", "bbox": [100.0, 0.0, 101.0, 1.0]}}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "WA.comparison.phase4_regional.get_dataset_config",
        lambda _dataset: {"years": [2013]},
    )

    base_mask = xr.DataArray(
        np.array([[1.0]], dtype=np.float32),
        coords={"lat": [0.5], "lon": [100.5]},
        dims=("lat", "lon"),
        name="shared_mask_fraction",
    )
    base_mask = base_mask.rio.write_crs("EPSG:4326", inplace=False)
    base_mask = base_mask.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    region = Phase4Region(
        region_id="demo_region",
        label="Demo",
        label_zh="示例",
        bbox=(100.0, 0.0, 101.0, 1.0),
        kind="priority_region",
        priority=1,
        is_priority_region=True,
    )

    table = compute_phase4_region_dataset_table(
        "gwd30",
        region=region,
        base_mask=base_mask,
        output_root=output_root,
        standardized_dir=tmp_path / "standardized",
        time_range=("2013-01-01", "2013-12-31"),
        skip_existing=False,
        show_progress=False,
    )

    annual = table.loc[table["series_type"] == "annual"].reset_index(drop=True)
    assert len(annual) == 1
    assert annual.loc[0, "wetland_percentage"] == 50.0
    assert (output_root / "cache" / "gwd30" / "demo_region" / "regional_series.csv").is_file()
    assert (
        output_root
        / "cache"
        / "gwd30"
        / "demo_region"
        / "years"
        / "regional_series_2013.csv"
    ).is_file()


def test_compute_phase4_region_dataset_table_gwd30_merges_existing_year_caches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "results"
    year_cache_dir = output_root / "cache" / "gwd30" / "demo_region" / "years"
    year_cache_dir.mkdir(parents=True)

    pd.DataFrame(
        {
            "time": pd.to_datetime(["2013-01-01", "2013-02-01"]),
            "year": [2013, 2013],
            "month": [1, 2],
            "wetland_area_km2": [10.0, 20.0],
            "valid_area_km2": [20.0, 40.0],
            "wetland_percentage": [50.0, 50.0],
            "observation_count": [3, 3],
        }
    ).to_csv(year_cache_dir / "regional_series_2013.csv", index=False)
    pd.DataFrame(
        {
            "time": pd.to_datetime(["2014-01-01", "2014-02-01"]),
            "year": [2014, 2014],
            "month": [1, 2],
            "wetland_area_km2": [30.0, 40.0],
            "valid_area_km2": [60.0, 80.0],
            "wetland_percentage": [50.0, 50.0],
            "observation_count": [4, 4],
        }
    ).to_csv(year_cache_dir / "regional_series_2014.csv", index=False)

    monkeypatch.setattr(
        "WA.comparison.phase4_regional.get_dataset_config",
        lambda _dataset: {"years": [2013, 2014]},
    )

    base_mask = xr.DataArray(
        np.array([[1.0]], dtype=np.float32),
        coords={"lat": [0.5], "lon": [100.5]},
        dims=("lat", "lon"),
        name="shared_mask_fraction",
    )
    base_mask = base_mask.rio.write_crs("EPSG:4326", inplace=False)
    base_mask = base_mask.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    region = Phase4Region(
        region_id="demo_region",
        label="Demo",
        label_zh="示例",
        bbox=(100.0, 0.0, 101.0, 1.0),
        kind="priority_region",
        priority=1,
        is_priority_region=True,
    )

    table = compute_phase4_region_dataset_table(
        "gwd30",
        region=region,
        base_mask=base_mask,
        output_root=output_root,
        standardized_dir=tmp_path / "standardized",
        time_range=("2013-01-01", "2014-12-31"),
        skip_existing=True,
        show_progress=False,
    )

    monthly = table.loc[table["series_type"] == "monthly"].reset_index(drop=True)
    assert monthly["year"].tolist() == [2013.0, 2013.0, 2014.0, 2014.0]
    assert np.allclose(
        monthly["wetland_percentage"].to_numpy(dtype=float),
        [50.0, 50.0, 50.0, 50.0],
    )
    assert (output_root / "cache" / "gwd30" / "demo_region" / "regional_series.csv").is_file()



def _load_script_module(script_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(
        f"test_{script_name.replace('.', '_')}",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_phase4_regional_help_mentions_contract_subset_and_legacy_default() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/run_phase4_regional.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "--subset" in completed.stdout
    assert "canonical" in completed.stdout
    assert "ten" in completed.stdout
    assert "macro+priority" in completed.stdout
    assert "all-region run" in completed.stdout


def test_run_phase4_regional_resolve_cli_region_ids_preserves_legacy_default_and_ten_subset(
) -> None:
    module = _load_script_module("run_phase4_regional.py")

    legacy_region_ids, legacy_mode = module.resolve_cli_region_ids(
        regions_file=Path("config/priority_regions.yaml"),
        requested_subset=None,
        requested_region_ids=[],
    )
    ten_region_ids, ten_mode = module.resolve_cli_region_ids(
        regions_file=Path("config/priority_regions.yaml"),
        requested_subset="ten",
        requested_region_ids=[],
    )

    assert legacy_mode == "legacy-all-regions"
    assert legacy_region_ids[0] == "pan_trop_subtrop"
    assert len(legacy_region_ids) == 16
    assert ten_mode == "contract-subset:ten"
    assert ten_region_ids == EXPECTED_TEN_REGION_IDS


@pytest.mark.parametrize(
    ("script_name", "extra_args"),
    [
        ("run_phase4_trend_contract.py", []),
        ("run_phase4_hotspot_ledger.py", []),
    ],
)
def test_contract_cli_rejects_subset_and_region_together(
    tmp_path: Path,
    script_name: str,
    extra_args: list[str],
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            f"scripts/{script_name}",
            "--output-root",
            str(tmp_path),
            "--subset",
            "ten",
            "--region",
            "amazon",
            *extra_args,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "Ambiguous region selector" in (completed.stderr + completed.stdout)


@pytest.mark.parametrize(
    "script_name",
    ["run_phase4_trend_contract.py", "run_phase4_hotspot_ledger.py"],
)
def test_contract_cli_help_mentions_ten_subset(script_name: str) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, f"scripts/{script_name}", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "--subset" in completed.stdout
    assert "canonical" in completed.stdout
    assert "ten" in completed.stdout


def test_run_phase4_regional_main_logs_resolved_ten_subset(
    tmp_path: Path,
    monkeypatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    module = _load_script_module("run_phase4_regional.py")

    monkeypatch.setattr(
        module,
        "build_or_load_phase4_berkeley_valid_mask",
        lambda **kwargs: "mask",
    )
    monkeypatch.setattr(
        module,
        "compute_phase4_region_dataset_table",
        lambda dataset_id, **kwargs: pd.DataFrame({"dataset_id": [dataset_id]}),
    )
    monkeypatch.setattr(
        module,
        "build_phase4_region_table",
        lambda *, region, dataset_tables, output_root: output_root / f"{region.region_id}.csv",
    )

    with caplog.at_level(logging.INFO):
        module.main(
            [
                "--subset",
                "ten",
                "--dataset-id",
                "wad2m",
                "--output-root",
                str(tmp_path),
                "--standardized-dir",
                str(tmp_path),
                "--start-year",
                "2016",
                "--end-year",
                "2016",
                "--no-progress",
            ]
        )

    assert "stage=region-selector subset=ten selector_mode=contract-subset:ten" in caplog.text
    assert "amazon" in caplog.text
    assert "northernaus" in caplog.text
