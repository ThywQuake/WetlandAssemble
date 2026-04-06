# 2026-03-31 Phase 2.6 cache-based entropy and mean wetland outputs

## 变更

- `scripts/run_phase2_6_analysis.py` 改为直接读取 `plot_tropical_wetland_025deg.py` 生成的 `05_coarse_surface.nc` staged cache。
- Phase 2.6 默认输入现在是 HPC 上的 `results/cache/tropical_025deg/<region>/<dataset>/<year>/<resolution>/05_coarse_surface.nc`。
- 输出两个 NetCDF：
  - `phase2_6_stack_<region>_<resolution>.nc`
  - `phase2_6_metrics_<region>_<resolution>.nc`

## 指标

- 此 stash 已被后续实现更新。
- 当前 Phase 2.6 主指标以最新文档为准：
  - `mean_wetland_fraction`
  - `std_wetland_fraction`
  - `participant_count`

## 文件

- `src/WA/comparison/phase26.py`
- `scripts/run_phase2_6_analysis.py`
- `tests/test_phase2_6_analysis.py`

## 验证

- `python -m pytest tests/test_phase2_6_analysis.py -q`
- `ruff check src/WA/comparison/phase26.py scripts/run_phase2_6_analysis.py tests/test_phase2_6_analysis.py`
- `python -m pytest tests/`
