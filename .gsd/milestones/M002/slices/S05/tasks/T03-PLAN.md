---
estimated_steps: 24
estimated_files: 5
skills_used: []
---

# T03: Restore the classification contract adapter and thin Phase 4 runner

The current snapshot is also missing `src/WA/comparison/classification_contract.py` and `scripts/run_phase4_classification_contract.py` even though older slice artifacts say they landed already. Restore that adapter/runner path on top of `phase36.py` and `phase37_hotspots.py` so the ten-region proof has a real classification producer instead of stale planner text.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/phase36.py`, `src/WA/phase37_hotspots.py`, and `src/WA/visualization/phase4.py` | Fail before any contract artifact is trusted, with `region_id`, `participant_set_key`, and source artifact path in the exception/log context. | Keep region-scoped reruns restartable so one bad region does not force a full ten-region restart. | Reject malformed bbox payloads, mixed-region hotspot rows, missing `joint_valid_mask` / dominant-class variables, or participant-set mismatches instead of inferring silently. |

## Load Profile

- **Shared resources**: Phase 3.6 global disagreement outputs, Phase 3.7 hotspot manifest/CSV inputs, and the shared `results/phase4` contract tree.
- **Per-operation cost**: reopen one global metrics surface plus hotspot-source trio, subset to one contract bbox, then rewrite one region-scoped surface/summary/hotspot family.
- **10x breakpoint**: repeated NetCDF slicing/materialization and hotspot-manifest rewrites become the first I/O bottleneck when widening to all ten regions.

## Negative Tests

- **Malformed inputs**: missing source-dominant variables, malformed bbox JSON, wrong region ids, and participant-set mismatches.
- **Error paths**: missing Phase 3.6 outputs, malformed Phase 3.7 source trios, or bad contract metadata must fail before any output pair looks complete.
- **Boundary conditions**: descending-lat datasets, hotspot shortfall regions, and `amazon → canonical → ten` ordering must all preserve the same participant-set key and relpaths.

## Steps

1. Add `src/WA/comparison/classification_contract.py` as the thin contract adapter over `phase36.py` and `phase37_hotspots.py`, with stable relpaths, region-scoped surface/summary writers, and hotspot rewrite helpers for the fixed `g2017+glwd_v2+gwd30` participant set.
2. Add `scripts/run_phase4_classification_contract.py` as the thin orchestration CLI that resolves one region, `--subset canonical`, or `--subset ten`, keeps the project default year at `2016`, and reuses existing producers instead of moving the science into the runner.
3. Extend `src/WA/visualization/phase4.py` with classification semantic reload helpers so downstream checks can reopen summaries/hotspot tables by semantics instead of guessed filenames.
4. Add `tests/test_comparison/test_classification_contract.py` and extend `tests/test_visualization/test_phase4.py` so relpaths, metadata, malformed-source failures, and runner help/reload behavior are pinned explicitly.

## Must-Haves

- [ ] The classification line is restored as a real contract adapter/runner over `phase36.py` and `phase37_hotspots.py`; no duplicate disagreement science is introduced.
- [ ] Region-scoped classification outputs keep the full entropy / agreement / dominant-class diagnostic payload needed by the ledger and later paper surfaces.
- [ ] Semantic reload helpers make malformed or mixed-region artifacts fail loudly before any ten-region readiness step trusts them.

## Done when

- A real classification contract CLI plus reload helpers can materialize and reopen one region's contract surface/summary/hotspot family, and the same path can widen to `--subset ten` without manual filename guessing.

## Inputs

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/phase36.py`
- `src/WA/phase37_hotspots.py`
- `src/WA/visualization/phase4.py`
- `tests/test_visualization/test_phase4.py`

## Expected Output

- `src/WA/comparison/classification_contract.py`
- `scripts/run_phase4_classification_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_classification_contract.py`
- `tests/test_visualization/test_phase4.py`

## Verification

ruff check src/WA/comparison/classification_contract.py scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py
python scripts/run_phase4_classification_contract.py --help
python -m pytest tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py -q

## Observability Impact

Keep stage-tagged `phase36`, `phase37`, `classification_contract_write`, and `classification_reload` logs with `region_id` and `participant_set_key` so broken source trios or malformed rewrites can be localized quickly.
