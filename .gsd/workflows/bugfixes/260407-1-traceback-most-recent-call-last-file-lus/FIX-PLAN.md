# FIX PLAN

1. Update `_resolve_phase4_berkeley_mask_source_time_range()` so a non-overlapping requested year falls back to the earliest available standardized Berkeley file instead of raising.
2. Add tests covering the no-overlap fallback case while preserving the current overlapping-window behavior.
3. Run targeted verification, then commit the fix atomically.
