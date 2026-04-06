from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "check_gwd30_sizes_from_manifest.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_check_gwd30_sizes_from_manifest_script",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Failed to load check_gwd30_sizes_from_manifest.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_manifest_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["year", "file_name", "relative_path", "size_bytes", "gid"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_load_manifest_records_filters_years_and_limit(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest_csv = _write_manifest_csv(
        tmp_path / "manifest.csv",
        [
            {
                "year": 2013,
                "file_name": "a.tif",
                "relative_path": "2013/a.tif",
                "size_bytes": 10,
                "gid": 1,
            },
            {
                "year": 2014,
                "file_name": "b.tif",
                "relative_path": "2014/b.tif",
                "size_bytes": 20,
                "gid": 2,
            },
        ],
    )

    records = module.load_manifest_records(manifest_csv, years=[2014], limit=1)

    assert len(records) == 1
    assert records[0].relative_path == "2014/b.tif"


def test_check_sizes_against_manifest_collects_missing_and_mismatch(tmp_path: Path) -> None:
    module = _load_script_module()
    root = tmp_path / "GWD30"
    good_path = root / "2013" / "good.tif"
    bad_path = root / "2013" / "bad.tif"
    good_path.parent.mkdir(parents=True, exist_ok=True)
    good_path.write_bytes(b"1234")
    bad_path.write_bytes(b"123456")

    records = [
        module.ManifestRecord(
            year=2013,
            file_name="good.tif",
            relative_path="2013/good.tif",
            expected_size_bytes=4,
            gid=1,
        ),
        module.ManifestRecord(
            year=2013,
            file_name="bad.tif",
            relative_path="2013/bad.tif",
            expected_size_bytes=5,
            gid=2,
        ),
        module.ManifestRecord(
            year=2013,
            file_name="missing.tif",
            relative_path="2013/missing.tif",
            expected_size_bytes=7,
            gid=3,
        ),
    ]

    summary = module.check_sizes_against_manifest(root, records)

    assert summary["checked_files"] == 3
    assert summary["ok_files"] == 1
    assert summary["mismatch_files"] == 2
    assert summary["size_mismatch_files"] == 1
    assert summary["missing_files"] == 1
    mismatch_statuses = [row["status"] for row in summary["mismatches"]]
    assert mismatch_statuses == ["size_mismatch", "missing_file"]


def test_write_size_check_reports_outputs_expected_files(tmp_path: Path) -> None:
    module = _load_script_module()
    summary = {
        "root": "/tmp/GWD30",
        "checked_files": 2,
        "ok_files": 1,
        "mismatch_files": 1,
        "missing_files": 1,
        "size_mismatch_files": 0,
        "stat_failed_files": 0,
        "per_year_checked": {"2013": 2},
        "per_year_mismatches": {"2013": 1},
        "mismatches": [
            {
                "year": 2013,
                "file_name": "missing.tif",
                "relative_path": "2013/missing.tif",
                "absolute_path": "/tmp/GWD30/2013/missing.tif",
                "gid": 3,
                "status": "missing_file",
                "expected_size_bytes": 7,
                "actual_size_bytes": None,
                "difference_bytes": None,
                "error_message": "file not found",
            }
        ],
    }

    outputs = module.write_size_check_reports(
        summary,
        output_dir=tmp_path / "reports",
        manifest_csv=tmp_path / "manifest.csv",
    )

    rendered_summary = json.loads(outputs["summary_json"].read_text(encoding="utf-8"))
    mismatch_csv = outputs["mismatch_csv"].read_text(encoding="utf-8")
    mismatch_paths = outputs["mismatch_paths"].read_text(encoding="utf-8")

    assert rendered_summary["mismatch_files"] == 1
    assert "2013/missing.tif" in mismatch_csv
    assert mismatch_paths.strip() == "2013/missing.tif"


def test_run_returns_nonzero_when_mismatches_exist(tmp_path: Path) -> None:
    module = _load_script_module()
    root = tmp_path / "GWD30"
    manifest_csv = _write_manifest_csv(
        tmp_path / "manifest.csv",
        [
            {
                "year": 2013,
                "file_name": "missing.tif",
                "relative_path": "2013/missing.tif",
                "size_bytes": 7,
                "gid": 1,
            }
        ],
    )
    root.mkdir(parents=True, exist_ok=True)

    exit_code = module._run(
        [
            "--root",
            str(root),
            "--manifest-csv",
            str(manifest_csv),
            "--output-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert exit_code == 2


def test_run_emits_stage_announcements(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module()
    root = tmp_path / "GWD30"
    good_path = root / "2013" / "good.tif"
    good_path.parent.mkdir(parents=True, exist_ok=True)
    good_path.write_bytes(b"1234")
    manifest_csv = _write_manifest_csv(
        tmp_path / "manifest.csv",
        [
            {
                "year": 2013,
                "file_name": "good.tif",
                "relative_path": "2013/good.tif",
                "size_bytes": 4,
                "gid": 1,
            }
        ],
    )

    exit_code = module._run(
        [
            "--root",
            str(root),
            "--manifest-csv",
            str(manifest_csv),
            "--output-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "[gwd30-size-check] resolving GWD30 root" in stdout
    assert "[gwd30-size-check] loading manifest CSV:" in stdout
    assert "[gwd30-size-check] starting local size verification" in stdout
    assert "[gwd30-size-check] writing reports to" in stdout
    assert "[gwd30-size-check] finished:" in stdout
