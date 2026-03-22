"""Tests for Landsat reference download planning and execution."""

# ruff: noqa: N802

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from WA.comparison.focus_areas import select_focus_areas
from WA.validation.gee_client import EarthEngineClient
from WA.validation.landsat_reference import (
    download_landsat_reference,
    resolve_landsat_fusion_window,
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

    def select(self, bands: object, names: object | None = None) -> FakeImage:
        return FakeImage(f"{self.identifier}|select={bands}|rename={names}")

    def bitwiseAnd(self, value: int) -> FakeImage:
        return FakeImage(f"{self.identifier}|bitand={value}")

    def eq(self, value: int) -> FakeImage:
        return FakeImage(f"{self.identifier}|eq={value}")

    def And(self, other: object) -> FakeImage:
        return FakeImage(f"{self.identifier}|and={other}")

    def multiply(self, value: float) -> FakeImage:
        return FakeImage(f"{self.identifier}|mul={value}")

    def add(self, value: float) -> FakeImage:
        return FakeImage(f"{self.identifier}|add={value}")

    def updateMask(self, mask: object) -> FakeImage:
        return FakeImage(f"{self.identifier}|mask={mask}")

    def visualize(self, **kwargs: object) -> FakeImage:
        return FakeImage(f"{self.identifier}|visualize={kwargs}")

    def getDownloadURL(self, params: dict[str, object]) -> str:
        return f"https://example.test/landsat-download?{self.identifier}&scale={params['scale']}"

    def getThumbURL(self, params: dict[str, object]) -> str:
        return f"https://example.test/landsat-thumb?{self.identifier}&dim={params['dimensions']}"


class FakeImageCollection:
    def __init__(self, identifier: str, *, size: int = 1) -> None:
        self.identifier = identifier
        self._size = size

    def filterBounds(self, geometry: object) -> FakeImageCollection:
        return self

    def filterDate(self, start: str, end: str) -> FakeImageCollection:
        return self

    def map(self, func) -> FakeImageCollection:  # type: ignore[no-untyped-def]
        func(FakeImage(f"{self.identifier}|map"))
        return self

    def merge(self, other: FakeImageCollection) -> FakeImageCollection:
        return FakeImageCollection(
            f"{self.identifier}|merge={other.identifier}",
            size=self._size + other._size,
        )

    def size(self) -> FakeSize:
        return FakeSize(self._size)

    def median(self) -> FakeImage:
        return FakeImage(self.identifier)


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


def test_resolve_landsat_fusion_window_expands_to_two_month_padding() -> None:
    assert resolve_landsat_fusion_window("1980-01-01") is None
    window = resolve_landsat_fusion_window("2019-07-15")
    assert window == (pd.Timestamp("2019-05-01"), pd.Timestamp("2019-10-01"))


def test_download_landsat_reference_can_materialize_artifacts(tmp_path: Path) -> None:
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
        target_time="2019-07-01",
        top_n=1,
    )[0]

    written: list[Path] = []

    def fake_download(url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(url, encoding="utf-8")
        written.append(destination)

    artifact = download_landsat_reference(
        focus_area,
        EarthEngineClient("geopy-472814", ee_module=FakeEeModule()),
        results_root=tmp_path,
        download_file=fake_download,
    )

    assert artifact.status == "downloaded"
    assert len(written) == 2
    assert artifact.quicklook_path.exists()
    assert artifact.chip_path.exists()
    assert "quicklooks_landsat" in str(artifact.quicklook_path)
    assert "rough_truth_landsat" in str(artifact.chip_path)
    assert artifact.window_start == pd.Timestamp("2019-05-01")
    assert artifact.window_end == pd.Timestamp("2019-10-01")
    assert "scale=250" in artifact.chip_path.read_text(encoding="utf-8")
