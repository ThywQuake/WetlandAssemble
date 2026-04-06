#!/usr/bin/env python3
# ruff: noqa: E402
"""Batch-plot Phase 2.6 regional 2x3 comparison panels."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from WA.comparison.phase26 import DEFAULT_PHASE26_REGION_ID, DEFAULT_PHASE26_RESOLUTION_DEG
from WA.phase26_region_imagery import (
    DEFAULT_PHASE26_REGION_IMAGERY_DIR,
    DEFAULT_PHASE26_REGION_IMAGERY_YEAR,
    find_phase26_region_quicklook,
)
from WA.visualization.phase26 import (
    load_phase26_regions,
    plot_phase26_region_panel,
    resolve_phase26_panel_dataset_ids,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按 priority_regions.yaml 批量绘制 Phase 2.6 的 2x3 regional comparison panels",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("results/phase2.6"),
        help="Phase 2.6 NetCDF 输出目录 (默认：results/phase2.6)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/figures/phase2.6_regions"),
        help="区域图输出目录 (默认：results/figures/phase2.6_regions)",
    )
    parser.add_argument(
        "--regions-file",
        type=Path,
        default=Path("config/priority_regions.yaml"),
        help="区域配置文件 (默认：config/priority_regions.yaml)",
    )
    parser.add_argument(
        "--input-region",
        default=DEFAULT_PHASE26_REGION_ID,
        help="输入 metrics/stack 所属的大区域 id (默认：global_tropical_subtropical_35)",
    )
    parser.add_argument(
        "--resolution-deg",
        type=float,
        default=DEFAULT_PHASE26_RESOLUTION_DEG,
        help="输入 Phase 2.6 输出分辨率 (默认：0.25)",
    )
    parser.add_argument(
        "--regions",
        nargs="*",
        help="可选：只绘制指定 region id 列表；默认绘制配置中的全部区域",
    )
    parser.add_argument(
        "--imagery-dir",
        type=Path,
        default=DEFAULT_PHASE26_REGION_IMAGERY_DIR,
        help="区域卫星底图目录；由 download_phase2_6_region_imagery.py 生成",
    )
    parser.add_argument(
        "--imagery-year",
        type=int,
        default=DEFAULT_PHASE26_REGION_IMAGERY_YEAR,
        help="区域卫星底图年份 (默认：2016)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="输出 PNG dpi (默认：150)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    metrics_path = phase26_metrics_path(
        args.input_dir,
        region_id=args.input_region,
        resolution_deg=args.resolution_deg,
    )
    stack_path = phase26_stack_path(
        args.input_dir,
        region_id=args.input_region,
        resolution_deg=args.resolution_deg,
    )
    if not metrics_path.is_file():
        logger.error("metrics 文件不存在：%s", metrics_path)
        return 1
    if not stack_path.is_file():
        logger.error("stack 文件不存在：%s", stack_path)
        return 1

    logger.info("读取 metrics: %s", metrics_path)
    metrics = xr.open_dataset(metrics_path)
    try:
        loaded_metrics = metrics.load()
    finally:
        metrics.close()

    logger.info("读取 stack: %s", stack_path)
    stack_ds = xr.open_dataset(stack_path)
    try:
        loaded_stack = stack_ds["wetland_fraction"].load()
    finally:
        stack_ds.close()

    dataset_ids = resolve_phase26_panel_dataset_ids(loaded_stack, loaded_metrics)
    logger.info("区域图使用的数据集: %s", ", ".join(dataset_ids))

    regions = load_phase26_regions(args.regions_file)
    if args.regions:
        wanted = set(args.regions)
        regions = [region for region in regions if region.region_id in wanted]

    if not regions:
        logger.error("没有可绘制的 region")
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for region in regions:
        output_path = args.output_dir / f"{region.region_id}.png"
        satellite_image_path = find_phase26_region_quicklook(
            args.imagery_dir,
            region_id=region.region_id,
            target_year=args.imagery_year,
        )
        logger.info("绘制 region: %s -> %s", region.region_id, output_path)
        if satellite_image_path is None:
            logger.warning(
                "region=%s 未找到卫星底图，将使用空白占位面板", region.region_id
            )
        plot_phase26_region_panel(
            loaded_metrics,
            loaded_stack,
            region=region,
            output_path=output_path,
            dataset_ids=dataset_ids,
            satellite_image_path=satellite_image_path,
            dpi=args.dpi,
        )

    logger.info("全部区域绘图完成：%d 张", len(regions))
    return 0


def phase26_metrics_path(input_dir: Path, *, region_id: str, resolution_deg: float) -> Path:
    return input_dir / f"phase2_6_metrics_{output_suffix(region_id, resolution_deg)}.nc"


def phase26_stack_path(input_dir: Path, *, region_id: str, resolution_deg: float) -> Path:
    return input_dir / f"phase2_6_stack_{output_suffix(region_id, resolution_deg)}.nc"


def output_suffix(region_id: str, resolution_deg: float) -> str:
    resolution_text = f"{resolution_deg:.6f}".rstrip("0").rstrip(".")
    return f"{region_id}_{resolution_text.replace('.', 'p')}deg"


if __name__ == "__main__":
    raise SystemExit(main())
