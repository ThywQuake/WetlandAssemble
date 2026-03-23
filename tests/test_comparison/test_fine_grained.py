from __future__ import annotations

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr

from WA.comparison.fine_grained import (
    FINE_4CLASS_MAPS,
    FINE_8CLASS_MAPS,
    compute_class_agreement,
    dataset_supports_fine_comparison,
    harmonize_fine_collection,
    harmonize_fine_dataset,
)
from WA.comparison.harmonize import create_comparison_grid


def _reference_grid() -> xr.DataArray:
    return create_comparison_grid((100.0, 0.0, 102.0, 2.0), resolution_deg=1.0)


def test_fine_4class_maps_cover_all_known_values() -> None:
    assert set(FINE_4CLASS_MAPS["g2017"]) == {0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100}
    assert set(FINE_4CLASS_MAPS["glwd_v2"]) == set(range(34))
    assert set(FINE_4CLASS_MAPS["gwd30"]) == set(range(15))


def test_fine_8class_maps_cover_all_known_values() -> None:
    assert set(FINE_8CLASS_MAPS["g2017"]) == {0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100}
    assert set(FINE_8CLASS_MAPS["glwd_v2"]) == set(range(34))
    assert set(FINE_8CLASS_MAPS["gwd30"]) == set(range(15))


def test_harmonize_fine_dataset_remaps_g2017() -> None:
    dataset = xr.Dataset(
        {
            "wetland": (
                ("lat", "lon"),
                np.array([[10, 20], [30, 0]], dtype=np.uint8),
            )
        },
        coords={"lat": [2.0, 1.0], "lon": [100.0, 101.0]},
    )
    harmonized = harmonize_fine_dataset("g2017", dataset, reference_grid=_reference_grid())

    np.testing.assert_allclose(
        harmonized.values,
        np.array([[1.0, 2.0], [2.0, 0.0]], dtype=np.float32),
    )
    assert harmonized.attrs["comparison_source_variable"] == "wetland"


def test_harmonize_fine_dataset_remaps_glwd() -> None:
    dataset = xr.Dataset(
        {
            "combined_classes": (
                ("lat", "lon"),
                np.array([[0, 1], [8, 33]], dtype=np.uint8),
            )
        },
        coords={"lat": [2.0, 1.0], "lon": [100.0, 101.0]},
    )
    harmonized = harmonize_fine_dataset("glwd_v2", dataset, reference_grid=_reference_grid())

    np.testing.assert_allclose(
        harmonized.values,
        np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32),
    )


def test_harmonize_fine_dataset_remaps_gwd30() -> None:
    dataset = xr.Dataset(
        {
            "wetland_class": (
                ("time", "lat", "lon"),
                np.array(
                    [
                        [[8, 1], [7, 0]],
                        [[8, 1], [7, 0]],
                        [[10, 1], [7, 14]],
                    ],
                    dtype=np.uint8,
                ),
            )
        },
        coords={
            "time": pd.to_datetime(["2019-07-01", "2019-07-05", "2019-07-09"]),
            "lat": [2.0, 1.0],
            "lon": [100.0, 101.0],
        },
    )
    harmonized = harmonize_fine_dataset("gwd30", dataset, reference_grid=_reference_grid())

    np.testing.assert_allclose(
        harmonized.values,
        np.array([[2.0, 1.0], [3.0, 0.0]], dtype=np.float32),
    )


def test_harmonize_fine_collection_aligns_to_shared_grid() -> None:
    reference = _reference_grid()
    datasets = {
        "g2017": xr.Dataset(
            {"wetland": (("lat", "lon"), np.array([[10]], dtype=np.uint8))},
            coords={"lat": [2.0], "lon": [100.0]},
        ),
        "glwd_v2": xr.Dataset(
            {"combined_classes": (("lat", "lon"), np.array([[8]], dtype=np.uint8))},
            coords={"lat": [2.0], "lon": [100.0]},
        ),
    }

    harmonized = harmonize_fine_collection(datasets, reference)

    assert set(harmonized) == {"g2017", "glwd_v2"}
    for surface in harmonized.values():
        assert surface.dims == ("lat", "lon")
        assert surface.sizes == reference.sizes


def test_compute_class_agreement_majority_and_count() -> None:
    coords = {"lat": [2.0, 1.0], "lon": [100.0, 101.0]}
    harmonized = {
        "g2017": xr.DataArray(
            np.array([[1.0, 2.0], [2.0, np.nan]], dtype=np.float32),
            coords=coords,
            dims=("lat", "lon"),
        ),
        "glwd_v2": xr.DataArray(
            np.array([[1.0, 1.0], [2.0, np.nan]], dtype=np.float32),
            coords=coords,
            dims=("lat", "lon"),
        ),
        "gwd30": xr.DataArray(
            np.array([[2.0, 1.0], [2.0, np.nan]], dtype=np.float32),
            coords=coords,
            dims=("lat", "lon"),
        ),
    }

    result = compute_class_agreement(harmonized, num_classes=4)

    np.testing.assert_allclose(
        result["majority_class"].values,
        np.array([[1.0, 1.0], [2.0, np.nan]], dtype=np.float32),
        equal_nan=True,
    )
    np.testing.assert_array_equal(
        result["agreement_count"].values,
        np.array([[2, 2], [3, 0]], dtype=np.int16),
    )
    np.testing.assert_allclose(
        result["class_distribution"].sel(class_id=1).values,
        np.array([[2 / 3, 2 / 3], [0.0, np.nan]], dtype=np.float32),
        rtol=1e-6,
        equal_nan=True,
    )
    np.testing.assert_allclose(
        result["class_distribution"].sel(class_id=2).values,
        np.array([[1 / 3, 1 / 3], [1.0, np.nan]], dtype=np.float32),
        rtol=1e-6,
        equal_nan=True,
    )


def test_dataset_supports_fine_comparison() -> None:
    assert dataset_supports_fine_comparison("g2017") is True
    assert dataset_supports_fine_comparison("glwd_v2") is True
    assert dataset_supports_fine_comparison("gwd30") is True
    assert dataset_supports_fine_comparison("wad2m") is False


def test_gwd30_temporal_mode_reduction() -> None:
    dataset = xr.Dataset(
        {
            "wetland_class": (
                ("time", "lat", "lon"),
                np.array(
                    [
                        [[8]],
                        [[8]],
                        [[10]],
                    ],
                    dtype=np.uint8,
                ),
            )
        },
        coords={
            "time": pd.to_datetime(["2019-07-01", "2019-07-05", "2019-07-09"]),
            "lat": [1.5],
            "lon": [100.5],
        },
    )
    reference = create_comparison_grid((100.0, 1.0, 101.0, 2.0), resolution_deg=1.0)

    harmonized = harmonize_fine_dataset("gwd30", dataset, reference_grid=reference)

    np.testing.assert_allclose(harmonized.values, np.array([[2.0]], dtype=np.float32))
