---
estimated_steps: 23
estimated_files: 4
skills_used: []
---

# T01: Extend the evidence contract with dedicated trend artifact families and writer helpers

Create the contract adapter layer that turns in-memory `TrendResult` / `TrendAgreementResult` objects into deterministic files before any orchestration is added.

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

## Inputs

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/trends.py`
- `src/WA/comparison/trend_agreement.py`
- `tests/test_comparison/test_evidence_contract.py`
- `tests/test_comparison/test_trends.py`
- `tests/test_comparison/test_trend_agreement.py`

## Expected Output

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/trend_contract.py`
- `tests/test_comparison/test_evidence_contract.py`
- `tests/test_comparison/test_trend_contract.py`

## Verification

ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_contract.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py
python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py -q

## Observability Impact

Writer/validator errors must expose `dataset_id`, `region_id`, participant-set key, and output relpath before any NetCDF/CSV is written, so later CLI retries can tell exactly which artifact family failed.
