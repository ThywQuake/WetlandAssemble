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
    """A high-entropy AOI where classification datasets disagree most."""

    hotspot_id: str
    region_slug: str
    bbox: BBox
    center_lon: float
    center_lat: float
    mean_entropy: float
    max_entropy: float
    cell_count: int
    class_disagreement_summary: dict[str, float]


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
