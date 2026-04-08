---
id: T01
parent: S06
milestone: M002
key_files:
  - src/WA/comparison/trend_contract.py
  - scripts/run_phase4_trend_contract.py
  - src/WA/visualization/phase4.py
  - tests/test_comparison/test_trend_contract.py
  - tests/test_visualization/test_phase4.py
  - docs/stashes/2026-04-09-013-m002-s06-t01-reload-helpers.md
key_decisions:
  - Keep trend-agreement pair validation in the comparison contract layer and keep phase4 wrappers thin so later pack code never imports script-private helpers or guesses contract paths.
duration: 
verification_result: mixed
completed_at: 2026-04-08T21:06:22.625Z
blocker_discovered: false
---

# T01: Promoted public trend-agreement semantic reload helpers and added phase4 percentage/trend wrapper reload APIs for pack-safe reuse.

**Promoted public trend-agreement semantic reload helpers and added phase4 percentage/trend wrapper reload APIs for pack-safe reuse.**

## What Happened

Moved the trend-agreement semantic reopen path out of scripts/run_phase4_trend_contract.py and into src/WA/comparison/trend_contract.py as public contract helpers. The comparison layer now owns trend-agreement output-path helpers plus strict surface/summary reload validation with region_id and participant_set_key context. Updated the trend runner to reuse those public helpers instead of duplicating artifact path logic or relying on a script-private reload function. Extended src/WA/visualization/phase4.py with pack-facing wrappers for percentage summary/surface and trend-agreement summary/surface so later pack tasks can reopen artifacts entirely through public comparison/visualization APIs. Added focused regression tests covering successful semantic reopen, partial agreement pairs, malformed metadata, mixed participant ids, and wrapper-level failure envelopes.

## Verification

Task-level verification passed: targeted ruff check, python scripts/run_phase4_trend_contract.py --help, and python -m pytest tests/test_comparison/test_trend_contract.py tests/test_visualization/test_phase4.py -q (22 passed). Slice-level/project context was also checked: python scripts/run_related_tests.py ... succeeded as a selector; slice-level pack verification commands failed as expected because T02/T03 pack files do not exist yet; python -m pytest tests/ surfaced the known unrelated baseline failure in tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case before the run later exited 137.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/comparison/trend_contract.py scripts/run_phase4_trend_contract.py src/WA/comparison/percentage_backbone.py src/WA/visualization/phase4.py tests/test_comparison/test_trend_contract.py tests/test_visualization/test_phase4.py` | 0 | ✅ pass | 90ms |
| 2 | `python scripts/run_phase4_trend_contract.py --help` | 0 | ✅ pass | 1531ms |
| 3 | `python -m pytest tests/test_comparison/test_trend_contract.py tests/test_visualization/test_phase4.py -q` | 0 | ✅ pass | 10300ms |
| 4 | `ruff check src/WA/comparison/trend_contract.py src/WA/visualization/phase4.py src/WA/visualization/phase4_pack.py scripts/run_phase4_trend_contract.py scripts/run_phase4_evidence_pack.py src/WA/test_selection.py docs/testing/test-categories.md tests/test_comparison/test_trend_contract.py tests/test_visualization/test_phase4.py tests/test_visualization/test_phase4_pack.py CHANGELOG.md` | 1 | ❌ fail | 42ms |
| 5 | `python scripts/run_phase4_evidence_pack.py --help` | 2 | ❌ fail | 8ms |
| 6 | `python -m pytest tests/test_visualization/test_phase4.py tests/test_visualization/test_phase4_pack.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_hotspot_ledger.py tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_classification_contract.py tests/test_comparison/test_trend_hotspots.py -q` | 4 | ❌ fail | 12900ms |
| 7 | `python scripts/run_related_tests.py src/WA/comparison/trend_contract.py src/WA/visualization/phase4.py src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py src/WA/test_selection.py` | 0 | ✅ pass | 233ms |
| 8 | `python -m pytest tests/` | 137 | ❌ fail | 40600ms |

## Deviations

None.

## Known Issues

Slice-level pack checks still fail until T02/T03 create src/WA/visualization/phase4_pack.py, scripts/run_phase4_evidence_pack.py, and tests/test_visualization/test_phase4_pack.py. Repo baseline issue remains: tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case fails on exact float equality and is unrelated to this task; the full-suite pytest run later exited 137 after surfacing that failure.

## Files Created/Modified

- `src/WA/comparison/trend_contract.py`
- `scripts/run_phase4_trend_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_trend_contract.py`
- `tests/test_visualization/test_phase4.py`
- `docs/stashes/2026-04-09-013-m002-s06-t01-reload-helpers.md`
