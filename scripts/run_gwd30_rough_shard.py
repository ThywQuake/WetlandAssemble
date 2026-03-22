#!/usr/bin/env python3
"""Compute one shard of the GWD30 rough-comparison partial reduce output."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from pathlib import Path

import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logging.getLogger("rasterio").setLevel(logging.WARNING)
    logging.getLogger("rioxarray").setLevel(logging.WARNING)
    logging.getLogger("pyproj").setLevel(logging.WARNING)


def _coerce_exit_code(code: object) -> int:
    if code is None:
        return 0
    if isinstance(code, bool):
        return int(code)
    if isinstance(code, int):
        return code
    return 1


def _region_token(region_name: str | None, bbox: tuple[float, float, float, float]) -> str:
    if region_name is not None:
        return region_name
    west, south, east, north = bbox
    return f"bbox_{west:.3f}_{south:.3f}_{east:.3f}_{north:.3f}".replace("-", "m")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one shard of the GWD30 rough-comparison partial reduce pipeline."
    )
    parser.add_argument("--bbox")
    parser.add_argument("--region")
    parser.add_argument("--target-time", required=True)
    parser.add_argument("--resolution-deg", type=float, default=0.25)
    parser.add_argument("--aggregation", choices=("mean", "max"), default="mean")
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--gwd30-workers", type=int, default=0)
    parser.add_argument("--output-root", default="results/phase2/gwd30_shards")
    parser.add_argument("--dataset-config", default="config/datasets.yaml")
    parser.add_argument("--gee-config", default="config/gee_config.yaml")
    return parser


def _run(argv: list[str] | None = None) -> int:
    _configure_logging()
    print("[bootstrap] configure WA geospatial runtime", flush=True)
    from WA._geo_env import configure_geospatial_runtime

    configure_geospatial_runtime()

    from WA.comparison.harmonize import create_comparison_grid
    from WA.config import load_config
    from WA.loader_probe import make_json_safe, resolve_probe_bbox
    from WA.loaders import get_loader
    from WA.rough_probe import build_target_time_range, normalize_target_time

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    app_config = load_config(args.dataset_config, args.gee_config)
    bbox_value, bbox_label = resolve_probe_bbox(
        app_config,
        bbox_text=args.bbox,
        region_name=args.region,
        unsafe_full_spatial_scan=False,
    )
    if bbox_value is None:
        raise ValueError("GWD30 shard run requires a bounded bbox or region")

    target_time = normalize_target_time(pd.Timestamp(args.target_time))
    loader = get_loader("gwd30", app_config.datasets["gwd30"])
    metadata = loader.metadata()
    effective_time_range = build_target_time_range(metadata, target_time)
    if effective_time_range is None:
        raise ValueError(f"GWD30 has no data for target month {target_time:%Y-%m}")

    reference_grid = create_comparison_grid(
        bbox_value,
        resolution_deg=float(args.resolution_deg),
    )
    partial_sum, partial_count, trace = loader.compute_rough_binary_partial(
        bbox=bbox_value,
        time_range=effective_time_range,
        reference_grid=reference_grid,
        aggregation=args.aggregation,
        target_time=target_time,
        worker_count=args.gwd30_workers,
        shard_index=int(args.shard_index),
        shard_count=int(args.shard_count),
    )

    region_token = _region_token(args.region, bbox_value)
    run_dir = Path(args.output_root) / region_token / f"{target_time:%Y%m}"
    run_dir.mkdir(parents=True, exist_ok=True)
    shard_suffix = f"{int(args.shard_index):03d}_of_{int(args.shard_count):03d}"

    partial_ds = xr.Dataset(
        {
            "partial_sum": reference_grid.copy(data=partial_sum.astype("float32")),
            "partial_count": reference_grid.copy(data=partial_count.astype("int32")),
        },
        attrs={
            "dataset_id": "gwd30",
            "bbox": json.dumps(list(bbox_value)),
            "bbox_label": bbox_label,
            "target_time": target_time.isoformat(),
            "effective_time_range": json.dumps(list(effective_time_range)),
            "aggregation": args.aggregation,
            "resolution_deg": float(args.resolution_deg),
            "shard_index": int(args.shard_index),
            "shard_count": int(args.shard_count),
            "worker_count": int(trace["worker_count"]),
        },
    )
    partial_path = run_dir / f"gwd30_partial_{shard_suffix}.nc"
    partial_ds.to_netcdf(partial_path)

    trace_path = run_dir / f"gwd30_partial_trace_{shard_suffix}.json"
    trace_path.write_text(
        json.dumps(make_json_safe(trace), indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )

    print(f"[done] wrote partial shard to {partial_path}", flush=True)
    print(f"[done] wrote trace to {trace_path}", flush=True)
    return 0


def _main() -> int:
    try:
        return _coerce_exit_code(_run())
    except SystemExit as exc:
        return _coerce_exit_code(exc.code)
    except BaseException as exc:
        traceback.print_exception(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = _main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
