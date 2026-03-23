"""Phase 3.5 classification comparison panel — 2×3 grid per hotspot.

Layout:
  [0,0] S2 RGB          [0,1] Shannon Entropy   [0,2] Vote Classification
  [1,0] GLWD v2 native  [1,1] G2017 native      [1,2] GWD30 (500m)

Right margin:  Shannon entropy colorbar (white → red, [0, 1])
Bottom margin: Categorical legend patches (4-class)
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import rioxarray  # noqa: F401
import xarray as xr
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Patch
from rasterio.enums import Resampling

from WA.comparison.fine_grained import (
    FINE_4CLASS_LABELS,
    FINE_4CLASS_MAPS,
    ClassScheme,
)
from WA.loaders.base import BBox

# ---------------------------------------------------------------------------
# Colour definitions
# ---------------------------------------------------------------------------

FINE_4CLASS_COLORS: dict[int, str] = {
    0: "#d9d9d9",  # Non-wetland  — light grey
    1: "#2166ac",  # Open Water   — deep blue
    2: "#1b7837",  # Wetland      — deep green
    3: "#f4a582",  # Artificial   — peach
}

CLASS_CMAP = ListedColormap(
    [FINE_4CLASS_COLORS[i] for i in range(len(FINE_4CLASS_COLORS))],
    name="wetland_4class",
)

ENTROPY_CMAP = LinearSegmentedColormap.from_list("entropy_wr", ["white", "red"])


# ---------------------------------------------------------------------------
# Helpers — class-fraction resampling at arbitrary resolution
# ---------------------------------------------------------------------------

def _map_to_4class(data: xr.DataArray, dataset_id: str) -> xr.DataArray:
    """Apply ``FINE_4CLASS_MAPS`` to raw classification values."""
    mapping = FINE_4CLASS_MAPS[dataset_id]
    result = xr.full_like(data, np.nan, dtype=np.float32)
    for src_val, cls_id in mapping.items():
        result = xr.where(data == src_val, np.float32(cls_id), result)
    return result.where(data.notnull()).astype(np.float32)


def _class_fractions_at_resolution(
    mapped: xr.DataArray,
    target_res_deg: float,
    bbox: BBox,
    num_classes: int = 4,
) -> xr.DataArray:
    """Compute per-class area fractions on a regular grid.

    For each class *k*, builds a binary mask ``(mapped == k)`` and reprojects
    with ``Resampling.average`` to the target grid, yielding the *fraction* of
    source pixels belonging to class *k* in each coarse cell.

    Returns DataArray (class_id, lat, lon) with values in [0, 1].
    """
    west, south, east, north = bbox
    n_lat = max(1, round((north - south) / target_res_deg))
    n_lon = max(1, round((east - west) / target_res_deg))
    lats = np.linspace(north - target_res_deg / 2, south + target_res_deg / 2, n_lat)
    lons = np.linspace(west + target_res_deg / 2, east - target_res_deg / 2, n_lon)

    ref = xr.DataArray(
        np.zeros((n_lat, n_lon), dtype=np.float32),
        dims=("lat", "lon"),
        coords={"lat": lats, "lon": lons},
    )
    ref = ref.rio.write_crs("EPSG:4326")
    ref = ref.rio.set_spatial_dims(x_dim="lon", y_dim="lat")

    fractions = []
    for cls in range(num_classes):
        binary = xr.where(mapped == cls, 1.0, 0.0).astype(np.float32)
        binary = binary.where(mapped.notnull())
        if not binary.rio.crs:
            binary = binary.rio.write_crs("EPSG:4326")
        binary = binary.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
        coarse = binary.rio.reproject_match(ref, resampling=Resampling.average)
        fractions.append(coarse.expand_dims(class_id=[cls]))

    return xr.concat(fractions, dim="class_id").astype(np.float32)


# ---------------------------------------------------------------------------
# Public — vote classification
# ---------------------------------------------------------------------------

def compute_vote_classification(
    datasets: Mapping[str, xr.Dataset],
    bbox: BBox,
    *,
    class_scheme: ClassScheme = "4class",
    vote_resolution_deg: float = 0.005,  # ~500 m
) -> xr.DataArray:
    """Majority-vote classification at a common grid.

    For each participating dataset (GLWD / G2017 / GWD30):
      1. Load raw classification within *bbox*.
      2. Map to 4-class scheme.
      3. Compute per-class area fractions at *vote_resolution_deg*.

    Then, for each grid cell, sum class fractions across datasets and
    ``argmax`` → the winning class.
    """
    from WA.comparison.fine_grained import _prepare_fine_source

    num_classes = 4 if class_scheme == "4class" else 8

    all_fractions: list[xr.DataArray] = []
    for ds_id, ds in datasets.items():
        try:
            source, _ = _prepare_fine_source(ds_id, ds)
        except Exception:
            continue
        mapped = _map_to_4class(source, ds_id) if class_scheme == "4class" else source
        frac = _class_fractions_at_resolution(mapped, vote_resolution_deg, bbox, num_classes)
        all_fractions.append(frac)

    if not all_fractions:
        raise ValueError("No classification datasets available for vote")

    # Align all fractions to the first grid (they should match, but be safe)
    ref = all_fractions[0]
    aligned = [ref]
    for f in all_fractions[1:]:
        aligned.append(f.interp_like(ref, method="nearest"))

    summed = sum(aligned)  # type: ignore[arg-type]
    vote = summed.argmax(dim="class_id").astype(np.float32)  # type: ignore[union-attr]
    # Mask cells where no dataset had data
    valid = sum(a.sum(dim="class_id") for a in aligned)  # type: ignore[arg-type]
    vote = vote.where(valid > 0)  # type: ignore[union-attr]
    vote.name = "vote_classification"
    return vote  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Public — native-resolution classification loading
# ---------------------------------------------------------------------------

def load_native_classification(
    dataset_id: str,
    dataset: xr.Dataset,
    bbox: BBox,
    *,
    class_scheme: ClassScheme = "4class",
    gwd30_display_resolution_deg: float = 0.005,  # ~500 m
) -> xr.DataArray:
    """Load one dataset's classification at display resolution.

    GLWD (~1 km) and G2017 (0.05°) are kept at native resolution.
    GWD30 is aggregated to *gwd30_display_resolution_deg* via class-fraction
    resampling, then ``argmax`` → dominant class.

    Returns integer DataArray with values in {0, 1, 2, 3}.
    """
    from WA.comparison.fine_grained import _prepare_fine_source

    num_classes = 4 if class_scheme == "4class" else 8
    source, _ = _prepare_fine_source(dataset_id, dataset)
    mapped = _map_to_4class(source, dataset_id)

    if dataset_id == "gwd30":
        frac = _class_fractions_at_resolution(
            mapped, gwd30_display_resolution_deg, bbox, num_classes,
        )
        dominant = frac.argmax(dim="class_id").astype(np.float32)
        dominant = dominant.where(frac.sum(dim="class_id") > 0)
        dominant.name = "fine_class"
        return dominant

    return mapped


# ---------------------------------------------------------------------------
# Public — main panel plot
# ---------------------------------------------------------------------------

def plot_classification_panel(
    hotspot_id: str,
    region_label: str,
    bbox: BBox,
    *,
    satellite_image_path: Path | None,
    entropy_surface: xr.DataArray,
    vote_classification: xr.DataArray,
    native_classifications: dict[str, xr.DataArray],
    output_path: Path,
    dpi: int = 200,
    figsize: tuple[float, float] = (14.0, 9.0),
) -> Path:
    """Generate a 2×3 classification comparison panel and save as PNG.

    Parameters
    ----------
    hotspot_id : identifier shown in the title
    region_label : region shown in the title
    bbox : (west, south, east, north) geographic extent
    satellite_image_path : S2 RGB quicklook (JPG/PNG), or *None*
    entropy_surface : Shannon entropy DataArray [0, 1]
    vote_classification : majority-vote class DataArray {0..3}
    native_classifications : {dataset_id: 4-class DataArray}
    output_path : where to write the PNG
    dpi : output resolution
    figsize : figure size in inches
    """
    plt.rcParams.update({"font.size": 9})

    fig = plt.figure(figsize=figsize)
    gs = GridSpec(
        2, 4,
        figure=fig,
        width_ratios=[1, 1, 1, 0.04],
        wspace=0.08,
        hspace=0.15,
    )

    axes: dict[tuple[int, int], plt.Axes] = {}
    for r in range(2):
        for c in range(3):
            axes[(r, c)] = fig.add_subplot(gs[r, c])

    west, south, east, north = bbox

    # ── [0, 0] Sentinel-2 RGB ──
    ax = axes[(0, 0)]
    if satellite_image_path and satellite_image_path.exists():
        img = mpimg.imread(str(satellite_image_path))
        ax.imshow(
            img,
            extent=[west, east, south, north],
            aspect="auto",
            origin="upper",
        )
    else:
        ax.text(
            0.5, 0.5, "No S2 Image",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=11, color="gray",
        )
    ax.set_title("Sentinel-2", fontsize=10)

    # ── [0, 1] Shannon Entropy ──
    ax = axes[(0, 1)]
    im_ent = entropy_surface.plot.pcolormesh(
        ax=ax, cmap=ENTROPY_CMAP, vmin=0, vmax=1,
        add_colorbar=False, add_labels=False,
    )
    ax.set_title("Shannon Entropy", fontsize=10)

    # ── [0, 2] Vote Classification ──
    ax = axes[(0, 2)]
    _plot_categorical(ax, vote_classification)
    ax.set_title("Vote Classification", fontsize=10)

    # ── Bottom row: GLWD / G2017 / GWD30 ──
    bottom_order = ["glwd_v2", "g2017", "gwd30"]
    bottom_labels = {
        "glwd_v2": "GLWD v2 (~1 km)",
        "g2017": "G2017 (0.05\u00b0)",
        "gwd30": "GWD30 (500 m)",
    }
    for col, ds_id in enumerate(bottom_order):
        ax = axes[(1, col)]
        if ds_id in native_classifications:
            _plot_categorical(ax, native_classifications[ds_id])
        else:
            ax.text(
                0.5, 0.5, "No Data",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=11, color="gray",
            )
        ax.set_title(bottom_labels.get(ds_id, ds_id), fontsize=10)

    # ── Axis label control ──
    for (r, c), ax in axes.items():
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)
        ax.set_aspect("equal")
        if c != 0:
            ax.set_ylabel("")
            ax.tick_params(labelleft=False)
        else:
            ax.set_ylabel("Lat", fontsize=8)
        if r != 1:
            ax.set_xlabel("")
            ax.tick_params(labelbottom=False)
        else:
            ax.set_xlabel("Lon", fontsize=8)
        ax.tick_params(labelsize=7)

    # ── Entropy colorbar (right) ──
    cax = fig.add_subplot(gs[:, 3])
    fig.colorbar(im_ent, cax=cax, label="Shannon Entropy")
    cax.tick_params(labelsize=7)

    # ── Classification legend (bottom) ──
    legend_patches = [
        Patch(
            facecolor=FINE_4CLASS_COLORS[k],
            edgecolor="black",
            linewidth=0.5,
            label=FINE_4CLASS_LABELS[k],
        )
        for k in sorted(FINE_4CLASS_LABELS)
    ]
    fig.legend(
        handles=legend_patches,
        loc="lower center",
        ncol=len(FINE_4CLASS_LABELS),
        fontsize=9,
        frameon=False,
        bbox_to_anchor=(0.45, -0.02),
    )

    # ── Title ──
    fig.suptitle(f"{region_label} ({hotspot_id})", fontsize=13, y=0.98)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Internal — categorical pcolormesh
# ---------------------------------------------------------------------------

def _plot_categorical(ax: plt.Axes, data: xr.DataArray) -> None:  # type: ignore[type-arg]
    """Plot a 4-class categorical DataArray with the standard CLASS_CMAP."""
    data.plot.pcolormesh(
        ax=ax,
        cmap=CLASS_CMAP,
        vmin=-0.5,
        vmax=3.5,
        add_colorbar=False,
        add_labels=False,
    )
