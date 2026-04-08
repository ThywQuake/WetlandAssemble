---
estimated_steps: 10
estimated_files: 6
skills_used:
  - doc-coauthoring
  - document-review
---

# T01: Author the canonical S05 operator recovery pack as the first-stop re-entry index

Draft the canonical S05 pack first so a fresh operator can answer “which artifact owns this question?” without reopening route debates or copying S04's full command ladder into a new summary.

## Steps

1. Create `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` and frame it as the first-stop re-entry index, explicitly saying that S03 remains route truth and S04 remains execution truth.
2. Add a `Canonical Question -> Source Map` table that routes raw inventory, drift boundaries, phase/module status, current-vs-stale route truth, and next-step execution back to the exact S01/S02/S03/S04 artifacts and section names a reader should jump to first.
3. Finish the pack with `Fast Re-entry Modes`, `Open Proof Boundary Snapshot`, `Do Not Promote to Source of Truth`, and `Immediate Next Action`, keeping the still-open HPC-only rerun gap explicit and demoting `docs/stashes/2026-04-06-008-phase4-recall-entry.md` behind the canonical S03/S04 documents.

## Must-Haves

- [ ] The pack is clearly an index/handoff layer, not a fifth audit, and it states that S03 owns route truth while S04 owns execution truth.
- [ ] The pack names every canonical recovery artifact, points to exact section anchors, keeps the HPC-only proof gap explicit, and sends operators back to S04 instead of duplicating the full command ladder.

## Done when

- `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` exists with the required six sections and a question-to-artifact map that lets a fresh reader find route truth, execution order, and open proof gaps in one skim.

## Inputs

- `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
- `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`
- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md`

## Expected Output

- `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`

## Verification

`test -s .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`
`rg -n '^## (What This Pack Is|Canonical Question -> Source Map|Fast Re-entry Modes|Open Proof Boundary Snapshot|Do Not Promote to Source of Truth|Immediate Next Action)$' .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`
`rg -n 'S01-INVENTORY.md|S01-DRIFT-BOUNDARIES.md|S02-PHASE-MODULE-MATRIX.md|S03-ROUTE-AUDIT-RISK-REGISTER.md|S04-NEXT-STEP-EXECUTION-MAP.md' .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`
`rg -n 'Current Recommended Routes|Ordered Continuation Path|Proof Targets / Exit Criteria|Open Proof Gaps|docs/stashes/2026-04-06-008-phase4-recall-entry.md' .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`
