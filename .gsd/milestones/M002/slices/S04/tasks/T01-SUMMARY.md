---
id: T01
parent: S04
milestone: M002
key_files:
  - src/WA/comparison/evidence_contract.py
  - src/WA/comparison/trend_hotspots.py
  - scripts/run_phase4_trend_contract.py
  - src/WA/visualization/phase4.py
  - tests/test_comparison/test_evidence_contract.py
  - tests/test_comparison/test_trend_hotspots.py
  - tests/test_visualization/test_phase4.py
  - src/WA/test_selection.py
  - CHANGELOG.md
  - docs/stashes/2026-04-08-001-m002-s04-t01-trend-hotspot-contract.md
key_decisions:
  - Use sorted participant ids joined by `+` as the stable `participant_set_key` for trend agreement and hotspot artifact stems.
  - Require hotspot manifest reloads to validate participant metadata and table SHA-256 so partial or mixed JSON/CSV pairs fail closed instead of being reused.
duration: 
verification_result: mixed
completed_at: 2026-04-08T16:24:13.935Z
blocker_discovered: false
---

# T01: Added contract-backed trend hotspot manifests, a real trend contract runner, and semantic reloads for Phase 4 trend outputs

**Added contract-backed trend hotspot manifests, a real trend contract runner, and semantic reloads for Phase 4 trend outputs**

## What Happened

Repaired the Phase 4 evidence contract module, added `src/WA/comparison/trend_hotspots.py` for sorted participant-set keys plus disagreement-first hotspot ranking and fail-closed JSON/CSV reload validation, created `scripts/run_phase4_trend_contract.py` to write/reload agreement artifacts and then run a dedicated `trend-hotspots` stage, extended `src/WA/visualization/phase4.py` with `load_phase4_contract_trend_hotspot_table(...)`, added focused regression tests, updated related-test mapping, and documented the user-facing change in `CHANGELOG.md`. The implemented must-haves are now explicit in code: hotspot artifacts are keyed by sorted participant ids, ranking uses `1 - agreement_ratio` with `slope_std` only as a tie-breaker, and the runner exposes `stage=agreement` / `stage=trend-hotspots` logging while rejecting incomplete or malformed pairs before reuse.

## Verification

Passed: `uvx ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md`; `uv run python scripts/run_phase4_trend_contract.py --help`; `uv run --with pytest python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py -q`; `uv run python scripts/run_related_tests.py src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py`. Additional observability smoke confirmed `stage=agreement` / `stage=trend-hotspots` logs and the `Phase4 semantic reload failed ...` wrapper error. Repository-wide pytest did not fully pass because `uv run --with pytest python -m pytest tests/ -x` fails at the unrelated existing float-equality assertion in `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case`, and a non-`-x` full-suite run later exited 137 after continuing through the broader suite.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uvx ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md` | 0 | ✅ pass | 744ms |
| 2 | `uv run python scripts/run_phase4_trend_contract.py --help` | 0 | ✅ pass | 1080ms |
| 3 | `uv run --with pytest python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py -q` | 0 | ✅ pass | 3217ms |
| 4 | `uv run python scripts/run_related_tests.py src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py` | 0 | ✅ pass | 256ms |
| 5 | `uv run --with pytest python -m pytest tests/ -x` | 1 | ❌ fail | 4525ms |
| 6 | `uv run --with pytest python -m pytest tests/` | 137 | ❌ fail | 62500ms |

## Deviations

The planner snapshot assumed `scripts/run_phase4_trend_contract.py`, `tests/test_comparison/test_evidence_contract.py`, and `tests/test_comparison/test_trend_hotspots.py` already existed, but this repo snapshot did not contain them, so they were created from scratch. Agreement artifact write/reload helpers were kept inside the new runner instead of adding a separate `src/WA/comparison/trend_contract.py` module because that module was also absent and this task only required a real runner plus the hotspot contract family.

## Known Issues

`uv run --with pytest python -m pytest tests/ -x` currently fails outside this task’s surface at `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` due to an exact floating-point equality assertion, and a non-`-x` full-suite run later exited 137 after continuing through the suite. This auto-mode shell also lacks a bare `python` executable, so verification used `uv run python` / `uv run --with pytest python`.

## Files Created/Modified

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/trend_hotspots.py`
- `scripts/run_phase4_trend_contract.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_evidence_contract.py`
- `tests/test_comparison/test_trend_hotspots.py`
- `tests/test_visualization/test_phase4.py`
- `src/WA/test_selection.py`
- `CHANGELOG.md`
- `docs/stashes/2026-04-08-001-m002-s04-t01-trend-hotspot-contract.md`
