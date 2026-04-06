# 2026-03-31 Phase 2.6 区域图改为卫星底图 + 两阶段流程

## Summary

- Phase 2.6 区域对比图不再把 `Mean` 放在第 1 个子图。
- 现在第 1 个子图改为 **区域级卫星底图**，当前采用：
  - `MODIS/061/MOD09A1`
  - 对目标年份做全年云掩膜后 `median()` 合成
  - 输出 RGB quicklook JPG
- 整个流程被拆成两个独立步骤：
  1. **下载区域卫星底图**
  2. **读取本地底图并绘制区域对比图**

## Files

- `src/WA/phase26_region_imagery.py`
- `scripts/download_phase2_6_region_imagery.py`
- `src/WA/visualization/phase26.py`
- `scripts/plot_phase2_6_regional_panels.py`
- `tests/test_phase2_6_region_imagery.py`
- `tests/test_phase2_6_regional_panels.py`

## Behavior

- 区域底图默认输出到：
  - `results/phase2.6_region_imagery/2016/<region_id>/<region_id>_modis_rgb.jpg`
- 区域图脚本现在只消费本地底图，不再承担下载职责。
- 如果某个 region 缺少底图，绘图不会报错，而是用空白占位面板继续出图。

## Commands

- 第一步：下载区域卫星底图

```bash
python scripts/download_phase2_6_region_imagery.py
```

- 第二步：绘制区域对比图

```bash
python scripts/plot_phase2_6_regional_panels.py
```

## Verification

- `ruff check src/WA/phase26_region_imagery.py scripts/download_phase2_6_region_imagery.py src/WA/visualization/phase26.py scripts/plot_phase2_6_regional_panels.py tests/test_phase2_6_region_imagery.py tests/test_phase2_6_regional_panels.py`
- `python -m pytest tests/test_phase2_6_region_imagery.py tests/test_phase2_6_regional_panels.py -q`
- `python -m pytest tests/`

结果：`336 passed`

## Notes

- 当前区域底图年份默认跟 Phase 2.6 动态数据默认年份一致，为 `2016`。
- 右侧 colorbar 仍保留两条：
  - `Std`
  - `Wetland Fraction`
- `Mean` 子图已从 2×3 区域图中移除，布局现在是：
  - `MODIS RGB`
  - `Std`
  - 四个 std-eligible 数据集面板
