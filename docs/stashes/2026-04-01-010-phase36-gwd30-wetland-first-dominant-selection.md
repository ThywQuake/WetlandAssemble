# Phase 3.6 GWD30 Wetland-First Dominant Selection

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 已修正 Phase 3.6 中 GWD30 年度主导类选择逻辑，避免 `Non-wetland` / `Water` 在存在湿地类别时覆盖湿地主导判断。

## Key Changes

| File | Change |
|------|--------|
| `src/WA/comparison/phase36.py` | 新增 `compute_gwd30_annual_dominant_class(...)`：先排除 unified `0=Non-wetland` 与 `1=Water`，若 2-7 任一湿地类年内比例大于 0，则只在湿地类中选主导类；否则退回到 `Non-wetland` / `Water` 二选一 |
| `src/WA/comparison/phase36.py` | Phase 3.6 GWD30 stripe cache 写出改用新规则；同时把 Phase 3.6 cache 读取改为 version-aware，避免旧 dominant/metrics cache 被继续复用 |
| `tests/test_phase3_6_analysis.py` | 新增 wetland-first 与 fallback 两条回归测试，并让 mock GWD30 cache builder 跟真实规则保持一致 |
| `CHANGELOG.md` | 记录这次用户可见的 Phase 3.6 算法修正 |

## Verification

- `ruff check src/WA/comparison/phase36.py tests/test_phase3_6_analysis.py` → passed
- `python -m pytest tests/test_phase3_6_analysis.py tests/test_loaders/test_gwd30.py -q` → `40 passed`
- `python -m pytest tests/` → `380 passed`

## HPC Command

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 512
```

## Notes

- 这次已提升 Phase 3.6 cache version，并在读取时检查 version；沿用原 `results/cache/phase3_6` 即可触发旧 cache 重建。
- 若 HPC 仍有内存压力，再把 `--lat-chunk-size` 下调到 `256`。
