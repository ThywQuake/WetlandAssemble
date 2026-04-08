# S05: Operator Recovery Pack — UAT

**Milestone:** M001
**Written:** 2026-04-06T23:14:55.998Z

# S05: Operator Recovery Pack — UAT

**Milestone:** M001
**Written:** 2026-04-07

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S05 ships documentation and metadata recovery surfaces, not runtime code; correctness is whether a fresh operator can recover the right source hierarchy without reproducing commands or route debates from scratch.

## Preconditions

- `.gsd/milestones/M001/slices/S01` through `S05` artifacts exist in the worktree.
- `.gsd/REQUIREMENTS.md`, `.gsd/PROJECT.md`, `CHANGELOG.md`, and `.gsd/KNOWLEDGE.md` are present.
- No HPC cluster access is required; this UAT inspects artifact content only.

## Smoke Test

Open `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` and confirm it contains all six required sections plus a `Canonical Question -> Source Map` that sends route-truth questions to S03 and execution copying to S04.

## Test Cases

### 1. Recover orientation from the first-stop pack

1. Open `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`.
2. Read `## What This Pack Is` and `## Canonical Question -> Source Map`.
3. Find the row answering “What exact continuation order should I follow next?”
4. **Expected:** The pack identifies itself as an index/handoff layer, not a fifth audit, and routes actual continuation steps to `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` -> `## Ordered Continuation Path`.

### 2. Resolve route truth without promoting stale breadcrumbs

1. In the same pack, find the row answering “Which Phase 4 route is current, and which route family is stale or misleading?”
2. Follow that pointer to `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`.
3. Return to the pack and read `## Do Not Promote to Source of Truth`.
4. **Expected:** S03 is clearly named as route truth, and `docs/stashes/2026-04-06-008-phase4-recall-entry.md` is explicitly demoted beneath S03/S04 rather than treated as equal-weight guidance.

### 3. Verify the recovery hierarchy is repeated across metadata surfaces

1. Open `docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md`.
2. Confirm it says to `先读` the S05 pack and to copy any actual execution steps from S04.
3. Open `.gsd/REQUIREMENTS.md` and confirm `R008` is validated against the S05 pack plus the subordinate breadcrumb.
4. Open `.gsd/PROJECT.md`, `CHANGELOG.md`, and `.gsd/KNOWLEDGE.md`.
5. **Expected:** All four metadata surfaces repeat the same hierarchy: S05 = first-stop recovery index, S03 = route truth, S04 = execution truth, and the inherited HPC-only proof gap remains open.

## Edge Cases

### Operator starts from the wrong short note

1. Start from `docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md` or the 2026-04-07 `CHANGELOG.md` entry instead of the S05 pack.
2. Follow the references they provide.
3. **Expected:** Those shorter breadcrumbs route the operator back to the canonical S05/S03/S04 chain and do not themselves try to become a replacement recovery pack or execution map.

## Failure Signals

- `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` is missing any of the six required sections.
- The pack embeds a standalone command ladder instead of sending execution copying back to S04.
- Route-truth questions are not clearly routed to S03.
- `R008` is not rendered as validated in `.gsd/REQUIREMENTS.md`.
- `.gsd/KNOWLEDGE.md` or `.gsd/PROJECT.md` fails to preserve the S05/S03/S04 precedence rule.
- The breadcrumb note reads like another equal-weight recovery pack instead of a subordinate pointer.

## Not Proven By This UAT

- Fresh HPC reruns of the Phase 4 Stage-1 / Stage-2 route.
- Existence or correctness of remote `results/phase4/...` artifacts on HPC.
- Any scientific output beyond the recovery/documentation hierarchy created by S05.

## Notes for Tester

Treat this as a control-recovery UAT, not a pipeline runtime UAT. The pass condition is that a fresh operator can recover the correct source hierarchy quickly and is pushed back to S03 for route truth and S04 for execution truth without reopening stale-route ambiguity.
