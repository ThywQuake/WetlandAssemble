---
id: T03
parent: S05
milestone: M002
key_files:
  - src/WA/comparison/classification_contract.py
  - scripts/run_phase4_classification_contract.py
  - src/WA/visualization/phase4.py
  - tests/test_comparison/test_classification_contract.py
  - tests/test_visualization/test_phase4.py
  - CHANGELOG.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-09-007-m002-s05-t03-classification-contract.md
key_decisions:
  - D045 — keep `classification_key=canonical` as the contract family key for the fixed `g2017+glwd_v2+gwd30` participant set, and rewrite region hotspot artifacts from the Phase 3.7 source trio instead of recomputing hotspot selection inside the Phase 4 adapter.
duration: 
verification_result: mixed
completed_at: 2026-04-08T19:13:28.209Z
blocker_discovered: false
---

# T03: Restored the real Phase 4 classification contract adapter, runner, and semantic reload helpers over the existing Phase 3.6/3.7 producers.

**Restored the real Phase 4 classification contract adapter, runner, and semantic reload helpers over the existing Phase 3.6/3.7 producers.**

## What Happened

Added `src/WA/comparison/classification_contract.py` as the real Phase 4 classification adapter over Phase 3.6 and Phase 3.7, writing region-scoped classification surfaces, summaries, and fail-closed hotspot manifest/CSV pairs while preserving the full entropy/agreement/dominant-class diagnostic payload and fixed participant provenance (`g2017+glwd_v2+gwd30`). Added `scripts/run_phase4_classification_contract.py` as the thin orchestration CLI for one region, `canonical`, or `ten`, keeping the project default year at 2016 and delegating all science back to the existing Phase 3.6/3.7 producers. Extended `src/WA/visualization/phase4.py` with classification semantic reload wrappers, added focused regressions for relpaths, malformed Phase 3.6/3.7 inputs, descending-lat slicing, and CLI help behavior, and recorded the downstream decision/knowledge/stash breadcrumbs required by the project contract.

## Verification

Passed the task-plan verification commands exactly as written: targeted `ruff check`, `python scripts/run_phase4_classification_contract.py --help`, and `python -m pytest tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py -q` (`15 passed`). I also ran the project-required broader suite check `python -m pytest tests/`; it still reproduces the existing unrelated `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` failure and then the full run is killed later with exit `137`, matching the same repository-wide boundary already seen in earlier S05 task work rather than a new classification regression. I reran `python -m pytest tests/test_mgrs_tiling.py -q` separately to confirm that red bar in isolation.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/comparison/classification_contract.py scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py` | 0 | ✅ pass | 111ms |
| 2 | `python scripts/run_phase4_classification_contract.py --help` | 0 | ✅ pass | 1918ms |
| 3 | `python -m pytest tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py -q` | 0 | ✅ pass | 6300ms |
| 4 | `python -m pytest tests/` | 137 | ❌ fail | 63400ms |
| 5 | `python -m pytest tests/test_mgrs_tiling.py -q` | 1 | ❌ fail | 400ms |

## Deviations

Beyond the task plan’s expected output files, I also updated CHANGELOG.md, .gsd/KNOWLEDGE.md, recorded D045, and wrote docs/stashes/2026-04-09-007-m002-s05-t03-classification-contract.md because the project contract requires changelog maintenance, durable architectural breadcrumbs, and a quick-reference stash with specific HPC commands after user-visible CLI changes.

## Known Issues

`python -m pytest tests/` still reproduces the pre-existing unrelated failure at `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` and the broad run is later killed with exit 137 before the suite completes. No real HPC execution against external standardized inputs was run from this worktree.

## Files Created/Modified

- `src/WA/comparison/classification_contract.py`
- `scripts/run_phase4_classification_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_classification_contract.py`
- `tests/test_visualization/test_phase4.py`
- `CHANGELOG.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-09-007-m002-s05-t03-classification-contract.md`
