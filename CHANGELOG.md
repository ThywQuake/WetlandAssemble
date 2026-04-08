# Changelog

## 2026-04-08

- Added one shared Phase 4 evidence-contract `--subset {canonical,ten}` selector in `src/WA/comparison/evidence_contract.py`, and wired `scripts/run_phase4_regional.py`, `scripts/run_phase4_trend_contract.py`, and `scripts/run_phase4_hotspot_ledger.py` to log the resolved ordered region list before fanout. The regional runner keeps its legacy no-arg macro+priority route explicit, while contract-aware wide runs now have one fixed ten-region source instead of hand-written lists.
- Added a contract-backed Phase 4 trend hotspot family under `results/phase4/trend_hotspot_manifests/`, with JSON manifests plus CSV companions keyed by sorted participant-set ids, disagreement-first ranking (`1 - agreement_ratio`), and semantic reload helpers in `src/WA/visualization/phase4.py`.
- Added `scripts/run_phase4_trend_contract.py`, which writes/reloads contract-stable trend agreement artifacts and then runs a dedicated `trend-hotspots` stage that fails closed on partial or malformed JSON/CSV pairs instead of reusing them.
- Added a contract-backed unified Phase 4 hotspot ledger under `results/phase4/unified_hotspot_ledgers/`, with semantic reload helpers for percentage, classification, and trend hotspot families, long-form `analysis_object_id` rows that keep family-local score names/percentiles instead of faking cross-family raw-score comparability, and provenance columns for downstream figure work.
- Added `scripts/run_phase4_hotspot_ledger.py`, which logs a dedicated `stage=ledger` flow, validates all three hotspot families before any ledger write, and makes region-scoped skip/rebuild decisions explicit in logs.
- Added focused regression coverage for the Phase 4 evidence contract, trend hotspot ranking/validation, the semantic reload wrappers, the new runners' help surfaces, unified ledger normalization/fail-closed reload behavior, and related-test routing updates for the new Phase 4 comparison surfaces.
- Restored the missing Phase 4 percentage contract backbone: `src/WA/comparison/percentage_backbone.py` now owns the shared 0.25° surface/cache path, explicit GWD30 Stage-1 pixel-statistics surface recovery, and contract-backed multi-dataset surface/summary artifacts keyed by `dataset_key + region_id`.
- Added `src/WA/comparison/percentage_hotspots.py` plus `scripts/run_phase4_percentage_contract.py`, so one contract-aware CLI can materialize percentage regional summaries, stacked coarse surfaces, and atomic hotspot manifest/CSV pairs for one region, `--subset canonical`, or `--subset ten`, with visible `stage=percentage-summary` / `stage=percentage-surface` / `stage=percentage-hotspots` logs and fail-closed skip behavior on partial hotspot pairs.
- Updated `scripts/plot_tropical_wetland_025deg.py`, `src/WA/test_selection.py`, and `docs/testing/test-categories.md` to point at the restored percentage backbone, expose the new percentage runner in related-test routing, and keep the standalone plot entrypoint as a thin wrapper over the shared implementation.

## 2026-04-07

- Phase 4 Berkeley valid-mask source-window resolution now falls back to the earliest available standardized Berkeley file when a year-split request (for example `2017`) does not overlap Berkeley coverage. The valid-mask path still uses one real Berkeley time slice, but it no longer aborts pre-coverage GWD30 yearly runs with `FileNotFoundError`.
- Added `scripts/submit_phase4_gwd30_regional_year_split.sh`, which submits one `run_phase4_regional.py` job per selected year for `gwd30` and one dependent merge job that rebuilds the final `regional_series.csv` and region table from the yearly caches.
- Phase 4 `gwd30` regional processing now supports year-split execution and merge-on-read. The `gwd30` path writes one monthly region cache per year under `results/phase4/cache/gwd30/<region>/years/regional_series_<year>.csv`, and later wide-window runs can reuse those year caches to assemble the final `regional_series.csv` without recomputing every year in one task.
- Phase 4 `gwd30` pixel-statistics regional reduction now accumulates one year's monthly totals incrementally instead of storing every tile-month DataFrame in memory before concatenation. This reduces memory pressure and makes year-scoped HPC fanout practical for large regions such as `pan_trop_subtrop`.
- Phase 4 Berkeley/shared-mask projection for pixel-statistics tiles now subsets the region mask to the target tile bbox before reprojection. This avoids repeatedly reprojecting the full pan-tropical mask for every tile and removes the next OOM bottleneck after the Berkeley mask cold-start fix.
- Added `docs/testing/test-categories.md` as the canonical test-family index and added `scripts/run_related_tests.py` plus `src/WA/test_selection.py` so changed-file paths can be mapped to the smallest relevant pytest subset instead of defaulting to full-suite reruns.
- Added `tests/test_test_selection.py` to lock the related-test mapping behavior for Phase 4, loaders, standardization, and direct test-file selection.
- Phase 4 Berkeley valid-mask cold start now narrows the standardized Berkeley source request to the first real available timestamp inside the requested analysis window before opening any data. On cache miss, the regional workflow no longer concatenates all overlapping Berkeley annual files just to derive one spatial footprint, which directly targets the remaining `berkeley_valid_mask` OOM seen on the long `2013-2022` Amazon run.
- Added a regression test confirming that `build_or_load_phase4_berkeley_valid_mask(...)` now forwards only the first available Berkeley source timestamp (for example `2018-08-01`) into the cold-start open path instead of the whole requested `2013-2022` window.
- Added `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` as the canonical first-stop operator recovery index and added `docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md` as the subordinate Chinese-friendly breadcrumb; both explicitly send route-truth questions back to S03, actual execution copying back to S04, and keep the inherited HPC-only proof gap open while closing `R008` around the compact recovery pack.
- Added `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` as the canonical Phase 4 route audit / risk register, naming the current Stage-1 pixel-stats plus Stage-2 regional-table chain, the still-usable trend probe lane, the historical/stale full-tropics and missing-runner routes, and the carry-forward proof gaps tied to R003 / R004 / R005.
- Added `docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md` as the compact Chinese-friendly pointer back to `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`, preserving the current route, the routes to avoid, and the still-open HPC-only proof boundaries without creating a second source of truth.
- Added `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` as the canonical evidence-graded matrix for M001/S02, with a grading contract that restates the D002 vocabulary, cross-links S01's frozen inventory/drift-boundary artifacts, and separates local proof from HPC/external proof for the early/core phase rows (`Phase 1` through `Phase 3.5`).
- Extended the same matrix with late-phase rows for `Phase 3.6`, `Phase 3.6.1`, `Phase 3.7`, and an explicit Phase 4 split between the current Stage-1 / Stage-2 regional chain and the historical full-tropics reducer route, so newer 2026-04-06 continuation signals are visibly separated from the older 2026-04-05 path.
- Added the first `Module Matrix` block for loader/comparison-core families (`loaders/classification`, `standardized loader`, `standardization & GWD30 staging`, `rough comparison`, `fine-grained comparison`), reusing the D002 rubric and pairing each row with concrete `src/WA/...` + regression-test anchors.
- Completed the remaining higher-level `Module Matrix` families (`validation/GEE references`, `Phase 2.6 regional metrics`, `Phase 3.6 global disagreement`, `Phase 3.7 hotspot/plotting`, `Phase 4 regional/trends`, `visualization surfaces`) and added `Requirement Coverage` plus `Open Proof Gaps` so the matrix now states which surfaces are locally exercised versus which ones still need HPC / external proof.
- Validated `R002` and `R007` against `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` in `.gsd/REQUIREMENTS.md` and added `docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md` as the compact Chinese-friendly re-entry note covering the canonical matrix path, the current-vs-historical Phase 4 split, the still-relevant verification commands, and the remaining HPC-only gaps.
- Validated `R006` against `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`, added the map’s explicit `Requirement Coverage` section, and added `docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md` as a compact Chinese-friendly breadcrumb that points operators back to the canonical next-step execution map instead of creating a second source of truth.

## 2026-04-06

- Phase 4 Berkeley valid-mask cold-start generation now uses a single
  Berkeley time slice to derive the finite spatial footprint instead of
  materializing a multi-time `notnull().any(dim="time")` cube. This cuts the
  peak memory of the mask cache-miss path and directly targets the remaining
  Amazon-region OOM that still happened before GWD30 Stage 2 started.
- Phase 4 Berkeley valid-mask loading now passes the requested region bbox
  directly into the standardized Berkeley time-series loader before any data
  are materialized. This avoids the previous full-domain Berkeley read that
  could OOM before the regional GWD30 Stage 2 path even started.
- Phase 4 Berkeley valid-mask generation now follows the standardized loader
  contract in `config/datasets.yaml` instead of using a Phase 4-specific raw
  Berkeley override. The regional workflow now reads Berkeley from the same
  standardized annual netCDF outputs used elsewhere in analysis-time code.
- Phase 4 regional `gwd30` processing now reads the Stage-1 native
  pixel-statistics tile manifests under `results/phase4/pixel_stats/` instead
  of restoring `_staging/gwd30_<year>/stage_shard_*.json` directly. Regional
  aggregation now applies the Berkeley-valid mask at Stage 2 on each native
  pixel-statistics tile grid and then combines those per-tile monthly areas
  into the final region tables.
- Added `scripts/submit_phase4_gwd30_pixel_stats.sh` so Phase 4 Stage-1
  GWD30 native pixel-statistics jobs can be batch-submitted to SLURM as one
  job per year, with year discovery from `config/datasets.yaml` and overrides
  for aggregation, workers, CPUs, walltime, partition, and `--no-skip`.
- Added a dedicated Phase 4 Stage-1 GWD30 pixel-statistics builder that
  restores staged tiles on their native staged grids and writes transformed
  per-tile statistics datasets containing `wetland_fraction`,
  `valid_observation_count`, `mean_wetland_fraction`, `std_wetland_fraction`,
  and `cell_area_km2` without applying any external mask or reprojection.
  This is intended to feed later region-targeted trend analysis rather than
  the old full-tropics reduce path.
- Phase 4 regional processing no longer depends on the Phase 3.6
  `joint_valid_mask` as its shared analysis mask. The workflow now builds a
  Berkeley-valid spatial mask per region from Berkeley-RWAWC's finite monthly
  watermask extent and uses that mask as the regional denominator for all
  dataset reductions.
- Phase 4 `gwd30` regional processing no longer requires the full-tropics
  cache path in order to produce regional series. It now restores staged tiles
  directly from `standardized/_staging/gwd30_<year>/stage_shard_*.json`,
  filters them by region bbox, and computes the regional monthly series
  directly on demand, which avoids the previous global reduce OOM path.

## 2026-04-05

- Phase 4 regional processing is now data-only: it computes cache-backed
  area-weighted monthly, annual, and climatological time series for
  `gwd30 / giems_mc / topmodel / swamps / wad2m` plus auxiliary
  `berkeley_rwawc`, using the Phase 3.6 500 m shared mask as the base mask
  and writing tables/caches under `results/phase4/` without bundling plotting
  into the same execution path.
- Phase 4 `gwd30` regional processing now restores existing shard manifests
  from `standardized/_staging/gwd30_<year>/stage_shard_*.json`, builds a
  shared full-tropics tile-month cache under
  `results/phase4/cache/gwd30/full_tropics/`, and derives each region from
  that tropical cache instead of rebuilding staged tiles or rescanning
  `tile_*.nc` independently for every region.
- Phase 4 now also has a dedicated sharded HPC path for the `gwd30`
  full-tropics cache: manifest-list builder, one-shard runner, shard reducer,
  and a SLURM submit script that maps each manifest list to one array task and
  then writes the final yearly `tile_monthly_<year>.csv` cache before the
  regional workflow consumes it.
- Phase 4 `gwd30` sharded HPC cache building now defers Phase 3.6 shared-mask
  application to the final merge stage: shard tasks now transform staged
  `tile_*.nc` files into smaller pixel-scale `wetland_weighted + coverage`
  time cubes without any mask, and the reduce job then applies the shared mask
  tile-by-tile with optional multi-core workers. The reducer now also reads
  only the current manifest-list summary instead of globbing all historical
  partials, which prevents stale shard outputs from being mixed into a new run.
- Phase 4 `hpc_probe_trends.py` now restores `gwd30` staged tiles from the
  standardized staging root instead of using an ad hoc Phase 4 cache root,
  so trend probes reuse the existing shard-manifest partials rather than
  falling back to a fresh raw-staging path.

## 2026-04-04

- Phase 3.7 raw hotspot panel legends now append the class ID to each
  categorical label (for example `Coastal Marsh 11`) so duplicate class names
  remain distinguishable, and the raw-mode legend layout now orders the bottom
  patch area as `G2017 / GLWD v2 / GWD30` on the first row and
  `Unified Majority / Entropy` on the second row.
- Phase 3.6 `gwd30_source_dominant_class` extraction now uses the same
  wetland-first annual selection rule as GWD30 unified dominance: prefer
  wetland source classes first, then water, and only fall back to
  non-wetland when neither wetland nor water is present. The Phase 3.6 cache
  version was bumped so stale source-dominant caches are not silently reused.
- Phase 3.6 now supports an explicit `--static-worker-count` override so the
  G2017 and GLWD v2 stage[01] global cache builds can run through a shared
  stripe-level worker pool on HPC, allowing GLWD v2 to use more than one
  worker when available, with broad-exception fallback back to serial
  execution if the static parallel path fails.
- Phase 3.6 now supports an explicit `--gwd30-worker-count` override so HPC
  runs can raise GWD30 staged/reduced tile transform parallelism above the
  conservative automatic cap of 4 when the node has sufficient memory.
- Phase 3.6 GWD30 raw/source dominant-class export now aggregates
  `annual_source_weighted_sum` from reduced tiles instead of reconstructing
  full staged time cubes stripe-by-stripe, which avoids the new stage[01]
  OOM path on HPC and still writes `gwd30_source_dominant_class` into the
  final Phase 3.6 classes output.
- Phase 3.7 raw hotspot panels now render four independent classification
  legends in the 2x3 layout: one for `Unified Majority` and one each for
  `G2017`, `GLWD v2`, and `GWD30`, instead of visually grouping them around a
  shared legend area.

## 2026-04-02

- GWD30 Phase 3.6 reduced-tile transforms now validate the staged tile source
  before reusing cached outputs, so stale reduced tiles are rebuilt instead of
  being silently reused after staged tile updates.

## 2026-04-03

- Phase 3.6 now writes each dataset's precomputed raw/source dominant classes
  into the staged dominant caches and final `phase3_6_unified_classes_*.nc`
  outputs, and Phase 3.7 hotspot panels now prefer those cached variables
  instead of re-deriving source dominance during plotting.
- Phase 3.7 hotspot panels now keep hotspot selection on the unified
  coarse classes but switch per-dataset hotspot inspection to each source
  dataset's raw dominant classes loaded from standardized outputs, with
  per-dataset stable legends that only list classes present in the panel.
- Added a small world-map plotting script for `config/priority_regions.yaml`
  that draws coastlines, highlights each region bbox, and annotates every
  region with callout text on the map.
- Updated the priority-region world map labels so every annotation is anchored
  from the bbox top-right corner with stacked offsets to reduce overlap in
  crowded areas.

## 2026-04-01

- Phase 3.6 GWD30 annual dominant-class selection now prefers wetland classes
  over `Non-wetland` and `Water` whenever any wetland class is present in the
  annual fractions, and only falls back to `Non-wetland` vs `Water` when no
  wetland class is present.
- Phase 3.6 cache reads are now version-aware so stale dominant-class and
  metrics outputs are rebuilt after algorithm changes instead of being silently
  reused.
- Added a Phase 3.6.1 hotspot trace diagnostic that compares GWD30 raw tiles,
  staged tiles, reduced tiles, and final Phase 3.6 outputs for selected
  hotspots.
- Added a minimal Phase 3.6.1 hotspot file-list script that only outputs the
  matching raw tif, staged tile, and reduced tile paths for selected hotspots.
- Phase 3.6.1 hotspot trace and file-list scripts now default to all hotspots
  from the manifest when `--hotspots` is not provided.
