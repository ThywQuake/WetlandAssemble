#!/usr/bin/env python3
"""Verify local GWD30 TIFF sizes against a remote CSV manifest."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from WA.config import get_dataset_config  # noqa: E402
from WA.utils.progress import tqdm  # noqa: E402

DEFAULT_MANIFEST_CSV = Path("temp/check_gwd30/remote_sizes/gwd30_remote_sizes.csv")
DEFAULT_OUTPUT_DIR = Path("results/maintenance/gwd30_size_check")


@dataclass(frozen=True)
class ManifestRecord:
    """One expected file entry loaded from the remote size manifest."""

    year: int
    file_name: str
    relative_path: str
    expected_size_bytes: int
    gid: int | None


@dataclass(frozen=True)
class SizeMismatchRecord:
    """One local file that does not match the manifest."""

    year: int
    file_name: str
    relative_path: str
    absolute_path: str
    gid: int | None
    status: str
    expected_size_bytes: int
    actual_size_bytes: int | None
    difference_bytes: int | None
    error_message: str | None = None


def _announce(message: str) -> None:
    print(f"[gwd30-size-check] {message}", flush=True)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify local GWD30 TIFF file sizes against the remote CSV manifest."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="GWD30 root directory. Defaults to datasets.gwd30.path from config/datasets.yaml.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/datasets.yaml"),
        help="Dataset config used when --root is omitted.",
    )
    parser.add_argument(
        "--manifest-csv",
        type=Path,
        default=DEFAULT_MANIFEST_CSV,
        help="CSV manifest created by fetch_gwd30_remote_sizes.py.",
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="*",
        help="Optional subset of years to verify.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of manifest rows to verify.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for mismatch reports.",
    )
    return parser


def resolve_gwd30_root(root: Path | None, *, dataset_config_path: Path) -> Path:
    """Resolve the local GWD30 root path."""

    if root is not None:
        return root.expanduser().resolve()

    dataset_config = get_dataset_config("gwd30", dataset_config_path=dataset_config_path)
    raw_path = dataset_config.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("datasets.gwd30.path must be a non-empty string")
    return Path(raw_path).expanduser().resolve()


def _normalize_years(years: list[int] | None) -> set[int] | None:
    if not years:
        return None
    return {int(year) for year in years}


def load_manifest_records(
    manifest_csv: Path,
    *,
    years: list[int] | None = None,
    limit: int = 0,
) -> list[ManifestRecord]:
    """Load manifest records from CSV."""

    resolved_manifest = manifest_csv.expanduser().resolve()
    if not resolved_manifest.exists():
        raise FileNotFoundError(f"manifest CSV does not exist: {resolved_manifest}")

    selected_years = _normalize_years(years)
    records: list[ManifestRecord] = []
    with resolved_manifest.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required_fields = {"year", "file_name", "relative_path", "size_bytes", "gid"}
        if reader.fieldnames is None or not required_fields.issubset(set(reader.fieldnames)):
            raise ValueError(
                "manifest CSV must contain columns: year,file_name,relative_path,size_bytes,gid"
            )

        for row in reader:
            year = int(row["year"])
            if selected_years is not None and year not in selected_years:
                continue

            gid_value = row["gid"].strip()
            gid = int(gid_value) if gid_value else None
            records.append(
                ManifestRecord(
                    year=year,
                    file_name=row["file_name"].strip(),
                    relative_path=row["relative_path"].strip(),
                    expected_size_bytes=int(row["size_bytes"]),
                    gid=gid,
                )
            )
            if limit > 0 and len(records) >= limit:
                break

    if not records:
        raise ValueError("no manifest records selected for verification")
    return records


def check_sizes_against_manifest(
    root: Path,
    records: list[ManifestRecord],
) -> dict[str, object]:
    """Compare local file sizes against the manifest and collect mismatches."""

    mismatches: list[SizeMismatchRecord] = []
    ok_files = 0
    missing_files = 0
    size_mismatch_files = 0
    stat_failed_files = 0
    per_year_checked: dict[str, int] = {}
    per_year_mismatches: dict[str, int] = {}

    progress = tqdm(records, total=len(records), desc="GWD30 size check", unit="file")
    try:
        for record in progress:
            year_key = str(record.year)
            per_year_checked[year_key] = per_year_checked.get(year_key, 0) + 1
            local_path = root / record.relative_path

            try:
                stat_result = local_path.stat()
            except FileNotFoundError:
                missing_files += 1
                per_year_mismatches[year_key] = per_year_mismatches.get(year_key, 0) + 1
                mismatches.append(
                    SizeMismatchRecord(
                        year=record.year,
                        file_name=record.file_name,
                        relative_path=record.relative_path,
                        absolute_path=str(local_path),
                        gid=record.gid,
                        status="missing_file",
                        expected_size_bytes=record.expected_size_bytes,
                        actual_size_bytes=None,
                        difference_bytes=None,
                        error_message="file not found",
                    )
                )
                continue
            except OSError as exc:
                stat_failed_files += 1
                per_year_mismatches[year_key] = per_year_mismatches.get(year_key, 0) + 1
                mismatches.append(
                    SizeMismatchRecord(
                        year=record.year,
                        file_name=record.file_name,
                        relative_path=record.relative_path,
                        absolute_path=str(local_path),
                        gid=record.gid,
                        status="stat_failed",
                        expected_size_bytes=record.expected_size_bytes,
                        actual_size_bytes=None,
                        difference_bytes=None,
                        error_message=str(exc),
                    )
                )
                continue

            actual_size = int(stat_result.st_size)
            if actual_size != record.expected_size_bytes:
                size_mismatch_files += 1
                per_year_mismatches[year_key] = per_year_mismatches.get(year_key, 0) + 1
                mismatches.append(
                    SizeMismatchRecord(
                        year=record.year,
                        file_name=record.file_name,
                        relative_path=record.relative_path,
                        absolute_path=str(local_path),
                        gid=record.gid,
                        status="size_mismatch",
                        expected_size_bytes=record.expected_size_bytes,
                        actual_size_bytes=actual_size,
                        difference_bytes=actual_size - record.expected_size_bytes,
                    )
                )
                continue

            ok_files += 1
            progress.set_postfix_str(
                f"ok={ok_files} mismatch={len(mismatches)}",
                refresh=False,
            )
    finally:
        progress.close()

    return {
        "root": str(root),
        "checked_files": len(records),
        "ok_files": ok_files,
        "mismatch_files": len(mismatches),
        "missing_files": missing_files,
        "size_mismatch_files": size_mismatch_files,
        "stat_failed_files": stat_failed_files,
        "per_year_checked": per_year_checked,
        "per_year_mismatches": per_year_mismatches,
        "mismatches": [asdict(record) for record in mismatches],
    }


def write_size_check_reports(
    summary: dict[str, object],
    *,
    output_dir: Path,
    manifest_csv: Path,
) -> dict[str, Path]:
    """Write mismatch reports and summary."""

    output_dir.mkdir(parents=True, exist_ok=True)

    mismatch_json = output_dir / "mismatches.json"
    mismatch_csv = output_dir / "mismatches.csv"
    mismatch_paths = output_dir / "mismatch_paths.txt"
    summary_json = output_dir / "summary.json"

    mismatches = summary["mismatches"]
    if not isinstance(mismatches, list):
        raise ValueError("summary.mismatches must be a list")

    mismatch_json.write_text(json.dumps(mismatches, indent=2), encoding="utf-8")
    with mismatch_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "year",
                "file_name",
                "relative_path",
                "absolute_path",
                "gid",
                "status",
                "expected_size_bytes",
                "actual_size_bytes",
                "difference_bytes",
                "error_message",
            ],
        )
        writer.writeheader()
        for row in mismatches:
            if not isinstance(row, dict):
                raise ValueError("mismatch row must be a mapping")
            writer.writerow(row)
    mismatch_paths.write_text(
        "\n".join(
            row["relative_path"]
            for row in mismatches
            if isinstance(row, dict) and isinstance(row.get("relative_path"), str)
        ),
        encoding="utf-8",
    )

    summary_payload = {
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest_csv": str(manifest_csv.expanduser().resolve()),
        **{key: value for key, value in summary.items() if key != "mismatches"},
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    return {
        "mismatch_json": mismatch_json,
        "mismatch_csv": mismatch_csv,
        "mismatch_paths": mismatch_paths,
        "summary_json": summary_json,
    }


def _run(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    _announce("resolving GWD30 root")
    root = resolve_gwd30_root(args.root, dataset_config_path=args.config)
    _announce(f"using root: {root}")

    _announce(f"loading manifest CSV: {args.manifest_csv}")
    records = load_manifest_records(args.manifest_csv, years=args.years, limit=args.limit)
    _announce(f"loaded {len(records)} manifest record(s)")

    _announce("starting local size verification")
    summary = check_sizes_against_manifest(root, records)

    _announce(f"writing reports to {args.output_dir}")
    outputs = write_size_check_reports(
        summary,
        output_dir=args.output_dir,
        manifest_csv=args.manifest_csv,
    )
    _announce(
        "finished: "
        f"checked={summary['checked_files']} "
        f"ok={summary['ok_files']} "
        f"mismatch={summary['mismatch_files']} "
        f"csv={outputs['mismatch_csv']}"
    )
    return 0 if int(summary["mismatch_files"]) == 0 else 2


def _main(argv: list[str] | None = None) -> int:
    try:
        return _run(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return code
    except Exception as exc:
        print(f"[gwd30-size-check] fatal: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
