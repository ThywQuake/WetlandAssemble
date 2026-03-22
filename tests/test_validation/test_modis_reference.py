"""Tests for MODIS reference download planning and execution."""

# ruff: noqa: N802

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.focus_areas import select_focus_areas
from WA.comparison.harmonize import (
    create_comparison_grid,
    harmonize_binary_collection,
    select_comparison_slice,
)
from WA.comparison.rough_binary import compute_rough_binary_metrics
from WA.validation.gee_client import EarthEngineClient
from WA.validation.modis_reference import (
    download_modis_reference,
    resolve_modis_composite_window,
    resolve_modis_fusion_window,
)

pytestmark = pytest.mark.gee


class FakeSize:
    def __init__(self, value: int) -> None:
        self.value = value

    def getInfo(self) -> int:
        return self.value


class FakeImage:
    def __init__(self, identifier: str) -> None:
        self.identifier = identifier

    def clip(self, geometry: object) -> FakeImage:
        return FakeImage(f"{self.identifier}|clip={geometry}")

    def select(self, bands: object) -> FakeImage:
        return FakeImage(f"{self.identifier}|select={bands}")

    def bitwiseAnd(self, value: int) -> FakeImage:  # noqa: N802
        return FakeImage(f"{self.identifier}|bitand={value}")

    def rightShift(self, value: int) -> FakeImage:  # noqa: N802
        return FakeImage(f"{self.identifier}|rshift={value}")

    def eq(self, value: int) -> FakeImage:
        return FakeImage(f"{self.identifier}|eq={value}")

    def lte(self, value: int) -> FakeImage:
        return FakeImage(f"{self.identifier}|lte={value}")

    def And(self, other: object) -> FakeImage:  # noqa: N802
        return FakeImage(f"{self.identifier}|and={other}")

    def Or(self, other: object) -> FakeImage:  # noqa: N802
        return FakeImage(f"{self.identifier}|or={other}")

    def updateMask(self, mask: object) -> FakeImage:  # noqa: N802
        return FakeImage(f"{self.identifier}|mask={mask}")

    def visualize(self, **kwargs: object) -> FakeImage:
        return FakeImage(f"{self.identifier}|visualize={kwargs}")

    def getDownloadURL(self, params: dict[str, object]) -> str:
        return f"https://example.test/download?{self.identifier}&scale={params['scale']}"

    def getThumbURL(self, params: dict[str, object]) -> str:
        return f"https://example.test/thumb?{self.identifier}&dim={params['dimensions']}"


class FakeImageCollection:
    def __init__(self, identifier: str, *, size: int = 1) -> None:
        self.identifier = identifier
        self._size = size

    def filterBounds(self, geometry: object) -> FakeImageCollection:
        return self

    def filterDate(self, start: str, end: str) -> FakeImageCollection:
        return self

    def select(self, bands: list[str]) -> FakeImageCollection:
        return self

    def map(self, func) -> FakeImageCollection:  # type: ignore[no-untyped-def]
        func(FakeImage(f"{self.identifier}|map"))
        return self

    def median(self) -> FakeImage:
        return FakeImage(self.identifier)

    def size(self) -> FakeSize:
        return FakeSize(self._size)


class FakeEeModule:
    def __init__(self, *, collection_size: int = 1) -> None:
        self.collection_size = collection_size

        class GeometryNamespace:
            @staticmethod
            def Rectangle(coords: list[float], *, proj: str, geodesic: bool) -> dict[str, object]:
                return {"coords": coords, "proj": proj, "geodesic": geodesic}

        self.Geometry = GeometryNamespace

    def Initialize(self, *, project: str | None = None) -> None:
        return None

    def ImageCollection(self, identifier: str) -> FakeImageCollection:
        return FakeImageCollection(identifier, size=self.collection_size)


def test_resolve_modis_composite_window_respects_availability() -> None:
    assert resolve_modis_composite_window("1999-12-01") is None
    window = resolve_modis_composite_window("2001-01-10")
    assert window == (pd.Timestamp("2001-01-09"), pd.Timestamp("2001-01-17"))


def test_resolve_modis_fusion_window_expands_to_multi_temporal_range() -> None:
    assert resolve_modis_fusion_window("1999-12-01") is None
    window = resolve_modis_fusion_window("2001-01-10")
    assert window == (pd.Timestamp("2000-11-01"), pd.Timestamp("2001-04-01"))


def test_download_modis_reference_reports_unsupported_window(tmp_path: Path) -> None:
    focus_area = select_focus_areas(
        xr.DataArray(
            np.array([[0.8]], dtype=np.float32),
            coords={"lat": [-4.5], "lon": [-60.5]},
            dims=("lat", "lon"),
        ),
        xr.DataArray(
            np.array([[3]], dtype=np.int32),
            coords={"lat": [-4.5], "lon": [-60.5]},
            dims=("lat", "lon"),
        ),
        target_time="1999-01-01",
        top_n=1,
    )[0]
    client = EarthEngineClient("geopy-472814", ee_module=FakeEeModule())

    artifact = download_modis_reference(focus_area, client, results_root=tmp_path)

    assert artifact.status == "unsupported_time_window"
    assert artifact.quicklook_path.name.endswith("_modis_rgb.jpg")
    assert artifact.chip_path.name.endswith("_modis_chip.tif")


def test_phase2_pipeline_can_select_aoi_and_download_modis(tmp_path: Path) -> None:
    reference = create_comparison_grid((-61.0, -6.0, -59.0, -4.0), resolution_deg=1.0)
    dataset_coords = {"lat": [-4.5, -5.5], "lon": [-60.5, -59.5]}
    datasets = {
        "g2017": xr.Dataset(
            {
                "wetland_nolake": (
                    ("lat", "lon"),
                    np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
                )
            },
            coords=dataset_coords,
            attrs={"time_resolution": None},
        ),
        "wad2m": xr.Dataset(
            {
                "wetland_fraction": (
                    ("time", "lat", "lon"),
                    np.array([[[0.9, 0.8], [0.1, 0.2]]], dtype=np.float32),
                )
            },
            coords={**dataset_coords, "time": pd.to_datetime(["2001-01-01"])},
            attrs={"time_resolution": "monthly"},
        ),
        "swamps": xr.Dataset(
            {
                "wetland_fraction": (
                    ("time", "lat", "lon"),
                    np.array([[[0.1, 0.8], [0.2, 0.2]]], dtype=np.float32),
                )
            },
            coords={**dataset_coords, "time": pd.to_datetime(["2001-01-01"])},
            attrs={"time_resolution": "monthly"},
        ),
    }

    harmonized = harmonize_binary_collection(datasets, reference)
    slices = {
        dataset_id: select_comparison_slice(surface, "2001-01-01")
        for dataset_id, surface in harmonized.items()
    }
    rough_result = compute_rough_binary_metrics(slices)
    focus_area = select_focus_areas(
        rough_result.disagreement_score,
        rough_result.participant_count,
        target_time="2001-01-01",
        wetland_vote_fraction=rough_result.wetland_vote_fraction,
        top_n=1,
        aoi_size_deg=1.0,
        min_distance_deg=0.5,
    )[0]

    written: list[Path] = []

    def fake_download(url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(url, encoding="utf-8")
        written.append(destination)

    artifact = download_modis_reference(
        focus_area,
        EarthEngineClient("geopy-472814", ee_module=FakeEeModule()),
        results_root=tmp_path,
        download_file=fake_download,
    )

    assert artifact.status == "downloaded"
    assert focus_area.region_slug == "brazil"
    assert len(written) == 2
    assert artifact.quicklook_path.exists()
    assert artifact.chip_path.exists()
    assert artifact.window_start == pd.Timestamp("2000-11-01")
    assert artifact.window_end == pd.Timestamp("2001-04-01")
    assert "20001101_20010401" in str(artifact.quicklook_path)
    assert "20001101_20010401" in str(artifact.chip_path)
