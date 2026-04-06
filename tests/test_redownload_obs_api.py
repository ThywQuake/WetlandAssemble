from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "redownload_obs_api.py"
    spec = importlib.util.spec_from_file_location("test_redownload_obs_api_script", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Failed to load redownload_obs_api.py")
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


def test_load_download_tasks_from_mismatch_csv_skips_already_fixed(tmp_path: Path) -> None:
    module = _load_script_module()
    local_root = tmp_path / "GWD30"
    fixed_path = local_root / "2014" / "01KAB_wetland_2014.tif"
    broken_path = local_root / "2014" / "01WCN_wetland_2014.tif"
    fixed_path.parent.mkdir(parents=True, exist_ok=True)
    fixed_path.write_bytes(b"II*\x00" + b"\x00" * 12)
    broken_path.write_bytes(b"II*\x00" + b"\x00" * 4)

    csv_path = _write_mismatch_csv(
        tmp_path / "mismatches.csv",
        [
            {
                "year": 2014,
                "file_name": fixed_path.name,
                "relative_path": "2014/01KAB_wetland_2014.tif",
                "absolute_path": str(fixed_path),
                "gid": 18450,
                "status": "size_mismatch",
                "expected_size_bytes": fixed_path.stat().st_size,
                "actual_size_bytes": 1,
                "difference_bytes": 0,
                "error_message": "",
            },
            {
                "year": 2014,
                "file_name": broken_path.name,
                "relative_path": "2014/01WCN_wetland_2014.tif",
                "absolute_path": str(broken_path),
                "gid": 18470,
                "status": "size_mismatch",
                "expected_size_bytes": 999,
                "actual_size_bytes": broken_path.stat().st_size,
                "difference_bytes": -1,
                "error_message": "",
            },
        ],
    )

    tasks, already_downloaded = module.load_download_tasks(csv_path)

    assert already_downloaded == 1
    assert tasks == [
        module.DownloadTask(
            local_path=broken_path,
            object_key=f"{module.BASE_PREFIX}/2014/01WCN_wetland_2014.tif",
            expected_size_bytes=999,
        )
    ]


def test_load_download_tasks_from_mismatch_csv_uses_relative_path_when_absolute_missing(
    tmp_path: Path,
) -> None:
    module = _load_script_module()
    csv_path = _write_mismatch_csv(
        tmp_path / "mismatches.csv",
        [
            {
                "year": 2020,
                "file_name": "52UFF_wetland_2020.tif",
                "relative_path": "2020/52UFF_wetland_2020.tif",
                "absolute_path": "",
                "gid": 1,
                "status": "missing_file",
                "expected_size_bytes": 123,
                "actual_size_bytes": "",
                "difference_bytes": "",
                "error_message": "file not found",
            }
        ],
    )

    tasks, already_downloaded = module.load_download_tasks(csv_path)

    assert already_downloaded == 0
    assert tasks == [
        module.DownloadTask(
            local_path=Path("2020/52UFF_wetland_2020.tif"),
            object_key=f"{module.BASE_PREFIX}/2020/52UFF_wetland_2020.tif",
            expected_size_bytes=123,
        )
    ]


def test_load_download_tasks_from_txt_preserves_legacy_behavior(tmp_path: Path) -> None:
    module = _load_script_module()
    txt_path = tmp_path / "corrupted_files_list.txt"
    existing = tmp_path / "2021" / "good.tif"
    missing = tmp_path / "2021" / "bad.tif"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"II*\x00" + b"\x00" * 8)
    txt_path.write_text(f"{existing}\n{missing}\n", encoding="utf-8")

    tasks, already_downloaded = module.load_download_tasks(txt_path)

    assert already_downloaded == 1
    assert tasks == [
        module.DownloadTask(
            local_path=missing,
            object_key=f"{module.BASE_PREFIX}/2021/bad.tif",
            expected_size_bytes=None,
        )
    ]


class _FakeResponse:
    def __init__(self, payload: bytes, content_length: int | None = None) -> None:
        self._payload = payload
        self._offset = 0
        self._content_length = content_length

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._payload) - self._offset
        chunk = self._payload[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def getheader(self, name: str) -> str | None:
        if name.lower() == "content-length" and self._content_length is not None:
            return str(self._content_length)
        return None


def test_download_file_retries_when_downloaded_size_mismatches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    local_path = tmp_path / "2014" / "01WCN_wetland_2014.tif"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    task = module.DownloadTask(
        local_path=local_path,
        object_key=f"{module.BASE_PREFIX}/2014/01WCN_wetland_2014.tif",
        expected_size_bytes=10,
    )

    payloads = [b"1234", b"1234567890"]

    def fake_get_valid_token(force_refresh=False):  # type: ignore[no-untyped-def]
        return "token"

    def fake_get_signed_url(object_key, token):  # type: ignore[no-untyped-def]
        return "https://example.com/file.tif"

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        return _FakeResponse(payloads.pop(0))

    monkeypatch.setattr(module, "get_valid_token", fake_get_valid_token)
    monkeypatch.setattr(module, "get_signed_url", fake_get_signed_url)
    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    path, success, message = module.download_file(task, max_retries=2)

    assert success is True
    assert path == local_path
    assert message == "Success"
    assert local_path.read_bytes() == b"1234567890"


def test_download_file_retries_when_response_content_length_mismatches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    local_path = tmp_path / "2014" / "10WEV_wetland_2014.tif"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    task = module.DownloadTask(
        local_path=local_path,
        object_key=f"{module.BASE_PREFIX}/2014/10WEV_wetland_2014.tif",
        expected_size_bytes=10,
    )

    responses = [
        _FakeResponse(b"1234", content_length=4),
        _FakeResponse(b"1234567890", content_length=10),
    ]

    monkeypatch.setattr(module, "get_valid_token", lambda force_refresh=False: "token")
    monkeypatch.setattr(module, "get_signed_url", lambda object_key, token: "https://example.com/file.tif")
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda request, timeout: responses.pop(0))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    path, success, message = module.download_file(task, max_retries=2, download_timeout=30)

    assert success is True
    assert message == "Success"
    assert path == local_path
    assert local_path.read_bytes() == b"1234567890"
