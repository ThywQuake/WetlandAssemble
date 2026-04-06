# submit_standardize HPC 路径修复

**Date:** 2026-03-27  
**Branch:** `refactor/loader-reference-grid-alignment`

## 修复内容

- `scripts/submit_standardize.sh`
  - 默认优先用当前工作目录作为 `REPO`（若其中存在 `scripts/standardize_datasets.py`），否则回退到脚本所在仓库
  - 新增 `--python-bin` / `PYTHON_BIN`，默认使用 `${REPO}/.venv/bin/python`
  - 生成 SLURM 脚本时不再 `source .venv/bin/activate`，改为直接调用 venv 里的 Python
  - 提交前增加 `REPO` / `PYTHON_BIN` 存在性检查，路径不对时立刻报错
  - 运行时临时目录继续固定到 `~/temp`

## Why

用户在 HPC 上遇到：

- `cd` 到了错误仓库（不是 `WA2`）
- `.venv/bin/activate` 不存在
- `python` 不在 compute node 的 PATH 中

直接使用 `${REPO}/.venv/bin/python` 更稳，也更少依赖 shell 环境。

## 建议用法

- `bash scripts/submit_standardize.sh --repo /lustre/home/2200013429/repos/WA2 glwd berkeley`
- 如有必要：`bash scripts/submit_standardize.sh --repo /lustre/home/2200013429/repos/WA2 --python-bin /lustre/home/2200013429/repos/WA2/.venv/bin/python glwd`
