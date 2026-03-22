"""Thin Google Earth Engine client wrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

from WA.loaders.base import BBox


class GeeInitializationError(RuntimeError):
    """Raised when Earth Engine authentication or initialization fails."""


@dataclass
class EarthEngineClient:
    """Lazily import, authenticate, and initialize the Earth Engine SDK."""

    project_id: str
    ee_module: Any | None = None
    _initialized: bool = field(default=False, init=False, repr=False)

    @classmethod
    def from_config(
        cls,
        gee_config: dict[str, object],
        ee_module: Any | None = None,
    ) -> EarthEngineClient:
        project_id = gee_config.get("gee_project_id")
        if not isinstance(project_id, str) or not project_id:
            raise ValueError("GEE config must contain a non-empty gee_project_id")
        return cls(project_id=project_id, ee_module=ee_module)

    @property
    def ee(self) -> Any:
        if self.ee_module is None:
            try:
                self.ee_module = import_module("ee")
            except ModuleNotFoundError as exc:
                raise GeeInitializationError(
                    "earthengine-api is not installed; install it before running GEE workflows"
                ) from exc
        return self.ee_module

    def authenticate_and_initialize(self, *, allow_interactive_auth: bool = False) -> Any:
        """Initialize the Earth Engine SDK, optionally falling back to interactive auth."""

        if self._initialized:
            return self.ee

        ee = self.ee
        try:
            ee.Initialize(project=self.project_id)
        except Exception as exc:
            if not allow_interactive_auth or not hasattr(ee, "Authenticate"):
                raise GeeInitializationError(
                    f"Failed to initialize Earth Engine for project {self.project_id}"
                ) from exc
            ee.Authenticate()
            try:
                ee.Initialize(project=self.project_id)
            except Exception as auth_exc:
                raise GeeInitializationError(
                    "Failed to initialize Earth Engine for project "
                    f"{self.project_id} after authentication"
                ) from auth_exc

        self._initialized = True
        return ee

    def rectangle(self, bbox: BBox) -> Any:
        """Construct an EPSG:4326 rectangle geometry for the given bounding box."""

        return self.ee.Geometry.Rectangle(list(bbox), proj="EPSG:4326", geodesic=False)
