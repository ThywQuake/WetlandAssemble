from __future__ import annotations

from pathlib import Path

import pytest

from WA.config import load_config, load_dataset_config, load_gee_config


def test_load_config_reads_dataset_and_gee_documents(tmp_path: Path) -> None:
    dataset_path = tmp_path / "datasets.yaml"
    dataset_path.write_text(
        """
datasets:
  sample:
    name: Sample
regions:
  global:
    bbox: [-180, -90, 180, 90]
analysis:
  spatial_metrics: ["OA"]
""".strip(),
        encoding="utf-8",
    )

    gee_path = tmp_path / "gee.yaml"
    gee_path.write_text('gee_project_id: "demo-project"\n', encoding="utf-8")

    dataset_document = load_dataset_config(dataset_path)
    gee_document = load_gee_config(gee_path)
    config = load_config(dataset_path, gee_path)

    assert dataset_document["datasets"]["sample"]["name"] == "Sample"
    assert gee_document["gee_project_id"] == "demo-project"
    assert config.datasets["sample"]["name"] == "Sample"
    assert config.gee["gee_project_id"] == "demo-project"


def test_load_dataset_config_requires_expected_top_level_keys(tmp_path: Path) -> None:
    dataset_path = tmp_path / "datasets.yaml"
    dataset_path.write_text("datasets: {}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required keys"):
        load_dataset_config(dataset_path)
