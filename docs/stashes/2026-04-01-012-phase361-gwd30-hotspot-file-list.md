# Phase 3.6.1 GWD30 Hotspot File List

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 已新增一个极简 Phase 3.6.1 文件清单脚本，只输出选定 hotspot 对应的 `raw tif / staged tile / reduced tile` 路径，不做任何统计、重建或诊断处理。

## Key Changes

| File | Change |
|------|--------|
| `src/WA/phase361_gwd30_trace.py` | 新增 `run_phase361_hotspot_file_listing(...)` 与 `build_phase361_hotspot_file_listing(...)`，复用已有 hotspot 解析、raw tile 发现、staged/reduced 匹配逻辑，输出纯路径清单 |
| `scripts/list_phase3_6_1_gwd30_hotspot_files.py` | 新增 CLI，默认处理 manifest 中全部 hotspots，也支持显式 `--hotspots` 或 `--limit` |
| `tests/test_phase3_6_1_gwd30_trace.py` | 新增回归测试，覆盖 raw/staged/reduced 文件名的一一对应关系 |
| `CHANGELOG.md` | 记录新增 Phase 3.6.1 文件清单脚本 |

## Verification

- `ruff check src/WA/phase361_gwd30_trace.py scripts/list_phase3_6_1_gwd30_hotspot_files.py tests/test_phase3_6_1_gwd30_trace.py` → passed
- `python -m pytest tests/test_phase3_6_1_gwd30_trace.py -q` → `5 passed`

## HPC Command

默认处理 manifest 里的全部 hotspots：

```bash
python scripts/list_phase3_6_1_gwd30_hotspot_files.py \
  --hotspots-manifest results/phase3.7_hotspots/phase3_7_hotspots_2016.json \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --phase36-cache-dir results/cache/phase3_6 \
  --output-dir results/phase3.6.1 \
  --year 2016 \
  --lat-chunk-size 512
```

指定两个 hotspot：

```bash
python scripts/list_phase3_6_1_gwd30_hotspot_files.py \
  --hotspots-manifest results/phase3.7_hotspots/phase3_7_hotspots_2016.json \
  --hotspots entropy-amazon_basin-001 entropy-kakaku_wetlands-001 \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --phase36-cache-dir results/cache/phase3_6 \
  --output-dir results/phase3.6.1 \
  --year 2016 \
  --lat-chunk-size 512
```

## Outputs

- 每个 hotspot 一个文件：
  `results/phase3.6.1/<hotspot_id>_gwd30_files.json`
- 汇总文件：
  `results/phase3.6.1/phase3_6_1_gwd30_hotspot_files_2016.json`
