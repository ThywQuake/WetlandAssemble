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
    REPRESENTATIVE_WETLAND_SITES,
    EntropyHotspot,
    compute_shannon_entropy,
    extract_hotspots,
    get_representative_sites,
)
from WA.comparison.rough_binary import RoughBinaryResult, compute_rough_binary_metrics
from WA.comparison.trend_agreement import (
    TrendAgreementResult,
    compute_overlap_window,
    compute_trend_agreement,
)
from WA.comparison.trends import (
    AggregationLevel,
    TrendResult,
    compute_pixel_trends,
    compute_regional_summary,
    compute_year_over_year_change,
)

__all__ = [
    "BINARY_WETLAND_THRESHOLD",
    "CLASSIFICATION_DATASET_IDS",
    "DEFAULT_FOCUS_REGION_BBOXES",
    "AggregationLevel",
    "BinaryComparisonUnavailableError",
    "EmptyBinarySurfaceError",
    "FINE_4CLASS_LABELS",
    "FINE_4CLASS_MAPS",
    "FINE_8CLASS_LABELS",
    "FINE_8CLASS_MAPS",
    "EntropyHotspot",
    "REPRESENTATIVE_WETLAND_SITES",
    "FineComparisonUnavailableError",
    "RoughBinaryResult",
    "RoughFocusArea",
    "TrendAgreementResult",
    "TrendResult",
    "compute_class_agreement",
    "compute_overlap_window",
    "compute_pixel_trends",
    "compute_regional_summary",
    "compute_rough_binary_metrics",
    "compute_shannon_entropy",
    "compute_trend_agreement",
    "compute_year_over_year_change",
    "create_comparison_grid",
    "dataset_supports_binary_comparison",
    "dataset_supports_fine_comparison",
    "extract_hotspots",
    "get_representative_sites",
    "harmonize_binary_collection",
    "harmonize_binary_dataset",
    "harmonize_fine_collection",
    "harmonize_fine_dataset",
    "select_comparison_slice",
    "select_focus_areas",
]
