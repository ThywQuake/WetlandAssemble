from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def test_phase4_gwd30_tropical_submit_generates_task_array_and_reduce_scripts(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "submit_phase4_gwd30_tropical_shards.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo = tmp_path / "WA2"
    (fake_repo / "scripts").mkdir(parents=True)
    for script_name in (
        "build_phase4_gwd30_shard_lists.py",
        "run_phase4_gwd30_tropical_shard.py",
        "reduce_phase4_gwd30_tropical_shards.py",
    ):
        (fake_repo / "scripts" / script_name).write_text(
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
            "--task-lists",
            "12",
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Task lists:      12" in completed.stdout

    task_scripts = sorted(jobs_base.glob("phase4-gwd30-trop-task-20*/submit.slurm"))
    reduce_scripts = sorted(jobs_base.glob("phase4-gwd30-trop-reduce-20*/submit.slurm"))
    assert len(task_scripts) == 2
    assert len(reduce_scripts) == 2

    task_contents = [path.read_text(encoding="utf-8") for path in task_scripts]
    reduce_contents = [path.read_text(encoding="utf-8") for path in reduce_scripts]

    assert all("#SBATCH --array=0-11" in content for content in task_contents)
    assert all("scripts/run_phase4_gwd30_tropical_shard.py" in content for content in task_contents)
    assert all("manifest_list_*.txt" in content for content in task_contents)
    assert all("--phase36-cache-dir" not in content for content in task_contents)
    assert all("--worker-count 4" in content for content in task_contents)
    assert any(" --year 2013" in content for content in task_contents)
    assert any(" --year 2014" in content for content in task_contents)

    assert all(
        "scripts/reduce_phase4_gwd30_tropical_shards.py" in content
        for content in reduce_contents
    )
    assert all("--phase36-cache-dir" in content for content in reduce_contents)
    assert all("--worker-count 4" in content for content in reduce_contents)
    assert any(" --year 2013" in content for content in reduce_contents)
    assert any(" --year 2014" in content for content in reduce_contents)
