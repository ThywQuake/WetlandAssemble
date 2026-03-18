"""Registry for dataset loader implementations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from WA.loaders.base import DatasetLoader

LoaderFactory = type[DatasetLoader]
LOADER_REGISTRY: dict[str, LoaderFactory] = {}
OUT_OF_SCOPE_DATASET_IDS = {"lstm_wetland"}


class UnsupportedDatasetError(ValueError):
    """Raised when a dataset exists in config but is not part of the implementation scope."""


def register_loader(loader_type: str) -> Callable[[LoaderFactory], LoaderFactory]:
    """Register a dataset loader by its configured loader type."""

    def decorator(loader_class: LoaderFactory) -> LoaderFactory:
        LOADER_REGISTRY[loader_type] = loader_class
        return loader_class

    return decorator


def get_loader(dataset_id: str, dataset_config: Mapping[str, Any]) -> DatasetLoader:
    """Instantiate the loader configured for one dataset id."""

    if dataset_id in OUT_OF_SCOPE_DATASET_IDS:
        raise UnsupportedDatasetError(
            f"{dataset_id} is explicitly out of scope until its documentation exists."
        )

    loader_type = str(dataset_config["loader_type"])
    try:
        loader_class = LOADER_REGISTRY[loader_type]
    except KeyError as exc:
        known_types = ", ".join(sorted(LOADER_REGISTRY))
        raise UnsupportedDatasetError(
            f"Unknown loader_type {loader_type!r}. Registered loader types: {known_types}"
        ) from exc

    return loader_class(dataset_id, dataset_config)


def list_loader_types() -> tuple[str, ...]:
    """Return the currently registered loader types."""

    return tuple(sorted(LOADER_REGISTRY))
