# Phase 3.6 全局缓存机制

**Date:** 2026-03-31
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 已为 Phase 3.6 增加全局 staged cache，支持缓存全局 unified fraction / joint-valid / dominant classes / metrics / summary，并可在源标准化数据缺失时直接从缓存恢复最终输出。

---

## 本次改动

| File | Change |
|------|--------|
| `src/WA/comparison/phase36.py` | 将原先“单次流式计算 + 直接写最终输出”扩展为全局 staged cache 流程 |
| `scripts/run_phase3_6_global_entropy.py` | 新增 `--cache-dir`、`--no-prefer-cache`、`--no-write-cache` 参数 |
| `tests/test_phase3_6_analysis.py` | 新增全局缓存复用测试，验证删除标准化源文件后仍可从缓存重建输出 |

## 全局缓存目录结构

默认缓存目录：`results/cache/phase3_6`

按 `bbox/year/lat_chunk_size` 组织：

- `00_grid_template.nc`
- `01_g2017_unified_fraction.nc`
- `01_glwd_v2_unified_fraction.nc`
- `01_gwd30_unified_fraction.nc`
- `02_joint_valid_mask.nc`
- `03_dominant_classes.nc`
- `04_metrics.nc`
- `05_summary.json`

其中：

1. `01_*_unified_fraction.nc`
   - 缓存全局 unified 8 类 fraction 立方体
   - 是用户明确要求的“全局缓存”核心层
2. `02_joint_valid_mask.nc`
   - 缓存严格三者共同有效格点掩膜
3. `03_dominant_classes.nc`
   - 缓存三个数据集在 joint-valid 域上的主导类别结果
4. `04_metrics.nc`
   - 缓存最终 entropy / majority / agreement / joint_valid 结果
5. `05_summary.json`
   - 缓存汇总统计，便于直接恢复最终 summary

## 行为说明

- 默认会优先复用已存在的全局缓存
- 若 `04_metrics.nc`、`03_dominant_classes.nc`、`05_summary.json` 已存在，则可直接恢复最终输出
- 若只有前序阶段存在，则会从最靠后的全局缓存阶段继续向后计算
- 缓存文件写入使用临时文件 + `os.replace`，避免半写损坏
- 最终输出仍写到 `results/phase3.6/`，缓存不会替代正式产物

## 新增 CLI 参数

- `--cache-dir`
- `--no-prefer-cache`
- `--no-write-cache`

说明：

- 默认行为：读缓存 + 写缓存
- `--no-prefer-cache`：忽略现有缓存，强制重算并覆盖缓存
- `--no-write-cache`：不写新缓存；若已有完整后期缓存则仍可直接复用，否则退回一次性直算流程

## 验证

- `python -m py_compile src/WA/comparison/phase36.py scripts/run_phase3_6_global_entropy.py tests/test_phase3_6_analysis.py`
- `ruff check src/WA/comparison/phase36.py scripts/run_phase3_6_global_entropy.py tests/test_phase3_6_analysis.py`
- `python -m pytest tests/test_phase3_6_analysis.py -q`
- `python -m pytest tests/ -q`

结果：

- `ruff` 通过
- `tests/test_phase3_6_analysis.py`：`13 passed`
- 全量测试：`350 passed`

## 风险与备注

- 由于用户要求“全局 unified fraction 缓存”，`01_*_unified_fraction.nc` 在真实全球 500m 场景下会比较大；这是按用户要求显式保留的中间产物，不再改为更轻的条带缓存方案。
- 当前缓存按 `lat_chunk_size` 分目录，因此更换条带大小不会复用旧缓存。
- 当前 summary 最终会重写为正式输出路径，避免把缓存路径误写进 `results/phase3.6/*.json`。

## 建议运行方式

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir output/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 512
```
