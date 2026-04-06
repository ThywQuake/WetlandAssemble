# 2026-03-31 Phase 2.6 std eligible subset

## Summary

- 回退并收紧了 Phase 2.6 的 Rough 尺度 `std` 参与口径。
- 现在：
  - `mean_wetland_fraction` 仍基于所有已加载数据集计算
  - `std_wetland_fraction` 和 `participant_count` 改为只基于适合 Rough 尺度比较的子集
- 当前默认从 `std` 中排除：
  - `berkeley_rwawc`
  - `g2017`
  - `glwd_v2`

## Why

- `Berkeley` 是辅助水体产品；
- `G2017`、`GLWD v2` 与动态粗尺度湿地百分比产品的产品性质不同；
- 把它们继续放进 Rough 尺度 `std` 会让分歧度量失真。

## Files

- `src/WA/comparison/phase26.py`
- `scripts/run_phase2_6_analysis.py`
- `tests/test_phase2_6_analysis.py`
- `docs/phase2_6_metrics_explained.md`

## Verification

- `ruff check src/WA/comparison/phase26.py scripts/run_phase2_6_analysis.py tests/test_phase2_6_analysis.py`
- `python -m pytest tests/test_phase2_6_analysis.py -q`
- `python -m pytest tests/`

结果：`327 passed`

## Notes

- `participant_count` 现在表示的是 **参与 `std_wetland_fraction` 计算的数据集数**，不再是“所有已加载数据集数”。
- `metrics.nc` 里新增了 `std_dataset_ids_json`、`std_dataset_count`、`std_excluded_dataset_ids_json` 等 attrs，方便后续绘图和解释口径。
