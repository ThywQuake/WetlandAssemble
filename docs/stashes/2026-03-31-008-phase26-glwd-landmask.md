# 2026-03-31 Phase 2.6 GLWD landmask

## Summary

- Phase 2.6 现在在计算前会先使用 `GLWD v2` 当前有效范围作为统一 landmask。
- 具体规则是：以 `glwd_v2` 的 `05_coarse_surface.nc` 中 **非空单元** 为有效域，对其余数据集进行统一框定。
- 这样可以去掉部分数据集在海洋上的异常非空值，避免这些值进入 `mean_wetland_fraction` 和 `std_wetland_fraction`。

## Files

- `src/WA/comparison/phase26.py`
- `scripts/run_phase2_6_analysis.py`
- `tests/test_phase2_6_analysis.py`
- `docs/phase2_6_metrics_explained.md`

## Verification

- `ruff check src/WA/comparison/phase26.py scripts/run_phase2_6_analysis.py tests/test_phase2_6_analysis.py`
- `python -m pytest tests/test_phase2_6_analysis.py -q`
- `python -m pytest tests/`

结果：`321 passed`

## Notes

- 当前实现要求 `Phase 2.6` 输入缓存里必须包含 `glwd_v2`，否则脚本会直接报错，不会在缺少 landmask 的情况下继续输出结果。
- 这里用的是“GLWD 当前有效范围”，不是把 `GLWD` 当作湿地真值；它只负责限定统计空间范围。
