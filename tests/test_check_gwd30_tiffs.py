from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_gwd30_tiffs.py"
    spec = importlib.util.spec_from_file_location(
        "test_check_gwd30_tiffs_script",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Failed to load check_gwd30_tiffs.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_tiled_gwd30_tiff(
    path: Path,
    *,
    band_count: int = 92,
    width: int = 128,
    height: int = 128,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.arange(band_count * width * height, dtype=np.uint8).reshape(
        band_count,
        height,
        width,
    )
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=band_count,
        dtype="uint8",
        crs="EPSG:32633",
        transform=from_origin(0.0, float(height) * 30.0, 30.0, 30.0),
        nodata=255,
        tiled=True,
        blockxsize=32,
        blockysize=32,
        compress="lzw",
    ) as dataset:
        dataset.write(data)
    return path


def _write_year_manifest(root: Path, year: int, file_names: list[str]) -> Path:
    manifest_path = root / f"GWD30_file_list_{year}.json"
    manifest_path.write_text(json.dumps(file_names), encoding="utf-8")
    return manifest_path


def test_inspect_gwd30_tiff_reports_metadata_mismatch(tmp_path: Path) -> None:
    module = _load_script_module()
    root = tmp_path / "GWD30"
    path = _write_tiled_gwd30_tiff(root / "2021" / "33PVS_wetland_2021.tif", width=64, height=64)

    result = module.inspect_gwd30_tiff(path, root=root, strict_profile=True)

    assert result.ok is False
    assert result.status == "metadata_mismatch"
    assert "width=64" in (result.error_message or "")
    assert result.relative_path == "2021/33PVS_wetland_2021.tif"


def test_inspect_gwd30_tiff_reports_structure_failure_for_truncated_file(tmp_path: Path) -> None:
    module = _load_script_module()
    root = tmp_path / "GWD30"
    path = _write_tiled_gwd30_tiff(root / "2021" / "33PVS_wetland_2021.tif")

    raw_bytes = path.read_bytes()
    path.write_bytes(raw_bytes[: len(raw_bytes) // 2])

    result = module.inspect_gwd30_tiff(
        path,
        root=root,
        strict_profile=False,
        read_mode="footprint",
    )

    assert result.ok is False
    assert result.status == "structure_failed"
    assert result.error_type is not None


def test_audit_reports_and_quarantine_bad_files(tmp_path: Path) -> None:
    module = _load_script_module()
    root = tmp_path / "GWD30"
    good_path = _write_tiled_gwd30_tiff(root / "2021" / "33PVS_wetland_2021.tif")
    bad_path = _write_tiled_gwd30_tiff(root / "2021" / "33PVT_wetland_2021.tif")
    _write_year_manifest(root, 2021, [good_path.name, bad_path.name])
    bad_path.write_bytes(bad_path.read_bytes()[: len(bad_path.read_bytes()) // 2])

    summary = module.audit_gwd30_tiffs(
        root,
        workers=1,
        strict_profile=False,
        read_mode="footprint",
    )
    output_dir = tmp_path / "audit"
    report_paths = module.write_audit_reports(summary, output_dir=output_dir)

    assert summary["total_files"] == 2
    assert summary["ok_files"] == 1
    assert summary["bad_files"] == 1
    assert report_paths["summary_json"].exists()
    assert report_paths["bad_csv"].exists()
    assert report_paths["redownload_targets"].read_text(encoding="utf-8").strip() == (
        "2021/33PVT_wetland_2021.tif"
    )

    quarantine_dir = tmp_path / "quarantine"
    moves = module.quarantine_bad_files(summary, root=root, quarantine_dir=quarantine_dir)

    assert len(moves) == 1
    assert good_path.exists()
    assert not bad_path.exists()
    assert (quarantine_dir / "2021" / "33PVT_wetland_2021.tif").exists()

    summary_json = json.loads(report_paths["summary_json"].read_text(encoding="utf-8"))
    assert summary_json["bad_files"] == 1


def test_run_returns_nonzero_when_bad_files_found(tmp_path: Path) -> None:
    module = _load_script_module()
    root = tmp_path / "GWD30"
    good_path = _write_tiled_gwd30_tiff(root / "2021" / "33PVS_wetland_2021.tif")
    bad_path = _write_tiled_gwd30_tiff(root / "2021" / "33PVT_wetland_2021.tif")
    _write_year_manifest(root, 2021, [good_path.name, bad_path.name])
    bad_path.write_bytes(bad_path.read_bytes()[: len(bad_path.read_bytes()) // 2])

    exit_code = module._run(
        [
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "audit"),
            "--workers",
            "1",
            "--no-strict-profile",
            "--read-mode",
            "footprint",
        ]
    )

    assert exit_code == 2


def test_resolve_audit_worker_count_uses_env_and_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module()

    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "64")

    assert module._resolve_audit_worker_count(0) == module._GWD30_AUDIT_MAX_WORKERS


def test_run_uses_auto_parallel_workers_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module()
    root = tmp_path / "GWD30"
    path = _write_tiled_gwd30_tiff(root / "2021" / "33PVS_wetland_2021.tif")
    _write_year_manifest(root, 2021, [path.name])

    monkeypatch.setenv("WA_GWD30_AUDIT_WORKERS", "3")

    exit_code = module._run(
        [
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "audit"),
            "--no-strict-profile",
        ]
    )

    assert exit_code == 0
    summary = json.loads((tmp_path / "audit" / "summary.json").read_text(encoding="utf-8"))
    assert summary["workers"] == 3


def test_run_emits_stage_announcements(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module()
    root = tmp_path / "GWD30"
    path = _write_tiled_gwd30_tiff(root / "2021" / "33PVS_wetland_2021.tif")
    _write_year_manifest(root, 2021, [path.name])

    exit_code = module._run(
        [
            "--root",
            str(root),
            "--output-dir",
            str(tmp_path / "audit"),
            "--workers",
            "1",
            "--no-strict-profile",
        ]
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "[gwd30-audit] resolving GWD30 root" in stdout
    assert "[gwd30-audit] discovering TIFF files under" in stdout
    assert "[gwd30-audit] discovery plan: loading manifest files 2021" in stdout
    assert "[gwd30-audit] discovery: loading manifest GWD30_file_list_2021.json" in stdout
    assert "[gwd30-audit] starting serial TIFF scan" in stdout
    assert "[gwd30-audit] writing reports to" in stdout
    assert "[gwd30-audit] audit finished" in stdout


def test_discover_gwd30_tiffs_uses_year_manifests(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module()
    root = tmp_path / "GWD30"
    path_2021 = _write_tiled_gwd30_tiff(root / "2021" / "33PVS_wetland_2021.tif")
    path_2022 = _write_tiled_gwd30_tiff(root / "2022" / "33PVT_wetland_2022.tif")
    _write_year_manifest(root, 2021, [path_2021.name])
    _write_year_manifest(root, 2022, [path_2022.name])

    discovered = module.discover_gwd30_tiffs(root)

    assert [path.name for path in discovered] == [
        "33PVS_wetland_2021.tif",
        "33PVT_wetland_2022.tif",
    ]
    stdout = capsys.readouterr().out
    assert "discovery plan: loading manifest files 2021, 2022" in stdout
    assert "manifest GWD30_file_list_2021.json yielded 1 TIFF file(s)" in stdout
    assert "manifest GWD30_file_list_2022.json yielded 1 TIFF file(s)" in stdout


def test_discover_gwd30_tiffs_filters_requested_year_manifests(tmp_path: Path) -> None:
    module = _load_script_module()
    root = tmp_path / "GWD30"
    path_2021 = _write_tiled_gwd30_tiff(root / "2021" / "33PVS_wetland_2021.tif")
    _write_tiled_gwd30_tiff(root / "2022" / "33PVT_wetland_2022.tif")
    _write_year_manifest(root, 2021, [path_2021.name])
    _write_year_manifest(root, 2022, ["33PVT_wetland_2022.tif"])

    discovered = module.discover_gwd30_tiffs(root, years=[2021])

    assert [path.name for path in discovered] == ["33PVS_wetland_2021.tif"]
