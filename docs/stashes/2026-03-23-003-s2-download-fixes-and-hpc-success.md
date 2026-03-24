# S2 下载修复 + HPC 3/3 成功

**Date:** 2026-03-23
**Branch:** feat/phase3-fine-grained-entropy-s2
**Status:** Phase 3 S2 下载完成，3/3 hotspots 成功下载

---

## Key Changes

| File | Change |
|------|--------|
| `src/WA/s2_batch.py` | 改为发现 `fine_grained_probe.json`（非 `hotspots.csv`），默认 target-time 2017-07-01 |
| `src/WA/validation/s2_reference.py` | L1C 集合 (`S2_HARMONIZED`)，±3 月窗口，RGB only，100m scale，诊断日志 |
| `src/WA/validation/_download_utils.py` | 添加 3 次重试 + 退避（10/20/30s），4xx 立即失败 |
| `scripts/run_phase3_s2_downloads.py` | 默认 target-time 改为 2017-07-01 |
| `tests/test_s2_batch.py` | 测试改为 JSON manifest 解析 |
| `.claude/skills/stash/SKILL.md` | 新增 /stash skill |

## Commits (本 session)

| Hash | Message |
|------|---------|
| `01bde50` | fix(s2): align default target-time to G2017 reference year 2016-07-01 |
| `9505c3c` | fix(s2-batch): discover probe JSON manifests instead of nonexistent hotspots.csv |
| `b04e26a` | fix(s2): use 2017-07-01 as default (S2 unavailable before 2017-03-28) |
| `6365d9c` | fix(s2): widen time window to ±3 months for tropical S2 coverage |
| `2012993` | fix(s2): use L1C collection for broader 2017 coverage |
| `fe4421a` | fix(s2): select RGB only + scale to 100m (GEE 50MB limit) |
| `379690e` | fix(s2): add retry with backoff for transient GEE download errors |

## HPC 迭代过程

1. `hotspots.csv` 不存在 → 改为读取 `fine_grained_probe.json`
2. `unsupported_time_window` → 2016 早于 S2，改为 2017-07-01
3. `empty_collection` × 3 → 单月窗口太窄，扩展到 ±3 月
4. `empty_collection` × 3 → `S2_SR_HARMONIZED` 在 2017 印尼无数据，改用 L1C
5. `3.3GB > 50MB` 限制 → RGB only + 100m scale
6. `download_failed` 2/3（500 + SSL EOF）→ 添加重试逻辑
7. **3/3 `downloaded`** — 全部成功（每个首次重试后通过）

## Verification

- pytest: 110 passed
- ruff: clean
- HPC: 3/3 hotspots downloaded（印尼 3 个区域，90/115/82 images）

## Open Risks / TODOs

- 诊断 print 语句留在 `s2_reference.py`（对 HPC 有用，可后续清理）
- S2 quicklook 为 L1C TOA 反射率，非大气校正后 — 视觉参考足够

## Next Steps

1. Phase 4：趋势分析（Mann-Kendall + Sen's slope）
