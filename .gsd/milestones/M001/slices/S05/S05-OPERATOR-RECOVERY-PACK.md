# S05 Operator Recovery Pack

## What This Pack Is

This is the **first-stop re-entry index** for Milestone M001. It is **not** a fifth audit, not a replacement execution map, and not a new source of proof.

Source-precedence rule for recovery:

1. **S05** (`.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`) = first-stop index that tells you which artifact owns which question.
2. **S03** (`../S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`) = **route truth**. If the question is “which continuation path is current vs stale?”, jump to `## Current Recommended Routes`, `## Historical/Stale or Misleading Routes`, and `## Risk Register`.
3. **S04** (`../S04/S04-NEXT-STEP-EXECUTION-MAP.md`) = **execution truth**. If the question is “what do I run next, in what order, and what counts as proof?”, jump to `## Ordered Continuation Path`, `## Proof Targets / Exit Criteria`, and `## Do Not Touch First`.
4. **S02** (`../S02/S02-PHASE-MODULE-MATRIX.md`) = current status/proof-boundary grading. Use `## Phase Matrix`, `## Module Matrix`, and `## Open Proof Gaps`.
5. **S01** (`../S01/S01-INVENTORY.md` and `../S01/S01-DRIFT-BOUNDARIES.md`) = raw inventory freeze plus current-vs-historical weighting and proof-boundary context.

Canonical recovery artifacts named explicitly:

- `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
- `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`
- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`

Read this pack first only to recover orientation quickly. Then leave it and go to the canonical owner.

## Canonical Question -> Source Map

| If the question is... | Jump to this source first | Exact section anchor to read first | Why this source owns it |
|---|---|---|---|
| What is actually present locally, and what repository surface exists right now? | `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` | `## Snapshot`, `## Runtime Code Surface`, `## Operational Script Surface` | S01 is the raw evidence freeze for files, counts, and directly inspectable surfaces. |
| What is absent-local vs external/HPC-only, and what proof boundary should I keep in mind? | `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` then `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` | `## Artifact Presence and Proof Boundaries` then `## Proof Boundaries` | S01 owns the local absence/presence freeze and the explicit external/HPC-only boundary language. |
| Which signals are current, and which notes/plans are historical or superseded? | `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` | `## Current Signals`, `## Historical / Superseded Signals` | S01 drift boundaries weights the evidence before route judgment begins. |
| Which Phase 4 route is current, and which route family is stale or misleading? | `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` | `## Current Recommended Routes`, `## Historical/Stale or Misleading Routes` | S03 is the canonical route judgment. Do not answer route disputes from stash notes alone. |
| What evidence order should win if an older plan or stash conflicts with newer code-backed history? | `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` | `## Evidence Rule` | S03 explicitly defines how newer source-code-backed 2026-04-06 evidence outranks older route language. |
| What is validated vs implemented-but-unverified across phases and modules? | `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` | `## Phase Matrix`, `## Module Matrix` | S02 owns status grading and proof-boundary classification. |
| Where are the still-open proof gaps, especially the HPC-only rerun gap? | `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` then `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` | `## Open Proof Gaps` then `## Proof Targets / Exit Criteria` | S02 states the gap; S04 states what fresh proof must exist before that gap counts as closed. |
| What exact continuation order should I follow next? | `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` | `## Canonical Read Order`, `## Ordered Continuation Path` | S04 is the canonical operator ladder. Copy commands from there, not from this pack. |
| What should I avoid touching first, and which stale flags/routes should I not copy? | `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` then `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` | `## Do Not Touch First` then `## Historical/Stale or Misleading Routes` | S04 owns execution guardrails; S03 explains why the avoided routes are stale. |
| Where did the older human-readable recall breadcrumb live, and how much authority should it have now? | `docs/stashes/2026-04-06-008-phase4-recall-entry.md` | `## Current Entry Point`, `## Open Risks`, `## Verification Snapshot` | Use it only as an older convenience note. It no longer outranks S03 route truth or S04 execution truth. |

## Fast Re-entry Modes

### 1. 60-second orientation mode

- Read this pack only through `## Canonical Question -> Source Map`.
- If your question is about **route truth**, jump immediately to `S03 -> ## Current Recommended Routes`.
- If your question is about **what to run next**, jump immediately to `S04 -> ## Ordered Continuation Path`.
- If your question is about **proof boundaries**, jump immediately to `S02 -> ## Open Proof Gaps`.

### 2. Route dispute mode

Use this order only:

1. `S03 -> ## Evidence Rule`
2. `S03 -> ## Current Recommended Routes`
3. `S03 -> ## Historical/Stale or Misleading Routes`
4. `S03 -> ## Risk Register`

Do not resolve route disputes from `CHANGELOG.md` snippets or stash notes without passing back through S03.

### 3. Execute-now mode

Use this order only:

1. `S03 -> ## Current Recommended Routes`
2. `S02 -> Phase 4 current Stage-1 / Stage-2 route` row plus `## Open Proof Gaps`
3. `S04 -> ## Ordered Continuation Path`
4. `S04 -> ## Proof Targets / Exit Criteria`

When you are ready to run commands, return to S04 and copy the ladder there verbatim instead of recreating it here.

### 4. Proof-gap audit mode

If the question is “what is still open?” read:

1. `S02 -> ## Open Proof Gaps`
2. `S03 -> ## Risk Register`
3. `S04 -> ## Proof Targets / Exit Criteria`
4. `S01 -> ## Artifact Presence and Proof Boundaries`

This keeps the distinction clear between **current route judgment** and **fresh runtime proof**.

## Open Proof Boundary Snapshot

- The current canonical Phase 4 mainline remains the **Stage 1 pixel-statistics build -> Stage 2 regional tables** chain documented in `S03 -> ## Current Recommended Routes` and operationalized in `S04 -> ## Ordered Continuation Path`.
- That chain is still **implemented-but-unverified** in `S02 -> Phase 4 current Stage-1 / Stage-2 route`. The open gap is not conceptual; it is the still-missing **fresh HPC rerun**.
- The specific proof bar remains the one frozen in `S04 -> ## Proof Targets / Exit Criteria`: narrow Stage-1 proof first, narrow Stage-2 proof second, then widen only after the required artifacts exist.
- `results/` is absent in this worktree and `/lustre/...` roots are external/HPC-only. Local docs, changelog entries, and stash notes can prove the intended route hierarchy, but they do **not** prove that remote artifacts currently exist.
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md` is useful as historical operator context, but its command snapshot does not close the proof gap and should not be read as fresher than S02/S03/S04.

## Do Not Promote to Source of Truth

- Do **not** promote this pack into a fifth audit. It is an index/handoff layer only.
- Do **not** promote this pack into a second execution map. The full command ladder stays in `S04 -> ## Ordered Continuation Path`.
- Do **not** promote stash breadcrumbs over canonical recovery docs. In particular, `docs/stashes/2026-04-06-008-phase4-recall-entry.md` is now subordinate to S03 and S04.
- Do **not** answer “what route is current?” from this pack alone. Go back to `S03-ROUTE-AUDIT-RISK-REGISTER.md`.
- Do **not** answer “what should I run next?” from this pack alone. Go back to `S04-NEXT-STEP-EXECUTION-MAP.md`.
- Do **not** answer “is the route freshly proven?” from this pack alone. Go back to `S02 -> ## Open Proof Gaps` and `S04 -> ## Proof Targets / Exit Criteria`.

## Immediate Next Action

1. Re-read `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`, starting with `## Current Recommended Routes` and `## Risk Register`, until the current-vs-stale route split is unambiguous again.
2. Re-read `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`, focusing on the `Phase 4 current Stage-1 / Stage-2 route` row and `## Open Proof Gaps`, so the HPC-only rerun boundary is explicit before any execution starts.
3. Then return to `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` and use `## Ordered Continuation Path` plus `## Proof Targets / Exit Criteria` as the canonical continuation contract.
4. If real execution is starting now, do **not** copy commands from this pack. Copy them from S04, starting with the narrow Stage-1 rung and then the narrow Stage-2 rung.
