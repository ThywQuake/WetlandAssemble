---
estimated_steps: 23
estimated_files: 5
skills_used: []
---

# T02: Wire the canonical trend-contract runner and downstream reload helpers

Close the slice by composing the existing trend math on the canonical subset and exposing reload helpers that future slices can consume without guessing filenames.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/trends.py`, `src/WA/comparison/trend_agreement.py`, the new contract writers, staged GWD30 inputs, and S01 Phase 4 visualization reload patterns | Fail with stage, `dataset_id`, `region_id`, and participant-set context; never emit partial agreement artifacts silently. | Keep `--skip/--no-skip` behavior visible in logs so a long canonical-subset rerun can resume at the region/dataset boundary. | Reject missing trend artifacts, mixed participant-set outputs, or malformed contract metadata instead of inferring filenames or participant membership silently. |

## Load Profile

- **Shared resources**: staged GWD30 tile manifests, trend NetCDF/CSV outputs, and any derived reload tables.
- **Per-operation cost**: one trend surface load plus Mann-Kendall write per dataset×region, then one agreement stack/write per region.
- **10x breakpoint**: GWD30 staged-tile reads and agreement stacking across many datasets become the first runtime/I/O bottleneck when scaling beyond the canonical subset.

## Negative Tests

- **Malformed inputs**: bad `--subset` / `--region` combinations, unknown dataset ids, and malformed participant-key metadata.
- **Error paths**: missing staged GWD30 manifests, missing trend output files during reload, or empty agreement overlap results all stay explicit.
- **Boundary conditions**: one-region dry runs, dataset-id order differences, and missing optional dataset outputs do not corrupt the participant-set naming or reload logic.

## Steps

1. Add `scripts/run_phase4_trend_contract.py` as a thin CLI patterned after `scripts/run_phase4_percentage_contract.py`: resolve `--subset canonical` / `--region`, preserve `--standardized-dir`, `--output-root`, `--aggregation`, `--start-year`, `--end-year`, `--progress`, and `--no-skip`, keep `scripts/hpc_probe_trends.py` diagnostic-only, and define a `DEFAULT_TREND_CONTRACT_DATASET_IDS` list only from datasets that the existing trend loaders/tests already prove trend-capable instead of blindly inheriting the percentage runner defaults.
2. For each selected dataset×region, call `load_trend_surface()` + `compute_pixel_trends()` and write contract trend surfaces/summaries through `src/WA/comparison/trend_contract.py`; then compute per-region agreement with contract-region bboxes only and write agreement artifacts keyed by the sorted participant set.
3. Extend `src/WA/visualization/phase4.py` with contract trend reload helpers so later slices can reopen trend regional summaries and agreement summaries by semantics rather than filename guessing, and expand `tests/test_visualization/test_phase4.py` to prove missing-path and mixed-participant failures stay explicit.
4. Update `src/WA/test_selection.py` and `CHANGELOG.md`, and document the narrow-first HPC ladder in CLI help/comments: first one region/dataset, then canonical subset, always with `--no-skip`.

## Must-Haves

- [ ] The new runner composes the existing trend math and contract writers; it does not absorb logic from `scripts/hpc_probe_trends.py`.
- [ ] Downstream reload helpers can reopen trend summaries/agreement summaries from contract paths with explicit missing-output errors.

## Done when

- One contract-aware CLI plus reload helpers cover execution and consumption, the help text documents the HPC ladder, and focused tests/related-test selection prove the trend contract is wired end-to-end.

## Inputs

- `src/WA/comparison/trend_contract.py`
- `src/WA/comparison/trends.py`
- `src/WA/comparison/trend_agreement.py`
- `scripts/run_phase4_percentage_contract.py`
- `scripts/hpc_probe_trends.py`
- `src/WA/visualization/phase4.py`
- `tests/test_visualization/test_phase4.py`
- `src/WA/test_selection.py`
- `CHANGELOG.md`

## Expected Output

- `scripts/run_phase4_trend_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_visualization/test_phase4.py`
- `src/WA/test_selection.py`
- `CHANGELOG.md`

## Verification

ruff check scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md
python scripts/run_phase4_trend_contract.py --help
python -m pytest tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_visualization/test_phase4.py -q
python scripts/run_related_tests.py src/WA/comparison/trend_contract.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py

## Observability Impact

The runner must log `trend-load`, `trend-write`, `agreement`, and `reload` stages with `dataset_id`, `region_id`, participant-set key, and output paths; reload helpers must surface missing/mixed artifacts with the same identifiers so S04 can diagnose failures quickly.
