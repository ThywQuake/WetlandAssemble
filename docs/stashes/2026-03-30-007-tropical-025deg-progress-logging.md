# 2026-03-30 Tropical 0.25deg progress logging

## 目的

给 `scripts/plot_tropical_wetland_025deg.py` 增加明确的阶段日志，方便在 HPC 上追踪脚本进度、判断当前是在命中缓存还是重新加工。

## 新增日志点

- 运行入口打印：
  - `output_dir`
  - `cache_dir`
  - `resolution_deg`
  - `prefer_cache`
  - `write_cache`
- 每个数据集打印：
  - 目标年份
  - staged cache 根目录
  - `01_loaded_dataset` 到 `05_coarse_surface` 各阶段的 cache hit / miss
  - 从 loader 读取源数据
  - 提取湿地变量
  - 时间筛选
  - 非空间维聚合
  - 热带 bbox 裁剪
  - 粗尺度面积加权聚合
  - 各阶段缓存写盘完成
  - 最终 `nc` 输出写盘
  - cartopy 是否启用
  - 最终 `png` 输出写盘
  - pipeline 完成及解析出的实际年份

## 验证

- `python -m py_compile scripts/plot_tropical_wetland_025deg.py tests/test_plot_tropical_wetland_025deg.py`
- `ruff check scripts/plot_tropical_wetland_025deg.py tests/test_plot_tropical_wetland_025deg.py`
- `python -m pytest tests/`

结果：全部通过，`310 passed`。
