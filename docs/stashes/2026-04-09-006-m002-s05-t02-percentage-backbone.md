# 2026-04-09 M002/S05/T02 Percentage Backbone Quick Reference

## 本次交付

- 新增 `src/WA/comparison/percentage_backbone.py`
  - 统一了 Phase 4 percentage 的 `0.25°` coarse surface/cache 路径。
  - 非 GWD30 继续走现有 plot-route loader/aggregation 逻辑。
  - GWD30 新增 Stage-1 pixel-statistics tile 恢复路径，不再永久排除。
  - 新增 contract-backed `surface` / `regional_summary` 语义写入与 reload。
- 新增 `src/WA/comparison/percentage_hotspots.py`
  - 从 contract surface bundle 生成 percentage hotspot JSON manifest + CSV。
  - 写入后会按语义 reload 验证；partial/stale pair 不会被静默复用。
- 新增 `scripts/run_phase4_percentage_contract.py`
  - 支持 `--region`、`--subset canonical`、`--subset ten`。
  - 默认 percentage dataset set 现在是有序 six-pack：`gwd30, giems_mc, topmodel, swamps, wad2m, berkeley_rwawc`。
  - `dataset_key=canonical` 表示这组默认有序 dataset set；其他组合会自动生成 `+` 连接 key。
- `scripts/plot_tropical_wetland_025deg.py` 现在只是 shared backbone 的 thin wrapper，不再拥有第二份 surface 实现。

## 关键语义

1. **percentage contract family 是 multi-dataset bundle，不是单 dataset 文件集合。**
   - contract `surface` NetCDF 里保存 stack 后的 `wetland_fraction(dataset_id, lat, lon)`
   - 同时保存 `mean_wetland_percentage` / `std_wetland_percentage` / `valid_dataset_count`
2. **hotspot 排名是 family-local 的 mean wetland percentage 排名。**
   - primary score 仍叫 `wetland_percentage`
   - bbox/area 来自 coarse cell，不是假造 cross-line 共享分数
3. **GWD30 coarse surface 走 Stage-1 tile manifest 恢复。**
   - 需要 `results/phase4/pixel_stats/gwd30/gwd30_<year>/monthly/tile_manifest.json`
   - 若 manifest 缺失或 tile 不覆盖 region，会带 `stage=percentage-surface dataset_id=gwd30 region_id=...` 明确失败
4. **skip/reload 是 fail-closed。**
   - contract summary / surface 会按语义 reload
   - hotspot manifest/table 只接受完整 pair；partial pair 需要显式 `--no-skip` 重建

## 已通过验证

- `ruff check src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py scripts/run_phase4_percentage_contract.py scripts/plot_tropical_wetland_025deg.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_plot_tropical_wetland_025deg.py`
- `python scripts/run_phase4_percentage_contract.py --help`
- `python -m pytest tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_plot_tropical_wetland_025deg.py -q` → `19 passed`
- `python scripts/run_related_tests.py src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py scripts/run_phase4_percentage_contract.py scripts/plot_tropical_wetland_025deg.py`
- `python -m pytest tests/test_test_selection.py -q`
- `python -m pytest tests/` 仍在 repo 既有边界处出现 `tests/test_mgrs_tiling.py` failure，随后 broader suite 继续跑到后段时 exit `137`

## HPC 命令

### 先跑单区 amazon（显式 no-skip）

```bash
python scripts/run_phase4_percentage_contract.py \
  --region amazon \
  --output-root results/phase4 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --surface-year 2016 \
  --start-year 2016 \
  --end-year 2016 \
  --no-skip
```

### canonical subset

```bash
python scripts/run_phase4_percentage_contract.py \
  --subset canonical \
  --output-root results/phase4 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --surface-year 2016 \
  --start-year 2016 \
  --end-year 2016 \
  --no-skip
```

### ten-region widen

```bash
python scripts/run_phase4_percentage_contract.py \
  --subset ten \
  --output-root results/phase4 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --surface-year 2016 \
  --start-year 2016 \
  --end-year 2016 \
  --no-skip
```

## 继续执行时先看什么

- contract surface: `results/phase4/surfaces/<region>/<dataset_key>__<region>__surface.nc`
- contract summary: `results/phase4/regional_summaries/<region>/<dataset_key>__<region>__regional_summary.csv`
- hotspot pair: `results/phase4/hotspot_manifests/<region>/<dataset_key>__<region>__hotspot_manifest.{json,csv}`
- CLI logs: `stage=percentage-summary`, `stage=percentage-surface`, `stage=percentage-hotspots`
