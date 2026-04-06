from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr

from WA.phase361_gwd30_trace import (
    Phase361Hotspot,
    build_phase361_hotspot_file_listing,
    compare_dominant_classes,
    load_phase361_hotspots_manifest,
    reconstruct_reduced_tiles_to_unified_fraction,
    select_phase361_hotspots,
    subset_phase36_reference_grid,
)


def _sample_metrics() -> xr.Dataset:
    lat = np.array([1.5, 0.5], dtype=np.float32)
    lon = np.array([100.5, 101.5], dtype=np.float32)
    return xr.Dataset(
        {
            "entropy": xr.DataArray(
                np.array([[0.2, 0.4], [0.6, 0.8]], dtype=np.float32),
                dims=("lat", "lon"),
                coords={"lat": lat, "lon": lon},
            )
        }
    )


def test_load_and_select_phase361_hotspots(tmp_path: Path) -> None:
    manifest = tmp_path / "hotspots.json"
    manifest.write_text(
        json.dumps(
            {
                "hotspots": [
                    {
                        "hotspot_id": "entropy-a-001",
                        "bbox": [100.0, 0.0, 101.0, 1.0],
                        "region_slug": "a",
                        "region_label": "Region A",
                        "region_rank": 1,
                    },
                    {
                        "hotspot_id": "entropy-b-001",
                        "bbox": [101.0, 0.0, 102.0, 1.0],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    hotspots = load_phase361_hotspots_manifest(manifest)
    selected = select_phase361_hotspots(hotspots, hotspot_ids=["entropy-b-001"])
    selected_all = select_phase361_hotspots(hotspots)

    assert [hotspot.hotspot_id for hotspot in hotspots] == ["entropy-a-001", "entropy-b-001"]
    assert [hotspot.hotspot_id for hotspot in selected] == ["entropy-b-001"]
    assert [hotspot.hotspot_id for hotspot in selected_all] == [
        "entropy-a-001",
        "entropy-b-001",
    ]


def test_subset_phase36_reference_grid_preserves_phase36_coords() -> None:
    grid = subset_phase36_reference_grid(_sample_metrics()["entropy"], (100.0, 0.0, 101.0, 2.0))

    assert grid.dims == ("lat", "lon")
    np.testing.assert_allclose(grid.coords["lat"].values, np.array([1.5, 0.5], dtype=np.float32))
    np.testing.assert_allclose(grid.coords["lon"].values, np.array([100.5], dtype=np.float32))


def test_reconstruct_reduced_tiles_to_unified_fraction_matches_expected(tmp_path: Path) -> None:
    reference_grid = subset_phase36_reference_grid(
        _sample_metrics()["entropy"],
        (100.0, 0.0, 102.0, 2.0),
    )
    reduced_path = tmp_path / "tile_demo.nc"
    class_ids = np.arange(8, dtype=np.int16)
    weighted = np.zeros((8, 2, 1), dtype=np.float32)
    weighted[0, :, :] = 0.4
    weighted[2, :, :] = 0.6
    coverage = np.ones((2, 1), dtype=np.float32)
    xr.Dataset(
        {
            "annual_unified_weighted_sum": xr.DataArray(
                weighted,
                dims=("class_id", "lat", "lon"),
                coords={
                    "class_id": class_ids,
                    "lat": np.array([1.5, 0.5], dtype=np.float32),
                    "lon": np.array([100.5], dtype=np.float32),
                },
            ),
            "annual_coverage_sum": xr.DataArray(
                coverage,
                dims=("lat", "lon"),
                coords={
                    "lat": np.array([1.5, 0.5], dtype=np.float32),
                    "lon": np.array([100.5], dtype=np.float32),
                },
            ),
        }
    ).to_netcdf(reduced_path)

    unified = reconstruct_reduced_tiles_to_unified_fraction(
        reduced_tiles=[(reduced_path, (100.0, 0.0, 101.0, 2.0))],
        reference_grid=reference_grid,
    )

    np.testing.assert_allclose(
        unified.sel(class_id=0).values,
        np.array([[0.4, np.nan], [0.4, np.nan]], dtype=np.float32),
        equal_nan=True,
    )
    np.testing.assert_allclose(
        unified.sel(class_id=2).values,
        np.array([[0.6, np.nan], [0.6, np.nan]], dtype=np.float32),
        equal_nan=True,
    )


def test_compare_dominant_classes_reports_transition_counts() -> None:
    coords = {"lat": [1.5, 0.5], "lon": [100.5, 101.5]}
    left = xr.DataArray(
        np.array([[0, 2], [2, 3]], dtype=np.int16),
        dims=("lat", "lon"),
        coords=coords,
    )
    right = xr.DataArray(
        np.array([[1, 2], [2, 4]], dtype=np.int16),
        dims=("lat", "lon"),
        coords=coords,
    )

    comparison = compare_dominant_classes(left, right)

    assert comparison["valid_cells"] == 4
    assert comparison["changed_cells"] == 2
    assert comparison["transitions"] == [
        {"from": 0, "to": 1, "count": 1},
        {"from": 3, "to": 4, "count": 1},
    ]


def test_build_phase361_hotspot_file_listing_keeps_raw_staged_reduced_alignment(
    tmp_path: Path,
) -> None:
    hotspot = Phase361Hotspot(
        hotspot_id="entropy-a-001",
        bbox=(100.0, 0.0, 101.0, 1.0),
    )
    raw_tile = tmp_path / "T51PXM_wetland_2016.tif"
    raw_tile.write_bytes(b"raw")
    staged_tile = tmp_path / "tile_T51PXM_wetland_2016.nc"
    staged_tile.write_bytes(b"staged")
    reduced_dir = tmp_path / "reduced"
    reduced_dir.mkdir()
    reduced_tile = reduced_dir / staged_tile.name
    reduced_tile.write_bytes(b"reduced")
    staged_tiles = [(staged_tile, (100.0, 0.0, 101.0, 1.0))]

    class _FakeLoader:
        def _discover_tiles(self, *, bbox, time_range):
            assert bbox == hotspot.bbox
            assert time_range == ("2016-01-01", "2016-12-31")
            return {2016: [raw_tile]}

        def _tile_bbox(self, tile_code):
            assert tile_code == "51PXM"
            return (100.0, 0.0, 101.0, 1.0)

        def _tile_bounds_for_stage(self, path):
            raise AssertionError("should not fall back to stage bounds")

    listing = build_phase361_hotspot_file_listing(
        hotspot,
        loader=_FakeLoader(),
        staged_tiles=staged_tiles,
        reduced_dir=reduced_dir,
        year=2016,
    )

    assert listing["raw_tiles"]["count"] == 1
    assert listing["raw_tiles"]["tiles"][0]["path"] == str(raw_tile)
    assert listing["staged_tiles"]["count"] == 1
    assert listing["staged_tiles"]["tiles"][0]["path"] == str(staged_tile)
    assert listing["reduced_tiles"]["count"] == 1
    assert listing["reduced_tiles"]["tiles"][0]["path"] == str(reduced_tile)
