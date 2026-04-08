---
estimated_steps: 12
estimated_files: 7
skills_used: []
---

# T01: Add contract-backed trend hotspot manifests and semantic reloads

Close the main scientific gap first: trend outputs currently stop at agreement surfaces and summaries, so this task creates the missing contract-stable hotspot family before any cross-line ledger work starts.

## Steps

1. Extend `src/WA/comparison/evidence_contract.py` and `tests/test_comparison/test_evidence_contract.py` so the contract locks both `trend_hotspot_manifest` and `unified_hotspot_ledger` artifact families before new writers/runners are added.
2. Add `src/WA/comparison/trend_hotspots.py` with path helpers, disagreement-first hotspot selection over `TrendAgreementResult` (`disputed` candidate mask, `disagreement_score = 1 - agreement_ratio`, `slope_std` tie-breaker), JSON/CSV writers, validators, and provenance-rich manifest/table reload helpers.
3. Extend `scripts/run_phase4_trend_contract.py` with a dedicated `trend-hotspots` stage after agreement write/reload, and add `load_phase4_contract_trend_hotspot_table(...)` to `src/WA/visualization/phase4.py` so downstream code reopens the new family by semantics instead of filename guessing.
4. Add focused tests in `tests/test_comparison/test_trend_hotspots.py` and `tests/test_visualization/test_phase4.py` covering stable relpaths, participant-set metadata, malformed bbox/metadata failures, trend hotspot reload behavior, and runner help/smoke expectations.

## Must-Haves

- [ ] Trend hotspot artifacts are keyed by sorted participant-set ids and stay contract-stable alongside the existing trend surface/summary/agreement families.
- [ ] Trend hotspot ranking is disagreement-first (`1 - agreement_ratio`) and never redefines trend correctness as raw slope magnitude.
- [ ] Runner logging exposes a dedicated `trend-hotspots` stage with region/participant context and fails before any partial JSON/CSV pair is treated as valid.

## Done when

- One region's trend agreement output can be written and reloaded as a hotspot manifest + CSV companion through stable contract helpers, and focused tests pin the ranking, metadata, and failure behavior.

## Inputs

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/trend_contract.py`
- `src/WA/comparison/trend_agreement.py`
- `scripts/run_phase4_trend_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_evidence_contract.py`
- `tests/test_visualization/test_phase4.py`

## Expected Output

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/trend_hotspots.py`
- `scripts/run_phase4_trend_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_evidence_contract.py`
- `tests/test_comparison/test_trend_hotspots.py`
- `tests/test_visualization/test_phase4.py`

## Verification

ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py
python scripts/run_phase4_trend_contract.py --help
python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py -q

## Observability Impact

- Signals added/changed: `trend-hotspots` stage logging plus participant-set / region context on write and reload failures.
- How a future agent inspects this: reload the written table via `load_phase4_contract_trend_hotspot_table(...)` and inspect the manifest's `surface_output_path`, `summary_output_path`, and contract metadata JSON.
- Failure state exposed: missing agreement artifacts, malformed metadata, zero disputed candidates, and participant-set mismatches surface as explicit validation failures before any pair is reused.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/trend_contract.py`, `src/WA/comparison/trend_agreement.py`, the shared `results/phase4` contract tree, and the new `trend_hotspot_manifest` semantics | Abort the `trend-hotspots` stage before any JSON/CSV pair is committed, with `region_id` and `participant_set_key` in the exception/log context. | Resume at the region boundary through visible `--skip` / `--no-skip`; never treat a half-written pair as reusable. | Reject mixed participant ids, malformed `bbox` / `contract_metadata_json`, or empty disputed-candidate selections instead of backfilling guesses.

## Load Profile

- **Shared resources**: trend agreement surfaces/summaries, the shared `results/phase4` contract tree, and region-scoped hotspot JSON/CSV pairs.
- **Per-operation cost**: reopen one agreement surface plus summary per region, rank disputed cells, and write one JSON/CSV pair plus focused tests.
- **10x breakpoint**: per-region surface reopening and local-max ranking over large disputed masks become the first I/O and memory pressure point when the canonical subset expands to all ten regions.

## Negative Tests

- **Malformed inputs**: mixed participant ids, malformed `bbox` JSON, missing agreement variables, and non-JSON-safe metadata.
- **Error paths**: missing agreement surface/summary files, malformed contract metadata, or zero disputed candidates all raise explicit failures.
- **Boundary conditions**: reordered participant ids, hotspot shortfall regions, and tie-break behavior when `agreement_ratio` matches but `slope_std` differs.
