---
id: T03
parent: S06
milestone: M002
key_files:
  - src/WA/visualization/phase4_pack.py
  - scripts/run_phase4_evidence_pack.py
  - tests/test_visualization/test_phase4_pack.py
  - CHANGELOG.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-09-015-m002-s06-t03-strict-proof.md
key_decisions:
  - Always write deterministic proof JSON/Markdown artifacts under the pack root; only `--strict` upgrades an incomplete proof into a non-zero exit, while non-strict runs still emit explicit incomplete-proof artifacts and never leave behind a fresh manifest claim.
duration: 
verification_result: mixed
completed_at: 2026-04-08T22:04:00.432Z
blocker_discovered: false
---

# T03: Gated Phase 4 complete-pack claims behind readiness/ledger proof with deterministic proof artifacts and strict CLI exit semantics.

**Gated Phase 4 complete-pack claims behind readiness/ledger proof with deterministic proof artifacts and strict CLI exit semantics.**

## What Happened

Extended `src/WA/visualization/phase4_pack.py` with a proof wrapper that clears stale manifest/proof state, writes a fresh scale-out readiness report, validates readiness row coverage for the requested selector, reopens every requested unified ledger, checks trend participant-set alignment inside reopened ledger rows, and persists deterministic `complete_pack_proof.json` plus `complete_pack_proof.md` artifacts under the pack root before allowing a new manifest claim. Updated `scripts/run_phase4_evidence_pack.py` so `--strict` is the explicit complete-pack gate: incomplete proof now returns exit code `2` in strict mode, while non-strict runs still emit explicit incomplete-proof artifacts and never leave behind a fresh manifest claim. Expanded `tests/test_visualization/test_phase4_pack.py` with coverage for complete proof success, incomplete proof on missing readiness/ledger inputs, trend participant-set mismatch rejection, and CLI strict/non-strict proof behavior; also documented the operator-facing HPC rerun ladder in the stash/task summary and recorded the downstream proof/CLI choice in GSD decision D050 plus the readiness-gotcha in `.gsd/KNOWLEDGE.md`.

## Verification

Passed the task verification bundle: `ruff check src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py tests/test_visualization/test_phase4_pack.py`, `python scripts/run_phase4_evidence_pack.py --help`, `python -m pytest tests/test_visualization/test_phase4_pack.py tests/test_comparison/test_hotspot_ledger.py tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_classification_contract.py tests/test_comparison/test_trend_hotspots.py -q`, and `python scripts/run_related_tests.py src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py`. Broader repo context remains mixed because `python -m pytest tests/` still surfaced the unrelated baseline failure `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` and later exited `137`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py tests/test_visualization/test_phase4_pack.py` | 0 | ✅ pass | 40ms |
| 2 | `python scripts/run_phase4_evidence_pack.py --help` | 0 | ✅ pass | 1300ms |
| 3 | `python -m pytest tests/test_visualization/test_phase4_pack.py tests/test_comparison/test_hotspot_ledger.py tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_classification_contract.py tests/test_comparison/test_trend_hotspots.py -q` | 0 | ✅ pass | 17450ms |
| 4 | `python scripts/run_related_tests.py src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py` | 0 | ✅ pass | 250ms |
| 5 | `python -m pytest tests/` | 137 | ❌ fail | 39420ms |

## Deviations

Added `CHANGELOG.md`, `.gsd/KNOWLEDGE.md`, `.gsd/DECISIONS.md`, and the stash quick-reference update in addition to the three planned implementation files so the user-facing CLI change, downstream proof semantics, and HPC handoff all stay documented under the project contract.

## Known Issues

`python -m pytest tests/` still hits the unrelated repo baseline failure `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` and later exited `137`; this task does not change that surface.

## Files Created/Modified

- `src/WA/visualization/phase4_pack.py`
- `scripts/run_phase4_evidence_pack.py`
- `tests/test_visualization/test_phase4_pack.py`
- `CHANGELOG.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-09-015-m002-s06-t03-strict-proof.md`
