# 2026-04-06-002 Phase4 Stage1 GWD30 Native Pixel Statistics

## 结论

- 你说得对，Stage 1 不应该带 `resolution-deg` 这种重投影选项。
- 现在 Stage 1 改成了：
  - 直接复用 `standardized/_staging/gwd30_<year>/stage_shard_*.json`
  - 在 **native staged grid** 上把每个 `tile_*.nc` 转成一个统计 tile
  - 不做 Berkeley mask
  - 不做 comparison grid 重投影

## 本次改动

- [src/WA/comparison/trends.py](/Users/mac/Code/WA/src/WA/comparison/trends.py)
  - 保留原有 `build_gwd30_pixel_statistics(...)` 供后续 trend-grid 逻辑复用
  - 新增 `build_gwd30_native_pixel_statistics_tiles(...)`
  - 新增三个 staged-tile transform:
    - `phase4_gwd30_pixel_statistics_native_tile(...)`
    - `phase4_gwd30_pixel_statistics_monthly_tile(...)`
    - `phase4_gwd30_pixel_statistics_annual_tile(...)`
  - 新增 `phase4_gwd30_pixel_stats_tile_dir(...)`
- [scripts/build_phase4_gwd30_pixel_stats.py](/Users/mac/Code/WA/scripts/build_phase4_gwd30_pixel_stats.py)
  - 改成 Stage 1 原生统计入口
  - 删除 `--resolution-deg`
  - 删除 `--region/--bbox` 这类 comparison-grid 定位参数
  - 改为按 `--year` 批量构建 native staged-grid statistics tiles

## Stage 1 输出

每个 transformed tile 会写到：

`results/phase4/pixel_stats/gwd30/gwd30_<year>/<aggregation>/tiles/tile_*.nc`

变量包括：

- `wetland_fraction(time, y, x)`
- `valid_observation_count(y, x)`
- `mean_wetland_fraction(y, x)`
- `std_wetland_fraction(y, x)`
- `cell_area_km2(y, x)`

并写一个同目录 manifest：

- `tile_manifest.json`

## 验证

- `ruff check src/WA/comparison/trends.py scripts/build_phase4_gwd30_pixel_stats.py tests/test_comparison/test_trends.py`
  - 通过
- `python -m compileall src/WA/comparison/trends.py scripts/build_phase4_gwd30_pixel_stats.py tests/test_comparison/test_trends.py`
  - 通过
- `python -m pytest tests/test_comparison/test_trends.py -q`
  - `18 passed`

## HPC 建议命令

按年生成 monthly native statistics tiles：

```bash
python scripts/build_phase4_gwd30_pixel_stats.py \
  --year 2020 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --aggregation monthly \
  --worker-count 1 \
  --no-skip
```

如果要 annual：

```bash
python scripts/build_phase4_gwd30_pixel_stats.py \
  --year 2020 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --aggregation annual \
  --worker-count 1 \
  --no-skip
```
