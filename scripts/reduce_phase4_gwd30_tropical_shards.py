#!/usr/bin/env python3
"""Reduce Phase 4 GWD30 tropical shard partial CSVs into one yearly tile cache."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.comparison.phase4_regional import (  # noqa: E402
    DEFAULT_PHASE4_MASK_YEAR,
    DEFAULT_PHASE4_OUTPUT_ROOT,
    PHASE4_GWD30_TROPICAL_CACHE_KEY,
    build_phase4_gwd30_tropical_monthly_tile_from_reduced_file,
    default_phase36_mask_path,
    phase4_gwd30_tropical_tile_cache_path,
)
from WA.utils.progress import tqdm  # noqa: E402


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


def _manifest_lists_dir(*, output_root: Path, year: int) -> Path:
    return (
        output_root
        / "cache"
        / "gwd30"
        / PHASE4_GWD30_TROPICAL_CACHE_KEY
        / f"gwd30_{year}"
        / "manifest_lists"
    )


def _load_expected_partial_paths(*, output_root: Path, year: int) -> list[Path]:
    summary_path = (
        _manifest_lists_dir(output_root=output_root, year=year) / "manifest_lists_summary.json"
    )
    if not summary_path.is_file():
        partials_dir = _partials_dir(output_root=output_root, year=year)
        return sorted(partials_dir.glob("manifest_list_*.csv"))

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    partials_dir = _partials_dir(output_root=output_root, year=year)
    expected_partial_paths = [
        partials_dir / f"{Path(str(item['path'])).stem}.csv"
        for item in payload.get("manifest_lists", [])
    ]
    missing_partial_paths = [path for path in expected_partial_paths if not path.is_file()]
    if missing_partial_paths:
        raise FileNotFoundError(
            "Phase4 GWD30 tropical reduce is missing expected partial CSV(s): "
            + ", ".join(str(path) for path in missing_partial_paths[:5])
            + (" ..." if len(missing_partial_paths) > 5 else "")
        )
    return expected_partial_paths


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reduce Phase 4 GWD30 tropical partial shard CSVs into one yearly cache.",
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_PHASE4_OUTPUT_ROOT,
    )
    parser.add_argument(
        "--phase36-mask-path",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--phase36-cache-dir",
        type=Path,
        default=Path("results/cache/phase3_6"),
    )
    parser.add_argument(
        "--phase36-mask-year",
        type=int,
        default=DEFAULT_PHASE4_MASK_YEAR,
    )
    parser.add_argument(
        "--worker-count",
        type=int,
        default=1,
        help="Number of tile workers to use during the masked reduce stage.",
    )
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show tqdm progress during the masked reduce stage (default: True).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser


def _build_tile_monthly_task(
    *,
    reduced_path: str,
    tile_bbox: tuple[float, float, float, float],
    time_range: tuple[str, str],
    phase36_mask_path: str,
) -> pd.DataFrame:
    return build_phase4_gwd30_tropical_monthly_tile_from_reduced_file(
        reduced_path=reduced_path,
        tile_bbox=tile_bbox,
        time_range=time_range,
        phase36_mask_path=phase36_mask_path,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    partials_dir = _partials_dir(output_root=args.output_root, year=args.year)
    partial_paths = _load_expected_partial_paths(output_root=args.output_root, year=args.year)
    if not partial_paths:
        raise FileNotFoundError(f"No Phase4 GWD30 tropical partials were found in {partials_dir}")

    partial_frames = [pd.read_csv(path) for path in partial_paths]
    tile_index = (
        pd.concat(partial_frames, ignore_index=True)
        .sort_values(["tile_id", "reduced_path"])
        .reset_index(drop=True)
    )
    before = len(tile_index)
    tile_index = tile_index.drop_duplicates(subset=["reduced_path"]).reset_index(
        drop=True
    )
    if len(tile_index) != before:
        logging.warning(
            "Phase4 GWD30 tropical reduce dropped %d duplicate tile index row(s)",
            before - len(tile_index),
        )

    if tile_index.empty:
        raise ValueError(f"Phase4 GWD30 tile index partials were empty in {partials_dir}")

    mask_path = (
        args.phase36_mask_path
        if args.phase36_mask_path is not None
        else default_phase36_mask_path(
            cache_dir=args.phase36_cache_dir,
            year=args.phase36_mask_year,
        )
    )
    tasks = [
        {
            "reduced_path": str(row["reduced_path"]),
            "tile_bbox": (
                float(row["tile_west"]),
                float(row["tile_south"]),
                float(row["tile_east"]),
                float(row["tile_north"]),
            ),
        }
        for row in tile_index.to_dict(orient="records")
    ]
    logging.info(
        "Phase4 GWD30 tropical reduce start: year=%s partials=%s tiles=%s mask=%s workers=%s",
        args.year,
        len(partial_paths),
        len(tasks),
        mask_path,
        max(1, int(args.worker_count)),
    )
    logging.info("Phase4 GWD30 reduce uses shared mask only at merge stage")

    time_range = (f"{args.year}-01-01", f"{args.year}-12-31")
    tile_frames: list[pd.DataFrame] = []
    processed_reduced_paths: set[str] = set()
    progress = tqdm(
        total=len(tasks),
        desc=f"Phase4 gwd30 reduce {args.year}",
        unit="tile",
        disable=not args.progress,
    )

    def process_serial(task_batch: list[dict[str, object]]) -> None:
        for task in task_batch:
            frame = _build_tile_monthly_task(
                reduced_path=str(task["reduced_path"]),
                tile_bbox=task["tile_bbox"],  # type: ignore[arg-type]
                time_range=time_range,
                phase36_mask_path=str(mask_path),
            )
            processed_reduced_paths.add(str(task["reduced_path"]))
            if not frame.empty:
                tile_frames.append(frame)
            progress.update(1)

    worker_count = max(1, int(args.worker_count))
    if worker_count > 1 and len(tasks) > 1:
        fallback_to_serial = False
        try:
            with ProcessPoolExecutor(
                max_workers=worker_count,
                max_tasks_per_child=1,
            ) as executor:
                future_to_task = {
                    executor.submit(
                        _build_tile_monthly_task,
                        reduced_path=str(task["reduced_path"]),
                        tile_bbox=task["tile_bbox"],  # type: ignore[arg-type]
                        time_range=time_range,
                        phase36_mask_path=str(mask_path),
                    ): task
                    for task in tasks
                }
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        frame = future.result()
                        processed_reduced_paths.add(str(task["reduced_path"]))
                        if not frame.empty:
                            tile_frames.append(frame)
                        progress.update(1)
                    except BrokenProcessPool as exc:
                        logging.warning(
                            "Phase4 GWD30 tropical reduce parallel pool broke (%s: %s); "
                            "falling back to serial for remaining tiles",
                            type(exc).__name__,
                            exc,
                        )
                        fallback_to_serial = True
                        break
                    except Exception as exc:
                        logging.warning(
                            "Phase4 GWD30 tropical reduce parallel worker failed (%s: %s); "
                            "falling back to serial for remaining tiles",
                            type(exc).__name__,
                            exc,
                        )
                        fallback_to_serial = True
                        break
        except Exception as exc:
            logging.warning(
                "Phase4 GWD30 tropical reduce parallel launch failed (%s: %s); "
                "falling back to serial",
                type(exc).__name__,
                exc,
            )
            fallback_to_serial = True

        if fallback_to_serial:
            remaining = [
                task for task in tasks if str(task["reduced_path"]) not in processed_reduced_paths
            ]
            process_serial(remaining)
    else:
        process_serial(tasks)

    progress.close()
    if not tile_frames:
        raise ValueError(
            f"Phase4 GWD30 tropical reduce produced no tile-month rows for {args.year}"
        )

    combined = (
        pd.concat(tile_frames, ignore_index=True)
        .sort_values(["time", "tile_id"])
        .reset_index(drop=True)
    )
    before = len(combined)
    combined = combined.drop_duplicates(subset=["time", "tile_id", "stage_path"]).reset_index(
        drop=True
    )
    if len(combined) != before:
        logging.warning(
            "Phase4 GWD30 tropical reduce dropped %d duplicate monthly row(s)",
            before - len(combined),
        )

    output_path = phase4_gwd30_tropical_tile_cache_path(
        output_root=args.output_root,
        year=args.year,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False)
    logging.info(
        "Phase4 cache write: gwd30_tropical_tile_monthly year=%s rows=%s path=%s",
        args.year,
        len(combined),
        output_path,
    )

    trace_path = partials_dir / "reduce_trace.json"
    trace_payload = {
        "year": int(args.year),
        "partial_count": len(partial_paths),
        "tile_count": len(tasks),
        "output_path": str(output_path),
        "rows": len(combined),
        "mask_path": str(mask_path),
        "worker_count": worker_count,
        "partials": [str(path) for path in partial_paths],
    }
    trace_path.write_text(
        json.dumps(trace_payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    logging.info("Phase4 trace write: gwd30_tropical_reduce -> %s", trace_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
