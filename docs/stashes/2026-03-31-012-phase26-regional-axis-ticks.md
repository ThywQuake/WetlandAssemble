# 2026-03-31 Phase 2.6 regional panel 经纬度刻度修复

## Summary

- 修复了 Phase 2.6 区域对比图“只有轴标题、没有经纬度数值刻度”的问题。
- 现在区域图会按需求显示：
  - 只有最左列显示纬度刻度
  - 只有最下行显示经度刻度
- 刻度值会根据 region bbox 自动挑选较简洁的步长，避免小区域出现过密刻度。

## Files

- `src/WA/visualization/phase26.py`
- `tests/test_phase2_6_regional_panels.py`

## Verification

- `ruff check src/WA/visualization/phase26.py tests/test_phase2_6_regional_panels.py`
- `python -m pytest tests/test_phase2_6_regional_panels.py -q`
- `python -m pytest tests/`

结果：`333 passed`

## Notes

- 这次修复主要针对 `plot_phase2_6_regional_panels.py` 生成的 2×3 区域图。
- 之前代码只设置了 `Latitude` / `Longitude` 轴标题，但没有真正配置经纬度刻度与显示规则。
