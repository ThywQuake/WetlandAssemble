# Fix Plan: Phase 2.5 Visualization OOM + Dataset Skip Issues

**Date:** 2026-03-24
**Branch:** feat/phase3-fine-grained-entropy-s2
**Triggered by:** SLURM OOM kill on job 10245409 after 7/38 focus areas

---

## Issues

### 1. OOM — g2017 loads at ~1795×1795 per focus area (CRITICAL)

g2017 is a 30m-resolution GeoTIFF (~0.001°/pixel). A 2°×2° focus area bbox
contains ~2000×2000 pixels. Loading full-resolution into memory, then rendering
with matplotlib, consumes >1 GB per panel.

**Fix:** Resample g2017 to a capped display resolution (≤0.05°, same as its
nominal resolution listed in docs) inside `load_native_wetland_surface` using
`rioxarray` coarsen or `rasterio` overview, before returning the surface.

Alternatively, add a `max_display_pixels` cap in `_extract_native_wetland_surface`
using `xr.DataArray.coarsen()` when the array exceeds a threshold (e.g. 200×200).

**Target:** g2017 display resolution ≤ 0.05° (~40×40 for a 2°×2° bbox)

---

### 2. swamps SKIP `'fw'` — missing time_range causes full dataset scan

When `target_time` falls within SWAMPS coverage, `_build_visualization_time_range`
should return a valid time_range. But the `'fw'` KeyError suggests `loader.load()`
was called without time_range (or time_range=None) so `_candidate_files(None)`
does `rglob("*.nc")` returning files from different format versions lacking `fw`.

Actual log shows: `swamps: SKIP ('fw')` — this is a KeyError on `source["fw"]`
in the loader, meaning some SWAMPS files don't have the `fw` variable.

**Fix options (in order of preference):**

**A.** In `SwampsLoader.load()`, skip files that don't contain `fw` instead of
crashing:
```python
if "fw" not in source:
    source.close()
    continue
```

**B.** In `_build_visualization_time_range`, if swamps temporal_coverage is not
parseable, fall back to loading nothing (return None for swamps).

**Recommended: Fix A** — defensive per-file skip, already consistent with
the broader pattern of not silently suppressing errors (we log the skip).

---

### 3. gwd30 SKIP — two distinct causes

- `"Read failed. See previous exception for details."` — tile read error, likely
  a broken/missing shard file. Already caught by try/except. No code fix needed;
  needs HPC data check.
- `"No data found in bounds."` — focus area outside GWD30 tile coverage. Expected
  behavior. No fix needed.

---

### 4. Slow per-panel render (656s, 300s) — g2017 I/O

Directly caused by issue #1 (full-res g2017 load). Fixing #1 will resolve this.

---

## Fix Plan

| # | File | Change | Priority |
|---|------|--------|----------|
| 1 | `src/WA/visualization/comparison_panel.py` | Add coarsen/resample cap for g2017 (and any dataset) when surface exceeds max pixel threshold | HIGH |
| 2 | `src/WA/loaders/swamps.py` | Skip files without `fw` variable instead of crashing | HIGH |
| 3 | HPC | Check gwd30 tile integrity for broken shards | LOW (data issue) |

---

## Implementation: Fix 1 — Display Resolution Cap

In `comparison_panel.py`, after `_extract_native_wetland_surface()` returns,
add a cap:

```python
MAX_DISPLAY_PIXELS = 200  # per axis

def _cap_display_resolution(surface: xr.DataArray) -> xr.DataArray:
    """Coarsen to at most MAX_DISPLAY_PIXELS per axis for memory safety."""
    ny, nx = surface.shape[-2], surface.shape[-1]
    factor_y = max(1, ny // MAX_DISPLAY_PIXELS)
    factor_x = max(1, nx // MAX_DISPLAY_PIXELS)
    if factor_y == 1 and factor_x == 1:
        return surface
    factor = max(factor_y, factor_x)
    return surface.coarsen(
        {surface.dims[-2]: factor, surface.dims[-1]: factor},
        boundary="trim",
    ).mean()
```

Call after line 85 in `load_native_wetland_surface`:
```python
return _cap_display_resolution(surface.astype(np.float32).load())
```

## Implementation: Fix 2 — SWAMPS per-file skip

In `src/WA/loaders/swamps.py`, line 51:
```python
source = xr.open_dataset(path)
if "fw" not in source:  # ADD THIS
    source.close()       # ADD THIS
    continue             # ADD THIS
```
