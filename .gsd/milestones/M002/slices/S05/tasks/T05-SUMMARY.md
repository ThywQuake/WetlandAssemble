---
id: T05
parent: S05
milestone: M002
key_files:
  - src/WA/comparison/scaleout_readiness.py
  - scripts/run_phase4_scaleout_readiness.py
  - scripts/run_phase4_hotspot_ledger.py
  - src/WA/test_selection.py
  - tests/test_comparison/test_scaleout_readiness.py
  - tests/test_comparison/test_hotspot_ledger.py
  - tests/test_test_selection.py
  - CHANGELOG.md
  - docs/stashes/2026-04-09-009-m002-s05-t05-scaleout-readiness.md
key_decisions:
  - D047 — treat a hotspot family as missing only when both the manifest and CSV are absent; classify partial pairs or semantic/provenance reload failures as partial, and auto-write a single-region readiness report whenever the ledger CLI fails.
duration: 
verification_result: mixed
completed_at: 2026-04-08T20:11:07.284Z
blocker_discovered: false
---

# T05: Added ten-region readiness reporting and kept the ledger fail-closed with family-specific diagnostics.

**Added ten-region readiness reporting and kept the ledger fail-closed with family-specific diagnostics.**

## What Happened

Added src/WA/comparison/scaleout_readiness.py plus scripts/run_phase4_scaleout_readiness.py so Phase 4 operators can scan one region, the canonical subset, or the ordered ten-region subset and get deterministic CSV/JSON readiness rows for percentage, classification, and trend hotspot families. The readiness layer reuses the real semantic reload paths, distinguishes ready vs missing vs partial with explicit reasons and artifact paths, and writes stable report stems under results/phase4/scaleout_readiness/. Updated scripts/run_phase4_hotspot_ledger.py to keep the unified ledger fail-closed while pointing operators at the readiness CLI, auto-writing a single-region readiness diagnostic report on failure, and logging one family-context line per metric family before re-raising. Expanded src/WA/test_selection.py and tests/test_test_selection.py so the newer Phase 4 classification/trend contract files and the new readiness gate route back to the focused Phase 4 pytest bundle, added tests/test_comparison/test_scaleout_readiness.py, extended tests/test_comparison/test_hotspot_ledger.py, updated CHANGELOG.md, recorded D047, and wrote docs/stashes/2026-04-09-009-m002-s05-t05-scaleout-readiness.md with quick-reference notes plus HPC commands.

## Verification

Passed the task-plan verification commands exactly as written: ruff check on the touched readiness/ledger/routing files, python scripts/run_phase4_scaleout_readiness.py --help, python scripts/run_phase4_hotspot_ledger.py --help, python -m pytest tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q (23 passed), and python scripts/run_related_tests.py src/WA/comparison/scaleout_readiness.py scripts/run_phase4_scaleout_readiness.py scripts/run_phase4_hotspot_ledger.py src/WA/test_selection.py. I also ran python -m pytest tests/test_test_selection.py -q (5 passed) because src/WA/test_selection.py changed. Per the project contract, I ran python -m pytest tests/ as a broader suite check; it still reproduces the pre-existing unrelated tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case failure and the broad run is later killed with exit 137. I reran python -m pytest tests/test_mgrs_tiling.py -q to confirm that repo-wide red bar in isolation.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/comparison/scaleout_readiness.py scripts/run_phase4_scaleout_readiness.py scripts/run_phase4_hotspot_ledger.py src/WA/test_selection.py tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py CHANGELOG.md` | 0 | ✅ pass | 50ms |
| 2 | `python scripts/run_phase4_scaleout_readiness.py --help` | 0 | ✅ pass | 1295ms |
| 3 | `python scripts/run_phase4_hotspot_ledger.py --help` | 0 | ✅ pass | 1280ms |
| 4 | `python -m pytest tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q` | 0 | ✅ pass | 9010ms |
| 5 | `python scripts/run_related_tests.py src/WA/comparison/scaleout_readiness.py scripts/run_phase4_scaleout_readiness.py scripts/run_phase4_hotspot_ledger.py src/WA/test_selection.py` | 0 | ✅ pass | 247ms |
| 6 | `python -m pytest tests/test_test_selection.py -q` | 0 | ✅ pass | 372ms |
| 7 | `python -m pytest tests/` | 137 | ❌ fail | 43141ms |
| 8 | `python -m pytest tests/test_mgrs_tiling.py -q` | 1 | ❌ fail | 864ms |

## Deviations

Beyond the task plan’s expected output files, I also updated tests/test_test_selection.py, recorded decision D047, and wrote docs/stashes/2026-04-09-009-m002-s05-t05-scaleout-readiness.md because the project contract requires durable routing coverage, persistent architectural/observability breadcrumbs, and a quick-reference stash with concrete HPC commands after operator-facing workflow changes. I also chose deterministic readiness report stems under results/phase4/scaleout_readiness/ so ledger failures can point at stable CSV/JSON paths instead of ephemeral temp files.

## Known Issues

python -m pytest tests/ still reproduces the pre-existing unrelated failure at tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case and the broader run is later killed with exit 137 before the suite completes. No real HPC rerun against external standardized inputs was executed from this worktree.

## Files Created/Modified

- `src/WA/comparison/scaleout_readiness.py`
- `scripts/run_phase4_scaleout_readiness.py`
- `scripts/run_phase4_hotspot_ledger.py`
- `src/WA/test_selection.py`
- `tests/test_comparison/test_scaleout_readiness.py`
- `tests/test_comparison/test_hotspot_ledger.py`
- `tests/test_test_selection.py`
- `CHANGELOG.md`
- `docs/stashes/2026-04-09-009-m002-s05-t05-scaleout-readiness.md`
