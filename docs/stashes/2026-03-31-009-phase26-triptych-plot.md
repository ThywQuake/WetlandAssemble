# 2026-03-31 Phase 2.6 triptych plot

## Summary

- 新增 Phase 2.6 三联图绘图支持，布局为 **三行一列**：
  - `Mean Wetland Fraction`
  - `Std Wetland Fraction`
  - `Participant Count`
- `Participant Count` 现在按整数离散绘制：
  - 先把值取整到整数计数
  - `0` 统一转为 `NaN`，不在图上显示
  - colorbar 使用“一整数一颜色”的离散分级，而不是连续渐变
- 三个子图的垂直间距已收紧，便于整体对比。

## Files

- `src/WA/visualization/phase26.py`
- `scripts/plot_phase2_6_metrics.py`
- `tests/test_phase2_6_plotting.py`

## Verification

- `ruff check src/WA/visualization/phase26.py scripts/plot_phase2_6_metrics.py tests/test_phase2_6_plotting.py`
- `python -m pytest tests/test_phase2_6_plotting.py -q`
- `python -m pytest tests/`

结果：`325 passed`

## Usage

- 默认输入：
  - `results/phase2.6/phase2_6_metrics_global_tropical_subtropical_35_0p25deg.nc`
- 默认输出：
  - `results/figures/phase2.6/phase2_6_triptych_global_tropical_subtropical_35_0p25deg.png`

示例：

```bash
python scripts/plot_phase2_6_metrics.py
```
