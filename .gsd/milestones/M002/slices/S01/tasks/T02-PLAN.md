---
estimated_steps: 23
estimated_files: 4
skills_used: []
---

# T02: Extract a contract-aware 0.25° surface backbone from the plotting route

Retire the surface-side drift next by moving the reusable `0.25°` aggregation/cache logic out of the plotting script and into a contract-aware library path that can also admit GWD30 Stage-1 pixel-statistics inputs.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `scripts/plot_tropical_wetland_025deg.py` and dataset loaders | Fail with `dataset_id`, `region_id`, and stage name instead of silently skipping contract outputs. | Keep cache-reuse semantics visible so a long re-run can resume from the last good stage. | Reject empty/non-spatial surfaces or stale cache versions instead of writing misleading `0.25°` outputs. |

## Load Profile

- **Shared resources**: staged cache dirs under `results/cache/tropical_025deg` and Stage-1 GWD30 tile manifests under `results/phase4/pixel_stats/...`.
- **Per-operation cost**: one dataset load or many tile reads plus area-weighted aggregation to a regular grid.
- **10x breakpoint**: disk I/O and memory pressure become the first limit if the code broadens from the canonical subset to wider regions/years without cache reuse.

## Negative Tests

- **Malformed inputs**: unknown region ids, empty surface arrays, stale cache version attrs, and missing GWD30 tile manifests.
- **Error paths**: loader failure, unreadable cache files, or empty clipped surfaces surface a readable exception with stage context.
- **Boundary conditions**: Berkeley static-vs-dynamic year handling, GWD30 inclusion, and canonical subset region resolution stay deterministic.

## Steps

1. Add `src/WA/comparison/percentage_backbone.py` as the reusable library entrypoint for contract-tagged `0.25°` wetland-fraction surfaces and cache metadata.
2. Refactor `scripts/plot_tropical_wetland_025deg.py` into a thin CLI wrapper over the new library, replacing legacy region-only assumptions with contract region resolution while preserving visible cache hit/miss logging.
3. Wire GWD30 into the shared-grid surface path by reading Stage-1 monthly pixel-statistics tiles instead of silently excluding the dataset, and record whether each surface is Berkeley-valid or raw-bbox in attrs/metadata.
4. Add `tests/test_comparison/test_percentage_backbone.py` and extend `tests/test_plot_tropical_wetland_025deg.py` to assert cache reuse, contract attrs, region resolution, and GWD30 adapter behavior.

## Must-Haves

- [ ] The `0.25°` surface builder becomes reusable library code rather than living only inside a plotting script.
- [ ] Contract metadata makes mask-domain and dataset/year semantics inspectable in saved outputs.

## Done when

- The new backbone module exists, the plot script becomes a thin wrapper, GWD30 is no longer skipped by design in the shared-grid route, and the surface tests cover the contract attrs and cache path.

## Inputs

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/trends.py`
- `scripts/plot_tropical_wetland_025deg.py`
- `tests/test_plot_tropical_wetland_025deg.py`

## Expected Output

- `src/WA/comparison/percentage_backbone.py`
- `scripts/plot_tropical_wetland_025deg.py`
- `tests/test_comparison/test_percentage_backbone.py`
- `tests/test_plot_tropical_wetland_025deg.py`

## Verification

python -m pytest tests/test_comparison/test_percentage_backbone.py tests/test_plot_tropical_wetland_025deg.py -q
python scripts/run_related_tests.py src/WA/comparison/percentage_backbone.py scripts/plot_tropical_wetland_025deg.py

## Observability Impact

- Signals added/changed: surface cache stage logs, `dataset_id/region_id/year` metadata on cache misses, and GWD30 tile-restore counts.
- How a future agent inspects this: inspect `results/cache/tropical_025deg/...` plus contract attrs on the written NetCDF outputs.
- Failure state exposed: stale caches, missing Stage-1 manifests, or wrong mask-domain attrs become visible in logs and saved metadata.
