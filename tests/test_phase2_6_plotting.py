from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import xarray as xr

from WA.visualization.phase26 import (
    participant_count_style,
    plot_phase26_triptych,
    prepare_participant_count_for_plot,
)


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "plot_phase2_6_metrics.py"
    spec = importlib.util.spec_from_file_location("plot_phase2_6_metrics", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_metrics() -> xr.Dataset:
    coords = {
        "lat": np.array([10.0, 0.0], dtype=np.float32),
        "lon": np.array([100.0, 110.0, 120.0], dtype=np.float32),
    }
    return xr.Dataset(
        {
            "mean_wetland_fraction": xr.DataArray(
                np.array([[0.1, 0.4, 0.7], [0.2, 0.5, 0.8]], dtype=np.float32),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "std_wetland_fraction": xr.DataArray(
                np.array([[0.02, 0.10, 0.24], [0.05, 0.11, 0.30]], dtype=np.float32),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "participant_count": xr.DataArray(
                np.array([[0, 2, 3], [1, 0, 4]], dtype=np.int16),
                dims=("lat", "lon"),
                coords=coords,
            ),
        }
    )


def test_prepare_participant_count_for_plot_masks_zero_cells() -> None:
    prepared = prepare_participant_count_for_plot(_sample_metrics()["participant_count"])

    np.testing.assert_allclose(
        prepared.values,
        np.array([[np.nan, 2.0, 3.0], [1.0, np.nan, 4.0]], dtype=np.float32),
        equal_nan=True,
    )


def test_participant_count_style_uses_integer_bins() -> None:
    prepared = prepare_participant_count_for_plot(_sample_metrics()["participant_count"])
    style = participant_count_style(prepared)

    assert style.ticks == (1, 2, 3, 4)
    np.testing.assert_allclose(style.norm.boundaries, np.array([0.5, 1.5, 2.5, 3.5, 4.5]))


def test_plot_phase26_triptych_writes_png(tmp_path: Path) -> None:
    output_path = tmp_path / "phase2_6_triptych.png"

    written = plot_phase26_triptych(_sample_metrics(), output_path=output_path)

    assert written == output_path
    assert output_path.is_file()


def test_plot_phase2_6_script_writes_png_from_metrics_file(tmp_path: Path) -> None:
    module = _load_script_module()
    input_dir = tmp_path / "phase2.6"
    input_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = input_dir / "phase2_6_metrics_global_tropical_subtropical_35_0p25deg.nc"
    _sample_metrics().to_netcdf(metrics_path)

    exit_code = module.main(
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(tmp_path / "figures"),
        ]
    )

    assert exit_code == 0
    assert (
        tmp_path / "figures" / "phase2_6_triptych_global_tropical_subtropical_35_0p25deg.png"
    ).is_file()
