# Phase 3.7 Hotspot Panel Title

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 按用户要求简化 Phase 3.7 hotspot panel 大标题，只显示 `Region-[Hotspot ID]`。

## Key Change

- `scripts/plot_phase3_7_hotspot_panels.py`：把 panel `suptitle` 从双行详细说明改成单行 `"{region_label}-[{hotspot_id}]"`，减少标题占用空间。

## Verification

- `ruff check scripts/plot_phase3_7_hotspot_panels.py`
- `python -m pytest tests/test_phase3_7_hotspot_panels.py -q`
