#!/usr/bin/env python3
# ruff: noqa: E402
"""Plot Phase 2.6 mean/std/participant-count maps as a 3x1 figure."""

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
from WA.visualization.phase26 import plot_phase26_triptych

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把 Phase 2.6 的 metrics.nc 画成三行一列图：mean / std / participant",
    )
    parser.add_argument(
        "--metrics-path",
        type=Path,
        help="显式指定 phase2_6_metrics_*.nc 路径；若不传则按 input-dir/region/resolution 推断",
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
        default=Path("results/figures/phase2.6"),
        help="PNG 输出目录 (默认：results/figures/phase2.6)",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        help="显式指定输出 PNG 路径；若不传则自动按 region/resolution 命名",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_PHASE26_REGION_ID,
        help="region id (默认：global_tropical_subtropical_35)",
    )
    parser.add_argument(
        "--resolution-deg",
        type=float,
        default=DEFAULT_PHASE26_RESOLUTION_DEG,
        help="分辨率 (默认：0.25)",
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
    metrics_path = args.metrics_path or default_metrics_path(
        args.input_dir,
        region_id=args.region,
        resolution_deg=args.resolution_deg,
    )
    output_path = args.output_path or default_output_path(
        args.output_dir,
        region_id=args.region,
        resolution_deg=args.resolution_deg,
    )

    if not metrics_path.is_file():
        logger.error("metrics 文件不存在：%s", metrics_path)
        return 1

    logger.info("读取 metrics: %s", metrics_path)
    metrics = xr.open_dataset(metrics_path)
    try:
        loaded = metrics.load()
    finally:
        metrics.close()

    suptitle = (
        f"Phase 2.6 Metrics ({args.region}, {args.resolution_deg:g}°)\n"
        "Mean / Std / Participant Count"
    )
    plot_phase26_triptych(
        loaded,
        output_path=output_path,
        dpi=args.dpi,
        suptitle=suptitle,
    )
    logger.info("PNG 已输出：%s", output_path)
    return 0


def default_metrics_path(input_dir: Path, *, region_id: str, resolution_deg: float) -> Path:
    return input_dir / f"phase2_6_metrics_{output_suffix(region_id, resolution_deg)}.nc"


def default_output_path(output_dir: Path, *, region_id: str, resolution_deg: float) -> Path:
    return output_dir / f"phase2_6_triptych_{output_suffix(region_id, resolution_deg)}.png"


def output_suffix(region_id: str, resolution_deg: float) -> str:
    resolution_text = f"{resolution_deg:.6f}".rstrip("0").rstrip(".")
    return f"{region_id}_{resolution_text.replace('.', 'p')}deg"


if __name__ == "__main__":
    raise SystemExit(main())
