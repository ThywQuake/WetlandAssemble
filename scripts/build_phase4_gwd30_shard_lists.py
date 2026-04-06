#!/usr/bin/env python3
"""Build deterministic manifest-list files for sharded Phase 4 GWD30 tropical caching."""

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
    DEFAULT_PHASE4_STANDARDIZED_DIR,
    PHASE4_GWD30_TROPICAL_CACHE_KEY,
    list_phase4_gwd30_stage_shard_manifests,
)
from WA.config import get_dataset_config  # noqa: E402


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="[%(levelname)s] %(message)s",
        force=True,
    )


def _resolve_years(requested: list[str]) -> list[int]:
    if not requested:
        config = get_dataset_config("gwd30")
        return [int(year) for year in config.get("years", [])]

    years: list[int] = []
    for entry in requested:
        years.extend(int(part.strip()) for part in str(entry).split(",") if part.strip())
    return years


def _manifest_lists_dir(*, output_root: Path, year: int) -> Path:
    return (
        output_root
        / "cache"
        / "gwd30"
        / PHASE4_GWD30_TROPICAL_CACHE_KEY
        / f"gwd30_{year}"
        / "manifest_lists"
    )


def _split_manifest_paths(manifest_paths: list[Path], task_count: int) -> list[list[Path]]:
    actual_task_count = max(1, min(int(task_count), len(manifest_paths)))
    groups: list[list[Path]] = [[] for _ in range(actual_task_count)]
    for index, manifest_path in enumerate(manifest_paths):
        groups[index % actual_task_count].append(manifest_path)
    return groups


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build shard-list files for Phase 4 GWD30 tropical tile-cache HPC jobs.",
    )
    parser.add_argument("--year", action="append", default=[])
    parser.add_argument(
        "--task-count",
        type=int,
        default=16,
        help="Number of manifest-list files to build per year (default: 16).",
    )
    parser.add_argument(
        "--standardized-dir",
        type=Path,
        default=DEFAULT_PHASE4_STANDARDIZED_DIR,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_PHASE4_OUTPUT_ROOT,
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

    years = _resolve_years(args.year)
    if not years:
        raise ValueError("No GWD30 years were resolved for shard-list generation")

    for year in years:
        manifest_paths = list_phase4_gwd30_stage_shard_manifests(
            args.standardized_dir,
            year=year,
        )
        groups = _split_manifest_paths(manifest_paths, args.task_count)
        output_dir = _manifest_lists_dir(output_root=args.output_root, year=year)
        output_dir.mkdir(parents=True, exist_ok=True)
        stale_list_paths = list(output_dir.glob("manifest_list_*.txt"))
        for stale_list_path in stale_list_paths:
            stale_list_path.unlink()
        if stale_list_paths:
            logging.info(
                "Phase4 GWD30 shard list cleanup: year=%s removed=%s stale list(s)",
                year,
                len(stale_list_paths),
            )
        (output_dir / "manifest_lists_summary.json").unlink(missing_ok=True)
        summary_payload = {
            "year": int(year),
            "manifest_count": len(manifest_paths),
            "task_count": len(groups),
            "standardized_dir": str(args.standardized_dir),
            "manifest_lists": [],
        }
        for index, group in enumerate(groups):
            list_path = output_dir / f"manifest_list_{index:04d}_of_{len(groups):04d}.txt"
            list_path.write_text(
                "\n".join(str(path) for path in group) + "\n",
                encoding="utf-8",
            )
            logging.info(
                "Phase4 GWD30 shard list write: year=%s list=%s manifests=%s path=%s",
                year,
                index + 1,
                len(group),
                list_path,
            )
            summary_payload["manifest_lists"].append(
                {
                    "path": str(list_path),
                    "manifest_count": len(group),
                }
            )
        summary_path = output_dir / "manifest_lists_summary.json"
        summary_path.write_text(
            json.dumps(summary_payload, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        logging.info(
            "Phase4 GWD30 shard list summary: year=%s manifests=%s task_lists=%s path=%s",
            year,
            len(manifest_paths),
            len(groups),
            summary_path,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
