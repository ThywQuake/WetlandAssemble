from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.config import AppConfig
from WA.loaders.base import BBox, DatasetLoader, DatasetMetadata, TimeRange
from WA.rough_probe import (
    PreparedRoughDataset,
    RoughDatasetProbeResult,
    RoughProbeOptions,
    RoughProbeRunResult,
    derive_target_time,
    options_from_args,
    probe_prepared_dataset,
    render_rough_probe_report,
    run_rough_probe,
)


class DummyRoughLoader(DatasetLoader):
    def __init__(
        self,
        dataset_id: str,
        config: dict[str, object],
        dataset: xr.Dataset,
        *,
        metadata: DatasetMetadata,
    ) -> None:
        super().__init__(dataset_id, config)
        self._dataset = dataset
        self._metadata = metadata

    def load(
        self,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
    ) -> xr.Dataset:
        return self._dataset

    def metadata(self) -> DatasetMetadata:
        return self._metadata


def build_app_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        datasets={},
        regions={"tropical": {"bbox": [-180, -23.5, 180, 23.5]}},
        analysis={},
        gee={"gee_project_id": "demo-project"},
        dataset_config_path=tmp_path / "datasets.yaml",
        gee_config_path=tmp_path / "gee.yaml",
    )


def test_derive_target_time_prefers_earliest_month_with_max_participants() -> None:
    metadata_by_dataset = {
        "swamps": DatasetMetadata(
            dataset_id="swamps",
            name="SWAMPS",
            source_path=".",
            crs="EPSG:4326",
            spatial_resolution="0.25deg",
            temporal_coverage=("1992-01-01", "2020-12-31"),
            time_resolution="daily",
            is_static=False,
            is_classification=False,
        ),
        "giems_mc": DatasetMetadata(
            dataset_id="giems_mc",
            name="GIEMS-MC",
            source_path=".",
            crs="EPSG:4326",
            spatial_resolution="0.25deg",
            temporal_coverage=("1993-01-01", "2007-12-31"),
            time_resolution="monthly",
            is_static=False,
            is_classification=False,
        ),
        "gwd30": DatasetMetadata(
            dataset_id="gwd30",
            name="GWD30",
            source_path=".",
            crs="EPSG:4326",
            spatial_resolution="30m",
            temporal_coverage=("2013-01-01", "2022-12-31"),
            time_resolution="4-day",
            is_static=False,
            is_classification=True,
        ),
    }

    target_time, label = derive_target_time(metadata_by_dataset, requested_target_time=None)

    assert target_time == pd.Timestamp("2000-03-01")
    assert label == "derived_max_dynamic_participants"


def test_options_from_args_uses_cli_target_time_if_provided(tmp_path: Path) -> None:
    app_config = build_app_config(tmp_path)
    metadata_by_dataset = {
        "swamps": DatasetMetadata(
            dataset_id="swamps",
            name="SWAMPS",
            source_path=".",
            crs="EPSG:4326",
            spatial_resolution="0.25deg",
            temporal_coverage=("1992-01-01", "2020-12-31"),
            time_resolution="daily",
            is_static=False,
            is_classification=False,
        )
    }

    args = type(
        "Args",
        (),
        {
            "bbox": None,
            "region": None,
            "target_time": "2019-07-19",
            "resolution_deg": 0.25,
            "aggregation": "mean",
            "top_n": 8,
            "top_n_per_region": 2,
            "aoi_size_deg": 2.0,
            "min_distance_deg": 3.0,
            "preview_items": 5,
            "download_modis": False,
            "allow_interactive_auth": False,
            "results_root": "results",
            "fail_fast": False,
        },
    )()

    options = options_from_args(args, app_config, metadata_by_dataset)

    assert options.target_time == pd.Timestamp("2019-07-01")
    assert options.target_time_label == "cli_target_time"


def test_probe_prepared_dataset_reports_participating_surface(tmp_path: Path) -> None:
    dataset = xr.Dataset(
        {
            "wetland_fraction": (
                ("time", "lat", "lon"),
                np.array([[[0.9, 0.2], [0.1, 0.6]]], dtype=np.float32),
            )
        },
        coords={
            "time": pd.to_datetime(["2001-01-01"]),
            "lat": [0.5, -0.5],
            "lon": [100.5, 101.5],
        },
    )
    metadata = DatasetMetadata(
        dataset_id="wad2m",
        name="WAD2M",
        source_path=str(tmp_path),
        crs="EPSG:4326",
        spatial_resolution="0.25deg",
        temporal_coverage=("2000-01-01", "2020-12-31"),
        time_resolution="monthly",
        is_static=False,
        is_classification=False,
    )
    prepared = PreparedRoughDataset(
        dataset_id="wad2m",
        dataset_config={"loader_type": "netcdf", "name": "WAD2M", "path": str(tmp_path)},
        loader=DummyRoughLoader(
            "wad2m",
            {"loader_type": "netcdf", "name": "WAD2M", "path": str(tmp_path)},
            dataset,
            metadata=metadata,
        ),
        metadata=metadata,
    )
    options = RoughProbeOptions(
        bbox=(-61.0, -6.0, -59.0, -4.0),
        bbox_label="test",
        target_time=pd.Timestamp("2001-01-01"),
        target_time_label="cli_target_time",
        resolution_deg=1.0,
        aggregation="mean",
        top_n=4,
        top_n_per_region=2,
        aoi_size_deg=1.0,
        min_distance_deg=1.0,
        preview_items=5,
        download_modis=False,
        allow_interactive_auth=False,
        results_root="results",
        fail_fast=False,
    )
    reference_grid = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        coords={"lat": [0.5, -0.5], "lon": [100.5, 101.5]},
        dims=("lat", "lon"),
        name="reference_grid",
    )
    reference_grid = reference_grid.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    reference_grid = reference_grid.rio.write_crs("EPSG:4326", inplace=False)

    result, surface = probe_prepared_dataset(prepared, options, reference_grid)

    assert result.status == "participating"
    assert result.comparison_source_variable == "wetland_fraction"
    assert result.harmonized_summary is not None
    assert result.harmonized_summary["wetland_cell_count"] == 2
    assert surface is not None


def test_probe_prepared_dataset_marks_empty_harmonized_surface_failed(tmp_path: Path) -> None:
    dataset = xr.Dataset(
        {
            "combined_classes": (
                ("lat", "lon"),
                np.array([[8.0]], dtype=np.float32),
            )
        },
        coords={"lat": [10.5], "lon": [10.5]},
    )
    metadata = DatasetMetadata(
        dataset_id="glwd_v2",
        name="GLWD v2",
        source_path=str(tmp_path),
        crs="EPSG:4326",
        spatial_resolution="15 arc-second",
        temporal_coverage=None,
        time_resolution=None,
        is_static=True,
        is_classification=True,
    )
    prepared = PreparedRoughDataset(
        dataset_id="glwd_v2",
        dataset_config={"loader_type": "glwd", "name": "GLWD v2", "path": str(tmp_path)},
        loader=DummyRoughLoader(
            "glwd_v2",
            {"loader_type": "glwd", "name": "GLWD v2", "path": str(tmp_path)},
            dataset,
            metadata=metadata,
        ),
        metadata=metadata,
    )
    options = RoughProbeOptions(
        bbox=(-61.0, -6.0, -59.0, -4.0),
        bbox_label="test",
        target_time=pd.Timestamp("2001-01-01"),
        target_time_label="cli_target_time",
        resolution_deg=1.0,
        aggregation="mean",
        top_n=4,
        top_n_per_region=2,
        aoi_size_deg=1.0,
        min_distance_deg=1.0,
        preview_items=5,
        download_modis=False,
        allow_interactive_auth=False,
        results_root="results",
        fail_fast=False,
    )
    reference_grid = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        coords={"lat": [0.5, -0.5], "lon": [100.5, 101.5]},
        dims=("lat", "lon"),
        name="reference_grid",
    )
    reference_grid = reference_grid.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    reference_grid = reference_grid.rio.write_crs("EPSG:4326", inplace=False)

    result, surface = probe_prepared_dataset(prepared, options, reference_grid)

    assert result.status == "failed_empty_harmonized_surface"
    assert result.error is not None
    assert "aligned_to_reference_grid" in result.error
    assert result.traceback_text is None
    assert result.comparison_source_variable == "combined_classes"
    assert surface is None


def test_probe_prepared_dataset_keeps_source_variable_for_empty_fraction_surface(
    tmp_path: Path,
) -> None:
    dataset = xr.Dataset(
        {
            "wetland_fraction": (
                ("time", "lat", "lon"),
                np.array([[[np.nan]]], dtype=np.float32),
            )
        },
        coords={
            "time": pd.to_datetime(["2019-07-01"]),
            "lat": [10.5],
            "lon": [10.5],
        },
    )
    metadata = DatasetMetadata(
        dataset_id="swamps",
        name="SWAMPS",
        source_path=str(tmp_path),
        crs="EPSG:4326",
        spatial_resolution="0.25deg",
        temporal_coverage=("1992-01-01", "2020-12-31"),
        time_resolution="daily",
        is_static=False,
        is_classification=False,
    )
    prepared = PreparedRoughDataset(
        dataset_id="swamps",
        dataset_config={"loader_type": "swamps", "name": "SWAMPS", "path": str(tmp_path)},
        loader=DummyRoughLoader(
            "swamps",
            {"loader_type": "swamps", "name": "SWAMPS", "path": str(tmp_path)},
            dataset,
            metadata=metadata,
        ),
        metadata=metadata,
    )
    options = RoughProbeOptions(
        bbox=(-61.0, -6.0, -59.0, -4.0),
        bbox_label="test",
        target_time=pd.Timestamp("2019-07-01"),
        target_time_label="cli_target_time",
        resolution_deg=1.0,
        aggregation="mean",
        top_n=4,
        top_n_per_region=2,
        aoi_size_deg=1.0,
        min_distance_deg=1.0,
        preview_items=5,
        download_modis=False,
        allow_interactive_auth=False,
        results_root="results",
        fail_fast=False,
    )
    reference_grid = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        coords={"lat": [0.5, -0.5], "lon": [100.5, 101.5]},
        dims=("lat", "lon"),
        name="reference_grid",
    )
    reference_grid = reference_grid.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    reference_grid = reference_grid.rio.write_crs("EPSG:4326", inplace=False)

    result, surface = probe_prepared_dataset(prepared, options, reference_grid)

    assert result.status == "failed_empty_harmonized_surface"
    assert result.comparison_source_variable == "wetland_fraction"
    assert result.error is not None
    assert "prepared_source" in result.error
    assert surface is None


def test_probe_prepared_dataset_uses_precomputed_gwd30_surface(tmp_path: Path) -> None:
    metadata = DatasetMetadata(
        dataset_id="gwd30",
        name="GWD30",
        source_path=str(tmp_path),
        crs="EPSG:4326",
        spatial_resolution="0.25deg",
        temporal_coverage=("2013-01-01", "2022-12-31"),
        time_resolution="4-day",
        is_static=False,
        is_classification=True,
    )
    prepared = PreparedRoughDataset(
        dataset_id="gwd30",
        dataset_config={"loader_type": "gwd30", "name": "GWD30", "path": str(tmp_path)},
        loader=DummyRoughLoader(
            "gwd30",
            {"loader_type": "gwd30", "name": "GWD30", "path": str(tmp_path)},
            xr.Dataset(),
            metadata=metadata,
        ),
        metadata=metadata,
    )
    surface_path = tmp_path / "gwd30_surface.nc"
    xr.Dataset(
        {
            "wetland_fraction": (
                ("lat", "lon"),
                np.array([[0.9, 0.1], [0.2, 0.8]], dtype=np.float32),
            )
        },
        coords={"lat": [0.5, -0.5], "lon": [100.5, 101.5]},
    ).to_netcdf(surface_path)

    options = RoughProbeOptions(
        bbox=(-61.0, -6.0, -59.0, -4.0),
        bbox_label="test",
        target_time=pd.Timestamp("2019-07-01"),
        target_time_label="cli_target_time",
        resolution_deg=1.0,
        aggregation="mean",
        top_n=4,
        top_n_per_region=2,
        aoi_size_deg=1.0,
        min_distance_deg=1.0,
        preview_items=5,
        download_modis=False,
        allow_interactive_auth=False,
        results_root="results",
        fail_fast=False,
        gwd30_surface_path=str(surface_path),
    )
    reference_grid = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        coords={"lat": [0.5, -0.5], "lon": [100.5, 101.5]},
        dims=("lat", "lon"),
        name="reference_grid",
    )
    reference_grid = reference_grid.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    reference_grid = reference_grid.rio.write_crs("EPSG:4326", inplace=False)

    result, surface = probe_prepared_dataset(prepared, options, reference_grid)

    assert result.status == "participating"
    assert result.dataset_summary == {
        "strategy": "precomputed_surface",
        "surface_path": str(surface_path),
    }
    assert surface is not None
    np.testing.assert_allclose(
        np.asarray(surface.values, dtype=np.float32),
        np.array([[0.9, 0.1], [0.2, 0.8]], dtype=np.float32),
    )


def test_probe_prepared_dataset_skips_time_window_before_discovery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dataset = xr.Dataset(
        {
            "wetland_fraction": (
                ("time", "lat", "lon"),
                np.array([[[0.9, 0.2], [0.1, 0.6]]], dtype=np.float32),
            )
        },
        coords={
            "time": pd.to_datetime(["2019-01-01"]),
            "lat": [0.5, -0.5],
            "lon": [100.5, 101.5],
        },
    )
    metadata = DatasetMetadata(
        dataset_id="gwd30",
        name="GWD30",
        source_path=str(tmp_path),
        crs="EPSG:4326",
        spatial_resolution="30m",
        temporal_coverage=("2013-01-01", "2022-12-31"),
        time_resolution="4-day",
        is_static=False,
        is_classification=True,
    )
    prepared = PreparedRoughDataset(
        dataset_id="gwd30",
        dataset_config={"loader_type": "gwd30", "name": "GWD30", "path": str(tmp_path)},
        loader=DummyRoughLoader(
            "gwd30",
            {"loader_type": "gwd30", "name": "GWD30", "path": str(tmp_path)},
            dataset,
            metadata=metadata,
        ),
        metadata=metadata,
    )
    options = RoughProbeOptions(
        bbox=(-61.0, -6.0, -59.0, -4.0),
        bbox_label="test",
        target_time=pd.Timestamp("2001-01-01"),
        target_time_label="cli_target_time",
        resolution_deg=1.0,
        aggregation="mean",
        top_n=4,
        top_n_per_region=2,
        aoi_size_deg=1.0,
        min_distance_deg=1.0,
        preview_items=5,
        download_modis=False,
        allow_interactive_auth=False,
        results_root="results",
        fail_fast=False,
    )
    reference_grid = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        coords={"lat": [0.5, -0.5], "lon": [100.5, 101.5]},
        dims=("lat", "lon"),
        name="reference_grid",
    )
    reference_grid = reference_grid.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    reference_grid = reference_grid.rio.write_crs("EPSG:4326", inplace=False)

    monkeypatch.setattr(
        "WA.rough_probe.collect_input_discovery",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("discovery should not run for skipped_time_window")
        ),
    )

    result, surface = probe_prepared_dataset(prepared, options, reference_grid)

    assert result.status == "skipped_time_window"
    assert result.discovery == {}
    assert surface is None


def test_probe_prepared_dataset_keeps_not_eligible_status_for_berkeley(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dataset = xr.Dataset(
        {
            "water_mask": (
                ("time", "lat", "lon"),
                np.array([[[1.0, 0.0], [0.0, 1.0]]], dtype=np.float32),
            )
        },
        coords={
            "time": pd.to_datetime(["2019-07-01"]),
            "lat": [0.5, -0.5],
            "lon": [100.5, 101.5],
        },
    )
    metadata = DatasetMetadata(
        dataset_id="berkeley_rwawc",
        name="Berkeley-RWAWC",
        source_path=str(tmp_path),
        crs="EPSG:4326",
        spatial_resolution="30m",
        temporal_coverage=("2018-08-01", "2025-10-01"),
        time_resolution="monthly",
        is_static=False,
        is_classification=False,
    )
    prepared = PreparedRoughDataset(
        dataset_id="berkeley_rwawc",
        dataset_config={"loader_type": "berkeley", "name": "Berkeley-RWAWC", "path": str(tmp_path)},
        loader=DummyRoughLoader(
            "berkeley_rwawc",
            {"loader_type": "berkeley", "name": "Berkeley-RWAWC", "path": str(tmp_path)},
            dataset,
            metadata=metadata,
        ),
        metadata=metadata,
    )
    options = RoughProbeOptions(
        bbox=(-61.0, -6.0, -59.0, -4.0),
        bbox_label="test",
        target_time=pd.Timestamp("2000-03-01"),
        target_time_label="cli_target_time",
        resolution_deg=1.0,
        aggregation="mean",
        top_n=4,
        top_n_per_region=2,
        aoi_size_deg=1.0,
        min_distance_deg=1.0,
        preview_items=5,
        download_modis=False,
        allow_interactive_auth=False,
        results_root="results",
        fail_fast=False,
    )
    reference_grid = xr.DataArray(
        np.zeros((2, 2), dtype=np.float32),
        coords={"lat": [0.5, -0.5], "lon": [100.5, 101.5]},
        dims=("lat", "lon"),
        name="reference_grid",
    )
    reference_grid = reference_grid.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    reference_grid = reference_grid.rio.write_crs("EPSG:4326", inplace=False)

    calls = {"discovery": 0}

    def counting_discovery(*args: object, **kwargs: object) -> dict[str, object]:
        calls["discovery"] += 1
        return {"path_exists": True}

    monkeypatch.setattr("WA.rough_probe.collect_input_discovery", counting_discovery)
    monkeypatch.setattr("WA.rough_probe.compact_discovery_summary", lambda discovery: discovery)
    monkeypatch.setattr("WA.rough_probe.compact_discovery_preview", lambda discovery: None)

    result, surface = probe_prepared_dataset(prepared, options, reference_grid)

    assert result.status == "skipped_not_eligible"
    assert calls["discovery"] == 1
    assert surface is None


def test_run_and_render_rough_probe_with_dummy_loaders(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app_config = AppConfig(
        datasets={
            "g2017": {"loader_type": "geotiff", "name": "G2017", "path": str(tmp_path)},
            "wad2m": {"loader_type": "netcdf", "name": "WAD2M", "path": str(tmp_path)},
            "swamps": {"loader_type": "swamps", "name": "SWAMPS", "path": str(tmp_path)},
        },
        regions={"tropical": {"bbox": [-180, -23.5, 180, 23.5]}},
        analysis={},
        gee={"gee_project_id": "demo-project"},
        dataset_config_path=tmp_path / "datasets.yaml",
        gee_config_path=tmp_path / "gee.yaml",
    )

    datasets = {
        "g2017": xr.Dataset(
            {
                "wetland_nolake": (
                    ("lat", "lon"),
                    np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
                )
            },
            coords={"lat": [-4.5, -5.5], "lon": [-60.5, -59.5]},
        ),
        "wad2m": xr.Dataset(
            {
                "wetland_fraction": (
                    ("time", "lat", "lon"),
                    np.array([[[0.9, 0.8], [0.1, 0.2]]], dtype=np.float32),
                )
            },
            coords={
                "time": pd.to_datetime(["2001-01-01"]),
                "lat": [-4.5, -5.5],
                "lon": [-60.5, -59.5],
            },
        ),
        "swamps": xr.Dataset(
            {
                "wetland_fraction": (
                    ("time", "lat", "lon"),
                    np.array([[[0.1, 0.8], [0.2, 0.2]]], dtype=np.float32),
                )
            },
            coords={
                "time": pd.to_datetime(["2001-01-01"]),
                "lat": [-4.5, -5.5],
                "lon": [-60.5, -59.5],
            },
        ),
    }
    metadata_by_dataset = {
        "g2017": DatasetMetadata(
            dataset_id="g2017",
            name="G2017",
            source_path=str(tmp_path),
            crs="EPSG:4326",
            spatial_resolution="0.05deg",
            temporal_coverage=None,
            time_resolution=None,
            is_static=True,
            is_classification=True,
        ),
        "wad2m": DatasetMetadata(
            dataset_id="wad2m",
            name="WAD2M",
            source_path=str(tmp_path),
            crs="EPSG:4326",
            spatial_resolution="0.25deg",
            temporal_coverage=("2000-01-01", "2020-12-31"),
            time_resolution="monthly",
            is_static=False,
            is_classification=False,
        ),
        "swamps": DatasetMetadata(
            dataset_id="swamps",
            name="SWAMPS",
            source_path=str(tmp_path),
            crs="EPSG:4326",
            spatial_resolution="0.25deg",
            temporal_coverage=("1992-01-01", "2020-12-31"),
            time_resolution="daily",
            is_static=False,
            is_classification=False,
        ),
    }

    def loader_factory(dataset_id: str, dataset_config: dict[str, object]) -> DummyRoughLoader:
        return DummyRoughLoader(
            dataset_id,
            dataset_config,
            datasets[dataset_id],
            metadata=metadata_by_dataset[dataset_id],
        )

    monkeypatch.setattr("WA.rough_probe.get_loader", loader_factory)

    options = RoughProbeOptions(
        bbox=(-61.0, -6.0, -59.0, -4.0),
        bbox_label="test",
        target_time=pd.Timestamp("2001-01-01"),
        target_time_label="cli_target_time",
        resolution_deg=1.0,
        aggregation="mean",
        top_n=2,
        top_n_per_region=1,
        aoi_size_deg=1.0,
        min_distance_deg=0.5,
        preview_items=3,
        download_modis=False,
        allow_interactive_auth=False,
        results_root="results",
        fail_fast=False,
    )

    run_result = run_rough_probe(app_config, ["g2017", "wad2m", "swamps"], options)
    report = render_rough_probe_report(
        app_config,
        ["g2017", "wad2m", "swamps"],
        options,
        run_result,
    )

    assert run_result.status == "completed"
    assert run_result.metrics_rows is not None
    assert run_result.focus_areas is not None
    assert "participant_datasets" in report
    assert "metrics:" in report
    assert "focus_areas:" in report


def test_render_rough_probe_report_omits_traceback_for_expected_domain_failures(
    tmp_path: Path,
) -> None:
    app_config = AppConfig(
        datasets={},
        regions={"tropical": {"bbox": [-180, -23.5, 180, 23.5]}},
        analysis={},
        gee={"gee_project_id": "demo-project"},
        dataset_config_path=tmp_path / "datasets.yaml",
        gee_config_path=tmp_path / "gee.yaml",
    )
    options = RoughProbeOptions(
        bbox=(-61.0, -6.0, -59.0, -4.0),
        bbox_label="test",
        target_time=pd.Timestamp("2001-01-01"),
        target_time_label="cli_target_time",
        resolution_deg=1.0,
        aggregation="mean",
        top_n=2,
        top_n_per_region=1,
        aoi_size_deg=1.0,
        min_distance_deg=0.5,
        preview_items=3,
        download_modis=False,
        allow_interactive_auth=False,
        results_root="results",
        fail_fast=False,
    )
    run_result = RoughProbeRunResult(
        status="failed",
        target_time=pd.Timestamp("2001-01-01"),
        modis_window=None,
        reference_grid_summary={"dims": ["lat", "lon"], "shape": [1, 1], "crs": "EPSG:4326"},
        dataset_results=[
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
                traceback_text="Traceback (most recent call last): ...",
                elapsed_seconds=0.1,
            )
        ],
        participant_dataset_ids=[],
        metrics_rows=None,
        disagreement_summary=None,
        focus_areas=None,
        modis_artifacts=None,
        warnings=[],
    )

    report = render_rough_probe_report(app_config, ["glwd_v2"], options, run_result)

    assert "glwd_v2 produced an empty binary surface from combined_classes" in report
    assert "traceback:" not in report


def test_run_rough_probe_marks_completed_with_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app_config = AppConfig(
        datasets={
            "g2017": {"loader_type": "geotiff", "name": "G2017", "path": str(tmp_path)},
            "swamps": {"loader_type": "swamps", "name": "SWAMPS", "path": str(tmp_path)},
            "wad2m": {"loader_type": "netcdf", "name": "WAD2M", "path": str(tmp_path)},
        },
        regions={"tropical": {"bbox": [-180, -23.5, 180, 23.5]}},
        analysis={},
        gee={"gee_project_id": "demo-project"},
        dataset_config_path=tmp_path / "datasets.yaml",
        gee_config_path=tmp_path / "gee.yaml",
    )

    good_datasets = {
        "g2017": xr.Dataset(
            {
                "wetland_nolake": (
                    ("lat", "lon"),
                    np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
                )
            },
            coords={"lat": [-4.5, -5.5], "lon": [-60.5, -59.5]},
        ),
        "swamps": xr.Dataset(
            {
                "wetland_fraction": (
                    ("time", "lat", "lon"),
                    np.array([[[0.2, 0.8], [0.1, 0.3]]], dtype=np.float32),
                )
            },
            coords={
                "time": pd.to_datetime(["2001-01-01"]),
                "lat": [-4.5, -5.5],
                "lon": [-60.5, -59.5],
            },
        ),
    }
    metadata_by_dataset = {
        "g2017": DatasetMetadata(
            dataset_id="g2017",
            name="G2017",
            source_path=str(tmp_path),
            crs="EPSG:4326",
            spatial_resolution="0.05deg",
            temporal_coverage=None,
            time_resolution=None,
            is_static=True,
            is_classification=True,
        ),
        "swamps": DatasetMetadata(
            dataset_id="swamps",
            name="SWAMPS",
            source_path=str(tmp_path),
            crs="EPSG:4326",
            spatial_resolution="0.25deg",
            temporal_coverage=("1992-01-01", "2020-12-31"),
            time_resolution="daily",
            is_static=False,
            is_classification=False,
        ),
        "wad2m": DatasetMetadata(
            dataset_id="wad2m",
            name="WAD2M",
            source_path=str(tmp_path),
            crs="EPSG:4326",
            spatial_resolution="0.25deg",
            temporal_coverage=("2000-01-01", "2020-12-31"),
            time_resolution="monthly",
            is_static=False,
            is_classification=False,
        ),
    }

    class FailingLoader(DummyRoughLoader):
        def load(
            self,
            bbox: BBox | None = None,
            time_range: TimeRange | None = None,
        ) -> xr.Dataset:
            raise KeyError("synthetic failure")

    def loader_factory(dataset_id: str, dataset_config: dict[str, object]) -> DatasetLoader:
        if dataset_id == "wad2m":
            return FailingLoader(
                dataset_id,
                dataset_config,
                good_datasets["swamps"],
                metadata=metadata_by_dataset[dataset_id],
            )
        return DummyRoughLoader(
            dataset_id,
            dataset_config,
            good_datasets[dataset_id],
            metadata=metadata_by_dataset[dataset_id],
        )

    monkeypatch.setattr("WA.rough_probe.get_loader", loader_factory)

    options = RoughProbeOptions(
        bbox=(-61.0, -6.0, -59.0, -4.0),
        bbox_label="test",
        target_time=pd.Timestamp("2001-01-01"),
        target_time_label="cli_target_time",
        resolution_deg=1.0,
        aggregation="mean",
        top_n=2,
        top_n_per_region=1,
        aoi_size_deg=1.0,
        min_distance_deg=0.5,
        preview_items=3,
        download_modis=False,
        allow_interactive_auth=False,
        results_root="results",
        fail_fast=False,
    )

    run_result = run_rough_probe(app_config, ["g2017", "swamps", "wad2m"], options)
    report = render_rough_probe_report(
        app_config,
        ["g2017", "swamps", "wad2m"],
        options,
        run_result,
    )

    assert run_result.status == "completed_with_failures"
    assert "failed_dataset_count: 1" in report
