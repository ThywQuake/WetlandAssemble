"""Fine-grained classification harmonization helpers for Phase 3."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, cast

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
from rasterio.enums import Resampling
from scipy.stats import mode as scipy_mode

ClassScheme = Literal["4class", "8class"]
CLASSIFICATION_DATASET_IDS = frozenset({"g2017", "glwd_v2", "gwd30"})

FINE_4CLASS_MAPS: dict[str, dict[int, int]] = {
    "g2017": {
        0: 0,
        10: 1,
        20: 2,
        30: 2,
        40: 2,
        50: 2,
        60: 2,
        70: 2,
        80: 2,
        90: 2,
        100: 2,
    },
    "glwd_v2": {
        0: 0,
        1: 1,
        2: 1,
        3: 1,
        4: 1,
        5: 1,
        6: 1,
        7: 1,
        8: 2,
        9: 2,
        10: 2,
        11: 2,
        12: 2,
        13: 2,
        14: 2,
        15: 2,
        16: 2,
        17: 2,
        18: 2,
        19: 2,
        20: 2,
        21: 2,
        22: 2,
        23: 2,
        24: 2,
        25: 2,
        26: 2,
        27: 2,
        28: 2,
        29: 2,
        30: 2,
        31: 2,
        32: 2,
        33: 3,
    },
    "gwd30": {
        0: 0,
        1: 1,
        2: 1,
        3: 1,
        4: 1,
        5: 1,
        6: 1,
        7: 3,
        8: 2,
        9: 2,
        10: 2,
        11: 2,
        12: 2,
        13: 2,
        14: 1,
    },
}

FINE_4CLASS_LABELS = {
    0: "non_wetland",
    1: "open_water",
    2: "wetland",
    3: "artificial_wetland",
}

FINE_8CLASS_MAPS: dict[str, dict[int, int]] = {
    "g2017": {
        0: 0,
        10: 1,
        20: 2,
        30: 4,
        40: 5,
        50: 5,
        60: 6,
        70: 6,
        80: 5,
        90: 5,
        100: 5,
    },
    "glwd_v2": {
        0: 0,
        1: 1,
        2: 1,
        3: 1,
        4: 1,
        5: 1,
        6: 1,
        7: 1,
        8: 4,
        9: 5,
        10: 4,
        11: 5,
        12: 4,
        13: 5,
        14: 4,
        15: 5,
        16: 4,
        17: 5,
        18: 4,
        19: 5,
        20: 4,
        21: 5,
        22: 3,
        23: 3,
        24: 3,
        25: 3,
        26: 3,
        27: 3,
        28: 2,
        29: 7,
        30: 1,
        31: 7,
        32: 7,
        33: 5,
    },
    "gwd30": {
        0: 0,
        1: 1,
        2: 1,
        3: 1,
        4: 1,
        5: 1,
        6: 1,
        7: 1,
        8: 5,
        9: 4,
        10: 6,
        11: 7,
        12: 2,
        13: 7,
        14: 1,
    },
}

FINE_8CLASS_LABELS = {
    0: "Non-wetland",
    1: "Open Water",
    2: "Mangrove",
    3: "Peatland",
    4: "Forested Swamp",
    5: "Marsh",
    6: "Floodplain",
    7: "Coastal Wetland",
}


class FineComparisonUnavailableError(ValueError):
    """Raised when a dataset cannot participate in fine-grained comparison."""


def dataset_supports_fine_comparison(dataset_id: str) -> bool:
    """Return whether a dataset is eligible for fine-grained comparison."""

    return dataset_id in CLASSIFICATION_DATASET_IDS


def harmonize_fine_collection(
    datasets: Mapping[str, xr.Dataset],
    reference_grid: xr.DataArray,
    *,
    class_scheme: ClassScheme = "4class",
) -> dict[str, xr.DataArray]:
    """Harmonize classification datasets to a shared vocabulary and grid."""

    harmonized: dict[str, xr.DataArray] = {}
    for dataset_id, dataset in datasets.items():
        if not dataset_supports_fine_comparison(dataset_id):
            continue
        harmonized[dataset_id] = harmonize_fine_dataset(
            dataset_id,
            dataset,
            reference_grid=reference_grid,
            class_scheme=class_scheme,
        )

    if not harmonized:
        raise FineComparisonUnavailableError("No classification datasets were provided")
    return harmonized


def harmonize_fine_dataset(
    dataset_id: str,
    dataset: xr.Dataset,
    *,
    reference_grid: xr.DataArray,
    class_scheme: ClassScheme = "4class",
) -> xr.DataArray:
    """Harmonize one classification dataset into the requested class scheme."""

    if not dataset_supports_fine_comparison(dataset_id):
        raise FineComparisonUnavailableError(
            f"{dataset_id} is not eligible for fine-grained comparison"
        )

    source, source_variable = _prepare_fine_source(dataset_id, dataset)
    mapped = _map_classification_surface(source, _mapping_for(dataset_id, class_scheme))
    # Lazy import to break circular: comparison → harmonize → loaders → gwd30 → harmonize
    from WA.comparison.harmonize import _align_2d_surface  # noqa: PLC0415

    aligned = _align_2d_surface(mapped, reference_grid, resampling=Resampling.mode)
    if int(aligned.count().item()) == 0:
        raise FineComparisonUnavailableError(
            f"{dataset_id} produced no valid cells after fine-grained alignment"
        )
    aligned.name = "fine_class"
    aligned.attrs.update(
        {
            "dataset_id": dataset_id,
            "comparison_source_variable": source_variable,
            "comparison_class_scheme": class_scheme,
        }
    )
    return aligned.astype(np.float32)


def compute_class_agreement(
    harmonized: Mapping[str, xr.DataArray],
    *,
    num_classes: int,
) -> xr.Dataset:
    """Compute majority-class agreement and per-class frequency surfaces."""

    if not harmonized:
        raise ValueError("harmonized must contain at least one dataset")

    stack = xr.concat(
        [
            data.astype(np.float32).expand_dims(dataset=[dataset_id])
            for dataset_id, data in harmonized.items()
        ],
        dim=pd.Index(list(harmonized), name="dataset"),
    )

    valid_count = stack.notnull().sum(dim="dataset").astype(np.int16)
    class_counts: list[xr.DataArray] = []
    class_distribution: list[xr.DataArray] = []

    for class_id in range(num_classes):
        count = (stack == np.float32(class_id)).sum(dim="dataset").astype(np.int16)
        class_counts.append(count.expand_dims(class_id=[class_id]))
        distribution = xr.where(
            valid_count > 0,
            count.astype(np.float32) / valid_count.astype(np.float32),
            np.nan,
        )
        class_distribution.append(distribution.expand_dims(class_id=[class_id]))

    counts_by_class = xr.concat(class_counts, dim="class_id")
    distribution_by_class = xr.concat(class_distribution, dim="class_id").astype(np.float32)
    majority_class = counts_by_class.argmax(dim="class_id").astype(np.float32)
    majority_class = majority_class.where(valid_count > 0)
    agreement_count = counts_by_class.max(dim="class_id").astype(np.int16)

    result = xr.Dataset(
        {
            "majority_class": majority_class,
            "agreement_count": agreement_count,
            "class_distribution": distribution_by_class,
        }
    )
    result["class_distribution"].attrs["num_classes"] = num_classes
    return result


def _prepare_fine_source(dataset_id: str, dataset: xr.Dataset) -> tuple[xr.DataArray, str]:
    if dataset_id == "g2017":
        if "wetland" in dataset:
            return dataset["wetland"], "wetland"
        if "wetland_nolake" in dataset:
            return dataset["wetland_nolake"], "wetland_nolake"
    elif dataset_id == "glwd_v2" and "combined_classes" in dataset:
        return dataset["combined_classes"], "combined_classes"
    elif dataset_id == "gwd30" and "wetland_class" in dataset:
        source = dataset["wetland_class"]
        if "time" in source.dims:
            source = _temporal_mode(source)
        return source, "wetland_class"

    raise FineComparisonUnavailableError(
        f"Could not derive a classification surface for {dataset_id}"
    )


def _mapping_for(dataset_id: str, class_scheme: ClassScheme) -> Mapping[int, int]:
    if class_scheme == "4class":
        return FINE_4CLASS_MAPS[dataset_id]
    return FINE_8CLASS_MAPS[dataset_id]


def _map_classification_surface(data: xr.DataArray, mapping: Mapping[int, int]) -> xr.DataArray:
    result = xr.full_like(data, np.nan, dtype=np.float32)
    for source_value, class_id in mapping.items():
        result = xr.where(  # type: ignore[no-untyped-call]
            data == source_value,
            np.float32(class_id),
            result,
        )
    return result.where(data.notnull()).astype(np.float32)


def _temporal_mode(data: xr.DataArray) -> xr.DataArray:
    """Collapse a categorical time series to the per-pixel modal class."""

    def mode_1d(values: np.ndarray) -> np.float32:
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            return np.float32(np.nan)
        resolved = scipy_mode(finite, axis=None, nan_policy="omit", keepdims=False).mode
        if isinstance(resolved, np.ndarray):
            if resolved.size == 0:
                return np.float32(np.nan)
            return np.float32(resolved.reshape(-1)[0])
        return np.float32(resolved)

    reduced = xr.apply_ufunc(
        mode_1d,
        data.astype(np.float32),
        input_core_dims=[["time"]],
        output_core_dims=[[]],
        vectorize=True,
        dask="allowed",
        output_dtypes=[np.float32],
    )
    return cast(xr.DataArray, reduced)
