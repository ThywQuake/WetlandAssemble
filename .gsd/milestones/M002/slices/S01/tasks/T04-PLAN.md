---
estimated_steps: 23
estimated_files: 5
skills_used: []
---

# T04: Add percentage hotspot manifests and proof-oriented orchestration for the canonical subset

Finish S01 by writing the first contract-shaped percentage hotspot outputs and a thin orchestration surface that can run the canonical subset proof without inventing a parallel pipeline.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Contract surfaces/summaries, `src/WA/phase37_hotspots.py` patterns, and visualization writers | Fail with `region_id`, `dataset_id`, and hotspot stage instead of emitting partial manifests. | Preserve per-region progress + cache reuse so long canonical-subset runs can resume after a partial failure. | Reject missing contract columns/attrs, duplicate AOI records, or zero-cell hotspot candidates before final manifest write. |

## Load Profile

- **Shared resources**: contract NetCDF/CSV outputs, hotspot manifest JSON/CSV files, and figure outputs.
- **Per-operation cost**: per-region candidate scoring plus manifest serialization and plot generation.
- **10x breakpoint**: candidate clustering and per-region fanout become the first memory/I/O pressure point when widening from the canonical subset to all ten regions.

## Negative Tests

- **Malformed inputs**: missing hotspot columns, malformed manifest metadata, invalid subset names, and duplicate region/hotspot ids.
- **Error paths**: no valid hotspot cells, missing upstream surface/summary files, or visualization write failures are surfaced explicitly.
- **Boundary conditions**: nearby hotspot deduplication, zero-hotspot regions, and canonical subset orchestration still preserve the shared object schema.

## Steps

1. Add `src/WA/comparison/percentage_hotspots.py` that reuses the Phase-3.7 quota/manifest pattern but emits contract hotspot records from percentage surfaces/regional summaries rather than `RoughFocusArea`-style AOIs.
2. Add `scripts/run_phase4_percentage_contract.py` as a thin orchestration CLI that can run `--subset canonical` end to end after Stage-1 data exists, while preserving `--no-skip`, visible progress, and stage-aware logging.
3. Update `src/WA/visualization/phase4.py` to consume the contract summary/hotspot outputs rather than ad hoc CSV naming assumptions, and add `tests/test_comparison/test_percentage_hotspots.py` plus `tests/test_visualization/test_phase4.py` coverage.
4. Keep the proof commands explicit in help text and comments so the operator can run Stage-1 2016, Stage-2 amazon, then canonical subset orchestration on HPC without guessing the next command.

## Must-Haves

- [ ] Percentage hotspots land as manifest + CSV outputs under the shared contract, ready for later classification/trend adoption.
- [ ] The orchestration surface composes existing producers; it does not create a second standalone wetland-percentage pipeline.

## Done when

- Canonical subset orchestration and hotspot manifests exist behind one contract-aware CLI/module path, and the hotspot/visualization tests prove the new shared object shape is consumable.

## Inputs

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/percentage_backbone.py`
- `src/WA/comparison/phase4_regional.py`
- `src/WA/phase37_hotspots.py`
- `src/WA/visualization/phase4.py`
- `tests/test_visualization/test_phase4.py`

## Expected Output

- `src/WA/comparison/percentage_hotspots.py`
- `scripts/run_phase4_percentage_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_percentage_hotspots.py`
- `tests/test_visualization/test_phase4.py`

## Verification

python -m pytest tests/test_comparison/test_percentage_hotspots.py tests/test_visualization/test_phase4.py -q
python scripts/run_related_tests.py src/WA/comparison/percentage_hotspots.py src/WA/visualization/phase4.py scripts/run_phase4_percentage_contract.py

## Observability Impact

- Signals added/changed: per-region hotspot quota/selection summaries, manifest write counts, orchestration stage logs, and figure output paths.
- How a future agent inspects this: inspect hotspot manifest JSON/CSV outputs, any region-summary sidecar CSVs, generated phase4 figures, and CLI logs.
- Failure state exposed: zero-hotspot regions, duplicate AOIs, or missing contract columns are visible in manifest summaries, tests, and stage-aware log messages.
