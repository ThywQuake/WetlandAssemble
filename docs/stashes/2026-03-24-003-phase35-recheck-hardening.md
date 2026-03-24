# Phase 3.5 复查补洞

**Date:** 2026-03-24  
**Branch:** `feat/phase3-fine-grained-entropy-s2`  
**Status:** 二次复查完成，补齐并行参数与 CLI 约束

## Additional Fixes

| File | Change |
|------|--------|
| `src/WA/loaders/gwd30.py` | 将 `ProcessPoolExecutor` 参数从错误的 `maxtasksperchild` 修正为 `max_tasks_per_child`，避免 `gwd30-workers > 1` 时无意义退回串行 |
| `scripts/plot_phase3_panels.py` | 将 `--class-scheme` 收紧为仅支持 `4class`，避免 8class 下错误使用 4-class 图例/配色 |

## Verification

- `uv run python -m pytest tests/` ✅ `160 passed`
- `uv run python -m pytest tests/test_loaders/test_gwd30.py tests/test_visualization/test_panel.py` ✅ `23 passed`
- `uv run ruff check scripts/plot_phase3_panels.py src/WA/loaders/gwd30.py src/WA/visualization/panel.py tests/test_visualization/test_panel.py tests/test_loaders/test_gwd30.py` ✅
- `python scripts/plot_phase3_panels.py --help` ✅

## Notes

- 当前 `Phase 3.5` 脚本默认仍建议 `--gwd30-workers 1` 先稳妥重跑；若节点内存富余，可提高到 `2` 做试探。
- 本次复查未发现新的失败测试或新的 lint 问题。
