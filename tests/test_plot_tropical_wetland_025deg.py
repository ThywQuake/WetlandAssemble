from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import matplotlib.axes
import matplotlib.figure
import numpy as np
import pytest
import xarray as xr


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "plot_tropical_wetland_025deg.py"
    )
    spec = importlib.util.spec_from_file_location("plot_tropical_wetland_025deg", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_backbone_module():
    return importlib.import_module("WA.comparison.percentage_backbone")


class _DummyLoader:
    def __init__(self, dataset: xr.Dataset) -> None:
        self.dataset = dataset
        self.calls = 0

    def load(self, *, bbox, time_range):  # noqa: ANN001
        del bbox, time_range
        self.calls += 1
        return self.dataset.copy(deep=True)


def _sample_dataset() -> xr.Dataset:
    dataset = xr.Dataset(
        {
            "wetland_fraction": xr.DataArray(
                np.array(
                    [
                        [0.2, 0.4],
                        [0.6, 0.8],
                    ],
                    dtype=np.float32,
                ),
                dims=("lat", "lon"),
                attrs={"semantic_mapping": {"wetland_fraction": "demo_fraction"}},
            ),
        },
        coords={
            "lat": np.array([5.0, -5.0], dtype=np.float32),
            "lon": np.array([100.0, 110.0], dtype=np.float32),
        },
        attrs={"semantic_mapping": {"wetland_fraction": "demo_fraction"}},
    )
    dataset["lat"].attrs["nested"] = {"units": "degrees_north"}
    return dataset


def _write_gwd30_stage1_fixture(output_root: Path, *, year: int = 2016) -> Path:
    tiles_dir = output_root / "pixel_stats" / "gwd30" / f"gwd30_{year}" / "monthly" / "tiles"
    tiles_dir.mkdir(parents=True)
    tile_path = tiles_dir / "tile_demo.nc"
    xr.Dataset(
        {
            "wetland_fraction": xr.DataArray(
                np.full((12, 1, 1), 0.5, dtype=np.float32),
                dims=("time", "lat", "lon"),
                coords={
                    "time": np.array(
                        [f"{year}-{month:02d}-01" for month in range(1, 13)], dtype="datetime64[ns]"
                    ),
                    "lat": [0.5],
                    "lon": [100.5],
                },
            )
        }
    ).to_netcdf(tile_path)
    manifest_path = (
        output_root / "pixel_stats" / "gwd30" / f"gwd30_{year}" / "monthly" / "tile_manifest.json"
    )
    manifest_path.write_text(
        (
            "{\n"
            f'  "year": {year},\n'
            '  "aggregation": "monthly",\n'
            '  "tile_count": 1,\n'
            f'  "output_dir": "{tiles_dir}",\n'
            '  "tiles": [\n'
            f'    {{"path": "{tile_path}", "bbox": [100.0, 0.0, 101.0, 1.0]}}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    return tile_path


def test_load_tropical_surface_writes_all_stage_caches_and_reuses_final_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_backbone_module()
    loader = _DummyLoader(_sample_dataset())
    bbox = (-180.0, -35.0, 180.0, 35.0)
    region_id = "global_tropical_subtropical_35"

    monkeypatch.setattr(
        module,
        "load_config",
        lambda *_args, **_kwargs: SimpleNamespace(datasets={"g2017": {"name": "G2017"}}),
    )
    monkeypatch.setattr(module, "get_loader", lambda *_args, **_kwargs: loader)

    cache_dir = tmp_path / "cache"
    actual_year, coarse = module.load_tropical_surface(
        "g2017",
        region_id=region_id,
        bbox=bbox,
        target_year=None,
        resolution_deg=10.0,
        cache_dir=cache_dir,
        prefer_cache=True,
        write_cache=True,
    )

    assert actual_year is None
    assert loader.calls == 1

    for stage_name in (
        module.STAGE_LOADED,
        module.STAGE_WETLAND,
        module.STAGE_AGGREGATED,
        module.STAGE_CLIPPED,
        module.STAGE_COARSE,
    ):
        path = module.stage_cache_path(
            cache_dir,
            "g2017",
            region_id,
            target_year=None,
            resolution_deg=10.0,
            stage_name=stage_name,
        )
        assert path.is_file()

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("loader should not be called when final cache is available")

    monkeypatch.setattr(module, "get_loader", _fail_if_called)
    cached_year, cached_coarse = module.load_tropical_surface(
        "g2017",
        region_id=region_id,
        bbox=bbox,
        target_year=None,
        resolution_deg=10.0,
        cache_dir=cache_dir,
        prefer_cache=True,
        write_cache=True,
    )

    assert cached_year is None
    xr.testing.assert_allclose(cached_coarse, coarse)


def test_load_tropical_surface_can_bypass_existing_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_backbone_module()
    loader = _DummyLoader(_sample_dataset())
    bbox = (-180.0, -35.0, 180.0, 35.0)
    region_id = "global_tropical_subtropical_35"

    monkeypatch.setattr(
        module,
        "load_config",
        lambda *_args, **_kwargs: SimpleNamespace(datasets={"g2017": {"name": "G2017"}}),
    )
    monkeypatch.setattr(module, "get_loader", lambda *_args, **_kwargs: loader)

    cache_dir = tmp_path / "cache"
    module.load_tropical_surface(
        "g2017",
        region_id=region_id,
        bbox=bbox,
        target_year=None,
        resolution_deg=10.0,
        cache_dir=cache_dir,
        prefer_cache=True,
        write_cache=True,
    )
    assert loader.calls == 1

    module.load_tropical_surface(
        "g2017",
        region_id=region_id,
        bbox=bbox,
        target_year=None,
        resolution_deg=10.0,
        cache_dir=cache_dir,
        prefer_cache=False,
        write_cache=True,
    )
    assert loader.calls == 2


def test_load_tropical_surface_ignores_stale_coarse_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_backbone_module()
    loader = _DummyLoader(_sample_dataset())
    bbox = (-180.0, -35.0, 180.0, 35.0)
    region_id = "global_tropical_subtropical_35"

    monkeypatch.setattr(
        module,
        "load_config",
        lambda *_args, **_kwargs: SimpleNamespace(datasets={"g2017": {"name": "G2017"}}),
    )
    monkeypatch.setattr(module, "get_loader", lambda *_args, **_kwargs: loader)

    cache_dir = tmp_path / "cache"
    stale_path = module.stage_cache_path(
        cache_dir,
        "g2017",
        region_id,
        target_year=None,
        resolution_deg=10.0,
        stage_name=module.STAGE_COARSE,
    )
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    xr.DataArray(
        np.array([[0.5]], dtype=np.float32),
        dims=("lat", "lon"),
        coords={"lat": [0.0], "lon": [100.0]},
    ).to_netcdf(stale_path)

    module.load_tropical_surface(
        "g2017",
        region_id=region_id,
        bbox=bbox,
        target_year=None,
        resolution_deg=10.0,
        cache_dir=cache_dir,
        prefer_cache=True,
        write_cache=True,
    )

    assert loader.calls == 1


def test_load_tropical_surface_supports_gwd30_stage1_tiles(tmp_path: Path) -> None:
    module = _load_backbone_module()
    output_root = tmp_path / "results"
    _write_gwd30_stage1_fixture(output_root)

    actual_year, coarse = module.load_tropical_surface(
        "gwd30",
        region_id="amazon",
        bbox=(100.0, 0.0, 101.0, 1.0),
        target_year=2016,
        resolution_deg=1.0,
        cache_dir=tmp_path / "cache",
        output_root=output_root,
        prefer_cache=True,
        write_cache=True,
        show_progress=False,
    )

    assert actual_year == 2016
    assert coarse.shape == (1, 1)
    assert coarse.values[0, 0] == pytest.approx(0.5)


def test_save_surface_plot_writes_netcdf_before_png(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_backbone_module()
    surface = _sample_dataset()["wetland_fraction"]
    bbox = (-180.0, -35.0, 180.0, 35.0)
    region_id = "global_tropical_subtropical_35"

    def _boom(*_args, **_kwargs):
        raise RuntimeError("png write failed")

    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", _boom)

    with pytest.raises(RuntimeError, match="png write failed"):
        module.save_surface_plot(
            surface,
            "g2017",
            region_id=region_id,
            region_label="Global Tropical and Subtropical Belt (35°S to 35°N)",
            bbox=bbox,
            output_dir=tmp_path,
            actual_year=None,
        )

    assert (tmp_path / f"g2017_{region_id}_025deg.nc").is_file()
    assert not (tmp_path / f"g2017_{region_id}_025deg.png").exists()


def test_save_surface_plot_uses_simple_dataset_title(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_backbone_module()
    surface = _sample_dataset()["wetland_fraction"]
    bbox = (-180.0, -35.0, 180.0, 35.0)
    region_id = "global_tropical_subtropical_35"
    recorded_titles: list[str] = []
    original_set_title = matplotlib.axes.Axes.set_title

    def _record_title(self, label, *args, **kwargs):  # noqa: ANN001
        recorded_titles.append(label)
        return original_set_title(self, label, *args, **kwargs)

    monkeypatch.setattr(matplotlib.axes.Axes, "set_title", _record_title)

    module.save_surface_plot(
        surface,
        "g2017",
        region_id=region_id,
        region_label="Global Tropical and Subtropical Belt (35°S to 35°N)",
        bbox=bbox,
        output_dir=tmp_path,
        actual_year=2016,
    )

    assert recorded_titles[-1] == "G2017"


def test_save_overview_plot_creates_stacked_png(tmp_path: Path) -> None:
    module = _load_backbone_module()
    surface_a = _sample_dataset()["wetland_fraction"]
    surface_b = surface_a * 0.5

    result = module.save_overview_plot(
        [("g2017", surface_a), ("swamps", surface_b)],
        region_id="global_tropical_subtropical_35",
        region_label="Global Tropical and Subtropical Belt (35°S to 35°N)",
        bbox=(-180.0, -35.0, 180.0, 35.0),
        output_dir=tmp_path,
    )

    assert result == tmp_path / "overview_global_tropical_subtropical_35_025deg.png"
    assert result.is_file()
    assert result.stat().st_size > 0


def test_bbox_to_cartopy_extent_reorders_bbox_axes() -> None:
    module = _load_backbone_module()

    assert module._bbox_to_cartopy_extent((-180.0, -23.5, 180.0, 23.5)) == (
        -180.0,
        180.0,
        -23.5,
        23.5,
    )


def test_resolve_plot_region_reads_bbox_from_catalog(tmp_path: Path) -> None:
    module = _load_backbone_module()
    regions_path = tmp_path / "regions.yaml"
    regions_path.write_text(
        """
regions:
  global_tropical_subtropical_35:
    label: "Global Tropical and Subtropical Belt (35°S to 35°N)"
    bbox: [-180.0, -35.0, 180.0, 35.0]
""".strip(),
        encoding="utf-8",
    )

    label, bbox = module.resolve_plot_region(
        "global_tropical_subtropical_35",
        regions_file=regions_path,
    )

    assert label == "Global Tropical and Subtropical Belt (35°S to 35°N)"
    assert bbox == (-180.0, -35.0, 180.0, 35.0)


def test_plot_script_help_mentions_gwd30_and_output_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/plot_tropical_wetland_025deg.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "gwd30" in completed.stdout.lower()
    assert "--output-root" in completed.stdout
    assert "--progress" in completed.stdout
