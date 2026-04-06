#!/usr/bin/env python3
# ruff: noqa: E402
"""Find Phase 3.7 entropy hotspots inside priority regions."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from WA.phase37_hotspots import (  # noqa: E402
    DEFAULT_PHASE37_HOTSPOT_AOI_SIZE_DEG,
    DEFAULT_PHASE37_HOTSPOT_BUDGET,
    DEFAULT_PHASE37_HOTSPOT_CACHE_DIR,
    DEFAULT_PHASE37_HOTSPOT_MIN_CLUSTER_CELLS,
    DEFAULT_PHASE37_HOTSPOT_MIN_DISTANCE_DEG,
    DEFAULT_PHASE37_HOTSPOT_OUTPUT_DIR,
    DEFAULT_PHASE37_HOTSPOT_PERCENTILE,
    DEFAULT_PHASE37_HOTSPOT_REGIONS_FILE,
    DEFAULT_PHASE37_HOTSPOT_YEAR,
    DEFAULT_PHASE37_SAMPLE_STEP,
    DEFAULT_PHASE37_SOURCE_LAT_CHUNK_SIZE,
    run_phase37_hotspot_selection,
)

DEFAULT_PHASE37_INPUT_DIR = Path("results/phase3.6")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="在 priority regions 内提取 Phase 3.7 entropy hotspots",
    )
    parser.add_argument(
        "--metrics-path",
        type=Path,
        help="显式指定 phase3_6_entropy_*.nc 路径；若不传则按 input-dir/year 推断",
    )
    parser.add_argument(
        "--classes-path",
        type=Path,
        help="显式指定 phase3_6_unified_classes_*.nc 路径；若不传则按 input-dir/year 推断",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_PHASE37_INPUT_DIR,
        help="Phase 3.6 NetCDF 输出目录 (默认：results/phase3.6)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_PHASE37_HOTSPOT_OUTPUT_DIR,
        help="Phase 3.7 hotspot 输出目录 (默认：results/phase3.7_hotspots)",
    )
    parser.add_argument(
        "--regions-file",
        type=Path,
        default=DEFAULT_PHASE37_HOTSPOT_REGIONS_FILE,
        help="区域配置文件 (默认：config/priority_regions.yaml)",
    )
    parser.add_argument(
        "--regions",
        nargs="*",
        help="可选：只处理指定 region id 列表；默认处理全部 priority regions",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_PHASE37_HOTSPOT_CACHE_DIR,
        help="Phase 3.7 coarse candidate cache 目录 (默认：results/cache/phase3_7)",
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        help="显式指定 Phase 3.7 coarse candidate cache 路径",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_PHASE37_HOTSPOT_YEAR,
        help="目标年份 (默认：2016)",
    )
    parser.add_argument(
        "--total-hotspot-budget",
        type=int,
        default=DEFAULT_PHASE37_HOTSPOT_BUDGET,
        help="总 hotspot 预算，按 region 面积加权分配 (默认：20)",
    )
    parser.add_argument(
        "--threshold-percentile",
        type=float,
        default=DEFAULT_PHASE37_HOTSPOT_PERCENTILE,
        help="每个 region 内的局部分位数阈值 (默认：95)",
    )
    parser.add_argument(
        "--min-cluster-cells",
        type=int,
        default=DEFAULT_PHASE37_HOTSPOT_MIN_CLUSTER_CELLS,
        help="候选 cluster 的最小像元数 (默认：16)",
    )
    parser.add_argument(
        "--aoi-size-deg",
        type=float,
        default=DEFAULT_PHASE37_HOTSPOT_AOI_SIZE_DEG,
        help="输出 hotspot AOI 的固定方框边长，单位度 (默认：0.5)",
    )
    parser.add_argument(
        "--min-distance-deg",
        type=float,
        default=DEFAULT_PHASE37_HOTSPOT_MIN_DISTANCE_DEG,
        help="同一区域内 hotspot 中心的最小去重间距，单位度 (默认：0.5)",
    )
    parser.add_argument(
        "--candidate-sample-step",
        type=int,
        default=DEFAULT_PHASE37_SAMPLE_STEP,
        help="coarse candidate 阶段复用的 Phase 3.7 sparse cache 步长 (默认：8)",
    )
    parser.add_argument(
        "--source-lat-chunk-size",
        type=int,
        default=DEFAULT_PHASE37_SOURCE_LAT_CHUNK_SIZE,
        help="构建 coarse candidate cache 时的源文件纬向条带行数 (默认：512)",
    )
    parser.add_argument(
        "--no-debug-png",
        action="store_false",
        dest="write_debug_png",
        help="不写 region-level debug PNG，只输出 manifest/CSV",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    metrics_path = args.metrics_path or default_metrics_path(args.input_dir, year=args.year)
    classes_path = args.classes_path or default_classes_path(args.input_dir, year=args.year)

    if not metrics_path.is_file():
        logger.error("metrics 文件不存在：%s", metrics_path)
        return 1
    if not classes_path.is_file():
        logger.error("classes 文件不存在：%s", classes_path)
        return 1

    logger.info(
        "Phase3.7 hotspots args: metrics=%s classes=%s output=%s cache=%s year=%s "
        "budget=%s percentile=%s min_cluster_cells=%s aoi_size_deg=%s min_distance_deg=%s "
        "candidate_sample_step=%s debug_png=%s",
        metrics_path,
        classes_path,
        args.output_dir,
        args.cache_path or args.cache_dir,
        args.year,
        args.total_hotspot_budget,
        args.threshold_percentile,
        args.min_cluster_cells,
        args.aoi_size_deg,
        args.min_distance_deg,
        args.candidate_sample_step,
        args.write_debug_png,
    )

    result = run_phase37_hotspot_selection(
        metrics_path,
        classes_path,
        output_dir=args.output_dir,
        regions_file=args.regions_file,
        cache_dir=args.cache_dir,
        cache_path=args.cache_path,
        selected_region_ids=args.regions,
        year=args.year,
        total_budget=args.total_hotspot_budget,
        threshold_percentile=args.threshold_percentile,
        min_cluster_cells=args.min_cluster_cells,
        aoi_size_deg=args.aoi_size_deg,
        min_distance_deg=args.min_distance_deg,
        candidate_sample_step=args.candidate_sample_step,
        source_lat_chunk_size=args.source_lat_chunk_size,
        write_debug_png=args.write_debug_png,
    )
    logger.info("manifest -> %s", result.manifest_path)
    logger.info("csv -> %s", result.csv_path)
    logger.info("region csv -> %s", result.region_csv_path)
    logger.info(
        "Phase3.7 hotspots done: selected=%s shortfall=%s",
        len(result.hotspots),
        sum(summary.shortfall for summary in result.region_summaries),
    )
    return 0


def default_metrics_path(input_dir: Path, *, year: int) -> Path:
    return input_dir / f"phase3_6_entropy_global_500m_{year}.nc"


def default_classes_path(input_dir: Path, *, year: int) -> Path:
    return input_dir / f"phase3_6_unified_classes_global_500m_{year}.nc"


if __name__ == "__main__":
    raise SystemExit(main())
