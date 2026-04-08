# S05: Operator Recovery Pack

**Goal:** Package the now-canonical S01/S02/S03/S04 audit artifacts into one compact operator recovery pack that lets a future re-entry recover control quickly, find the right source for each question, and keep the HPC-only proof boundary explicit without recreating competing route or execution summaries.
**Demo:** After this: After this: a future re-entry can recover control quickly from compact milestone artifacts instead of replaying the entire repository history.

## Tasks
- [x] **T01: Add the canonical S05 operator recovery pack and freeze recovery source precedence.** — Draft the canonical S05 pack first so a fresh operator can answer “which artifact owns this question?” without reopening route debates or copying S04's full command ladder into a new summary.

## Steps

1. Create `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` and frame it as the first-stop re-entry index, explicitly saying that S03 remains route truth and S04 remains execution truth.
2. Add a `Canonical Question -> Source Map` table that routes raw inventory, drift boundaries, phase/module status, current-vs-stale route truth, and next-step execution back to the exact S01/S02/S03/S04 artifacts and section names a reader should jump to first.
3. Finish the pack with `Fast Re-entry Modes`, `Open Proof Boundary Snapshot`, `Do Not Promote to Source of Truth`, and `Immediate Next Action`, keeping the still-open HPC-only rerun gap explicit and demoting `docs/stashes/2026-04-06-008-phase4-recall-entry.md` behind the canonical S03/S04 documents.

## Must-Haves

- [ ] The pack is clearly an index/handoff layer, not a fifth audit, and it states that S03 owns route truth while S04 owns execution truth.
- [ ] The pack names every canonical recovery artifact, points to exact section anchors, keeps the HPC-only proof gap explicit, and sends operators back to S04 instead of duplicating the full command ladder.

## Done when

- `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` exists with the required six sections and a question-to-artifact map that lets a fresh reader find route truth, execution order, and open proof gaps in one skim.
  - Estimate: 35m
  - Files: .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md, .gsd/milestones/M001/slices/S01/S01-INVENTORY.md, .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md, .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md, .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md, .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md
  - Verify: `test -s .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`
`rg -n '^## (What This Pack Is|Canonical Question -> Source Map|Fast Re-entry Modes|Open Proof Boundary Snapshot|Do Not Promote to Source of Truth|Immediate Next Action)$' .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`
`rg -n 'S01-INVENTORY.md|S01-DRIFT-BOUNDARIES.md|S02-PHASE-MODULE-MATRIX.md|S03-ROUTE-AUDIT-RISK-REGISTER.md|S04-NEXT-STEP-EXECUTION-MAP.md' .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`
`rg -n 'Current Recommended Routes|Ordered Continuation Path|Proof Targets / Exit Criteria|Open Proof Gaps|docs/stashes/2026-04-06-008-phase4-recall-entry.md' .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`
- [x] **T02: Published the S05 recovery breadcrumb and validated R008 against the canonical operator recovery pack.** — Close the slice by adding a subordinate stash breadcrumb and refreshing the recovery metadata so `R008` validates against the new pack instead of leaving the next operator to rediscover the hierarchy manually.

## Steps

1. Write `docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md` as a short Chinese-friendly breadcrumb that points to `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` first and sends any actual execution copying back to S04.
2. Update `.gsd/REQUIREMENTS.md`, `.gsd/PROJECT.md`, and `CHANGELOG.md` so `R008` validates against the S05 pack, the current-state recovery stack now includes S05 as the top-level index, and the changelog leaves a breadcrumb back to the canonical pack and note.
3. Add one knowledge rule in `.gsd/KNOWLEDGE.md` that freezes the precedence order `S05 = first-stop recovery index`, `S03 = route truth`, `S04 = execution truth`, so future re-entry notes do not regain equal weight.

## Must-Haves

- [ ] The stash note stays subordinate to the canonical S05 pack and S04 map instead of becoming another recovery pack or execution map.
- [ ] `R008` is validated against the finished S05 pack, and the project/knowledge/changelog surfaces preserve the same precedence rule without implying that the HPC-only proof gap is closed.

## Done when

- The stash note exists, `R008` is validated in `.gsd/REQUIREMENTS.md`, `.gsd/PROJECT.md` reflects S05 as the top recovery layer, `CHANGELOG.md` links back to the pack/note, and `.gsd/KNOWLEDGE.md` records the precedence rule.
  - Estimate: 30m
  - Files: docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md, .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md, .gsd/REQUIREMENTS.md, .gsd/PROJECT.md, CHANGELOG.md, .gsd/KNOWLEDGE.md
  - Verify: `test -s docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md`
`rg -n 'S05-OPERATOR-RECOVERY-PACK.md|S04-NEXT-STEP-EXECUTION-MAP.md|先读|canonical|breadcrumb' docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md`
`rg -n 'R008 \[continuity\] \(validated\)|S05-OPERATOR-RECOVERY-PACK.md' .gsd/REQUIREMENTS.md`
`rg -n 'S05|Operator Recovery Pack|S05-OPERATOR-RECOVERY-PACK.md' .gsd/PROJECT.md`
`rg -n 'S05-OPERATOR-RECOVERY-PACK.md|docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md' CHANGELOG.md`
`rg -n 'S05-OPERATOR-RECOVERY-PACK.md|S03-ROUTE-AUDIT-RISK-REGISTER.md|S04-NEXT-STEP-EXECUTION-MAP.md' .gsd/KNOWLEDGE.md`
