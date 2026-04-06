# 2026-03-30 Tropical 0.25deg HPC netCDF attr fix

## 问题

HPC 运行 `scripts/plot_tropical_wetland_025deg.py` 时，所有数据集都在写 `nc` 阶段失败：

- `TypeError: Invalid value for attr 'semantic_mapping'`

根因是 staged cache 和最终输出都直接调用 `to_netcdf()`，而 loader 产物里的 `semantic_mapping` 是 `dict`，不符合 netCDF attr 类型约束。

## 修复

- 在 `scripts/plot_tropical_wetland_025deg.py` 中新增本地 attr sanitize：
  - `dict` -> 稳定 JSON 字符串
  - 嵌套 `list/tuple` -> JSON 字符串
  - `bool` -> `int`
  - 丢弃 `None`
- staged cache 的 dataset/dataarray 写盘全部先 sanitize。
- 最终输出 `wetland_fraction.nc` 也先 sanitize 再写。
- `save_surface_plot()` 调整为：
  1. 先写 `nc`
  2. 再画图并写 `png`

这样即使 `png` 失败，处理后的 `nc` 也已经保留下来。

## 验证

- `python -m py_compile scripts/plot_tropical_wetland_025deg.py tests/test_plot_tropical_wetland_025deg.py`
- `ruff check scripts/plot_tropical_wetland_025deg.py tests/test_plot_tropical_wetland_025deg.py`
- `python -m pytest tests/test_plot_tropical_wetland_025deg.py tests/test_visualization/test_coarse_scale.py -q`
- `python -m pytest tests/`

结果：全部通过，`310 passed`。
