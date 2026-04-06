#!/usr/bin/env python3
"""Build Phase 4 Stage-1 GWD30 native-grid pixel-statistics tiles."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.comparison.trends import (  # noqa: E402
    DEFAULT_GWD30_STANDARDIZED_DIR,
    build_gwd30_native_pixel_statistics_tiles,
    phase4_gwd30_pixel_stats_tile_dir,
)
from WA.config import get_dataset_config  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build Phase 4 Stage-1 GWD30 native-grid pixel statistics tiles.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("results/phase4"),
    )
    parser.add_argument(
        "--standardized-dir",
        type=Path,
        default=DEFAULT_GWD30_STANDARDIZED_DIR,
    )
    parser.add_argument("--year", action="append", default=[])
    parser.add_argument(
        "--aggregation",
        choices=("native", "monthly", "annual"),
        default="monthly",
    )
    parser.add_argument(
        "--worker-count",
        type=int,
        default=1,
        help="Number of tile workers to use during native staged-tile statistics transforms.",
    )
    parser.add_argument(
        "--skip",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reuse existing transformed statistics tiles when present (default: True).",
    )
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show tqdm progress where available (default: True).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser


def _resolve_years(requested: list[str]) -> list[int] | None:
    if not requested:
        return None
    years: list[int] = []
    for entry in requested:
        years.extend(int(part.strip()) for part in str(entry).split(",") if part.strip())
    return years


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="[%(levelname)s] %(message)s",
        force=True,
    )

    years = _resolve_years(args.year)
    if years is None:
        config = get_dataset_config("gwd30")
        years = [int(year) for year in config.get("years", [])]
    if not years:
        raise ValueError("No GWD30 years were selected for Stage-1 native pixel statistics")

    transformed = build_gwd30_native_pixel_statistics_tiles(
        output_root=args.output_root,
        standardized_dir=args.standardized_dir,
        years=years,
        aggregation=args.aggregation,
        worker_count=args.worker_count,
        show_progress=args.progress,
        skip_existing=args.skip,
    )

    for year, tiles in transformed.items():
        output_dir = phase4_gwd30_pixel_stats_tile_dir(
            output_root=args.output_root,
            year=year,
            aggregation=args.aggregation,
        )
        summary_path = output_dir.parent / "tile_manifest.json"
        summary_payload = {
            "year": int(year),
            "aggregation": str(args.aggregation),
            "tile_count": len(tiles),
            "output_dir": str(output_dir),
            "tiles": [
                {
                    "path": str(path),
                    "bbox": [float(value) for value in bbox],
                }
                for path, bbox in tiles
            ],
        }
        summary_path.write_text(
            json.dumps(summary_payload, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        logging.info(
            "Phase4 cache write: gwd30_native_pixel_stats year=%s aggregation=%s tiles=%s path=%s",
            year,
            args.aggregation,
            len(tiles),
            summary_path,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
