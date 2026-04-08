#!/usr/bin/env python3
"""Generate contract-backed Phase 4 classification artifacts.

This runner stays intentionally thin:
- Phase 3.6 still computes the global disagreement outputs.
- Phase 3.7 still computes the hotspot source trio.
- This CLI only resolves one region / canonical / ten, then rewrites
  region-scoped contract surface, summary, and hotspot artifacts.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.comparison.classification_contract import (  # noqa: E402
    CLASSIFICATION_CONTRACT_DATASET_KEY,
    CLASSIFICATION_PARTICIPANT_SET_KEY,
    ClassificationHotspotReload,
    ClassificationSummaryBundle,
    ClassificationSurfaceBundle,
    Phase37SourcePaths,
    classification_hotspot_manifest_output_path,
    classification_hotspot_table_output_path,
    classification_summary_output_path,
    classification_surface_output_path,
    load_contract_classification_hotspot_table,
    load_contract_classification_summary,
    load_contract_classification_surface,
    phase37_source_paths,
    write_contract_classification_hotspot_outputs,
    write_contract_classification_summary,
    write_contract_classification_surface,
)
from WA.comparison.evidence_contract import (  # noqa: E402
    DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
    DEFAULT_PHASE4_REGIONS_FILE,
    SUPPORTED_PHASE4_REGION_SUBSETS,
    load_phase4_evidence_contract,
)
from WA.comparison.phase36 import (  # noqa: E402
    DEFAULT_PHASE36_CACHE_DIR,
    DEFAULT_PHASE36_LAT_CHUNK_SIZE,
    DEFAULT_PHASE36_OUTPUT_DIR,
    DEFAULT_PHASE36_STANDARDIZED_DIR,
    DEFAULT_PHASE36_TARGET_YEAR,
    Phase36OutputPaths,
    run_phase36_analysis,
)
from WA.phase37_hotspots import (  # noqa: E402
    DEFAULT_PHASE37_HOTSPOT_AOI_SIZE_DEG,
    DEFAULT_PHASE37_HOTSPOT_BUDGET,
    DEFAULT_PHASE37_HOTSPOT_CACHE_DIR,
    DEFAULT_PHASE37_HOTSPOT_MIN_CLUSTER_CELLS,
    DEFAULT_PHASE37_HOTSPOT_MIN_DISTANCE_DEG,
    DEFAULT_PHASE37_HOTSPOT_OUTPUT_DIR,
    DEFAULT_PHASE37_HOTSPOT_PERCENTILE,
    DEFAULT_PHASE37_SAMPLE_STEP,
    DEFAULT_PHASE37_SOURCE_LAT_CHUNK_SIZE,
    Phase37HotspotSelectionResult,
    run_phase37_hotspot_selection,
)

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or reload one contract-backed classification family: "
            "a region-scoped Phase 3.6 disagreement surface, a contract summary, "
            "and a rewritten Phase 3.7 hotspot manifest/CSV pair. Supports one "
            "--region, --subset canonical, or --subset ten."
        )
    )
    parser.add_argument("--regions-file", default=str(DEFAULT_PHASE4_REGIONS_FILE))
    parser.add_argument(
        "--subset",
        choices=SUPPORTED_PHASE4_REGION_SUBSETS,
        default=None,
        help=(
            "Evidence-contract priority-region subset. Use 'canonical' for the "
            "four-region hydro-diverse subset or 'ten' for the full ordered contract "
            "list. Omit --subset to keep the canonical default unless --region is "
            "passed explicitly."
        ),
    )
    parser.add_argument(
        "--region",
        action="append",
        default=[],
        help=(
            "Explicit region id override; may be repeated. Cannot be combined "
            "with --subset."
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_PHASE4_CONTRACT_OUTPUT_ROOT,
        help="Phase 4 contract output root (default: results/phase4).",
    )
    parser.add_argument(
        "--standardized-dir",
        type=Path,
        default=DEFAULT_PHASE36_STANDARDIZED_DIR,
        help=(
            "Standardized dataset root used by Phase 3.6 "
            "(default: output/standardized)."
        ),
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_PHASE36_TARGET_YEAR,
        help="Classification target year for Phase 3.6/3.7 (default: 2016).",
    )
    parser.add_argument(
        "--phase36-output-dir",
        type=Path,
        default=DEFAULT_PHASE36_OUTPUT_DIR,
        help="Phase 3.6 output root (default: results/phase3.6).",
    )
    parser.add_argument(
        "--phase36-cache-dir",
        type=Path,
        default=DEFAULT_PHASE36_CACHE_DIR,
        help="Phase 3.6 cache root (default: results/cache/phase3_6).",
    )
    parser.add_argument(
        "--phase36-lat-chunk-size",
        type=int,
        default=DEFAULT_PHASE36_LAT_CHUNK_SIZE,
        help="Phase 3.6 stripe height (default: 512).",
    )
    parser.add_argument(
        "--phase37-output-dir",
        type=Path,
        default=DEFAULT_PHASE37_HOTSPOT_OUTPUT_DIR,
        help="Phase 3.7 hotspot output root (default: results/phase3.7_hotspots).",
    )
    parser.add_argument(
        "--phase37-cache-dir",
        type=Path,
        default=DEFAULT_PHASE37_HOTSPOT_CACHE_DIR,
        help="Phase 3.7 cache root (default: results/cache/phase3_7).",
    )
    parser.add_argument(
        "--total-hotspot-budget",
        type=int,
        default=DEFAULT_PHASE37_HOTSPOT_BUDGET,
        help="Phase 3.7 total hotspot budget before region rewrite (default: 20).",
    )
    parser.add_argument(
        "--threshold-percentile",
        type=float,
        default=DEFAULT_PHASE37_HOTSPOT_PERCENTILE,
        help="Phase 3.7 hotspot threshold percentile (default: 95).",
    )
    parser.add_argument(
        "--min-cluster-cells",
        type=int,
        default=DEFAULT_PHASE37_HOTSPOT_MIN_CLUSTER_CELLS,
        help="Phase 3.7 minimum candidate cluster cells (default: 16).",
    )
    parser.add_argument(
        "--aoi-size-deg",
        type=float,
        default=DEFAULT_PHASE37_HOTSPOT_AOI_SIZE_DEG,
        help="Phase 3.7 AOI size in degrees (default: 0.5).",
    )
    parser.add_argument(
        "--min-distance-deg",
        type=float,
        default=DEFAULT_PHASE37_HOTSPOT_MIN_DISTANCE_DEG,
        help="Phase 3.7 hotspot center spacing in degrees (default: 0.5).",
    )
    parser.add_argument(
        "--candidate-sample-step",
        type=int,
        default=DEFAULT_PHASE37_SAMPLE_STEP,
        help="Phase 3.7 candidate cache sample step (default: 4).",
    )
    parser.add_argument(
        "--source-lat-chunk-size",
        type=int,
        default=DEFAULT_PHASE37_SOURCE_LAT_CHUNK_SIZE,
        help="Phase 3.7 source lat chunk size (default: 512).",
    )
    parser.add_argument(
        "--write-debug-png",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Write Phase 3.7 debug PNGs when rebuilding the source trio "
            "(default: True)."
        ),
    )
    parser.add_argument(
        "--skip",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Reuse complete Phase 3.6/3.7 and contract outputs when present "
            "(default: True)."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="[%(levelname)s] %(message)s",
    )

    contract = load_phase4_evidence_contract(
        output_root=args.output_root,
        regions_file=args.regions_file,
    )
    contract.output_root.mkdir(parents=True, exist_ok=True)

    try:
        regions = contract.resolve_regions(
            subset=args.subset,
            requested_region_ids=args.region or None,
        )
    except Exception as exc:
        logger.error(
            "stage=region-selector subset=%s requested_regions=%s "
            "participant_set_key=%s error=%s",
            args.subset or "<none>",
            args.region,
            CLASSIFICATION_PARTICIPANT_SET_KEY,
            exc,
        )
        raise

    selector_subset = args.subset or (
        "explicit-region-list" if args.region else "canonical"
    )
    logger.info(
        "stage=region-selector subset=%s participant_set_key=%s "
        "dataset_key=%s region_ids=%s",
        selector_subset,
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        CLASSIFICATION_CONTRACT_DATASET_KEY,
        [region.region_id for region in regions],
    )

    phase36_outputs = _materialize_phase36_sources(args)
    phase37_sources = _materialize_phase37_sources(
        args,
        phase36_outputs=phase36_outputs,
        region_ids=[region.region_id for region in regions],
    )

    for region in regions:
        logger.info(
            "stage=classification region=%s participant_set_key=%s "
            "dataset_key=%s bbox=%s action=start",
            region.region_id,
            CLASSIFICATION_PARTICIPANT_SET_KEY,
            CLASSIFICATION_CONTRACT_DATASET_KEY,
            region.bbox,
        )
        surface_bundle = _materialize_classification_surface(
            contract=contract,
            region=region,
            year=args.year,
            phase36_outputs=phase36_outputs,
            skip=args.skip,
        )
        summary_bundle = _materialize_classification_summary(
            contract=contract,
            region=region,
            year=args.year,
            phase37_sources=phase37_sources,
            skip=args.skip,
        )
        hotspot_bundle = _materialize_classification_hotspots(
            contract=contract,
            region_id=region.region_id,
            phase37_sources=phase37_sources,
            skip=args.skip,
        )
        logger.info(
            "stage=classification region=%s participant_set_key=%s "
            "dataset_key=%s action=ready surface=%s summary=%s hotspots=%s",
            region.region_id,
            CLASSIFICATION_PARTICIPANT_SET_KEY,
            CLASSIFICATION_CONTRACT_DATASET_KEY,
            surface_bundle.surface_path,
            summary_bundle.summary_path,
            hotspot_bundle.manifest.manifest_path,
        )

    logger.info(
        "Phase4 classification contract complete: subset=%s dataset_key=%s regions=%s",
        selector_subset,
        CLASSIFICATION_CONTRACT_DATASET_KEY,
        [region.region_id for region in regions],
    )
    return 0


def _materialize_phase36_sources(args: argparse.Namespace) -> Phase36OutputPaths:
    logger.info(
        "stage=phase36 participant_set_key=%s action=ensure year=%s "
        "output_dir=%s cache_dir=%s skip=%s",
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        args.year,
        args.phase36_output_dir,
        args.phase36_cache_dir,
        args.skip,
    )
    outputs = run_phase36_analysis(
        standardized_dir=args.standardized_dir,
        output_dir=args.phase36_output_dir,
        cache_dir=args.phase36_cache_dir,
        year=args.year,
        lat_chunk_size=args.phase36_lat_chunk_size,
        prefer_cache=args.skip,
        write_cache=True,
    )
    logger.info(
        "stage=phase36 participant_set_key=%s action=ready metrics=%s "
        "dominant=%s summary=%s",
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        outputs.metrics_path,
        outputs.dominant_classes_path,
        outputs.summary_path,
    )
    return outputs


def _materialize_phase37_sources(
    args: argparse.Namespace,
    *,
    phase36_outputs: Phase36OutputPaths,
    region_ids: list[str],
) -> Phase37SourcePaths:
    paths = phase37_source_paths(output_dir=args.phase37_output_dir, year=args.year)
    if args.skip and _phase37_trio_complete(paths):
        logger.info(
            "stage=phase37 participant_set_key=%s action=reload "
            "manifest=%s table=%s region_table=%s",
            CLASSIFICATION_PARTICIPANT_SET_KEY,
            paths.manifest_path,
            paths.hotspot_csv_path,
            paths.region_csv_path,
        )
        return paths
    if args.skip:
        _require_complete_phase37_trio(paths)

    logger.info(
        "stage=phase37 participant_set_key=%s action=write metrics=%s "
        "dominant=%s manifest=%s table=%s region_table=%s",
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        phase36_outputs.metrics_path,
        phase36_outputs.dominant_classes_path,
        paths.manifest_path,
        paths.hotspot_csv_path,
        paths.region_csv_path,
    )
    result = run_phase37_hotspot_selection(
        phase36_outputs.metrics_path,
        phase36_outputs.dominant_classes_path,
        output_dir=args.phase37_output_dir,
        regions_file=args.regions_file,
        cache_dir=args.phase37_cache_dir,
        selected_region_ids=region_ids,
        year=args.year,
        total_budget=max(args.total_hotspot_budget, len(region_ids)),
        threshold_percentile=args.threshold_percentile,
        min_cluster_cells=args.min_cluster_cells,
        aoi_size_deg=args.aoi_size_deg,
        min_distance_deg=args.min_distance_deg,
        candidate_sample_step=args.candidate_sample_step,
        source_lat_chunk_size=args.source_lat_chunk_size,
        write_debug_png=args.write_debug_png,
    )
    return _phase37_paths_from_result(result)


def _materialize_classification_surface(
    *,
    contract,
    region,
    year: int,
    phase36_outputs: Phase36OutputPaths,
    skip: bool,
) -> ClassificationSurfaceBundle:
    surface_path = classification_surface_output_path(
        contract,
        region_id=region.region_id,
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
    )
    if skip and surface_path.is_file():
        logger.info(
            "stage=classification_reload region=%s participant_set_key=%s "
            "dataset_key=%s action=surface-reload path=%s",
            region.region_id,
            CLASSIFICATION_PARTICIPANT_SET_KEY,
            CLASSIFICATION_CONTRACT_DATASET_KEY,
            surface_path,
        )
        return load_contract_classification_surface(
            contract=contract,
            region_id=region.region_id,
            dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        )

    logger.info(
        "stage=classification_contract_write region=%s participant_set_key=%s "
        "dataset_key=%s action=surface-write path=%s",
        region.region_id,
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        CLASSIFICATION_CONTRACT_DATASET_KEY,
        surface_path,
    )
    return write_contract_classification_surface(
        contract=contract,
        region_id=region.region_id,
        region_label=region.label,
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        bbox=region.bbox,
        target_year=year,
        metrics_path=phase36_outputs.metrics_path,
        dominant_classes_path=phase36_outputs.dominant_classes_path,
    )


def _materialize_classification_summary(
    *,
    contract,
    region,
    year: int,
    phase37_sources: Phase37SourcePaths,
    skip: bool,
) -> ClassificationSummaryBundle:
    summary_path = classification_summary_output_path(
        contract,
        region_id=region.region_id,
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
    )
    if skip and summary_path.is_file():
        logger.info(
            "stage=classification_reload region=%s participant_set_key=%s "
            "dataset_key=%s action=summary-reload path=%s",
            region.region_id,
            CLASSIFICATION_PARTICIPANT_SET_KEY,
            CLASSIFICATION_CONTRACT_DATASET_KEY,
            summary_path,
        )
        return load_contract_classification_summary(
            contract=contract,
            region_id=region.region_id,
            dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        )

    logger.info(
        "stage=classification_contract_write region=%s participant_set_key=%s "
        "dataset_key=%s action=summary-write path=%s",
        region.region_id,
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        CLASSIFICATION_CONTRACT_DATASET_KEY,
        summary_path,
    )
    return write_contract_classification_summary(
        contract=contract,
        region_id=region.region_id,
        region_label=region.label,
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        target_year=year,
        source_region_summary_path=phase37_sources.region_csv_path,
    )


def _materialize_classification_hotspots(
    *,
    contract,
    region_id: str,
    phase37_sources: Phase37SourcePaths,
    skip: bool,
) -> ClassificationHotspotReload:
    manifest_path = classification_hotspot_manifest_output_path(
        contract,
        region_id=region_id,
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
    )
    table_path = classification_hotspot_table_output_path(
        contract,
        region_id=region_id,
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
    )
    if skip and (manifest_path.exists() or table_path.exists()):
        _require_complete_pair(
            label="classification-hotspots",
            region_id=region_id,
            left_path=manifest_path,
            right_path=table_path,
        )
        logger.info(
            "stage=classification_reload region=%s participant_set_key=%s "
            "dataset_key=%s action=hotspots-reload manifest=%s table=%s",
            region_id,
            CLASSIFICATION_PARTICIPANT_SET_KEY,
            CLASSIFICATION_CONTRACT_DATASET_KEY,
            manifest_path,
            table_path,
        )
        return load_contract_classification_hotspot_table(
            contract=contract,
            region_id=region_id,
            dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        )

    logger.info(
        "stage=classification_contract_write region=%s participant_set_key=%s "
        "dataset_key=%s action=hotspots-write manifest=%s table=%s",
        region_id,
        CLASSIFICATION_PARTICIPANT_SET_KEY,
        CLASSIFICATION_CONTRACT_DATASET_KEY,
        manifest_path,
        table_path,
    )
    write_contract_classification_hotspot_outputs(
        contract=contract,
        region_id=region_id,
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
        source_manifest_path=phase37_sources.manifest_path,
        source_hotspot_table_path=phase37_sources.hotspot_csv_path,
        source_region_summary_path=phase37_sources.region_csv_path,
    )
    return load_contract_classification_hotspot_table(
        contract=contract,
        region_id=region_id,
        dataset_key=CLASSIFICATION_CONTRACT_DATASET_KEY,
    )


def _phase37_trio_complete(paths: Phase37SourcePaths) -> bool:
    return (
        paths.manifest_path.is_file()
        and paths.hotspot_csv_path.is_file()
        and paths.region_csv_path.is_file()
    )


def _require_complete_phase37_trio(paths: Phase37SourcePaths) -> None:
    exists = {
        "manifest": paths.manifest_path.is_file(),
        "hotspot_csv": paths.hotspot_csv_path.is_file(),
        "region_csv": paths.region_csv_path.is_file(),
    }
    if all(exists.values()) or not any(exists.values()):
        return
    raise FileNotFoundError(
        "stage=phase37 participant_set_key="
        f"{CLASSIFICATION_PARTICIPANT_SET_KEY} found partial source trio: "
        f"manifest={paths.manifest_path} exists={exists['manifest']} "
        f"hotspot_csv={paths.hotspot_csv_path} exists={exists['hotspot_csv']} "
        f"region_csv={paths.region_csv_path} exists={exists['region_csv']}"
    )


def _phase37_paths_from_result(
    result: Phase37HotspotSelectionResult,
) -> Phase37SourcePaths:
    return Phase37SourcePaths(
        manifest_path=result.manifest_path,
        hotspot_csv_path=result.csv_path,
        region_csv_path=result.region_csv_path,
    )


def _require_complete_pair(
    *,
    label: str,
    region_id: str,
    left_path: Path,
    right_path: Path,
) -> None:
    left_exists = left_path.is_file()
    right_exists = right_path.is_file()
    if left_exists and right_exists:
        return
    if left_exists or right_exists:
        raise FileNotFoundError(
            f"stage={label} region={region_id} participant_set_key="
            f"{CLASSIFICATION_PARTICIPANT_SET_KEY} found partial artifact pair: "
            f"{left_path} exists={left_exists} {right_path} exists={right_exists}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
