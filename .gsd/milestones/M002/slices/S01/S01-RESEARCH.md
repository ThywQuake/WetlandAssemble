# S01 — Research

**Date:** 2026-04-08

## Summary

S01 primarily owns `R101`, `R102`, and `R106`, and it sets the first practical shape for `R105`. The wetland-percentage backbone already exists in pieces: `src/WA/comparison/phase4_regional.py` + `scripts/run_phase4_regional.py` provide the live Stage-2 regional summary route with Berkeley-valid mask semantics and Stage-1 GWD30 pixel-statistics caches; `src/WA/comparison/trends.py` + `scripts/build_phase4_gwd30_pixel_stats.py` provide the Stage-1 GWD30 native-tile builder; and `scripts/plot_tropical_wetland_025deg.py` provides a separate `0.25°` surface/cache route. What is missing is the contract glue: one explicit region set, one canonical subset definition, one percentage hotspot manifest, and one stable artifact layout that both subset proof and ten-region scale-out share.

The key integration risk is semantic drift between the existing surface and summary paths. The `0.25°` plotting script is the closest existing producer for shared-grid wetland-fraction surfaces, but it is visualization-centric, currently excludes GWD30, and does not obviously inherit the Berkeley-valid denominator used by `phase4_regional.py`. Meanwhile hotspot writing already exists in mature form in `src/WA/phase37_hotspots.py`, but percentage AOIs still live in older rough-binary objects (`RoughFocusArea`) with a different region catalog (`DEFAULT_FOCUS_REGION_BBOXES`). The first implementation should therefore add a thin contract layer and wire current producers into it, not start a third standalone pipeline.

## Recommendation

Take a **thin contract + adapters** approach:

1. **Add one explicit contract module** under `src/WA/comparison/` for:
   - canonical subset membership
   - shared region identifiers/labels
   - percentage surface metadata
   - regional summary artifact metadata
   - hotspot manifest records

2. **Keep the current Phase 4 route as the operational percentage backbone**:
   - Stage 1: `src/WA/comparison/trends.py` + `scripts/build_phase4_gwd30_pixel_stats.py`
   - Stage 2: `src/WA/comparison/phase4_regional.py` + `scripts/run_phase4_regional.py`
   Reuse their cache/year-split semantics instead of reviving the old full-tropics one-shot route.

3. **Refactor or wrap the existing `0.25°` surface builder instead of hand-writing a new one**: `scripts/plot_tropical_wetland_025deg.py` already contains the coarse-grid aggregation/cache pattern. Pull the reusable surface-building logic into a library module so S01 can emit contract-managed NetCDF/summary artifacts without making a plotting script the only API.

4. **Reuse the Phase 3.7 hotspot-manifest pattern** for percentage hotspots: `src/WA/phase37_hotspots.py` already solves JSON manifest + hotspot CSV + region CSV + quota/debug bookkeeping. Adapt that pattern to percentage hotspots rather than inventing a fourth hotspot output shape.

5. **Do not modify `config/` for the canonical subset without approval.** `config/priority_regions.yaml` should remain the read-only master catalog. Put canonical subset selection in a new code/data file outside `config/` (for example a new module under `src/WA/comparison/` and, if needed, a companion note under `docs/`).

Recommended first-cut canonical subset: **`amazon`, `pantanal`, `sudd`, `borneo`**. This covers large floodplain, seasonal wetland system, swamp/inland-delta/flood-basin behavior, and peat/swamp-island settings while staying inside the existing ten-region catalog. The list should remain data-driven / editable without code surgery.

## Implementation Landscape

### Key Files

- `config/priority_regions.yaml` — current ten-region source of truth for M002-scale regions. Use as read-only input; no canonical-subset marker exists yet.
- `src/WA/comparison/phase4_regional.py` — live percentage backbone. Important pieces:
  - `load_phase4_regions(...)`
  - `compute_phase4_region_dataset_table(...)`
  - `build_phase4_gwd30_monthly_series_from_pixel_stats_tiles(...)`
  - `build_or_load_phase4_berkeley_valid_mask(...)`
  - `assemble_phase4_series_table(...)`
  This is the best place to preserve regional summary semantics and cache layout.
- `scripts/run_phase4_regional.py` — current Stage-2 CLI for per-region percentage summaries; likely should stay thin and call new contract-aware library functions.
- `src/WA/comparison/trends.py` — contains the Stage-1 GWD30 native pixel-statistics path:
  - `build_gwd30_native_pixel_statistics_tiles(...)`
  - `phase4_gwd30_pixel_stats_tile_dir(...)`
  - `build_gwd30_pixel_statistics(...)`
  Do not bypass this when bringing GWD30 into the shared `0.25°` surface route.
- `scripts/build_phase4_gwd30_pixel_stats.py` — current Stage-1 operational entrypoint; already writes `tile_manifest.json`.
- `scripts/plot_tropical_wetland_025deg.py` — existing `0.25°` wetland-fraction surface/cache builder. Reusable, but currently script-owned, visualization-oriented, and excludes GWD30.
- `src/WA/comparison/rough_binary.py` — existing shared-grid pairwise metrics/disagreement surface object (`RoughBinaryResult`). Useful as a reference for percentage hotspot scoring and pairwise summary tables.
- `src/WA/comparison/focus_areas.py` — existing coarse AOI selector (`RoughFocusArea`, `select_focus_areas(...)`). Reusable selection logic, but its hardcoded 4-region defaults do **not** match the M002 ten-region catalog.
- `src/WA/phase37_hotspots.py` — best existing artifact pattern for hotspot manifests:
  - reads `config/priority_regions.yaml`
  - allocates per-region quota
  - writes JSON manifest + hotspot CSV + region CSV + debug PNG
  This is the strongest existing template for S01 hotspot outputs.
- `src/WA/visualization/phase4.py` — current paper-ish percentage figure layer from regional tables; should consume contract outputs rather than an ad hoc CSV naming convention.
- `src/WA/comparison/trend_agreement.py` and `src/WA/comparison/hotspots.py` — later-line implementations that currently use separate dataclasses / old region defaults; S01 contract should be designed so these modules can adopt it later.
- `tests/test_comparison/test_phase4_regional.py` — main regression surface for the operational percentage route.
- `tests/test_comparison/test_trends.py` — main regression surface for Stage-1 GWD30 pixel-statistics.
- `tests/test_comparison/test_rough_binary.py` — pairwise percentage/binary disagreement reference behavior.
- `tests/test_comparison/test_hotspots.py` — reference behavior for hotspot object extraction / dedup / region stratification.
- `tests/test_visualization/test_phase4.py` and `tests/test_plot_tropical_wetland_025deg.py` — figure/surface cache regressions for current percentage outputs.

### Build Order

1. **Lock the contract and canonical subset first.**  
   This retires `R101` / `R106` risk early and prevents S01 from hard-coding yet another region or hotspot shape. The planner should make this its first task, with tests around region ids, artifact metadata, and JSON-safe serialization.

2. **Bridge the existing percentage producers onto the contract.**  
   - keep `phase4_regional.py` as the source of regional summaries
   - extract/wrap reusable `0.25°` surface building from `scripts/plot_tropical_wetland_025deg.py`
   - bring GWD30 into the same surface route via Stage-1 pixel-statistics tiles  
   This closes `R102` on the canonical subset without reworking the underlying data route.

3. **Add percentage hotspot manifests on top of the shared-grid surfaces.**  
   The natural implementation seam is:
   - scoring logic inspired by `rough_binary.py` / `focus_areas.py`
   - manifest/CSV/debug writing pattern borrowed from `phase37_hotspots.py`  
   This gives S01 the first contract-shaped hotspot output that later slices can reuse.

4. **Only after subset proof passes, fan out to the full ten-region catalog.**  
   Reuse the existing year-split/cache/merge pattern described in `phase4_regional.py` and the 2026-04-07 stashes. Do not start with broad one-shot full-tropics jobs.

### Verification Approach

Use the related subset, not the full suite, per the current project rule.

Recommended local regression set after S01 changes:

```bash
python -m pytest \
  tests/test_comparison/test_phase4_regional.py \
  tests/test_comparison/test_trends.py \
  tests/test_comparison/test_rough_binary.py \
  tests/test_comparison/test_hotspots.py \
  tests/test_comparison/test_trend_agreement.py \
  tests/test_visualization/test_phase4.py \
  tests/test_plot_tropical_wetland_025deg.py -q
```

Also use the repo’s related-test helper when the changed-file set is stable:

```bash
python scripts/run_related_tests.py src/WA/comparison/phase4_regional.py scripts/build_phase4_gwd30_pixel_stats.py scripts/plot_tropical_wetland_025deg.py
```

Canonical-subset proof should produce, for the same region ids:
- contract-managed `0.25°` surface artifacts
- contract-managed regional summary tables
- hotspot manifest JSON + CSV (+ region CSV if reused from the Phase 3.7 pattern)
- at least one figure path that reads the same summary/surface artifacts instead of private script-only cache names

HPC-safe proof commands to keep in the resume pack:

```bash
python scripts/build_phase4_gwd30_pixel_stats.py \
  --year 2016 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --aggregation monthly \
  --worker-count 1 \
  --no-skip
```

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2016 \
  --end-year 2016 \
  --no-skip
```

If S01 introduces a new contract CLI, it should be verified **after** these two commands succeed, not instead of them.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| `0.25°` area-weighted wetland-fraction aggregation | `scripts/plot_tropical_wetland_025deg.py` + `WA.visualization.coarse_scale` helpers | The aggregation/cache logic already exists; S01 needs to expose it through a stable library API, not recreate the math. |
| Hotspot quota + manifest + debug artifact writing | `src/WA/phase37_hotspots.py` | This is the most mature JSON/CSV/region-summary/debug pattern in the repo and already reads the ten-region catalog. |
| GWD30 Stage-1 resumable input path | `src/WA/comparison/trends.py::build_gwd30_native_pixel_statistics_tiles` and `scripts/build_phase4_gwd30_pixel_stats.py` | This is the current low-risk path; the older full-tropics reduction route is specifically called out as HPC-risky. |

## Constraints

- **Do not change `config/` without approval.** `config/priority_regions.yaml` should be treated as the read-only region catalog; canonical-subset selection must live elsewhere.
- **Default target year is 2016.** S01 proof commands and new defaults should use 2016 unless there is a deliberate exception.
- **GWD30 must stay on the staged / pixel-statistics route.** The old full-tropics reduce chain is a historical/stale path with known HPC/OOM pain.
- **Berkeley valid mask semantics matter.** `phase4_regional.py` computes summaries over Berkeley-valid spatial footprints; the contract must record whether a surface or summary is Berkeley-masked or raw-bbox.
- **Visible progress is required for GWD30 loops.** Existing `tqdm` patterns in `phase4_regional.py` and `trends.py` should be preserved or mirrored.
- **HPC parallel code must fall back broadly, not narrowly.** Follow the existing `except Exception: ... fallback to serial` pattern already present in `phase36.py` when adding new parallel fanout.

## Common Pitfalls

- **Reusing the legacy 4-region defaults** — `DEFAULT_FOCUS_REGION_BBOXES` in `focus_areas.py`, `hotspots.py`, and `trend_agreement.py` do not match the M002 ten-region catalog. S01 should standardize on `region_id` from `priority_regions.yaml`, not on `brazil/africa/southeast_asia/indonesia`.
- **Treating the `0.25°` surface script and Phase 4 summaries as already aligned** — they currently come from different code paths and may carry different valid-domain semantics, especially around Berkeley masking and GWD30 inclusion.
- **Creating a new hotspot record shape** — the repo already has `RoughFocusArea`, `EntropyHotspot`, and `Phase37Hotspot`. S01 should reduce that divergence, not add a fourth incompatible schema.
- **Broad reruns before subset proof** — the current safe order is Stage-1 per year, then Stage-2 per subset region, then wider fanout. Do not make the planner’s first executor task a ten-region wide job.
- **Hardcoding the canonical subset inside a CLI default** — because the subset is a proof-ordering device, it should be editable without rewriting multiple scripts.

## Open Risks

- The **canonical subset list is still a decision surface**. The repo has the ten-region catalog, but no explicit subset file yet.
- The **percentage hotspot score is not yet canonized**. Existing code offers binary disagreement (`rough_binary`) and class entropy (`phase36` / `phase37`) patterns, but no settled continuous wetland-percentage hotspot metric.
- `scripts/plot_tropical_wetland_025deg.py` appears to carry **legacy assumptions** (script-owned API, GWD30 excluded, legacy global default), so some refactor is likely required before it can serve as the S01 surface backbone.
- Later slices still use **separate dataclasses and region defaults**, so S01’s contract needs to be lightweight enough that S02/S03 can adopt it incrementally.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| xarray / raster geospatial Python | `tondevrel/scientific-agent-skills@xarray` | available |
| broader geospatial Python | `davila7/claude-code-templates@geopandas` | available |
