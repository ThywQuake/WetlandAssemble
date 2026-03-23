"""Tests for Sentinel-2 reference download planning and execution."""

# ruff: noqa: N802
from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_validation.conftest import FakeEeModule
from WA.comparison.hotspots import EntropyHotspot
from WA.validation.gee_client import EarthEngineClient
from WA.validation.s2_reference import download_s2_reference

pytestmark = pytest.mark.gee


def _dummy_hotspot() -> EntropyHotspot:
    return EntropyHotspot(
        hotspot_id="entropy-brazil-001",
        region_slug="brazil",
        bbox=(-62.0, -6.0, -60.0, -4.0),
        center_lon=-61.0,
        center_lat=-5.0,
        mean_entropy=0.85,
        max_entropy=0.95,
        cell_count=12,
        class_disagreement_summary={"0": 0.1, "1": 0.3, "2": 0.6},
    )


def test_s2_unsupported_time_window_before_2017(tmp_path: Path) -> None:
    client = EarthEngineClient("geopy-472814", ee_module=FakeEeModule())
    artifact = download_s2_reference(
        _dummy_hotspot(),
        client,
        target_time="2015-01-01",
        results_root=tmp_path,
    )
    assert artifact.status == "unsupported_time_window"
    assert "2017" in (artifact.message or "")


def test_s2_cached_skips_download(tmp_path: Path) -> None:
    hotspot = _dummy_hotspot()
    client = EarthEngineClient("geopy-472814", ee_module=FakeEeModule())

    # First download: creates artifacts
    def fake_download(url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake")

    first = download_s2_reference(
        hotspot,
        client,
        target_time="2019-07-01",
        results_root=tmp_path,
        download_file_fn=fake_download,
    )
    assert first.status == "downloaded"

    # Second download: should be cached
    second = download_s2_reference(
        hotspot,
        client,
        target_time="2019-07-01",
        results_root=tmp_path,
        download_file_fn=fake_download,
    )
    assert second.status == "cached"


def test_s2_gee_auth_failed_returns_terminal_state(tmp_path: Path) -> None:
    class FailingEeModule:
        def Initialize(self, *, project: str | None = None) -> None:
            raise RuntimeError("Auth failed")

    client = EarthEngineClient("geopy-472814", ee_module=FailingEeModule())
    artifact = download_s2_reference(
        _dummy_hotspot(),
        client,
        target_time="2019-07-01",
        results_root=tmp_path,
    )
    assert artifact.status == "gee_auth_failed"


def test_s2_empty_collection_returns_terminal_state(tmp_path: Path) -> None:
    client = EarthEngineClient(
        "geopy-472814", ee_module=FakeEeModule(collection_size=0)
    )
    artifact = download_s2_reference(
        _dummy_hotspot(),
        client,
        target_time="2019-07-01",
        results_root=tmp_path,
    )
    assert artifact.status == "empty_collection"


def test_s2_download_success_creates_artifacts(tmp_path: Path) -> None:
    downloaded_urls: list[str] = []

    def fake_download(url: str, dest: Path) -> None:
        downloaded_urls.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake-image-data")

    client = EarthEngineClient("geopy-472814", ee_module=FakeEeModule())
    artifact = download_s2_reference(
        _dummy_hotspot(),
        client,
        target_time="2019-07-01",
        results_root=tmp_path,
        download_file_fn=fake_download,
    )

    assert artifact.status == "downloaded"
    assert artifact.quicklook_path.exists()
    assert artifact.chip_path.exists()
    assert artifact.quicklook_path.name.endswith("_s2_rgb.jpg")
    assert artifact.chip_path.name.endswith("_s2_chip.tif")
    assert len(downloaded_urls) == 2


def test_s2_download_failed_returns_terminal_state(tmp_path: Path) -> None:
    def failing_download(url: str, dest: Path) -> None:
        raise ConnectionError("Network error")

    client = EarthEngineClient("geopy-472814", ee_module=FakeEeModule())
    artifact = download_s2_reference(
        _dummy_hotspot(),
        client,
        target_time="2019-07-01",
        results_root=tmp_path,
        download_file_fn=failing_download,
    )

    assert artifact.status == "download_failed"
    assert "Network error" in (artifact.message or "")
