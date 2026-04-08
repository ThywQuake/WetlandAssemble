---
estimated_steps: 23
estimated_files: 7
skills_used:
  - brainstorming
---

# T03: Add the canonical classification-contract runner and phase4 reload wiring

Close the slice with a real contract-aware entrypoint and downstream reload helpers so S04 can consume classification artifacts without guessing filenames.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/WA/comparison/classification_contract.py`, `src/WA/comparison/phase36.py`, `src/WA/phase37_hotspots.py`, `src/WA/visualization/phase4.py`, and related-test routing | Fail with stage, `region_id`, `participant_set_key`, and source-path context; never emit a half-written region directory that looks complete. | Keep `--skip` / `--no-skip` behavior visible in logs so long canonical-subset reruns can resume at the region boundary. | Reject bad `--subset` + `--region` combinations, missing source artifacts on reload, and malformed contract metadata instead of inferring filenames or participant sets from directory scans. |

## Load Profile

- **Shared resources**: phase3.6 cache directories, phase3.7 candidate cache/hotspot outputs, and the shared `results/phase4` contract tree.
- **Per-operation cost**: one global disagreement run/reload, one hotspot-selection run/reload, and one contract write/reload cycle per selected region.
- **10x breakpoint**: GWD30-backed phase3.6 materialization and repeated hotspot selection dominate wall time once the canonical subset expands to all ten regions.

## Negative Tests

- **Malformed inputs**: unknown region ids, illegal `--subset` + `--region` combinations, and broken classification metadata JSON during reload.
- **Error paths**: missing phase3.6 outputs, missing phase3.7 hotspot artifacts, or malformed classification summaries/hotspot CSVs surface explicit CLI/reload failures.
- **Boundary conditions**: canonical-subset ordering, one-region smoke runs, and reloads from already-written contract outputs all preserve the same participant-set key and region relpaths.

## Steps

1. Add `scripts/run_phase4_classification_contract.py` as a thin CLI patterned after `scripts/run_phase4_trend_contract.py`: resolve evidence-contract regions/subsets, preserve `--standardized-dir`, `--output-root`, `--year`, `--progress`, and `--no-skip`, and document the narrow-first HPC ladder in the help text.
2. Compose the existing producers instead of rewriting them: call `run_phase36_analysis()` for the global backbone, run or reuse `run_phase37_hotspot_selection()` for hotspot candidates, then write region-scoped contract artifacts through `src/WA/comparison/classification_contract.py`.
3. Extend `src/WA/visualization/phase4.py` with classification reload helpers for region summaries and hotspot tables, and expand `tests/test_visualization/test_phase4.py` to prove missing-path, malformed-metadata, and participant-set/region mismatch failures stay explicit.
4. Update `src/WA/test_selection.py`, `docs/testing/test-categories.md`, and `CHANGELOG.md` so related-test routing and user-facing release notes both know about the new classification contract path.

## Must-Haves

- [ ] The new runner stays a thin orchestration layer over `phase36.py`, `phase37_hotspots.py`, and `classification_contract.py`; it does not absorb scientific logic from those modules.
- [ ] Downstream reload helpers can reopen classification contract summaries/hotspot tables by semantics, and related-test routing covers the new runner/adapter files.

## Done when

- One CLI plus reload helpers cover execution and consumption, the help text documents the HPC ladder, and focused tests/related-test routing prove the classification contract is wired end to end.

## Inputs

- `src/WA/comparison/classification_contract.py`
- `src/WA/comparison/phase4_regional.py`
- `src/WA/comparison/phase36.py`
- `src/WA/phase37_hotspots.py`
- `src/WA/visualization/phase4.py`
- `tests/test_visualization/test_phase4.py`
- `src/WA/test_selection.py`
- `docs/testing/test-categories.md`
- `CHANGELOG.md`

## Expected Output

- `scripts/run_phase4_classification_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_visualization/test_phase4.py`
- `src/WA/test_selection.py`
- `docs/testing/test-categories.md`
- `CHANGELOG.md`

## Verification

ruff check scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py tests/test_visualization/test_phase4.py src/WA/test_selection.py docs/testing/test-categories.md CHANGELOG.md
python scripts/run_phase4_classification_contract.py --help
python -m pytest tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py -q
python scripts/run_related_tests.py src/WA/comparison/classification_contract.py scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py

## Observability Impact

- Signals added/changed: stage-tagged runner logs for `phase36`, `phase37`, `classification_contract_write`, `classification_reload`, `region_id`, `participant_set_key`, and skip/rebuild decisions.
- How a future agent inspects this: `python scripts/run_phase4_classification_contract.py --help`, reload the written summary/hotspot artifacts via `src/WA/visualization/phase4.py`, and run `python scripts/run_related_tests.py ...`.
- Failure state exposed: bad region selection, missing source artifacts, malformed metadata JSON, and hotspot shortfall accounting remain visible in CLI errors/logs.
