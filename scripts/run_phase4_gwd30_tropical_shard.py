#!/usr/bin/env python3
"""Build one Phase 4 GWD30 tropical tile-cache partial from one manifest-list file."""

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

from WA.comparison.phase4_regional import (  # noqa: E402
    DEFAULT_PHASE4_OUTPUT_ROOT,
    PHASE4_GWD30_TROPICAL_CACHE_KEY,
    build_phase4_gwd30_reduced_tile_index_for_staged_tiles,
    load_phase4_gwd30_staged_tiles_from_manifest_paths,
)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="[%(levelname)s] %(message)s",
        force=True,
    )


def _partials_dir(*, output_root: Path, year: int) -> Path:
    return (
        output_root
        / "cache"
        / "gwd30"
        / PHASE4_GWD30_TROPICAL_CACHE_KEY
        / f"gwd30_{year}"
        / "partials"
    )


def _reduced_tiles_dir(*, output_root: Path, year: int, shard_key: str) -> Path:
    return (
        output_root
        / "cache"
        / "gwd30"
        / PHASE4_GWD30_TROPICAL_CACHE_KEY
        / f"gwd30_{year}"
        / "reduced_tiles"
        / shard_key
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one manifest-list shard for the Phase 4 GWD30 tropical tile cache.",
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--manifest-list", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_PHASE4_OUTPUT_ROOT,
    )
    parser.add_argument(
        "--standardized-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--skip",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reuse an existing partial CSV when present (default: True).",
    )
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show tqdm progress for staged tiles (default: True).",
    )
    parser.add_argument(
        "--worker-count",
        type=int,
        default=1,
        help="Number of tile workers to use in this shard task.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    manifest_list = args.manifest_list.resolve()
    if not manifest_list.is_file():
        raise FileNotFoundError(f"Phase4 GWD30 manifest list was not found: {manifest_list}")

    partials_dir = _partials_dir(output_root=args.output_root, year=args.year)
    partials_dir.mkdir(parents=True, exist_ok=True)
    partial_path = partials_dir / f"{manifest_list.stem}.csv"
    trace_path = partials_dir / f"{manifest_list.stem}.json"
    if args.skip and partial_path.is_file():
        logging.info("Phase4 cache hit: gwd30_tropical_partial <- %s", partial_path)
        return 0

    manifest_paths = [
        Path(line.strip())
        for line in manifest_list.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not manifest_paths:
        raise ValueError(f"Phase4 GWD30 manifest list is empty: {manifest_list}")

    staged_tiles = load_phase4_gwd30_staged_tiles_from_manifest_paths(manifest_paths)
    reduced_tiles_dir = _reduced_tiles_dir(
        output_root=args.output_root,
        year=args.year,
        shard_key=manifest_list.stem,
    )
    partial = build_phase4_gwd30_reduced_tile_index_for_staged_tiles(
        year=args.year,
        staged_tiles=staged_tiles,
        output_dir=reduced_tiles_dir,
        skip_existing=args.skip,
        worker_count=args.worker_count,
        show_progress=args.progress,
    )
    partial.to_csv(partial_path, index=False)
    logging.info(
        "Phase4 cache write: gwd30_tropical_reduced_tile_index year=%s rows=%s path=%s",
        args.year,
        len(partial),
        partial_path,
    )
    trace_payload = {
        "year": int(args.year),
        "manifest_list": str(manifest_list),
        "manifest_count": len(manifest_paths),
        "restored_tile_count": int(partial["tile_id"].nunique()) if not partial.empty else 0,
        "rows": len(partial),
        "partial_path": str(partial_path),
        "reduced_tiles_dir": str(reduced_tiles_dir),
        "standardized_dir": str(args.standardized_dir),
        "mode": "reduced_tile_index",
        "worker_count": int(args.worker_count),
    }
    trace_path.write_text(
        json.dumps(trace_payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    logging.info("Phase4 trace write: gwd30_tropical_reduced_tile_index -> %s", trace_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
