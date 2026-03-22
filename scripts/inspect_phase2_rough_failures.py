#!/usr/bin/env python3
"""Inspect Phase 2 rough comparison outputs and summarize failure patterns."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize failed and skipped datasets from Phase 2 rough run summaries."
    )
    parser.add_argument(
        "--phase2-root",
        default="results/phase2/rough",
        help="Directory containing per-run rough outputs.",
    )
    parser.add_argument(
        "--priority-csv",
        default="results/phase2/rough/landsat_review_priority.csv",
        help="Optional priority review CSV used to mark runs that reached review.",
    )
    parser.add_argument(
        "--json-out",
        help="Optional JSON path for the structured inspection summary.",
    )
    return parser


def inspect_phase2_rough_failures(
    phase2_root: Path,
    *,
    priority_csv: Path | None = None,
) -> dict[str, Any]:
    run_summaries = sorted(phase2_root.glob("*/*/run_summary.json"))
    priority_run_ids = load_priority_run_ids(priority_csv) if priority_csv is not None else set()

    run_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    run_status_counts: Counter[str] = Counter()
    dataset_status_counts: Counter[str] = Counter()

    for summary_path in run_summaries:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        region_id = summary_path.parent.parent.name
        run_slug = summary_path.parent.name
        run_id = f"{region_id}_{run_slug}"
        target_time = str(payload.get("target_time", ""))
        run_status = str(payload.get("status", "unknown"))
        run_status_counts[run_status] += 1

        failed_entries: list[dict[str, Any]] = []
        skipped_entries: list[dict[str, Any]] = []
        for dataset_result in payload.get("dataset_results", []):
            dataset_status = str(dataset_result.get("status", "unknown"))
            if dataset_status.startswith("failed"):
                row = {
                    "run_id": run_id,
                    "region_id": region_id,
                    "target_time": target_time,
                    "run_status": run_status,
                    "dataset_id": dataset_result.get("dataset_id"),
                    "dataset_status": dataset_status,
                    "comparison_source_variable": (
                        dataset_result.get("comparison_source_variable")
                        or infer_source_variable_from_error(dataset_result.get("error"))
                    ),
                    "error": dataset_result.get("error"),
                    "in_priority_review": run_id in priority_run_ids,
                }
                failure_rows.append(row)
                failed_entries.append(row)
                dataset_status_counts[f"{row['dataset_id']}::{dataset_status}"] += 1
            elif dataset_status.startswith("skipped"):
                skipped_entries.append(
                    {
                        "dataset_id": dataset_result.get("dataset_id"),
                        "dataset_status": dataset_status,
                    }
                )

        run_rows.append(
            {
                "run_id": run_id,
                "region_id": region_id,
                "target_time": target_time,
                "run_status": run_status,
                "in_priority_review": run_id in priority_run_ids,
                "failed_datasets": failed_entries,
                "skipped_datasets": skipped_entries,
            }
        )

    return {
        "phase2_root": str(phase2_root),
        "priority_run_ids": sorted(priority_run_ids),
        "run_status_counts": dict(run_status_counts),
        "dataset_status_counts": dict(dataset_status_counts),
        "runs": run_rows,
        "failures": failure_rows,
    }


def load_priority_run_ids(priority_csv: Path | None) -> set[str]:
    if priority_csv is None or not priority_csv.exists():
        return set()

    with priority_csv.open(encoding="utf-8", newline="") as handle:
        return {row["run_id"] for row in csv.DictReader(handle) if row.get("run_id")}


def infer_source_variable_from_error(error: object) -> str | None:
    if not isinstance(error, str):
        return None
    match = re.search(r"from ([A-Za-z0-9_]+)", error)
    if match is None:
        return None
    return match.group(1)


def render_inspection_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"phase2_root: {summary['phase2_root']}",
        f"priority_runs: {len(summary['priority_run_ids'])}",
        "run_status_counts:",
    ]
    for status, count in sorted(summary["run_status_counts"].items()):
        lines.append(f"  - {status}: {count}")

    lines.append("dataset_failure_counts:")
    if summary["dataset_status_counts"]:
        for status, count in sorted(summary["dataset_status_counts"].items()):
            lines.append(f"  - {status}: {count}")
    else:
        lines.append("  - none")

    lines.append("failed_runs:")
    failed_runs = [run for run in summary["runs"] if run["failed_datasets"]]
    if not failed_runs:
        lines.append("  - none")
    else:
        for run in failed_runs:
            suffix = " priority_review" if run["in_priority_review"] else ""
            lines.append(
                f"  - {run['run_id']} ({run['run_status']}, {run['target_time']}){suffix}"
            )
            for failure in run["failed_datasets"]:
                source_variable = failure.get("comparison_source_variable") or "unknown_variable"
                lines.append(
                    "      "
                    f"* {failure['dataset_id']} [{failure['dataset_status']}] "
                    f"source={source_variable} error={failure['error']}"
                )
    return "\n".join(lines)


def _run() -> int:
    args = build_arg_parser().parse_args()
    phase2_root = Path(args.phase2_root)
    priority_csv = Path(args.priority_csv) if args.priority_csv else None

    summary = inspect_phase2_rough_failures(phase2_root, priority_csv=priority_csv)
    print(render_inspection_summary(summary))

    if args.json_out:
        output_path = Path(args.json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    return 0


def _coerce_exit_code(code: object) -> int:
    if code is None:
        return 0
    if isinstance(code, bool):
        return int(code)
    if isinstance(code, int):
        return code
    return 1


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
