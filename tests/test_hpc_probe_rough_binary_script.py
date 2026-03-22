from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "hpc_probe_rough_binary.py"
    spec = importlib.util.spec_from_file_location("test_hpc_probe_rough_binary_script", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Failed to load hpc_probe_rough_binary.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_wrapper_converts_system_exit_to_int(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(module, "_run", lambda: (_ for _ in ()).throw(SystemExit(3)))

    assert module._main() == 3


def test_main_wrapper_returns_one_for_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module()

    monkeypatch.setattr(module, "_run", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    assert module._main() == 1
