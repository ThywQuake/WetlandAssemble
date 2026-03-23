from __future__ import annotations

import numpy as np
import xarray as xr

from WA.comparison.hotspots import (
    EntropyHotspot,
    compute_shannon_entropy,
    extract_hotspots,
)


def _make_harmonized(
    values_map: dict[str, list[list[float]]],
    lat: list[float] | None = None,
    lon: list[float] | None = None,
) -> dict[str, xr.DataArray]:
    lat = lat or [3.0, 2.0, 1.0, 0.0]
    lon = lon or [100.0, 101.0, 102.0, 103.0]
    return {
        dataset_id: xr.DataArray(
            np.array(values, dtype=np.float32),
            coords={"lat": lat, "lon": lon},
            dims=("lat", "lon"),
        )
        for dataset_id, values in values_map.items()
    }


def test_compute_shannon_entropy_uniform_distribution_gives_max() -> None:
    """When each dataset votes for a different class, entropy should be 1.0."""
    harmonized = _make_harmonized(
        {
            "a": [[0.0]],
            "b": [[1.0]],
            "c": [[2.0]],
            "d": [[3.0]],
        },
        lat=[1.0],
        lon=[100.0],
    )
    entropy = compute_shannon_entropy(harmonized, num_classes=4)
    np.testing.assert_allclose(entropy.values, [[1.0]], atol=1e-6)


def test_compute_shannon_entropy_perfect_agreement_gives_zero() -> None:
    """When all datasets agree, entropy should be 0.0."""
    harmonized = _make_harmonized(
        {
            "a": [[2.0]],
            "b": [[2.0]],
            "c": [[2.0]],
        },
        lat=[1.0],
        lon=[100.0],
    )
    entropy = compute_shannon_entropy(harmonized, num_classes=4)
    np.testing.assert_allclose(entropy.values, [[0.0]], atol=1e-6)


def test_compute_shannon_entropy_partial_agreement() -> None:
    """Two out of three agree → entropy between 0 and 1."""
    harmonized = _make_harmonized(
        {
            "a": [[1.0]],
            "b": [[1.0]],
            "c": [[2.0]],
        },
        lat=[1.0],
        lon=[100.0],
    )
    entropy = compute_shannon_entropy(harmonized, num_classes=4)
    val = float(entropy.values[0, 0])
    assert 0.0 < val < 1.0


def test_compute_shannon_entropy_nan_cells_produce_nan() -> None:
    """Cells with all-NaN input should produce NaN entropy."""
    harmonized = _make_harmonized(
        {
            "a": [[np.nan]],
            "b": [[np.nan]],
        },
        lat=[1.0],
        lon=[100.0],
    )
    entropy = compute_shannon_entropy(harmonized, num_classes=4)
    assert np.isnan(entropy.values[0, 0])


def test_extract_hotspots_finds_high_entropy_clusters() -> None:
    """End-to-end: a high-entropy block should produce a hotspot."""
    # 4x4 grid: top-left 2x2 has high entropy, rest is agreement
    harmonized = _make_harmonized(
        {
            "a": [[0, 0, 2, 2], [0, 0, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2]],
            "b": [[1, 1, 2, 2], [1, 1, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2]],
            "c": [[2, 2, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2]],
        },
    )
    entropy = compute_shannon_entropy(harmonized, num_classes=4)

    hotspots = extract_hotspots(
        entropy,
        harmonized,
        percentile_threshold=50.0,
        min_cluster_cells=2,
        min_distance_deg=0.1,
        top_n=5,
        top_n_per_region=5,
        aoi_size_deg=1.0,
        region_bboxes={"test_region": (99.0, -1.0, 104.0, 4.0)},
    )

    assert len(hotspots) >= 1
    assert all(isinstance(h, EntropyHotspot) for h in hotspots)
    assert hotspots[0].mean_entropy > 0


def test_extract_hotspots_respects_min_cluster_cells() -> None:
    """A single isolated high-entropy cell should be filtered by min_cluster_cells=4."""
    # Only 1 cell disagrees; the rest have perfect agreement (entropy=0).
    harmonized = _make_harmonized(
        {
            "a": [[0, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]],
            "b": [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]],
            "c": [[2, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]],
        },
    )
    entropy = compute_shannon_entropy(harmonized, num_classes=4)

    hotspots = extract_hotspots(
        entropy,
        harmonized,
        percentile_threshold=99.0,
        min_cluster_cells=4,
        min_distance_deg=0.1,
        region_bboxes={"test_region": (99.0, -1.0, 104.0, 4.0)},
    )

    assert len(hotspots) == 0


def test_extract_hotspots_deduplicates_nearby() -> None:
    """Clusters closer than min_distance_deg should be deduplicated."""
    harmonized = _make_harmonized(
        {
            "a": [[0, 0, 2, 0], [0, 0, 2, 0], [2, 2, 2, 2], [2, 2, 2, 2]],
            "b": [[1, 1, 2, 1], [1, 1, 2, 1], [2, 2, 2, 2], [2, 2, 2, 2]],
            "c": [[2, 2, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2]],
        },
    )
    entropy = compute_shannon_entropy(harmonized, num_classes=4)

    hotspots = extract_hotspots(
        entropy,
        harmonized,
        percentile_threshold=50.0,
        min_cluster_cells=2,
        min_distance_deg=5.0,
        top_n=10,
        top_n_per_region=10,
        aoi_size_deg=1.0,
        region_bboxes={"test_region": (99.0, -1.0, 104.0, 4.0)},
    )

    assert len(hotspots) <= 1


def test_extract_hotspots_stratifies_by_region() -> None:
    """top_n_per_region should cap hotspots from one region."""
    harmonized = _make_harmonized(
        {
            "a": [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
            "b": [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]],
            "c": [[2, 2, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2]],
        },
    )
    entropy = compute_shannon_entropy(harmonized, num_classes=4)

    hotspots = extract_hotspots(
        entropy,
        harmonized,
        percentile_threshold=0.0,
        min_cluster_cells=1,
        min_distance_deg=0.1,
        top_n=10,
        top_n_per_region=1,
        aoi_size_deg=0.5,
        region_bboxes={"test_region": (99.0, -1.0, 104.0, 4.0)},
    )

    assert len(hotspots) <= 1


def test_class_disagreement_summary_content() -> None:
    """class_disagreement_summary should reflect per-class vote distribution."""
    harmonized = _make_harmonized(
        {
            "a": [[0, 0, 2, 2], [0, 0, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2]],
            "b": [[1, 1, 2, 2], [1, 1, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2]],
            "c": [[2, 2, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2], [2, 2, 2, 2]],
        },
    )
    entropy = compute_shannon_entropy(harmonized, num_classes=4)

    hotspots = extract_hotspots(
        entropy,
        harmonized,
        percentile_threshold=50.0,
        min_cluster_cells=2,
        min_distance_deg=0.1,
        top_n=5,
        top_n_per_region=5,
        aoi_size_deg=1.0,
        region_bboxes={"test_region": (99.0, -1.0, 104.0, 4.0)},
    )

    assert len(hotspots) >= 1
    summary = hotspots[0].class_disagreement_summary
    assert isinstance(summary, dict)
    assert len(summary) > 0
    total = sum(summary.values())
    assert abs(total - 1.0) < 0.01
