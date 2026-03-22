# 2026-03-18 Plan Summary

## Architecture decisions

- Canonical plan is `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`.
- Workflow is split into loaders, comparison, GEE truth imagery, and review manifests.
- Workflow now explicitly includes a separate trend-analysis phase between comparison and GEE truth review.
- Rough-scale truth uses MODIS via GEE.
- Fine-grained truth uses Shannon-entropy hotspots plus Sentinel-2 via GEE.
- Trend analysis covers short-term year-over-year change and long-term multi-decadal change with Mann-Kendall and Sen's slope.
- GEE uses existing `config/gee_config.yaml` only; no `config/` schema expansion is assumed.
- `lstm_wetland` remains out of scope until documentation exists.

## Modified files and key changes

- Added new canonical plan with sequence-based naming, completed GEE requirements, and restored the missing Trend Analysis phase.
- Added stash summary for fast handoff.

## Verification status

- Plan research completed against `CLAUDE.md`, `docs/aim.md`, `config/datasets.yaml`, `config/gee_config.yaml`, dataset docs, and official Earth Engine documentation.
- No code tests run because this turn only produced planning artifacts.

## Open risks, TODOs, rollback notes

- Old draft `docs/plans/2026-03-18-feat-dataset-loaders-plan.md` still exists and should be treated as superseded, not canonical.
- Actual implementation will need a decision on whether `getDownloadURL`, `computePixels`, or `Export` is the default for each AOI size band.
- Historical fine-grained hotspots before Sentinel-2 availability are intentionally unsupported in this plan and need explicit manifest states.
- Trend outputs must distinguish dataset-native windows from cross-dataset overlap windows to avoid false temporal comparisons.
