#!/usr/bin/env python
"""Stage one deterministic shard of GWD30 coarse tile partials."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.config import load_dataset_config  # noqa: E402
from WA.loaders import get_loader  # noqa: E402
from WA.standardize import build_reference_grid  # noqa: E402

logger = logging.getLogger("WA.gwd30.shard")

_NOISY_LOGGERS = (
    "rasterio",
    "rioxarray",
    "pyproj",
    "fiona",
)


def _configure_logging(*, verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("WA").setLevel(logging.DEBUG if verbose else logging.INFO)
    for logger_name in _NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def _staging_dir(output_dir: Path, year: int) -> Path:
    return output_dir / "_staging" / f"gwd30_{year}" / "tile_partials"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage one shard of GWD30 coarse tile partials for later merge.",
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument(
        "--resolution",
        type=float,
        default=500,
        help="Spatial resolution in metres (default: 500)",
    )
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        default=[-180, -35, 180, 35],
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help="Bounding box (default: [-180, -35, 180, 35])",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/standardized"),
        help="Standardized output root (default: output/standardized)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/datasets.yaml"),
        help="Path to datasets.yaml",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Per-task local worker count (0 = auto/capped)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Reuse already staged tile partials when present",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        help="Optional JSON summary path for this shard",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    _configure_logging(verbose=args.verbose)

    bbox = tuple(float(value) for value in args.bbox)
    reference_grid = build_reference_grid(bbox, resolution_m=args.resolution)
    dataset_document = load_dataset_config(args.config)
    loader = get_loader("gwd30", dataset_document["datasets"]["gwd30"])
    staging_dir = _staging_dir(args.output_dir, args.year)

    logger.info(
        "GWD30 shard run: year=%s shard=%s/%s output_dir=%s staging_dir=%s",
        args.year,
        args.shard_index + 1,
        args.shard_count,
        args.output_dir,
        staging_dir,
    )

    staged_tiles = loader.stage_time_fraction_tiles(
        bbox=bbox,
        reference_grid=reference_grid,
        year=args.year,
        staging_dir=staging_dir,
        worker_count=(args.workers if args.workers > 0 else None),
        show_progress=True,
        skip_existing=args.skip_existing,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
    )

    manifest_path = args.manifest_path
    if manifest_path is None:
        manifest_path = staging_dir.parent / (
            f"stage_shard_{args.shard_index:04d}_of_{args.shard_count:04d}.json"
        )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset_id": "gwd30",
        "year": int(args.year),
        "bbox": list(bbox),
        "resolution_m": float(args.resolution),
        "shard_index": int(args.shard_index),
        "shard_count": int(args.shard_count),
        "skip_existing": bool(args.skip_existing),
        "worker_count": int(args.workers if args.workers > 0 else 0),
        "staging_dir": str(staging_dir),
        "staged_tile_count": len(staged_tiles),
        "staged_tiles": [
            {"path": str(stage_path), "bbox": list(stage_bbox)}
            for stage_path, stage_bbox in staged_tiles
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )

    logger.info(
        "GWD30 shard run complete: %d staged tile partial(s), manifest=%s",
        len(staged_tiles),
        manifest_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
