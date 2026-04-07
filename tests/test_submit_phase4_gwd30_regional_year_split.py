from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def test_phase4_gwd30_regional_year_split_submit_generates_year_and_merge_scripts(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "submit_phase4_gwd30_regional_year_split.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo = tmp_path / "WA2"
    (fake_repo / "scripts").mkdir(parents=True)
    (fake_repo / "scripts" / "run_phase4_regional.py").write_text(
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
    name: \"GWD30\"
    loader_type: \"gwd30\"
    path: \"/tmp/gwd30\"
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
            "--region",
            "pan_trop_subtrop",
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

    assert "Region:       pan_trop_subtrop" in completed.stdout
    assert "Years:        2013,2014" in completed.stdout

    year_scripts = sorted(
        jobs_base.glob("phase4-gwd30-region-pan_trop_subtrop-20*/submit.slurm")
    )
    merge_scripts = sorted(
        jobs_base.glob("phase4-gwd30-region-merge-pan_trop_subtrop-20*/submit.slurm")
    )
    assert len(year_scripts) == 2
    assert len(merge_scripts) == 1

    year_contents = [path.read_text(encoding="utf-8") for path in year_scripts]
    merge_content = merge_scripts[0].read_text(encoding="utf-8")

    assert all("scripts/run_phase4_regional.py" in content for content in year_contents)
    assert all(" --dataset-id gwd30" in content for content in year_contents)
    assert all(" --region pan_trop_subtrop" in content for content in year_contents)
    assert all(" --no-skip" in content for content in year_contents)
    assert all(" --no-progress" in content for content in year_contents)
    assert any(" --start-year 2013 --end-year 2013" in content for content in year_contents)
    assert any(" --start-year 2014 --end-year 2014" in content for content in year_contents)

    assert "scripts/run_phase4_regional.py" in merge_content
    assert " --dataset-id gwd30" in merge_content
    assert " --region pan_trop_subtrop" in merge_content
    assert " --start-year 2013 --end-year 2014" in merge_content
    assert " --no-skip" not in merge_content
    assert "#SBATCH --dependency=afterok:" not in merge_content
