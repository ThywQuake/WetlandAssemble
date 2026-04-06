from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

from WA.visualization.phase4 import plot_phase4_climatology, plot_phase4_interannual

matplotlib.use("Agg")


def _sample_phase4_table() -> pd.DataFrame:
    annual_rows = [
        {
            "dataset_id": "gwd30",
            "region_id": "amazon",
            "series_type": "annual",
            "time": pd.Timestamp("2019-01-01"),
            "year": 2019,
            "month": None,
            "wetland_area_km2": 100.0,
            "valid_area_km2": 200.0,
            "wetland_percentage": 50.0,
            "observation_count": 12,
            "is_auxiliary_dataset": False,
        },
        {
            "dataset_id": "berkeley_rwawc",
            "region_id": "amazon",
            "series_type": "annual",
            "time": pd.Timestamp("2019-01-01"),
            "year": 2019,
            "month": None,
            "wetland_area_km2": 20.0,
            "valid_area_km2": 100.0,
            "wetland_percentage": 20.0,
            "observation_count": 12,
            "is_auxiliary_dataset": True,
        },
    ]
    climatology_rows = [
        {
            "dataset_id": "gwd30",
            "region_id": "amazon",
            "series_type": "climatology",
            "time": pd.Timestamp("2000-01-01"),
            "year": None,
            "month": 1,
            "wetland_area_km2": 90.0,
            "valid_area_km2": 180.0,
            "wetland_percentage": 50.0,
            "observation_count": 3,
            "is_auxiliary_dataset": False,
        },
        {
            "dataset_id": "berkeley_rwawc",
            "region_id": "amazon",
            "series_type": "climatology",
            "time": pd.Timestamp("2000-01-01"),
            "year": None,
            "month": 1,
            "wetland_area_km2": 25.0,
            "valid_area_km2": 100.0,
            "wetland_percentage": 25.0,
            "observation_count": 3,
            "is_auxiliary_dataset": True,
        },
    ]
    return pd.DataFrame(annual_rows + climatology_rows)


def test_plot_phase4_interannual_writes_png(tmp_path: Path) -> None:
    output_path = tmp_path / "interannual.png"

    result = plot_phase4_interannual(
        _sample_phase4_table(),
        region_label="Amazon",
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.is_file()
    assert output_path.stat().st_size > 0


def test_plot_phase4_climatology_writes_png(tmp_path: Path) -> None:
    output_path = tmp_path / "climatology.png"

    result = plot_phase4_climatology(
        _sample_phase4_table(),
        region_label="Amazon",
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.is_file()
    assert output_path.stat().st_size > 0
