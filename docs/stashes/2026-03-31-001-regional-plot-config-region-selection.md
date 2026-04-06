# 2026-03-31 Regional plot config-backed region selection

## 变更

- 在 `config/priority_regions.yaml` 新增：
  - `global_tropical_subtropical_35`
  - bbox: `[-180.0, -35.0, 180.0, 35.0]`
- `scripts/plot_tropical_wetland_025deg.py` 改成按 region catalog 读取 bbox，不再写死热带 `±23.5°`。
- 新增参数：
  - `--regions-file`
  - `--region`
- 默认 region 现在是：
  - `global_tropical_subtropical_35`
- 缓存目录和输出文件名都带 `region_id`，避免不同区域互相覆盖。

## 结果

- 同一个脚本现在既能跑全带状热带/亚热带 `±35°`，也能从配置里切换到其他命名区域。
- 绘图范围、loader bbox、裁剪 bbox、coarse 聚合 bbox 都来自同一个 region bbox。

## 验证

- `python -m py_compile scripts/plot_tropical_wetland_025deg.py tests/test_plot_tropical_wetland_025deg.py`
- `ruff check scripts/plot_tropical_wetland_025deg.py tests/test_plot_tropical_wetland_025deg.py`
- `python -m pytest tests/test_plot_tropical_wetland_025deg.py -q`
- `python -m pytest tests/`

结果：全部通过，`312 passed`。
