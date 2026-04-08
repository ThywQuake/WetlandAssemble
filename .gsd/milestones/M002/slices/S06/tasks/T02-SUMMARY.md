---
id: T02
parent: S06
milestone: M002
key_files:
  - src/WA/visualization/phase4_pack.py
  - scripts/run_phase4_evidence_pack.py
  - tests/test_visualization/test_phase4_pack.py
  - src/WA/test_selection.py
  - docs/testing/test-categories.md
  - CHANGELOG.md
  - docs/stashes/2026-04-09-014-m002-s06-t02-paper-pack.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Keep the derived pack split into one wide joined regional evidence CSV and one long-form unified hotspot CSV, and duplicate exact source provenance into both the joined table and the deterministic manifest.
  - Clear any stale pack manifest before rebuild so a partial rerun cannot leave behind a misleading complete-pack claim.
duration: 
verification_result: mixed
completed_at: 2026-04-08T21:32:22.010Z
blocker_discovered: false
---

# T02: Added a contract-reload Phase 4 paper-pack builder and CLI with deterministic manifesting.

**Added a contract-reload Phase 4 paper-pack builder and CLI with deterministic manifesting.**

## What Happened

Added `src/WA/visualization/phase4_pack.py` as the derived Phase 4 paper-pack builder that reopens contract-backed percentage summaries/surfaces, classification summaries, trend-agreement summaries/surfaces, and unified hotspot ledgers through the public semantic reload helpers, validates the pack root stays outside `results/phase4`, clears stale manifests before rebuild, writes region-scoped percentage interannual + climatology figures, assembles one wide joined regional evidence table plus one long-form unified hotspot table, emits a narrative `summary.md`, and only writes the deterministic `manifest.json` after a full successful pack. Added `scripts/run_phase4_evidence_pack.py` as the thin CLI with `--region`, `--subset {canonical,ten}`, explicit phase4 vs pack output roots, explicit keys, and explicit trend participant ids. Added fixture-backed coverage in `tests/test_visualization/test_phase4_pack.py` for one-region smoke packs, ordered ten-region packs, deterministic relpaths, invalid pack roots, missing climatology rows, malformed ledger JSON, CLI help, and fail-closed CLI behavior. Updated `src/WA/test_selection.py`, `docs/testing/test-categories.md`, and `CHANGELOG.md`, and recorded the downstream pack-shape decision plus the unified-ledger parsed-column export gotcha in GSD artifacts.

## Verification

Task-level verification passed: `ruff check src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py tests/test_visualization/test_phase4_pack.py src/WA/test_selection.py docs/testing/test-categories.md CHANGELOG.md`, `python scripts/run_phase4_evidence_pack.py --help`, `python -m pytest tests/test_visualization/test_phase4_pack.py tests/test_visualization/test_phase4.py -q`, and `python scripts/run_related_tests.py src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py src/WA/test_selection.py` all succeeded. Repo-wide context remains mixed because `python -m pytest tests/` again surfaced the unrelated baseline failure `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` and later exited `137`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py tests/test_visualization/test_phase4_pack.py src/WA/test_selection.py docs/testing/test-categories.md CHANGELOG.md` | 0 | ✅ pass | 91ms |
| 2 | `python scripts/run_phase4_evidence_pack.py --help` | 0 | ✅ pass | 2005ms |
| 3 | `python -m pytest tests/test_visualization/test_phase4_pack.py tests/test_visualization/test_phase4.py -q` | 0 | ✅ pass | 11454ms |
| 4 | `python scripts/run_related_tests.py src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py src/WA/test_selection.py` | 0 | ✅ pass | 229ms |
| 5 | `python -m pytest tests/` | 137 | ❌ fail | 82800ms |

## Deviations

None.

## Known Issues

`python -m pytest tests/` still fails for the repo baseline on `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` and later exited `137`; this is unrelated to the paper-pack implementation and remains unresolved by this task.

## Files Created/Modified

- `src/WA/visualization/phase4_pack.py`
- `scripts/run_phase4_evidence_pack.py`
- `tests/test_visualization/test_phase4_pack.py`
- `src/WA/test_selection.py`
- `docs/testing/test-categories.md`
- `CHANGELOG.md`
- `docs/stashes/2026-04-09-014-m002-s06-t02-paper-pack.md`
- `.gsd/KNOWLEDGE.md`
