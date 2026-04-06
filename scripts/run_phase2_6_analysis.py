#!/usr/bin/env python3
"""Phase 2.6: use HPC 0.25° plotting caches to compute coarse comparison grids."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

import xarray as xr

# ruff: noqa: E402
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from WA.comparison.phase26 import (
    DEFAULT_PHASE26_CACHE_DIR,
    DEFAULT_PHASE26_DATASET_IDS,
    DEFAULT_PHASE26_LANDMASK_DATASET_ID,
    DEFAULT_PHASE26_REGION_ID,
    DEFAULT_PHASE26_RESOLUTION_DEG,
    DEFAULT_PHASE26_STD_EXCLUDED_DATASET_IDS,
    DEFAULT_PHASE26_TARGET_YEAR,
    Phase26CacheLoadResult,
    apply_landmask_to_surfaces,
    build_phase26_stack,
    compute_phase26_metrics,
    load_cached_coarse_surfaces,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 2.6: 从 0.25° 绘图缓存生成统计量，并用 GLWD 有效范围统一做 landmask",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_PHASE26_CACHE_DIR,
        help="plot_tropical_wetland_025deg.py 生成的 staged cache 根目录",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/phase2.6"),
        help="输出目录 (默认：results/phase2.6)",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_PHASE26_REGION_ID,
        help="缓存 region id (默认：global_tropical_subtropical_35)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_PHASE26_TARGET_YEAR,
        help="动态数据集默认年份 (默认：2016；Berkeley 仍强制 2019)",
    )
    parser.add_argument(
        "--resolution-deg",
        type=float,
        default=DEFAULT_PHASE26_RESOLUTION_DEG,
        help="缓存分辨率 (默认：0.25)",
    )
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=list(DEFAULT_PHASE26_DATASET_IDS),
        help="参与分析的数据集；GWD30 会被自动排除",
    )
    parser.add_argument(
        "--min-participants",
        type=int,
        default=2,
        help="计算标准差所需的最少有效数据集数 (默认：2)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="只要任一请求数据集缺缓存/缓存陈旧就直接失败",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅检查缓存命中情况，不写输出",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_ids = [dataset_id for dataset_id in args.datasets if dataset_id != "gwd30"]

    if "gwd30" in args.datasets:
        logger.info("按要求排除 GWD30；不会参与 Phase 2.6 计算")

    cache_result = load_cached_coarse_surfaces(
        args.cache_dir,
        region_id=args.region,
        dataset_ids=dataset_ids,
        default_year=args.year,
        resolution_deg=args.resolution_deg,
    )

    _log_cache_status(cache_result)

    if args.strict and cache_result.skipped:
        logger.error("strict 模式下存在缺失/陈旧缓存，停止执行")
        return 1

    if args.dry_run:
        logger.info("dry-run 完成，不写输出")
        return 0

    if len(cache_result.surfaces) < 2:
        logger.error("可用缓存少于 2 个，无法计算跨数据集标准差")
        return 1

    try:
        masked_surfaces = apply_landmask_to_surfaces(
            cache_result.surfaces,
            landmask_dataset_id=DEFAULT_PHASE26_LANDMASK_DATASET_ID,
        )
    except ValueError as exc:
        logger.error("无法应用 GLWD landmask: %s", exc)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("已应用统一 landmask: %s", DEFAULT_PHASE26_LANDMASK_DATASET_ID)
    logger.info(
        "std 统计排除数据集: %s",
        ", ".join(DEFAULT_PHASE26_STD_EXCLUDED_DATASET_IDS),
    )

    stack = build_phase26_stack(masked_surfaces)
    metrics = compute_phase26_metrics(
        masked_surfaces,
        min_participants=args.min_participants,
        std_excluded_dataset_ids=DEFAULT_PHASE26_STD_EXCLUDED_DATASET_IDS,
    )
    metrics.attrs.update(
        {
            "region_id": args.region,
            "resolution_deg": float(args.resolution_deg),
            "cache_dir": str(args.cache_dir),
            "landmask_dataset_id": DEFAULT_PHASE26_LANDMASK_DATASET_ID,
            "std_excluded_dataset_ids_json": json.dumps(
                sorted(DEFAULT_PHASE26_STD_EXCLUDED_DATASET_IDS)
            ),
        }
    )

    suffix = _output_suffix(args.region, args.resolution_deg)
    stack_path = args.output_dir / f"phase2_6_stack_{suffix}.nc"
    metrics_path = args.output_dir / f"phase2_6_metrics_{suffix}.nc"
    summary_path = args.output_dir / f"phase2_6_summary_{suffix}.json"

    _write_stack(stack_path, stack)
    _write_metrics(metrics_path, metrics)

    summary = {
        "region_id": args.region,
        "resolution_deg": args.resolution_deg,
        "cache_dir": str(args.cache_dir),
        "loaded_dataset_ids": sorted(cache_result.surfaces),
        "landmask_dataset_id": DEFAULT_PHASE26_LANDMASK_DATASET_ID,
        "std_excluded_dataset_ids": sorted(DEFAULT_PHASE26_STD_EXCLUDED_DATASET_IDS),
        "skipped": cache_result.skipped,
        "stack_path": str(stack_path),
        "metrics_path": str(metrics_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.info("Phase 2.6 完成")
    logger.info("  stack   -> %s", stack_path)
    logger.info("  metrics -> %s", metrics_path)
    logger.info("  summary -> %s", summary_path)
    return 0


def _log_cache_status(cache_result: Phase26CacheLoadResult) -> None:
    logger.info("可用缓存数据集：%d", len(cache_result.surfaces))
    for dataset_id, path in sorted(cache_result.cache_paths.items()):
        logger.info("  [hit] %s <- %s", dataset_id, path)
    for dataset_id, reason in sorted(cache_result.skipped.items()):
        logger.warning("  [skip] %s: %s", dataset_id, reason)


def _output_suffix(region_id: str, resolution_deg: float) -> str:
    resolution_text = f"{resolution_deg:.6f}".rstrip("0").rstrip(".")
    return f"{region_id}_{resolution_text.replace('.', 'p')}deg"


def _write_stack(path: Path, stack: xr.DataArray) -> None:
    stack.to_dataset(name="wetland_fraction").to_netcdf(
        path,
        encoding={"wetland_fraction": {"zlib": True, "complevel": 4}},
    )


def _write_metrics(path: Path, metrics: xr.Dataset) -> None:
    metrics.to_netcdf(
        path,
        encoding={
            "mean_wetland_fraction": {"zlib": True, "complevel": 4},
            "std_wetland_fraction": {"zlib": True, "complevel": 4},
            "participant_count": {"zlib": True, "complevel": 4},
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
