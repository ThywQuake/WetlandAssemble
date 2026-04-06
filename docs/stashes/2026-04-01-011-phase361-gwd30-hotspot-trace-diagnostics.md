# Phase 3.6.1 GWD30 Hotspot Trace Diagnostics

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 已新增 Phase 3.6.1 诊断工具，可从现有 hotspot 反查 GWD30 `raw -> staged -> reduced -> final`
四层链路，定位 Phase 3.6 异常主导类结果到底在哪一层开始偏掉。

## Key Changes

| File | Change |
|------|--------|
| `src/WA/phase361_gwd30_trace.py` | 新增 Phase 3.6.1 核心诊断模块：读取 hotspot manifest，构建与 Phase 3.6 对齐的 AOI reference grid，分别对 raw/staged/reduced/final 四层做 tile 命中列表、annual unified fraction 摘要、old/new dominant 对比与逐格差异统计 |
| `scripts/inspect_phase3_6_1_gwd30_hotspots.py` | 新增 CLI，默认处理 manifest 中全部 hotspots，也支持显式 `--hotspots` 或 `--limit`；输出单 hotspot JSON 和汇总 JSON |
| `tests/test_phase3_6_1_gwd30_trace.py` | 新增回归测试，覆盖 hotspot manifest 解析、AOI reference grid 对齐、reduced tile 重建、dominant transition 统计 |
| `docs/plans/2026-04-01-phase361-gwd30-hotspot-trace-plan.md` | 记录并完成 Phase 3.6.1 诊断方案 |
| `CHANGELOG.md` | 记录新增 Phase 3.6.1 诊断能力 |

## Verification

- `ruff check src/WA/phase361_gwd30_trace.py scripts/inspect_phase3_6_1_gwd30_hotspots.py tests/test_phase3_6_1_gwd30_trace.py` → passed
- `python -m pytest tests/test_phase3_6_1_gwd30_trace.py -q` → `4 passed`
- `python -m pytest tests/test_phase3_6_1_gwd30_trace.py tests/test_phase3_6_analysis.py tests/test_loaders/test_gwd30.py -q` → `44 passed`
- `python -m pytest tests/` → `384 passed`

## HPC Command

默认处理 manifest 里的全部 hotspots：

```bash
python scripts/inspect_phase3_6_1_gwd30_hotspots.py \
  --hotspots-manifest results/phase3.7_hotspots/phase3_7_hotspots_2016.json \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --phase36-output-dir results/phase3.6 \
  --phase36-cache-dir results/cache/phase3_6 \
  --output-dir results/phase3.6.1 \
  --year 2016 \
  --lat-chunk-size 512 \
  --worker-count 1
```

指定两个 hotspot：

```bash
python scripts/inspect_phase3_6_1_gwd30_hotspots.py \
  --hotspots-manifest results/phase3.7_hotspots/phase3_7_hotspots_2016.json \
  --hotspots entropy-amazon_basin-001 entropy-kakaku_wetlands-001 \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --phase36-output-dir results/phase3.6 \
  --phase36-cache-dir results/cache/phase3_6 \
  --output-dir results/phase3.6.1 \
  --year 2016 \
  --lat-chunk-size 512 \
  --worker-count 1
```

## Notes

- 这个诊断工具不会修改 Phase 3.6 结果，只读取现有 raw/staged/reduced/final 产物并输出 JSON 诊断。
- 如果 `raw_vs_staged` 已经明显偏离，优先查 staged tile 构建；如果 `staged_vs_reduced` 才开始偏，优先查 tile-reduce；如果 `reduced_new_vs_final_gwd30` 才偏，优先查 final export。
