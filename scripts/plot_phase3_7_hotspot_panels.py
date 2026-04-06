#!/usr/bin/env python3
# ruff: noqa: E402
"""Batch-plot Phase 3.7 hotspot panels from hotspot + S2 artifact manifests."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections.abc import Sequence
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from WA.comparison.phase36 import DEFAULT_PHASE36_STANDARDIZED_DIR  # noqa: E402
from WA.s2_batch import (  # noqa: E402
    DEFAULT_PHASE37_HOTSPOTS_MANIFEST,
    DEFAULT_PHASE37_S2_TARGET_TIME,
    default_phase37_s2_artifact_manifest_path,
)
from WA.visualization.phase37 import (  # noqa: E402
    build_phase37_hotspot_plot_dataset,
    plot_phase37_hotspot_panel,
)

DEFAULT_PHASE37_INPUT_DIR = Path("results/phase3.6")
DEFAULT_PHASE37_HOTSPOT_PANELS_DIR = Path("results/figures/phase3.7_hotspots")
DEFAULT_PHASE37_YEAR = 2016
DEFAULT_PHASE37_DPI = 300

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot Phase 3.7 hotspot panels from hotspot and S2 manifests.",
    )
    parser.add_argument(
        "--hotspots-manifest",
        type=Path,
        default=DEFAULT_PHASE37_HOTSPOTS_MANIFEST,
        help="Phase 3.7 hotspot manifest path",
    )
    parser.add_argument(
        "--s2-artifacts-manifest",
        type=Path,
        help="Phase 3.7 S2 artifact manifest path; defaults to year/target-time derived path",
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
        default=DEFAULT_PHASE37_HOTSPOT_PANELS_DIR,
        help="Hotspot panel 输出目录 (默认：results/figures/phase3.7_hotspots)",
    )
    parser.add_argument(
        "--metrics-path",
        type=Path,
        help="显式指定 phase3_6_entropy_*.nc 路径；若不传则按 input-dir/year 推断",
    )
    parser.add_argument(
        "--classes-path",
        type=Path,
        help="兼容旧 unified hotspot panel 流程；raw mode 下一般不需要传",
    )
    parser.add_argument(
        "--standardized-dir",
        type=Path,
        default=DEFAULT_PHASE36_STANDARDIZED_DIR,
        help="standardized 原始分类目录，用于 raw hotspot panel (默认：output/standardized)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_PHASE37_YEAR,
        help="目标年份 (默认：2016)",
    )
    parser.add_argument(
        "--hotspots",
        nargs="*",
        help="可选：只绘制指定 hotspot id 列表",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_PHASE37_DPI,
        help="输出 PNG dpi (默认：300)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    metrics_path = args.metrics_path or default_metrics_path(args.input_dir, year=args.year)
    classes_path = args.classes_path or default_classes_path(args.input_dir, year=args.year)
    s2_artifacts_manifest = args.s2_artifacts_manifest or default_s2_artifacts_manifest_path(
        args.hotspots_manifest
    )

    if not args.hotspots_manifest.is_file():
        logger.error("hotspots manifest 不存在：%s", args.hotspots_manifest)
        return 1
    if not metrics_path.is_file():
        logger.error("metrics 文件不存在：%s", metrics_path)
        return 1
    if not args.standardized_dir.exists() and not classes_path.is_file():
        logger.error("classes 文件不存在，且 standardized-dir 也不可用：%s", classes_path)
        return 1
    if not args.standardized_dir.exists():
        logger.warning(
            "standardized-dir 不存在，将优先依赖 classes 文件中的预计算 source dominant vars；"
            "若缺失则回退 unified hotspot panel: %s",
            args.standardized_dir,
        )

    hotspots, _default_title_time = load_phase37_hotspots_manifest(args.hotspots_manifest)
    if args.hotspots:
        wanted = set(args.hotspots)
        hotspots = [row for row in hotspots if row["hotspot_id"] in wanted]

    if not hotspots:
        logger.error("没有可绘制的 hotspot")
        return 1

    s2_index, _s2_target_time = load_phase37_s2_quicklook_index(s2_artifacts_manifest)

    logger.info(
        "Phase3.7 hotspot panels args: hotspots=%s s2_artifacts=%s metrics=%s "
        "standardized=%s classes=%s output=%s count=%s dpi=%s",
        args.hotspots_manifest,
        s2_artifacts_manifest,
        metrics_path,
        args.standardized_dir,
        classes_path,
        args.output_dir,
        len(hotspots),
        args.dpi,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    classes_context = (
        xr.open_dataset(classes_path, decode_cf=True)
        if classes_path.is_file()
        else nullcontext(None)
    )
    with (
        xr.open_dataset(metrics_path, decode_cf=True) as metrics_dataset,
        classes_context as classes_dataset,
    ):
        for index, hotspot in enumerate(hotspots, start=1):
            hotspot_id = str(hotspot["hotspot_id"])
            logger.info(
                "Phase3.7 hotspot panel start: %s (%s/%s)",
                hotspot_id,
                index,
                len(hotspots),
            )
            plot_dataset = build_phase37_hotspot_plot_dataset(
                metrics_dataset,
                classes_dataset,
                bbox=tuple(float(value) for value in hotspot["bbox"]),
                standardized_dir=args.standardized_dir if args.standardized_dir.exists() else None,
                year=args.year,
            )
            try:
                output_path = args.output_dir / f"{hotspot_id}_panel.png"
                suptitle = format_phase37_hotspot_title(hotspot)
                plot_phase37_hotspot_panel(
                    plot_dataset,
                    output_path=output_path,
                    satellite_image_path=s2_index.get(hotspot_id),
                    dpi=args.dpi,
                    suptitle=suptitle,
                )
            finally:
                plot_dataset.close()
            logger.info("Phase3.7 hotspot panel done: %s -> %s", hotspot_id, output_path)

    logger.info("Phase3.7 hotspot panels finished: %d panel(s)", len(hotspots))
    return 0


def load_phase37_hotspots_manifest(path: Path) -> tuple[list[dict[str, Any]], pd.Timestamp | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_hotspots = payload.get("hotspots", [])
    if not isinstance(raw_hotspots, list):
        raise ValueError("hotspots manifest must contain a 'hotspots' list")
    default_time = None
    year = payload.get("year")
    if isinstance(year, int):
        default_time = pd.Timestamp(year=year, month=7, day=1)
    return raw_hotspots, default_time


def format_phase37_hotspot_title(hotspot: dict[str, Any]) -> str:
    region_label = str(hotspot.get("region_label", hotspot.get("region_slug", "Unknown")))
    rank = hotspot.get("region_rank")
    if isinstance(rank, int):
        return f"{region_label} {rank:03d}"

    hotspot_id = str(hotspot.get("hotspot_id", "")).strip()
    match = re.search(r"(\d+)$", hotspot_id)
    if match:
        return f"{region_label} {int(match.group(1)):03d}"
    return region_label


def load_phase37_s2_quicklook_index(
    path: Path,
) -> tuple[dict[str, Path | None], pd.Timestamp | None]:
    if not path.is_file():
        logger.warning("S2 artifact manifest 不存在，将全部使用占位面板：%s", path)
        return {}, None

    payload = json.loads(path.read_text(encoding="utf-8"))
    target_time = payload.get("target_time")
    timestamp = pd.Timestamp(target_time) if isinstance(target_time, str) else None
    index: dict[str, Path | None] = {}
    for row in payload.get("artifacts", []):
        hotspot_id = str(row.get("hotspot_id", ""))
        artifact = row.get("artifact", {})
        if not hotspot_id or not isinstance(artifact, dict):
            continue
        status = str(artifact.get("status", ""))
        quicklook_path = artifact.get("quicklook_path")
        if status in {"downloaded", "cached"} and isinstance(quicklook_path, str):
            candidate = Path(quicklook_path)
            index[hotspot_id] = candidate if candidate.is_file() else None
        else:
            index[hotspot_id] = None
    return index, timestamp


def default_metrics_path(input_dir: Path, *, year: int) -> Path:
    return input_dir / f"phase3_6_entropy_global_500m_{year}.nc"


def default_classes_path(input_dir: Path, *, year: int) -> Path:
    return input_dir / f"phase3_6_unified_classes_global_500m_{year}.nc"


def default_s2_artifacts_manifest_path(hotspots_manifest: Path) -> Path:
    return default_phase37_s2_artifact_manifest_path(
        hotspots_manifest,
        target_time=DEFAULT_PHASE37_S2_TARGET_TIME,
    )


if __name__ == "__main__":
    raise SystemExit(main())
