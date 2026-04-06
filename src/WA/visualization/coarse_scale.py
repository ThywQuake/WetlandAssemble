"""Coarse-scale wetland percentage distribution visualization.

Generates full-domain (tropical/subtropical) wetland percentage maps,
temporal comparison plots, and multi-dataset statistical comparisons.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import Normalize
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Patch

from WA.classification import wetland_fraction_from_standardized_classes
from WA.loaders.base import BBox

# Progress callback type: (current, total, message) -> None
ProgressCallback = Callable[[int, int, str], None]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REGION_BBOXES: dict[str, BBox] = {
    "tropical": (-180, -23.5, 180, 23.5),
    "subtropical": (-180, -35, 180, -23.5),
    "tropical_subtropical": (-180, -35, 180, 23.5),
    "all": (-180, -35, 180, 23.5),
}

DATASET_DISPLAY_NAMES: dict[str, str] = {
    "berkeley_rwawc": "Berkeley-RWAWC",
    "g2017": "G2017",
    "giems_mc": "GIEMS-MC",
    "glwd_v2": "GLWD v2",
    "swamps": "SWAMPS",
    "topmodel": "TOPMODEL",
    "wad2m": "WAD2M",
}

# Color scheme for dataset comparison (distinct colors)
DATASET_COLORS = {
    "berkeley_rwawc": "#1f77b4",  # blue
    "g2017": "#ff7f0e",  # orange
    "giems_mc": "#2ca02c",  # green
    "glwd_v2": "#d62728",  # red
    "swamps": "#9467bd",  # purple
    "topmodel": "#8c564b",  # brown
    "wad2m": "#e377c2",  # pink
}

WETLAND_CMAP = "viridis"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_wetland_variable(dataset: xr.Dataset, dataset_id: str) -> xr.DataArray | None:
    """Extract wetland fraction variable from a standardized dataset.

    For classification datasets the latest YAML mapping decides which classes
    count as wetland. Waterbody classes are always excluded.
    """
    # Case 1: Direct wetland variable exists
    for var_name in ["wetland_fraction", "watermask", "inundation", "frac"]:
        if var_name in dataset.data_vars:
            return dataset[var_name]

    # Case 2: Classification dataset with frac_* variables
    classified_fraction = wetland_fraction_from_standardized_classes(dataset_id, dataset)
    if classified_fraction is not None:
        return classified_fraction

    # Case 3: Fallback - try frac_1 (single fraction variable)
    if "frac_1" in dataset.data_vars:
        return dataset["frac_1"]

    return None


def _aggregate_non_spatial(
    data: xr.DataArray,
    aggregation: str = "mean",
) -> xr.DataArray:
    """Aggregate non-spatial dimensions (time, config, forcing) to get a 2D surface.

    For TOPMODEL: aggregates over (config, forcing, time) → (lat, lon)
    For SWAMPS/GIEMS: aggregates over time → (lat, lon)
    For G2017/GLWD: no aggregation needed (already 2D)
    """
    result = data

    # Aggregate over config dimension if present (TOPMODEL)
    if "config" in result.dims:
        if aggregation == "mean":
            result = result.mean(dim="config", skipna=True)
        elif aggregation == "sum":
            result = result.sum(dim="config", skipna=True)

    # Aggregate over forcing dimension if present (TOPMODEL)
    if "forcing" in result.dims:
        if aggregation == "mean":
            result = result.mean(dim="forcing", skipna=True)
        elif aggregation == "sum":
            result = result.sum(dim="forcing", skipna=True)

    # Aggregate over time dimension if present
    if "time" in result.dims:
        if aggregation == "mean":
            result = result.mean(dim="time", skipna=True)
        elif aggregation == "sum":
            result = result.sum(dim="time", skipna=True)
        elif aggregation == "max":
            result = result.max(dim="time", skipna=True)
        elif aggregation == "min":
            result = result.min(dim="time", skipna=True)
        else:
            result = result.mean(dim="time", skipna=True)

    return result


def _aggregate_temporal(
    data: xr.DataArray,
    aggregation: str = "mean",
) -> xr.DataArray:
    """Aggregate temporal dimension to get a single surface.

    Deprecated: use _aggregate_non_spatial instead.
    """
    return _aggregate_non_spatial(data, aggregation)


def _clip_to_bbox(data: xr.DataArray, bbox: BBox) -> xr.DataArray:
    """Clip data to bounding box."""
    west, south, east, north = bbox

    # Handle both (lat, lon) and (y, x) conventions
    lat_dim = "lat" if "lat" in data.dims else "y"
    lon_dim = "lon" if "lon" in data.dims else "x"

    # Clip latitude (descending order: north to south)
    lat_coord = data.coords[lat_dim]
    if lat_coord[0] > lat_coord[-1]:  # Descending order
        lat_slice = slice(north, south)
    else:  # Ascending order
        lat_slice = slice(south, north)

    # Clip longitude (ascending order: west to east)
    lon_coord = data.coords[lon_dim]
    if lon_coord[0] > lon_coord[-1]:  # Descending order (rare)
        lon_slice = slice(east, west)
    else:  # Ascending order
        lon_slice = slice(west, east)

    clipped = data.sel({lat_dim: lat_slice, lon_dim: lon_slice})
    return clipped


def area_weighted_mean_to_regular_grid(
    data: xr.DataArray,
    bbox: BBox,
    *,
    resolution_deg: float = 0.25,
) -> xr.DataArray:
    """Aggregate one lat/lon wetland-fraction surface onto a regular grid.

    The aggregation uses cosine-latitude weighting so finer input pixels are
    averaged by approximate surface area rather than by raw cell count.
    If the source grid is coarser than the requested target grid along either
    axis, the function switches to coordinate interpolation instead of leaving
    empty target columns/rows.
    """

    if resolution_deg <= 0:
        raise ValueError("resolution_deg must be positive")

    surface = _as_latlon_surface(data)
    clipped = _clip_to_bbox(surface, bbox)

    west, south, east, north = bbox
    n_lat = int(round((north - south) / resolution_deg))
    n_lon = int(round((east - west) / resolution_deg))
    if n_lat <= 0 or n_lon <= 0:
        raise ValueError("bbox and resolution_deg produced an empty target grid")

    target_lons = west + (np.arange(n_lon, dtype=np.float64) + 0.5) * resolution_deg
    target_lats_ascending = south + (
        np.arange(n_lat, dtype=np.float64) + 0.5
    ) * resolution_deg
    target_lats = target_lats_ascending[::-1]

    if _is_already_regular_target_grid(clipped, target_lats, target_lons):
        result = clipped.transpose("lat", "lon").astype(np.float32)
        result.attrs.update(clipped.attrs)
        result.attrs["aggregation_strategy_version"] = 2
        return result

    lat_values = np.asarray(clipped["lat"].values, dtype=np.float64)
    lon_values = np.asarray(clipped["lon"].values, dtype=np.float64)
    values = np.asarray(clipped.values, dtype=np.float64)

    if values.ndim != 2:
        raise ValueError(
            "area_weighted_mean_to_regular_grid expects a 2D surface after temporal aggregation"
        )

    if clipped.sizes["lat"] < n_lat or clipped.sizes["lon"] < n_lon:
        interpolated = _interpolate_to_regular_grid(
            clipped,
            target_lats_ascending=target_lats_ascending,
            target_lons=target_lons,
        )
        interpolated.attrs["aggregation_method"] = "interpolated_to_regular_grid"
        interpolated.attrs["aggregation_resolution_deg"] = float(resolution_deg)
        interpolated.attrs["aggregation_strategy_version"] = 2
        return interpolated

    epsilon = resolution_deg * 1e-6
    lat_edges = south + np.arange(n_lat + 1, dtype=np.float64) * resolution_deg
    lon_edges = west + np.arange(n_lon + 1, dtype=np.float64) * resolution_deg

    clipped_lats = np.clip(lat_values, south + epsilon, north - epsilon)
    clipped_lons = np.clip(lon_values, west + epsilon, east - epsilon)
    lat_index = np.searchsorted(lat_edges, clipped_lats, side="right") - 1
    lon_index = np.searchsorted(lon_edges, clipped_lons, side="right") - 1

    valid_lat = (lat_index >= 0) & (lat_index < n_lat)
    valid_lon = (lon_index >= 0) & (lon_index < n_lon)
    if not valid_lat.any() or not valid_lon.any():
        raise ValueError("No source pixels overlap the requested target grid")

    target_index = lat_index[:, None] * n_lon + lon_index[None, :]
    area_weights = np.cos(np.deg2rad(lat_values))[:, None]
    broadcast_weights = np.broadcast_to(area_weights, values.shape)
    valid_mask = np.isfinite(values) & valid_lat[:, None] & valid_lon[None, :]

    result_flat = np.full(n_lat * n_lon, np.nan, dtype=np.float32)
    if valid_mask.any():
        flat_index = target_index[valid_mask].astype(np.int64)
        numerator = np.bincount(
            flat_index,
            weights=(values * broadcast_weights)[valid_mask],
            minlength=n_lat * n_lon,
        )
        denominator = np.bincount(
            flat_index,
            weights=broadcast_weights[valid_mask],
            minlength=n_lat * n_lon,
        )
        nonzero = denominator > 0
        result_flat[nonzero] = (numerator[nonzero] / denominator[nonzero]).astype(np.float32)

    result = result_flat.reshape(n_lat, n_lon)[::-1, :]
    aggregated = xr.DataArray(
        result,
        dims=("lat", "lon"),
        coords={"lat": target_lats, "lon": target_lons},
        name=clipped.name,
        attrs=dict(clipped.attrs),
    )
    aggregated.attrs["aggregation_method"] = "cosine_latitude_area_weighted_mean"
    aggregated.attrs["aggregation_resolution_deg"] = float(resolution_deg)
    aggregated.attrs["aggregation_strategy_version"] = 2
    return aggregated


def _as_latlon_surface(data: xr.DataArray) -> xr.DataArray:
    """Normalize one spatial 2D surface to ``lat``/``lon`` dimensions."""

    rename_map: dict[str, str] = {}
    if "y" in data.dims and "lat" not in data.dims:
        rename_map["y"] = "lat"
    if "x" in data.dims and "lon" not in data.dims:
        rename_map["x"] = "lon"
    result = data.rename(rename_map) if rename_map else data
    if "lat" not in result.dims or "lon" not in result.dims:
        raise ValueError(f"Expected lat/lon or y/x dimensions, got {result.dims}")
    return result


def _is_already_regular_target_grid(
    data: xr.DataArray,
    target_lats: np.ndarray,
    target_lons: np.ndarray,
    *,
    rtol: float = 1e-6,
) -> bool:
    """Return whether a surface already matches the requested target grid."""

    if data.sizes.get("lat") != len(target_lats) or data.sizes.get("lon") != len(target_lons):
        return False
    return np.allclose(data["lat"].values, target_lats, rtol=rtol, atol=0.0) and np.allclose(
        data["lon"].values,
        target_lons,
        rtol=rtol,
        atol=0.0,
    )


def _interpolate_to_regular_grid(
    data: xr.DataArray,
    *,
    target_lats_ascending: np.ndarray,
    target_lons: np.ndarray,
) -> xr.DataArray:
    """Interpolate a coarse rectilinear surface onto a regular target grid."""

    source = data
    if source["lat"].values[0] > source["lat"].values[-1]:
        source = source.sortby("lat")
    if source["lon"].values[0] > source["lon"].values[-1]:
        source = source.sortby("lon")

    interpolated = source.interp(
        lat=xr.DataArray(target_lats_ascending, dims="lat"),
        lon=xr.DataArray(target_lons, dims="lon"),
        method="linear",
        kwargs={"fill_value": np.nan},
    )
    result = interpolated.transpose("lat", "lon").isel(lat=slice(None, None, -1)).astype(np.float32)
    result.attrs = dict(data.attrs)
    return result


def _compute_statistics(
    data: xr.DataArray,
) -> dict[str, float]:
    """Compute basic statistics for wetland distribution."""
    # Flatten and remove NaN values
    flat_values = data.values.flatten()
    valid_mask = ~np.isnan(flat_values)
    valid_data = flat_values[valid_mask]

    if len(valid_data) == 0:
        return {"mean": np.nan, "std": np.nan, "min": np.nan, "max": np.nan, "total": np.nan}

    # Estimate area-weighted statistics (simplified: assume equal grid spacing)
    return {
        "mean": float(np.mean(valid_data)),
        "std": float(np.std(valid_data)),
        "min": float(np.min(valid_data)),
        "max": float(np.max(valid_data)),
        "total": float(np.sum(valid_data)),
    }


# ---------------------------------------------------------------------------
# Single dataset visualization
# ---------------------------------------------------------------------------

def plot_single_dataset_distribution(
    dataset: xr.Dataset,
    dataset_id: str,
    region: str = "all",
    year: int | None = None,
    output_path: Path | None = None,
    dpi: int = 150,
    figsize: tuple[float, float] = (12, 8),
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Generate wetland percentage distribution plot for a single dataset.

    Layout:
      [Main] Wetland percentage map (tropical/subtropical domain)
      [Bottom-left] Histogram of pixel percentages
      [Bottom-right] Temporal trend (if multi-year data)

    Parameters
    ----------
    dataset : Standardized dataset
    dataset_id : Dataset identifier (e.g., "g2017", "swamps")
    region : One of "tropical", "subtropical", "tropical_subtropical", "all"
    year : Specific year to plot (for multi-year datasets)
    output_path : Output file path
    dpi : Output resolution
    figsize : Figure size in inches
    progress_callback : Optional callback (current, total, message) for progress updates

    Returns
    -------
    Path to saved figure
    """
    plt.rcParams.update({"font.size": 10})

    bbox = REGION_BBOXES.get(region, REGION_BBOXES["all"])
    west, south, east, north = bbox

    # Get wetland variable
    wetland_var = _get_wetland_variable(dataset, dataset_id)
    if wetland_var is None:
        raise ValueError(f"No wetland variable found in dataset {dataset_id}")

    if progress_callback:
        progress_callback(0, 3, "Extracting wetland variable...")

    # Select year if specified
    if year is not None and "time" in wetland_var.dims:
        time_coord = wetland_var.coords["time"]
        if hasattr(time_coord.dt, "year"):
            wetland_var = wetland_var.sel(time=time_coord.dt.year == year)

    if progress_callback:
        progress_callback(1, 3, "Aggregating dimensions...")

    # Aggregate non-spatial dimensions (time, config, forcing)
    wetland_surface = _aggregate_non_spatial(wetland_var, aggregation="mean")

    # Clip to region
    wetland_clipped = _clip_to_bbox(wetland_surface, bbox)

    if progress_callback:
        progress_callback(2, 3, "Creating figure...")

    # Create figure
    fig = plt.figure(figsize=figsize)
    gs = GridSpec(
        2, 2,
        figure=fig,
        width_ratios=[1, 0.3],
        height_ratios=[3, 1],
        wspace=0.15,
        hspace=0.25,
    )

    # Main map
    ax_map = fig.add_subplot(gs[0, :])
    lat_dim = "lat" if "lat" in wetland_clipped.dims else "y"
    lon_dim = "lon" if "lon" in wetland_clipped.dims else "x"

    im = wetland_clipped.plot.pcolormesh(
        ax=ax_map,
        x=lon_dim,
        y=lat_dim,
        cmap=WETLAND_CMAP,
        vmin=0,
        vmax=1,
        add_colorbar=True,
    )
    ax_map.set_title(f"{DATASET_DISPLAY_NAMES.get(dataset_id, dataset_id)} - Wetland Percentage")
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")

    # Histogram
    ax_hist = fig.add_subplot(gs[1, 0])
    valid_values = wetland_clipped.values.flatten()
    valid_values = valid_values[~np.isnan(valid_values)]
    if len(valid_values) > 0:
        ax_hist.hist(valid_values, bins=50, range=(0, 1), color=DATASET_COLORS.get(dataset_id, "#1f77b4"), edgecolor="black", linewidth=0.5)
        ax_hist.set_xlabel("Wetland Percentage")
        ax_hist.set_ylabel("Pixel Count")
        ax_hist.set_title("Distribution of Wetland Percentages")
        ax_hist.grid(True, alpha=0.3)

    # Statistics text box
    stats = _compute_statistics(wetland_clipped)
    stats_text = (
        f"Mean: {stats['mean']:.2%}\n"
        f"Std: {stats['std']:.2%}\n"
        f"Min: {stats['min']:.2%}\n"
        f"Max: {stats['max']:.2%}"
    )
    ax_stats = fig.add_subplot(gs[1, 1])
    ax_stats.text(
        0.5, 0.8, stats_text,
        transform=ax_stats.transAxes,
        fontsize=9,
        verticalalignment="top",
        bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
    )
    ax_stats.axis("off")

    # Add year to title if specified
    if year:
        fig.suptitle(f"Year: {year}", fontsize=12, y=0.98)

    if output_path is None:
        year_str = f"_{year}" if year else ""
        output_path = Path(f"{dataset_id}_wetland{year_str}_{region}.png")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Multi-dataset comparison
# ---------------------------------------------------------------------------

def plot_multi_dataset_comparison(
    datasets: dict[str, xr.Dataset],
    region: str = "all",
    year: int | None = None,
    output_path: Path | None = None,
    dpi: int = 150,
    figsize: tuple[float, float] = (16, 10),
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Generate side-by-side comparison of multiple datasets.

    Layout: 2×4 grid (or auto-sized) showing wetland percentage for each dataset.

    Parameters
    ----------
    datasets : Dict of {dataset_id: dataset}
    region : One of "tropical", "subtropical", "tropical_subtropical", "all"
    year : Specific year to plot
    output_path : Output file path
    dpi : Output resolution
    figsize : Figure size in inches
    progress_callback : Optional callback (current, total, message) for progress updates

    Returns
    -------
    Path to saved figure
    """
    plt.rcParams.update({"font.size": 9})

    bbox = REGION_BBOXES.get(region, REGION_BBOXES["all"])
    west, south, east, north = bbox

    # Filter datasets that have data with progress
    valid_datasets: dict[str, xr.DataArray] = {}
    dataset_items = list(datasets.items())
    total_steps = len(dataset_items)

    for idx, (ds_id, ds) in enumerate(dataset_items):
        if progress_callback:
            progress_callback(idx, total_steps, f"Processing {ds_id}...")

        wetland_var = _get_wetland_variable(ds, ds_id)
        if wetland_var is not None:
            # Select year if specified
            if year is not None and "time" in wetland_var.dims:
                time_coord = wetland_var.coords["time"]
                if hasattr(time_coord.dt, "year"):
                    wetland_var = wetland_var.sel(time=time_coord.dt.year == year)
            # Aggregate and clip
            wetland_surface = _aggregate_non_spatial(wetland_var, aggregation="mean")
            wetland_clipped = _clip_to_bbox(wetland_surface, bbox)
            valid_datasets[ds_id] = wetland_clipped

    if not valid_datasets:
        raise ValueError("No valid datasets with wetland data")

    # Determine grid size
    n_datasets = len(valid_datasets)
    n_cols = min(4, n_datasets)
    n_rows = (n_datasets + n_cols - 1) // n_cols

    if progress_callback:
        progress_callback(total_steps, total_steps, "Creating figure...")

    fig = plt.figure(figsize=figsize)
    gs = GridSpec(
        n_rows, n_cols + 1,
        figure=fig,
        width_ratios=[1] * n_cols + [0.05],
        wspace=0.12,
        hspace=0.20,
    )

    # Plot each dataset
    sorted_ids = sorted(valid_datasets.keys())
    for idx, ds_id in enumerate(sorted_ids):
        row = idx // n_cols
        col = idx % n_cols
        ax = fig.add_subplot(gs[row, col])

        data = valid_datasets[ds_id]
        lat_dim = "lat" if "lat" in data.dims else "y"
        lon_dim = "lon" if "lon" in data.dims else "x"

        im = data.plot.pcolormesh(
            ax=ax,
            x=lon_dim,
            y=lat_dim,
            cmap=WETLAND_CMAP,
            vmin=0,
            vmax=1,
            add_colorbar=False,
            add_labels=False,
        )

        # Title with dataset name
        ax.set_title(DATASET_DISPLAY_NAMES.get(ds_id, ds_id), fontsize=10, fontweight="bold")
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)
        ax.set_aspect("equal")

        # Only show axis labels on left/bottom
        if col != 0:
            ax.set_ylabel("")
            ax.tick_params(labelleft=False)
        else:
            ax.set_ylabel("Lat", fontsize=8)

        if row != n_rows - 1:
            ax.set_xlabel("")
            ax.tick_params(labelbottom=False)
        else:
            ax.set_xlabel("Lon", fontsize=8)

    # Colorbar on the right
    cax = fig.add_subplot(gs[:, -1])
    fig.colorbar(im, cax=cax, label="Wetland Fraction")
    cax.tick_params(labelsize=8)

    # Add year to title
    title = f"Wetland Percentage Comparison - {region.replace('_', ' ').title()}"
    if year:
        title += f" ({year})"
    fig.suptitle(title, fontsize=13, fontweight="bold", y=0.98)

    if output_path is None:
        year_str = f"_{year}" if year else ""
        output_path = Path(f"multi_dataset_comparison{year_str}_{region}.png")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Temporal comparison
# ---------------------------------------------------------------------------

def plot_temporal_comparison(
    datasets: dict[str, xr.Dataset],
    region: str = "all",
    output_path: Path | None = None,
    dpi: int = 150,
    figsize: tuple[float, float] = (14, 8),
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Generate time series comparison of wetland area across datasets.

    Layout:
      [Main] Time series of total wetland area
      [Inset] Mean wetland percentage over time

    Parameters
    ----------
    datasets : Dict of {dataset_id: dataset}
    region : One of "tropical", "subtropical", "tropical_subtropical", "all"
    output_path : Output file path
    dpi : Output resolution
    figsize : Figure size in inches
    progress_callback : Optional callback (current, total, message) for progress updates

    Returns
    -------
    Path to saved figure
    """
    plt.rcParams.update({"font.size": 11})

    bbox = REGION_BBOXES.get(region, REGION_BBOXES["all"])

    # Collect time series data for each dataset
    timeseries_data: dict[str, dict] = {}
    dataset_items = list(datasets.items())
    total_steps = len(dataset_items)

    for idx, (ds_id, ds) in enumerate(dataset_items):
        if progress_callback:
            progress_callback(idx, total_steps, f"Processing {ds_id}...")

        wetland_var = _get_wetland_variable(ds, ds_id)
        if wetland_var is None or "time" not in wetland_var.dims:
            continue

        # Clip to region
        wetland_clipped = _clip_to_bbox(wetland_var, bbox)

        # Compute time series
        time_coord = wetland_clipped.coords["time"]

        # Aggregate over space for each time step
        total_wetland = wetland_clipped.sum(dim=["lat", "lon"] if "lat" in wetland_clipped.dims else ["y", "x"])
        mean_wetland = wetland_clipped.mean(dim=["lat", "lon"] if "lat" in wetland_clipped.dims else ["y", "x"])

        timeseries_data[ds_id] = {
            "time": time_coord.values,
            "total": total_wetland.values,
            "mean": mean_wetland.values,
        }

    if not timeseries_data:
        raise ValueError("No datasets with temporal data available")

    if progress_callback:
        progress_callback(total_steps, total_steps, "Creating figure...")

    fig = plt.figure(figsize=figsize)
    gs = GridSpec(1, 2, figure=fig, width_ratios=[2, 1], wspace=0.15)

    # Main time series plot
    ax_ts = fig.add_subplot(gs[0, 0])

    for ds_id, data in timeseries_data.items():
        color = DATASET_COLORS.get(ds_id, None)
        # Convert cftime to numpy datetime64 for matplotlib compatibility
        time_values = data["time"]
        try:
            # Try to convert cftime to datetime64
            import cftime
            if len(time_values) > 0 and isinstance(time_values[0], cftime.datetime):
                time_values = np.array([t.strftime("%Y-%m") for t in time_values])
        except (ImportError, IndexError, AttributeError):
            pass  # Keep original if conversion fails

        ax_ts.plot(
            time_values, data["mean"],
            label=DATASET_DISPLAY_NAMES.get(ds_id, ds_id),
            color=color,
            linewidth=1.5,
            marker="o",
            markersize=3,
        )

    ax_ts.set_xlabel("Time")
    ax_ts.set_ylabel("Mean Wetland Fraction")
    ax_ts.set_title("Temporal Evolution of Wetland Percentage")
    ax_ts.legend(loc="upper right", fontsize=9)
    ax_ts.grid(True, alpha=0.3)
    ax_ts.tick_params(axis="x", rotation=45)

    # Summary statistics bar chart
    ax_bar = fig.add_subplot(gs[0, 1])

    # Compute overall mean for each dataset
    dataset_means = []
    dataset_names = []
    dataset_colors = []

    for ds_id in sorted(timeseries_data.keys()):
        data = timeseries_data[ds_id]
        overall_mean = float(np.nanmean(data["mean"]))
        dataset_means.append(overall_mean)
        dataset_names.append(DATASET_DISPLAY_NAMES.get(ds_id, ds_id)[:12])  # Truncate long names
        dataset_colors.append(DATASET_COLORS.get(ds_id, "#1f77b4"))

    y_pos = np.arange(len(dataset_names))
    bars = ax_bar.barh(y_pos, dataset_means, color=dataset_colors)
    ax_bar.set_yticks(y_pos)
    ax_bar.set_yticklabels(dataset_names)
    ax_bar.set_xlabel("Mean Wetland Fraction")
    ax_bar.set_title("Overall Average")
    ax_bar.grid(True, alpha=0.3, axis="x")

    # Add value labels on bars
    for bar, val in zip(bars, dataset_means):
        ax_bar.text(
            bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
            f"{val:.2%}", va="center", fontsize=9,
        )

    fig.suptitle(f"Wetland Temporal Comparison - {region.replace('_', ' ').title()}", fontsize=13, fontweight="bold")

    if output_path is None:
        output_path = Path(f"temporal_comparison_{region}.png")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Statistical comparison
# ---------------------------------------------------------------------------

def plot_wetland_area_statistics(
    datasets: dict[str, xr.Dataset],
    region: str = "all",
    year: int | None = None,
    output_path: Path | None = None,
    dpi: int = 150,
    figsize: tuple[float, float] = (12, 8),
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Generate statistical comparison bar charts.

    Layout:
      [Left] Total wetland area by dataset
      [Right] Mean and std deviation comparison

    Parameters
    ----------
    datasets : Dict of {dataset_id: dataset}
    region : One of "tropical", "subtropical", "tropical_subtropical", "all"
    year : Specific year to plot
    output_path : Output file path
    dpi : Output resolution
    figsize : Figure size in inches
    progress_callback : Optional callback (current, total, message) for progress updates

    Returns
    -------
    Path to saved figure
    """
    plt.rcParams.update({"font.size": 11})

    bbox = REGION_BBOXES.get(region, REGION_BBOXES["all"])

    # Collect statistics for each dataset
    stats: dict[str, dict] = {}
    dataset_items = list(datasets.items())
    total_steps = len(dataset_items)

    for idx, (ds_id, ds) in enumerate(dataset_items):
        if progress_callback:
            progress_callback(idx, total_steps, f"Processing {ds_id}...")

        wetland_var = _get_wetland_variable(ds, ds_id)
        if wetland_var is None:
            continue

        # Select year if specified
        if year is not None and "time" in wetland_var.dims:
            time_coord = wetland_var.coords["time"]
            if hasattr(time_coord.dt, "year"):
                wetland_var = wetland_var.sel(time=time_coord.dt.year == year)

        # Aggregate non-spatial dimensions
        wetland_surface = _aggregate_non_spatial(wetland_var, aggregation="mean")

        # Clip to region
        wetland_clipped = _clip_to_bbox(wetland_surface, bbox)

        # Compute statistics
        stats[ds_id] = _compute_statistics(wetland_clipped)

    if not stats:
        raise ValueError("No valid datasets with wetland data")

    if progress_callback:
        progress_callback(total_steps, total_steps, "Creating figure...")

    fig, (ax_total, ax_stats) = plt.subplots(1, 2, figsize=figsize)

    # Prepare data
    sorted_ids = sorted(stats.keys())
    names = [DATASET_DISPLAY_NAMES.get(ds_id, ds_id) for ds_id in sorted_ids]
    colors = [DATASET_COLORS.get(ds_id, "#1f77b4") for ds_id in sorted_ids]

    # Total wetland area
    totals = [stats[ds_id]["total"] for ds_id in sorted_ids]
    x_pos = np.arange(len(names))
    bars1 = ax_total.bar(x_pos, totals, color=colors)

    ax_total.set_ylabel("Total Wetland Area (pixel-sum)")
    ax_total.set_title("Total Wetland Area by Dataset")
    ax_total.set_xticks(x_pos)
    ax_total.set_xticklabels(names, rotation=45, ha="right")
    ax_total.grid(True, alpha=0.3, axis="y")

    # Add value labels
    for bar, val in zip(bars1, totals):
        ax_total.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height(),
            f"{val:.0f}", ha="center", va="bottom", fontsize=9,
        )

    # Mean and std comparison
    means = [stats[ds_id]["mean"] for ds_id in sorted_ids]
    stds = [stats[ds_id]["std"] for ds_id in sorted_ids]

    x_pos = np.arange(len(names))
    width = 0.35

    bars_mean = ax_stats.bar(x_pos - width / 2, means, width, label="Mean", color=colors, alpha=0.8)
    bars_std = ax_stats.bar(x_pos + width / 2, stds, width, label="Std Dev", color=colors, hatch="//", alpha=0.6)

    ax_stats.set_ylabel("Wetland Fraction")
    ax_stats.set_title("Mean and Standard Deviation")
    ax_stats.set_xticks(x_pos)
    ax_stats.set_xticklabels(names, rotation=45, ha="right")
    ax_stats.legend()
    ax_stats.grid(True, alpha=0.3, axis="y")
    ax_stats.set_ylim(0, max(max(means) * 1.2, 0.1))

    # Add value labels
    for bar, val in zip(bars_mean, means):
        ax_stats.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height(),
            f"{val:.2%}", ha="center", va="bottom", fontsize=8,
        )

    fig.suptitle(f"Wetland Statistics Comparison - {region.replace('_', ' ').title()}" + (f" ({year})" if year else ""), fontsize=13, fontweight="bold")

    if output_path is None:
        year_str = f"_{year}" if year else ""
        output_path = Path(f"wetland_statistics{year_str}_{region}.png")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path
