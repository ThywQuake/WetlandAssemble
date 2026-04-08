"""Test category catalog and changed-path to pytest selection helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class TestCategory:
    """One curated test family for targeted verification."""

    key: str
    description: str
    tests: tuple[str, ...]
    triggers: tuple[str, ...]


TEST_CATEGORIES: tuple[TestCategory, ...] = (
    TestCategory(
        key="core_infra",
        description="Core config, classification, runtime bootstrap, and shared utility tests.",
        tests=(
            "tests/test_classification.py",
            "tests/test_config.py",
            "tests/test_geo_env.py",
            "tests/test_mgrs_tiling.py",
            "tests/test_progress.py",
        ),
        triggers=(
            "src/WA/classification.py",
            "src/WA/config.py",
            "src/WA/_geo_env.py",
            "src/WA/utils/progress.py",
            "config/",
        ),
    ),
    TestCategory(
        key="loaders",
        description="Dataset loader, standardized loader, and loader probe surfaces.",
        tests=(
            "tests/test_loader_probe.py",
            "tests/test_standardized_loader.py",
            "tests/test_loaders/test_base.py",
            "tests/test_loaders/test_berkeley.py",
            "tests/test_loaders/test_g2017.py",
            "tests/test_loaders/test_glwd.py",
            "tests/test_loaders/test_gwd30.py",
            "tests/test_loaders/test_netcdf_generic.py",
            "tests/test_loaders/test_registry.py",
            "tests/test_loaders/test_standardized_netcdf.py",
            "tests/test_loaders/test_swamps.py",
            "tests/test_loaders/test_topmodel.py",
        ),
        triggers=(
            "src/WA/loaders/",
            "src/WA/loader_probe.py",
            "src/WA/standardized_loader.py",
        ),
    ),
    TestCategory(
        key="standardization_and_gwd30_io",
        description="Standardization, GWD30 staging/audit, and rsync/download helper tests.",
        tests=(
            "tests/test_standardize.py",
            "tests/test_submit_standardize.py",
            "tests/test_check_gwd30_sizes_from_manifest.py",
            "tests/test_check_gwd30_tiffs.py",
            "tests/test_download_gwd30_local_then_rsync.py",
            "tests/test_fetch_gwd30_remote_sizes.py",
            "tests/test_redownload_obs_api.py",
            "tests/test_submit_gwd30_sharded.py",
        ),
        triggers=(
            "src/WA/standardize.py",
            "scripts/check_gwd30_sizes_from_manifest.py",
            "scripts/check_gwd30_tiffs.py",
            "scripts/download_gwd30_local_then_rsync.py",
            "scripts/fetch_gwd30_remote_sizes.py",
            "scripts/redownload_obs_api.py",
            "scripts/submit_standardize.sh",
            "scripts/submit_gwd30_sharded.sh",
            "scripts/run_gwd30_stage_shard.py",
        ),
    ),
    TestCategory(
        key="phase2_rough",
        description="Phase 2 rough binary comparison, probe, and failure-inspection tests.",
        tests=(
            "tests/test_rough_batch.py",
            "tests/test_rough_probe.py",
            "tests/test_hpc_probe_rough_binary_script.py",
            "tests/test_inspect_phase2_rough_failures_script.py",
            "tests/test_comparison/test_harmonize.py",
            "tests/test_comparison/test_rough_binary.py",
        ),
        triggers=(
            "src/WA/rough_batch.py",
            "src/WA/rough_probe.py",
            "src/WA/comparison/harmonize.py",
            "src/WA/comparison/rough_binary.py",
            "scripts/hpc_probe_rough_binary.py",
            "scripts/inspect_phase2_rough_failures.py",
        ),
    ),
    TestCategory(
        key="phase2_reference_downloads",
        description="MODIS/Landsat download and review-manifest tests.",
        tests=(
            "tests/test_modis_batch.py",
            "tests/test_landsat_batch.py",
            "tests/test_landsat_review_manifest.py",
            "tests/test_validation/test_modis_reference.py",
            "tests/test_validation/test_landsat_reference.py",
        ),
        triggers=(
            "src/WA/modis_batch.py",
            "src/WA/landsat_batch.py",
            "src/WA/landsat_review_manifest.py",
            "src/WA/validation/modis_reference.py",
            "src/WA/validation/landsat_reference.py",
        ),
    ),
    TestCategory(
        key="phase2_6",
        description="Phase 2.6 metrics, imagery, plotting, and regional-panel tests.",
        tests=(
            "tests/test_phase2_6_analysis.py",
            "tests/test_phase2_6_plotting.py",
            "tests/test_phase2_6_region_imagery.py",
            "tests/test_phase2_6_regional_panels.py",
        ),
        triggers=(
            "src/WA/comparison/phase26.py",
            "src/WA/phase26_region_imagery.py",
            "src/WA/visualization/phase26.py",
            "scripts/run_phase2_6_analysis.py",
            "scripts/plot_phase2_6_metrics.py",
            "scripts/plot_phase2_6_regional_panels.py",
            "scripts/download_phase2_6_region_imagery.py",
        ),
    ),
    TestCategory(
        key="phase3_core",
        description="Fine-grained comparison, hotspot logic, and S2 validation tests.",
        tests=(
            "tests/test_s2_batch.py",
            "tests/test_comparison/test_fine_grained.py",
            "tests/test_comparison/test_focus_areas.py",
            "tests/test_comparison/test_hotspots.py",
            "tests/test_validation/test_s2_reference.py",
        ),
        triggers=(
            "src/WA/s2_batch.py",
            "src/WA/comparison/fine_grained.py",
            "src/WA/comparison/focus_areas.py",
            "src/WA/comparison/hotspots.py",
            "src/WA/validation/s2_reference.py",
        ),
    ),
    TestCategory(
        key="phase3_6",
        description="Phase 3.6 disagreement analysis and 3.6.1 trace diagnostics tests.",
        tests=(
            "tests/test_phase3_6_analysis.py",
            "tests/test_phase3_6_1_gwd30_trace.py",
        ),
        triggers=(
            "src/WA/comparison/phase36.py",
            "src/WA/phase361_gwd30_trace.py",
            "scripts/inspect_phase3_6_1_gwd30_hotspots.py",
            "scripts/list_phase3_6_1_gwd30_hotspot_files.py",
        ),
    ),
    TestCategory(
        key="phase3_7",
        description="Phase 3.7 hotspot selection, plotting, and regional panel tests.",
        tests=(
            "tests/test_phase3_7_hotspots.py",
            "tests/test_phase3_7_plotting.py",
            "tests/test_phase3_7_hotspot_panels.py",
            "tests/test_phase3_7_regional_panels.py",
        ),
        triggers=(
            "src/WA/phase37_hotspots.py",
            "src/WA/visualization/phase37.py",
            "scripts/find_phase3_7_hotspots.py",
            "scripts/plot_phase3_7_hotspot_panels.py",
            "scripts/plot_phase3_7_metrics.py",
            "scripts/plot_phase3_7_regional_panels.py",
            "scripts/run_phase3_7_s2_downloads.py",
        ),
    ),
    TestCategory(
        key="phase4",
        description=(
            "Phase 4 contract, regional analysis, trend, readiness, ledger, and "
            "submit-script tests."
        ),
        tests=(
            "tests/test_comparison/test_classification_contract.py",
            "tests/test_comparison/test_evidence_contract.py",
            "tests/test_comparison/test_hotspot_ledger.py",
            "tests/test_comparison/test_percentage_backbone.py",
            "tests/test_comparison/test_percentage_hotspots.py",
            "tests/test_comparison/test_phase4_regional.py",
            "tests/test_comparison/test_scaleout_readiness.py",
            "tests/test_comparison/test_trend_agreement.py",
            "tests/test_comparison/test_trend_contract.py",
            "tests/test_comparison/test_trend_hotspots.py",
            "tests/test_comparison/test_trends.py",
            "tests/test_visualization/test_phase4.py",
            "tests/test_submit_phase4_gwd30_pixel_stats.py",
            "tests/test_submit_phase4_gwd30_regional_year_split.py",
            "tests/test_submit_phase4_gwd30_tropical_shards.py",
            "tests/test_submit_phase4_trend_contract.py",
        ),
        triggers=(
            "src/WA/comparison/classification_contract.py",
            "src/WA/comparison/evidence_contract.py",
            "src/WA/comparison/hotspot_ledger.py",
            "src/WA/comparison/percentage_backbone.py",
            "src/WA/comparison/percentage_hotspots.py",
            "src/WA/comparison/phase4_regional.py",
            "src/WA/comparison/scaleout_readiness.py",
            "src/WA/comparison/trend_agreement.py",
            "src/WA/comparison/trend_contract.py",
            "src/WA/comparison/trend_hotspots.py",
            "src/WA/comparison/trends.py",
            "src/WA/visualization/phase4.py",
            "scripts/build_phase4_gwd30_pixel_stats.py",
            "scripts/build_phase4_gwd30_shard_lists.py",
            "scripts/hpc_probe_trends.py",
            "scripts/reduce_phase4_gwd30_tropical_shards.py",
            "scripts/run_phase4_classification_contract.py",
            "scripts/run_phase4_gwd30_tropical_shard.py",
            "scripts/run_phase4_hotspot_ledger.py",
            "scripts/run_phase4_percentage_contract.py",
            "scripts/run_phase4_regional.py",
            "scripts/run_phase4_scaleout_readiness.py",
            "scripts/run_phase4_trend_contract.py",
            "scripts/submit_phase4_gwd30_pixel_stats.sh",
            "scripts/submit_phase4_gwd30_regional_year_split.sh",
            "scripts/submit_phase4_gwd30_tropical_shards.sh",
            "scripts/submit_phase4_trend_contract.sh",
        ),
    ),
    TestCategory(
        key="visualization_misc",
        description="Shared visualization primitives and standalone plotting script tests.",
        tests=(
            "tests/test_visualization/test_coarse_scale.py",
            "tests/test_visualization/test_comparison_panel.py",
            "tests/test_visualization/test_panel.py",
            "tests/test_plot_priority_regions_world.py",
            "tests/test_plot_tropical_wetland_025deg.py",
        ),
        triggers=(
            "src/WA/visualization/coarse_scale.py",
            "src/WA/visualization/comparison_panel.py",
            "src/WA/visualization/panel.py",
            "scripts/plot_coarse_scale.py",
            "scripts/plot_comparison_panels.py",
            "scripts/plot_global.py",
            "scripts/plot_global_v2.py",
            "scripts/plot_phase3_panels.py",
            "scripts/plot_priority_regions_world.py",
            "scripts/plot_tropical_wetland_025deg.py",
        ),
    ),
    TestCategory(
        key="gee_validation",
        description=(
            "GEE wrapper and reference-integration tests guarded by the existing "
            "gee marker."
        ),
        tests=(
            "tests/test_validation/test_gee_client.py",
            "tests/test_validation/test_landsat_reference.py",
            "tests/test_validation/test_modis_reference.py",
            "tests/test_validation/test_s2_reference.py",
        ),
        triggers=(
            "src/WA/validation/gee_client.py",
            "src/WA/validation/landsat_reference.py",
            "src/WA/validation/modis_reference.py",
            "src/WA/validation/s2_reference.py",
        ),
    ),
)


def iter_test_categories() -> tuple[TestCategory, ...]:
    """Return the curated test catalog."""

    return TEST_CATEGORIES


def normalize_repo_path(path: str) -> str:
    """Normalize one repository-relative path for trigger matching."""

    return path.strip().replace("\\", "/").removeprefix("./")


def category_keys_for_path(path: str) -> list[str]:
    """Return the matching category keys for one changed path."""

    normalized = normalize_repo_path(path)
    matched: list[str] = []
    for category in TEST_CATEGORIES:
        if any(
            normalized == trigger or normalized.startswith(trigger)
            for trigger in category.triggers
        ):
            matched.append(category.key)
    return matched


def categories_for_paths(paths: Iterable[str]) -> list[TestCategory]:
    """Return matching categories for a set of changed paths."""

    seen: set[str] = set()
    matched: list[TestCategory] = []
    for path in paths:
        for category in TEST_CATEGORIES:
            if category.key in seen:
                continue
            normalized = normalize_repo_path(path)
            if any(
                normalized == trigger or normalized.startswith(trigger)
                for trigger in category.triggers
            ):
                matched.append(category)
                seen.add(category.key)
    return matched


def infer_related_tests(paths: Iterable[str]) -> list[str]:
    """Infer a de-duplicated pytest target list for the provided paths."""

    selected: list[str] = []
    seen: set[str] = set()
    normalized_paths = [normalize_repo_path(path) for path in paths]

    for path in normalized_paths:
        if path.startswith("tests/") and path.endswith(".py") and path not in seen:
            selected.append(path)
            seen.add(path)

    for category in categories_for_paths(normalized_paths):
        for test_path in category.tests:
            if test_path in seen:
                continue
            selected.append(test_path)
            seen.add(test_path)

    return selected
