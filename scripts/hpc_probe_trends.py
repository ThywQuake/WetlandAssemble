"""HPC diagnostic script for Phase 4 trend analysis.

Usage:
    uv run python scripts/hpc_probe_trends.py \\
        --dataset-id wad2m \\
        --aggregation annual \\
        --bbox -60 -20 -50 5 \\
        --json-out results/phase4/probe_wad2m.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from WA.comparison.harmonize import (
    create_comparison_grid,
    harmonize_binary_dataset,
)
from WA.comparison.trends import compute_pixel_trends
from WA.loaders.registry import get_loader


def _load_config() -> dict:  # type: ignore[type-arg]
    config_path = Path(__file__).parent.parent / "config" / "datasets.yaml"
    with config_path.open() as f:
        return yaml.safe_load(f)  # type: ignore[no-any-return]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 4 trend analysis HPC diagnostic probe."
    )
    parser.add_argument(
        "--dataset-id",
        required=True,
        help="Dataset ID to probe (e.g. wad2m, giems_mc, swamps).",
    )
    parser.add_argument(
        "--aggregation",
        default="annual",
        choices=["annual", "seasonal", "monthly"],
        help="Time aggregation level (default: annual).",
    )
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        default=[-65.0, -20.0, -45.0, 5.0],
        help="Bounding box (default: Brazil wetland region).",
    )
    parser.add_argument(
        "--min-observations",
        type=int,
        default=5,
        help="Minimum time steps required for trend (default: 5).",
    )
    parser.add_argument(
        "--time-range",
        nargs=2,
        metavar=("START", "END"),
        help="Time range to load (e.g., 2000-01-01 2020-12-31). If not specified, loads full dataset.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Path to write JSON result report.",
    )
    args = parser.parse_args()

    config = _load_config()
    dataset_config = config["datasets"].get(args.dataset_id)
    if dataset_config is None:
        print(f"ERROR: Unknown dataset '{args.dataset_id}'")
        sys.exit(1)

    bbox = tuple(args.bbox)  # (west, south, east, north)
    print(f"[probe] dataset_id = {args.dataset_id}")
    print(f"[probe] aggregation = {args.aggregation}")
    print(f"[probe] bbox = {bbox}")

    print("[probe] Loading dataset...")
    loader = get_loader(args.dataset_id, dataset_config)
    time_range = tuple(args.time_range) if args.time_range else None  # type: ignore[arg-type]
    ds = loader.load(bbox=bbox, time_range=time_range)  # type: ignore[call-arg]

    print("[probe] Harmonizing to binary wetland fraction...")
    reference_grid = create_comparison_grid(bbox)  # type: ignore[arg-type]
    harmonized = harmonize_binary_dataset(
        args.dataset_id,
        ds,
        reference_grid=reference_grid,
    )
    print(f"[probe] harmonized shape: {dict(harmonized.sizes)}")

    print(f"[probe] Computing {args.aggregation} trends...")
    result = compute_pixel_trends(
        harmonized,
        dataset_id=args.dataset_id,
        aggregation=args.aggregation,
        min_observations=args.min_observations,
    )

    # Build report
    report: dict[str, object] = {
        "dataset_id": result.dataset_id,
        "aggregation": result.aggregation,
        "time_range": list(result.time_range),
        "observation_count": result.observation_count,
        "status": result.status,
    }

    if result.status == "computed":
        valid_mask = np.isfinite(result.sens_slope.values)
        total_valid = int(valid_mask.sum())
        report["total_valid_pixels"] = total_valid
        if total_valid > 0:
            report["significant_pixels"] = int(result.significant.values[valid_mask].sum())
            report["increasing_pixels"] = int(
                (result.trend_direction.values[valid_mask] == 1).sum()
            )
            report["decreasing_pixels"] = int(
                (result.trend_direction.values[valid_mask] == -1).sum()
            )
            report["stable_pixels"] = int(
                (result.trend_direction.values[valid_mask] == 0).sum()
            )
            report["mean_slope"] = float(np.nanmean(result.sens_slope.values))
            report["median_slope"] = float(np.nanmedian(result.sens_slope.values))

    print(json.dumps(report, indent=2))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2))
        print(f"[probe] Report written to {args.json_out}")


if __name__ == "__main__":
    main()
