# 2026-04-07-012 Phase4 GWD30 Year-Split Regional Cache Merge

## Summary

- `amazon` 已能跑通后，新的瓶颈出现在 `pan_trop_subtrop`：不是 Berkeley mask 冷启动，而是 `gwd30` Stage-1 pixel-stats 区域聚合在大区域下单任务推进过慢、且仍有新的内存压力。
- 这次把 `gwd30` Phase 4 区域链改成 **按年缓存 + 最终 merge**：
  - 每年先写一个 region monthly cache
  - 最终再合并成年表、climatology 和 `regional_series.csv`
- 同时把 tile 级 mask 投影改成 **先按 tile bbox 裁大 mask，再重投影**，避免对全热带大 mask 做重复全域重投影。

## Why

`pan_trop_subtrop` 的日志显示：

- Berkeley valid mask 已成功写出
- OOM / 性能瓶颈转移到 `Phase4 GWD30 pixel-stats selection`
- 单任务串行扫 `2013-2022` 全年、全区域，会让任务推进太慢，也不利于 HPC fanout

所以最合适的改法是：

1. 允许按 `year` 粒度单独生成 `gwd30` 区域 monthly cache
2. 后续宽时间窗运行优先读取这些年缓存并 merge
3. 避免在年内还把所有 tile-month 小表全攒在内存里

## Key Changes

- `src/WA/comparison/phase4_regional.py`
  - 新增 `phase4_dataset_region_year_cache_path(...)`
  - `build_phase4_gwd30_monthly_series_from_pixel_stats_tiles(...)` 改成逐年读写 cache
  - 新增 `_accumulate_phase4_gwd30_pixel_stats_tiles(...)`，按时间戳流式累计 tile 结果，不再先攒完整 `tile_frames`
  - `_mask_fraction_for_template(...)` 现在会先按 tile bbox 裁 `base_mask`，再做重投影

- `scripts/submit_phase4_gwd30_regional_year_split.sh`
  - 新增按年 fanout 的 SLURM 提交脚本：每年一个 `run_phase4_regional.py` 任务，最后再提交一个 dependent merge job

- `tests/test_comparison/test_phase4_regional.py`
  - 覆盖 year-cache 写入
  - 覆盖已有 year caches 的 merge 行为
  - 覆盖 tile bbox 子集后再重投影的行为

- `tests/test_submit_phase4_gwd30_regional_year_split.py`
  - 覆盖新 submit 脚本的 dry-run 产物，确认逐年 job script 和 merge script 都被正确生成

## Verification

只跑了 Phase 4 相关测试：

```bash
ruff check src/WA/comparison/phase4_regional.py tests/test_comparison/test_phase4_regional.py
```

```bash
python -m pytest tests/test_comparison/test_phase4_regional.py -q
```

Result:

- `ruff` passed
- `22 passed`

## Recommended HPC Usage

### 1. 先按年 fanout 跑

例如：

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region pan_trop_subtrop \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2013 \
  --end-year 2013 \
  --no-skip
```

每年各跑一个任务：`2013 ... 2022`。

### 2. 全年 merge pass

等所有年份缓存都在以后，再跑：

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region pan_trop_subtrop \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2013 \
  --end-year 2022
```

这里故意**不要**加 `--no-skip`，让它优先复用 `years/regional_series_<year>.csv` 再生成最终 `regional_series.csv`。

## Expected Cache Layout

```text
results/phase4/cache/gwd30/<region>/years/regional_series_2013.csv
results/phase4/cache/gwd30/<region>/years/regional_series_2014.csv
...
results/phase4/cache/gwd30/<region>/years/regional_series_2022.csv
results/phase4/cache/gwd30/<region>/regional_series.csv
```

## Remaining Risk

- 这个改法已经把“全时间窗单任务”拆开，但 `pan_trop_subtrop` 单年仍然可能很重，尤其是 tile 数非常多时。
- 如果单年任务仍然偏慢，下一步就该继续下钻到 **按 manifest shard / tile batch** 级别，而不是再回到单任务扫完整年。