"""Helpers for dataset classification crosswalks defined in YAML."""

from __future__ import annotations

from functools import cache, lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr
import yaml

DEFAULT_CLASSIFICATION_PATH = Path("config/classification_mappings.yaml")
_DATASET_KEY_ALIASES = {
    "g2017": "G2017",
    "glwd_v2": "GLWD_v2",
    "gwd30": "GWD30",
}
NON_WETLAND_UNIFIED_ID = 0
WATER_UNIFIED_ID = 1


def normalize_classification_dataset_id(dataset_id: str) -> str:
    """Normalize dataset ids used by classification consumers."""

    parts = dataset_id.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0].lower()
    return dataset_id.lower()


@lru_cache(maxsize=1)
def _classification_document() -> dict[str, Any]:
    with DEFAULT_CLASSIFICATION_PATH.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    if not isinstance(document, dict):
        raise ValueError("classification_mappings.yaml must contain a mapping document")
    return document


@cache
def class_to_unified_id(dataset_id: str) -> dict[int, int]:
    """Return one dataset's source-class -> unified-class-id mapping."""

    normalized_id = normalize_classification_dataset_id(dataset_id)
    try:
        dataset_key = _DATASET_KEY_ALIASES[normalized_id]
    except KeyError as exc:
        raise KeyError(f"No classification mapping configured for {dataset_id!r}") from exc

    datasets = _classification_document()["classification_config"]["datasets"]
    classes = datasets[dataset_key]["classes"]
    mapping = {
        int(source_class): int(definition["unified_id"])
        for source_class, definition in classes.items()
    }
    if normalized_id == "g2017":
        mapping.setdefault(0, NON_WETLAND_UNIFIED_ID)
    return mapping


@cache
def source_class_names(dataset_id: str) -> dict[int, str]:
    """Return one dataset's source-class-id -> original class-name mapping."""

    normalized_id = normalize_classification_dataset_id(dataset_id)
    try:
        dataset_key = _DATASET_KEY_ALIASES[normalized_id]
    except KeyError as exc:
        raise KeyError(f"No classification mapping configured for {dataset_id!r}") from exc

    datasets = _classification_document()["classification_config"]["datasets"]
    classes = datasets[dataset_key]["classes"]
    return {
        int(source_class): str(definition["original_name"])
        for source_class, definition in classes.items()
    }


@cache
def source_class_ids(dataset_id: str) -> tuple[int, ...]:
    """Return source class ids in ascending numeric order."""

    return tuple(sorted(source_class_names(dataset_id)))


@cache
def dataset_display_name(dataset_id: str) -> str:
    """Return the human-readable dataset name from the classification YAML."""

    normalized_id = normalize_classification_dataset_id(dataset_id)
    try:
        dataset_key = _DATASET_KEY_ALIASES[normalized_id]
    except KeyError as exc:
        raise KeyError(f"No classification mapping configured for {dataset_id!r}") from exc

    datasets = _classification_document()["classification_config"]["datasets"]
    return str(datasets[dataset_key]["dataset_name"])


@lru_cache(maxsize=1)
def unified_class_names() -> dict[int, str]:
    """Return the unified class-id -> class-name mapping from YAML."""

    classes = _classification_document()["classification_config"]["unified_classes"]
    return {
        int(definition["id"]): str(definition["name"])
        for definition in classes
    }


@lru_cache(maxsize=1)
def unified_class_ids() -> tuple[int, ...]:
    """Return unified class ids in ascending numeric order."""

    return tuple(sorted(unified_class_names()))


@cache
def source_class_ids_by_unified_id(dataset_id: str) -> dict[int, tuple[int, ...]]:
    """Return one dataset's grouped source-class ids for each unified class id."""

    grouped: dict[int, list[int]] = {}
    for source_class_id, unified_id in class_to_unified_id(dataset_id).items():
        grouped.setdefault(int(unified_id), []).append(int(source_class_id))
    return {
        unified_id: tuple(sorted(source_class_ids))
        for unified_id, source_class_ids in grouped.items()
    }


@lru_cache(maxsize=1)
def unified_priority_order() -> tuple[int, ...]:
    """Return unified class ids in YAML priority order for tie-breaking."""

    document = _classification_document()["classification_config"]
    names_by_id = unified_class_names()
    id_by_name = {name: class_id for class_id, name in names_by_id.items()}
    ordered_names = document["priority_rules"]["order"]
    return tuple(int(id_by_name[str(name)]) for name in ordered_names)


def water_class_ids(dataset_id: str) -> tuple[int, ...]:
    """Return source classes that map to Water."""

    mapping = class_to_unified_id(dataset_id)
    return tuple(
        sorted(
            class_id
            for class_id, unified_id in mapping.items()
            if unified_id == WATER_UNIFIED_ID
        )
    )


def wetland_class_ids(
    dataset_id: str,
    *,
    include_water: bool = False,
) -> tuple[int, ...]:
    """Return source classes counted as wetland-like for area/fraction summaries."""

    mapping = class_to_unified_id(dataset_id)
    excluded_ids = {NON_WETLAND_UNIFIED_ID}
    if not include_water:
        excluded_ids.add(WATER_UNIFIED_ID)
    return tuple(
        sorted(
            class_id
            for class_id, unified_id in mapping.items()
            if unified_id not in excluded_ids
        )
    )


def binary_class_mapping(
    dataset_id: str,
    *,
    include_water: bool = False,
) -> dict[int, float]:
    """Build a 0/1 mapping from source classes into wetland fraction."""

    allowed = set(wetland_class_ids(dataset_id, include_water=include_water))
    return {
        class_id: 1.0 if class_id in allowed else 0.0
        for class_id in class_to_unified_id(dataset_id)
    }


def has_fraction_variables(dataset: xr.Dataset) -> bool:
    """Return whether a dataset contains standardized class fraction variables."""

    return any(name.startswith("frac_") for name in dataset.data_vars)


def wetland_fraction_from_standardized_classes(
    dataset_id: str,
    dataset: xr.Dataset,
    *,
    include_water: bool = False,
) -> xr.DataArray | None:
    """Sum class fraction variables into one wetland-fraction surface.

    For known classification datasets this follows the YAML mapping exactly.
    For unknown datasets it falls back to summing every ``frac_*`` variable
    except ``frac_0``.
    """

    fraction_names = _wetland_fraction_variable_names(
        dataset_id,
        dataset,
        include_water=include_water,
    )
    if not fraction_names:
        return None

    total: xr.DataArray | None = None
    for variable_name in fraction_names:
        variable = dataset[variable_name]
        total = variable if total is None else total + variable

    if total is None:
        return None
    return total.clip(min=0.0, max=1.0).astype(np.float32)


def _wetland_fraction_variable_names(
    dataset_id: str,
    dataset: xr.Dataset,
    *,
    include_water: bool,
) -> tuple[str, ...]:
    normalized_id = normalize_classification_dataset_id(dataset_id)
    try:
        class_ids = wetland_class_ids(normalized_id, include_water=include_water)
        names = tuple(
            variable_name
            for class_id in class_ids
            if (variable_name := f"frac_{class_id}") in dataset.data_vars
        )
        if names:
            return names
    except KeyError:
        pass

    return tuple(
        name
        for name in sorted(dataset.data_vars)
        if name.startswith("frac_") and name != "frac_0"
    )
