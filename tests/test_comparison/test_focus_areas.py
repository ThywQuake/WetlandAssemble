from __future__ import annotations

import numpy as np
import xarray as xr

from WA.comparison.focus_areas import select_focus_areas


def test_select_focus_areas_stratifies_and_deduplicates() -> None:
    disagreement_score = xr.DataArray(
        np.array([[0.9, 0.8], [0.85, 0.1]], dtype=np.float32),
        coords={"lat": [-4.5, 0.5], "lon": [-60.5, 110.5]},
        dims=("lat", "lon"),
    )
    participant_count = xr.DataArray(
        np.array([[3, 2], [4, 2]], dtype=np.int32),
        coords=disagreement_score.coords,
        dims=disagreement_score.dims,
    )

    focus_areas = select_focus_areas(
        disagreement_score,
        participant_count,
        target_time="2001-01-01",
        top_n=2,
        top_n_per_region=1,
        aoi_size_deg=1.0,
        min_distance_deg=1.5,
    )

    assert [area.region_slug for area in focus_areas] == ["brazil", "indonesia"]
    assert focus_areas[0].aoi_id == "rough-200101-brazil-001"
    assert focus_areas[1].aoi_id == "rough-200101-indonesia-002"
