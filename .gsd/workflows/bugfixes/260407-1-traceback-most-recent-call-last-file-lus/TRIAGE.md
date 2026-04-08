# TRIAGE

## Bug
`run_phase4_regional.py` fails during Berkeley valid-mask cache generation for year-split Phase 4 runs whose requested year is earlier than the first available standardized Berkeley file.

Observed stack trace:

```text
FileNotFoundError: No standardized files for berkeley_rwawc overlap ('2017-01-01', '2017-12-31')
```

## Root cause
`build_or_load_phase4_berkeley_valid_mask()` delegates to `_resolve_phase4_berkeley_mask_source_time_range()` to choose a minimal Berkeley source window for the valid-mask footprint.

That helper currently does this:
1. calls `StandardizedDataLoader.resolve_file_paths("berkeley_rwawc", time_range=requested_time_range)`
2. takes the first returned file
3. opens its first time slice and uses that as the mask source window

This works when the requested analysis window overlaps Berkeley coverage, such as a full `2013-2022` request that overlaps `2018+` Berkeley files.

It fails for year-split jobs like `2017-01-01 .. 2017-12-31`, because `resolve_file_paths()` filters dynamic files strictly by overlapping year and raises `FileNotFoundError` when no overlap exists.

The Berkeley valid mask is only a spatial footprint. It does **not** need to come from the same analysis year as GWD30. Any real Berkeley slice is sufficient for this cache warm-up step.

## Minimal reproduction
Create a temporary standardized directory with:
- `berkeley_rwawc_2018.nc`
- `berkeley_rwawc_2019.nc`

Then call:

```python
_resolve_phase4_berkeley_mask_source_time_range(
    standardized_dir=tmp_dir,
    requested_time_range=("2017-01-01", "2017-12-31"),
)
```

Current result:

```text
FileNotFoundError: No standardized files for berkeley_rwawc overlap ('2017-01-01', '2017-12-31')
```

## Affected files / functions
- `src/WA/comparison/phase4_regional.py`
  - `build_or_load_phase4_berkeley_valid_mask(...)`
  - `_resolve_phase4_berkeley_mask_source_time_range(...)`
- `src/WA/standardized_loader.py`
  - `StandardizedDataLoader.resolve_file_paths(...)` (behavior relied on by the helper)
- `scripts/run_phase4_regional.py`
  - triggers the failing mask-cache warm-up path for year-split runs

## Blast radius
- Affects Phase 4 regional runs that request years before Berkeley standardized coverage starts.
- Most visible in the new GWD30 year-split workflow (`2013-2017` jobs).
- Full-range runs like `2013-2022` may hide the bug because they overlap Berkeley files and therefore do not trigger the fallback case.

## Proposed fix
Make `_resolve_phase4_berkeley_mask_source_time_range()` tolerant of non-overlapping requested windows:

1. First try the current overlap-based resolution.
2. If no overlap exists, fall back to the earliest available standardized Berkeley file.
3. Continue selecting that file's first real time slice as the mask source window.
4. Add/update tests for:
   - overlapping request still picks first overlapping source window
   - pre-coverage request (e.g. 2017) falls back to earliest available Berkeley source window instead of raising

## Why this is the root fix
The failing assumption is not in HPC scheduling or GWD30 staging. The failure comes from treating the Berkeley valid-mask footprint as year-coupled analysis data. Fixing the source-window resolver removes that bad assumption and keeps the valid-mask behavior aligned with its real purpose: obtaining one valid Berkeley spatial footprint for regridding and masking.
