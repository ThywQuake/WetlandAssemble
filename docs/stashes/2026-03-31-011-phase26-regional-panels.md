# 2026-03-31 Phase 2.6 regional panels

## Summary

- 新增按 `config/priority_regions.yaml` 批量出图的 Phase 2.6 regional panel 脚本。
- 每个 region 生成一张 **2×3** 对比图：
  - 第 1 格：`Mean`
  - 第 2 格：`Std`
  - 第 3-6 格：四个 std-eligible 数据集的具体湿地百分比
- 当前四个数据集面板固定使用：
  - `GIEMS-MC`
  - `SWAMPS`
  - `TOPMODEL`
  - `WAD2M`
- 版式规则已按需求落实：
  - 所有子图等大
  - 标题简短
  - 只有最左列显示纬度
  - 只有最下行显示经度
  - 所有子图自身不带 colorbar
  - 右侧统一两个 colorbar：`Std` 和 `Wetland Fraction`
  - 所有湿地百分比面板统一 `0-1` 色标
  - 子图间距收紧
  - 总标题只写 region 名称

## Files

- `src/WA/visualization/phase26.py`
- `scripts/plot_phase2_6_regional_panels.py`
- `tests/test_phase2_6_regional_panels.py`

## Verification

- `ruff check src/WA/visualization/phase26.py scripts/plot_phase2_6_regional_panels.py tests/test_phase2_6_regional_panels.py`
- `python -m pytest tests/test_phase2_6_regional_panels.py -q`
- `python -m pytest tests/`

结果：`331 passed`

## Usage

默认从：

- `results/phase2.6/phase2_6_metrics_global_tropical_subtropical_35_0p25deg.nc`
- `results/phase2.6/phase2_6_stack_global_tropical_subtropical_35_0p25deg.nc`

批量输出到：

- `results/figures/phase2.6_regions/<region_id>.png`

示例：

```bash
python scripts/plot_phase2_6_regional_panels.py
```
