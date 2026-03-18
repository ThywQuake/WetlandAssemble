"""Configuration loading helpers for the Wetland Assemble project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ConfigDict = dict[str, Any]


@dataclass(frozen=True)
class AppConfig:
    """Resolved application configuration."""

    datasets: ConfigDict
    regions: ConfigDict
    analysis: ConfigDict
    gee: ConfigDict
    dataset_config_path: Path
    gee_config_path: Path


def _resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _load_yaml(path: str | Path) -> ConfigDict:
    resolved_path = _resolve_path(path)
    with resolved_path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}

    if not isinstance(document, dict):
        raise ValueError(f"Expected a mapping in {resolved_path}, got {type(document).__name__}")

    return document


def load_dataset_config(path: str | Path = "config/datasets.yaml") -> ConfigDict:
    """Load the dataset configuration document."""

    document = _load_yaml(path)
    required_keys = {"datasets", "regions", "analysis"}
    missing_keys = sorted(required_keys - set(document))
    if missing_keys:
        raise ValueError(
            "Dataset config is missing required keys: " + ", ".join(missing_keys)
        )
    return document


def load_gee_config(path: str | Path = "config/gee_config.yaml") -> ConfigDict:
    """Load Google Earth Engine configuration."""

    document = _load_yaml(path)
    if "gee_project_id" not in document:
        raise ValueError("GEE config is missing required key: gee_project_id")
    return document


def load_config(
    dataset_config_path: str | Path = "config/datasets.yaml",
    gee_config_path: str | Path = "config/gee_config.yaml",
) -> AppConfig:
    """Load the full application configuration bundle."""

    dataset_document = load_dataset_config(dataset_config_path)
    gee_document = load_gee_config(gee_config_path)

    return AppConfig(
        datasets=dataset_document["datasets"],
        regions=dataset_document["regions"],
        analysis=dataset_document["analysis"],
        gee=gee_document,
        dataset_config_path=_resolve_path(dataset_config_path),
        gee_config_path=_resolve_path(gee_config_path),
    )


def get_dataset_config(
    dataset_id: str,
    dataset_config_path: str | Path = "config/datasets.yaml",
) -> ConfigDict:
    """Load one dataset entry by its configured id."""

    dataset_document = load_dataset_config(dataset_config_path)
    try:
        dataset_config = dataset_document["datasets"][dataset_id]
    except KeyError as exc:
        raise KeyError(f"Unknown dataset id: {dataset_id}") from exc

    if not isinstance(dataset_config, dict):
        raise ValueError(f"Dataset config for {dataset_id} must be a mapping")

    return dataset_config
