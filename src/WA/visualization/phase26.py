"""Visualization helpers for Phase 2.6 coarse metrics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
import yaml
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap

from WA.visualization.coarse_scale import DATASET_DISPLAY_NAMES

MEAN_CMAP = LinearSegmentedColormap.from_list("phase26_mean", ["#ffffff", "#1f77b4"])
STD_CMAP = LinearSegmentedColormap.from_list("phase26_std", ["#ffffff", "#d62728"])
DEFAULT_PHASE26_PANEL_DATASET_IDS = ("giems_mc", "swamps", "topmodel", "wad2m")
GEO_TICK_STEPS = (0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0)


@dataclass(frozen=True)
class ParticipantCountStyle:
    """Discrete plotting style for participant counts."""

    cmap: ListedColormap
    norm: BoundaryNorm
    ticks: tuple[int, ...]


@dataclass(frozen=True)
class Phase26Region:
    """One named Phase 2.6 plotting region."""

    region_id: str
    label: str
    bbox: tuple[float, float, float, float]


def prepare_participant_count_for_plot(participant_count: xr.DataArray) -> xr.DataArray:
    """Mask zeros and preserve only positive integer participant counts for plotting."""

    prepared = xr.where(participant_count > 0, np.rint(participant_count), np.nan).astype(
        np.float32
    )
    prepared.name = "participant_count"
    prepared.attrs = dict(participant_count.attrs)
    prepared.attrs["plot_mask_rule"] = "participant_count > 0"
    prepared.attrs["plot_discrete"] = 1
    return prepared


def participant_count_style(participant_count: xr.DataArray) -> ParticipantCountStyle:
    """Build a one-integer-per-color discrete style for participant count plots."""

    finite = participant_count.values[np.isfinite(participant_count.values)]
    if finite.size == 0:
        raise ValueError("participant_count has no positive finite values to plot")

    ticks = tuple(
        range(
            int(np.nanmin(finite)),
            int(np.nanmax(finite)) + 1,
        )
    )
    base = plt.get_cmap("viridis", len(ticks))
    cmap = ListedColormap([base(index) for index in range(len(ticks))], name="participants")
    cmap.set_bad((1.0, 1.0, 1.0, 0.0))
    boundaries = np.arange(ticks[0] - 0.5, ticks[-1] + 1.5, 1.0)
    norm = BoundaryNorm(boundaries, cmap.N)
    return ParticipantCountStyle(cmap=cmap, norm=norm, ticks=ticks)


def plot_phase26_triptych(
    metrics: xr.Dataset,
    *,
    output_path: Path,
    dpi: int = 150,
    suptitle: str | None = None,
    hspace: float = 0.08,
) -> Path:
    """Plot mean/std/participant-count maps in a 3x1 layout."""

    required = {"mean_wetland_fraction", "std_wetland_fraction", "participant_count"}
    missing = required.difference(metrics.data_vars)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"metrics dataset missing required variables: {missing_text}")

    mean_surface = metrics["mean_wetland_fraction"]
    std_surface = metrics["std_wetland_fraction"]
    participant_surface = prepare_participant_count_for_plot(metrics["participant_count"])
    participant_style = participant_count_style(participant_surface)

    extent = _surface_extent(mean_surface)
    use_cartopy = False
    transform = None
    try:
        import cartopy.crs as ccrs

        use_cartopy = True
        transform = ccrs.PlateCarree()
    except ImportError:
        pass

    subplot_kwargs = {"projection": transform} if use_cartopy else {}
    fig, axes = plt.subplots(
        nrows=3,
        ncols=1,
        figsize=(11.5, 10.2),
        squeeze=False,
        subplot_kw=subplot_kwargs,
    )
    axes_list = list(axes[:, 0])

    try:
        _plot_surface(
            axes_list[0],
            mean_surface,
            title="Mean Wetland Fraction",
            colorbar_label="Mean Wetland Fraction",
            cmap=MEAN_CMAP,
            vmin=0.0,
            vmax=1.0,
            extent=extent,
            use_cartopy=use_cartopy,
            transform=transform,
            show_xlabel=False,
        )
        _plot_surface(
            axes_list[1],
            std_surface,
            title="Std Wetland Fraction",
            colorbar_label="Std Wetland Fraction",
            cmap=STD_CMAP,
            vmin=0.0,
            vmax=0.5,
            extent=extent,
            use_cartopy=use_cartopy,
            transform=transform,
            show_xlabel=False,
        )
        _plot_surface(
            axes_list[2],
            participant_surface,
            title="Participant Count",
            colorbar_label="Participant Count",
            cmap=participant_style.cmap,
            norm=participant_style.norm,
            extent=extent,
            use_cartopy=use_cartopy,
            transform=transform,
            colorbar_ticks=participant_style.ticks,
            show_xlabel=True,
        )

        if suptitle:
            fig.suptitle(suptitle, fontsize=14, fontweight="bold", y=0.985)
        fig.subplots_adjust(left=0.08, right=0.92, top=0.95, bottom=0.06, hspace=hspace)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)

    return output_path


def load_phase26_regions(regions_file: Path) -> list[Phase26Region]:
    """Load plotting regions from `config/priority_regions.yaml`."""

    document = yaml.safe_load(regions_file.read_text(encoding="utf-8")) or {}
    regions = document.get("regions")
    if not isinstance(regions, dict):
        raise ValueError("regions_file must contain a top-level 'regions' mapping")

    ordered: list[tuple[int, str, dict[str, object]]] = []
    for region_id, payload in regions.items():
        if not isinstance(payload, dict):
            raise ValueError(f"Region {region_id!r} must be a mapping")
        ordered.append((int(payload.get("priority", 9999)), str(region_id), payload))

    result: list[Phase26Region] = []
    for _priority, region_id, payload in sorted(ordered):
        bbox = payload.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"Region {region_id!r} must provide bbox as 4-item list")
        result.append(
            Phase26Region(
                region_id=region_id,
                label=str(payload.get("label", region_id)),
                bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
            )
        )
    return result


def resolve_phase26_panel_dataset_ids(
    stack: xr.DataArray,
    metrics: xr.Dataset,
    *,
    preferred_order: tuple[str, ...] = DEFAULT_PHASE26_PANEL_DATASET_IDS,
) -> tuple[str, str, str, str]:
    """Resolve the four dataset panels used in the 2x3 regional comparison figure."""

    dataset_coord = [str(value) for value in stack.coords["dataset"].values]
    attr_value = metrics.attrs.get("std_dataset_ids_json")
    if isinstance(attr_value, str) and attr_value:
        candidate_ids = [str(item) for item in json.loads(attr_value)]
    else:
        candidate_ids = [
            dataset_id for dataset_id in dataset_coord if dataset_id in preferred_order
        ]

    ordered = tuple(dataset_id for dataset_id in preferred_order if dataset_id in candidate_ids)
    if len(ordered) != 4:
        raise ValueError(
            "Expected exactly four std-eligible dataset panels, got "
            f"{len(ordered)} from {ordered!r}"
        )
    return ordered  # type: ignore[return-value]


def subset_phase26_surface_to_bbox(
    surface: xr.DataArray,
    bbox: tuple[float, float, float, float],
) -> xr.DataArray:
    """Subset one lat/lon surface to a region bbox while preserving coordinate order."""

    west, south, east, north = bbox
    lon_subset = surface.sel(lon=slice(west, east))

    lat_values = np.asarray(lon_subset["lat"].values)
    if lat_values.size == 0:
        raise ValueError(f"Region bbox {bbox!r} produces empty lon selection")
    lat_slice = slice(south, north) if lat_values[0] <= lat_values[-1] else slice(north, south)
    subset = lon_subset.sel(lat=lat_slice)
    if subset.sizes.get("lat", 0) == 0 or subset.sizes.get("lon", 0) == 0:
        raise ValueError(f"Region bbox {bbox!r} produces empty lat/lon subset")
    return subset


def plot_phase26_region_panel(
    metrics: xr.Dataset,
    stack: xr.DataArray,
    *,
    region: Phase26Region,
    output_path: Path,
    dataset_ids: tuple[str, str, str, str],
    satellite_image_path: Path | None = None,
    dpi: int = 150,
    wspace: float = 0.06,
    hspace: float = 0.08,
) -> Path:
    """Plot one 2x3 Phase 2.6 regional comparison figure."""

    std_surface = subset_phase26_surface_to_bbox(metrics["std_wetland_fraction"], region.bbox)
    dataset_surfaces = [
        subset_phase26_surface_to_bbox(stack.sel(dataset=dataset_id), region.bbox)
        for dataset_id in dataset_ids
    ]

    use_cartopy = False
    transform = None
    try:
        import cartopy.crs as ccrs

        use_cartopy = True
        transform = ccrs.PlateCarree()
    except ImportError:
        pass

    subplot_kwargs = {"projection": transform} if use_cartopy else {}
    fig = plt.figure(figsize=(12.2, 7.6))
    gs = fig.add_gridspec(
        2,
        4,
        width_ratios=[1.0, 1.0, 1.0, 0.07],
        wspace=wspace,
        hspace=hspace,
    )
    axes = [
        fig.add_subplot(gs[row, col], **subplot_kwargs)
        for row in range(2)
        for col in range(3)
    ]

    _plot_panel_satellite(
        axes[0],
        image_path=satellite_image_path,
        title="MODIS RGB",
        extent=region.bbox,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=True,
        show_bottom_labels=False,
    )

    wetland_titles = [_short_panel_title(dataset_id) for dataset_id in dataset_ids]
    wetland_positions = [2, 3, 4, 5]

    wetland_mesh = None
    for position, title, surface in zip(
        wetland_positions,
        wetland_titles,
        dataset_surfaces,
        strict=True,
    ):
        row = position // 3
        col = position % 3
        wetland_mesh = _plot_panel_surface(
            axes[position],
            surface,
            title=title,
            extent=region.bbox,
            cmap=MEAN_CMAP,
            vmin=0.0,
            vmax=1.0,
            use_cartopy=use_cartopy,
            transform=transform,
            show_left_labels=col == 0,
            show_bottom_labels=row == 1,
        )

    std_mesh = _plot_panel_surface(
        axes[1],
        std_surface,
        title="Std",
        extent=region.bbox,
        cmap=STD_CMAP,
        vmin=0.0,
        vmax=0.5,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=False,
        show_bottom_labels=False,
    )

    cbar_gs = gs[:, 3].subgridspec(2, 1, hspace=0.25)
    cax_std = fig.add_subplot(cbar_gs[0, 0])
    cax_wet = fig.add_subplot(cbar_gs[1, 0])
    fig.colorbar(std_mesh, cax=cax_std, label="Std")
    fig.colorbar(wetland_mesh, cax=cax_wet, label="Wetland Fraction")

    fig.suptitle(region.label, fontsize=14, fontweight="bold", y=0.98)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def _plot_surface(
    ax,
    surface: xr.DataArray,
    *,
    title: str,
    colorbar_label: str,
    cmap,
    extent: tuple[float, float, float, float],
    use_cartopy: bool,
    transform,
    vmin: float | None = None,
    vmax: float | None = None,
    norm: BoundaryNorm | None = None,
    colorbar_ticks: tuple[int, ...] | None = None,
    show_xlabel: bool,
) -> None:
    plot_kwargs = {
        "ax": ax,
        "x": "lon",
        "y": "lat",
        "cmap": cmap,
        "add_colorbar": False,
        "rasterized": True,
    }
    if vmin is not None:
        plot_kwargs["vmin"] = vmin
    if vmax is not None:
        plot_kwargs["vmax"] = vmax
    if norm is not None:
        plot_kwargs["norm"] = norm
    if transform is not None:
        plot_kwargs["transform"] = transform

    mesh = surface.plot.pcolormesh(**plot_kwargs)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel("Latitude")
    if show_xlabel:
        ax.set_xlabel("Longitude")
    else:
        ax.set_xlabel("")
        ax.tick_params(labelbottom=False)
    ax.set_aspect("equal")

    west, east, south, north = extent
    if use_cartopy:
        ax.set_extent((west, east, south, north), crs=transform)
        ax.coastlines(linewidth=0.5, color="black")
    else:
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)

    colorbar = plt.gcf().colorbar(mesh, ax=ax, pad=0.015, fraction=0.028)
    if colorbar_ticks is not None:
        colorbar.set_ticks(colorbar_ticks)
    colorbar.set_label(colorbar_label)


def _plot_panel_surface(
    ax,
    surface: xr.DataArray,
    *,
    title: str,
    extent: tuple[float, float, float, float],
    cmap,
    use_cartopy: bool,
    transform,
    vmin: float | None = None,
    vmax: float | None = None,
    show_left_labels: bool,
    show_bottom_labels: bool,
):
    plot_kwargs = {
        "ax": ax,
        "x": "lon",
        "y": "lat",
        "cmap": cmap,
        "add_colorbar": False,
        "rasterized": True,
    }
    if vmin is not None:
        plot_kwargs["vmin"] = vmin
    if vmax is not None:
        plot_kwargs["vmax"] = vmax
    if transform is not None:
        plot_kwargs["transform"] = transform

    mesh = surface.plot.pcolormesh(**plot_kwargs)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_aspect("equal")

    west, south, east, north = extent
    if use_cartopy:
        ax.set_extent((west, east, south, north), crs=transform)
        ax.coastlines(linewidth=0.5, color="black")
    else:
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)

    _configure_panel_geo_axes(
        ax,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=show_left_labels,
        show_bottom_labels=show_bottom_labels,
    )
    return mesh


def _plot_panel_satellite(
    ax,
    *,
    image_path: Path | None,
    title: str,
    extent: tuple[float, float, float, float],
    use_cartopy: bool,
    transform,
    show_left_labels: bool,
    show_bottom_labels: bool,
) -> None:
    """Draw one regional satellite quicklook panel."""

    west, south, east, north = extent
    ax.set_title(title, fontsize=11, fontweight="bold")

    if image_path and image_path.exists():
        try:
            image = mpimg.imread(str(image_path))
            image_kwargs = {
                "extent": (west, east, south, north),
                "origin": "upper",
                "aspect": "auto",
            }
            if transform is not None:
                image_kwargs["transform"] = transform
            ax.imshow(image, **image_kwargs)
        except Exception:  # noqa: BLE001
            ax.text(
                0.5,
                0.5,
                "Image\nunavailable",
                transform=ax.transAxes,
                ha="center",
                va="center",
                fontsize=10,
                color="gray",
            )
    else:
        ax.text(
            0.5,
            0.5,
            "No satellite\nimage",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=10,
            color="gray",
        )

    ax.set_aspect("equal")
    if use_cartopy:
        ax.set_extent((west, east, south, north), crs=transform)
        ax.coastlines(linewidth=0.5, color="black")
    else:
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)

    _configure_panel_geo_axes(
        ax,
        extent=extent,
        use_cartopy=use_cartopy,
        transform=transform,
        show_left_labels=show_left_labels,
        show_bottom_labels=show_bottom_labels,
    )


def _configure_panel_geo_axes(
    ax,
    *,
    extent: tuple[float, float, float, float],
    use_cartopy: bool,
    transform,
    show_left_labels: bool,
    show_bottom_labels: bool,
) -> None:
    """Apply regional-panel geographic ticks and label visibility."""

    west, south, east, north = extent
    xticks = _geo_tick_values(west, east)
    yticks = _geo_tick_values(south, north)

    if use_cartopy:
        from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter

        ax.set_xticks(xticks, crs=transform)
        ax.set_yticks(yticks, crs=transform)
        ax.xaxis.set_major_formatter(LongitudeFormatter(zero_direction_label=False))
        ax.yaxis.set_major_formatter(LatitudeFormatter())
    else:
        ax.set_xticks(xticks)
        ax.set_yticks(yticks)
        ax.set_xticklabels([_format_longitude(value) for value in xticks])
        ax.set_yticklabels([_format_latitude(value) for value in yticks])

    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.tick_params(
        axis="x",
        bottom=show_bottom_labels,
        labelbottom=show_bottom_labels,
        top=False,
        labeltop=False,
        labelsize=9,
    )
    ax.tick_params(
        axis="y",
        left=show_left_labels,
        labelleft=show_left_labels,
        right=False,
        labelright=False,
        labelsize=9,
    )


def _geo_tick_values(min_value: float, max_value: float, *, target_count: int = 4) -> list[float]:
    """Generate a small set of readable geographic tick values within one extent."""

    lower = float(min(min_value, max_value))
    upper = float(max(min_value, max_value))
    span = upper - lower
    if np.isclose(span, 0.0):
        return [round(lower, 2)]

    chosen_step = GEO_TICK_STEPS[-1]
    preferred_step = span / max(target_count - 1, 1)
    for step in GEO_TICK_STEPS:
        if step >= preferred_step:
            chosen_step = step
            break

    start = np.ceil(lower / chosen_step) * chosen_step
    stop = np.floor(upper / chosen_step) * chosen_step
    if stop < start:
        return [round(lower, 2), round(upper, 2)]

    tick_values = np.arange(start, stop + chosen_step * 0.5, chosen_step)
    rounded = np.round(tick_values, 2)
    return [float(value) for value in rounded]


def _format_longitude(value: float) -> str:
    suffix = "E" if value >= 0 else "W"
    return f"{abs(value):g}°{suffix}"


def _format_latitude(value: float) -> str:
    suffix = "N" if value >= 0 else "S"
    return f"{abs(value):g}°{suffix}"


def _surface_extent(surface: xr.DataArray) -> tuple[float, float, float, float]:
    lon = surface["lon"].values
    lat = surface["lat"].values
    return (
        float(np.nanmin(lon)),
        float(np.nanmax(lon)),
        float(np.nanmin(lat)),
        float(np.nanmax(lat)),
    )


def _short_panel_title(dataset_id: str) -> str:
    return DATASET_DISPLAY_NAMES.get(dataset_id, dataset_id)
