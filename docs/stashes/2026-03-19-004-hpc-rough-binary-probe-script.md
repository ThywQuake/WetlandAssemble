# HPC Rough Binary Probe Script — 摘要

**日期:** 2026-03-19
**分支:** `feat/phase2-rough-binary-modis-truth`
**状态:** 粗尺度 HPC 诊断脚本完成

## Architecture decisions

- 新增独立的 rough probe helper：`src/WA/rough_probe.py`
- 新增 HPC 入口脚本：`scripts/hpc_probe_rough_binary.py`
- 复用 `loader_probe.py` 的风格与通用能力：
  - safe bbox / region 解析
  - dataset selection
  - discovery diagnostics
  - JSON-safe pretty report
- 默认行为是 “rough comparison 诊断优先”，不是自动下载 MODIS。
- MODIS 下载通过 `--download-modis` 显式开启，避免无 GEE 凭据时脚本失去诊断价值。
- 默认 target month 使用“MODIS 可用且 dynamic participant 数量最大的最早月份”，当前策略会优先落到 `2000-03-01` 一类窗口，而不是硬编码某一个数据集年份。

## Modified files and key changes

- `src/WA/rough_probe.py`
  新增 rough probe 主逻辑：
  - target time 推导
  - per-dataset status probing
  - rough harmonization + comparison
  - disagreement / focus AOI 摘要
  - optional MODIS artifacts
  - terminal report rendering
- `scripts/hpc_probe_rough_binary.py`
  新增 HPC CLI entrypoint
- `tests/test_rough_probe.py`
  新增 rough probe 单元测试
- `todos/004-complete-p1-build-hpc-rough-binary-probe-script.md`
  完成本轮 todo

## Verification status

- `uv run python scripts/hpc_probe_rough_binary.py --help`: pass
- `uv run pytest -q`: pass (`43 passed, 1 warning`)
- `uv run ruff check .`: pass
- `uv run mypy src tests`: pass

已知 warning:
- `numpy.ndarray size changed, may indicate binary incompatibility`
  仍来自 Berkeley loader 测试，和本次 rough probe 无直接关系。

## Useful HPC commands

- 默认安全探测：
  - `uv run python scripts/hpc_probe_rough_binary.py`
- 指定区域和月份：
  - `uv run python scripts/hpc_probe_rough_binary.py --region tropical --target-time 2019-07-01`
- 指定数据集：
  - `uv run python scripts/hpc_probe_rough_binary.py --dataset g2017,wad2m,swamps`
- 同时导出 JSON：
  - `uv run python scripts/hpc_probe_rough_binary.py --json-out temp/rough_probe.json`
- 需要连带测试 MODIS：
  - `uv run python scripts/hpc_probe_rough_binary.py --download-modis`

## Open risks, TODOs, rollback notes

- 当前脚本会在 `run_rough_probe()` 内重新 prepare loaders 一次；这只是效率问题，不影响结果正确性。
- MODIS 下载仍沿用同步 small-chip 优先策略；大 AOI 还没有真正的 `Export.image.*` fallback。
- 如果后续要把 rough probe 接入 batch HPC job，建议下一步加：
  - TSV/CSV metrics export
  - focus AOI table export
  - manifest 对接
