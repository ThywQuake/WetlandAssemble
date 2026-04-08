---
id: T04
parent: S01
milestone: M002
key_files:
  - src/WA/comparison/percentage_hotspots.py
  - scripts/run_phase4_percentage_contract.py
  - src/WA/visualization/phase4.py
  - tests/test_comparison/test_percentage_hotspots.py
  - tests/test_visualization/test_phase4.py
  - src/WA/test_selection.py
  - CHANGELOG.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-08-017-m002-s01-t04-percentage-hotspots.md
key_decisions:
  - D029 — use a thin Phase 4 percentage contract runner that composes the existing regional producer and 0.25° surface builder instead of creating a second standalone pipeline.
duration: 
verification_result: passed
completed_at: 2026-04-07T19:37:14.586Z
blocker_discovered: false
---

# T04: Added contract-stable percentage hotspot manifests and a canonical Phase 4 orchestration CLI.

**Added contract-stable percentage hotspot manifests and a canonical Phase 4 orchestration CLI.**

## What Happened

Added `src/WA/comparison/percentage_hotspots.py` to validate contract-tagged regional summaries, load 0.25° percentage surfaces, allocate per-region hotspot quotas, select/deduplicate local-max hotspot cells, and emit contract-stable hotspot JSON + CSV artifacts under `results/phase4/hotspots/`. Added `scripts/run_phase4_percentage_contract.py` as a thin stage-aware proof runner that composes the live Phase 4 regional producer, lazily reuses `plot_tropical_wetland_025deg.py` for surfaces, then writes hotspot manifests plus interannual/climatology/hotspot figures. Updated `src/WA/visualization/phase4.py` so figures can be rebuilt from contract summary CSVs and contract hotspot CSV companions rather than old ad hoc table naming. Extended tests with `tests/test_comparison/test_percentage_hotspots.py` and an expanded `tests/test_visualization/test_phase4.py`, updated `src/WA/test_selection.py`, recorded D029, appended a lazy-import gotcha to `.gsd/KNOWLEDGE.md`, and wrote the task stash summary at `docs/stashes/2026-04-08-017-m002-s01-t04-percentage-hotspots.md`.

## Verification

Passed Ruff on the modified Phase 4 hotspot/orchestration/visualization surfaces, confirmed `python scripts/run_phase4_percentage_contract.py --help` boots successfully, verified the related-test selector maps the new files into the Phase 4 family, passed the focused hotspot/visualization pytest suite, and passed the full repository pytest suite. The full run still emits the pre-existing numpy/pandas/xarray warnings already seen elsewhere in the worktree, but no new failures were introduced.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/comparison/percentage_hotspots.py src/WA/visualization/phase4.py scripts/run_phase4_percentage_contract.py tests/test_comparison/test_percentage_hotspots.py tests/test_visualization/test_phase4.py src/WA/test_selection.py` | 0 | ✅ pass | 12ms |
| 2 | `python scripts/run_phase4_percentage_contract.py --help` | 0 | ✅ pass | 1353ms |
| 3 | `python scripts/run_related_tests.py src/WA/comparison/percentage_hotspots.py src/WA/visualization/phase4.py scripts/run_phase4_percentage_contract.py` | 0 | ✅ pass | 149ms |
| 4 | `python -m pytest tests/test_comparison/test_percentage_hotspots.py tests/test_visualization/test_phase4.py -q` | 0 | ✅ pass | 1671ms |
| 5 | `python -m pytest tests/` | 0 | ✅ pass | 21497ms |

## Deviations

The new orchestration CLI defaults to the current overlap between the live Phase 4 regional producer and the existing 0.25° surface builder (`berkeley_rwawc`, `giems_mc`, `topmodel`, `swamps`, `wad2m`) instead of forcing `gwd30` through a new surface path. This preserves the existing producers and avoids inventing the still-missing dedicated percentage-backbone module inside this task.

## Known Issues

A real canonical-subset execution against HPC-standardized inputs was not run locally in this worktree; local verification covered schema, CLI bootstrap, focused regressions, and the full repository pytest suite. The summary documents the exact three-step HPC command ladder to run after rsync sync.

## Files Created/Modified

- `src/WA/comparison/percentage_hotspots.py`
- `scripts/run_phase4_percentage_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_percentage_hotspots.py`
- `tests/test_visualization/test_phase4.py`
- `src/WA/test_selection.py`
- `CHANGELOG.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-08-017-m002-s01-t04-percentage-hotspots.md`
