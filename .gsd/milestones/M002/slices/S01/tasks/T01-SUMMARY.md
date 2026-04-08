---
id: T01
parent: S01
milestone: M002
key_files:
  - src/WA/comparison/evidence_contract.py
  - tests/test_comparison/test_evidence_contract.py
  - docs/stashes/2026-04-08-014-m002-s01-t01-evidence-contract.md
  - .gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md
key_decisions:
  - D031 — use one strict evidence-contract module backed by `config/priority_regions.yaml` with no legacy fallback defaults.
duration: 
verification_result: mixed
completed_at: 2026-04-07T18:31:56.088Z
blocker_discovered: false
---

# T01: Added a strict config-backed evidence contract for the canonical subset, artifact semantics, and JSON-safe metadata export.

**Added a strict config-backed evidence contract for the canonical subset, artifact semantics, and JSON-safe metadata export.**

## What Happened

Added `src/WA/comparison/evidence_contract.py` as the first shared M002/S01 contract surface. The module now loads the ten priority regions directly from `config/priority_regions.yaml`, validates required and unknown fields strictly, rejects duplicate YAML keys, resolves the canonical subset (`amazon`, `pantanal`, `sudd`, `borneo`) deterministically, and centralizes reusable artifact naming/layout plus JSON-safe metadata export helpers for surfaces, regional summaries, and hotspot manifests. Added `tests/test_comparison/test_evidence_contract.py` to lock real catalog order, canonical subset order, bad-catalog rejection, duplicate subset rejection, unknown-region rejection, and metadata serialization. Recorded the architectural choice as D031 and wrote a compact stash note for re-entry.

## Verification

Task-local verification passed: Ruff passed on the new module/tests, `python -m pytest tests/test_comparison/test_evidence_contract.py -q` passed, and the full repository suite `python -m pytest tests/` passed from the M002 worktree. Slice-level probes were also executed: the related-tests command returned successfully, while the broader slice pytest/HPC commands failed for expected T01-boundary reasons (later T02-T04 files not created yet, missing `/lustre/...` staged inputs, direct script import-path issue, and the not-yet-created T04 orchestration CLI).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/comparison/evidence_contract.py tests/test_comparison/test_evidence_contract.py` | 0 | ✅ pass | 27ms |
| 2 | `python -m pytest tests/test_comparison/test_evidence_contract.py -q` | 0 | ✅ pass | 1440ms |
| 3 | `python -m pytest tests/` | 0 | ✅ pass | 22750ms |
| 4 | `python scripts/run_related_tests.py src/WA/comparison/evidence_contract.py` | 0 | ✅ pass | 257ms |
| 5 | `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_phase4_regional.py tests/test_comparison/test_percentage_hotspots.py tests/test_visualization/test_phase4.py tests/test_plot_tropical_wetland_025deg.py -q` | 4 | ❌ fail | 157ms |
| 6 | `python scripts/run_related_tests.py src/WA/comparison/evidence_contract.py src/WA/comparison/percentage_backbone.py src/WA/comparison/phase4_regional.py src/WA/comparison/percentage_hotspots.py scripts/plot_tropical_wetland_025deg.py scripts/run_phase4_regional.py scripts/run_phase4_percentage_contract.py src/WA/visualization/phase4.py` | 0 | ✅ pass | 167ms |
| 7 | `python scripts/build_phase4_gwd30_pixel_stats.py --year 2016 --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --aggregation monthly --worker-count 1 --no-skip` | 1 | ❌ fail | 1142ms |
| 8 | `python scripts/run_phase4_regional.py --dataset-id gwd30 --region amazon --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --start-year 2016 --end-year 2016 --no-skip` | 1 | ❌ fail | 340ms |
| 9 | `python scripts/run_phase4_percentage_contract.py --subset canonical --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --start-year 2016 --end-year 2016 --no-skip` | 2 | ❌ fail | 21ms |

## Deviations

None.

## Known Issues

The slice verification bundle still cannot pass until T02-T04 create the remaining contract-aware files; direct `python scripts/run_phase4_regional.py ...` invocation in this environment still raises `ModuleNotFoundError: No module named 'WA'`; and the local machine does not have the `/lustre/...` staged GWD30 inputs needed for the HPC proof commands.

## Files Created/Modified

- `src/WA/comparison/evidence_contract.py`
- `tests/test_comparison/test_evidence_contract.py`
- `docs/stashes/2026-04-08-014-m002-s01-t01-evidence-contract.md`
- `.gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md`
