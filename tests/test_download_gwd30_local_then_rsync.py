from __future__ import annotations

import csv
import importlib.util
import json
import sys
import threading
from pathlib import Path


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "download_gwd30_local_then_rsync.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_download_gwd30_local_then_rsync_script",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Failed to load download_gwd30_local_then_rsync.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_mismatch_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
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
        for row in rows:
            writer.writerow(row)
    return path


def test_build_stage_tasks_uses_staging_root_and_skips_existing(tmp_path: Path) -> None:
    module = _load_script_module()
    staging_root = tmp_path / "stage"
    existing = staging_root / "2014" / "01KAB_wetland_2014.tif"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"x" * 10)

    csv_path = _write_mismatch_csv(
        tmp_path / "mismatches.csv",
        [
            {
                "year": 2014,
                "file_name": "01KAB_wetland_2014.tif",
                "relative_path": "2014/01KAB_wetland_2014.tif",
                "absolute_path": "/lustre/home/user/GWD30/2014/01KAB_wetland_2014.tif",
                "gid": 1,
                "status": "size_mismatch",
                "expected_size_bytes": 10,
                "actual_size_bytes": 5,
                "difference_bytes": -5,
                "error_message": "",
            },
            {
                "year": 2014,
                "file_name": "01WCN_wetland_2014.tif",
                "relative_path": "2014/01WCN_wetland_2014.tif",
                "absolute_path": "/lustre/home/user/GWD30/2014/01WCN_wetland_2014.tif",
                "gid": 2,
                "status": "size_mismatch",
                "expected_size_bytes": 20,
                "actual_size_bytes": 5,
                "difference_bytes": -15,
                "error_message": "",
            },
        ],
    )

    pending, already_staged = module.build_stage_tasks(csv_path, staging_root)

    assert already_staged == 1
    assert pending == [
        module.DownloadTask(
            local_path=staging_root / "2014" / "01WCN_wetland_2014.tif",
            object_key="shared-dataset/Wetland/GWD30/2014/01WCN_wetland_2014.tif",
            expected_size_bytes=20,
        )
    ]


def test_build_stage_tasks_skips_existing_file_in_batch_root(tmp_path: Path) -> None:
    module = _load_script_module()
    staging_root = tmp_path / "stage"
    batch_root = tmp_path / "stage.batch_00001"
    existing = batch_root / "2014" / "01WCN_wetland_2014.tif"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"x" * 20)

    csv_path = _write_mismatch_csv(
        tmp_path / "mismatches.csv",
        [
            {
                "year": 2014,
                "file_name": "01WCN_wetland_2014.tif",
                "relative_path": "2014/01WCN_wetland_2014.tif",
                "absolute_path": "/lustre/home/user/GWD30/2014/01WCN_wetland_2014.tif",
                "gid": 2,
                "status": "size_mismatch",
                "expected_size_bytes": 20,
                "actual_size_bytes": 5,
                "difference_bytes": -15,
                "error_message": "",
            },
        ],
    )

    pending, already_staged = module.build_stage_tasks(csv_path, staging_root)

    assert already_staged == 1
    assert pending == []


def test_partition_batches_respects_file_and_size_thresholds(tmp_path: Path) -> None:
    module = _load_script_module()
    tasks = [
        module.DownloadTask(tmp_path / "a.tif", "k1", 4),
        module.DownloadTask(tmp_path / "b.tif", "k2", 5),
        module.DownloadTask(tmp_path / "c.tif", "k3", 6),
    ]

    batches = module.partition_batches(tasks, batch_files=2, batch_size_bytes=8)

    assert [[task.object_key for task in batch] for batch in batches] == [
        ["k1"],
        ["k2"],
        ["k3"],
    ]


def test_rsync_staging_root_builds_expected_command_and_prunes(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    staging_root = tmp_path / "stage"
    file_path = staging_root / "2014" / "a.tif"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"1234")

    captured = {}

    class _FakeStdout:
        def __init__(self) -> None:
            self._chunks = iter(
                [
                    "      2,048  50%  1.00MB/s    0:00:01\r",
                    "      4,096 100%  1.00MB/s    0:00:00 (xfr#1, to-chk=0/1)\n",
                ]
            )

        def read(self, size: int = -1) -> str:
            del size
            try:
                return next(self._chunks)
            except StopIteration:
                return ""

    class _FakePopen:
        def __init__(self, command, stdout, stderr, text) -> None:  # type: ignore[no-untyped-def]
            captured["command"] = command
            captured["stdout"] = stdout
            captured["stderr"] = stderr
            captured["text"] = text
            self.stdout = _FakeStdout()

        def wait(self) -> int:
            file_path.unlink()
            return 0

    monkeypatch.setattr(module.subprocess, "Popen", _FakePopen)

    result = module.rsync_staging_root(
        staging_root,
        remote_dest="user@host:/remote/GWD30",
        rsync_bin="rsync",
        rsync_wrapper="/Users/mac/.ssh/script/with_pkuhpc_auth.sh",
    )

    assert captured["command"] == [
        "/Users/mac/.ssh/script/with_pkuhpc_auth.sh",
        "rsync",
        "-avz",
        "--info=progress2",
        "--remove-source-files",
        "--exclude=*.part",
        f"{staging_root}/",
        "user@host:/remote/GWD30",
    ]
    assert result == {"transferred_files": 1, "transferred_bytes": 4}
    assert not staging_root.exists()


def test_parse_rsync_progress_bytes_extracts_progress2_counter() -> None:
    module = _load_script_module()

    assert (
        module._parse_rsync_progress_bytes(
            "  123,456  78%   10.00MB/s    0:00:03 (xfr#1, to-chk=0/1)"
        )
        == 123456
    )
    assert module._parse_rsync_progress_bytes("=== 自动认证 ===") is None


def test_run_downloads_in_batches_and_writes_reports(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    csv_path = _write_mismatch_csv(
        tmp_path / "mismatches.csv",
        [
            {
                "year": 2014,
                "file_name": "a.tif",
                "relative_path": "2014/a.tif",
                "absolute_path": "",
                "gid": 1,
                "status": "size_mismatch",
                "expected_size_bytes": 4,
                "actual_size_bytes": 0,
                "difference_bytes": -4,
                "error_message": "",
            },
            {
                "year": 2014,
                "file_name": "b.tif",
                "relative_path": "2014/b.tif",
                "absolute_path": "",
                "gid": 2,
                "status": "size_mismatch",
                "expected_size_bytes": 4,
                "actual_size_bytes": 0,
                "difference_bytes": -4,
                "error_message": "",
            },
        ],
    )
    staging_root = tmp_path / "stage"
    report_dir = tmp_path / "reports"
    transfer_calls: list[int] = []

    def fake_download_file(task, max_retries, download_timeout):  # type: ignore[no-untyped-def]
        task.local_path.parent.mkdir(parents=True, exist_ok=True)
        task.local_path.write_bytes(b"1234")
        return task.local_path, True, "Success"

    def fake_rsync_staging_root(
        staging_root,
        remote_dest,
        rsync_bin,
        rsync_wrapper,
        progress_bar,
        reserve_total_bytes,
    ):  # type: ignore[no-untyped-def]
        transfer_calls.append(len(module._iter_stage_files(staging_root)))
        assert rsync_bin == "rsync"
        assert rsync_wrapper == module.DEFAULT_RSYNC_WRAPPER
        assert progress_bar is not None
        assert reserve_total_bytes is False
        for path in module._iter_stage_files(staging_root):
            path.unlink()
        module._prune_empty_dirs(staging_root)
        return {"transferred_files": 1, "transferred_bytes": 4}

    monkeypatch.setattr(module, "download_file", fake_download_file)
    monkeypatch.setattr(module, "rsync_staging_root", fake_rsync_staging_root)

    exit_code = module._run(
        [
            str(csv_path),
            "--remote-dest",
            "user@host:/remote/GWD30",
            "--staging-root",
            str(staging_root),
            "--report-dir",
            str(report_dir),
            "--batch-files",
            "1",
            "--workers",
            "2",
        ]
    )

    assert exit_code == 0
    assert transfer_calls == [1, 1]
    summary = json.loads((report_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["successful_downloads"] == 2
    assert summary["failed_downloads"] == 0


def test_run_overlap_rsync_pipelines_next_batch(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    csv_path = _write_mismatch_csv(
        tmp_path / "mismatches.csv",
        [
            {
                "year": 2014,
                "file_name": "a.tif",
                "relative_path": "2014/a.tif",
                "absolute_path": "",
                "gid": 1,
                "status": "size_mismatch",
                "expected_size_bytes": 4,
                "actual_size_bytes": 0,
                "difference_bytes": -4,
                "error_message": "",
            },
            {
                "year": 2014,
                "file_name": "b.tif",
                "relative_path": "2014/b.tif",
                "absolute_path": "",
                "gid": 2,
                "status": "size_mismatch",
                "expected_size_bytes": 4,
                "actual_size_bytes": 0,
                "difference_bytes": -4,
                "error_message": "",
            },
        ],
    )
    staging_root = tmp_path / "stage"
    report_dir = tmp_path / "reports"
    first_rsync_started = threading.Event()
    allow_first_rsync_finish = threading.Event()
    rsync_calls: list[Path] = []

    def fake_download_file(task, max_retries, download_timeout):  # type: ignore[no-untyped-def]
        task.local_path.parent.mkdir(parents=True, exist_ok=True)
        if task.local_path.name == "b.tif":
            assert first_rsync_started.is_set()
            assert not allow_first_rsync_finish.is_set()
            allow_first_rsync_finish.set()
        task.local_path.write_bytes(b"1234")
        return task.local_path, True, "Success"

    def fake_rsync_staging_root(
        stage_root,
        remote_dest,
        rsync_bin,
        rsync_wrapper,
        progress_bar,
        reserve_total_bytes,
    ):  # type: ignore[no-untyped-def]
        assert rsync_bin == "rsync"
        assert rsync_wrapper == module.DEFAULT_RSYNC_WRAPPER
        assert progress_bar is not None
        assert reserve_total_bytes is False
        rsync_calls.append(stage_root)
        assert stage_root == staging_root
        if len(rsync_calls) == 1:
            first_rsync_started.set()
            assert allow_first_rsync_finish.wait(timeout=1)
        for path in module._iter_stage_files(stage_root):
            path.unlink()
        module._prune_empty_dirs(stage_root)
        return {"transferred_files": 1, "transferred_bytes": 4}

    monkeypatch.setattr(module, "download_file", fake_download_file)
    monkeypatch.setattr(module, "rsync_staging_root", fake_rsync_staging_root)

    exit_code = module._run(
        [
            str(csv_path),
            "--remote-dest",
            "user@host:/remote/GWD30",
            "--staging-root",
            str(staging_root),
            "--report-dir",
            str(report_dir),
            "--batch-files",
            "1",
            "--workers",
            "1",
            "--overlap-rsync",
        ]
    )

    assert exit_code == 0
    summary = json.loads((report_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["overlap_rsync"] is True
    assert summary["successful_downloads"] == 2
    assert not (tmp_path / "stage.batch_00001").exists()
