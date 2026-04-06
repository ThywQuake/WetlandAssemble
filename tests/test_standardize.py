"""Tests for src/WA/standardize.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import rioxarray  # noqa: F401
import xarray as xr

from WA.standardize import (
    GridChunk,
    _bbox_from_reference_grid,
    _build_chunked_output,
    _build_encoding,
    _build_gwd30_output_from_staged_tiles,
    _chunk_parallel_worker_count,
    _clip_continuous,
    _filter_selected_years,
    _get_available_years,
    _grid_chunk_view,
    _load_gwd30_staged_tiles_from_stage_shard_manifests,
    _reproject_per_timestep,
    _resolve_parallel_worker_count,
    _sanitize_dataset_for_netcdf,
    _standardize_berkeley,
    _standardize_continuous_yearly,
    build_reference_grid,
    classification_to_fractions,
    glwd_ha_to_fractions,
    standardize_all,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reference_grid(
    lat_range: tuple[float, float] = (-1.0, 1.0),
    lon_range: tuple[float, float] = (-1.0, 1.0),
    resolution_deg: float = 0.5,
) -> xr.DataArray:
    """Build a small WGS84 reference grid for tests."""
    south, north = lat_range
    west, east = lon_range
    lats = np.arange(north, south, -resolution_deg, dtype=np.float64)
    lons = np.arange(west, east, resolution_deg, dtype=np.float64)
    grid = xr.DataArray(
        np.zeros((len(lats), len(lons)), dtype=np.float32),
        dims=("lat", "lon"),
        coords={"lat": lats, "lon": lons},
    )
    grid.attrs["comparison_resolution_deg"] = float(resolution_deg)
    grid = grid.rio.write_crs("EPSG:4326")
    grid = grid.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    return grid


# ---------------------------------------------------------------------------
# build_reference_grid
# ---------------------------------------------------------------------------

class TestBuildReferenceGrid:
    def test_basic_grid(self):
        bbox = (-10.0, -5.0, 10.0, 5.0)
        grid = build_reference_grid(bbox, resolution_m=500)

        assert grid.rio.crs is not None
        assert str(grid.rio.crs) == "EPSG:4326"
        assert "lat" in grid.dims
        assert "lon" in grid.dims
        # Resolution should be close to 500/111320
        expected_res = 500 / 111_320
        lon_diff = abs(float(grid.lon[1] - grid.lon[0]))
        assert abs(lon_diff - expected_res) < 1e-6

    def test_grid_covers_bbox(self):
        bbox = (100.0, -10.0, 110.0, 10.0)
        grid = build_reference_grid(bbox, resolution_m=1000)

        assert float(grid.lon.min()) >= 100.0
        assert float(grid.lon.max()) <= 110.0
        assert float(grid.lat.min()) >= -10.0
        assert float(grid.lat.max()) <= 10.0


# ---------------------------------------------------------------------------
# _bbox_from_reference_grid
# ---------------------------------------------------------------------------

class TestBboxFromReferenceGrid:
    def test_single_cell_chunk_uses_half_cell_padding(self):
        grid = _make_reference_grid(
            lat_range=(0.0, 0.5),
            lon_range=(100.0, 100.5),
            resolution_deg=0.5,
        )

        west, south, east, north = _bbox_from_reference_grid(grid)

        assert west == pytest.approx(99.75)
        assert east == pytest.approx(100.25)
        assert south == pytest.approx(0.25)
        assert north == pytest.approx(0.75)

    def test_clamps_global_bounds(self):
        grid = build_reference_grid((-180.0, -35.0, 180.0, 35.0), resolution_m=500)
        chunk = _grid_chunk_view(grid, GridChunk(row_start=0, row_stop=2, col_start=0, col_stop=2))

        west, south, east, north = _bbox_from_reference_grid(chunk)

        assert west >= -180.0
        assert south >= -90.0
        assert east <= 180.0
        assert north <= 90.0


class TestGridChunkView:
    def test_preserves_spatial_dims_and_crs(self):
        grid = build_reference_grid((-180.0, -35.0, 180.0, 35.0), resolution_m=500)

        chunk = _grid_chunk_view(grid, GridChunk(row_start=0, row_stop=2, col_start=0, col_stop=2))

        assert chunk.rio.x_dim == "lon"
        assert chunk.rio.y_dim == "lat"
        assert str(chunk.rio.crs) == "EPSG:4326"


class TestParallelBuildChunkedOutput:
    def test_parallel_chunk_staging_writes_and_merges_all_chunks(self, tmp_path: Path):
        grid = _make_reference_grid(
            lat_range=(0.0, 2.0),
            lon_range=(0.0, 2.0),
            resolution_deg=1.0,
        )
        output_path = tmp_path / "parallel_chunks.nc"

        def build_chunk(
            chunk_grid: xr.DataArray,
            _chunk_bbox: tuple[float, float, float, float],
        ) -> xr.Dataset:
            return xr.Dataset(
                {
                    "value": xr.DataArray(
                        np.ones(chunk_grid.shape, dtype=np.float32),
                        dims=chunk_grid.dims,
                        coords=chunk_grid.coords,
                    )
                }
            )

        paths = _build_chunked_output(
            output_path=output_path,
            reference_grid=grid,
            chunk_cells=1,
            skip_existing=False,
            desc="parallel test chunks",
            build_chunk_dataset=build_chunk,
            max_workers=2,
        )

        assert paths == [output_path]
        assert output_path.exists()
        merged = xr.open_dataset(output_path)
        try:
            assert merged["value"].shape == grid.shape
            assert np.allclose(merged["value"].values, 1.0, equal_nan=False)
        finally:
            merged.close()

    def test_log_chunk_start_emits_chunk_token(self, tmp_path: Path, caplog):
        grid = _make_reference_grid(
            lat_range=(0.0, 1.0),
            lon_range=(100.0, 101.0),
            resolution_deg=0.5,
        )
        output_path = tmp_path / "chunk_log.nc"

        def build_chunk(
            chunk_grid: xr.DataArray,
            _chunk_bbox: tuple[float, float, float, float],
        ) -> xr.Dataset:
            return xr.Dataset(
                {
                    "value": xr.DataArray(
                        np.ones(chunk_grid.shape, dtype=np.float32),
                        dims=chunk_grid.dims,
                        coords=chunk_grid.coords,
                    )
                }
            )

        caplog.set_level("INFO", logger="WA.standardize")
        _build_chunked_output(
            output_path=output_path,
            reference_grid=grid,
            chunk_cells=1,
            skip_existing=False,
            desc="chunk log test",
            build_chunk_dataset=build_chunk,
            max_workers=1,
            log_chunk_start=True,
        )

        assert "starting chunk r00000-00001_c00000-00001" in caplog.text

    def test_gwd30_streaming_final_merge_avoids_open_mfdataset(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        import WA.standardize as standardize_module

        grid = _make_reference_grid(
            lat_range=(0.0, 2.0),
            lon_range=(100.0, 102.0),
            resolution_deg=1.0,
        )
        output_path = tmp_path / "gwd30_2016.nc"

        def fail_open_mfdataset(*_args, **_kwargs):
            raise AssertionError("GWD30 final merge should not call open_mfdataset")

        monkeypatch.setattr(standardize_module.xr, "open_mfdataset", fail_open_mfdataset)

        def build_chunk(
            chunk_grid: xr.DataArray,
            _chunk_bbox: tuple[float, float, float, float],
        ) -> xr.Dataset:
            lat0 = float(chunk_grid.coords["lat"].values[0])
            lon0 = float(chunk_grid.coords["lon"].values[0])
            if lat0 == 2.0 and lon0 == 100.0:
                raise FileNotFoundError("simulate empty chunk")
            fill_value = np.float32(lat0 + lon0)
            times = np.array(["2016-01-16", "2016-02-15"], dtype="datetime64[ns]")
            return xr.Dataset(
                {
                    "frac_0": xr.DataArray(
                        np.full((2, *chunk_grid.shape), fill_value, dtype=np.float32),
                        dims=("time", *chunk_grid.dims),
                        coords={"time": times, **chunk_grid.coords},
                    ),
                },
                attrs={"dataset_id": "gwd30", "year": 2016},
            )

        paths = _build_chunked_output(
            output_path=output_path,
            reference_grid=grid,
            chunk_cells=1,
            skip_existing=False,
            desc="gwd30 stream merge",
            build_chunk_dataset=build_chunk,
            max_workers=1,
        )

        assert paths == [output_path]
        assert output_path.exists()
        with xr.open_dataset(output_path, engine="netcdf4") as merged:
            assert merged["frac_0"].shape == (2, 2, 2)
            assert np.isnan(merged["frac_0"].isel(time=0, lat=0, lon=0).item())
            assert merged["frac_0"].isel(time=0, lat=0, lon=1).item() == pytest.approx(103.0)
            assert merged["frac_0"].isel(time=0, lat=1, lon=0).item() == pytest.approx(101.0)
            assert merged["frac_0"].isel(time=0, lat=1, lon=1).item() == pytest.approx(102.0)


class TestGwd30TileDrivenRebucket:
    def test_opens_each_staged_tile_once_during_rebucket(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        import WA.standardize as standardize_module
        from WA.loaders.base import DatasetMetadata

        grid = _make_reference_grid(
            lat_range=(0.0, 2.0),
            lon_range=(100.0, 102.0),
            resolution_deg=0.5,
        )
        output_path = tmp_path / "gwd30_2016.nc"
        staging_dir = tmp_path / "_staging" / "gwd30_2016" / "tile_partials"
        staging_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(standardize_module, "_chunk_cell_size", lambda _dataset_id: 2)

        times = np.array(["2016-01-16"], dtype="datetime64[ns]")
        class_ids = np.array([0], dtype=np.int16)
        lons = np.array([100.0, 100.5, 101.0, 101.5], dtype=np.float64)

        def make_stage_tile(path: Path, lats: np.ndarray, value: float) -> None:
            ds = xr.Dataset(
                {
                    "weighted": xr.DataArray(
                        np.full((1, 1, len(lats), len(lons)), value, dtype=np.float32),
                        dims=("time", "class_id", "lat", "lon"),
                        coords={
                            "time": times,
                            "class_id": class_ids,
                            "lat": lats,
                            "lon": lons,
                        },
                    ),
                    "coverage": xr.DataArray(
                        np.ones((1, len(lats), len(lons)), dtype=np.float32),
                        dims=("time", "lat", "lon"),
                        coords={"time": times, "lat": lats, "lon": lons},
                    ),
                },
                attrs={"dataset_id": "gwd30", "year": 2016},
            )
            ds.to_netcdf(path, format="NETCDF4", engine="netcdf4")
            ds.close()

        top_path = staging_dir / "tile_top.nc"
        bottom_path = staging_dir / "tile_bottom.nc"
        make_stage_tile(top_path, np.array([2.0, 1.5], dtype=np.float64), 0.25)
        make_stage_tile(bottom_path, np.array([1.0, 0.5], dtype=np.float64), 0.75)

        staged_tiles = [
            (top_path, (100.0, 1.5, 101.5, 2.0)),
            (bottom_path, (100.0, 0.5, 101.5, 1.0)),
        ]

        class FakeLoader:
            dataset_id = "gwd30"

            def metadata(self):
                return DatasetMetadata(
                    dataset_id="gwd30",
                    name="GWD30",
                    source_path="/tmp/gwd30",
                    crs="EPSG:4326",
                    spatial_resolution="500m",
                    temporal_coverage=("2016-01-01", "2016-12-31"),
                    time_resolution="4-day",
                    is_static=False,
                    is_classification=True,
                )

            def merge_staged_time_fraction_tiles(
                self,
                *,
                staged_tiles: list[tuple[Path, tuple[float, float, float, float]]],
                reference_grid: xr.DataArray,
                bbox: tuple[float, float, float, float],
                year: int,
            ) -> xr.Dataset:
                del bbox, year
                chunk_y = reference_grid.coords["lat"].values
                chunk_x = reference_grid.coords["lon"].values
                with xr.open_dataset(staged_tiles[0][0], engine="netcdf4") as first:
                    time_coords = np.asarray(first.coords["time"].values)
                    class_coords = np.asarray(first.coords["class_id"].values)

                weighted_sum = np.zeros(
                    (len(time_coords), len(class_coords), len(chunk_y), len(chunk_x)),
                    dtype=np.float32,
                )
                coverage_sum = np.zeros(
                    (len(time_coords), len(chunk_y), len(chunk_x)),
                    dtype=np.float32,
                )
                for stage_path, _stage_bbox in staged_tiles:
                    with xr.open_dataset(stage_path, engine="netcdf4") as source:
                        weighted = source["weighted"].reindex(
                            {"lat": chunk_y, "lon": chunk_x},
                            fill_value=0.0,
                        )
                        coverage = source["coverage"].reindex(
                            {"lat": chunk_y, "lon": chunk_x},
                            fill_value=0.0,
                        )
                        weighted_sum += np.asarray(weighted.values, dtype=np.float32)
                        coverage_sum += np.asarray(coverage.values, dtype=np.float32)

                fractions = np.full_like(weighted_sum, np.nan)
                np.divide(
                    weighted_sum,
                    coverage_sum[:, None, :, :],
                    out=fractions,
                    where=coverage_sum[:, None, :, :] > 0,
                )
                return xr.Dataset(
                    {
                        f"frac_{int(class_id)}": xr.DataArray(
                            fractions[:, class_index],
                            dims=("time", "lat", "lon"),
                            coords={
                                "time": time_coords,
                                "lat": chunk_y,
                                "lon": chunk_x,
                            },
                        )
                        for class_index, class_id in enumerate(class_coords)
                    }
                )

        real_open_dataset = standardize_module.xr.open_dataset
        stage_open_counts = {top_path: 0, bottom_path: 0}

        def counting_open_dataset(path, *args, **kwargs):
            candidate = Path(path)
            if candidate in stage_open_counts:
                stage_open_counts[candidate] += 1
            return real_open_dataset(path, *args, **kwargs)

        monkeypatch.setattr(standardize_module.xr, "open_dataset", counting_open_dataset)

        paths = _build_gwd30_output_from_staged_tiles(
            loader=FakeLoader(),
            output_path=output_path,
            reference_grid=grid,
            staged_tiles=staged_tiles,
            year=2016,
            resolution_m=500.0,
            skip_existing=False,
        )

        assert paths == [output_path]
        assert stage_open_counts == {top_path: 1, bottom_path: 1}
        with xr.open_dataset(output_path, engine="netcdf4") as merged:
            assert np.allclose(
                merged["frac_0"].isel(time=0).values,
                np.array(
                    [
                        [0.25, 0.25, 0.25, 0.25],
                        [0.25, 0.25, 0.25, 0.25],
                        [0.75, 0.75, 0.75, 0.75],
                        [0.75, 0.75, 0.75, 0.75],
                    ],
                    dtype=np.float32,
                ),
                equal_nan=False,
            )


class TestResolveParallelWorkerCount:
    def test_prefers_explicit_worker_env_over_slurm_node_total(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv("WA_STANDARDIZE_WORKERS", "6")
        monkeypatch.setenv("SLURM_CPUS_ON_NODE", "128")
        monkeypatch.setenv("SLURM_CPUS_PER_TASK", "12")

        assert _resolve_parallel_worker_count() == 6

    def test_chunk_parallel_whitelist_keeps_gwd30_serial(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("WA_STANDARDIZE_WORKERS", "6")

        assert _chunk_parallel_worker_count("gwd30") == 1
        assert _chunk_parallel_worker_count("g2017") == 1


class TestStandardizeBerkeley:
    def test_uses_open_time_series_instead_of_reopening_every_chunk(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from WA.loaders.base import DatasetMetadata

        grid = _make_reference_grid(
            lat_range=(-1.0, 1.0),
            lon_range=(100.0, 102.0),
            resolution_deg=0.5,
        )
        bbox = (100.0, -1.0, 102.0, 1.0)
        output_dir = tmp_path / "out"

        source = xr.Dataset(
            {
                "watermask": xr.DataArray(
                    np.array(
                        [
                            [[0.0, 0.5, 1.0, 0.5], [0.25, 0.75, 0.5, 0.0]],
                            [[1.0, 0.5, 0.0, 0.5], [0.75, 0.25, 0.5, 1.0]],
                        ],
                        dtype=np.float32,
                    ),
                    dims=("time", "lat", "lon"),
                    coords={
                        "time": np.array(["2020-01-01", "2020-02-01"], dtype="datetime64[ns]"),
                        "lat": np.array([0.5, -0.5], dtype=np.float64),
                        "lon": np.array([100.25, 100.75, 101.25, 101.75], dtype=np.float64),
                    },
                )
            }
        )
        source = source.rio.write_crs("EPSG:4326").rio.set_spatial_dims(x_dim="lon", y_dim="lat")

        loader = MagicMock()
        loader.dataset_id = "berkeley_rwawc"
        loader.config = {"time_range": {"start": "2020-01", "end": "2020-12"}}
        loader.metadata.return_value = DatasetMetadata(
            dataset_id="berkeley_rwawc",
            name="Berkeley",
            source_path=str(tmp_path),
            crs="EPSG:4326",
            spatial_resolution="30m",
            temporal_coverage=("2020-01", "2020-12"),
            time_resolution="monthly",
            is_static=False,
            is_classification=False,
            native_variables=("watermask",),
            semantic_mapping={"watermask": "auxiliary_open_water_mask"},
        )
        loader.open_time_series.return_value = source

        def _unexpected_load(*_args, **_kwargs):
            raise AssertionError("Berkeley standardize should not call loader.load() per chunk")

        loader.load.side_effect = _unexpected_load

        outputs = _standardize_berkeley(
            loader,
            grid,
            bbox,
            output_dir,
            years=[2020],
            skip_existing=False,
        )

        assert outputs == [output_dir / "berkeley_rwawc_2020.nc"]
        loader.open_time_series.assert_called_once()
        merged = xr.open_dataset(outputs[0])
        try:
            assert merged.sizes["time"] == 2
            assert "watermask" in merged.data_vars
        finally:
            merged.close()


class TestStandardizeContinuousOpenOnce:
    @pytest.mark.parametrize("dataset_id", ["giems_mc", "topmodel"])
    def test_uses_open_time_series_instead_of_reopening_every_chunk(
        self,
        dataset_id: str,
        tmp_path: Path,
    ) -> None:
        from WA.loaders.base import DatasetMetadata

        grid = _make_reference_grid(
            lat_range=(-1.0, 1.0),
            lon_range=(100.0, 102.0),
            resolution_deg=0.5,
        )
        bbox = (100.0, -1.0, 102.0, 1.0)
        output_dir = tmp_path / "out"

        dims = ("time", "lat", "lon")
        coords: dict[str, np.ndarray | list[str]] = {
            "time": np.array(["2020-01-01", "2020-02-01"], dtype="datetime64[ns]"),
            "lat": np.array([0.5, -0.5], dtype=np.float64),
            "lon": np.array([100.25, 100.75, 101.25, 101.75], dtype=np.float64),
        }
        data = np.array(
            [
                [[0.0, 0.5, 1.0, 0.5], [0.25, 0.75, 0.5, 0.0]],
                [[1.0, 0.5, 0.0, 0.5], [0.75, 0.25, 0.5, 1.0]],
            ],
            dtype=np.float32,
        )
        if dataset_id == "topmodel":
            dims = ("config", "forcing", "time", "lat", "lon")
            coords = {
                "config": ["cfg_a"],
                "forcing": ["force_a"],
                "time": np.array(["2020-01-01", "2020-02-01"], dtype="datetime64[ns]"),
                "lat": np.array([0.5, -0.5], dtype=np.float64),
                "lon": np.array([100.25, 100.75, 101.25, 101.75], dtype=np.float64),
            }
            data = data[None, None, ...]

        source = xr.Dataset(
            {
                "wetland_fraction": xr.DataArray(
                    data,
                    dims=dims,
                    coords=coords,
                )
            }
        )
        source = source.rio.write_crs("EPSG:4326").rio.set_spatial_dims(x_dim="lon", y_dim="lat")

        loader = MagicMock()
        loader.dataset_id = dataset_id
        loader.config = {"time_range": {"start": "2020-01", "end": "2020-12"}}
        loader.metadata.return_value = DatasetMetadata(
            dataset_id=dataset_id,
            name=dataset_id,
            source_path=str(tmp_path),
            crs="EPSG:4326",
            spatial_resolution="0.25deg",
            temporal_coverage=("2020-01", "2020-12"),
            time_resolution="monthly",
            is_static=False,
            is_classification=False,
            native_variables=("wetland_fraction",),
            semantic_mapping={"wetland_fraction": "wetland_fraction"},
        )
        loader.open_time_series.return_value = source

        def _unexpected_load(*_args, **_kwargs):
            raise AssertionError(
                f"{dataset_id} standardize should not call loader.load() per chunk"
            )

        loader.load.side_effect = _unexpected_load

        outputs = _standardize_continuous_yearly(
            loader,
            grid,
            bbox,
            output_dir,
            file_prefix=dataset_id,
            years=[2020],
            skip_existing=False,
        )

        assert outputs == [output_dir / f"{dataset_id}_2020.nc"]
        loader.open_time_series.assert_called_once()
        merged = xr.open_dataset(outputs[0])
        try:
            assert merged.sizes["time"] == 2
            assert "wetland_fraction" in merged.data_vars
            if dataset_id == "topmodel":
                assert merged.sizes["config"] == 1
                assert merged.sizes["forcing"] == 1
        finally:
            merged.close()


# ---------------------------------------------------------------------------
# classification_to_fractions
# ---------------------------------------------------------------------------

class TestClassificationToFractions:
    def test_uniform_class(self):
        """A raster entirely filled with class 1 → frac_1 ≈ 1.0 everywhere."""
        grid = _make_reference_grid(resolution_deg=0.5)

        # Build a classification raster at finer resolution on the same extent
        fine_lats = np.arange(1.0, -1.0, -0.1)
        fine_lons = np.arange(-1.0, 1.0, 0.1)
        data_vals = np.ones((len(fine_lats), len(fine_lons)), dtype=np.float32)
        data = xr.DataArray(
            data_vals,
            dims=("lat", "lon"),
            coords={"lat": fine_lats, "lon": fine_lons},
        )
        data = data.rio.write_crs("EPSG:4326")
        data = data.rio.set_spatial_dims(x_dim="lon", y_dim="lat")

        result = classification_to_fractions(data, grid, [0, 1], prefix="frac")

        assert "frac_0" in result
        assert "frac_1" in result
        # frac_1 should be close to 1.0 for interior pixels
        frac_1_vals = result["frac_1"].values
        valid = frac_1_vals[np.isfinite(frac_1_vals)]
        if valid.size > 0:
            assert np.nanmean(valid) > 0.8

    def test_mixed_classes(self):
        """50/50 split between class 0 and class 1."""
        grid = _make_reference_grid(
            lat_range=(0.0, 1.0), lon_range=(0.0, 1.0), resolution_deg=1.0,
        )

        # Fine grid: top half class 0, bottom half class 1
        fine_lats = np.arange(1.0, 0.0, -0.05)
        fine_lons = np.arange(0.0, 1.0, 0.05)
        data_vals = np.zeros((len(fine_lats), len(fine_lons)), dtype=np.float32)
        mid = len(fine_lats) // 2
        data_vals[mid:, :] = 1.0
        data = xr.DataArray(
            data_vals,
            dims=("lat", "lon"),
            coords={"lat": fine_lats, "lon": fine_lons},
        )
        data = data.rio.write_crs("EPSG:4326")
        data = data.rio.set_spatial_dims(x_dim="lon", y_dim="lat")

        result = classification_to_fractions(data, grid, [0, 1], prefix="frac")

        # Both fractions should be roughly 0.5
        frac_0_vals = result["frac_0"].values.ravel()
        frac_1_vals = result["frac_1"].values.ravel()
        valid_0 = frac_0_vals[np.isfinite(frac_0_vals)]
        valid_1 = frac_1_vals[np.isfinite(frac_1_vals)]
        if valid_0.size > 0 and valid_1.size > 0:
            assert abs(np.nanmean(valid_0) - 0.5) < 0.2
            assert abs(np.nanmean(valid_1) - 0.5) < 0.2

    def test_class_0_included(self):
        """Class 0 (non-wetland) is included as a variable."""
        grid = _make_reference_grid(resolution_deg=0.5)
        data = xr.DataArray(
            np.zeros((4, 4), dtype=np.float32),
            dims=("lat", "lon"),
            coords={"lat": np.arange(1.0, -1.0, -0.5), "lon": np.arange(-1.0, 1.0, 0.5)},
        )
        data = data.rio.write_crs("EPSG:4326")
        data = data.rio.set_spatial_dims(x_dim="lon", y_dim="lat")

        result = classification_to_fractions(data, grid, [0, 1], prefix="frac")
        assert "frac_0" in result


# ---------------------------------------------------------------------------
# glwd_ha_to_fractions
# ---------------------------------------------------------------------------

class TestGlwdHaToFractions:
    def test_normalisation(self):
        """Fractions should sum to ~1.0 where data is valid."""
        grid = _make_reference_grid(
            lat_range=(0.0, 1.0), lon_range=(0.0, 1.0), resolution_deg=0.5,
        )

        # Create mock ha data with 3 classes
        lats = np.arange(1.0, 0.0, -0.1)
        lons = np.arange(0.0, 1.0, 0.1)
        ha_values = np.random.rand(3, len(lats), len(lons)).astype(np.float32) * 100
        ha = xr.DataArray(
            ha_values,
            dims=("glwd_class", "lat", "lon"),
            coords={
                "glwd_class": [0, 1, 2],
                "lat": lats,
                "lon": lons,
            },
        )
        ha = ha.rio.write_crs("EPSG:4326")

        result = glwd_ha_to_fractions(ha, grid)

        assert "frac_0" in result
        assert "frac_1" in result
        assert "frac_2" in result

        # Sum of fractions should be ~1.0
        total = result["frac_0"] + result["frac_1"] + result["frac_2"]
        valid = total.values[np.isfinite(total.values)]
        if valid.size > 0:
            np.testing.assert_allclose(valid, 1.0, atol=0.05)

    def test_zero_ha_produces_nan(self):
        """Where total ha is 0, fractions should be NaN."""
        grid = _make_reference_grid(
            lat_range=(0.0, 0.5), lon_range=(0.0, 0.5), resolution_deg=0.5,
        )

        lats = np.arange(0.5, 0.0, -0.1)
        lons = np.arange(0.0, 0.5, 0.1)
        ha_values = np.zeros((2, len(lats), len(lons)), dtype=np.float32)
        ha = xr.DataArray(
            ha_values,
            dims=("glwd_class", "lat", "lon"),
            coords={"glwd_class": [0, 1], "lat": lats, "lon": lons},
        )
        ha = ha.rio.write_crs("EPSG:4326")

        result = glwd_ha_to_fractions(ha, grid)
        # All fractions should be NaN since total_ha == 0
        for var_name in result.data_vars:
            assert np.all(np.isnan(result[var_name].values))


# ---------------------------------------------------------------------------
# _clip_continuous
# ---------------------------------------------------------------------------

class TestClipContinuous:
    def test_clips_to_0_1(self):
        data = xr.Dataset({
            "wetland_fraction": xr.DataArray(
                np.array([-0.1, 0.5, 1.2, np.nan]),
                dims="x",
            ),
        })
        clipped = _clip_continuous(data)
        expected = np.array([0.0, 0.5, 1.0, np.nan])
        np.testing.assert_array_equal(
            np.isnan(clipped["wetland_fraction"].values),
            np.isnan(expected),
        )
        valid_mask = ~np.isnan(expected)
        np.testing.assert_allclose(
            clipped["wetland_fraction"].values[valid_mask],
            expected[valid_mask],
        )


# ---------------------------------------------------------------------------
# _build_encoding
# ---------------------------------------------------------------------------

class TestBuildEncoding:
    def test_encoding_with_time_dim(self):
        ds = xr.Dataset({
            "var": xr.DataArray(
                np.zeros((3, 10, 20), dtype=np.float32),
                dims=("time", "lat", "lon"),
            ),
        })
        enc = _build_encoding(ds)
        assert "var" in enc
        assert enc["var"]["zlib"] is True
        assert enc["var"]["complevel"] == 4
        # time chunk = 1, spatial chunks ≤ 500
        assert enc["var"]["chunksizes"][0] == 1
        assert enc["var"]["chunksizes"][1] <= 500
        assert enc["var"]["chunksizes"][2] <= 500

    def test_encoding_without_time_dim(self):
        ds = xr.Dataset({
            "var": xr.DataArray(
                np.zeros((10, 20), dtype=np.float32),
                dims=("lat", "lon"),
            ),
        })
        enc = _build_encoding(ds)
        assert len(enc["var"]["chunksizes"]) == 2


# ---------------------------------------------------------------------------
# _sanitize_dataset_for_netcdf
# ---------------------------------------------------------------------------

class TestSanitizeDatasetForNetcdf:
    def test_sanitizes_dataset_variable_and_coord_attrs(self):
        ds = xr.Dataset(
            {
                "var": xr.DataArray(
                    np.ones((2, 2), dtype=np.float32),
                    dims=("lat", "lon"),
                    coords={"lat": [1.0, 0.5], "lon": [100.0, 100.5]},
                    attrs={"semantic_mapping": {"a": "b"}},
                ),
            },
            attrs={"dataset_meta": {"foo": "bar"}},
        )
        ds["lat"].attrs["nested"] = {"unit": "degrees_north"}

        clean = _sanitize_dataset_for_netcdf(ds)

        assert clean.attrs["dataset_meta"] == json.dumps({"foo": "bar"}, sort_keys=True)
        assert clean["var"].attrs["semantic_mapping"] == json.dumps({"a": "b"}, sort_keys=True)
        assert clean["lat"].attrs["nested"] == json.dumps(
            {"unit": "degrees_north"},
            sort_keys=True,
        )

    def test_drops_none_attrs(self):
        ds = xr.Dataset(
            {
                "var": xr.DataArray(
                    np.ones((2, 2), dtype=np.float32),
                    dims=("lat", "lon"),
                    coords={"lat": [1.0, 0.5], "lon": [100.0, 100.5]},
                    attrs={"time_resolution": None},
                ),
            },
            attrs={"time_resolution": None},
        )
        ds["lat"].attrs["optional"] = None

        clean = _sanitize_dataset_for_netcdf(ds)

        assert "time_resolution" not in clean.attrs
        assert "time_resolution" not in clean["var"].attrs
        assert "optional" not in clean["lat"].attrs

    def test_converts_bool_attrs_to_int(self):
        ds = xr.Dataset(
            {
                "var": xr.DataArray(
                    np.ones((2, 2), dtype=np.float32),
                    dims=("lat", "lon"),
                    coords={"lat": [1.0, 0.5], "lon": [100.0, 100.5]},
                    attrs={"is_static": True},
                ),
            },
            attrs={"is_static": False},
        )

        clean = _sanitize_dataset_for_netcdf(ds)

        assert clean.attrs["is_static"] == 0
        assert clean["var"].attrs["is_static"] == 1

    def test_clears_coord_encoding(self):
        ds = xr.Dataset(
            {
                "var": xr.DataArray(
                    np.ones((2,), dtype=np.float32),
                    dims=("time",),
                    coords={"time": np.array(["2000-01-16", "2000-02-15"], dtype="datetime64[ns]")},
                ),
            }
        )
        ds["time"].encoding = {
            "units": "days since 2000-01-16 00:00:00",
            "calendar": "proleptic_gregorian",
        }

        clean = _sanitize_dataset_for_netcdf(ds)

        assert clean["time"].encoding == {}


# ---------------------------------------------------------------------------
# _reproject_per_timestep
# ---------------------------------------------------------------------------

class TestReprojectPerTimestep:
    def test_handles_multiple_non_spatial_dims(self, monkeypatch: pytest.MonkeyPatch):
        grid = _make_reference_grid(
            lat_range=(0.0, 1.0),
            lon_range=(100.0, 101.0),
            resolution_deg=0.5,
        )
        values = np.arange(2 * 2 * 3 * 2 * 2, dtype=np.float32).reshape(2, 2, 3, 2, 2)
        dataset = xr.Dataset(
            {
                "wetland_fraction": xr.DataArray(
                    values,
                    dims=("config", "forcing", "time", "lat", "lon"),
                    coords={
                        "config": ["cfg_a", "cfg_b"],
                        "forcing": ["era5", "merra2"],
                        "time": np.array(
                            ["2001-01-01", "2001-02-01", "2001-03-01"],
                            dtype="datetime64[ns]",
                        ),
                        "lat": [1.0, 0.5],
                        "lon": [100.0, 100.5],
                    },
                ),
            }
        )

        calls: list[tuple[str, ...]] = []

        def fake_reproject(
            data: xr.DataArray,
            reference_grid: xr.DataArray,
            *,
            resampling,
        ) -> xr.DataArray:
            calls.append(tuple(data.dims))
            fill = float(np.nanmean(data.values))
            return xr.DataArray(
                np.full(reference_grid.shape, fill, dtype=np.float32),
                dims=reference_grid.dims,
                coords=reference_grid.coords,
            )

        monkeypatch.setattr("WA.standardize.reproject_to_grid", fake_reproject)

        result = _reproject_per_timestep(dataset, grid)

        assert result["wetland_fraction"].dims == (
            "config",
            "forcing",
            "time",
            "lat",
            "lon",
        )
        assert len(calls) == 2 * 2 * 3
        expected = float(
            np.nanmean(
                dataset["wetland_fraction"].isel(
                    config=1,
                    forcing=0,
                    time=2,
                ).values
            )
        )
        actual = float(result["wetland_fraction"].isel(config=1, forcing=0, time=2).mean().item())
        assert actual == pytest.approx(expected)

    def test_normalizes_yx_reproject_output_back_to_lat_lon(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        grid = _make_reference_grid(
            lat_range=(0.0, 1.0),
            lon_range=(100.0, 101.0),
            resolution_deg=0.5,
        )
        dataset = xr.Dataset(
            {
                "wetland_fraction": xr.DataArray(
                    np.arange(2 * 2 * 2, dtype=np.float32).reshape(2, 2, 2),
                    dims=("time", "lat", "lon"),
                    coords={
                        "time": np.array(["2001-01-01", "2001-02-01"], dtype="datetime64[ns]"),
                        "lat": [1.0, 0.5],
                        "lon": [100.0, 100.5],
                    },
                ),
            }
        )

        def fake_reproject(
            data: xr.DataArray,
            reference_grid: xr.DataArray,
            *,
            resampling,
        ) -> xr.DataArray:
            del resampling
            fill = float(np.nanmean(data.values))
            reproj = xr.DataArray(
                np.full(reference_grid.shape, fill, dtype=np.float32),
                dims=("y", "x"),
                coords={
                    "y": reference_grid["lat"].values,
                    "x": reference_grid["lon"].values,
                },
            )
            reproj = reproj.rio.write_crs("EPSG:4326")
            return reproj.rio.set_spatial_dims(x_dim="x", y_dim="y")

        monkeypatch.setattr("WA.standardize.reproject_to_grid", fake_reproject)

        result = _reproject_per_timestep(dataset, grid)

        assert result["wetland_fraction"].dims == ("time", "lat", "lon")
        np.testing.assert_allclose(
            result["wetland_fraction"].isel(time=1).values,
            np.full(grid.shape, np.nanmean(dataset["wetland_fraction"].isel(time=1).values)),
        )


# ---------------------------------------------------------------------------
# _build_chunked_output
# ---------------------------------------------------------------------------

class TestBuildChunkedOutput:
    def test_stages_and_merges_spatial_chunks(self, tmp_path: Path):
        grid = _make_reference_grid(
            lat_range=(0.0, 1.0),
            lon_range=(100.0, 101.0),
            resolution_deg=0.5,
        )
        output_path = tmp_path / "chunked.nc"

        def build_chunk(chunk_grid: xr.DataArray, chunk_bbox):
            fill = float(chunk_grid.lat.values[0] + chunk_grid.lon.values[0])
            ds = xr.Dataset(
                {
                    "var": xr.DataArray(
                        np.full(chunk_grid.shape, fill, dtype=np.float32),
                        dims=chunk_grid.dims,
                        coords=chunk_grid.coords,
                        attrs={"semantic_mapping": {"var": "demo"}},
                    )
                },
                attrs={"chunk_bbox": {"bbox": list(chunk_bbox)}},
            )
            return ds

        paths = _build_chunked_output(
            output_path=output_path,
            reference_grid=grid,
            chunk_cells=1,
            skip_existing=False,
            desc="test chunks",
            build_chunk_dataset=build_chunk,
        )

        assert paths == [output_path]
        staging_dir = output_path.parent / "_staging" / output_path.stem
        assert len(list(staging_dir.glob("chunk_*.nc"))) == 4

        with xr.open_dataset(output_path) as ds:
            assert ds.sizes["lat"] == grid.sizes["lat"]
            assert ds.sizes["lon"] == grid.sizes["lon"]
            np.testing.assert_allclose(
                ds["var"].values,
                np.array(
                    [
                        [101.0, 101.5],
                        [100.5, 101.0],
                    ],
                    dtype=np.float32,
                ),
            )

    def test_clears_stale_staged_chunks_on_fresh_run(self, tmp_path: Path):
        grid = _make_reference_grid(
            lat_range=(0.0, 1.0),
            lon_range=(100.0, 101.0),
            resolution_deg=0.5,
        )
        output_path = tmp_path / "chunked.nc"
        staging_dir = output_path.parent / "_staging" / output_path.stem
        staging_dir.mkdir(parents=True, exist_ok=True)
        stale_chunk = staging_dir / "chunk_stale.nc"
        stale_chunk.write_text("stale", encoding="utf-8")

        def build_chunk(chunk_grid: xr.DataArray, chunk_bbox):
            del chunk_bbox
            return xr.Dataset(
                {
                    "var": xr.DataArray(
                        np.ones(chunk_grid.shape, dtype=np.float32),
                        dims=chunk_grid.dims,
                        coords=chunk_grid.coords,
                    )
                }
            )

        _build_chunked_output(
            output_path=output_path,
            reference_grid=grid,
            chunk_cells=1,
            skip_existing=False,
            desc="test chunks",
            build_chunk_dataset=build_chunk,
        )

        assert not stale_chunk.exists()
        assert len(list(staging_dir.glob("chunk_*.nc"))) == 4

    def test_skip_existing_rebuilds_unreadable_staged_chunk(self, tmp_path: Path):
        grid = _make_reference_grid(
            lat_range=(0.0, 1.0),
            lon_range=(100.0, 101.0),
            resolution_deg=0.5,
        )
        output_path = tmp_path / "chunked.nc"
        build_calls = 0

        def build_chunk(chunk_grid: xr.DataArray, chunk_bbox):
            del chunk_bbox
            nonlocal build_calls
            build_calls += 1
            return xr.Dataset(
                {
                    "var": xr.DataArray(
                        np.ones(chunk_grid.shape, dtype=np.float32),
                        dims=chunk_grid.dims,
                        coords=chunk_grid.coords,
                    )
                }
            )

        _build_chunked_output(
            output_path=output_path,
            reference_grid=grid,
            chunk_cells=1,
            skip_existing=False,
            desc="initial chunks",
            build_chunk_dataset=build_chunk,
        )
        assert build_calls == 4

        staging_dir = output_path.parent / "_staging" / output_path.stem
        corrupt_chunk = staging_dir / "chunk_r00000-00001_c00000-00001.nc"
        corrupt_chunk.write_text("corrupt", encoding="utf-8")
        output_path.unlink()

        build_calls = 0
        _build_chunked_output(
            output_path=output_path,
            reference_grid=grid,
            chunk_cells=1,
            skip_existing=True,
            desc="resume chunks",
            build_chunk_dataset=build_chunk,
        )

        assert build_calls == 1
        with xr.open_dataset(output_path) as ds:
            assert ds["var"].shape == grid.shape

    def test_skip_existing_merge_ignores_stray_untracked_chunk_file(self, tmp_path: Path):
        grid = _make_reference_grid(
            lat_range=(0.0, 1.0),
            lon_range=(100.0, 101.0),
            resolution_deg=0.5,
        )
        output_path = tmp_path / "chunked.nc"

        def build_chunk(chunk_grid: xr.DataArray, chunk_bbox):
            del chunk_bbox
            return xr.Dataset(
                {
                    "var": xr.DataArray(
                        np.ones(chunk_grid.shape, dtype=np.float32),
                        dims=chunk_grid.dims,
                        coords=chunk_grid.coords,
                    )
                }
            )

        _build_chunked_output(
            output_path=output_path,
            reference_grid=grid,
            chunk_cells=1,
            skip_existing=False,
            desc="initial chunks",
            build_chunk_dataset=build_chunk,
        )

        staging_dir = output_path.parent / "_staging" / output_path.stem
        (staging_dir / "chunk_stale.nc").write_text("stale", encoding="utf-8")
        output_path.unlink()

        _build_chunked_output(
            output_path=output_path,
            reference_grid=grid,
            chunk_cells=1,
            skip_existing=True,
            desc="resume chunks",
            build_chunk_dataset=build_chunk,
        )

        with xr.open_dataset(output_path) as ds:
            assert ds["var"].shape == grid.shape

    def test_skip_existing_rebuilds_chunk_missing_spatial_coords(self, tmp_path: Path):
        grid = _make_reference_grid(
            lat_range=(0.0, 1.0),
            lon_range=(100.0, 101.0),
            resolution_deg=0.5,
        )
        output_path = tmp_path / "chunked.nc"
        staging_dir = output_path.parent / "_staging" / output_path.stem
        staging_dir.mkdir(parents=True, exist_ok=True)

        bad_chunk = staging_dir / "chunk_r00000-00001_c00000-00001.nc"
        xr.Dataset(
            {
                "var": xr.DataArray(
                    np.ones((1, 1), dtype=np.float32),
                    dims=("y", "x"),
                )
            }
        ).to_netcdf(bad_chunk)

        build_calls = 0

        def build_chunk(chunk_grid: xr.DataArray, chunk_bbox):
            del chunk_bbox
            nonlocal build_calls
            build_calls += 1
            return xr.Dataset(
                {
                    "var": xr.DataArray(
                        np.ones(chunk_grid.shape, dtype=np.float32),
                        dims=chunk_grid.dims,
                        coords=chunk_grid.coords,
                    )
                }
            )

        _build_chunked_output(
            output_path=output_path,
            reference_grid=grid,
            chunk_cells=1,
            skip_existing=True,
            desc="resume chunks",
            build_chunk_dataset=build_chunk,
        )

        assert build_calls == 4
        with xr.open_dataset(output_path) as ds:
            assert ds["var"].shape == grid.shape


class TestLoadGwd30StageShardManifests:
    def test_restores_unique_existing_stage_tiles(self, tmp_path: Path):
        staging_root = tmp_path / "_staging" / "gwd30_2016"
        tile_dir = staging_root / "tile_partials"
        tile_dir.mkdir(parents=True)

        tile_a = tile_dir / "tile_a.nc"
        tile_b = tile_dir / "tile_b.nc"
        tile_a.write_text("a", encoding="utf-8")
        tile_b.write_text("b", encoding="utf-8")

        (staging_root / "stage_shard_0000_of_0002.json").write_text(
            json.dumps(
                {
                    "staged_tiles": [
                        {"path": str(tile_a), "bbox": [100.0, 0.0, 101.0, 1.0]},
                        {"path": str(tile_b), "bbox": [101.0, 0.0, 102.0, 1.0]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        (staging_root / "stage_shard_0001_of_0002.json").write_text(
            json.dumps(
                {
                    "staged_tiles": [
                        {"path": str(tile_b), "bbox": [101.0, 0.0, 102.0, 1.0]},
                        {
                            "path": str(tile_dir / "missing.nc"),
                            "bbox": [102.0, 0.0, 103.0, 1.0],
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

        restored = _load_gwd30_staged_tiles_from_stage_shard_manifests(staging_root)

        assert restored == [
            (tile_a, (100.0, 0.0, 101.0, 1.0)),
            (tile_b, (101.0, 0.0, 102.0, 1.0)),
        ]

    def test_raises_on_conflicting_bbox_for_same_tile(self, tmp_path: Path):
        staging_root = tmp_path / "_staging" / "gwd30_2016"
        tile_dir = staging_root / "tile_partials"
        tile_dir.mkdir(parents=True)
        tile_a = tile_dir / "tile_a.nc"
        tile_a.write_text("a", encoding="utf-8")

        for shard_name, bbox in (
            ("stage_shard_0000_of_0002.json", [100.0, 0.0, 101.0, 1.0]),
            ("stage_shard_0001_of_0002.json", [100.0, 0.0, 101.5, 1.0]),
        ):
            (staging_root / shard_name).write_text(
                json.dumps({"staged_tiles": [{"path": str(tile_a), "bbox": bbox}]}),
                encoding="utf-8",
            )

        with pytest.raises(ValueError, match="Conflicting bbox metadata"):
            _load_gwd30_staged_tiles_from_stage_shard_manifests(staging_root)


# ---------------------------------------------------------------------------
# _get_available_years
# ---------------------------------------------------------------------------

class TestGetAvailableYears:
    def test_from_years_list(self):
        loader = MagicMock()
        loader.config = {"years": [2013, 2014, 2015]}
        years = _get_available_years(loader)
        assert years == [2013, 2014, 2015]

    def test_from_time_range(self):
        loader = MagicMock()
        loader.config = {"time_range": {"start": "2000-01", "end": "2003-12"}}
        years = _get_available_years(loader)
        assert years == [2000, 2001, 2002, 2003]

    def test_from_metadata(self):
        loader = MagicMock()
        loader.config = {}
        meta = MagicMock()
        meta.temporal_coverage = ("1993", "1995")
        loader.metadata.return_value = meta
        years = _get_available_years(loader)
        assert years == [1993, 1994, 1995]

    def test_empty_when_no_info(self):
        loader = MagicMock()
        loader.config = {}
        meta = MagicMock()
        meta.temporal_coverage = None
        loader.metadata.return_value = meta
        years = _get_available_years(loader)
        assert years == []


class TestFilterSelectedYears:
    def test_preserves_available_order(self):
        filtered = _filter_selected_years(
            "gwd30",
            [2013, 2014, 2015, 2016],
            [2016, 2014],
        )

        assert filtered == [2014, 2016]

    def test_raises_when_requested_year_is_missing(self):
        with pytest.raises(ValueError, match="requested year\\(s\\) not available: 2012"):
            _filter_selected_years("gwd30", [2013, 2014], [2012])


# ---------------------------------------------------------------------------
# standardize_all (integration-like with mock)
# ---------------------------------------------------------------------------

class TestStandardizeAll:
    def test_skips_missing_dataset(self, tmp_path: Path):
        """Datasets not in config should be reported as skipped."""
        grid = _make_reference_grid()
        results = standardize_all(
            dataset_configs={},
            dataset_ids=["nonexistent"],
            bbox=(-1, -1, 1, 1),
            reference_grid=grid,
            output_dir=tmp_path,
        )
        assert results["nonexistent"]["status"] == "skipped"
        # metadata.json should be written
        meta_path = tmp_path / "metadata.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert "datasets" in meta
        assert meta["datasets"]["nonexistent"]["status"] == "skipped"

    def test_metadata_uses_reference_grid_resolution(self, tmp_path: Path):
        grid = build_reference_grid((-10.0, -5.0, 10.0, 5.0), resolution_m=1000)

        standardize_all(
            dataset_configs={},
            dataset_ids=["nonexistent"],
            bbox=(-10.0, -5.0, 10.0, 5.0),
            reference_grid=grid,
            output_dir=tmp_path,
        )

        meta = json.loads((tmp_path / "metadata.json").read_text())
        assert meta["parameters"]["resolution_m"] == pytest.approx(1000.0, rel=1e-6)
        assert meta["parameters"]["resolution_deg"] == pytest.approx(1000 / 111_320, rel=1e-6)

    def test_can_skip_metadata_write(self, tmp_path: Path):
        grid = _make_reference_grid()

        standardize_all(
            dataset_configs={},
            dataset_ids=["nonexistent"],
            bbox=(-1, -1, 1, 1),
            reference_grid=grid,
            output_dir=tmp_path,
            write_metadata=False,
        )

        assert not (tmp_path / "metadata.json").exists()
