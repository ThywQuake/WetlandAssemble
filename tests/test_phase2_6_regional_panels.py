from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from WA.visualization.phase26 import (
    _configure_panel_geo_axes,
    _geo_tick_values,
    load_phase26_regions,
    resolve_phase26_panel_dataset_ids,
    subset_phase26_surface_to_bbox,
)


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "plot_phase2_6_regional_panels.py"
    )
    spec = importlib.util.spec_from_file_location("plot_phase2_6_regional_panels", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_metrics() -> xr.Dataset:
    coords = {
        "lat": np.array([3.0, 2.0, 1.0, 0.0], dtype=np.float32),
        "lon": np.array([100.0, 101.0, 102.0, 103.0], dtype=np.float32),
    }
    metrics = xr.Dataset(
        {
            "mean_wetland_fraction": xr.DataArray(
                np.full((4, 4), 0.4, dtype=np.float32),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "std_wetland_fraction": xr.DataArray(
                np.full((4, 4), 0.1, dtype=np.float32),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "participant_count": xr.DataArray(
                np.full((4, 4), 4, dtype=np.int16),
                dims=("lat", "lon"),
                coords=coords,
            ),
        }
    )
    metrics.attrs["std_dataset_ids_json"] = json.dumps(
        ["giems_mc", "swamps", "topmodel", "wad2m"]
    )
    return metrics


def _sample_stack() -> xr.DataArray:
    coords = {
        "dataset": ["giems_mc", "swamps", "topmodel", "wad2m", "g2017"],
        "lat": np.array([3.0, 2.0, 1.0, 0.0], dtype=np.float32),
        "lon": np.array([100.0, 101.0, 102.0, 103.0], dtype=np.float32),
    }
    return xr.DataArray(
        np.ones((5, 4, 4), dtype=np.float32),
        dims=("dataset", "lat", "lon"),
        coords=coords,
        name="wetland_fraction",
    )


def test_load_phase26_regions_sorts_by_priority(tmp_path: Path) -> None:
    config_path = tmp_path / "regions.yaml"
    config_path.write_text(
        """
regions:
  b:
    label: "B"
    priority: 2
    bbox: [101, 0, 103, 2]
  a:
    label: "A"
    priority: 1
    bbox: [100, 1, 102, 3]
""".strip(),
        encoding="utf-8",
    )

    regions = load_phase26_regions(config_path)

    assert [region.region_id for region in regions] == ["a", "b"]


def test_resolve_phase26_panel_dataset_ids_uses_std_attr_order() -> None:
    dataset_ids = resolve_phase26_panel_dataset_ids(_sample_stack(), _sample_metrics())
    assert dataset_ids == ("giems_mc", "swamps", "topmodel", "wad2m")


def test_subset_phase26_surface_to_bbox_handles_descending_lat() -> None:
    surface = _sample_metrics()["mean_wetland_fraction"]
    subset = subset_phase26_surface_to_bbox(surface, (100.5, 0.5, 102.5, 2.5))

    assert subset.sizes["lat"] == 2
    assert subset.sizes["lon"] == 2


def test_geo_tick_values_choose_readable_step() -> None:
    assert _geo_tick_values(100.0, 102.0) == [100.0, 101.0, 102.0]
    assert _geo_tick_values(-3.0, 3.0) == [-2.0, 0.0, 2.0]


def test_configure_panel_geo_axes_shows_only_requested_labels() -> None:
    fig, ax = plt.subplots()
    try:
        _configure_panel_geo_axes(
            ax,
            extent=(100.0, 0.0, 102.0, 3.0),
            use_cartopy=False,
            transform=None,
            show_left_labels=True,
            show_bottom_labels=False,
        )

        assert any(label.get_visible() for label in ax.get_yticklabels())
        assert not any(label.get_visible() for label in ax.get_xticklabels())
    finally:
        plt.close(fig)


def test_plot_phase2_6_regional_panels_script_writes_pngs(tmp_path: Path) -> None:
    module = _load_script_module()
    input_dir = tmp_path / "phase2.6"
    output_dir = tmp_path / "figures"
    imagery_dir = tmp_path / "region_imagery"
    input_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = input_dir / "phase2_6_metrics_global_tropical_subtropical_35_0p25deg.nc"
    stack_path = input_dir / "phase2_6_stack_global_tropical_subtropical_35_0p25deg.nc"
    _sample_metrics().to_netcdf(metrics_path)
    _sample_stack().to_dataset(name="wetland_fraction").to_netcdf(stack_path)

    for region_id in ("amazon_basin", "sudd"):
        image_path = imagery_dir / "2016" / region_id / f"{region_id}_modis_rgb.jpg"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        plt.imsave(image_path, np.zeros((10, 12, 3), dtype=np.float32))

    regions_file = tmp_path / "regions.yaml"
    regions_file.write_text(
        """
regions:
  amazon_basin:
    label: "Amazon Basin"
    priority: 1
    bbox: [100.0, 0.0, 102.0, 3.0]
  sudd:
    label: "Sudd Wetland"
    priority: 2
    bbox: [101.0, 1.0, 103.0, 3.0]
""".strip(),
        encoding="utf-8",
    )

    exit_code = module.main(
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--regions-file",
            str(regions_file),
            "--imagery-dir",
            str(imagery_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "amazon_basin.png").is_file()
    assert (output_dir / "sudd.png").is_file()
