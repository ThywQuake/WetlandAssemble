#!/usr/bin/env python3
# ruff: noqa: E402
"""Plot priority-region bounding boxes on a world coastline map."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cartopy.crs as ccrs
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_REGIONS_FILE = Path("config/priority_regions.yaml")
DEFAULT_OUTPUT_PATH = Path("results/figures/priority_regions/priority_regions_world.png")
DEFAULT_DPI = 300
WORLD_EXTENT = (-180.0, 180.0, -60.0, 85.0)
CONTINENT_COLORS = {
    "South America": "#d95f0e",
    "Africa": "#1b9e77",
    "Southeast Asia": "#7570b3",
    "South Asia": "#e7298a",
    "Insular Southeast Asia": "#66a61e",
    "Oceania": "#e6ab02",
}
CALLOUT_DX_POINTS = 6.0
CALLOUT_DY_POINTS = 6.0
CALLOUT_STACK_DY_POINTS = 20.0
CALLOUT_CONFLICT_LON_DEG = 8.0
CALLOUT_CONFLICT_LAT_DEG = 7.0


@dataclass(frozen=True)
class PriorityRegion:
    """Region metadata used for world-map annotation."""

    region_id: str
    label: str
    continent: str
    priority: int
    bbox: tuple[float, float, float, float]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Draw a world coastline map and annotate every bbox from "
            "config/priority_regions.yaml."
        ),
    )
    parser.add_argument(
        "--regions-file",
        type=Path,
        default=DEFAULT_REGIONS_FILE,
        help="Priority-region YAML path (default: config/priority_regions.yaml)",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=(
            "Output PNG path "
            "(default: results/figures/priority_regions/priority_regions_world.png)"
        ),
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help="Output PNG dpi (default: 300)",
    )
    return parser.parse_args(argv)


def load_priority_regions(path: Path) -> list[PriorityRegion]:
    """Load and order priority regions from YAML."""

    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    regions = document.get("regions")
    if not isinstance(regions, dict):
        raise ValueError("regions_file must contain a top-level 'regions' mapping")

    loaded: list[PriorityRegion] = []
    for region_id, payload in regions.items():
        if not isinstance(payload, dict):
            raise ValueError(f"Region {region_id!r} must be a mapping")
        bbox = payload.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"Region {region_id!r} must provide bbox as a 4-item list")
        loaded.append(
            PriorityRegion(
                region_id=str(region_id),
                label=str(payload.get("label", region_id)),
                continent=str(payload.get("continent", "Unknown")),
                priority=int(payload.get("priority", 9999)),
                bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
            )
        )

    loaded.sort(key=lambda region: (region.priority, region.region_id))
    return loaded


def bbox_center(region: PriorityRegion) -> tuple[float, float]:
    """Return the bbox center in lon/lat."""

    west, south, east, north = region.bbox
    return ((west + east) / 2.0, (south + north) / 2.0)


def callout_position(region: PriorityRegion) -> tuple[float, float]:
    """Return the top-right bbox corner used as the callout anchor."""

    _west, _south, east, north = region.bbox
    return (east, north)


def callout_offset_points(
    region: PriorityRegion,
    *,
    occupied_anchors: list[tuple[float, float, int]],
) -> tuple[float, float]:
    """Return one top-right callout offset with simple vertical de-overlap."""

    anchor_lon, anchor_lat = callout_position(region)
    level = 0
    for other_lon, other_lat, other_level in occupied_anchors:
        if (
            abs(anchor_lon - other_lon) <= CALLOUT_CONFLICT_LON_DEG
            and abs(anchor_lat - other_lat) <= CALLOUT_CONFLICT_LAT_DEG
        ):
            level = max(level, other_level + 1)
    return (
        CALLOUT_DX_POINTS,
        CALLOUT_DY_POINTS + level * CALLOUT_STACK_DY_POINTS,
    )


def region_color(region: PriorityRegion) -> str:
    """Return the display color for one region."""

    return CONTINENT_COLORS.get(region.continent, "#4d4d4d")


def format_callout_text(region: PriorityRegion) -> str:
    """Return the multi-line label shown on the map."""

    return f"{region.priority}. {region.label}\n{region.continent}"


def plot_priority_regions_world(
    regions: list[PriorityRegion],
    *,
    output_path: Path,
    dpi: int,
) -> Path:
    """Draw the world map, bbox rectangles, and callout text labels."""

    if not regions:
        raise ValueError("At least one region is required")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(18, 10))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.set_extent(WORLD_EXTENT, crs=ccrs.PlateCarree())
    ax.set_facecolor("#f8fcff")
    ax.coastlines(resolution="110m", linewidth=0.9, color="#444444")
    ax.gridlines(
        crs=ccrs.PlateCarree(),
        linestyle="--",
        linewidth=0.4,
        color="#9aa8b5",
        alpha=0.55,
        draw_labels=False,
    )

    legend_handles: dict[str, mpatches.Patch] = {}
    occupied_anchors: list[tuple[float, float, int]] = []
    sorted_regions = sorted(
        regions,
        key=lambda region: (callout_position(region)[0], callout_position(region)[1]),
    )
    for region in sorted_regions:
        west, south, east, north = region.bbox
        color = region_color(region)
        anchor_lon, anchor_lat = callout_position(region)
        center_lon, center_lat = bbox_center(region)
        text_dx, text_dy = callout_offset_points(
            region,
            occupied_anchors=occupied_anchors,
        )
        stack_level = int(round((text_dy - CALLOUT_DY_POINTS) / CALLOUT_STACK_DY_POINTS))
        occupied_anchors.append((anchor_lon, anchor_lat, stack_level))

        ax.add_patch(
            mpatches.Rectangle(
                (west, south),
                east - west,
                north - south,
                transform=ccrs.PlateCarree(),
                fill=False,
                linewidth=2.0,
                edgecolor=color,
                zorder=3,
            )
        )
        ax.plot(
            center_lon,
            center_lat,
            marker="o",
            markersize=3.5,
            color=color,
            transform=ccrs.PlateCarree(),
            zorder=4,
        )
        ax.annotate(
            format_callout_text(region),
            xy=(anchor_lon, anchor_lat),
            xycoords=ccrs.PlateCarree()._as_mpl_transform(ax),
            xytext=(text_dx, text_dy),
            textcoords="offset points",
            fontsize=8.5,
            color="#1f2933",
            ha="left",
            va="bottom",
            bbox={
                "boxstyle": "round,pad=0.26",
                "facecolor": "white",
                "edgecolor": color,
                "linewidth": 1.0,
                "alpha": 0.96,
            },
            arrowprops={
                "arrowstyle": "-",
                "linewidth": 1.0,
                "color": color,
                "shrinkA": 5,
                "shrinkB": 4,
            },
            zorder=5,
        )
        legend_handles.setdefault(
            region.continent,
            mpatches.Patch(facecolor=color, edgecolor=color, label=region.continent),
        )

    ax.set_title(
        "Priority Wetland Regions From config/priority_regions.yaml",
        fontsize=16,
        pad=14,
    )
    fig.text(
        0.015,
        0.02,
        "BBox convention: [min_lon, min_lat, max_lon, max_lat] in EPSG:4326",
        fontsize=9,
        color="#425466",
    )
    fig.legend(
        handles=list(legend_handles.values()),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.01),
        ncol=min(3, len(legend_handles)),
        frameon=False,
        fontsize=9,
    )
    fig.tight_layout(rect=(0.0, 0.05, 1.0, 1.0))
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info("Priority-region world map written -> %s", output_path)
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    regions = load_priority_regions(args.regions_file)
    logger.info(
        "Priority-region world plotting args: regions=%s output=%s dpi=%s count=%s",
        args.regions_file,
        args.output_path,
        args.dpi,
        len(regions),
    )
    plot_priority_regions_world(
        regions,
        output_path=args.output_path,
        dpi=args.dpi,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
