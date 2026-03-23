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
import xarray as xr
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.gridspec import GridSpec

from WA.loaders.base import BBox

N_COLS = 3

ENTROPY_CMAP = LinearSegmentedColormap.from_list("entropy_wr", ["#ffffff", "#d62728"])
WETLAND_CMAP = LinearSegmentedColormap.from_list("wetland_wb", ["#ffffff", "#1f77b4"])


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
