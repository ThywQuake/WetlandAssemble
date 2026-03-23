"""Tests for Sentinel-2 batch download orchestration."""

from __future__ import annotations

from pathlib import Path

from WA.s2_batch import (
    discover_hotspot_csv_files,
    load_hotspots_csv,
)


def test_discover_hotspot_csv_files(tmp_path: Path) -> None:
    sub = tmp_path / "region_a" / "2019-07"
    sub.mkdir(parents=True)
    (sub / "hotspots.csv").write_text("hotspot_id,region_slug\n")

    files = discover_hotspot_csv_files(tmp_path)
    assert len(files) == 1
    assert files[0].name == "hotspots.csv"


def test_load_hotspots_csv(tmp_path: Path) -> None:
    csv_content = (
        "hotspot_id,region_slug,bbox,center_lon,center_lat,"
        "mean_entropy,max_entropy,cell_count,class_disagreement_summary\n"
        'entropy-brazil-001,brazil,"(-62.0, -6.0, -60.0, -4.0)",-61.0,-5.0,'
        '0.85,0.95,12,"{\'0\': 0.1, \'2\': 0.9}"\n'
    )
    csv_path = tmp_path / "hotspots.csv"
    csv_path.write_text(csv_content)

    hotspots = load_hotspots_csv(csv_path)
    assert len(hotspots) == 1
    assert hotspots[0].hotspot_id == "entropy-brazil-001"
    assert hotspots[0].region_slug == "brazil"
    assert hotspots[0].mean_entropy == 0.85


def test_load_hotspots_csv_empty(tmp_path: Path) -> None:
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("")

    hotspots = load_hotspots_csv(csv_path)
    assert hotspots == []
