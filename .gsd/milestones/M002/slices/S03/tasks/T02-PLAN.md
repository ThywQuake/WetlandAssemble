---
estimated_steps: 23
estimated_files: 6
skills_used:
  - brainstorming
---

# T02: Write classification contract adapters for phase3.6 surfaces and phase3.7 hotspots

Create the adapter layer that turns the proven global disagreement/hotspot producers into region-scoped contract artifacts before any CLI orchestration is added.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/phase36.py`, `src/WA/phase37_hotspots.py`, `src/WA/visualization/phase37.py`, and `src/WA/classification.py` | Fail before writing any contract artifact, with `region_id`, `participant_set_key`, and source artifact path included in the exception/log context. | Region slicing or hotspot rewrite must remain restartable at the region boundary; never leave partially written JSON/CSV pairs that look complete. | Reject missing `joint_valid_mask` / `*_source_dominant_class` variables, mixed-region hotspot rows, malformed bbox payloads, or participant-set metadata mismatches instead of inferring silently. |

## Load Profile

- **Shared resources**: global 500m phase3.6 NetCDF outputs, phase3.7 hotspot manifest/CSV inputs, and the Phase 4 contract output root.
- **Per-operation cost**: reopen one metrics NetCDF plus one dominant-class NetCDF, subset them to a contract bbox, derive region-scoped summary stats, and rewrite one hotspot JSON/CSV pair per region.
- **10x breakpoint**: repeated NetCDF slicing/materialization and hotspot-manifest rewriting become the first I/O bottleneck when widening from the canonical subset to all ten regions.

## Negative Tests

- **Malformed inputs**: missing source-dominant variables, malformed bbox JSON, wrong region ids, and reordered participant ids.
- **Error paths**: missing phase3.6 source files, malformed phase3.7 hotspot manifests, or empty-region summaries all raise explicit validation errors.
- **Boundary conditions**: descending-lat datasets, hotspot shortfall regions, and compatibility with existing `entropy-<region>-NNN` hotspot ids stay intact while the contract metadata adds participant-set context.

## Steps

1. Add `src/WA/comparison/classification_contract.py` with stable output-path helpers plus a deterministic `participant_set_key` builder for the fixed `g2017` / `glwd_v2` / `gwd30` trio.
2. Write region-scoped classification surface builders that subset the phase3.6 metrics/dominant datasets with `subset_phase37_plot_dataset_to_bbox(...)`, preserve the entropy/agreement/joint-valid fields, and keep all three unified + source dominant-class layers.
3. Add summary/hotspot writer + validator helpers that attach contract metadata, explicit source artifact paths, quota/shortfall status, and region-scoped summary rows without reimplementing the phase3.6 or phase3.7 math.
4. Add `tests/test_comparison/test_classification_contract.py` to prove stable relpaths, metadata JSON, summary validation, hotspot manifest rewriting, and readable failure modes on malformed inputs.

## Must-Haves

- [ ] The adapter layer wraps existing phase3.6 / phase3.7 outputs; it does not fork the disagreement math or hotspot-selection rules.
- [ ] Region-scoped contract surfaces keep the full dominant/source-dominant diagnostic payload needed by downstream plotting and S04 ledger work.

## Done when

- Synthetic tests can round-trip phase3.6 + phase3.7 fixtures into stable contract surfaces, summaries, and hotspot manifests, and malformed inputs fail before any partial artifact pair is left behind.

## Inputs

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/phase36.py`
- `src/WA/phase37_hotspots.py`
- `src/WA/visualization/phase37.py`
- `src/WA/classification.py`

## Expected Output

- `src/WA/comparison/classification_contract.py`
- `tests/test_comparison/test_classification_contract.py`

## Verification

ruff check src/WA/comparison/classification_contract.py tests/test_comparison/test_classification_contract.py
python -m pytest tests/test_comparison/test_classification_contract.py -q

## Observability Impact

- Signals added/changed: contract-writer validation errors must include `region_id`, `participant_set_key`, and source artifact paths before any NetCDF/CSV/JSON write.
- How a future agent inspects this: open the written summary/manifest metadata JSON and compare the recorded source paths and participant-set key against the requested region.
- Failure state exposed: missing phase3.6 variables, malformed phase3.7 hotspot rows, and mixed-region rewrites are surfaced as explicit validation failures rather than silent row drops.
