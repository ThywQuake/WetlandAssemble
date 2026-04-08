---
id: T01
parent: S03
milestone: M002
key_files:
  - src/WA/comparison/evidence_contract.py
  - tests/test_comparison/test_evidence_contract.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-08-022-m002-s03-t01-classification-artifact-families.md
key_decisions:
  - D036 — reserve '__' for the outer evidence-contract stem separator and reject it inside dataset/participant tokens.
duration: 
verification_result: mixed
completed_at: 2026-04-08T13:38:38.799Z
blocker_discovered: false
---

# T01: Added classification artifact families and dataset-slot stem validation to the shared evidence contract.

**Added classification artifact families and dataset-slot stem validation to the shared evidence contract.**

## What Happened

Extended the shared evidence contract with dedicated classification artifact families before any adapter or runner code is added. `ArtifactKind`, required artifact-semantic validation, and `default_artifact_semantics()` now include `classification_surface`, `classification_regional_summary`, and `classification_hotspot_manifest`, all using stable relpaths rooted in the shared `<dataset_or_key>__<region>__<suffix>` grammar. Added stem-token validation so dataset/participant keys are trimmed and rejected if they contain `__` or path separators, keeping the participant-set key in the dataset slot without making stems ambiguous. Expanded `tests/test_comparison/test_evidence_contract.py` to lock deterministic classification relpaths, JSON-safe metadata for `g2017+glwd_v2+gwd30`, unknown artifact-kind failures, reserved-separator failures, and missing-classification-semantics failures. Recorded the reusable naming rule as decision D036 and added a stash/knowledge note for recovery and future execution.

## Verification

Passed the task-local gates with `ruff check src/WA/comparison/evidence_contract.py tests/test_comparison/test_evidence_contract.py` and `python -m pytest tests/test_comparison/test_evidence_contract.py -q` (`12 passed`). Also passed the repo-wide verification requirement with `python -m pytest tests/` (`461 passed`). Ran the slice-level verification commands as well: `run_related_tests.py` succeeded, while the later-slice classification runner/adapter commands failed as expected because their files are scheduled for T02/T03 and do not exist yet; the broad slice Ruff command also exposed a pre-existing markdown/Ruff parsing issue on `docs/testing/test-categories.md`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/comparison/evidence_contract.py tests/test_comparison/test_evidence_contract.py` | 0 | ✅ pass | 35ms |
| 2 | `python -m pytest tests/test_comparison/test_evidence_contract.py -q` | 0 | ✅ pass | 1989ms |
| 3 | `ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/classification_contract.py scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py docs/testing/test-categories.md CHANGELOG.md` | 1 | ❌ fail | 49ms |
| 4 | `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py -q` | 4 | ❌ fail | 185ms |
| 5 | `python scripts/run_phase4_classification_contract.py --help` | 2 | ❌ fail | 45ms |
| 6 | `python scripts/run_related_tests.py src/WA/comparison/classification_contract.py scripts/run_phase4_classification_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py` | 0 | ✅ pass | 286ms |
| 7 | `python -m pytest tests/` | 0 | ✅ pass | 24289ms |

## Deviations

Ran `python -m pytest tests/` in addition to the task-plan checks because the repo’s standing execution rules require a full-suite run after code changes. Also executed the slice-level verification commands early so the summary could record the expected T01 partial-slice boundary.

## Known Issues

Later-slice verification commands still fail until T02/T03 add `src/WA/comparison/classification_contract.py`, `scripts/run_phase4_classification_contract.py`, and `tests/test_comparison/test_classification_contract.py`. The broad slice Ruff command also still hits a pre-existing markdown parsing failure on `docs/testing/test-categories.md`.

## Files Created/Modified

- `src/WA/comparison/evidence_contract.py`
- `tests/test_comparison/test_evidence_contract.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-08-022-m002-s03-t01-classification-artifact-families.md`
