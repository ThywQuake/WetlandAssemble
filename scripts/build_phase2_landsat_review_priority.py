#!/usr/bin/env python3
"""Build a priority review list from the merged Landsat review manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

DEFAULT_INPUT = Path("results/phase2/rough/landsat_review_manifest.csv")
DEFAULT_OUTPUT = Path("results/phase2/rough/landsat_review_priority.csv")


def _split_multi(values: list[str]) -> list[str]:
    items: list[str] = []
    for value in values:
        items.extend(part.strip() for part in value.split(",") if part.strip())
    return items


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Filter landsat_review_manifest.csv into a smaller priority review list."
        )
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--output-json")
    parser.add_argument("--min-disagreement", type=float, default=0.8)
    parser.add_argument("--min-participants", type=int, default=4)
    parser.add_argument(
        "--image-status",
        action="append",
        default=["downloaded,cached"],
        help="Allowed image statuses. Repeatable or comma-separated.",
    )
    parser.add_argument(
        "--region",
        action="append",
        default=[],
        help="Restrict to region_id values. Repeatable or comma-separated.",
    )
    parser.add_argument(
        "--target-time",
        action="append",
        default=[],
        help="Restrict to target_time values. Repeatable or comma-separated.",
    )
    parser.add_argument("--top-n", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_json_path = (
        Path(args.output_json) if args.output_json else output_path.with_suffix(".json")
    )
    image_statuses = set(_split_multi(args.image_status))
    regions = set(_split_multi(args.region))
    target_times = set(_split_multi(args.target_time))

    frame = pd.read_csv(input_path)
    filtered = frame.copy()
    if image_statuses:
        filtered = filtered[filtered["image_status"].isin(image_statuses)]
    filtered = filtered[filtered["disagreement_score"] >= args.min_disagreement]
    filtered = filtered[filtered["participant_count"] >= args.min_participants]
    if regions:
        filtered = filtered[filtered["region_id"].isin(regions)]
    if target_times:
        filtered = filtered[filtered["target_time"].astype(str).isin(target_times)]

    filtered = filtered.sort_values(
        ["disagreement_score", "participant_count", "region_id", "target_time", "original_aoi_id"],
        ascending=[False, False, True, True, True],
    )
    if args.top_n is not None:
        filtered = filtered.head(args.top_n)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(output_path, index=False)
    output_json_path.write_text(
        json.dumps(
            {
                "input": str(input_path),
                "output": str(output_path),
                "filters": {
                    "min_disagreement": args.min_disagreement,
                    "min_participants": args.min_participants,
                    "image_status": sorted(image_statuses),
                    "region": sorted(regions),
                    "target_time": sorted(target_times),
                    "top_n": args.top_n,
                },
                "row_count": int(len(filtered)),
                "rows": filtered.to_dict("records"),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"[landsat-review-priority] input={input_path}")
    print(f"[landsat-review-priority] rows={len(filtered)}")
    print(f"[landsat-review-priority] output={output_path}")
    print(f"[landsat-review-priority] output_json={output_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
