from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _toolchain_python(repo_root: Path) -> Path:
    candidate = repo_root / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def _make_fake_repo(tmp_path: Path, *, delegate_python: Path) -> tuple[Path, Path]:
    fake_repo = tmp_path / "WA"
    (fake_repo / "scripts").mkdir(parents=True)
    (fake_repo / "scripts" / "run_phase4_trend_contract.py").write_text(
        "#!/usr/bin/env python\n",
        encoding="utf-8",
    )
    fake_python = fake_repo / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text(
        f"#!/bin/bash\nexec \"{delegate_python}\" \"$@\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)
    return fake_repo, fake_python


def test_phase4_trend_contract_submit_generates_one_script_per_region(
    tmp_path: Path,
) -> None:
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "submit_phase4_trend_contract.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo, _fake_python = _make_fake_repo(
        tmp_path,
        delegate_python=_toolchain_python(repo_root),
    )
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
    assert "Participant set key: gwd30+wad2m" in completed.stdout
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
    repo_root = _repo_root()
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
    fake_repo, _fake_python = _make_fake_repo(
        tmp_path,
        delegate_python=_toolchain_python(repo_root),
    )
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


def test_phase4_trend_contract_submit_dry_run_uses_python_bin_for_region_resolution(
    tmp_path: Path,
) -> None:
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "submit_phase4_trend_contract.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo, fake_python = _make_fake_repo(
        tmp_path,
        delegate_python=_toolchain_python(repo_root),
    )
    jobs_base = tmp_path / "jobs"
    tmp_root = tmp_path / "tmp"
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_system_python = fake_bin / "python3"
    fake_system_python.write_text(
        "#!/bin/bash\necho 'stub python3 should not be used' >&2\nexit 41\n",
        encoding="utf-8",
    )
    fake_system_python.chmod(fake_system_python.stat().st_mode | stat.S_IXUSR)

    completed = subprocess.run(
        [
            "bash",
            str(script_path),
            "--dry-run",
            "--repo",
            str(fake_repo),
            "--python-bin",
            str(fake_python),
            "--jobs-base",
            str(jobs_base),
            "--tmp-root",
            str(tmp_root),
            "--subset",
            "canonical",
            "--no-progress",
        ],
        cwd=repo_root,
        env={
            **os.environ,
            "HOME": str(fake_home),
            "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
        },
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Subset:       canonical" in completed.stdout
    assert "stub python3 should not be used" not in completed.stderr


def test_phase4_trend_contract_submit_rejects_duplicate_dataset_ids_before_fanout(
    tmp_path: Path,
) -> None:
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "submit_phase4_trend_contract.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo, fake_python = _make_fake_repo(
        tmp_path,
        delegate_python=_toolchain_python(repo_root),
    )
    jobs_base = tmp_path / "jobs"
    tmp_root = tmp_path / "tmp"

    completed = subprocess.run(
        [
            "bash",
            str(script_path),
            "--dry-run",
            "--repo",
            str(fake_repo),
            "--python-bin",
            str(fake_python),
            "--jobs-base",
            str(jobs_base),
            "--tmp-root",
            str(tmp_root),
            "--subset",
            "ten",
            "--dataset-id",
            "gwd30",
            "--dataset-id",
            "gwd30",
            "--no-progress",
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "Invalid --dataset-id values: participant_ids must not contain duplicates" in (
        completed.stderr + completed.stdout
    )
    assert not jobs_base.exists()


def test_phase4_trend_contract_submit_defaults_keep_topmodel_and_account_for_ten_regions(
    tmp_path: Path,
) -> None:
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "submit_phase4_trend_contract.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo, fake_python = _make_fake_repo(
        tmp_path,
        delegate_python=_toolchain_python(repo_root),
    )
    jobs_base = tmp_path / "jobs"
    tmp_root = tmp_path / "tmp"

    completed = subprocess.run(
        [
            "bash",
            str(script_path),
            "--dry-run",
            "--repo",
            str(fake_repo),
            "--python-bin",
            str(fake_python),
            "--jobs-base",
            str(jobs_base),
            "--tmp-root",
            str(tmp_root),
            "--subset",
            "ten",
            "--no-progress",
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Datasets:     gwd30,giems_mc,topmodel,swamps,wad2m" in completed.stdout
    assert (
        "Participant set key: giems_mc+gwd30+swamps+topmodel+wad2m"
        in completed.stdout
    )
    assert "Regions:      amazon,orinoco,pantanal,indogangetic,mekong,sudd,congo,okavango,borneo,northernaus" in completed.stdout

    submit_scripts = sorted(
        jobs_base.glob("phase4-trend-contract-*-20*/submit.slurm")
    )
    assert len(submit_scripts) == 10

    summary_files = sorted(jobs_base.glob("phase4-trend-contract-*.tsv"))
    assert len(summary_files) == 1
    summary_lines = summary_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(summary_lines) == 11
    assert summary_lines[0] == "region\tjob_name\tjob_id\tscript"
    assert summary_lines[1].startswith("amazon\t")
    assert summary_lines[-1].startswith("northernaus\t")


def test_phase4_trend_contract_submit_supports_single_region_debug_reruns(
    tmp_path: Path,
) -> None:
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "submit_phase4_trend_contract.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo, fake_python = _make_fake_repo(
        tmp_path,
        delegate_python=_toolchain_python(repo_root),
    )
    jobs_base = tmp_path / "jobs"
    tmp_root = tmp_path / "tmp"

    completed = subprocess.run(
        [
            "bash",
            str(script_path),
            "--dry-run",
            "--repo",
            str(fake_repo),
            "--python-bin",
            str(fake_python),
            "--jobs-base",
            str(jobs_base),
            "--tmp-root",
            str(tmp_root),
            "--region",
            "amazon",
            "--no-progress",
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Subset:       explicit-region-list" in completed.stdout
    assert "Regions:      amazon" in completed.stdout

    submit_scripts = sorted(
        jobs_base.glob("phase4-trend-contract-*-20*/submit.slurm")
    )
    assert len(submit_scripts) == 1
    assert " --region amazon" in submit_scripts[0].read_text(encoding="utf-8")

    summary_files = sorted(jobs_base.glob("phase4-trend-contract-*.tsv"))
    assert len(summary_files) == 1
    summary_lines = summary_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(summary_lines) == 2
    assert summary_lines[1].startswith("amazon\t")


def test_phase4_trend_contract_submit_rejects_bad_repo_and_bad_python_bin(
    tmp_path: Path,
) -> None:
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "submit_phase4_trend_contract.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo, _fake_python = _make_fake_repo(
        tmp_path,
        delegate_python=_toolchain_python(repo_root),
    )
    bad_repo = tmp_path / "missing-repo"
    bad_python = tmp_path / "missing-python"

    missing_repo = subprocess.run(
        [
            "bash",
            str(script_path),
            "--dry-run",
            "--repo",
            str(bad_repo),
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing_repo.returncode != 0
    assert f"Missing: {bad_repo}/scripts/run_phase4_trend_contract.py" in missing_repo.stderr

    bad_python_run = subprocess.run(
        [
            "bash",
            str(script_path),
            "--dry-run",
            "--repo",
            str(fake_repo),
            "--python-bin",
            str(bad_python),
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad_python_run.returncode != 0
    assert f"Missing executable python: {bad_python}" in bad_python_run.stderr
