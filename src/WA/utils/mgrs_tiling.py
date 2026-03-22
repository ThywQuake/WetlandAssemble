"""GWD30 tiling system implementation based on MGRS with 15 m offsets."""

from __future__ import annotations

import logging
import math
import warnings
from typing import cast

import mgrs as mgrs_lib
from pyproj import Transformer

logger = logging.getLogger(__name__)

_BBOX_EDGE_STEP_DEG = 0.1
_HEMISPHERE_CONTEXT_MARGIN_DEG = 1.0
_MGRS_GRID_SIZE_M = 100_000.0
_MGRS_MAX_LAT = 84.0
_MGRS_MIN_LAT = -80.0
_UTM_ZONE_CONTEXT_MARGIN_DEG = 1.0


class GWD30TilingSystem:
    """Tiling system for GWD30 based on shifted MGRS-aligned UTM tiles."""

    def __init__(
        self,
        offset_x: float = -15.0,
        offset_y: float = -15.0,
        tile_size_m: float = 109830.0,
    ) -> None:
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.tile_size_m = tile_size_m

        self._mgrs = mgrs_lib.MGRS()
        self._transformers: dict[tuple[int, bool], Transformer] = {}

    def _get_transformer(self, epsg: int, inverse: bool = False) -> Transformer:
        """Get transformer from WGS84 to UTM or vice versa."""

        key = (epsg, inverse)
        if key not in self._transformers:
            if inverse:
                self._transformers[key] = Transformer.from_crs(
                    f"EPSG:{epsg}", "EPSG:4326", always_xy=True
                )
            else:
                self._transformers[key] = Transformer.from_crs(
                    "EPSG:4326", f"EPSG:{epsg}", always_xy=True
                )
        return self._transformers[key]

    def parse_tile_code(self, tile_code: str) -> dict[str, str | int]:
        """Parse tile code like ``50TMK`` or ``01KAA``."""

        if len(tile_code) == 5:
            zone = int(tile_code[0:2])
            lat_band = tile_code[2]
            square = tile_code[3:]
        elif len(tile_code) == 4:
            zone = int(tile_code[0:1])
            lat_band = tile_code[1]
            square = tile_code[2:]
        else:
            raise ValueError(f"Invalid tile code: {tile_code}")

        hemisphere = "N" if lat_band.upper() >= "N" else "S"
        return {
            "zone": zone,
            "lat_band": lat_band,
            "square": square,
            "hemisphere": hemisphere,
        }

    def _mgrs_to_utm_origin(self, zone: int, lat_band: str, square: str) -> tuple[float, float]:
        """Get the UTM SW corner of a 100 km MGRS grid square."""

        mgrs_str = f"{zone:02d}{lat_band}{square}0000000000"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            _, _, easting, northing = self._mgrs.MGRSToUTM(mgrs_str.encode())
        return float(easting), float(northing)

    def tile_to_extent(self, tile_code: str) -> tuple[float, float, float, float]:
        """Get the WGS84 bounding box ``(W, S, E, N)`` for a GWD30 tile code."""

        info = self.parse_tile_code(tile_code)
        zone = cast(int, info["zone"])
        hemisphere = cast(str, info["hemisphere"])
        lat_band = cast(str, info["lat_band"])
        square = cast(str, info["square"])

        base_x, base_y = self._mgrs_to_utm_origin(zone, lat_band, square)
        x_min = base_x + self.offset_x
        y_min = base_y + self.offset_y
        x_max = x_min + self.tile_size_m
        y_max = y_min + self.tile_size_m

        epsg_code = int(("326" if hemisphere == "N" else "327") + f"{zone:02d}")
        transformer = self._get_transformer(epsg_code, inverse=True)
        lon_min, lat_min = transformer.transform(x_min, y_min)
        lon_max, lat_max = transformer.transform(x_max, y_max)
        return (lon_min, lat_min, lon_max, lat_max)

    def point_to_tile(self, lat: float, lon: float) -> str:
        """Get the GWD30 tile code for a WGS84 point."""

        zone = int((lon + 180) / 6) + 1
        hemisphere = "N" if lat >= 0 else "S"
        epsg = int(("326" if hemisphere == "N" else "327") + f"{zone:02d}")

        transformer = self._get_transformer(epsg)
        x_utm, y_utm = transformer.transform(lon, lat)
        x_adjusted = x_utm - self.offset_x
        y_adjusted = y_utm - self.offset_y

        transformer_inverse = self._get_transformer(epsg, inverse=True)
        lon_adjusted, lat_adjusted = transformer_inverse.transform(x_adjusted, y_adjusted)
        tile_code = self._mgrs.toMGRS(lat_adjusted, lon_adjusted, MGRSPrecision=0)
        return cast(str, tile_code)

    @staticmethod
    def _validate_bbox(
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
    ) -> None:
        """Validate WGS84 bbox inputs before spatial processing."""

        values = {
            "min_lat": min_lat,
            "min_lon": min_lon,
            "max_lat": max_lat,
            "max_lon": max_lon,
        }
        for name, value in values.items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite, got {value!r}")

        if min_lat > max_lat:
            raise ValueError(
                "bbox latitude bounds must satisfy min_lat <= max_lat, "
                f"got ({min_lat}, {max_lat})"
            )
        if min_lon > max_lon:
            raise ValueError(
                "bbox longitude bounds must satisfy min_lon <= max_lon, "
                f"got ({min_lon}, {max_lon})"
            )
        if min_lat < -90.0 or max_lat > 90.0:
            raise ValueError(
                "bbox latitude bounds must stay within [-90, 90], "
                f"got ({min_lat}, {max_lat})"
            )
        if min_lon < -180.0 or max_lon > 180.0:
            raise ValueError(
                "bbox longitude bounds must stay within [-180, 180], "
                f"got ({min_lon}, {max_lon})"
            )

    @staticmethod
    def _utm_zone_for_lon(lon: float) -> int:
        """Map a longitude to the conventional 1-60 UTM zone number."""

        if lon == 180.0:
            return 60
        return int(math.floor((lon + 180.0) / 6.0)) + 1

    @staticmethod
    def _zone_longitude_bounds(zone: int) -> tuple[float, float]:
        """Return the nominal longitude span for a UTM zone."""

        west = -180.0 + (zone - 1) * 6.0
        return west, west + 6.0

    @staticmethod
    def _axis_samples(start: float, stop: float, max_step: float) -> list[float]:
        """Create inclusive samples with a bounded step size."""

        if math.isclose(start, stop):
            return [start]

        segment_count = max(1, int(math.ceil(abs(stop - start) / max_step)))
        step = (stop - start) / segment_count
        return [start + step * index for index in range(segment_count + 1)]

    @classmethod
    def _bbox_boundary_points(
        cls,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
    ) -> list[tuple[float, float]]:
        """Densify a bbox perimeter to preserve curvature after reprojection."""

        lon_samples = cls._axis_samples(min_lon, max_lon, _BBOX_EDGE_STEP_DEG)
        lat_samples = cls._axis_samples(min_lat, max_lat, _BBOX_EDGE_STEP_DEG)

        boundary: list[tuple[float, float]] = [(lon, min_lat) for lon in lon_samples]
        boundary.extend((max_lon, lat) for lat in lat_samples[1:])
        boundary.extend((lon, max_lat) for lon in reversed(lon_samples[:-1]))
        boundary.extend((min_lon, lat) for lat in reversed(lat_samples[1:-1]))
        return boundary

    def _bbox_polygon_in_utm(
        self,
        epsg: int,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
    ) -> list[tuple[float, float]]:
        """Project a WGS84 bbox perimeter into a UTM CRS."""

        boundary = self._bbox_boundary_points(min_lat, min_lon, max_lat, max_lon)
        transformer = self._get_transformer(epsg)
        lons = [lon for lon, _ in boundary]
        lats = [lat for _, lat in boundary]
        xs, ys = transformer.transform(lons, lats)
        return [(float(x), float(y)) for x, y in zip(xs, ys, strict=True)]

    @staticmethod
    def _normalize_polygon(polygon: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Drop redundant consecutive vertices before geometry checks."""

        normalized: list[tuple[float, float]] = []
        for point in polygon:
            if not normalized or point != normalized[-1]:
                normalized.append(point)

        if len(normalized) > 1 and normalized[0] == normalized[-1]:
            normalized.pop()
        return normalized

    @staticmethod
    def _point_in_rect(
        point: tuple[float, float],
        rect: tuple[float, float, float, float],
    ) -> bool:
        """Return whether a point lies inside or on a rectangle."""

        x, y = point
        min_x, min_y, max_x, max_y = rect
        return min_x <= x <= max_x and min_y <= y <= max_y

    @staticmethod
    def _point_on_segment(
        point: tuple[float, float],
        start: tuple[float, float],
        end: tuple[float, float],
        *,
        tolerance: float = 1e-9,
    ) -> bool:
        """Return whether a point lies on a line segment."""

        px, py = point
        sx, sy = start
        ex, ey = end
        cross = (ex - sx) * (py - sy) - (ey - sy) * (px - sx)
        if abs(cross) > tolerance:
            return False

        dot = (px - sx) * (px - ex) + (py - sy) * (py - ey)
        return dot <= tolerance

    @staticmethod
    def _orientation(
        a: tuple[float, float],
        b: tuple[float, float],
        c: tuple[float, float],
    ) -> float:
        """Return the signed orientation of triangle ``abc``."""

        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    @classmethod
    def _segments_intersect(
        cls,
        a_start: tuple[float, float],
        a_end: tuple[float, float],
        b_start: tuple[float, float],
        b_end: tuple[float, float],
    ) -> bool:
        """Return whether two closed line segments intersect."""

        orientation_1 = cls._orientation(a_start, a_end, b_start)
        orientation_2 = cls._orientation(a_start, a_end, b_end)
        orientation_3 = cls._orientation(b_start, b_end, a_start)
        orientation_4 = cls._orientation(b_start, b_end, a_end)

        if ((orientation_1 > 0) != (orientation_2 > 0)) and (
            (orientation_3 > 0) != (orientation_4 > 0)
        ):
            return True

        return (
            cls._point_on_segment(b_start, a_start, a_end)
            or cls._point_on_segment(b_end, a_start, a_end)
            or cls._point_on_segment(a_start, b_start, b_end)
            or cls._point_on_segment(a_end, b_start, b_end)
        )

    @classmethod
    def _point_in_polygon(
        cls,
        point: tuple[float, float],
        polygon: list[tuple[float, float]],
    ) -> bool:
        """Return whether a point lies inside or on a simple polygon."""

        x, y = point
        inside = False
        previous = polygon[-1]
        for current in polygon:
            if cls._point_on_segment(point, previous, current):
                return True

            x1, y1 = previous
            x2, y2 = current
            if (y1 > y) != (y2 > y):
                intersect_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if intersect_x >= x:
                    inside = not inside
            previous = current
        return inside

    @classmethod
    def _polygon_intersects_rect(
        cls,
        polygon: list[tuple[float, float]],
        rect: tuple[float, float, float, float],
    ) -> bool:
        """Return whether a polygon or polyline intersects a rectangle."""

        normalized = cls._normalize_polygon(polygon)
        if not normalized:
            return False

        rect_min_x, rect_min_y, rect_max_x, rect_max_y = rect
        poly_min_x = min(x for x, _ in normalized)
        poly_max_x = max(x for x, _ in normalized)
        poly_min_y = min(y for _, y in normalized)
        poly_max_y = max(y for _, y in normalized)
        if (
            poly_max_x < rect_min_x
            or rect_max_x < poly_min_x
            or poly_max_y < rect_min_y
            or rect_max_y < poly_min_y
        ):
            return False

        if any(cls._point_in_rect(point, rect) for point in normalized):
            return True

        if len(normalized) >= 3:
            rect_corners = [
                (rect_min_x, rect_min_y),
                (rect_min_x, rect_max_y),
                (rect_max_x, rect_min_y),
                (rect_max_x, rect_max_y),
            ]
            if any(cls._point_in_polygon(corner, normalized) for corner in rect_corners):
                return True

        polygon_edges = list(zip(normalized, normalized[1:], strict=False))
        if len(normalized) >= 3:
            polygon_edges.append((normalized[-1], normalized[0]))

        rect_edges = [
            ((rect_min_x, rect_min_y), (rect_max_x, rect_min_y)),
            ((rect_max_x, rect_min_y), (rect_max_x, rect_max_y)),
            ((rect_max_x, rect_max_y), (rect_min_x, rect_max_y)),
            ((rect_min_x, rect_max_y), (rect_min_x, rect_min_y)),
        ]
        return any(
            cls._segments_intersect(start, end, rect_start, rect_end)
            for start, end in polygon_edges
            for rect_start, rect_end in rect_edges
        )

    def _utm_origin_to_tile_codes(
        self,
        zone: int,
        hemisphere: str,
        base_x: float,
        base_y: float,
    ) -> set[str]:
        """Convert a 100 km UTM square origin into one or more MGRS tile codes."""

        if base_x < 0.0 or base_y < 0.0:
            return set()

        sample_offsets = (
            (1.0, 1.0),
            (_MGRS_GRID_SIZE_M / 2.0, _MGRS_GRID_SIZE_M / 2.0),
            (1.0, _MGRS_GRID_SIZE_M - 1.0),
            (_MGRS_GRID_SIZE_M - 1.0, 1.0),
            (_MGRS_GRID_SIZE_M - 1.0, _MGRS_GRID_SIZE_M - 1.0),
        )

        tile_codes: set[str] = set()
        for sample_x, sample_y in sample_offsets:
            try:
                tile_code = self._mgrs.UTMToMGRS(
                    zone,
                    hemisphere,
                    base_x + sample_x,
                    base_y + sample_y,
                    0,
                )
            except Exception:
                continue
            tile_codes.add(cast(str, tile_code))
        return tile_codes

    def _candidate_tiles_for_utm_polygon(
        self,
        zone: int,
        hemisphere: str,
        polygon: list[tuple[float, float]],
    ) -> set[str]:
        """Enumerate intersecting candidate tiles for a projected bbox polygon."""

        if not polygon:
            return set()

        min_x = min(x for x, _ in polygon)
        max_x = max(x for x, _ in polygon)
        min_y = min(y for _, y in polygon)
        max_y = max(y for _, y in polygon)

        min_x_index = math.ceil((min_x - self.offset_x - self.tile_size_m) / _MGRS_GRID_SIZE_M)
        max_x_index = math.floor((max_x - self.offset_x) / _MGRS_GRID_SIZE_M)
        min_y_index = math.ceil((min_y - self.offset_y - self.tile_size_m) / _MGRS_GRID_SIZE_M)
        max_y_index = math.floor((max_y - self.offset_y) / _MGRS_GRID_SIZE_M)

        tile_codes: set[str] = set()
        for x_index in range(min_x_index, max_x_index + 1):
            base_x = x_index * _MGRS_GRID_SIZE_M
            for y_index in range(min_y_index, max_y_index + 1):
                base_y = y_index * _MGRS_GRID_SIZE_M
                tile_rect = (
                    base_x + self.offset_x,
                    base_y + self.offset_y,
                    base_x + self.offset_x + self.tile_size_m,
                    base_y + self.offset_y + self.tile_size_m,
                )
                if not self._polygon_intersects_rect(polygon, tile_rect):
                    continue
                tile_codes.update(self._utm_origin_to_tile_codes(zone, hemisphere, base_x, base_y))
        return tile_codes

    def bbox_to_tiles(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
    ) -> list[str]:
        """Find all GWD30 tiles whose shifted UTM footprints intersect a WGS84 bbox."""

        self._validate_bbox(min_lat, min_lon, max_lat, max_lon)

        clipped_min_lat = max(min_lat, _MGRS_MIN_LAT)
        clipped_max_lat = min(max_lat, _MGRS_MAX_LAT)
        if clipped_min_lat > clipped_max_lat:
            return []

        min_zone = self._utm_zone_for_lon(min_lon)
        max_zone = self._utm_zone_for_lon(max_lon)
        zone_candidates = range(max(1, min_zone - 1), min(60, max_zone + 1) + 1)

        latitude_segments: list[tuple[str, float, float]] = []
        if clipped_min_lat < 0.0:
            latitude_segments.append(
                ("S", clipped_min_lat, min(clipped_max_lat, _HEMISPHERE_CONTEXT_MARGIN_DEG))
            )
        if clipped_max_lat > 0.0:
            latitude_segments.append(
                ("N", max(clipped_min_lat, -_HEMISPHERE_CONTEXT_MARGIN_DEG), clipped_max_lat)
            )
        if not latitude_segments and math.isclose(clipped_min_lat, 0.0) and math.isclose(
            clipped_max_lat, 0.0
        ):
            latitude_segments = [("S", 0.0, 0.0), ("N", 0.0, 0.0)]

        tiles: set[str] = set()
        for zone in zone_candidates:
            zone_west, zone_east = self._zone_longitude_bounds(zone)
            zone_min_lon = max(min_lon, zone_west - _UTM_ZONE_CONTEXT_MARGIN_DEG)
            zone_max_lon = min(max_lon, zone_east + _UTM_ZONE_CONTEXT_MARGIN_DEG)
            if zone_min_lon > zone_max_lon:
                continue

            for hemisphere, segment_min_lat, segment_max_lat in latitude_segments:
                if segment_min_lat > segment_max_lat:
                    continue

                epsg = int(("326" if hemisphere == "N" else "327") + f"{zone:02d}")
                polygon = self._bbox_polygon_in_utm(
                    epsg,
                    segment_min_lat,
                    zone_min_lon,
                    segment_max_lat,
                    zone_max_lon,
                )
                tiles.update(self._candidate_tiles_for_utm_polygon(zone, hemisphere, polygon))
        return sorted(tiles)
