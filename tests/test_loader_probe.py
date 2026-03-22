from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from WA.config import AppConfig
from WA.loader_probe import (
    DEFAULT_PROBE_BBOX,
    ProbeOptions,
    collect_input_discovery,
    compact_discovery_preview,
    compact_discovery_summary,
    derive_probe_time_range,
    make_json_safe,
    probe_dataset,
    render_probe_report,
    resolve_probe_bbox,
)
from WA.loaders.base import BBox, DatasetLoader, DatasetMetadata, TimeRange


class DummyLoader(DatasetLoader):
    def __init__(
        self,
        dataset_id: str,
        config: dict[str, object],
        dataset: xr.Dataset,
        *,
        is_static: bool = False,
        should_fail: bool = False,
    ) -> None:
        super().__init__(dataset_id, config)
        self._dataset = dataset
        self._is_static = is_static
        self._should_fail = should_fail

    def load(
        self,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
    ) -> xr.Dataset:
        if self._should_fail:
            raise FileNotFoundError("missing HPC file")
        return self._dataset

    def metadata(self) -> DatasetMetadata:
        return DatasetMetadata(
            dataset_id=self.dataset_id,
            name=self.name,
            source_path=str(self.base_path),
            crs="EPSG:4326",
            spatial_resolution="1deg",
            temporal_coverage=None if self._is_static else ("2000-01-01", "2001-12-31"),
            time_resolution=None if self._is_static else "monthly",
            is_static=self._is_static,
            is_classification=False,
            native_variables=("wetland_fraction",),
            semantic_mapping={"wetland_fraction": "dummy"},
        )


class DiscoverFilesLoader(DummyLoader):
    def _discover_files(
        self,
        time_range: TimeRange | None = None,
    ) -> dict[tuple[str, str], list[tuple[int, Path]]]:
        return {
            ("cfg_a", "force_a"): [
                (2000, self.base_path / "cfg_a/force_a_2000.nc"),
                (2001, self.base_path / "cfg_a/force_a_2001.nc"),
            ]
        }


def build_app_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        datasets={},
        regions={"tropical": {"bbox": [-180, -23.5, 180, 23.5]}},
        analysis={},
        gee={"gee_project_id": "demo-project"},
        dataset_config_path=tmp_path / "datasets.yaml",
        gee_config_path=tmp_path / "gee.yaml",
    )


def test_resolve_probe_bbox_defaults_to_safe_amazon_window(tmp_path: Path) -> None:
    app_config = build_app_config(tmp_path)

    bbox, label = resolve_probe_bbox(
        app_config,
        bbox_text=None,
        region_name=None,
        unsafe_full_spatial_scan=False,
    )

    assert bbox == DEFAULT_PROBE_BBOX
    assert label == "default_amazon_probe"


def test_derive_probe_time_range_uses_one_month_window_for_dynamic_loader(tmp_path: Path) -> None:
    dataset = xr.Dataset(
        {"wetland_fraction": (("time",), np.array([1.0], dtype=np.float32))},
        coords={"time": np.array(["2000-01-01"], dtype="datetime64[ns]")},
    )
    loader = DummyLoader(
        "dummy",
        {"name": "Dummy", "path": str(tmp_path)},
        dataset,
    )

    assert derive_probe_time_range(loader, requested_time_range=None) == (
        "2000-01-01",
        "2000-01-31",
    )


def test_probe_dataset_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_file = tmp_path / "sample.nc"
    target_file.write_text("placeholder", encoding="utf-8")

    dataset = xr.Dataset(
        {
            "wetland_fraction": (
                ("time", "lat", "lon"),
                np.array([[[1.0, 2.0], [3.0, 4.0]]], dtype=np.float32),
            )
        },
        coords={
            "time": np.array(["2000-01-01"], dtype="datetime64[ns]"),
            "lat": [0.0, 1.0],
            "lon": [10.0, 11.0],
        },
    )
    config = {
        "loader_type": "netcdf",
        "name": "Dummy",
        "path": str(tmp_path),
        "file": "sample.nc",
    }
    options = ProbeOptions(
        bbox=None,
        bbox_label="test",
        time_range=None,
        compute_sample=True,
        metadata_only=False,
        sample_size=1,
        preview_items=3,
        fail_fast=False,
    )

    monkeypatch.setattr(
        "WA.loader_probe.get_loader",
        lambda dataset_id, dataset_config: DummyLoader(dataset_id, dataset_config, dataset),
    )
    success = probe_dataset("dummy", config, options)

    assert success.status == "sampled"
    assert success.discovery["target_file_exists"] is True
    assert success.sample_summary is not None
    assert success.sample_summary["variables"]["wetland_fraction"]["max"] == 1.0

    monkeypatch.setattr(
        "WA.loader_probe.get_loader",
        lambda dataset_id, dataset_config: DummyLoader(
            dataset_id,
            dataset_config,
            dataset,
            should_fail=True,
        ),
    )
    failed = probe_dataset("dummy", config, options)

    assert failed.status == "failed"
    assert failed.error is not None
    report = render_probe_report(build_app_config(tmp_path), ["dummy"], options, [failed])
    assert "missing HPC file" in report


def test_collect_input_discovery_summarizes_discover_files_loader(tmp_path: Path) -> None:
    dataset = xr.Dataset(
        {"wetland_fraction": (("time",), np.array([1.0], dtype=np.float32))},
        coords={"time": np.array(["2000-01-01"], dtype="datetime64[ns]")},
    )
    loader = DiscoverFilesLoader(
        "dummy",
        {"loader_type": "topmodel", "name": "Dummy", "path": str(tmp_path)},
        dataset,
    )

    discovery = collect_input_discovery(
        loader,
        bbox=None,
        time_range=("2000-01-01", "2000-01-31"),
        preview_items=2,
    )

    assert discovery["matched_groups"] == 1
    assert discovery["matched_files"] == 2
    assert compact_discovery_summary(discovery) == {
        "path_exists": True,
        "matched_files": 2,
        "matched_groups": 1,
    }
    assert compact_discovery_preview(discovery) == "group=cfg_a/force_a years=[2000, 2001]"


def test_make_json_safe_converts_non_finite_floats_to_none() -> None:
    payload = {
        "plain_nan": float("nan"),
        "plain_inf": float("inf"),
        "numpy_nan": np.float32(np.nan),
        "nested": [1.0, np.float64(np.inf)],
    }

    converted = make_json_safe(payload)

    assert converted == {
        "plain_nan": None,
        "plain_inf": None,
        "numpy_nan": None,
        "nested": [1.0, None],
    }
