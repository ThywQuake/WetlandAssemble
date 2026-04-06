# Tropical 0.25deg Plot: Simple Titles and Overview Figure

## Summary

- 单数据集 `png` 标题缩短为仅显示数据集简称，不再拼接区域名和年份。
- 同一次运行结束后，脚本会额外生成一个纵向总览图：
  - 按本次成功处理的数据集顺序自上而下堆叠
  - 所有子图共用右侧单一 colorbar
  - 输出文件名：`overview_{region_id}_025deg.png`

## Files

- `scripts/plot_tropical_wetland_025deg.py`
- `tests/test_plot_tropical_wetland_025deg.py`

## Verification

- `python -m py_compile scripts/plot_tropical_wetland_025deg.py tests/test_plot_tropical_wetland_025deg.py`
- `ruff check scripts/plot_tropical_wetland_025deg.py tests/test_plot_tropical_wetland_025deg.py`
- `python -m pytest tests/test_plot_tropical_wetland_025deg.py -q`
- `python -m pytest tests/`

## Result

- 全量测试通过：`316 passed`
