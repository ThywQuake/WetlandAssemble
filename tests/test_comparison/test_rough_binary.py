from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from WA.comparison.rough_binary import compute_rough_binary_metrics


def test_compute_rough_binary_metrics_builds_pairwise_metrics_and_disagreement() -> None:
    coords = {"lat": [1.5, 0.5], "lon": [100.5, 101.5]}
    surfaces = {
        "wad2m": xr.DataArray(
            np.array([[1.0, 0.8], [0.1, 0.6]], dtype=np.float32),
            coords=coords,
            dims=("lat", "lon"),
            attrs={"comparison_time": "2001-01-01T00:00:00"},
        ),
        "swamps": xr.DataArray(
            np.array([[0.9, 0.2], [0.2, 0.7]], dtype=np.float32),
            coords=coords,
            dims=("lat", "lon"),
            attrs={"comparison_time": "2001-01-01T00:00:00"},
        ),
        "g2017": xr.DataArray(
            np.array([[0.6, 0.4], [0.2, 0.8]], dtype=np.float32),
            coords=coords,
            dims=("lat", "lon"),
            attrs={"comparison_time": "2001-01-01T00:00:00"},
        ),
    }

    result = compute_rough_binary_metrics(surfaces)

    assert list(result.metrics["dataset_a"]) == ["g2017", "g2017", "swamps"]
    assert list(result.metrics["dataset_b"]) == ["swamps", "wad2m", "wad2m"]
    wad2m_swamps = result.metrics[
        (result.metrics["dataset_a"] == "swamps")
        & (result.metrics["dataset_b"] == "wad2m")
    ].iloc[0]
    assert wad2m_swamps["valid_cell_count"] == 4
    assert wad2m_swamps["overall_accuracy"] == 0.75
    assert wad2m_swamps["f1_score"] == 0.8

    np.testing.assert_allclose(
        result.wetland_vote_fraction.values,
        np.array([[1.0, 1 / 3], [0.0, 1.0]], dtype=np.float32),
    )
    np.testing.assert_allclose(
        result.disagreement_score.values,
        np.array([[0.0, 2 / 3], [0.0, 0.0]], dtype=np.float32),
        rtol=1e-6,
    )
    np.testing.assert_array_equal(
        result.participant_count.values,
        np.array([[3, 3], [3, 3]], dtype=np.int32),
    )


def test_compute_rough_binary_metrics_ignores_scalar_time_coords() -> None:
    coords = {"lat": [1.5], "lon": [100.5]}
    surfaces = {
        "wad2m": xr.DataArray(
            np.array([[1.0]], dtype=np.float32),
            coords={**coords, "time": pd.Timestamp("2000-03-16")},
            dims=("lat", "lon"),
            attrs={
                "comparison_time": "2000-03-01T00:00:00",
                "comparison_source_time": "2000-03-16T00:00:00",
            },
        ),
        "swamps": xr.DataArray(
            np.array([[0.0]], dtype=np.float32),
            coords={**coords, "time": pd.Timestamp("2000-03-01")},
            dims=("lat", "lon"),
            attrs={
                "comparison_time": "2000-03-01T00:00:00",
                "comparison_source_time": "2000-03-01T00:00:00",
            },
        ),
    }

    result = compute_rough_binary_metrics(surfaces)

    assert list(result.metrics["dataset_a"]) == ["swamps"]
    assert list(result.metrics["dataset_b"]) == ["wad2m"]
    assert result.metrics.iloc[0]["valid_cell_count"] == 1
    np.testing.assert_array_equal(result.participant_count.values, np.array([[2]], dtype=np.int32))
