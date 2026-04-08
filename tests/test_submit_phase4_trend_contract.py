from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def _make_fake_repo(tmp_path: Path) -> tuple[Path, Path]:
    fake_repo = tmp_path / "WA"
    (fake_repo / "scripts").mkdir(parents=True)
    (fake_repo / "scripts" / "run_phase4_trend_contract.py").write_text(
        "#!/usr/bin/env python\n",
        encoding="utf-8",
    )
    fake_python = fake_repo / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)
    return fake_repo, fake_python


def test_phase4_trend_contract_submit_generates_one_script_per_region(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "submit_phase4_trend_contract.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo, _fake_python = _make_fake_repo(tmp_path)
    jobs_base = tmp_path / "jobs"
    tmp_root = tmp_path / "tmp"

    completed = subprocess.run(
        [
            "bash",
            str(script_path),
            "--dry-run",
            "--repo",
            str(fake_repo),
            "--jobs-base",
            str(jobs_base),
            "--tmp-root",
            str(tmp_root),
            "--subset",
            "canonical",
            "--dataset-id",
            "gwd30",
            "--dataset-id",
            "wad2m",
            "--cpus",
            "2",
            "--time",
            "360",
            "--partition",
            "C032M0128G",
            "--no-progress",
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Subset:       canonical" in completed.stdout
    assert "Regions:      amazon,pantanal,sudd,borneo" in completed.stdout
    assert "Datasets:     gwd30,wad2m" in completed.stdout
    assert "Skip mode:    --no-skip" in completed.stdout

    submit_scripts = sorted(
        jobs_base.glob("phase4-trend-contract-*-20*/submit.slurm")
    )
    assert len(submit_scripts) == 4

    contents = [path.read_text(encoding="utf-8") for path in submit_scripts]
    assert all("scripts/run_phase4_trend_contract.py" in content for content in contents)
    assert all(" --dataset-id gwd30" in content for content in contents)
    assert all(" --dataset-id wad2m" in content for content in contents)
    assert all(" --no-skip" in content for content in contents)
    assert all("#SBATCH -c 2" in content for content in contents)
    assert all("#SBATCH --time=360" in content for content in contents)
    assert all("#SBATCH --partition=C032M0128G" in content for content in contents)
    assert any(" --region amazon" in content for content in contents)
    assert any(" --region pantanal" in content for content in contents)
    assert any(" --region sudd" in content for content in contents)
    assert any(" --region borneo" in content for content in contents)

    summary_files = sorted(jobs_base.glob("phase4-trend-contract-*.tsv"))
    assert len(summary_files) == 1
    summary_text = summary_files[0].read_text(encoding="utf-8")
    assert "region\tjob_name\tjob_id\tscript" in summary_text
    assert "amazon" in summary_text
    assert "borneo" in summary_text
    assert "dry-run" in summary_text


def test_phase4_trend_contract_submit_requires_repo_and_rejects_mixed_selector_flags(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "submit_phase4_trend_contract.sh"

    missing_repo = subprocess.run(
        ["bash", str(script_path), "--dry-run"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing_repo.returncode != 0
    assert "--repo is required" in missing_repo.stderr

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo, _fake_python = _make_fake_repo(tmp_path)
    mixed = subprocess.run(
        [
            "bash",
            str(script_path),
            "--dry-run",
            "--repo",
            str(fake_repo),
            "--subset",
            "canonical",
            "--region",
            "amazon",
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert mixed.returncode != 0
    assert "either --subset or --region" in mixed.stderr
