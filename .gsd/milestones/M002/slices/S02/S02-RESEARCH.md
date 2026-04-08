# M002 S02 — Research

**Date:** 2026-04-08

## Summary

This slice primarily serves `R101`, `R104`, `R106`, and `R107`: the existing trend math already computes 0.25° wetland-fraction trends and cross-dataset agreement, but it stops at in-memory `TrendResult` / `TrendAgreementResult` objects and legacy regional summary tables. S01 already established the right contract pattern on the percentage line — contract-tagged outputs, stable relpaths, subset-aware orchestration, and contract-aware figure loaders — so S02 should mirror that shape rather than revisiting the underlying trend statistics.

The important constraint is that the current trend path is already technically aligned with the shared grid. `create_comparison_grid()` defaults to `0.25°`, `load_trend_surface()` already supports GWD30 through staged-tile recovery, and the trend/agreement tests are green. What is missing is the shared-contract boundary: trend outputs have no contract metadata, no contract output naming, no canonical-subset runner, and no stable on-disk artifact family. `hpc_probe_trends.py` is still just a bbox-based diagnostic probe that writes a JSON report.

Baseline verification is good enough to treat this as integration work, not numerical debugging. In the M002 worktree, `python -m pytest tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_comparison/test_phase4_regional.py -q` passed (`51 passed, 1 warning`), `python scripts/hpc_probe_trends.py --help` works, and `python scripts/run_related_tests.py src/WA/comparison/trends.py src/WA/comparison/trend_agreement.py scripts/hpc_probe_trends.py` resolves the expected Phase 4 family.

## Recommendation

Use a thin contract-adapter approach. Keep `src/WA/comparison/trends.py` and `src/WA/comparison/trend_agreement.py` as pure computation modules, and add a small contract layer that resolves contract regions, serializes `TrendResult` / `TrendAgreementResult` into stable NetCDF/CSV artifacts, and attaches the same metadata style S01 already uses for percentage surfaces/summaries/hotspots.

Do **not** turn `scripts/hpc_probe_trends.py` into the shared-contract runner. Keep it as a diagnostic probe. Add a new orchestration entry point patterned after `scripts/run_phase4_percentage_contract.py` — likely `scripts/run_phase4_trend_contract.py` — with `--subset canonical`, `--region`, `--dataset-id`, `--standardized-dir`, `--output-root`, `--no-skip`, and stage-aware logging.

Also do **not** replace the current GWD30 trend load path with S01’s single-year percentage backbone. Trend analysis needs multi-year wetland-fraction time series; the existing staged-tile loader in `trends.py` already provides that and is covered by tests. S02 should adapt the outputs to the contract, not reinvent the input path.

## Implementation Landscape

### Key Files

- `src/WA/comparison/evidence_contract.py` — contract anchor. Right now it hard-validates only three artifact kinds: `surface`, `regional_summary`, and `hotspot_manifest`, all with percentage-era naming/semantics. S02 likely needs new trend-specific artifact semantics before stable output paths can exist.
- `src/WA/comparison/trends.py` — tested trend backbone. `load_trend_surface()` handles GWD30 staged tiles and other loaders, `compute_pixel_trends()` returns the per-pixel math surfaces, and `compute_regional_summary()` still returns a plain DataFrame with `region` + implicit `global` rows and no contract metadata or file output.
- `src/WA/comparison/trend_agreement.py` — tested cross-dataset agreement backbone. It accepts `region_bboxes=` already, but defaults to `DEFAULT_FOCUS_REGION_BBOXES`; its `regional_summary` is also a plain DataFrame with no contract fields, no stable relpaths, and no writers.
- `src/WA/comparison/phase4_regional.py` — best existing pattern to copy. `_phase4_regional_contract_columns()`, `_attach_phase4_regional_contract_columns()`, `_validate_phase4_regional_contract_table()`, and `_write_phase4_contract_summary()` show how to attach/output contract metadata without contaminating the math core.
- `scripts/run_phase4_percentage_contract.py` — orchestration template for S02. It resolves subset/regions/datasets through the contract, keeps visible stage logging, and composes existing producers instead of building a parallel pipeline.
- `src/WA/visualization/phase4.py` — current contract-aware loader/plot pattern. Today it only knows percentage summaries and hotspot CSV companions, but it is the right reference if S02 later needs trend summary/agreement figure loaders.
- `scripts/hpc_probe_trends.py` — diagnostic-only trend probe. Useful for HPC smoke tests and `--help` verification, but it should stay separate from contract orchestration.
- `src/WA/test_selection.py` — current `phase4` category already covers `trends.py`, `trend_agreement.py`, and `scripts/hpc_probe_trends.py`. If S02 adds a new runner script, add it here so `run_related_tests.py` continues to select the right family.
- `src/WA/comparison/trend_contract.py` **(new, recommended seam)** — best place for contract-specific writers/serializers so `trends.py` and `trend_agreement.py` can stay stable.
- `scripts/run_phase4_trend_contract.py` **(new, recommended seam)** — thin contract runner parallel to `run_phase4_percentage_contract.py`.
- `tests/test_comparison/test_trend_contract.py` **(new, recommended seam)** — focused verification for contract output paths, metadata columns, and writer behavior.

### Build Order

1. **Extend the shared contract for trend artifacts.** Decide the smallest persisted set up front: at minimum one per-dataset trend surface artifact and one trend regional-summary artifact; optionally one agreement surface and one agreement summary. This is the first blocker because the current contract file is still percentage-specific.
2. **Add a trend contract adapter/writer layer.** Keep `TrendResult` / `TrendAgreementResult` math untouched. Build helpers that serialize them to stable NetCDF/CSV artifacts, normalize `region` → `region_id`, attach contract metadata, and explicitly carry time/overlap fields.
3. **Wire contract-region execution.** Add a thin runner patterned after `run_phase4_percentage_contract.py`. Resolve `--subset canonical` / `--region` through `EvidenceContract`, pass contract bboxes into `load_trend_surface()` / `compute_trend_agreement()`, and preserve `--standardized-dir`, `--output-root`, `--no-skip`, and stage logs.
4. **Only then add loaders/figures.** If the slice requires side-by-side inspection beyond raw artifacts, extend `WA.visualization.phase4` or add a sibling trend loader/plot module after the contract files exist. Plotting is downstream of the missing artifact contract.

### Verification Approach

- Existing baseline:
  - `python -m pytest tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_comparison/test_phase4_regional.py -q`
  - `python scripts/hpc_probe_trends.py --help`
  - `python scripts/run_related_tests.py src/WA/comparison/trends.py src/WA/comparison/trend_agreement.py scripts/hpc_probe_trends.py`
- First-pass verification after implementation:
  - new trend-contract tests
  - `tests/test_comparison/test_trends.py`
  - `tests/test_comparison/test_trend_agreement.py`
  - `tests/test_comparison/test_phase4_regional.py` if contract-column helpers are reused or copied
- If S02 adds a new runner or figure loader, finish with the full phase4 family currently suggested by `run_related_tests.py`:
  - `tests/test_comparison/test_phase4_regional.py`
  - `tests/test_comparison/test_percentage_backbone.py`
  - `tests/test_comparison/test_percentage_hotspots.py`
  - `tests/test_comparison/test_trends.py`
  - `tests/test_comparison/test_trend_agreement.py`
  - `tests/test_visualization/test_phase4.py`
  - `tests/test_submit_phase4_gwd30_pixel_stats.py`
  - `tests/test_submit_phase4_gwd30_regional_year_split.py`
  - `tests/test_submit_phase4_gwd30_tropical_shards.py`

## Constraints

- `src/WA/comparison/harmonize.py` already defaults `create_comparison_grid()` to `0.25°`, so S02 does **not** need a second grid-definition layer unless the contract resolution changes.
- GWD30 trend loading in `src/WA/comparison/trends.py` depends on staged time-fraction manifests under `standardized_dir/_staging/gwd30_<year>/stage_shard_*.json` plus the loader’s `merge_staged_time_fraction_tiles()` helper. Preserve this multi-year path unless the slice explicitly budgets a replacement.
- `EvidenceContract` currently hard-validates the percentage-era artifact set, so trend-stable output relpaths likely require changes both in `default_artifact_semantics()` and in the required-artifact check during contract initialization.

## Common Pitfalls

- **Blindly keeping the `global` row** — both trend summary functions always append a `global` row. When the runner already scopes to one contract region bbox, that row duplicates the requested region domain and should be filtered or handled deliberately.
- **Drifting back to legacy focus regions** — `compute_trend_agreement()` defaults to `DEFAULT_FOCUS_REGION_BBOXES`. For M002 it must be called with contract-region bboxes from `EvidenceContract`, especially for `--subset canonical`.
- **Overloading `hpc_probe_trends.py`** — it is a diagnostic bbox probe with JSON output, not a contract runner.
- **Missing test-selection wiring for a new script** — current triggers cover `trends.py`, `trend_agreement.py`, and `hpc_probe_trends.py`, but not a future `run_phase4_trend_contract.py` unless it is added to `src/WA/test_selection.py`.
- **Assuming empty-frame concat is harmless** — the current baseline passes with one pandas `FutureWarning` in `phase4_regional.py` around `pd.concat`. If S02 assembles optional/empty artifact tables, handle empties explicitly.

## Open Risks

- The minimum acceptable trend artifact set is still a design choice. Regional summaries are clearly needed; persisted agreement surfaces are probably useful, but should be decided up front so `evidence_contract.py` does not get revised mid-slice.
- If S02 also needs paper-facing figures, `src/WA/visualization/phase4.py` may become too percentage-specific and a sibling trend visualization module may be cleaner than forcing two schemas through one loader.
