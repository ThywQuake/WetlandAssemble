---
id: T02
parent: S04
milestone: M002
key_files:
  - src/WA/comparison/hotspot_ledger.py
  - scripts/run_phase4_hotspot_ledger.py
  - src/WA/visualization/phase4.py
  - tests/test_comparison/test_hotspot_ledger.py
  - tests/test_visualization/test_phase4.py
  - src/WA/test_selection.py
  - CHANGELOG.md
  - docs/stashes/2026-04-09-001-m002-s04-t02-unified-hotspot-ledger.md
key_decisions:
  - Keep heterogeneous hotspot scores as family-local `primary_score_name` / `primary_score_value` pairs plus `family_percentile` and `line_specific_json` instead of inventing one cross-family raw score.
  - Treat evidence-contract artifact semantics and on-disk family manifests/CSVs as the source of truth for percentage/classification reloads in this repo snapshot because the planner’s referenced module paths are stale.
duration: 
verification_result: mixed
completed_at: 2026-04-08T16:51:14.531Z
blocker_discovered: false
---

# T02: Added a contract-backed unified hotspot ledger, semantic Phase 4 ledger reloads, and a fail-closed ledger CLI for percentage/classification/trend hotspot families.

**Added a contract-backed unified hotspot ledger, semantic Phase 4 ledger reloads, and a fail-closed ledger CLI for percentage/classification/trend hotspot families.**

## What Happened

Implemented `src/WA/comparison/hotspot_ledger.py` to semantically reload percentage, classification, and trend hotspot families through evidence-contract artifact semantics, validate their JSON/CSV pairs, and normalize them into stable long-form `analysis_object_id` rows with provenance plus family-local score semantics (`primary_score_name`, `primary_score_value`, `family_percentile`, `line_specific_json`). Added `scripts/run_phase4_hotspot_ledger.py` with explicit `stage=ledger` skip/rebuild logging and fail-closed writes, extended `src/WA/visualization/phase4.py` with `load_phase4_unified_hotspot_ledger(...)`, added focused regression coverage, updated related-test routing and changelog text, recorded the stale-planner-path rule in `.gsd/KNOWLEDGE.md`, recorded the ledger-semantics decision in `.gsd/DECISIONS.md`, and wrote a quick-reference stash. The planner snapshot referenced absent percentage/classification modules, so the implementation adapted locally by treating the evidence-contract artifact families as the real source of truth.

## Verification

Passed the task-plan verification commands exactly as written via the bare-command auto-mode surface: `ruff check src/WA/comparison/hotspot_ledger.py src/WA/visualization/phase4.py scripts/run_phase4_hotspot_ledger.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md`; `python scripts/run_phase4_hotspot_ledger.py --help`; `python -m pytest tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q`; `python scripts/run_related_tests.py src/WA/comparison/hotspot_ledger.py scripts/run_phase4_hotspot_ledger.py src/WA/visualization/phase4.py src/WA/test_selection.py`. Additional repo-wide verification showed the pre-existing unrelated failure in `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` under `python -m pytest tests/ -x`, and a non-`-x` full-suite run still exited 137 later in the suite.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/comparison/hotspot_ledger.py src/WA/visualization/phase4.py scripts/run_phase4_hotspot_ledger.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md` | 0 | ✅ pass | 54ms |
| 2 | `python scripts/run_phase4_hotspot_ledger.py --help` | 0 | ✅ pass | 1098ms |
| 3 | `python -m pytest tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q` | 0 | ✅ pass | 5418ms |
| 4 | `python scripts/run_related_tests.py src/WA/comparison/hotspot_ledger.py scripts/run_phase4_hotspot_ledger.py src/WA/visualization/phase4.py src/WA/test_selection.py` | 0 | ✅ pass | 259ms |
| 5 | `python -m pytest tests/ -x` | 1 | ❌ fail | 5870ms |
| 6 | `python -m pytest tests/` | 137 | ❌ fail | 89300ms |

## Deviations

The written plan named `src/WA/comparison/percentage_hotspots.py` and `src/WA/comparison/classification_contract.py`, but those modules are absent in this repo snapshot, so the ledger was built around evidence-contract artifact semantics and on-disk family manifests/CSVs instead. I also added local `/root/.local/bin/python` and `/root/.local/bin/ruff` wrappers so the task-plan’s bare verification commands succeed in auto mode.

## Known Issues

`python -m pytest tests/ -x` still fails outside this task at `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` because of an exact float-equality assertion, and `python -m pytest tests/` still exits 137 later in the broader suite.

## Files Created/Modified

- `src/WA/comparison/hotspot_ledger.py`
- `scripts/run_phase4_hotspot_ledger.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_hotspot_ledger.py`
- `tests/test_visualization/test_phase4.py`
- `src/WA/test_selection.py`
- `CHANGELOG.md`
- `docs/stashes/2026-04-09-001-m002-s04-t02-unified-hotspot-ledger.md`
