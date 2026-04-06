from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def test_gwd30_sharded_submit_generates_stage_array_and_merge_scripts(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "submit_gwd30_sharded.sh"

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_repo = tmp_path / "WA2"
    (fake_repo / "scripts").mkdir(parents=True)
    (fake_repo / "scripts" / "standardize_datasets.py").write_text(
        "#!/usr/bin/env python\n",
        encoding="utf-8",
    )
    (fake_repo / "scripts" / "run_gwd30_stage_shard.py").write_text(
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
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        env={**os.environ, "HOME": str(fake_home)},
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Stage shards:    64" in completed.stdout

    stage_scripts = sorted(jobs_base.glob("std-gwd30-stage-20*/submit.slurm"))
    merge_scripts = sorted(jobs_base.glob("std-gwd30-merge-20*/submit.slurm"))
    assert len(stage_scripts) == 2
    assert len(merge_scripts) == 2

    stage_contents = [path.read_text(encoding="utf-8") for path in stage_scripts]
    merge_contents = [path.read_text(encoding="utf-8") for path in merge_scripts]

    assert all("#SBATCH --array=0-63" in content for content in stage_contents)
    assert all("scripts/run_gwd30_stage_shard.py" in content for content in stage_contents)
    assert all(" --shard-count 64" in content for content in stage_contents)
    assert all('--shard-index "${SLURM_ARRAY_TASK_ID}"' in content for content in stage_contents)
    assert all(" --skip-existing" in content for content in stage_contents)

    assert any(" --year 2013" in content for content in stage_contents)
    assert any(" --year 2014" in content for content in stage_contents)
    assert all("scripts/standardize_datasets.py" in content for content in merge_contents)
    assert all(" --datasets gwd30" in content for content in merge_contents)
    assert any(" --years 2013" in content for content in merge_contents)
    assert any(" --years 2014" in content for content in merge_contents)
