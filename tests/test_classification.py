from __future__ import annotations

import numpy as np
import xarray as xr

from WA.classification import (
    binary_class_mapping,
    water_class_ids,
    wetland_class_ids,
    wetland_fraction_from_standardized_classes,
)


def test_water_and_wetland_class_ids_follow_yaml_mapping() -> None:
    assert water_class_ids("g2017") == (10,)
    assert 10 not in wetland_class_ids("g2017")
    assert 20 in wetland_class_ids("g2017")
    assert 40 in wetland_class_ids("g2017")


def test_binary_class_mapping_excludes_waterbody() -> None:
    mapping = binary_class_mapping("gwd30", include_water=False)

    assert mapping[1] == 0.0
    assert mapping[7] == 1.0
    assert mapping[8] == 1.0
    assert mapping[14] == 0.0


def test_standardized_fraction_sum_excludes_waterbody_for_known_dataset() -> None:
    dataset = xr.Dataset(
        {
            "frac_1": (("lat", "lon"), np.array([[0.2]], dtype=np.float32)),
            "frac_8": (("lat", "lon"), np.array([[0.3]], dtype=np.float32)),
            "frac_29": (("lat", "lon"), np.array([[0.4]], dtype=np.float32)),
        },
        coords={"lat": [0.5], "lon": [100.5]},
    )

    result = wetland_fraction_from_standardized_classes("glwd_v2", dataset)

    assert result is not None
    np.testing.assert_allclose(result.values, np.array([[0.7]], dtype=np.float32))


def test_standardized_fraction_sum_falls_back_for_unknown_dataset() -> None:
    dataset = xr.Dataset(
        {
            "frac_0": (("lat", "lon"), np.array([[0.1]], dtype=np.float32)),
            "frac_1": (("lat", "lon"), np.array([[0.2]], dtype=np.float32)),
            "frac_2": (("lat", "lon"), np.array([[0.3]], dtype=np.float32)),
        },
        coords={"lat": [0.5], "lon": [100.5]},
    )

    result = wetland_fraction_from_standardized_classes("unknown_dataset", dataset)

    assert result is not None
    np.testing.assert_allclose(result.values, np.array([[0.5]], dtype=np.float32))
