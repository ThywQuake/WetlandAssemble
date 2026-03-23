# ruff: noqa: N802
"""Shared GEE test doubles for validation tests."""

from __future__ import annotations


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

    def bitwiseAnd(self, value: int) -> FakeImage:
        return FakeImage(f"{self.identifier}|bitand={value}")

    def rightShift(self, value: int) -> FakeImage:
        return FakeImage(f"{self.identifier}|rshift={value}")

    def eq(self, value: int) -> FakeImage:
        return FakeImage(f"{self.identifier}|eq={value}")

    def lte(self, value: int) -> FakeImage:
        return FakeImage(f"{self.identifier}|lte={value}")

    def gte(self, value: float) -> FakeImage:
        return FakeImage(f"{self.identifier}|gte={value}")

    def And(self, other: object) -> FakeImage:
        return FakeImage(f"{self.identifier}|and={other}")

    def Or(self, other: object) -> FakeImage:
        return FakeImage(f"{self.identifier}|or={other}")

    def updateMask(self, mask: object) -> FakeImage:
        return FakeImage(f"{self.identifier}|mask={mask}")

    def visualize(self, **kwargs: object) -> FakeImage:
        return FakeImage(f"{self.identifier}|visualize={kwargs}")

    def get(self, key: str) -> FakeImage:
        return FakeImage(f"{self.identifier}|get={key}")

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


class FakeFilter:
    @staticmethod
    def equals(*, leftField: str, rightField: str) -> dict[str, str]:  # noqa: N803
        return {"leftField": leftField, "rightField": rightField}


class FakeJoin:
    @staticmethod
    def saveFirst(field: str) -> FakeJoinInstance:
        return FakeJoinInstance(field)


class FakeJoinInstance:
    def __init__(self, field: str) -> None:
        self.field = field

    def apply(
        self,
        *,
        primary: FakeImageCollection,
        secondary: FakeImageCollection,
        condition: object,
    ) -> FakeImageCollection:
        return primary


class FakeEeModule:
    """Configurable fake of the ``ee`` module for offline testing."""

    def __init__(self, *, collection_size: int = 1) -> None:
        self.collection_size = collection_size
        self.Filter = FakeFilter
        self.Join = FakeJoin

        class GeometryNamespace:
            @staticmethod
            def Rectangle(
                coords: list[float], *, proj: str, geodesic: bool
            ) -> dict[str, object]:
                return {"coords": coords, "proj": proj, "geodesic": geodesic}

        self.Geometry = GeometryNamespace

    def Initialize(self, *, project: str | None = None) -> None:
        return None

    def Image(self, source: object) -> FakeImage:
        return FakeImage(f"Image({source})")

    def ImageCollection(self, identifier: object) -> FakeImageCollection:
        if isinstance(identifier, FakeImageCollection):
            return identifier
        return FakeImageCollection(str(identifier), size=self.collection_size)
