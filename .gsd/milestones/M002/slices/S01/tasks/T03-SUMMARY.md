---
id: T03
parent: S01
milestone: M002
key_files:
  - src/WA/comparison/phase4_regional.py
  - scripts/run_phase4_regional.py
  - tests/test_comparison/test_phase4_regional.py
  - CHANGELOG.md
  - docs/stashes/2026-04-08-016-m002-s01-t03-regional-contract-summary.md
  - .gsd/milestones/M002/slices/S01/tasks/T03-SUMMARY.md
key_decisions:
  - D032 — keep the live Stage-2 cache/per-region table flow and additionally emit contract-stable dataset×region summary CSVs under the evidence-contract regional_summaries layout.
duration: 
verification_result: passed
completed_at: 2026-04-07T18:57:04.305Z
blocker_discovered: false
---

# T03: Wired Phase 4 regional summaries to the evidence contract with canonical-subset CLI selection and contract-stable metadata-rich outputs.

**Wired Phase 4 regional summaries to the evidence contract with canonical-subset CLI selection and contract-stable metadata-rich outputs.**

## What Happened

Updated `src/WA/comparison/phase4_regional.py` so the live Phase 4 regional route now resolves priority regions through `src/WA/comparison/evidence_contract.py` instead of hand-reading the YAML payload. Added contract-stable dataset×region summary-path helpers, flattened grid/mask metadata columns, Berkeley-valid mask attrs on both cache hits and cold builds, summary-table validation, and contract CSV writes under `results/phase4/regional_summaries/<region>/` while preserving the existing Stage-1/Stage-2 cache files and combined per-region table. Refactored `scripts/run_phase4_regional.py` to bootstrap `src/`, support `--subset canonical`, preserve `--no-skip` / year filters / progress flags, and document the narrow-first operational ladder. Extended `tests/test_comparison/test_phase4_regional.py` to cover strict contract-backed region loading, canonical subset resolution, contract summary path layout, Berkeley-valid attrs, and the new metadata-rich GWD30 Stage-2 outputs. Recorded decision D032 to keep the live cache/table route and emit contract outputs alongside it instead of replacing the operational path.

## Verification

Passed the focused T03 regression suite, direct CLI `--help` proof, Ruff on the modified files, the Phase 4 related-test selector command, and the full repository pytest suite. Commands run: `python -m pytest tests/test_comparison/test_phase4_regional.py -q`, `python scripts/run_phase4_regional.py --help`, `ruff check src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py tests/test_comparison/test_phase4_regional.py`, `python scripts/run_related_tests.py src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py`, and `python -m pytest tests/`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m pytest tests/test_comparison/test_phase4_regional.py -q` | 0 | ✅ pass | 1770ms |
| 2 | `python scripts/run_phase4_regional.py --help` | 0 | ✅ pass | 2009ms |
| 3 | `ruff check src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py tests/test_comparison/test_phase4_regional.py` | 0 | ✅ pass | 43ms |
| 4 | `python scripts/run_related_tests.py src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py` | 0 | ✅ pass | 463ms |
| 5 | `python -m pytest tests/` | 0 | ✅ pass | 37603ms |

## Deviations

Also repaired direct `python scripts/run_phase4_regional.py ...` execution by adding the standard `src/` bootstrap while refactoring the CLI, because earlier slice verification had already shown direct invocation failed with `ModuleNotFoundError: No module named 'WA'`.

## Known Issues

Full pytest still emits pre-existing warnings (`numpy` binary-compatibility runtime warning, `cftime_range` deprecation warnings in visualization tests, and a pandas `FutureWarning` on empty/all-NA concat in the GWD30 year-cache merge path). They do not block T03 verification.

## Files Created/Modified

- `src/WA/comparison/phase4_regional.py`
- `scripts/run_phase4_regional.py`
- `tests/test_comparison/test_phase4_regional.py`
- `CHANGELOG.md`
- `docs/stashes/2026-04-08-016-m002-s01-t03-regional-contract-summary.md`
- `.gsd/milestones/M002/slices/S01/tasks/T03-SUMMARY.md`
