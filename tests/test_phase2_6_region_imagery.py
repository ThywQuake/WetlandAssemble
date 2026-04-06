# ruff: noqa: N802

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from urllib.error import HTTPError

import pandas as pd

from WA.config import AppConfig
from WA.phase26_region_imagery import (
    Phase26RegionQuicklookArtifact,
    download_phase26_region_quicklook,
    find_phase26_region_quicklook,
    phase26_region_quicklook_path,
    resolve_phase26_region_window,
)
from WA.validation.gee_client import EarthEngineClient


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

    def updateMask(self, mask: object) -> FakeImage:  # noqa: N802
        return FakeImage(f"{self.identifier}|mask={mask}")

    def visualize(self, **kwargs: object) -> FakeImage:
        return FakeImage(f"{self.identifier}|visualize={kwargs}")

    def getThumbURL(self, params: dict[str, object]) -> str:  # noqa: N802
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

    def map(self, func):  # type: ignore[no-untyped-def]
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


def _load_download_script_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "download_phase2_6_region_imagery.py"
    )
    spec = importlib.util.spec_from_file_location("download_phase2_6_region_imagery", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_phase26_region_window_is_annual() -> None:
    assert resolve_phase26_region_window(1999) is None
    assert resolve_phase26_region_window(2016) == (
        pd.Timestamp("2016-01-01"),
        pd.Timestamp("2017-01-01"),
    )


def test_download_phase26_region_quicklook_writes_jpg(tmp_path: Path) -> None:
    written: list[Path] = []

    def fake_download(url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(url, encoding="utf-8")
        written.append(destination)

    artifact = download_phase26_region_quicklook(
        "amazon_basin",
        (-75.0, -20.0, -45.0, 5.0),
        EarthEngineClient("test-project", ee_module=FakeEeModule()),
        output_dir=tmp_path,
        target_year=2016,
        download_file=fake_download,
    )

    assert artifact.status == "downloaded"
    assert artifact.quicklook_path == phase26_region_quicklook_path(
        tmp_path,
        region_id="amazon_basin",
        target_year=2016,
    )
    assert artifact.quicklook_path.exists()
    assert written == [artifact.quicklook_path]
    assert find_phase26_region_quicklook(
        tmp_path,
        region_id="amazon_basin",
        target_year=2016,
    ) == artifact.quicklook_path


def test_download_phase26_region_quicklook_falls_back_after_http_400(
    tmp_path: Path,
) -> None:
    attempts: list[str] = []

    def fake_download(url: str, destination: Path) -> None:
        attempts.append(url)
        if "dim=1536" in url:
            raise HTTPError(url, 400, "Bad Request", hdrs=None, fp=None)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(url, encoding="utf-8")

    artifact = download_phase26_region_quicklook(
        "pantanal_upper_paraguay",
        (-61.5, -22.5, -54.0, -14.0),
        EarthEngineClient("test-project", ee_module=FakeEeModule()),
        output_dir=tmp_path,
        target_year=2016,
        dimensions=1536,
        download_file=fake_download,
    )

    assert artifact.status == "downloaded"
    assert artifact.quicklook_path.exists()
    assert len(attempts) == 2
    assert "dim=1536" in attempts[0]
    assert "dim=1024" in attempts[1]
    assert artifact.message == "quicklook_dimensions_used=1024"


def test_download_phase2_6_region_imagery_script_writes_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_download_script_module()

    app_config = AppConfig(
        datasets={},
        regions={},
        analysis={},
        gee={"gee_project_id": "test-project"},
        dataset_config_path=tmp_path / "datasets.yaml",
        gee_config_path=tmp_path / "gee.yaml",
    )

    monkeypatch.setattr(module, "load_config", lambda *_args, **_kwargs: app_config)

    class FakeEarthEngineClient:
        @classmethod
        def from_config(cls, gee: dict[str, object]) -> object:
            return {"gee": gee}

    monkeypatch.setattr(module, "EarthEngineClient", FakeEarthEngineClient)

    def fake_download_phase26_region_quicklook(  # type: ignore[no-untyped-def]
        region_id,
        bbox,
        gee_client,
        *,
        output_dir,
        target_year=2016,
        allow_interactive_auth=False,
        skip_existing=True,
        dimensions=1536,
    ):
        quicklook_path = (
            Path(output_dir) / str(target_year) / region_id / f"{region_id}_modis_rgb.jpg"
        )
        quicklook_path.parent.mkdir(parents=True, exist_ok=True)
        quicklook_path.write_text("fake-image", encoding="utf-8")
        return Phase26RegionQuicklookArtifact(
            region_id=region_id,
            target_year=target_year,
            window_start=pd.Timestamp(f"{target_year}-01-01"),
            window_end=pd.Timestamp(f"{target_year + 1}-01-01"),
            quicklook_path=quicklook_path,
            status="downloaded",
        )

    monkeypatch.setattr(
        module,
        "download_phase26_region_quicklook",
        fake_download_phase26_region_quicklook,
    )

    regions_file = tmp_path / "regions.yaml"
    regions_file.write_text(
        """
regions:
  amazon_basin:
    label: "Amazon Basin"
    priority: 1
    bbox: [-75.0, -20.0, -45.0, 5.0]
""".strip(),
        encoding="utf-8",
    )

    output_dir = tmp_path / "phase2.6_region_imagery"
    exit_code = module.main(
        [
            "--regions-file",
            str(regions_file),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    manifest_path = output_dir / "phase2_6_region_imagery_2016_manifest.json"
    assert manifest_path.is_file()

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["status_counts"] == {"downloaded": 1}
    assert payload["artifacts"][0]["region_id"] == "amazon_basin"
    assert payload["artifacts"][0]["quicklook_path"].endswith("amazon_basin_modis_rgb.jpg")
