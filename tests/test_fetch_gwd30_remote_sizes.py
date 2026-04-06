from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "fetch_gwd30_remote_sizes.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_fetch_gwd30_remote_sizes_script",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Failed to load fetch_gwd30_remote_sizes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_fetch_page_posts_expected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module()
    captured: dict[str, object] = {}

    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/curl")

    def fake_run(command, check, capture_output, text):  # type: ignore[no-untyped-def]
        captured["command"] = command
        assert check is True
        assert capture_output is True
        assert text is True
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=json.dumps(
                {
                    "response": [
                        {"file": "01KAA_wetland_2013.tif", "gid": 1, "size": 3331184},
                    ],
                    "total": 1,
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    records, total = module.fetch_page(
        endpoint=module.DEFAULT_ENDPOINT,
        table="rs_gwd",
        year=2013,
        page=1,
        count=50000,
        timeout=45,
        max_retries=1,
    )

    command = captured["command"]
    assert isinstance(command, list)
    assert command[:3] == ["curl", module.DEFAULT_ENDPOINT, "-X"]
    assert "--max-time" in command
    payload = json.loads(command[-1])
    assert payload == {
        "params": {
            "table": "rs_gwd",
            "path": "GWD30/2013",
            "page": 1,
            "enableSpatialQuery": False,
            "count": 50000,
        }
    }
    assert records[0].relative_path == "2013/01KAA_wetland_2013.tif"
    assert records[0].size_bytes == 3331184
    assert total == 1


def test_fetch_gwd30_remote_sizes_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module()
    calls: list[tuple[int, int]] = []

    def fake_fetch_page(**kwargs):  # type: ignore[no-untyped-def]
        year = kwargs["year"]
        page = kwargs["page"]
        calls.append((year, page))
        if page == 1:
            return (
                [
                    module.RemoteSizeRecord(
                        year=year,
                        file_name=f"a_wetland_{year}.tif",
                        relative_path=f"{year}/a_wetland_{year}.tif",
                        size_bytes=10,
                        gid=1,
                    ),
                    module.RemoteSizeRecord(
                        year=year,
                        file_name=f"b_wetland_{year}.tif",
                        relative_path=f"{year}/b_wetland_{year}.tif",
                        size_bytes=20,
                        gid=2,
                    ),
                ],
                3,
            )
        return (
            [
                module.RemoteSizeRecord(
                    year=year,
                    file_name=f"c_wetland_{year}.tif",
                    relative_path=f"{year}/c_wetland_{year}.tif",
                    size_bytes=30,
                    gid=3,
                ),
            ],
            3,
        )

    monkeypatch.setattr(module, "fetch_page", fake_fetch_page)

    records = module.fetch_gwd30_remote_sizes(
        years=[2021],
        endpoint="https://example.com",
        table="rs_gwd",
        count=2,
        timeout=60,
        max_retries=1,
    )

    assert calls == [(2021, 1), (2021, 2)]
    assert [record.relative_path for record in records] == [
        "2021/a_wetland_2021.tif",
        "2021/b_wetland_2021.tif",
        "2021/c_wetland_2021.tif",
    ]


def test_write_size_manifest_outputs_json_csv_and_summary(tmp_path: Path) -> None:
    module = _load_script_module()
    records = [
        module.RemoteSizeRecord(
            year=2013,
            file_name="01KAA_wetland_2013.tif",
            relative_path="2013/01KAA_wetland_2013.tif",
            size_bytes=3331184,
            gid=1,
        ),
        module.RemoteSizeRecord(
            year=2014,
            file_name="01KAA_wetland_2014.tif",
            relative_path="2014/01KAA_wetland_2014.tif",
            size_bytes=444,
            gid=2,
        ),
    ]

    outputs = module.write_size_manifest(
        records,
        output_dir=tmp_path / "manifest",
        years=[2013, 2014],
        endpoint="https://example.com",
        table="rs_gwd",
        count=50000,
    )

    summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
    csv_lines = outputs["csv"].read_text(encoding="utf-8").splitlines()
    json_payload = json.loads(outputs["json"].read_text(encoding="utf-8"))

    assert summary["total_files"] == 2
    assert summary["total_size_bytes"] == 3331628
    assert summary["per_year_counts"] == {"2013": 1, "2014": 1}
    assert csv_lines[0] == "year,file_name,relative_path,size_bytes,gid"
    assert json_payload[0]["relative_path"] == "2013/01KAA_wetland_2013.tif"


def test_run_uses_config_years_and_writes_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module()
    monkeypatch.setattr(module, "resolve_years", lambda years, dataset_config_path: [2013, 2014])
    monkeypatch.setattr(
        module,
        "fetch_gwd30_remote_sizes",
        lambda **kwargs: [
            module.RemoteSizeRecord(
                year=2013,
                file_name="01KAA_wetland_2013.tif",
                relative_path="2013/01KAA_wetland_2013.tif",
                size_bytes=3331184,
                gid=1,
            )
        ],
    )

    exit_code = module._run(["--output-dir", str(tmp_path / "manifest")])

    assert exit_code == 0
    assert (tmp_path / "manifest" / "gwd30_remote_sizes.csv").exists()
    assert (tmp_path / "manifest" / "gwd30_remote_sizes.json").exists()
    assert (tmp_path / "manifest" / "summary.json").exists()
