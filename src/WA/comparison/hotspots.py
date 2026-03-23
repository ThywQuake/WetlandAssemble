"""Shannon entropy hotspot detection for fine-grained classification disagreement."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import xarray as xr
from scipy.ndimage import label as ndimage_label

from WA.comparison.focus_areas import (
    DEFAULT_FOCUS_REGION_BBOXES,
    _assign_region,
    _is_far_enough,
)
from WA.loaders.base import BBox


@dataclass(frozen=True)
class EntropyHotspot:
    """A high-entropy AOI where classification datasets disagree most,
    or a curated representative wetland site."""

    hotspot_id: str
    region_slug: str
    bbox: BBox
    center_lon: float
    center_lat: float
    mean_entropy: float
    max_entropy: float
    cell_count: int
    class_disagreement_summary: dict[str, float]
    source: str = "entropy"


def compute_shannon_entropy(
    harmonized: Mapping[str, xr.DataArray],
    *,
    num_classes: int = 4,
) -> xr.DataArray:
    """Per-cell normalized Shannon entropy across classification datasets.

    H = -sum(p_k * log2(p_k)) / log2(K)

    Returns values in [0, 1]: 0 = perfect agreement, 1 = uniform distribution.
    """
    if not harmonized:
        raise ValueError("harmonized must contain at least one dataset")
    if num_classes < 2:
        raise ValueError("num_classes must be >= 2")

    stack = xr.concat(
        [
            data.astype(np.float32).expand_dims(dataset=[dataset_id])
            for dataset_id, data in harmonized.items()
        ],
        dim="dataset",
    )

    valid_count = stack.notnull().sum(dim="dataset").astype(np.float32)

    entropy = xr.zeros_like(valid_count, dtype=np.float32)

    for class_id in range(num_classes):
        count = (stack == np.float32(class_id)).sum(dim="dataset").astype(np.float32)
        p_k = xr.where(valid_count > 0, count / valid_count, 0.0).astype(np.float32)
        log_term = xr.where(p_k > 0, p_k * np.log2(p_k.values.clip(min=1e-30)), 0.0)
        entropy = entropy - log_term.astype(np.float32)

    normalizer = np.float32(np.log2(num_classes))
    entropy = xr.where(valid_count > 0, entropy / normalizer, np.nan).astype(np.float32)

    entropy.name = "shannon_entropy"
    entropy.attrs["num_classes"] = num_classes
    entropy.attrs["num_datasets"] = len(harmonized)
    return entropy


def extract_hotspots(
    entropy: xr.DataArray,
    harmonized: Mapping[str, xr.DataArray],
    *,
    percentile_threshold: float = 95.0,
    min_cluster_cells: int = 4,
    min_distance_deg: float = 3.0,
    top_n: int = 10,
    top_n_per_region: int = 3,
    aoi_size_deg: float = 1.0,
    region_bboxes: Mapping[str, BBox] | None = None,
) -> list[EntropyHotspot]:
    """Extract stratified, deduplicated entropy hotspot AOIs."""
    region_bboxes = dict(region_bboxes or DEFAULT_FOCUS_REGION_BBOXES)

    # Step 1: Threshold
    values = entropy.values[np.isfinite(entropy.values)]
    if values.size == 0:
        return []
    threshold = float(np.percentile(values, percentile_threshold))
    mask = np.where(np.isfinite(entropy.values) & (entropy.values >= threshold), 1, 0)

    # Step 2: Cluster with scipy.ndimage.label
    labeled, num_clusters = ndimage_label(mask)

    # Step 3-4: Filter by size, compute stats, sort by mean entropy
    lat_vals = entropy.coords["lat"].values
    lon_vals = entropy.coords["lon"].values
    clusters: list[dict[str, object]] = []

    for cluster_id in range(1, num_clusters + 1):
        cell_mask = labeled == cluster_id
        cell_count = int(cell_mask.sum())
        if cell_count < min_cluster_cells:
            continue

        cluster_entropy = entropy.values[cell_mask]
        mean_entropy = float(np.nanmean(cluster_entropy))
        max_entropy = float(np.nanmax(cluster_entropy))

        rows, cols = np.where(cell_mask)
        center_lat = float(np.mean(lat_vals[rows]))
        center_lon = float(np.mean(lon_vals[cols]))

        summary = _class_disagreement_summary(harmonized, cell_mask)

        clusters.append({
            "center_lon": center_lon,
            "center_lat": center_lat,
            "mean_entropy": mean_entropy,
            "max_entropy": max_entropy,
            "cell_count": cell_count,
            "class_disagreement_summary": summary,
            "lon": center_lon,
            "lat": center_lat,
        })

    clusters.sort(key=lambda c: c["mean_entropy"], reverse=True)  # type: ignore[arg-type]

    # Step 5-6: Region stratification + deduplication
    selected: list[dict[str, object]] = []
    region_counts: defaultdict[str, int] = defaultdict(int)

    for cluster in clusters:
        region_slug = _assign_region(
            float(cluster["center_lon"]),  # type: ignore[arg-type]
            float(cluster["center_lat"]),  # type: ignore[arg-type]
            region_bboxes,
        )
        cluster["region_slug"] = region_slug

        if region_counts[region_slug] >= top_n_per_region:
            continue
        if not _is_far_enough(cluster, selected, min_distance_deg=min_distance_deg):
            continue

        selected.append(cluster)
        region_counts[region_slug] += 1
        if len(selected) >= top_n:
            break

    # Step 7-8: Build AOIs
    hotspots: list[EntropyHotspot] = []
    for index, cluster in enumerate(selected, start=1):
        center_lon = float(cluster["center_lon"])  # type: ignore[arg-type]
        center_lat = float(cluster["center_lat"])  # type: ignore[arg-type]
        region_slug = str(cluster["region_slug"])
        hotspot_id = f"entropy-{region_slug}-{index:03d}"
        half = aoi_size_deg / 2.0

        hotspots.append(
            EntropyHotspot(
                hotspot_id=hotspot_id,
                region_slug=region_slug,
                bbox=(
                    max(-180.0, center_lon - half),
                    max(-90.0, center_lat - half),
                    min(180.0, center_lon + half),
                    min(90.0, center_lat + half),
                ),
                center_lon=center_lon,
                center_lat=center_lat,
                mean_entropy=float(cluster["mean_entropy"]),  # type: ignore[arg-type]
                max_entropy=float(cluster["max_entropy"]),  # type: ignore[arg-type]
                cell_count=int(cluster["cell_count"]),  # type: ignore[arg-type]
                class_disagreement_summary=cluster["class_disagreement_summary"],  # type: ignore[assignment]
            )
        )

    return hotspots


# ---------------------------------------------------------------------------
# Representative wetland sites — curated locations in major tropical basins
# ---------------------------------------------------------------------------

REPRESENTATIVE_WETLAND_SITES: list[EntropyHotspot] = [
    # ── South America (brazil region) ──
    EntropyHotspot(
        hotspot_id="rep-brazil-amazon",
        region_slug="brazil",
        bbox=(-61.0, -4.0, -60.0, -3.0),
        center_lon=-60.5,
        center_lat=-3.5,
        mean_entropy=0.0,
        max_entropy=0.0,
        cell_count=0,
        class_disagreement_summary={},
        source="representative",
    ),
    EntropyHotspot(
        hotspot_id="rep-brazil-pantanal",
        region_slug="brazil",
        bbox=(-57.5, -18.5, -56.5, -17.5),
        center_lon=-57.0,
        center_lat=-18.0,
        mean_entropy=0.0,
        max_entropy=0.0,
        cell_count=0,
        class_disagreement_summary={},
        source="representative",
    ),
    # ── Africa ──
    EntropyHotspot(
        hotspot_id="rep-africa-congo",
        region_slug="africa",
        bbox=(17.5, -0.5, 18.5, 0.5),
        center_lon=18.0,
        center_lat=0.0,
        mean_entropy=0.0,
        max_entropy=0.0,
        cell_count=0,
        class_disagreement_summary={},
        source="representative",
    ),
    EntropyHotspot(
        hotspot_id="rep-africa-sudd",
        region_slug="africa",
        bbox=(31.0, 7.0, 32.0, 8.0),
        center_lon=31.5,
        center_lat=7.5,
        mean_entropy=0.0,
        max_entropy=0.0,
        cell_count=0,
        class_disagreement_summary={},
        source="representative",
    ),
    # ── Southeast Asia ──
    EntropyHotspot(
        hotspot_id="rep-sea-tonlesap",
        region_slug="southeast_asia",
        bbox=(103.5, 12.5, 104.5, 13.5),
        center_lon=104.0,
        center_lat=13.0,
        mean_entropy=0.0,
        max_entropy=0.0,
        cell_count=0,
        class_disagreement_summary={},
        source="representative",
    ),
    EntropyHotspot(
        hotspot_id="rep-sea-irrawaddy",
        region_slug="southeast_asia",
        bbox=(95.0, 15.5, 96.0, 16.5),
        center_lon=95.5,
        center_lat=16.0,
        mean_entropy=0.0,
        max_entropy=0.0,
        cell_count=0,
        class_disagreement_summary={},
        source="representative",
    ),
    # ── Indonesia ──
    EntropyHotspot(
        hotspot_id="rep-indonesia-borneo",
        region_slug="indonesia",
        bbox=(110.5, -1.5, 111.5, -0.5),
        center_lon=111.0,
        center_lat=-1.0,
        mean_entropy=0.0,
        max_entropy=0.0,
        cell_count=0,
        class_disagreement_summary={},
        source="representative",
    ),
    EntropyHotspot(
        hotspot_id="rep-indonesia-papua",
        region_slug="indonesia",
        bbox=(136.5, -6.0, 137.5, -5.0),
        center_lon=137.0,
        center_lat=-5.5,
        mean_entropy=0.0,
        max_entropy=0.0,
        cell_count=0,
        class_disagreement_summary={},
        source="representative",
    ),
]


def get_representative_sites(
    *,
    existing_hotspots: list[EntropyHotspot] | None = None,
    min_distance_deg: float = 3.0,
    region_bboxes: Mapping[str, BBox] | None = None,
) -> list[EntropyHotspot]:
    """Return curated representative wetland sites, filtering out those too close
    to existing entropy hotspots."""
    region_bboxes = dict(region_bboxes or DEFAULT_FOCUS_REGION_BBOXES)

    # Build existing-as-dicts for _is_far_enough compatibility
    existing_dicts: list[dict[str, object]] = []
    if existing_hotspots:
        for h in existing_hotspots:
            existing_dicts.append({
                "lon": h.center_lon,
                "lat": h.center_lat,
            })

    sites: list[EntropyHotspot] = []
    for site in REPRESENTATIVE_WETLAND_SITES:
        candidate = {"lon": site.center_lon, "lat": site.center_lat}
        # Skip if too close to an existing entropy hotspot
        if not _is_far_enough(candidate, existing_dicts, min_distance_deg=min_distance_deg):
            continue
        # Skip if too close to an already-selected representative site
        selected_dicts = [{"lon": s.center_lon, "lat": s.center_lat} for s in sites]
        if not _is_far_enough(candidate, selected_dicts, min_distance_deg=min_distance_deg):
            continue
        sites.append(site)

    return sites


def _class_disagreement_summary(
    harmonized: Mapping[str, xr.DataArray],
    cell_mask: np.ndarray,
) -> dict[str, float]:
    """Compute per-class vote frequency within a cluster."""
    total = 0.0
    class_counts: defaultdict[int, float] = defaultdict(float)

    for _dataset_id, data in harmonized.items():
        values = data.values[cell_mask]
        finite = values[np.isfinite(values)]
        for v in finite:
            class_counts[int(v)] += 1.0
            total += 1.0

    if total == 0:
        return {}

    return {str(k): round(v / total, 4) for k, v in sorted(class_counts.items())}
