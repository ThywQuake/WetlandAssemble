from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def test_phase4_gwd30_pixel_stats_submit_generates_one_script_per_year(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "submit_phase4_gwd30_pixel_stats.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo = tmp_path / "WA2"
    (fake_repo / "scripts").mkdir(parents=True)
    (fake_repo / "scripts" / "build_phase4_gwd30_pixel_stats.py").write_text(
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

    completed = subprocess.run(
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
            "--aggregation",
            "annual",
            "--worker-count",
            "1",
            "--cpus",
            "2",
            "--time",
            "360",
            "--partition",
            "C032M0128G",
            "--no-skip",
            "--no-progress",
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Years:        2013,2014" in completed.stdout
    assert "Aggregation:  annual" in completed.stdout
    assert "Workers:      1" in completed.stdout
    assert "CPUs:         2" in completed.stdout

    submit_scripts = sorted(jobs_base.glob("phase4-gwd30-pixel-stats-20*/submit.slurm"))
    assert len(submit_scripts) == 2

    contents = [path.read_text(encoding="utf-8") for path in submit_scripts]
    assert all("scripts/build_phase4_gwd30_pixel_stats.py" in content for content in contents)
    assert all("#SBATCH -c 2" in content for content in contents)
    assert all("#SBATCH --time=360" in content for content in contents)
    assert all("#SBATCH --partition=C032M0128G" in content for content in contents)
    assert all(" --aggregation annual" in content for content in contents)
    assert all(" --worker-count 1" in content for content in contents)
    assert all(" --no-skip" in content for content in contents)
    assert all(" --no-progress" in content for content in contents)
    assert any(" --year 2013" in content for content in contents)
    assert any(" --year 2014" in content for content in contents)
