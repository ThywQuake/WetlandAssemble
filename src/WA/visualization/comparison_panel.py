"""Per-hotspot comparison panel figure generator.

Layout: 3 columns × N rows.
  Row 0: satellite image | entropy/disagreement (white→red) | mean wetland % (white→blue)
  Rows 1+: individual dataset wetland fractions at native resolution (white→blue)

Only leftmost subplots show latitude; only bottom subplots show longitude.
Two shared colorbars on the figure right margin.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.gridspec import GridSpec

from WA.comparison.harmonize import _CLASSIFICATION_BINARY_MAPS, create_comparison_grid
from WA.loaders.base import BBox, DatasetLoader, DatasetMetadata, TimeRange

N_COLS = 3
APPROX_METERS_PER_DEGREE = 111_320.0
DEFAULT_GWD30_DISPLAY_RESOLUTION_M = 1000

ENTROPY_CMAP = LinearSegmentedColormap.from_list("entropy_wr", ["#ffffff", "#d62728"])
WETLAND_CMAP = LinearSegmentedColormap.from_list("wetland_wb", ["#ffffff", "#1f77b4"])


def load_native_wetland_surface(
    dataset_id: str,
    loader: DatasetLoader,
    bbox: BBox,
    *,
    target_time: str | pd.Timestamp | None = None,
    gwd30_resolution_m: int = DEFAULT_GWD30_DISPLAY_RESOLUTION_M,
) -> xr.DataArray | None:
    """Load one dataset's display-ready wetland surface for Phase 2.5 panels.

    Dynamic datasets are restricted to the target month so the visualization does
    not materialize whole multi-year time series. GWD30 uses the loader's
    direct-to-reference-grid path to downsample into an approximately 1 km
    display grid before plotting.
    """

    metadata = loader.metadata()
    time_range = _build_visualization_time_range(metadata, target_time)
    if not metadata.is_static and target_time is not None and time_range is None:
        return None

    normalized_target_time = None
    if target_time is not None:
        normalized_target_time = pd.Timestamp(target_time).to_period("M").to_timestamp()

    rough_surface_loader = getattr(loader, "load_rough_binary_surface", None)
    if (
        dataset_id == "gwd30"
        and normalized_target_time is not None
        and time_range is not None
        and callable(rough_surface_loader)
    ):
        resolution_deg = gwd30_resolution_m / APPROX_METERS_PER_DEGREE
        reference_grid = create_comparison_grid(bbox, resolution_deg=resolution_deg)
        surface, _trace = rough_surface_loader(
            bbox=bbox,
            time_range=time_range,
            reference_grid=reference_grid,
            aggregation="mean",
            target_time=normalized_target_time,
            worker_count=1,
        )
        return surface.astype(np.float32).load()

    dataset = loader.load(bbox=bbox, time_range=time_range)
    try:
        surface = _extract_native_wetland_surface(dataset_id, dataset)
        if surface is None:
            return None
        return surface.astype(np.float32).load()
    finally:
        close = getattr(dataset, "close", None)
        if callable(close):
            close()


def plot_comparison_panel(
    hotspot_bbox: BBox,
    *,
    satellite_image_path: Path | None,
    entropy_surface: xr.DataArray,
    mean_wetland_surface: xr.DataArray,
    dataset_surfaces: Mapping[str, xr.DataArray],
    dataset_labels: Mapping[str, str] | None = None,
    year: int,
    region_label: str,
    hotspot_id: str,
    output_path: Path,
    dpi: int = 200,
    figsize_per_cell: tuple[float, float] = (4.0, 3.5),
) -> Path:
    """Generate a comparison panel figure for one hotspot.

    Parameters
    ----------
    hotspot_bbox : (west, south, east, north) geographic extent.
    satellite_image_path : RGB quicklook (MODIS/S2). ``None`` draws an empty panel.
    entropy_surface : Shannon entropy or disagreement_score, values in [0, 1].
    mean_wetland_surface : Mean wetland fraction across datasets, values in [0, 1].
    dataset_surfaces : ``{dataset_id: native-resolution wetland fraction DataArray}``.
    dataset_labels : ``{dataset_id: "G2017 (0.05°)"}``. Auto-generated if ``None``.
    year : Reference year for title.
    region_label : Region name for title.
    hotspot_id : Hotspot/focus-area ID for title.
    output_path : Where to save the PNG.
    dpi : Output resolution.
    figsize_per_cell : (width, height) in inches per subplot.

    Returns
    -------
    Path to the saved figure.
    """
    west, south, east, north = hotspot_bbox
    extent = [west, east, south, north]

    sorted_ids = sorted(dataset_surfaces)
    n_datasets = len(sorted_ids)
    n_data_rows = max(1, math.ceil(n_datasets / N_COLS))
    n_rows = 1 + n_data_rows

    if dataset_labels is None:
        dataset_labels = {ds_id: ds_id for ds_id in sorted_ids}

    # --- Figure + GridSpec ---
    cbar_width_ratio = 0.06
    fig_w = figsize_per_cell[0] * N_COLS + 1.4
    fig_h = figsize_per_cell[1] * n_rows
    fig = plt.figure(figsize=(fig_w, fig_h))

    gs = GridSpec(
        n_rows,
        N_COLS + 1,
        figure=fig,
        width_ratios=[1, 1, 1, cbar_width_ratio],
        wspace=0.08,
        hspace=0.20,
    )

    all_axes: list[tuple[int, int, plt.Axes]] = []
    entropy_mappable = None
    wetland_mappable = None
    wetland_norm = Normalize(vmin=0, vmax=1)

    # --- Row 0: special panels ---
    # Satellite
    ax_sat = fig.add_subplot(gs[0, 0])
    _configure_extent(ax_sat, extent)
    if satellite_image_path and satellite_image_path.exists():
        try:
            img = mpimg.imread(str(satellite_image_path))
            ax_sat.imshow(img, extent=extent, aspect="auto", origin="upper")
        except Exception:
            ax_sat.text(
                0.5, 0.5, "Image\nunavailable",
                transform=ax_sat.transAxes, ha="center", va="center",
                fontsize=9, color="gray",
            )
    else:
        ax_sat.text(
            0.5, 0.5, "No satellite\nimage",
            transform=ax_sat.transAxes, ha="center", va="center",
            fontsize=9, color="gray",
        )
    ax_sat.set_title("Satellite", fontsize=9, fontweight="bold")
    all_axes.append((0, 0, ax_sat))

    # Entropy
    ax_ent = fig.add_subplot(gs[0, 1])
    _configure_extent(ax_ent, extent)
    entropy_mappable = _plot_surface(
        ax_ent, entropy_surface, extent, ENTROPY_CMAP, Normalize(vmin=0, vmax=1),
    )
    ax_ent.set_title("Shannon Entropy", fontsize=9, fontweight="bold")
    all_axes.append((0, 1, ax_ent))

    # Mean wetland
    ax_avg = fig.add_subplot(gs[0, 2])
    _configure_extent(ax_avg, extent)
    wetland_mappable = _plot_surface(
        ax_avg, mean_wetland_surface, extent, WETLAND_CMAP, wetland_norm,
    )
    ax_avg.set_title("Mean Wetland %", fontsize=9, fontweight="bold")
    all_axes.append((0, 2, ax_avg))

    # --- Rows 1+: individual datasets ---
    for idx, ds_id in enumerate(sorted_ids):
        row = 1 + idx // N_COLS
        col = idx % N_COLS
        ax = fig.add_subplot(gs[row, col])
        _configure_extent(ax, extent)
        m = _plot_surface(ax, dataset_surfaces[ds_id], extent, WETLAND_CMAP, wetland_norm)
        if wetland_mappable is None:
            wetland_mappable = m
        label = dataset_labels.get(ds_id, ds_id)
        ax.set_title(label, fontsize=9)
        all_axes.append((row, col, ax))

    # --- Hide empty cells in last row ---
    filled_in_last_row = n_datasets % N_COLS
    if filled_in_last_row > 0:
        for empty_col in range(filled_in_last_row, N_COLS):
            ax_empty = fig.add_subplot(gs[n_rows - 1, empty_col])
            ax_empty.set_visible(False)

    # --- Tick label control ---
    _last_visible_row = {}  # col -> max visible row
    for row, col, _ax in all_axes:
        if col not in _last_visible_row or row > _last_visible_row[col]:
            _last_visible_row[col] = row

    for row, col, ax in all_axes:
        is_leftmost = col == 0
        is_bottom = row == _last_visible_row.get(col, n_rows - 1)

        if not is_leftmost:
            ax.set_ylabel("")
            ax.set_yticklabels([])
        else:
            ax.set_ylabel("Lat", fontsize=7)
            ax.tick_params(axis="y", labelsize=6)

        if not is_bottom:
            ax.set_xlabel("")
            ax.set_xticklabels([])
        else:
            ax.set_xlabel("Lon", fontsize=7)
            ax.tick_params(axis="x", labelsize=6)

    # --- Two colorbars on the right ---
    # Split colorbar column into upper and lower halves
    half = max(1, n_rows // 2)
    cax_ent = fig.add_subplot(gs[:half, N_COLS])
    cax_wet = fig.add_subplot(gs[half:, N_COLS])

    if entropy_mappable is not None:
        fig.colorbar(entropy_mappable, cax=cax_ent, label="Shannon Entropy")
        cax_ent.tick_params(labelsize=6)
    if wetland_mappable is not None:
        fig.colorbar(wetland_mappable, cax=cax_wet, label="Wetland Fraction")
        cax_wet.tick_params(labelsize=6)

    # --- Title ---
    fig.suptitle(
        f"{year} / {region_label} ({hotspot_id})",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _configure_extent(ax: plt.Axes, extent: list[float]) -> None:
    """Set axis limits to match geographic extent."""
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")


def _plot_surface(
    ax: plt.Axes,
    surface: xr.DataArray,
    extent: list[float],
    cmap: LinearSegmentedColormap,
    norm: Normalize,
) -> plt.cm.ScalarMappable | None:
    """Plot a 2D surface on the given axes using pcolormesh."""
    if surface is None:
        return None

    lat = surface.coords.get("lat", surface.coords.get("y"))
    lon = surface.coords.get("lon", surface.coords.get("x"))
    if lat is None or lon is None:
        return None

    mappable = ax.pcolormesh(
        lon.values,
        lat.values,
        surface.values,
        cmap=cmap,
        norm=norm,
        shading="auto",
        rasterized=True,
    )
    return mappable


def _build_visualization_time_range(
    metadata: DatasetMetadata,
    target_time: str | pd.Timestamp | None,
) -> TimeRange | None:
    """Build the month window used by visualization loads for dynamic datasets."""

    if metadata.is_static or target_time is None:
        return None

    normalized_target = pd.Timestamp(target_time).to_period("M").to_timestamp()
    coverage = metadata.temporal_coverage
    if coverage is not None:
        coverage_start, coverage_end = coverage
        if coverage_start is not None and coverage_end is not None:
            start_month = pd.Timestamp(coverage_start).to_period("M").to_timestamp()
            end_month = pd.Timestamp(coverage_end).to_period("M").to_timestamp()
            if not start_month <= normalized_target <= end_month:
                return None

    target_end = normalized_target + pd.offsets.MonthEnd(0)
    return normalized_target.strftime("%Y-%m-%d"), pd.Timestamp(target_end).strftime("%Y-%m-%d")


def _extract_native_wetland_surface(
    dataset_id: str,
    dataset: xr.Dataset,
) -> xr.DataArray | None:
    """Extract binary wetland fraction from one loaded dataset."""

    if "wetland_fraction" in dataset:
        source = dataset["wetland_fraction"]
        if "time" in source.dims:
            source = source.mean(dim="time", skipna=True)
        for dim in ("config", "forcing"):
            if dim in source.dims:
                source = source.mean(dim=dim, skipna=True)
        return source.clip(0, 1)

    if dataset_id == "g2017":
        if "wetland_nolake" in dataset:
            return dataset["wetland_nolake"].clip(0, 1)
        if "wetland" in dataset:
            return _map_to_binary(
                dataset["wetland"],
                _CLASSIFICATION_BINARY_MAPS["g2017"],
            )

    if dataset_id == "glwd_v2" and "combined_classes" in dataset:
        return _map_to_binary(
            dataset["combined_classes"],
            _CLASSIFICATION_BINARY_MAPS["glwd_v2"],
        )

    if dataset_id == "gwd30" and "wetland_class" in dataset:
        source = dataset["wetland_class"]
        binary = _map_to_binary(source, _CLASSIFICATION_BINARY_MAPS["gwd30"])
        if "time" in binary.dims:
            binary = binary.mean(dim="time", skipna=True)
        return binary

    return None


def _map_to_binary(
    data: xr.DataArray,
    mapping: dict[int, float],
) -> xr.DataArray:
    """Map integer class codes to binary wetland fraction values."""

    result = xr.full_like(data, np.nan, dtype=np.float32)
    for source_value, target_value in mapping.items():
        result = xr.where(data == source_value, np.float32(target_value), result)
    return result.where(data.notnull()).astype(np.float32)


# ---------------------------------------------------------------------------
# Dataset label helpers
# ---------------------------------------------------------------------------

DATASET_DISPLAY_NAMES: dict[str, str] = {
    "g2017": "G2017",
    "giems_mc": "GIEMS-MC",
    "glwd_v2": "GLWD v2",
    "gwd30": "GWD30",
    "swamps": "SWAMPS",
    "topmodel": "TOPMODEL",
    "wad2m": "WAD2M",
}

DATASET_NATIVE_RESOLUTIONS: dict[str, str] = {
    "g2017": "0.05\u00b0",
    "giems_mc": "0.25\u00b0",
    "glwd_v2": "~1km",
    "gwd30": "~1km",
    "swamps": "25km",
    "topmodel": "0.25\u00b0",
    "wad2m": "0.25\u00b0",
}


def make_dataset_labels(dataset_ids: list[str]) -> dict[str, str]:
    """Generate display labels like 'G2017 (0.05°)' for each dataset."""
    labels: dict[str, str] = {}
    for ds_id in dataset_ids:
        name = DATASET_DISPLAY_NAMES.get(ds_id, ds_id)
        res = DATASET_NATIVE_RESOLUTIONS.get(ds_id, "")
        labels[ds_id] = f"{name} ({res})" if res else name
    return labels
