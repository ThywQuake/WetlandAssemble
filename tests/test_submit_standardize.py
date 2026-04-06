from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def test_repo_override_updates_default_config_and_python_paths(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "submit_standardize.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo = tmp_path / "WA2"
    (fake_repo / "scripts").mkdir(parents=True)
    (fake_repo / "scripts" / "standardize_datasets.py").write_text(
        "#!/usr/bin/env python\n",
        encoding="utf-8",
    )
    fake_python = fake_repo / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    jobs_base = tmp_path / "jobs"
    tmp_root = tmp_path / "tmp"
    output_dir = tmp_path / "output"

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
            "--output-dir",
            str(output_dir),
            "g2017",
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        check=True,
        capture_output=True,
        text=True,
    )

    expected_config = fake_repo / "config" / "datasets.yaml"
    expected_python = fake_repo / ".venv" / "bin" / "python"
    assert f"Config:       {expected_config}" in completed.stdout
    assert f"Python:       {expected_python}" in completed.stdout

    submit_script = next(jobs_base.glob("std-g2017-*/submit.slurm"))
    content = submit_script.read_text(encoding="utf-8")
    assert str(expected_python) in content
    assert f"--config {expected_config}" in content
    assert f"--metadata-path {submit_script.parent / 'metadata.json'}" in content
    assert "#SBATCH -c 8" in content
    assert "#SBATCH --time=120" in content
    assert "export WA_STANDARDIZE_WORKERS=8" in content
    assert " -v" not in content


def test_verbose_flag_is_opt_in(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "submit_standardize.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo = tmp_path / "WA2"
    (fake_repo / "scripts").mkdir(parents=True)
    (fake_repo / "scripts" / "standardize_datasets.py").write_text(
        "#!/usr/bin/env python\n",
        encoding="utf-8",
    )
    fake_python = fake_repo / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    jobs_base = tmp_path / "jobs"
    tmp_root = tmp_path / "tmp"
    output_dir = tmp_path / "output"

    subprocess.run(
        [
            "bash",
            str(script_path),
            "--dry-run",
            "--verbose",
            "--repo",
            str(fake_repo),
            "--jobs-base",
            str(jobs_base),
            "--tmp-root",
            str(tmp_root),
            "--output-dir",
            str(output_dir),
            "g2017",
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        check=True,
        capture_output=True,
        text=True,
    )

    submit_script = next(jobs_base.glob("std-g2017-*/submit.slurm"))
    content = submit_script.read_text(encoding="utf-8")
    assert " -v" in content


def test_temporal_dataset_splits_into_year_subtasks_by_default(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "submit_standardize.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo = tmp_path / "WA2"
    (fake_repo / "scripts").mkdir(parents=True)
    (fake_repo / "scripts" / "standardize_datasets.py").write_text(
        "#!/usr/bin/env python\n",
        encoding="utf-8",
    )
    fake_python = fake_repo / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    fake_config = tmp_path / "datasets.yaml"
    fake_config.write_text(
        """datasets:
  gwd30:
    name: "GWD30"
    loader_type: "gwd30"
    path: "/tmp/gwd30"
    years:
      - 2013
      - 2014
""",
        encoding="utf-8",
    )

    jobs_base = tmp_path / "jobs"
    tmp_root = tmp_path / "tmp"
    output_dir = tmp_path / "output"

    subprocess.run(
        [
            "bash",
            str(script_path),
            "--dry-run",
            "--repo",
            str(fake_repo),
            "--config",
            str(fake_config),
            "--jobs-base",
            str(jobs_base),
            "--tmp-root",
            str(tmp_root),
            "--output-dir",
            str(output_dir),
            "gwd30",
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        check=True,
        capture_output=True,
        text=True,
    )

    submit_scripts = sorted(jobs_base.glob("std-gwd30-20*/submit.slurm"))
    assert len(submit_scripts) == 2

    contents = [path.read_text(encoding="utf-8") for path in submit_scripts]
    assert any(" --years 2013" in content for content in contents)
    assert any(" --years 2014" in content for content in contents)
    for submit_script, content in zip(submit_scripts, contents, strict=True):
        assert f"--metadata-path {submit_script.parent / 'metadata.json'}" in content
