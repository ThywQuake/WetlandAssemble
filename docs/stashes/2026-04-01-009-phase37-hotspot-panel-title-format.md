# Phase 3.7 Hotspot Panel Title Format

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** Phase 3.7 hotspot panel 大标题改为 `Region Label + 序号`，例如 `Kakaku Wetlands 001`。

## Key Change

- `scripts/plot_phase3_7_hotspot_panels.py`：新增标题格式化 helper，优先使用 `region_rank`，回退到从 `hotspot_id` 末尾解析序号；panel 标题不再显示原始 `hotspot_id`。

## Verification

- `ruff check scripts/plot_phase3_7_hotspot_panels.py tests/test_phase3_7_hotspot_panels.py`
- `python -m pytest tests/test_phase3_7_hotspot_panels.py -q`
