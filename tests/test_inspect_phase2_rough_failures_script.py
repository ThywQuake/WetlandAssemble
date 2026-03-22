from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "inspect_phase2_rough_failures.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_inspect_phase2_rough_failures_script",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Failed to load inspect_phase2_rough_failures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_wrapper_converts_system_exit_to_int(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(module, "_run", lambda: (_ for _ in ()).throw(SystemExit(4)))

    assert module._main() == 4


def test_inspect_phase2_rough_failures_summarizes_failures(tmp_path: Path) -> None:
    module = _load_script_module()
    phase2_root = tmp_path / "results" / "phase2" / "rough"
    run_dir = phase2_root / "mekong_delta" / "201907"
    run_dir.mkdir(parents=True)
    (run_dir / "run_summary.json").write_text(
        json.dumps(
            {
                "status": "completed_with_failures",
                "target_time": "2019-07-01T00:00:00",
                "dataset_results": [
                    {
                        "dataset_id": "glwd_v2",
                        "status": "failed_empty_harmonized_surface",
                        "comparison_source_variable": "combined_classes",
                        "error": (
                            "glwd_v2 produced an empty binary surface from "
                            "combined_classes at prepared_source"
                        ),
                    },
                    {
                        "dataset_id": "gwd30",
                        "status": "participating",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    priority_csv = phase2_root / "landsat_review_priority.csv"
    with priority_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["run_id"])
        writer.writeheader()
        writer.writerow({"run_id": "mekong_delta_201907"})

    summary = module.inspect_phase2_rough_failures(phase2_root, priority_csv=priority_csv)

    assert summary["run_status_counts"]["completed_with_failures"] == 1
    assert summary["dataset_status_counts"]["glwd_v2::failed_empty_harmonized_surface"] == 1
    assert summary["failures"][0]["comparison_source_variable"] == "combined_classes"
    assert summary["failures"][0]["in_priority_review"] is True

    rendered = module.render_inspection_summary(summary)
    assert "mekong_delta_201907" in rendered
    assert "priority_review" in rendered
    assert "combined_classes" in rendered
