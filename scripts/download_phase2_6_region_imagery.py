#!/usr/bin/env python3
# ruff: noqa: E402
"""Download Phase 2.6 region satellite quicklooks as a separate preprocessing step."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from WA.config import load_config
from WA.loader_probe import make_json_safe
from WA.phase26_region_imagery import (
    DEFAULT_PHASE26_REGION_IMAGERY_DIMENSIONS,
    DEFAULT_PHASE26_REGION_IMAGERY_DIR,
    DEFAULT_PHASE26_REGION_IMAGERY_YEAR,
    download_phase26_region_quicklook,
    phase26_region_quicklook_manifest_record,
)
from WA.utils.progress import tqdm
from WA.validation.gee_client import EarthEngineClient
from WA.visualization.phase26 import load_phase26_regions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按 priority_regions.yaml 下载 Phase 2.6 区域 MODIS RGB quicklook",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_PHASE26_REGION_IMAGERY_DIR,
        help="区域卫星底图输出目录 (默认：results/phase2.6_region_imagery)",
    )
    parser.add_argument(
        "--regions-file",
        type=Path,
        default=Path("config/priority_regions.yaml"),
        help="区域配置文件 (默认：config/priority_regions.yaml)",
    )
    parser.add_argument(
        "--regions",
        nargs="*",
        help="可选：只下载指定 region id 列表；默认下载全部区域",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_PHASE26_REGION_IMAGERY_YEAR,
        help="年度 MODIS 合成目标年份 (默认：2016)",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=DEFAULT_PHASE26_REGION_IMAGERY_DIMENSIONS,
        help="GEE quicklook 最大像素边长 (默认：1536)",
    )
    parser.add_argument(
        "--allow-interactive-auth",
        action="store_true",
        help="允许 Earth Engine 走交互认证",
    )
    parser.add_argument(
        "--no-skip",
        action="store_false",
        dest="skip_existing",
        help="即使本地已存在 JPG 也重新下载",
    )
    parser.add_argument(
        "--dataset-config",
        default="config/datasets.yaml",
        help="数据集配置文件路径",
    )
    parser.add_argument(
        "--gee-config",
        default="config/gee_config.yaml",
        help="GEE 配置文件路径",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app_config = load_config(args.dataset_config, args.gee_config)
    gee_client = EarthEngineClient.from_config(app_config.gee)

    regions = load_phase26_regions(args.regions_file)
    if args.regions:
        wanted = set(args.regions)
        regions = [region for region in regions if region.region_id in wanted]

    if not regions:
        logger.error("没有可下载的 region")
        return 1

    status_counts: Counter[str] = Counter()
    records: list[dict[str, Any]] = []

    progress = tqdm(
        regions,
        desc="Phase2.6 region imagery",
        unit="region",
        dynamic_ncols=True,
    )
    for region in progress:
        progress.set_postfix_str(region.region_id, refresh=False)
        artifact = download_phase26_region_quicklook(
            region.region_id,
            region.bbox,
            gee_client,
            output_dir=args.output_dir,
            target_year=args.year,
            allow_interactive_auth=args.allow_interactive_auth,
            skip_existing=args.skip_existing,
            dimensions=args.dimensions,
        )
        status_counts[artifact.status] += 1
        records.append(
            phase26_region_quicklook_manifest_record(
                artifact,
                region_label=region.label,
                bbox=region.bbox,
            )
        )
        logger.info(
            "region=%s status=%s quicklook=%s",
            region.region_id,
            artifact.status,
            artifact.quicklook_path,
        )
    progress.close()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / f"phase2_6_region_imagery_{args.year}_manifest.json"
    payload = {
        "target_year": args.year,
        "dimensions": args.dimensions,
        "skip_existing": args.skip_existing,
        "regions_file": args.regions_file,
        "output_dir": args.output_dir,
        "status_counts": dict(status_counts),
        "artifacts": records,
    }
    manifest_path.write_text(
        json.dumps(
            make_json_safe(payload),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    logger.info("manifest -> %s", manifest_path)
    logger.info("状态统计: %s", dict(status_counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
