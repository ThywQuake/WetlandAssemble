"""Tests for Sentinel-2 batch download orchestration."""

from __future__ import annotations

import json
from pathlib import Path

from WA.s2_batch import (
    discover_probe_manifests,
    load_hotspots_from_manifest,
)


def test_discover_probe_manifests(tmp_path: Path) -> None:
    sub = tmp_path / "probe"
    sub.mkdir(parents=True)
    (sub / "fine_grained_probe.json").write_text("{}")

    files = discover_probe_manifests(tmp_path)
    assert len(files) == 1
    assert files[0].name == "fine_grained_probe.json"


def test_load_hotspots_from_manifest(tmp_path: Path) -> None:
    manifest = {
        "hotspots": [
            {
                "hotspot_id": "entropy-brazil-001",
                "region_slug": "brazil",
                "bbox": [-62.0, -6.0, -60.0, -4.0],
                "center_lon": -61.0,
                "center_lat": -5.0,
                "mean_entropy": 0.85,
                "max_entropy": 0.95,
                "cell_count": 12,
                "class_disagreement_summary": {"0": 0.1, "2": 0.9},
            }
        ]
    }
    mf_path = tmp_path / "fine_grained_probe.json"
    mf_path.write_text(json.dumps(manifest))

    hotspots = load_hotspots_from_manifest(mf_path)
    assert len(hotspots) == 1
    assert hotspots[0].hotspot_id == "entropy-brazil-001"
    assert hotspots[0].region_slug == "brazil"
    assert hotspots[0].bbox == (-62.0, -6.0, -60.0, -4.0)
    assert hotspots[0].mean_entropy == 0.85


def test_load_hotspots_from_manifest_empty(tmp_path: Path) -> None:
    mf_path = tmp_path / "fine_grained_probe.json"
    mf_path.write_text(json.dumps({"hotspot_count": 0}))

    hotspots = load_hotspots_from_manifest(mf_path)
    assert hotspots == []
