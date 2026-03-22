# GWD30 临时瓦片镶嵌 OOM 硬化 — 摘要

**日期:** 2026-03-19
**分支:** `feat/phase2-rough-binary-modis-truth`
**状态:** GWD30 rough load 改为逐 tile 降采样落盘 + 最终镶嵌；本地定向验证通过

## Architecture decisions

- `GWD30Loader.load_rough_binary_surface()` 不再把每个 tile 直接作为 `xarray/rioxarray` 对象留在内存里累计。
- 新策略改为：
  1. 逐 tile 打开原始 GeoTIFF；
  2. 在源分辨率上完成月内时间聚合；
  3. 立刻重投影/降采样到 coarse reference grid；
  4. 将该 coarse tile 写入临时 GeoTIFF；
  5. 关闭原始文件并释放中间数组；
  6. 最后再把这些处理后的临时 coarse tile 做平均镶嵌。
- 这样把峰值内存从“多 tile 同时存在”压到“单 tile + 单个 coarse tile”。
- GWD30 加载过程新增 `tqdm` 进度条：
  - `GWD30 {year} process`
  - `GWD30 mosaic`
- 顶层 trace 里新增：
  - `intermediate_storage=temporary_coarse_geotiff_tiles`
  - `mosaic_strategy=average_of_processed_tiles`
  - `processed_temp_tile_count`

## Modified files and key changes

- `src/WA/loaders/gwd30.py`
  - 新增基于 bbox 的源窗口裁剪
  - 新增 masked class → binary fraction 的快速 lookup 映射
  - 新增逐 tile 粗尺度临时文件写出
  - 新增最终 coarse temp tile 平均镶嵌
  - `load()` 与 rough load 路径都增加 `tqdm` 进度显示
- `tests/test_loaders/test_gwd30.py`
  - 新增 rough binary tempfile mosaic + `tqdm` 回归测试

## Verification status

- `uv run pytest tests/test_loaders/test_gwd30.py -q`: pass (`5 passed`)
- `uv run ruff check src/WA/loaders/gwd30.py tests/test_loaders/test_gwd30.py`: pass
- `uv run mypy src/WA/loaders/gwd30.py tests/test_loaders/test_gwd30.py`: pass

## Open risks, TODOs, rollback notes

- 本轮只做了本地定向验证，**真正的验收仍然是 HPC 复跑**，需要确认：
  - 不再出现 OOM kill；
  - `GWD30 mosaic` 阶段可以稳定完成；
  - 处理速度在大流域窗口下可接受。
- 当前临时文件策略默认写整幅 coarse reference grid 大小的单 band GeoTIFF；如果后续区域数或 tile 数继续扩大，可再优化为“仅写有效 coarse window”。
- `tqdm` 采用“可导入则启用，否则退化为普通迭代”的方式，避免极简环境下直接 import 失败。
