from __future__ import annotations

from collections.abc import Callable
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
from pytest import MonkeyPatch
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

from tests.test_loaders.conftest import with_common_fields, write_multiband_geotiff
from WA.comparison.harmonize import create_comparison_grid
from WA.loaders import get_loader
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

    def fake_tqdm(iterable, *args, **kwargs):  # type: ignore[no-untyped-def]
        progress_descriptions.append(kwargs.get("desc"))
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
