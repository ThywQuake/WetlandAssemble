# 2026-04-06-009 Phase4 Berkeley Single-Slice Mask

## Summary

- 针对 `amazon` Phase 4 区域运行在 `berkeley_valid_mask` 冷启动阶段的 OOM，已将 Berkeley valid-mask 构建从多时相规约切换为单时间切片。
- 新逻辑不再执行 `monthly.notnull().any(dim="time")`，而是只选一个 Berkeley 时间切片来生成有效空间 footprint。
- 这次修改只影响 Berkeley valid-mask 的 cache-miss 路径，不改 `gwd30` Stage 1 / Stage 2 主链。

## Key Changes

- [src/WA/comparison/phase4_regional.py](/Users/mac/Code/WA/src/WA/comparison/phase4_regional.py)
  - `build_or_load_phase4_berkeley_valid_mask(...)` 改为单切片建 mask
  - 新增 `_select_phase4_berkeley_mask_slice(...)`
- [tests/test_comparison/test_phase4_regional.py](/Users/mac/Code/WA/tests/test_comparison/test_phase4_regional.py)
  - 新增单切片行为回归测试
- [CHANGELOG.md](/Users/mac/Code/WA/CHANGELOG.md)
  - 记录 Berkeley single-slice mask 变更

## Why

- HPC 日志显示 OOM 发生在：
  - `Phase4 cache miss: berkeley_valid_mask`
  - 尚未进入 `gwd30` Stage 2 tile 处理
- 根因收敛到 Berkeley mask 冷路径对多时相 3D 数据做 `notnull().any(dim="time")` 时峰值内存过高。

## Verification

- `ruff check src/WA/comparison/phase4_regional.py tests/test_comparison/test_phase4_regional.py`
- `python -m pytest tests/test_comparison/test_phase4_regional.py -q`
- `python -m pytest tests/`

Result:

- `ruff` passed
- targeted tests: `19 passed`
- full suite: `418 passed`

## HPC Retry

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2013 \
  --end-year 2022 \
  --no-skip
```

## Remaining Risk

- 这个修复默认 Berkeley 单切片 footprint 足够代表区域有效范围；如果后续发现 Berkeley 空间覆盖随时间变化显著，再回到“按年流式 OR”而不是恢复整窗 3D 规约。
