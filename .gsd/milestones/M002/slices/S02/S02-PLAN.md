# S02: Trend-correctness backbone on the shared contract

**Goal:** 把现有 `TrendResult` / `TrendAgreementResult` 数学主干接入 S01 已建立的 shared evidence contract：让 canonical subset 的 trend surfaces、regional summaries、agreement artifacts、以及重载入口都走稳定 relpath/metadata，而不是停留在内存对象和 legacy 表格。
**Demo:** After this: After this: 同一批 canonical regions 能产出统一 schema 的 trend metrics、trend hotspot manifests、以及区域级 trend summaries，而不是零散 probe 输出。

## Tasks
- [x] **T01: Added stable trend contract artifact families and strict writer helpers for trend and agreement outputs.** — Create the contract adapter layer that turns in-memory `TrendResult` / `TrendAgreementResult` objects into deterministic files before any orchestration is added.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/trends.py`, `src/WA/comparison/trend_agreement.py`, and the shared contract metadata/export helpers | Fail before writing any output, with `dataset_id`, `region_id`, and participant-set context in the exception/log message. | N/A for the pure writer layer; keep the design cache-safe so later CLI retries can reuse already-written region files. | Reject malformed metadata, duplicate participant keys, or summary tables that still mix a scoped region row with the legacy `global` row. |

## Load Profile

- **Shared resources**: contract NetCDF/CSV output directories under the Phase 4 output root.
- **Per-operation cost**: NetCDF serialization of five trend fields plus CSV summary validation/write per dataset×region, then one agreement surface + summary per region.
- **10x breakpoint**: agreement-surface writes and repeated NetCDF materialization become the first I/O pressure point when widening from the canonical subset to all ten regions.

## Negative Tests

- **Malformed inputs**: unknown artifact kind, duplicate participant ids, malformed metadata JSON, and summaries missing contract columns.
- **Error paths**: non-computed trend results, empty agreement overlap results, or missing output directories raise readable exceptions instead of partial writes.
- **Boundary conditions**: one-region scoped runs drop or rewrite the duplicated legacy `global` summary row, and agreement artifact names stay stable when dataset ids are provided in different orders.

## Steps

1. Extend `src/WA/comparison/evidence_contract.py` so `ArtifactKind` and `default_artifact_semantics()` include dedicated trend families: `trend_surface`, `trend_regional_summary`, `trend_agreement_surface`, and `trend_agreement_summary`, with stable output families such as `trend_surfaces/`, `trend_regional_summaries/`, `trend_agreement_surfaces/`, and `trend_agreement_summaries/`.
2. Add `src/WA/comparison/trend_contract.py` with path helpers, a deterministic participant-set key helper (sorted dataset ids), and writer/validator functions that serialize per-dataset trend surfaces (`sens_slope`, `p_value`, `z_score`, `significant`, `trend_direction`) plus region-scoped CSV summaries, and region-scoped agreement surfaces/summaries with overlap-window metadata.
3. Keep `src/WA/comparison/trends.py` and `src/WA/comparison/trend_agreement.py` as pure compute modules; any contract metadata attachment, summary filtering, or participant-key naming must live in the new adapter layer.
4. Add `tests/test_comparison/test_trend_contract.py` and extend `tests/test_comparison/test_evidence_contract.py` to lock artifact relpaths, metadata JSON, participant-key stability, malformed-table rejection, and the region-scoped summary behavior.

## Must-Haves

- [ ] Dedicated trend/trend-agreement artifact families exist without changing the S01 percentage artifact stems.
- [ ] Writer helpers attach stable contract metadata and region-scoped summary CSVs with no ambiguous duplicate `global` row.

## Done when

- `EvidenceContract` can describe the new artifact families, the new adapter layer round-trips `TrendResult` and `TrendAgreementResult` into stable NetCDF/CSV outputs, and focused contract tests prove path/metadata determinism.
  - Estimate: 90m
  - Files: src/WA/comparison/evidence_contract.py, src/WA/comparison/trend_contract.py, tests/test_comparison/test_evidence_contract.py, tests/test_comparison/test_trend_contract.py
  - Verify: ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_contract.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py
python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py -q
- [x] **T02: Added the canonical trend-contract runner and semantic trend reload helpers.** — Close the slice by composing the existing trend math on the canonical subset and exposing reload helpers that future slices can consume without guessing filenames.

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

1. Add `scripts/run_phase4_trend_contract.py` as a thin CLI patterned after `scripts/run_phase4_percentage_contract.py`: resolve `--subset canonical` / `--region`, preserve `--standardized-dir`, `--output-root`, `--aggregation`, `--start-year`, `--end-year`, `--progress`, and `--no-skip`, and keep `scripts/hpc_probe_trends.py` diagnostic-only.
2. For each selected dataset×region, call `load_trend_surface()` + `compute_pixel_trends()` and write contract trend surfaces/summaries through `src/WA/comparison/trend_contract.py`; then compute per-region agreement with contract-region bboxes only and write agreement artifacts keyed by the sorted participant set.
3. Extend `src/WA/visualization/phase4.py` with contract trend reload helpers so later slices can reopen trend regional summaries and agreement summaries by semantics rather than filename guessing, and expand `tests/test_visualization/test_phase4.py` to prove missing-path and mixed-participant failures stay explicit.
4. Update `src/WA/test_selection.py` and `CHANGELOG.md`, and document the narrow-first HPC ladder in CLI help/comments: first one region/dataset, then canonical subset, always with `--no-skip`.

## Must-Haves

- [ ] The new runner composes the existing trend math and contract writers; it does not absorb logic from `scripts/hpc_probe_trends.py`.
- [ ] Downstream reload helpers can reopen trend summaries/agreement summaries from contract paths with explicit missing-output errors.

## Done when

- One contract-aware CLI plus reload helpers cover execution and consumption, the help text documents the HPC ladder, and focused tests/related-test selection prove the trend contract is wired end-to-end.
  - Estimate: 2h
  - Files: scripts/run_phase4_trend_contract.py, src/WA/visualization/phase4.py, tests/test_visualization/test_phase4.py, src/WA/test_selection.py, CHANGELOG.md
  - Verify: ruff check scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md
python scripts/run_phase4_trend_contract.py --help
python -m pytest tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_visualization/test_phase4.py -q
python scripts/run_related_tests.py src/WA/comparison/trend_contract.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py
