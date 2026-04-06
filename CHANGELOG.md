# Changelog

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
