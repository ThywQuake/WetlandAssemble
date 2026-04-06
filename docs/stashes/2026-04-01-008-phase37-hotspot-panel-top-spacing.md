# Phase 3.7 Hotspot Panel Top Spacing

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 调整 Phase 3.7 hotspot panel 顶部留白，避免大标题与第一行子图标题重合。

## Key Change

- `src/WA/visualization/phase37.py`：在 `plot_phase37_hotspot_panel(...)` 中把 `suptitle` 上移，把 subplot `top` 下调，给大标题和第一行子图标题之间留出更多空间。

## Verification

- `ruff check src/WA/visualization/phase37.py`
- `python -m pytest tests/test_phase3_7_hotspot_panels.py -q`
