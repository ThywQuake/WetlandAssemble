---
estimated_steps: 11
estimated_files: 8
skills_used: []
---

# T02: Finish late-phase rows and lock the Phase 4 route split

## Description

Complete the most drift-prone rows after the contract is stable so S03 inherits a clear separation between current continuation signals and historical/stale routes.

## Steps

1. Extend the `Phase Matrix` with `Phase 3.6`, `Phase 3.6.1`, `Phase 3.7`, `Phase 4 current Stage-1 / Stage-2 route`, and `Phase 4 historical full-tropics reducer route` using the late Phase 3 stash notes, the 2026-04-05 / 2026-04-06 changelog entries, and the Phase 4 recall/handoff notes.
2. Cite the exact evidence that explains why `Phase 3.6` and `Phase 3.7` remain below fully validated state locally, and why the older Phase 4 full-tropics reducer path must be marked `historical/stale path` instead of being merged into the current route.
3. Make the chronology visible inside the matrix so a fresh executor can tell that the newer Stage-1/Stage-2 regional chain superseded the older full-tropics cache/reducer route without rereading the whole stash history.

## Must-Haves

- [ ] The matrix contains separate rows for the current Phase 4 Stage-1/Stage-2 route and the historical full-tropics reducer route.
- [ ] Every late-phase row cites concrete stash/changelog anchors and states whether the remaining gap is local, HPC-only, or route-history ambiguity.

## Done when

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` contains all late-phase rows from `Phase 3.6` onward and the Phase 4 split is reader-visible without extra interpretation.

## Inputs

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- `CHANGELOG.md`
- `docs/stashes/2026-03-31-022-phase36-gwd30-tile-reduce-handoff.md`
- `docs/stashes/2026-04-01-011-phase361-gwd30-hotspot-trace-diagnostics.md`
- `docs/stashes/2026-04-01-002-phase37-global-500m-handoff.md`
- `docs/stashes/2026-04-01-004-phase37-hotspots-implementation.md`
- `docs/stashes/2026-04-06-003-phase4-conversation-summary.md`
- `docs/stashes/2026-04-06-005-phase4-stage2-pixel-stats-regional-integration.md`
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md`

## Expected Output

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`

## Verification

`rg -n "Phase 3.6|Phase 3.6.1|Phase 3.7|Phase 4 current Stage-1 / Stage-2 route|Phase 4 historical full-tropics reducer route" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "2026-03-31-022|2026-04-01-011|2026-04-01-002|2026-04-01-004|2026-04-06-003|2026-04-06-005|2026-04-06-008" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "historical/stale path|implemented-but-unverified|HPC / external proof" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
