"""Comparison helpers for Phase 2 and Phase 3 wetland analysis."""

from WA.comparison.fine_grained import (
    CLASSIFICATION_DATASET_IDS,
    FINE_4CLASS_LABELS,
    FINE_4CLASS_MAPS,
    FINE_8CLASS_LABELS,
    FINE_8CLASS_MAPS,
    FineComparisonUnavailableError,
    compute_class_agreement,
    dataset_supports_fine_comparison,
    harmonize_fine_collection,
    harmonize_fine_dataset,
)
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
from WA.comparison.hotspots import (
    EntropyHotspot,
    compute_shannon_entropy,
    extract_hotspots,
)
from WA.comparison.rough_binary import RoughBinaryResult, compute_rough_binary_metrics

__all__ = [
    "BINARY_WETLAND_THRESHOLD",
    "CLASSIFICATION_DATASET_IDS",
    "DEFAULT_FOCUS_REGION_BBOXES",
    "BinaryComparisonUnavailableError",
    "EmptyBinarySurfaceError",
    "FINE_4CLASS_LABELS",
    "FINE_4CLASS_MAPS",
    "FINE_8CLASS_LABELS",
    "FINE_8CLASS_MAPS",
    "EntropyHotspot",
    "FineComparisonUnavailableError",
    "RoughBinaryResult",
    "RoughFocusArea",
    "compute_class_agreement",
    "compute_rough_binary_metrics",
    "compute_shannon_entropy",
    "create_comparison_grid",
    "dataset_supports_binary_comparison",
    "dataset_supports_fine_comparison",
    "extract_hotspots",
    "harmonize_binary_collection",
    "harmonize_binary_dataset",
    "harmonize_fine_collection",
    "harmonize_fine_dataset",
    "select_comparison_slice",
    "select_focus_areas",
]
