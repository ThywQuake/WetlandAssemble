# 2026-03-30  Tropical 0.25deg 分阶段缓存

## 背景

为了方便调试热带 `0.25deg` 湿地百分比绘图流程，需要把处理中间产物分阶段落盘，并在后续运行时优先读取已有加工结果，避免重复做 loader 读取、分类提取、时间聚合、裁剪和 coarse 聚合。

## 本次改动

- 在 `scripts/plot_tropical_wetland_025deg.py` 中新增 staged cache 机制。
- 缓存目录默认是 `results/cache/tropical_025deg`。
- 缓存路径按 `dataset / year / resolution` 分层，避免不同参数串扰。
- 当前阶段文件为：
  - `01_loaded_dataset.nc`
  - `02_wetland_surface.nc`
  - `03_aggregated_surface.nc`
  - `04_clipped_surface.nc`
  - `05_coarse_surface.nc`
- 默认行为：
  - 优先读取已存在的最高阶段缓存
  - 缺失时继续向前回溯并重算后续阶段
  - 新生成的阶段数据自动写回缓存
- 新增参数：
  - `--cache-dir`
  - `--no-prefer-cache`
  - `--no-write-cache`
- `loader.load(...)` 返回 `DataArray` 时会先规范为 `Dataset` 再进入缓存链，避免 `WAD2M` 类数据在 staged cache 中断裂。

## 验证

- `python -m py_compile scripts/plot_tropical_wetland_025deg.py tests/test_plot_tropical_wetland_025deg.py`
- `ruff check scripts/plot_tropical_wetland_025deg.py tests/test_plot_tropical_wetland_025deg.py`
- `python -m pytest tests/test_plot_tropical_wetland_025deg.py tests/test_visualization/test_coarse_scale.py -q`
- `python -m pytest tests/`

结果：全部通过，`309 passed`。

## 备注

- 输出目录下的最终 `png + nc` 仍会继续写；staged cache 是额外的调试/复用产物，不替代最终输出。
- 当前缓存是脚本级约定，还没有上升成通用 loader 缓存框架。
