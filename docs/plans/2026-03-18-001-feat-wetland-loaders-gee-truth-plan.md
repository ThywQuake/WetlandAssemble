---
title: "feat: Wetland Comparison Loaders and GEE Truth Workflow"
type: feat
status: active
date: 2026-03-18
supersedes: docs/plans/2026-03-18-feat-dataset-loaders-plan.md
---

# Wetland Comparison Loaders and GEE Truth Workflow

## Overview

Complete the current WA Phase 1 plan by combining four missing pieces into one coherent workflow:

1. Build dataset loaders and harmonization logic for the eight documented wetland datasets stored on HPC.
2. Run rough and fine-grained cross-dataset comparison on a shared spatial/temporal basis.
3. Run short-term and long-term trend analysis on harmonized wetland time series.
4. Use Google Earth Engine (GEE) to download reference imagery for visual truth comparison:
   - MODIS for rough binary comparison focus areas.
   - Sentinel-2 for high-Shannon-entropy fine-grained hotspots.

This plan supersedes the earlier draft at `docs/plans/2026-03-18-feat-dataset-loaders-plan.md`, which captured loader architecture and scientific mapping decisions but did not finish the GEE-based validation workflow.

## Problem Statement

The repository already establishes the project goal of comparing wetland datasets across tropical and subtropical regions (`docs/aim.md`) and already stores an Earth Engine project id in `config/gee_config.yaml`. However, the existing draft plan stops at loader implementation and normalized comparison. It does not define:

- how rough-scale disagreement cells become reviewable visual cases,
- how fine-grained disagreement is prioritized into hotspot AOIs,
- how short-term year-over-year and long-term multi-decadal wetland changes are computed consistently across datasets,
- which GEE datasets should be used for truth-reference imagery,
- how imagery downloads are triggered, named, and tracked,
- how temporal overlap limits are handled for MODIS and Sentinel-2.

Without this stage, the comparison pipeline can produce spatial metrics but cannot answer the project’s temporal-change objective or close the loop with interpretable visual evidence.

## Proposed Solution

Create a five-layer workflow:

1. **Loader & normalization layer**
   Read raw HPC datasets and normalize them into a common `xarray` representation with shared metadata and wetland semantics.

2. **Comparison layer**
   Produce:
   - rough-scale binary `wetland` vs `non_wetland` comparison across all eligible datasets,
   - fine-grained common-class comparison across classification datasets,
   - per-cell Shannon entropy to identify disagreement hotspots.

3. **Trend analysis layer**
   Produce:
   - short-term year-over-year wetland change summaries,
   - long-term multi-decadal trend estimates,
   - dataset-specific and cross-dataset trend agreement outputs.

4. **GEE reference imagery layer**
   Use GEE to create and download reference image chips:
   - MODIS composite chips for rough-scale focus regions.
   - Sentinel-2 cloud-masked composite chips for fine-grained hotspots.

5. **Review artifact layer**
   Persist AOI manifests, download manifests, preview images, GeoTIFF chips, trend artifacts, and review metadata under `results/` so metric outputs, temporal evidence, and visual evidence stay linked.

## Technical Approach

### Architecture

```text
src/WA/
  __init__.py
  config.py
  loaders/
    __init__.py
    base.py
    registry.py
    berkeley.py
    netcdf_generic.py
    swamps.py
    topmodel.py
    g2017.py
    glwd.py
    gwd30.py
  comparison/
    __init__.py
    harmonize.py
    rough_binary.py
    fine_grained.py
    hotspots.py
    focus_areas.py
    trends.py
    trend_agreement.py
  validation/
    __init__.py
    gee_client.py
    modis_reference.py
    s2_reference.py
    manifests.py
    export_policy.py
tests/
  test_config.py
  test_loaders/
  test_comparison/
  test_validation/
results/
  rough_truth/
  fine_truth/
  manifests/
  quicklooks/
  trends/
```

### Phase 1: Loader Foundation and Shared Semantics

Deliverables:

- `src/WA/config.py`
  Load `config/datasets.yaml` and `config/gee_config.yaml` as read-only inputs.
- `src/WA/loaders/base.py`
  Define the dataset loader contract.
- `src/WA/loaders/registry.py`
  Resolve `loader_type` into concrete implementations.
- Per-dataset loaders for the eight documented datasets:
  - Berkeley-RWAWC
  - G2017
  - GIEMS-MC
  - GLWD v2
  - GWD30
  - SWAMPS
  - TOPMODEL
  - WAD2M

Success criteria:

- Every documented dataset loads into a consistent `xr.Dataset` shape with explicit spatial metadata.
- Each loader supports `bbox` and `time_range` subsetting where the source data allows it.
- Shared metadata captures source dataset id, CRS, spatial resolution, temporal coverage, and semantic mapping.

### Phase 2: Rough Binary Comparison and MODIS Truth Workflow

Deliverables:

- `src/WA/comparison/harmonize.py`
  Convert all eligible datasets into common binary classes.
- `src/WA/comparison/rough_binary.py`
  Compute rough-scale binary metrics on a shared comparison grid.
- `src/WA/comparison/focus_areas.py`
  Select focus AOIs from disagreement outputs.
- `src/WA/validation/modis_reference.py`
  Use GEE to download MODIS chips for selected AOIs.

Operational rules:

- Use an overlap window that is valid for the participating wetland datasets **and** MODIS.
- Default MODIS reference collection: `MODIS/061/MOD09A1`.
- Build 8-day reference composites aligned to the target comparison month or nearest valid window.
- Download two artifacts per AOI:
  - quicklook RGB preview for manual inspection,
  - GeoTIFF or NumPy-form chip for reproducible review.

Focus-area selection policy:

- Rank AOIs by disagreement score at the rough binary scale.
- Enforce geographic stratification so Brazil, Indonesia, Southeast Asia, and Africa are all represented when eligible.
- Deduplicate neighboring cells into single review AOIs.

Success criteria:

- Every selected rough AOI has a linked metrics row, geometry, time window, and MODIS download artifact or an explicit skip reason.

### Phase 3: Fine-Grained Comparison, Entropy Hotspots, and Sentinel-2 Truth Workflow

Deliverables:

- `src/WA/comparison/fine_grained.py`
  Compare shared class vocabulary across classification datasets.
- `src/WA/comparison/hotspots.py`
  Compute Shannon entropy and identify hotspot AOIs.
- `src/WA/validation/s2_reference.py`
  Use GEE to build and download cloud-masked Sentinel-2 composites.

Operational rules:

- Fine-grained comparison uses classification datasets only:
  - G2017
  - GLWD v2
  - GWD30
- Compute Shannon entropy on the harmonized fine-grained class representation per analysis cell.
- Extract hotspot AOIs from the upper tail of the entropy distribution, then cluster contiguous or near-contiguous high-entropy cells.
- Default Sentinel-2 collection: `COPERNICUS/S2_SR_HARMONIZED`.
- Default cloud QA companion: `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`.
- Default masking rule: use `cs_cdf >= 0.60`, then create a median composite within the selected time window.

Success criteria:

- Every selected hotspot AOI has:
  - entropy score,
  - class-disagreement summary,
  - target time window,
  - Sentinel-2 reference chip or an explicit unsupported/failed status.

### Phase 4: Trend Analysis

Deliverables:

- `src/WA/comparison/trends.py`
  Compute short-term and long-term wetland change series from harmonized datasets.
- `src/WA/comparison/trend_agreement.py`
  Compare trend direction and magnitude consistency across datasets.
- `results/trends/`
  Persist annual, seasonal, and monthly trend products, summaries, and maps.

Operational rules:

- Respect the configured aggregation levels in `config/datasets.yaml`:
  - `annual`
  - `seasonal`
  - `monthly`
- Respect the configured trend tests in `config/datasets.yaml`:
  - `Mann-Kendall`
  - `Sen's Slope`
- Short-term trend analysis focuses on year-over-year wetland change within the study area.
- Long-term trend analysis focuses on multi-decadal direction, magnitude, and persistence of wetland change over the maximum defensible overlap window per dataset or dataset group.
- Trend analysis should operate on harmonized wetland representations:
  - binary wetland fraction for all eligible dynamic datasets,
  - fine-grained wetland-class fraction where classification-derived time series are meaningful.
- Persist both dataset-specific trend outputs and cross-dataset agreement summaries so temporal consistency can be reviewed separately from spatial agreement.

Success criteria:

- Annual and seasonal wetland change products exist for every eligible dynamic dataset over its supported time window.
- The workflow produces short-term year-over-year change summaries for target regions.
- The workflow produces long-term trend summaries with Mann-Kendall significance and Sen's slope effect size where the time series is sufficient.
- Cross-dataset trend agreement outputs identify where datasets agree on increase, decrease, or stable wetland trajectories.

### Phase 5: Review Manifests, Verification, and Documentation

Deliverables:

- `src/WA/validation/manifests.py`
  Persist one manifest row per AOI download job.
- `results/manifests/*.parquet` or `*.csv`
  Track the end-to-end state of truth workflows.
- `results/quicklooks/`
  Store fast review JPG/PNG outputs.
- `results/rough_truth/` and `results/fine_truth/`
  Store reproducible GeoTIFF/NumPy outputs.
- `results/trends/`
  Store time-series aggregates, trend rasters/tables, and regional summaries.
- `docs/gee-truth-protocol.md`
  Describe truth-reference collection choice, time-window policy, cloud masking, and review guidelines.
- `docs/trend-analysis-protocol.md`
  Describe overlap-window policy, aggregation logic, and statistical testing choices for trend analysis.

Success criteria:

- Reviewers can navigate from metric output to AOI manifest to downloaded reference imagery without manual bookkeeping.

## Alternative Approaches Considered

### 1. Use local STAC downloads instead of GEE

Rejected because the user explicitly wants downloads through GEE, and Earth Engine already provides catalog access, compositing, cloud masking helpers, and export mechanisms that would otherwise need to be rebuilt.

### 2. Use QA60-only masking for Sentinel-2

Rejected because the harmonized Sentinel-2 documentation notes QA60 handling changed over time, while Cloud Score+ provides a clearer continuous usability score and example thresholding pattern for cloud-free compositing.

### 3. Use daily MODIS scenes instead of an 8-day composite

Rejected as the default because rough-scale validation needs stable, low-cloud reference imagery more than day-exact acquisition timing. `MODIS/061/MOD09A1` provides an 8-day 500 m surface reflectance composite chosen using observation coverage and cloud/aerosol criteria, which is more appropriate for manual review chips.

### 4. Do hotspot extraction entirely in GEE

Rejected because the hotspot signal is derived from disagreement among locally normalized HPC datasets. Computing the entropy locally keeps one source of truth for comparison metrics and limits GEE to what the user specifically requested: imagery download and compositing.

## Scientific and Semantic Decisions Carried Forward

### 1. Wetland Definition

Binary comparison uses a **vegetated wetland** definition.

- Exclude open water bodies such as lakes, rivers, reservoirs, lagoons, estuarine water, and shallow marine water.
- Keep `artificial_wetland` as a separate class for rice paddies and aquaculture/salt-pan like classes.
- Treat Berkeley-RWAWC as auxiliary water-reference context only, not as a direct wetland classification truth layer.

### 2. Resampling Policy

- Classification datasets downsampled to coarse comparison grids use **area-weighted wetland fraction**.
- Fraction datasets use bilinear interpolation when resampling.

### 3. Temporal Aggregation Policy

When converting daily or 4-day products to monthly comparison products, keep:

- `wetland_fraction_mean`
- `wetland_fraction_max`

### 4. GWD30 Temporal Interpretation

- 92 bands represent 4-day composites starting on January 1.
- Band `N` corresponds to day `(N - 1) * 4 + 1`.

### 5. TOPMODEL Discovery

- Discover TOPMODEL combinations dynamically from the directory tree.
- Use the confirmed `6 configs x 7 forcings` structure instead of older 4-config assumptions.

### 6. SWAMPS Continuity

- Treat pre-2000 and post-2000 SWAMPS segments as one continuous series.
- Record the sensor-shift year in metadata, but defer bias-correction decisions to downstream analysis.

### 7. Rough and Fine Truth Are Reference Imagery, Not Survey Ground Truth

MODIS and Sentinel-2 downloads provide **visual reference truth proxies** for analyst comparison, not authoritative field labels. The review protocol must preserve that distinction in manifests and documentation.

### 8. Trend Analysis Must Respect Dataset Overlap and Semantics

- Do not compare trend magnitudes across datasets outside their defensible overlap windows.
- Distinguish between trend in wetland fraction, trend in inundation proxy, and trend in classification-derived area share.
- Report trend agreement and disagreement separately from absolute classification agreement.

## Common-Class Mapping for Fine-Grained Comparison

### G2017 Mapping

| Value | Description | Harmonized Class |
|---|---|---|
| 0 | No Data | `nodata` |
| 10 | Open Water | `open_water` |
| 20 | Mangrove | `wetland` |
| 30 | Swamps (Incl. bogs) | `wetland` |
| 40 | Fens | `wetland` |
| 50 | Riverine and Lacustrine | `wetland` |
| 60 | Floodplains (permanent) | `wetland` |
| 70 | Floodplains (seasonal) | `wetland` |
| 80 | Marshes (general) | `wetland` |
| 90 | Marshes (arid) | `wetland` |
| 100 | Marshes (wet meadows) | `wetland` |

### GLWD v2 Mapping

| Value | Description | Harmonized Class |
|---|---|---|
| 00 | Dryland | `non_wetland` |
| 01-07 | Lakes, reservoirs, rivers, streams, permanent water | `open_water` |
| 08-15 | Lacustrine and riverine wetlands | `wetland` |
| 16-21 | Palustrine and ephemeral wetlands | `wetland` |
| 22-27 | Peatlands | `wetland` |
| 28 | Mangrove | `wetland` |
| 29 | Saltmarsh | `wetland` |
| 30 | Large river delta | `wetland` |
| 31 | Other coastal wetland | `wetland` |
| 32 | Salt pan, saline/brackish wetland | `wetland` |
| 33 | Rice paddies | `artificial_wetland` |

### GWD30 Mapping

| Value | Description | Harmonized Class |
|---|---|---|
| 0 | Non-wetland | `non_wetland` |
| 1-6 | River, canal, lake, reservoir, estuary, lagoon | `open_water` |
| 7 | Aquaculture Pond / Salt Pan | `artificial_wetland` |
| 8-13 | Marsh, swamp, floodplain, tidal flat classes | `wetland` |
| 14 | Shallow Marine Water | `open_water` |

## Technical Considerations

### Existing Repository Constraints

- `CLAUDE.md` forbids editing `config/` without approval.
- `config/gee_config.yaml` already stores `gee_project_id: "geopy-472814"`.
- `config/datasets.yaml` already defines dataset paths, time ranges, regions, and analysis metrics.
- There is currently **no** `docs/brainstorms/` directory and **no** `docs/solutions/` directory, so this plan cannot inherit prior brainstorm or institutional learnings.

### Scope Boundary: Eight Documented Datasets vs `lstm_wetland`

`config/datasets.yaml` includes `lstm_wetland`, but the repository’s documented dataset set and existing dataset docs cover eight datasets only. Therefore:

- Loader implementation in this plan targets the eight documented datasets.
- `lstm_wetland` remains explicitly out of scope until dataset documentation and semantics are available.
- The comparison code should fail clearly if asked to include `lstm_wetland` before that work is planned.

### GEE Dataset Choices

#### Rough-scale reference imagery

Default choice:

- `MODIS/061/MOD09A1`

Reasons:

- 500 m surface reflectance is appropriate for coarse AOI review.
- 8-day compositing reduces cloud artifacts.
- Availability starts on `2000-02-18`, matching the modern overlap period for several dynamic wetland datasets.

Fallback:

- `MODIS/061/MOD09GA` only when exact-day inspection is more valuable than a cleaner composite.

#### Fine-grained hotspot imagery

Default choice:

- `COPERNICUS/S2_SR_HARMONIZED`
- linked with `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`

Reasons:

- 10 m to 20 m multispectral SR is appropriate for local hotspot interpretation.
- Harmonized collection handles post-2022 DN shifts.
- Cloud Score+ provides a stable QA signal and official example workflow.

### GEE Download Strategy

Use three download modes:

1. `ee.Image.getDownloadURL()`
   For small AOI chips where request size stays within the documented 32 MB and 10000-grid-dimension limits.
2. `ee.data.computePixels()`
   For computed composites when raw pixel extraction is needed directly in Python.
3. `Export.image.*`
   Only as fallback for larger or slower jobs that should run asynchronously on GEE infrastructure.

Design rule:

- Prefer small synchronous chip downloads for review artifacts.
- Escalate to `Export` when chip size, cloud compositing, or AOI tiling becomes too large for synchronous requests.

### Temporal-Overlap Rules

- MODIS rough-truth workflow only runs for comparison windows on or after `2000-02-18`.
- Sentinel-2 fine-truth workflow only runs for review windows on or after `2017-03-28`.
- If a hotspot is scientifically important but outside Sentinel-2 availability, the manifest records `unsupported_time_window` rather than silently dropping it.

### AOI Definition Rules

Rough AOIs:

- Derived from highest disagreement zones after regional stratification.
- Use cell-cluster buffering so the reference image shows context around the selected cell.

Fine AOIs:

- Derived from contiguous or nearby high-entropy cells.
- Require minimum area and minimum inter-hotspot distance to avoid redundant downloads.

### Trend Analysis Rules

- Use the maximum valid overlap window for cross-dataset trend agreement analyses.
- Allow dataset-specific trend products to use longer native windows when cross-dataset overlap would be too restrictive.
- Preserve both raw aggregated time series and derived trend statistics so trend outputs remain auditable.
- Separate regional summaries for:
  - Brazil,
  - Indonesia,
  - Southeast Asia,
  - Africa,
  - full tropical/subtropical domain.

### Review Artifact Naming

Use deterministic names:

```text
results/rough_truth/{region_slug}/{dataset_window}/{aoi_id}_modis_rgb.jpg
results/rough_truth/{region_slug}/{dataset_window}/{aoi_id}_modis_chip.tif
results/fine_truth/{region_slug}/{dataset_window}/{hotspot_id}_s2_rgb.jpg
results/fine_truth/{region_slug}/{dataset_window}/{hotspot_id}_s2_chip.tif
results/manifests/{run_id}_truth_manifest.parquet
```

### Recommended Dependencies

Base dependencies:

- `xarray`
- `netCDF4`
- `rasterio`
- `rioxarray`
- `dask[distributed]`
- `pyproj`
- `numpy`
- `pandas`
- `pyyaml`

Additional dependencies for this plan:

- `earthengine-api`
- `requests`

Optional:

- `geemap` for notebook-based QA and exploratory inspection, but not as a hard runtime dependency.

## System-Wide Impact

### Interaction Graph

`config/datasets.yaml` and per-dataset semantics in `docs/datasets/*.md` drive loader selection and mapping logic.

`DatasetLoader` output feeds:

1. harmonization,
2. rough binary metrics,
3. fine-grained comparison,
4. entropy hotspot extraction,
5. short-term and long-term trend analysis,
6. AOI selection,
7. GEE image request construction,
8. local truth artifact downloads,
9. manifests and review outputs.

The GEE layer does not replace the local comparison pipeline. It depends on local AOI selection and only provides review imagery.

### Error and Failure Propagation

Expected errors:

- `FileNotFoundError` or malformed raster/NetCDF errors from HPC loaders.
- GEE authentication failures if local credentials are missing or the configured project is not usable.
- Empty image collections for requested date/region windows.
- Cloud masking that removes nearly all pixels from an S2 window.
- Export or download size limit errors for large AOIs.
- Time series too short for defensible Mann-Kendall or Sen's slope estimation.
- Artificial trend breaks introduced by sensor transitions, resolution changes, or varying class semantics.

Required handling:

- Fail fast on loader configuration errors.
- Mark AOIs with explicit terminal states such as `gee_auth_failed`, `empty_collection`, `too_cloudy`, `unsupported_time_window`, or `download_limit_exceeded`.
- Mark trend jobs with explicit terminal states such as `insufficient_observations`, `overlap_window_empty`, or `semantic_incompatibility`.
- Never silently skip AOIs.

### State Lifecycle Risks

Risks:

- Partial download completion can leave orphaned quicklooks without manifests.
- Re-running the same AOI can duplicate files if naming is not deterministic.
- Mixed local and GEE outputs can drift if they do not share stable AOI ids and time windows.

Mitigation:

- Persist AOI manifests before download fan-out.
- Make output paths deterministic from `run_id`, `aoi_id`, `source_collection`, and time window.
- Update manifest status atomically after each download step.

### API Surface Parity

Any future CLI or notebook entry point should expose the same selectors for:

- dataset set,
- comparison scale,
- AOI strategy,
- time window,
- GEE source collection,
- cloud threshold,
- output directory.

Do not hide these decisions inside one-off scripts.

### Integration Test Scenarios

1. A post-2000 rough AOI produces binary metrics, AOI geometry, a MODIS quicklook, and a manifest row.
2. A 2019 fine-grained hotspot produces entropy summary, class disagreement summary, an S2 Cloud Score+ masked composite, and a manifest row.
3. A pre-2017 hotspot is preserved in the hotspot table but marked as `unsupported_time_window` for S2 truth download.
4. A dynamic dataset with sufficient history produces annual, seasonal, and monthly aggregates plus Mann-Kendall and Sen's slope outputs under `results/trends/`.
5. A short time series is retained in aggregate outputs but marked `insufficient_observations` for long-term trend inference.
6. Missing GEE credentials cause a clear setup error before download fan-out begins.
7. A requested AOI exceeding synchronous download limits falls back to tiled extraction or asynchronous export policy, with the path recorded in the manifest.

## Acceptance Criteria

### Functional Requirements

- [x] `src/WA/config.py` reads dataset config and GEE project config without mutating files under `config/`.
- [x] `src/WA/loaders/base.py` defines `load()` and `metadata()` contracts.
- [x] `src/WA/loaders/registry.py` resolves all planned loader types.
- [x] `src/WA/loaders/berkeley.py` loads Berkeley-RWAWC and parses time from filenames.
- [x] `src/WA/loaders/netcdf_generic.py` supports GIEMS-MC and WAD2M with dataset-specific variable mapping and flag handling.
- [x] `src/WA/loaders/swamps.py` supports pre/post-2000 file patterns as one continuous time series.
- [x] `src/WA/loaders/topmodel.py` discovers configs and forcings dynamically from the directory layout.
- [x] `src/WA/loaders/g2017.py` loads the G2017 GeoTIFF bundle.
- [x] `src/WA/loaders/glwd.py` loads GLWD v2 combined and area-by-class products with the documented scale factor rules.
- [x] `src/WA/loaders/gwd30.py` supports tile filtering and VRT-based access for GWD30.
- [x] `src/WA/comparison/rough_binary.py` produces harmonized wetland/non-wetland metrics for all eligible datasets.
- [ ] `src/WA/comparison/fine_grained.py` produces harmonized fine-grained class comparison for G2017, GLWD v2, and GWD30.
- [ ] `src/WA/comparison/hotspots.py` computes Shannon entropy and extracts hotspot AOIs.
- [x] `src/WA/comparison/focus_areas.py` derives rough-scale focus AOIs from disagreement outputs.
- [ ] `src/WA/comparison/trends.py` computes annual, seasonal, and monthly wetland time-series aggregates plus short-term and long-term trend outputs.
- [ ] `src/WA/comparison/trend_agreement.py` summarizes cross-dataset trend agreement for dynamic datasets.
- [x] `src/WA/validation/gee_client.py` authenticates and initializes GEE with the configured project id.
- [x] `src/WA/validation/modis_reference.py` downloads MODIS reference chips for rough AOIs through GEE.
- [ ] `src/WA/validation/s2_reference.py` downloads Cloud Score+-masked Sentinel-2 reference chips for hotspot AOIs through GEE.
- [ ] `src/WA/validation/manifests.py` persists deterministic manifest rows covering AOI id, data source, time window, cloud threshold, output paths, and terminal status.
- [ ] `results/rough_truth/`, `results/fine_truth/`, `results/quicklooks/`, and `results/manifests/` are populated by the workflow.
- [ ] `results/trends/` contains short-term and long-term trend outputs plus regional summaries.
- [ ] `docs/gee-truth-protocol.md` documents the review procedure and source selection rationale.
- [ ] `docs/trend-analysis-protocol.md` documents overlap windows, aggregation levels, and statistical testing choices.

### Non-Functional Requirements

- [ ] Loader outputs remain lazy for large datasets unless eager materialization is explicitly justified.
- [x] GEE collection filters apply spatial and temporal constraints as early as possible.
- [ ] Synchronous download requests respect Earth Engine size limits.
- [x] The workflow is idempotent for repeated AOI downloads.
- [x] Unsupported temporal windows are surfaced explicitly instead of being silently skipped.
- [ ] Trend inference is never computed on time series that fail minimum-length requirements.
- [ ] Sensor or semantic discontinuities are documented whenever they can affect trend interpretation.

### Quality Gates

- [ ] Unit tests cover loader semantics, class mapping, AOI selection, trend aggregation, and manifest state transitions.
- [ ] GEE-dependent tests are isolated behind a marker such as `@pytest.mark.gee`.
- [ ] HPC integration tests are isolated behind `@pytest.mark.hpc`.
- [x] `pytest`, `ruff`, and `mypy` pass for implementation work derived from this plan.

## Success Metrics

- All eight documented datasets load into the normalization pipeline without manual intervention.
- Rough binary comparison produces geographically stratified focus AOIs across the target study regions.
- Every eligible rough AOI has a MODIS reference artifact or an explicit terminal reason.
- Fine-grained comparison surfaces hotspot AOIs with reproducible Shannon entropy ranking.
- Every eligible hotspot AOI has a Sentinel-2 reference artifact or an explicit terminal reason.
- Trend analysis produces year-over-year wetland change summaries for the target regions.
- Trend analysis produces long-term Mann-Kendall and Sen's slope outputs for every eligible dynamic dataset.
- Cross-dataset trend agreement outputs clearly identify where change direction is robust versus disputed.
- Review manifests allow analysts to trace every reference image back to comparison metrics and source settings.

## Dependencies and Prerequisites

- HPC access to the wetland source datasets referenced in `config/datasets.yaml`.
- Valid Earth Engine access for the configured project in `config/gee_config.yaml`.
- Local authentication state created via `ee.Authenticate()` or equivalent Earth Engine CLI auth.
- Sufficient local disk for downloaded quicklooks and chip artifacts.
- Optional GEE export destination only if synchronous downloads prove insufficient.

## Risk Analysis and Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| GWD30 tile mosaics are too expensive to materialize eagerly | High | Filter by bbox, use VRTs, and keep downstream operations windowed |
| MODIS is unavailable for early historical windows | Medium | Restrict rough truth workflow to overlap periods and record unsupported windows |
| Sentinel-2 truth downloads fail for cloudy tropical hotspots | High | Use Cloud Score+, widen the date window, and record cloud-related skip reasons |
| `lstm_wetland` remains undocumented but appears in config | Medium | Keep it out of scope and fail clearly if selected |
| GEE download size limits break large AOIs | Medium | Use deterministic AOI sizing and escalate to `Export` or tiling |
| Reviewers confuse image reference with authoritative field truth | Medium | Make manifest fields and docs explicitly label these artifacts as reference imagery |
| Config changes would violate repository contract | Medium | Reuse existing config keys only; pass new runtime settings via code or environment until approval exists |
| Trend magnitude is biased by inconsistent overlap windows | High | Separate dataset-native trends from cross-dataset overlap trends and document both |
| Sensor transitions or semantic shifts create false trends | High | Add protocol notes, minimum quality checks, and explicit caution flags in outputs |

## Resource Requirements

- One implementation pass for loaders and harmonization.
- One implementation pass for comparison and AOI selection.
- One implementation pass for trend aggregation and statistical testing.
- One implementation pass for GEE reference imagery and manifests.
- Access to Earth Engine credentials on the machine that runs download jobs.
- HPC data visibility for integration checks.

## Future Considerations

- Add optional Landsat fallback for fine-grained truth review before 2017 if the team later needs historical optical reference.
- Add notebook dashboards for browsing AOIs and truth chips after the first manifest format stabilizes.
- Revisit `lstm_wetland` once documentation exists.
- If AOI volume grows substantially, consider Cloud Storage backed export orchestration instead of synchronous chip downloads.

## Documentation Plan

- Keep `docs/datasets/*.md` aligned with actual loader assumptions.
- Add `docs/gee-truth-protocol.md` describing:
  - MODIS and Sentinel-2 collection choices,
  - temporal overlap rules,
  - cloud masking settings,
  - AOI review instructions,
  - known limitations of imagery-as-truth.
- Add `docs/trend-analysis-protocol.md` describing:
  - annual, seasonal, and monthly aggregation logic,
  - overlap-window policy,
  - Mann-Kendall and Sen's slope usage,
  - minimum-length requirements,
  - caveats from sensor or semantic discontinuities.
- Keep `docs/stashes/` updated with short handoff summaries whenever the plan materially changes.

## Sources and References

### Internal References

- Project contract and planning constraints: `CLAUDE.md:1-51`
- Study goal and deliverables: `docs/aim.md`
- Dataset configuration and regions: `config/datasets.yaml:4-163`
- Existing GEE project configuration: `config/gee_config.yaml:1-3`
- Superseded draft: `docs/plans/2026-03-18-feat-dataset-loaders-plan.md`
- Dataset semantics: `docs/datasets/Berkeley-RWAWC.md`, `docs/datasets/G2017.md`, `docs/datasets/GIEMS-MC.md`, `docs/datasets/GLWD v2.md`, `docs/datasets/GWD30.md`, `docs/datasets/SWAMPS.md`, `docs/datasets/TOPMODEL.md`, `docs/datasets/WAD2M.md`

### External References

- Earth Engine Python install and initialization:
  `https://developers.google.com/earth-engine/guides/python_install`
- Earth Engine authentication and project initialization:
  `https://developers.google.com/earth-engine/guides/auth`
- Earth Engine coding best practices:
  `https://developers.google.com/earth-engine/guides/best_practices`
- Earth Engine exporting and extraction overview:
  `https://developers.google.com/earth-engine/guides/exporting`
- Earth Engine image data extraction:
  `https://developers.google.com/earth-engine/guides/data_extraction`
- `ee.Image.getDownloadURL` limits and usage:
  `https://developers.google.com/earth-engine/apidocs/ee-image-getdownloadurl`
- `ee.data.computePixels` usage:
  `https://developers.google.com/earth-engine/apidocs/ee-data-computepixels`
- MODIS 8-day SR catalog entry:
  `https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD09A1`
- MODIS daily SR fallback catalog entry:
  `https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD09GA`
- Sentinel-2 SR harmonized catalog entry:
  `https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED`
- Cloud Score+ catalog entry:
  `https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_CLOUD_SCORE_PLUS_V1_S2_HARMONIZED`

---

# 中文版计划

## 概述

这份计划用于补完当前 WA 第一阶段中缺失的比较、趋势分析和 GEE 真值参考影像流程。完整目标包括四部分：

1. 完成 8 个已文档化湿地数据集的 HPC 加载器与语义统一。
2. 在统一栅格和统一语义下执行 Rough 与 Fine-grained 两层比较。
3. 对统一后的时间序列执行短期与长期趋势分析。
4. 通过 GEE 下载用于人工真值核验的参考影像：
   - Rough 尺度使用 MODIS。
   - Fine-grained 尺度先提取 Shannon entropy 高值热点，再下载 Sentinel-2。

## 关键技术决策

### 1. Rough 尺度真值参考

- 面向 `wetland` / `non_wetland` 二分类比较。
- 从粗尺度分歧结果中选出 focus AOI。
- 默认使用 `MODIS/061/MOD09A1` 作为 GEE 参考影像源。
- 原因是 500 m、8-day composite、云影响更低，适合做区域级人工核验。

### 2. Fine-grained 尺度真值参考

- 仅对分类型数据集执行：
  - G2017
  - GLWD v2
  - GWD30
- 先在统一类别体系上计算 Shannon entropy。
- 提取高 entropy 热点 AOI。
- 默认使用 `COPERNICUS/S2_SR_HARMONIZED`，并通过 `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` 做云掩膜。
- 默认阈值为 `cs_cdf >= 0.60`。

### 3. GEE 下载策略

- 小图块优先使用 `ee.Image.getDownloadURL()`。
- 对计算后的 composite 可使用 `ee.data.computePixels()`。
- 只有在图块过大或请求过慢时才回退到 `Export.image.*`。
- 这样可以在不扩展 `config/` 的前提下完成大多数下载任务，符合仓库“未经批准不修改 config”的约束。

### 4. 时间边界

- MODIS 真值参考仅支持 `2000-02-18` 之后的比较窗口。
- Sentinel-2 真值参考仅支持 `2017-03-28` 之后的窗口。
- 如果热点不在支持时间段内，必须在 manifest 中明确记为 `unsupported_time_window`。

### 5. 真值的定义

- MODIS/S2 在本计划中是“人工判读参考影像”，不是田野调查级别的绝对真值。
- 文档、manifest 和 review 说明必须保留这个边界，避免误解。

### 6. Trend Analysis 规则

- 必须区分短期逐年变化和长期多年代趋势。
- 必须同时保留 `annual`、`seasonal`、`monthly` 聚合结果。
- 长期趋势默认使用 `Mann-Kendall` 与 `Sen's Slope`。
- 跨数据集趋势比较必须受共同时间重叠窗口约束。
- 数据语义或传感器切换可能影响趋势解释时，必须在输出和文档中明确标记。

## 分阶段实施

### 阶段 1：加载器与统一语义

- 完成 8 个已文档化数据集的 loader。
- 建立统一 wetland / non_wetland / open_water / artificial_wetland 语义。
- 让所有数据都能输出标准化 `xr.Dataset`。

### 阶段 2：Rough 比较与 MODIS 核验

- 在统一粗尺度网格上做二分类比较。
- 选出 focus AOI。
- 通过 GEE 下载对应 MODIS 真值参考影像。
- 输出 quicklook、GeoTIFF/NumPy chip 和 manifest。

### 阶段 3：Fine-grained 比较、Entropy 热点与 S2 核验

- 在统一细分类体系上比较 G2017、GLWD v2、GWD30。
- 计算 Shannon entropy。
- 选出热点 AOI。
- 用 GEE 下载 S2 云掩膜复合影像用于人工核验。

### 阶段 4：Trend Analysis

- 对动态数据集生成 `annual`、`seasonal`、`monthly` 聚合时间序列。
- 输出短期逐年变化结果。
- 输出长期多年代趋势结果。
- 采用 `Mann-Kendall` 检验和 `Sen's Slope` 斜率估计。
- 生成数据集内部趋势结果与跨数据集趋势一致性结果。

### 阶段 5：结果组织与文档

- 将所有下载结果统一写入 `results/rough_truth/`、`results/fine_truth/`、`results/quicklooks/`、`results/manifests/`。
- 将趋势结果统一写入 `results/trends/`。
- 补写 `docs/gee-truth-protocol.md`。
- 补写 `docs/trend-analysis-protocol.md`。
- 在 `docs/stashes/` 中保留简短摘要，方便后续接续。

## 验收标准

- [ ] 8 个已文档化数据集可统一加载并参与比较。
- [ ] Rough 尺度 focus AOI 可稳定生成并下载 MODIS 参考影像。
- [ ] Fine-grained 尺度可提取 Shannon entropy 热点并下载 S2 参考影像。
- [ ] 可输出短期逐年湿地变化结果。
- [ ] 可输出长期多年代趋势结果，并包含 `Mann-Kendall` 与 `Sen's Slope`。
- [ ] 可输出跨数据集趋势一致性结果。
- [ ] 所有 AOI 都能在 manifest 中追踪状态、时间窗口、数据源和输出文件。
- [ ] 对不支持时间段、过云、认证失败、下载超限等情况有明确终态，不允许静默跳过。
- [x] 后续实现需通过 `pytest`、`ruff`、`mypy`。
