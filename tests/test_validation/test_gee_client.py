"""Tests for the GEE client wrapper."""

# ruff: noqa: N802

from __future__ import annotations

import pytest

from WA.validation.gee_client import EarthEngineClient, GeeInitializationError

pytestmark = pytest.mark.gee


class FakeEeModule:
    def __init__(self) -> None:
        self.initialized_projects: list[str | None] = []
        self.auth_calls = 0

        class GeometryNamespace:
            @staticmethod
            def Rectangle(coords: list[float], *, proj: str, geodesic: bool) -> dict[str, object]:
                return {"coords": coords, "proj": proj, "geodesic": geodesic}

        self.Geometry = GeometryNamespace

    def Initialize(self, *, project: str | None = None) -> None:
        self.initialized_projects.append(project)

    def Authenticate(self) -> None:
        self.auth_calls += 1


class FailingThenWorkingEeModule(FakeEeModule):
    def __init__(self) -> None:
        super().__init__()
        self.fail_once = True

    def Initialize(self, *, project: str | None = None) -> None:
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("missing credentials")
        super().Initialize(project=project)


def test_gee_client_initializes_with_project_id() -> None:
    ee_module = FakeEeModule()
    client = EarthEngineClient.from_config(
        {"gee_project_id": "geopy-472814"},
        ee_module=ee_module,
    )

    client.authenticate_and_initialize()

    assert ee_module.initialized_projects == ["geopy-472814"]
    assert client.rectangle((-1.0, -2.0, 3.0, 4.0)) == {
        "coords": [-1.0, -2.0, 3.0, 4.0],
        "proj": "EPSG:4326",
        "geodesic": False,
    }


def test_gee_client_can_fallback_to_interactive_auth() -> None:
    ee_module = FailingThenWorkingEeModule()
    client = EarthEngineClient("geopy-472814", ee_module=ee_module)

    client.authenticate_and_initialize(allow_interactive_auth=True)

    assert ee_module.auth_calls == 1
    assert ee_module.initialized_projects == ["geopy-472814"]


def test_gee_client_raises_without_auth_fallback() -> None:
    ee_module = FailingThenWorkingEeModule()
    client = EarthEngineClient("geopy-472814", ee_module=ee_module)

    with pytest.raises(GeeInitializationError, match="Failed to initialize"):
        client.authenticate_and_initialize()
