# Test Categories

This file is the curated index for targeted pytest runs. It exists so we stop defaulting to `python -m pytest tests/` for every small change.

## Rule of Use

- Prefer **related tests only** for normal code changes.
- Use the changed file path to pick the smallest relevant pytest subset.
- Only broaden beyond the related subset when the change crosses category boundaries or touches shared infrastructure.
- Keep `ruff check` in the loop for edited Python files.

## Quick Helper

List the curated families:

```bash
python scripts/run_related_tests.py --list-categories
```

Infer the related tests for one or more changed files:

```bash
python scripts/run_related_tests.py src/WA/comparison/phase4_regional.py
```

Infer and run them immediately:

```bash
python scripts/run_related_tests.py --run src/WA/comparison/phase4_regional.py
```

## Curated Families

### core_infra
Core config, classification, runtime bootstrap, and shared utility tests.

```bash
python -m pytest \
  tests/test_classification.py \
  tests/test_config.py \
  tests/test_geo_env.py \
  tests/test_mgrs_tiling.py \
  tests/test_progress.py
```

### loaders
Dataset loader, standardized loader, and loader probe surfaces.

```bash
python -m pytest tests/test_loader_probe.py tests/test_standardized_loader.py tests/test_loaders/
```

### standardization_and_gwd30_io
Standardization, GWD30 staging/audit, and rsync/download helper tests.

```bash
python -m pytest \
  tests/test_standardize.py \
  tests/test_submit_standardize.py \
  tests/test_check_gwd30_sizes_from_manifest.py \
  tests/test_check_gwd30_tiffs.py \
  tests/test_download_gwd30_local_then_rsync.py \
  tests/test_fetch_gwd30_remote_sizes.py \
  tests/test_redownload_obs_api.py \
  tests/test_submit_gwd30_sharded.py
```

### phase2_rough
Phase 2 rough binary comparison, probe, and failure-inspection tests.

```bash
python -m pytest \
  tests/test_rough_batch.py \
  tests/test_rough_probe.py \
  tests/test_hpc_probe_rough_binary_script.py \
  tests/test_inspect_phase2_rough_failures_script.py \
  tests/test_comparison/test_harmonize.py \
  tests/test_comparison/test_rough_binary.py
```

### phase2_reference_downloads
MODIS/Landsat download and review-manifest tests.

```bash
python -m pytest \
  tests/test_modis_batch.py \
  tests/test_landsat_batch.py \
  tests/test_landsat_review_manifest.py \
  tests/test_validation/test_modis_reference.py \
  tests/test_validation/test_landsat_reference.py
```

### phase2_6
Phase 2.6 metrics, imagery, plotting, and regional-panel tests.

```bash
python -m pytest \
  tests/test_phase2_6_analysis.py \
  tests/test_phase2_6_plotting.py \
  tests/test_phase2_6_region_imagery.py \
  tests/test_phase2_6_regional_panels.py
```

### phase3_core
Fine-grained comparison, hotspot logic, and S2 validation tests.

```bash
python -m pytest \
  tests/test_s2_batch.py \
  tests/test_comparison/test_fine_grained.py \
  tests/test_comparison/test_focus_areas.py \
  tests/test_comparison/test_hotspots.py \
  tests/test_validation/test_s2_reference.py
```

### phase3_6
Phase 3.6 disagreement analysis and 3.6.1 trace diagnostics tests.

```bash
python -m pytest tests/test_phase3_6_analysis.py tests/test_phase3_6_1_gwd30_trace.py
```

### phase3_7
Phase 3.7 hotspot selection, plotting, and regional panel tests.

```bash
python -m pytest \
  tests/test_phase3_7_hotspots.py \
  tests/test_phase3_7_plotting.py \
  tests/test_phase3_7_hotspot_panels.py \
  tests/test_phase3_7_regional_panels.py
```

### phase4
Phase 4 contract, percentage/regional analysis, trend, agreement, readiness, paper-pack, hotspot ledger, and submit-script tests.

```bash
python -m pytest \
  tests/test_comparison/test_classification_contract.py \
  tests/test_comparison/test_evidence_contract.py \
  tests/test_comparison/test_hotspot_ledger.py \
  tests/test_comparison/test_percentage_backbone.py \
  tests/test_comparison/test_percentage_hotspots.py \
  tests/test_comparison/test_phase4_regional.py \
  tests/test_comparison/test_scaleout_readiness.py \
  tests/test_comparison/test_trend_hotspots.py \
  tests/test_comparison/test_trends.py \
  tests/test_comparison/test_trend_agreement.py \
  tests/test_comparison/test_trend_contract.py \
  tests/test_visualization/test_phase4.py \
  tests/test_visualization/test_phase4_pack.py \
  tests/test_submit_phase4_gwd30_pixel_stats.py \
  tests/test_submit_phase4_gwd30_regional_year_split.py \
  tests/test_submit_phase4_gwd30_tropical_shards.py \
  tests/test_submit_phase4_trend_contract.py
```

### visualization_misc
Shared visualization primitives and standalone plotting script tests.

```bash
python -m pytest \
  tests/test_visualization/test_coarse_scale.py \
  tests/test_visualization/test_comparison_panel.py \
  tests/test_visualization/test_panel.py \
  tests/test_plot_priority_regions_world.py \
  tests/test_plot_tropical_wetland_025deg.py
```

### gee_validation
GEE wrapper and reference-integration tests guarded by the existing `gee` marker.

```bash
python -m pytest -m gee tests/test_validation/
```

## Escalation Rule

Broaden the test run only when one of these is true:

- you changed more than one category in the same patch
- you touched shared loader/config/runtime infrastructure
- the related subset fails in a way that suggests a cross-category regression
- the user explicitly asks for a broader run

Otherwise, stick to the related subset.
