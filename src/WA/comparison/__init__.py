"""Comparison helpers for Phase 2 wetland analysis."""

from WA.comparison.focus_areas import (
    DEFAULT_FOCUS_REGION_BBOXES,
    RoughFocusArea,
    select_focus_areas,
)
from WA.comparison.harmonize import (
    BINARY_WETLAND_THRESHOLD,
    BinaryComparisonUnavailableError,
    EmptyBinarySurfaceError,
    create_comparison_grid,
    dataset_supports_binary_comparison,
    harmonize_binary_collection,
    harmonize_binary_dataset,
    select_comparison_slice,
)
from WA.comparison.rough_binary import RoughBinaryResult, compute_rough_binary_metrics

__all__ = [
    "BINARY_WETLAND_THRESHOLD",
    "DEFAULT_FOCUS_REGION_BBOXES",
    "BinaryComparisonUnavailableError",
    "EmptyBinarySurfaceError",
    "RoughBinaryResult",
    "RoughFocusArea",
    "compute_rough_binary_metrics",
    "create_comparison_grid",
    "dataset_supports_binary_comparison",
    "harmonize_binary_collection",
    "harmonize_binary_dataset",
    "select_comparison_slice",
    "select_focus_areas",
]
