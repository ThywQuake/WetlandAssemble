---
id: T01
parent: S02
milestone: M002
key_files:
  - src/WA/comparison/evidence_contract.py
  - src/WA/comparison/trend_contract.py
  - tests/test_comparison/test_evidence_contract.py
  - tests/test_comparison/test_trend_contract.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D032 — use '+'-joined sorted dataset ids for trend agreement participant_set_key values so agreement stems stay stable without colliding with the contract's '__' separator.
duration: 
verification_result: mixed
completed_at: 2026-04-08T12:37:33.815Z
blocker_discovered: false
---

# T01: Added stable trend contract artifact families and strict writer helpers for trend and agreement outputs.

**Added stable trend contract artifact families and strict writer helpers for trend and agreement outputs.**

## What Happened

Extended the shared evidence contract with four dedicated trend artifact families and added a new `src/WA/comparison/trend_contract.py` adapter layer that owns deterministic relpaths, sorted participant-set keys, strict pre-write validation, region-scoped summary normalization, and contract metadata attachment for trend and trend-agreement outputs. The adapter writes stable NetCDF/CSV artifacts while keeping `trends.py` and `trend_agreement.py` pure compute modules. I also locked the new families and writer behavior with focused tests covering relpath determinism, malformed metadata rejection, missing output-root failures, non-computed trend rejection, empty-overlap agreement rejection, and the legacy duplicated `global` row cleanup.

## Verification

Task-level verification passed with focused Ruff and pytest checks on the new contract files and tests. The wider trend/visualization pytest bundle also passes. Slice-level `python scripts/run_phase4_trend_contract.py --help` still fails because the T02 CLI does not exist yet, and the broader slice-level Ruff command still fails on the expected missing script plus a pre-existing `CHANGELOG.md` parsing issue unrelated to T01. A direct `PYTHONPATH=src python` spot check also confirmed that representative writer failures include dataset/region or participant-set key plus planned relpaths before any file write.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_contract.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py` | 0 | ✅ pass | 22ms |
| 2 | `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py -q` | 0 | ✅ pass | 2351ms |
| 3 | `ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_contract.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md` | 1 | ❌ fail | 93ms |
| 4 | `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_visualization/test_phase4.py -q` | 0 | ✅ pass | 2600ms |
| 5 | `python scripts/run_phase4_trend_contract.py --help` | 2 | ❌ fail | 24ms |
| 6 | `python scripts/run_related_tests.py src/WA/comparison/trend_contract.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py` | 0 | ✅ pass | 247ms |

## Deviations

Required `output_root` to pre-exist before writes, then created only the contract family/region subdirectories beneath it so missing-root failures stay explicit before any artifact write. This is a minor local adaptation to satisfy the task's failure-mode bar.

## Known Issues

`scripts/run_phase4_trend_contract.py` is still absent, so the slice-level `--help` proof remains red until T02. The broad slice-level Ruff command also still fails on a pre-existing `CHANGELOG.md` parsing issue unrelated to the new trend-contract files. No standalone HPC proof command exists for T01 alone; the first real HPC-facing proof starts once T02 adds the CLI.

## Files Created/Modified

- `src/WA/comparison/evidence_contract.py`
- `src/WA/comparison/trend_contract.py`
- `tests/test_comparison/test_evidence_contract.py`
- `tests/test_comparison/test_trend_contract.py`
- `.gsd/KNOWLEDGE.md`
