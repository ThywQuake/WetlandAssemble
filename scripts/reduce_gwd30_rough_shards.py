#!/usr/bin/env python3
"""Reduce sharded GWD30 rough-comparison partial outputs into one final surface."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from pathlib import Path

import numpy as np
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


def _coerce_exit_code(code: object) -> int:
    if code is None:
        return 0
    if isinstance(code, bool):
        return int(code)
    if isinstance(code, int):
        return code
    return 1


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reduce GWD30 rough-comparison shard partials into one final surface."
    )
    parser.add_argument("--shards-dir", required=True)
    parser.add_argument("--dataset-config", default="config/datasets.yaml")
    parser.add_argument("--gee-config", default="config/gee_config.yaml")
    parser.add_argument("--output-name", default="gwd30_surface.nc")
    return parser


def _run(argv: list[str] | None = None) -> int:
    _configure_logging()
    print("[bootstrap] configure WA geospatial runtime", flush=True)
    from WA._geo_env import configure_geospatial_runtime

    configure_geospatial_runtime()

    from WA.config import load_config
    from WA.loader_probe import make_json_safe
    from WA.loaders import get_loader

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    shards_dir = Path(args.shards_dir)
    partial_paths = sorted(shards_dir.glob("gwd30_partial_*.nc"))
    if not partial_paths:
        raise FileNotFoundError(f"No GWD30 partial shards found in {shards_dir}")

    app_config = load_config(args.dataset_config, args.gee_config)
    loader = get_loader("gwd30", app_config.datasets["gwd30"])

    combined_sum: np.ndarray | None = None
    combined_count: np.ndarray | None = None
    reference_grid: xr.DataArray | None = None
    target_time: pd.Timestamp | None = None
    aggregation: str | None = None
    shard_payloads: list[dict[str, object]] = []

    for partial_path in partial_paths:
        dataset = xr.open_dataset(partial_path)
        try:
            partial_sum = dataset["partial_sum"].load()
            partial_count = dataset["partial_count"].load()
            if reference_grid is None:
                reference_grid = partial_sum.copy(
                    data=np.zeros_like(partial_sum.values, dtype=np.float32)
                )
                target_time = pd.Timestamp(str(dataset.attrs["target_time"]))
                aggregation = str(dataset.attrs["aggregation"])
                combined_sum = np.zeros(partial_sum.shape, dtype=np.float32)
                combined_count = np.zeros(partial_count.shape, dtype=np.int32)
            assert combined_sum is not None
            assert combined_count is not None
            combined_sum = combined_sum + np.asarray(partial_sum.values, dtype=np.float32)
            combined_count = combined_count + np.asarray(partial_count.values, dtype=np.int32)
            shard_payloads.append(
                {
                    "partial_path": str(partial_path),
                    "shard_index": int(dataset.attrs["shard_index"]),
                    "shard_count": int(dataset.attrs["shard_count"]),
                    "worker_count": int(dataset.attrs["worker_count"]),
                }
            )
        finally:
            dataset.close()

    assert reference_grid is not None
    assert target_time is not None
    assert aggregation is not None
    assert combined_sum is not None
    assert combined_count is not None

    surface = loader.build_surface_from_partial(
        partial_sum=combined_sum.astype(np.float32),
        partial_count=combined_count.astype(np.int32),
        reference_grid=reference_grid,
        aggregation=aggregation,
        target_time=target_time,
    )
    output_path = shards_dir / args.output_name
    xr.Dataset({"wetland_fraction": surface}).to_netcdf(output_path)

    trace_path = shards_dir / "gwd30_reduce_trace.json"
    trace_payload = {
        "output_path": str(output_path),
        "target_time": target_time.isoformat(),
        "aggregation": aggregation,
        "partial_count": len(partial_paths),
        "partials": shard_payloads,
    }
    trace_path.write_text(
        json.dumps(make_json_safe(trace_payload), indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )

    print(f"[done] wrote reduced GWD30 surface to {output_path}", flush=True)
    print(f"[done] wrote reduce trace to {trace_path}", flush=True)
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
