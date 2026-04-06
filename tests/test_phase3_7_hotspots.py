from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import xarray as xr

from WA.phase37_hotspots import (
    Phase37PriorityRegion,
    _build_hotspot_bbox,
    allocate_phase37_region_quotas,
    load_phase37_priority_regions,
    run_phase37_hotspot_selection,
)


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "find_phase3_7_hotspots.py"
    spec = importlib.util.spec_from_file_location("find_phase3_7_hotspots", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _phase36_metrics_from_entropy(
    entropy_values: np.ndarray,
    *,
    majority_class: np.ndarray | None = None,
    joint_valid_mask: np.ndarray | None = None,
) -> xr.Dataset:
    lat = np.array([1.2, 0.8, 0.4, 0.0], dtype=np.float32)
    lon = np.array([100.0, 100.4, 100.8, 101.2], dtype=np.float32)
    coords = {"lat": lat, "lon": lon}
    shape = entropy_values.shape
    if majority_class is None:
        majority_class = np.full(shape, 2, dtype=np.int16)
    if joint_valid_mask is None:
        joint_valid_mask = np.ones(shape, dtype=np.int8)
    return xr.Dataset(
        {
            "entropy": xr.DataArray(
                entropy_values.astype(np.float32),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "majority_class": xr.DataArray(
                majority_class.astype(np.int16),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "agreement_count": xr.DataArray(
                np.where(np.isfinite(entropy_values), 2, -1).astype(np.int16),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "joint_valid_mask": xr.DataArray(
                joint_valid_mask.astype(np.int8),
                dims=("lat", "lon"),
                coords=coords,
            ),
        }
    )


def _sample_phase36_classes() -> xr.Dataset:
    lat = np.array([1.2, 0.8, 0.4, 0.0], dtype=np.float32)
    lon = np.array([100.0, 100.4, 100.8, 101.2], dtype=np.float32)
    coords = {"lat": lat, "lon": lon}
    base = np.full((4, 4), 2, dtype=np.int16)
    return xr.Dataset(
        {
            "g2017_dominant_class": xr.DataArray(
                base.copy(),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "glwd_v2_dominant_class": xr.DataArray(
                base.copy(),
                dims=("lat", "lon"),
                coords=coords,
            ),
            "gwd30_dominant_class": xr.DataArray(
                base.copy(),
                dims=("lat", "lon"),
                coords=coords,
            ),
        }
    )


def test_load_phase37_priority_regions_sorts_by_priority(tmp_path: Path) -> None:
    config_path = tmp_path / "regions.yaml"
    config_path.write_text(
        """
regions:
  b:
    label: "B"
    priority: 2
    bbox: [100, 0, 102, 2]
  a:
    label: "A"
    priority: 1
    bbox: [100, 0, 104, 2]
""".strip(),
        encoding="utf-8",
    )

    regions = load_phase37_priority_regions(config_path)

    assert [region.region_id for region in regions] == ["a", "b"]


def test_allocate_phase37_region_quotas_uses_min1_and_hamilton() -> None:
    regions = [
        Phase37PriorityRegion("large", "Large", (0.0, 0.0, 4.0, 1.0), 1, 4.0),
        Phase37PriorityRegion("mid", "Mid", (0.0, 0.0, 2.0, 1.0), 2, 2.0),
        Phase37PriorityRegion("small", "Small", (0.0, 0.0, 1.0, 1.0), 3, 1.0),
    ]

    quotas = allocate_phase37_region_quotas(regions, total_budget=10)

    assert quotas == {"large": 5, "mid": 3, "small": 2}


def test_build_hotspot_bbox_clamps_to_global_bounds() -> None:
    bbox = _build_hotspot_bbox(center_lon=179.9, center_lat=89.9, aoi_size_deg=0.5)
    assert bbox == (179.65, 89.65, 180.0, 90.0)


def test_run_phase37_hotspot_selection_uses_local_thresholds_per_region(tmp_path: Path) -> None:
    metrics = _phase36_metrics_from_entropy(
        np.array(
            [
                [0.10, 0.11, 0.90, 0.91],
                [0.12, 0.13, 0.92, 0.93],
                [0.14, 0.15, 0.94, 0.95],
                [0.16, 0.17, 0.96, 0.97],
            ],
            dtype=np.float32,
        )
    )
    metrics_path = tmp_path / "phase3_6_entropy_global_500m_2016.nc"
    classes_path = tmp_path / "phase3_6_unified_classes_global_500m_2016.nc"
    metrics.to_netcdf(metrics_path)
    _sample_phase36_classes().to_netcdf(classes_path)

    regions_file = tmp_path / "regions.yaml"
    regions_file.write_text(
        """
regions:
  west:
    label: "West"
    priority: 1
    bbox: [99.9, -0.1, 100.5, 1.3]
  east:
    label: "East"
    priority: 2
    bbox: [100.7, -0.1, 101.3, 1.3]
""".strip(),
        encoding="utf-8",
    )

    result = run_phase37_hotspot_selection(
        metrics_path,
        classes_path,
        output_dir=tmp_path / "out",
        regions_file=regions_file,
        year=2016,
        total_budget=2,
        threshold_percentile=95.0,
        min_cluster_cells=1,
        aoi_size_deg=0.5,
        min_distance_deg=0.5,
        candidate_sample_step=1,
    )

    thresholds = {summary.region_id: summary.threshold_value for summary in result.region_summaries}
    assert thresholds["west"] is not None
    assert thresholds["east"] is not None
    assert thresholds["west"] < thresholds["east"]
    assert len(result.hotspots) == 2
    assert "sample1" in result.manifest_path.read_text(encoding="utf-8")


def test_run_phase37_hotspot_selection_filters_non_wetland_cells(tmp_path: Path) -> None:
    metrics = _phase36_metrics_from_entropy(
        np.array(
            [
                [0.90, 0.91, 0.10, 0.11],
                [0.92, 0.93, 0.12, 0.13],
                [0.14, 0.15, 0.16, 0.17],
                [0.18, 0.19, 0.20, 0.21],
            ],
            dtype=np.float32,
        ),
        majority_class=np.array(
            [
                [0, 0, 2, 2],
                [0, 0, 2, 2],
                [2, 2, 2, 2],
                [2, 2, 2, 2],
            ],
            dtype=np.int16,
        ),
    )
    metrics_path = tmp_path / "phase3_6_entropy_global_500m_2016.nc"
    classes_path = tmp_path / "phase3_6_unified_classes_global_500m_2016.nc"
    metrics.to_netcdf(metrics_path)
    _sample_phase36_classes().to_netcdf(classes_path)

    regions_file = tmp_path / "regions.yaml"
    regions_file.write_text(
        """
regions:
  full:
    label: "Full"
    priority: 1
    bbox: [99.9, -0.1, 101.3, 1.3]
""".strip(),
        encoding="utf-8",
    )

    result = run_phase37_hotspot_selection(
        metrics_path,
        classes_path,
        output_dir=tmp_path / "out",
        regions_file=regions_file,
        total_budget=1,
        threshold_percentile=95.0,
        min_cluster_cells=1,
        aoi_size_deg=0.5,
        min_distance_deg=0.5,
        candidate_sample_step=1,
    )

    assert len(result.hotspots) == 1
    hotspot = result.hotspots[0]
    assert hotspot.center_lon >= 100.8


def test_run_phase37_hotspot_selection_deduplicates_nearby_clusters(tmp_path: Path) -> None:
    metrics = _phase36_metrics_from_entropy(
        np.array(
            [
                [0.99, 0.99, 0.10, 0.98],
                [0.99, 0.99, 0.10, 0.98],
                [0.10, 0.10, 0.10, 0.10],
                [0.10, 0.10, 0.10, 0.10],
            ],
            dtype=np.float32,
        )
    )
    metrics_path = tmp_path / "phase3_6_entropy_global_500m_2016.nc"
    classes_path = tmp_path / "phase3_6_unified_classes_global_500m_2016.nc"
    metrics.to_netcdf(metrics_path)
    _sample_phase36_classes().to_netcdf(classes_path)

    regions_file = tmp_path / "regions.yaml"
    regions_file.write_text(
        """
regions:
  full:
    label: "Full"
    priority: 1
    bbox: [99.9, -0.1, 101.3, 1.3]
""".strip(),
        encoding="utf-8",
    )

    result = run_phase37_hotspot_selection(
        metrics_path,
        classes_path,
        output_dir=tmp_path / "out",
        regions_file=regions_file,
        total_budget=2,
        threshold_percentile=80.0,
        min_cluster_cells=1,
        aoi_size_deg=0.5,
        min_distance_deg=2.0,
        candidate_sample_step=1,
    )

    assert len(result.hotspots) == 1
    assert result.region_summaries[0].shortfall == 1


def test_run_phase37_hotspot_selection_records_empty_region_shortfall(tmp_path: Path) -> None:
    metrics = _phase36_metrics_from_entropy(np.full((4, 4), 0.2, dtype=np.float32))
    metrics_path = tmp_path / "phase3_6_entropy_global_500m_2016.nc"
    classes_path = tmp_path / "phase3_6_unified_classes_global_500m_2016.nc"
    metrics.to_netcdf(metrics_path)
    _sample_phase36_classes().to_netcdf(classes_path)

    regions_file = tmp_path / "regions.yaml"
    regions_file.write_text(
        """
regions:
  empty:
    label: "Empty"
    priority: 1
    bbox: [110.0, 10.0, 111.0, 11.0]
""".strip(),
        encoding="utf-8",
    )

    result = run_phase37_hotspot_selection(
        metrics_path,
        classes_path,
        output_dir=tmp_path / "out",
        regions_file=regions_file,
        total_budget=1,
        threshold_percentile=95.0,
        min_cluster_cells=1,
        aoi_size_deg=0.5,
        min_distance_deg=0.5,
        candidate_sample_step=1,
    )

    assert result.hotspots == []
    summary = result.region_summaries[0]
    assert summary.status == "no_spatial_overlap"
    assert summary.shortfall == 1
    assert summary.debug_png_path.is_file()


def test_find_phase3_7_hotspots_script_writes_outputs(tmp_path: Path) -> None:
    module = _load_script_module()
    metrics = _phase36_metrics_from_entropy(
        np.array(
            [
                [0.10, 0.90, 0.20, 0.30],
                [0.11, 0.91, 0.21, 0.31],
                [0.12, 0.92, 0.22, 0.32],
                [0.13, 0.93, 0.23, 0.33],
            ],
            dtype=np.float32,
        )
    )
    input_dir = tmp_path / "phase3.6"
    input_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_netcdf(input_dir / "phase3_6_entropy_global_500m_2016.nc")
    _sample_phase36_classes().to_netcdf(
        input_dir / "phase3_6_unified_classes_global_500m_2016.nc"
    )

    regions_file = tmp_path / "regions.yaml"
    regions_file.write_text(
        """
regions:
  full:
    label: "Full"
    priority: 1
    bbox: [99.9, -0.1, 101.3, 1.3]
""".strip(),
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    exit_code = module.main(
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--regions-file",
            str(regions_file),
            "--total-hotspot-budget",
            "1",
            "--threshold-percentile",
            "80",
            "--min-cluster-cells",
            "1",
            "--candidate-sample-step",
            "2",
        ]
    )

    assert exit_code == 0
    manifest_path = output_dir / "phase3_7_hotspots_2016.json"
    csv_path = output_dir / "phase3_7_hotspots_2016.csv"
    region_csv_path = output_dir / "phase3_7_hotspot_regions_2016.csv"
    assert manifest_path.is_file()
    assert csv_path.is_file()
    assert region_csv_path.is_file()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["hotspot_count"] == 1
    assert payload["hotspots"][0]["region_id"] == "full"
    assert payload["candidate_sample_step"] == 2
    assert "sample2" in payload["candidate_cache_path"]
    assert (output_dir / "debug" / "full.png").is_file()
