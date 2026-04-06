#!/usr/bin/env python3
# ruff: noqa: E402
"""Plot the Phase 3.7 global overview figure from Phase 3.6 outputs."""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from WA.visualization.phase37 import (  # noqa: E402
    DEFAULT_PHASE37_SAMPLE_STEP,
    DEFAULT_PHASE37_SOURCE_LAT_CHUNK_SIZE,
    build_phase37_global_plot_dataset,
    plot_phase37_global_figure,
    write_phase37_global_plot_cache,
)

DEFAULT_PHASE37_INPUT_DIR = Path("results/phase3.6")
DEFAULT_PHASE37_OUTPUT_DIR = Path("results/figures/phase3.7")
DEFAULT_PHASE37_CACHE_DIR = Path("results/cache/phase3_7")
DEFAULT_PHASE37_YEAR = 2016
DEFAULT_PHASE37_DPI = 300

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "把 Phase 3.6 的全球分类分歧结果绘制成 2列3行 总览图，"
            "保持 500m 原网格，不重投影，仅按 sample-step 稀疏采样。"
        ),
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
        default=DEFAULT_PHASE37_OUTPUT_DIR,
        help="PNG 输出目录 (默认：results/figures/phase3.7)",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        help="显式指定输出 PNG 路径；若不传则按 year/sample-step 自动命名",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_PHASE37_CACHE_DIR,
        help="稀疏采样后的展示缓存目录 (默认：results/cache/phase3_7)",
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        help="显式指定展示缓存路径；若不传则按 year/sample-step 自动命名",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_PHASE37_YEAR,
        help="目标年份 (默认：2016)",
    )
    parser.add_argument(
        "--sample-step",
        type=int,
        default=DEFAULT_PHASE37_SAMPLE_STEP,
        help="500m 原网格稀疏采样步长；例如 8 表示每 8 个像元取 1 个 (默认：8)",
    )
    parser.add_argument(
        "--source-lat-chunk-size",
        type=int,
        default=DEFAULT_PHASE37_SOURCE_LAT_CHUNK_SIZE,
        help="构建采样缓存时的源文件纬向条带行数 (默认：512)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_PHASE37_DPI,
        help="输出 PNG dpi (默认：300)",
    )
    parser.add_argument(
        "--no-prefer-cache",
        action="store_false",
        dest="prefer_cache",
        help="即使展示缓存已存在，也强制重建",
    )
    parser.add_argument(
        "--no-write-cache",
        action="store_false",
        dest="write_cache",
        help="不把展示缓存写回磁盘，仅本次内存构图",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    metrics_path = args.metrics_path or default_metrics_path(args.input_dir, year=args.year)
    classes_path = args.classes_path or default_classes_path(args.input_dir, year=args.year)
    output_path = args.output_path or default_output_path(
        args.output_dir,
        year=args.year,
        sample_step=args.sample_step,
    )
    cache_path = args.cache_path or default_cache_path(
        args.cache_dir,
        year=args.year,
        sample_step=args.sample_step,
    )

    if not metrics_path.is_file():
        logger.error("metrics 文件不存在：%s", metrics_path)
        return 1
    if not classes_path.is_file():
        logger.error("classes 文件不存在：%s", classes_path)
        return 1

    logger.info(
        "Phase3.7 plotting args: metrics=%s classes=%s cache=%s output=%s sample_step=%s "
        "source_lat_chunk_size=%s prefer_cache=%s write_cache=%s dpi=%s",
        metrics_path,
        classes_path,
        cache_path,
        output_path,
        args.sample_step,
        args.source_lat_chunk_size,
        args.prefer_cache,
        args.write_cache,
        args.dpi,
    )

    plot_dataset: xr.Dataset | None = None
    try:
        if args.prefer_cache and cache_path.is_file():
            logger.info("Phase3.7 plot cache hit: %s", cache_path)
            plot_dataset = xr.open_dataset(cache_path)
            loaded = plot_dataset.load()
            plot_dataset.close()
            plot_dataset = loaded
        elif args.write_cache:
            logger.info("Phase3.7 plot cache miss: %s", cache_path)
            write_phase37_global_plot_cache(
                metrics_path,
                classes_path,
                cache_path=cache_path,
                sample_step=args.sample_step,
                source_lat_chunk_size=args.source_lat_chunk_size,
            )
            plot_dataset = xr.open_dataset(cache_path)
            loaded = plot_dataset.load()
            plot_dataset.close()
            plot_dataset = loaded
        else:
            logger.info("Phase3.7 plot cache disabled: building plot dataset in memory")
            with tempfile.TemporaryDirectory(prefix="phase37-plot-") as _temp_dir:
                plot_dataset = build_phase37_global_plot_dataset(
                    metrics_path,
                    classes_path,
                    sample_step=args.sample_step,
                )

        assert plot_dataset is not None
        suptitle = (
            f"Phase 3.7 Global Classification Disagreement ({args.year})\n"
            f"500m grid sparse-sampled every {args.sample_step} pixel(s)"
        )
        plot_phase37_global_figure(
            plot_dataset,
            output_path=output_path,
            dpi=args.dpi,
            suptitle=suptitle,
        )
    finally:
        if plot_dataset is not None:
            plot_dataset.close()

    logger.info("PNG 已输出：%s", output_path)
    return 0


def default_metrics_path(input_dir: Path, *, year: int) -> Path:
    return input_dir / f"phase3_6_entropy_global_500m_{year}.nc"


def default_classes_path(input_dir: Path, *, year: int) -> Path:
    return input_dir / f"phase3_6_unified_classes_global_500m_{year}.nc"


def default_cache_path(cache_dir: Path, *, year: int, sample_step: int) -> Path:
    return cache_dir / f"phase3_7_global_plot_cache_global_500m_{year}_sample{sample_step}.nc"


def default_output_path(output_dir: Path, *, year: int, sample_step: int) -> Path:
    return output_dir / f"phase3_7_global_overview_global_500m_{year}_sample{sample_step}.png"


if __name__ == "__main__":
    raise SystemExit(main())
