---
id: T04
parent: S05
milestone: M002
key_files:
  - src/WA/comparison/trend_contract.py
  - src/WA/comparison/trends.py
  - scripts/run_phase4_trend_contract.py
  - scripts/submit_phase4_trend_contract.sh
  - tests/test_comparison/test_trend_contract.py
  - tests/test_comparison/test_trends.py
  - tests/test_submit_phase4_trend_contract.py
  - CHANGELOG.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-09-008-m002-s05-t04-trend-checkpoints.md
key_decisions:
  - D046 — keep contract trend_surface/trend_regional_summary artifacts keyed by dataset_id + region_id, and keep resumable trend checkpoints as separate region/dataset/aggregation/requested-window cache files consumed before agreement.
duration: 
verification_result: mixed
completed_at: 2026-04-08T19:43:44.729Z
blocker_discovered: false
---

# T04: Restored dataset-scoped Phase 4 trend outputs and resumable trend-contract fanout via explicit checkpoints.

**Restored dataset-scoped Phase 4 trend outputs and resumable trend-contract fanout via explicit checkpoints.**

## What Happened

Added src/WA/comparison/trend_contract.py as the missing dataset-scoped contract layer for Phase 4 trends, writing one semantic trend_surface NetCDF and one trend_regional_summary CSV per dataset_id + region_id and reloading them fail-closed. Extended src/WA/comparison/trends.py with explicit trend checkpoint paths plus write/reload helpers under results/phase4/trend_checkpoints/, so the runner now persists one resumable checkpoint per region + dataset + aggregation + requested window before agreement. The checkpoint metadata now stores both the requested rerun window and the actual result time range, which avoids false stale/mixed reload failures on month-start series. Updated scripts/run_phase4_trend_contract.py to reuse or rebuild dataset checkpoints first, then write/reload dataset-scoped contract artifacts, and only then compute participant-set agreement plus trend-hotspot families. Added scripts/submit_phase4_trend_contract.sh as the HPC fanout wrapper that requires explicit --repo, hardcodes --no-skip into every generated job script, writes every participant dataset id explicitly, and emits one summary TSV per fanout run. Added focused regressions for contract round-trips, checkpoint reload behavior, mixed checkpoint metadata rejection, duplicate participant-id rejection, and submit-wrapper dry-run/error handling. Recorded D046, updated CHANGELOG.md and .gsd/KNOWLEDGE.md, and wrote docs/stashes/2026-04-09-008-m002-s05-t04-trend-checkpoints.md with copy-pasteable HPC commands.

## Verification

Passed the task-plan verification commands exactly as written: ruff check on the touched trend files, bash -n scripts/submit_phase4_trend_contract.sh, python scripts/run_phase4_trend_contract.py --help, and python -m pytest tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_submit_phase4_trend_contract.py -q (34 passed). I also ran the project-required broader suite check python -m pytest tests/, which still reproduces the existing unrelated tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case failure and later exits 137, and reran python -m pytest tests/test_mgrs_tiling.py -q to confirm that red bar in isolation.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/comparison/trend_contract.py src/WA/comparison/trends.py scripts/run_phase4_trend_contract.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_submit_phase4_trend_contract.py` | 0 | ✅ pass | 117ms |
| 2 | `bash -n scripts/submit_phase4_trend_contract.sh` | 0 | ✅ pass | 3ms |
| 3 | `python scripts/run_phase4_trend_contract.py --help` | 0 | ✅ pass | 1589ms |
| 4 | `python -m pytest tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_submit_phase4_trend_contract.py -q` | 0 | ✅ pass | 4450ms |
| 5 | `python -m pytest tests/` | 137 | ❌ fail | 59100ms |
| 6 | `python -m pytest tests/test_mgrs_tiling.py -q` | 1 | ❌ fail | 400ms |

## Deviations

Beyond the task plan’s expected output files, I also updated CHANGELOG.md, .gsd/KNOWLEDGE.md, recorded D046, and wrote docs/stashes/2026-04-09-008-m002-s05-t04-trend-checkpoints.md because the project contract requires changelog maintenance, durable execution breadcrumbs, and explicit HPC commands after user-visible CLI/workflow changes. I also preserved the runner’s existing agreement/hotspot validation helpers instead of refactoring them into the new module, because the blocker was missing dataset-scoped outputs plus checkpoints—not broken participant-set artifact semantics.

## Known Issues

python -m pytest tests/ still reproduces the pre-existing unrelated failure at tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case, and the broader suite is later killed with exit 137 before completing. No real HPC SLURM execution against external standardized inputs was run from this worktree; only the submit-wrapper dry-run surface and focused local tests were exercised here.

## Files Created/Modified

- `src/WA/comparison/trend_contract.py`
- `src/WA/comparison/trends.py`
- `scripts/run_phase4_trend_contract.py`
- `scripts/submit_phase4_trend_contract.sh`
- `tests/test_comparison/test_trend_contract.py`
- `tests/test_comparison/test_trends.py`
- `tests/test_submit_phase4_trend_contract.py`
- `CHANGELOG.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-09-008-m002-s05-t04-trend-checkpoints.md`
