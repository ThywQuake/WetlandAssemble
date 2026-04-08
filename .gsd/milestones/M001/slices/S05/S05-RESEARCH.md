# M001 / S05 — Research

**Date:** 2026-04-07

## Summary

S05 directly owns **R008** and only works if it stays a **packaging/index slice**, not a fifth audit. M001 already has four canonical layers and four compact breadcrumbs: S01 gives the raw fact base, S02 gives evidence grades and open proof gaps, S03 gives route truth plus stale-route demotion, and S04 gives the ordered execution ladder. The missing deliverable is a **single compact recovery index** that tells a future operator which artifact answers which question and what not to reread first.

The strongest local scaffold already exists in `.gsd/PROJECT.md`: it lists the four-layer recovery stack and explicitly says S05 should package S01/S02/S03/S04 into one re-entry bundle **without duplicating S04’s command ladder**. `S05-PLAN.md` currently has **no tasks**, so the planner should seed them from scratch. This slice should therefore create one canonical S05 pack doc, then one secondary stash breadcrumb, then close `R008` in metadata.

The installed `doc-coauthoring` skill is directly relevant here: create **one canonical reader-facing document first**, keep any shorter note as a pointer only, and judge success by whether a fresh reader can answer the right questions quickly. For S05, those questions are: “Where is the raw inventory?”, “What is the current-vs-stale route truth?”, “What remains HPC-only?”, and “Where is the actual next-step execution ladder?”

## Recommendation

Create one canonical artifact:

- `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`

That document should be a compact **question-to-artifact index**, not another prose retelling of the milestone. Recommended required blocks:

1. **What This Pack Is**
   - State that S05 is the first re-entry stop for M001.
   - State that S03 remains route truth and S04 remains execution order.

2. **Canonical Question -> Source Map**
   - A table such as:
     - raw inventory / repo surfaces -> `S01-INVENTORY.md`
     - current vs historical signals / proof boundaries -> `S01-DRIFT-BOUNDARIES.md`
     - phase/module status and local vs HPC proof -> `S02-PHASE-MODULE-MATRIX.md`
     - current route and stale routes -> `S03-ROUTE-AUDIT-RISK-REGISTER.md`
     - what to run next and what proves success -> `S04-NEXT-STEP-EXECUTION-MAP.md`
   - Include exact section names so the operator can jump directly.

3. **Fast Re-entry Modes**
   - `5-minute skim` — read S05 pack, then jump to the exact canonical artifact.
   - `15-minute route recovery` — S05 -> S03 -> S04.
   - `pre-HPC execution` — S05 -> S03 `Current Recommended Routes` -> S04 `Ordered Continuation Path` + `Proof Targets / Exit Criteria`.

4. **Open Proof Boundary Snapshot**
   - Preserve the still-open HPC-only rerun gap.
   - Make clear that M001 documented the route; it did not produce fresh remote proof.

5. **Do Not Promote to Source of Truth**
   - Older broad Phase 4 recall notes and retained active plans are supporting background only.
   - Explicitly demote `docs/stashes/2026-04-06-008-phase4-recall-entry.md` behind S03/S04.
   - State that compact stash notes are breadcrumbs, not canonical truth.

6. **Immediate Next Action**
   - Point to S04’s `Ordered Continuation Path`, `Proof Targets / Exit Criteria`, and `Do Not Touch First`.
   - Do **not** re-copy the full HPC commands; S05 should route the operator back to S04 for those.

Then add one short stash note under `docs/stashes/` following the existing `YYYY-MM-DD-###-m001-s05-...` pattern. That note should point back to the S05 pack first, and only then to S04 for actual execution. After the docs are stable, update `.gsd/REQUIREMENTS.md` to validate `R008`, refresh `.gsd/PROJECT.md`, and add a `CHANGELOG.md` breadcrumb. A `.gsd/KNOWLEDGE.md` rule is worth adding only if execution wants to freeze the precedence rule “S05 is the entry index; S03 is route truth; S04 is execution truth.”

## Implementation Landscape

### Key Files

- `.gsd/milestones/M001/slices/S05/S05-PLAN.md` — currently only contains the slice title/goal and **no tasks**; planner needs to populate this.
- `.gsd/PROJECT.md` — already contains the four-layer recovery scaffold and the explicit instruction that S05 should package those layers without recreating S04’s command ladder.
- `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` — raw evidence base; current headings are `Snapshot`, `Runtime Code Surface`, `Operational Script Surface`, `Verification Surface`, `Planning and History Surface`, `Dataset, TODO, and Config Surface`, `Git and Worktree State`, `Artifact Presence and Proof Boundaries`, and `Command Appendix`.
- `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` — interpretation layer for `Current Signals`, `Historical / Superseded Signals`, `Proof Boundaries`, and `Handoff to S02 and S03`.
- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` — canonical status surface; current headings are `Grading Contract`, `Phase Matrix`, `Module Matrix`, `Requirement Coverage`, and `Open Proof Gaps`.
- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` — canonical route-truth artifact; current headings are `Evidence Rule`, `Current Recommended Routes`, `Supporting but Non-Primary Routes`, `Historical/Stale or Misleading Routes`, `Risk Register`, and `Requirement Coverage`.
- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` — canonical execution-order artifact; current headings are `Canonical Read Order`, `Ordered Continuation Path`, `Proof Targets / Exit Criteria`, `Do Not Touch First`, and `Requirement Coverage`.
- `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` — compact S01 breadcrumb.
- `docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md` — compact S02 breadcrumb.
- `docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md` — compact S03 breadcrumb.
- `docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md` — compact S04 breadcrumb.
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md` — older pre-M001 recovery note; still useful background, but S05 should explicitly classify it as secondary to S03/S04.
- `CHANGELOG.md` — already contains 2026-04-07 breadcrumbs for S02/S03/S04; S05 should add one more breadcrumb rather than a long narrative.
- `.gsd/REQUIREMENTS.md` — `R008` is still active; S05 should validate it here once the pack exists.
- `.gsd/KNOWLEDGE.md` / `.gsd/DECISIONS.md` — optional metadata surfaces if S05 freezes a reusable precedence rule for future re-entry.

### Build Order

1. **Draft the canonical S05 pack first.**
   Use `.gsd/PROJECT.md` plus the canonical S01/S02/S03/S04 docs as inputs. Do not start from old Phase 4 recall notes.

2. **Add the question-to-artifact map and recovery modes second.**
   This is the real value of S05: turning four separate canonical layers into one operator-facing decision/index surface.

3. **Add the stash breadcrumb third.**
   Keep it short and subordinate. It should route to S05 first, not become a second recovery pack.

4. **Close metadata last.**
   Update `.gsd/REQUIREMENTS.md` for `R008`, refresh `.gsd/PROJECT.md`, and add the changelog breadcrumb after the docs are stable.

Natural seam for planning: this is best decomposed into **two tasks** — `(1)` canonical S05 pack, `(2)` compact stash note + metadata/requirement closure. A third task is only needed if the executor wants to separate metadata from the note.

### Verification Approach

Structural verification is the right proof class for S05:

```bash
test -s .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md
rg -n '^## (What This Pack Is|Canonical Question -> Source Map|Fast Re-entry Modes|Open Proof Boundary Snapshot|Do Not Promote to Source of Truth|Immediate Next Action)$' .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md
rg -n 'S01-INVENTORY.md|S01-DRIFT-BOUNDARIES.md|S02-PHASE-MODULE-MATRIX.md|S03-ROUTE-AUDIT-RISK-REGISTER.md|S04-NEXT-STEP-EXECUTION-MAP.md' .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md
rg -n 'Current Recommended Routes|Ordered Continuation Path|Proof Targets / Exit Criteria|Open Proof Gaps|docs/stashes/2026-04-06-008-phase4-recall-entry.md' .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md
test -s docs/stashes/*m001-s05*operator*recovery*.md
rg -n 'R008' .gsd/REQUIREMENTS.md
```

One extra reader test is worth doing manually: from the S05 pack alone, a fresh operator should be able to answer all three questions without opening old plans first:

1. Which file tells me what route is current?
2. Which file tells me what to run next?
3. Which proof gaps are still HPC-only?

If those answers are not obvious within one skim, the pack is still too diffuse.

## Constraints

- S05 owns **R008**; it should package prior slice outputs, not reopen route classification or re-grade modules.
- Follow the `doc-coauthoring` rule: one canonical reader-facing doc first, supporting note second.
- Keep S03 as **route truth** and S04 as **execution truth**; S05 is an index/handoff layer.
- Do not invent a new milestone-root naming convention unless absolutely necessary; the existing slice-local canonical-artifact pattern is consistent and sufficient.
- Do not modify `config/` or runtime code for this slice.
- Keep the project’s HPC proof boundary explicit: S05 should never imply that documentation closure equals fresh remote rerun proof.

## Common Pitfalls

- **Writing another narrative milestone summary instead of an index** — S05 is most useful as a routing surface, not as a fifth long-form explanation.
- **Copying S04’s full command ladder into S05** — this would create a competing execution map and break the current canonical hierarchy.
- **Flattening canonical docs and breadcrumbs into equal-weight sources** — the operator pack should explicitly preserve the precedence order.
- **Treating older recall notes as first-stop documents** — `2026-04-06-008-phase4-recall-entry.md` is now background, not the primary re-entry surface.
- **Forgetting metadata closure** — without updating `.gsd/REQUIREMENTS.md`, the slice can look complete locally while `R008` remains active.

## Open Risks

- **Over-compression risk** — if S05 gets too terse, it may hide why S03 and S04 are separate. Use exact section anchors to retain precision without length.
- **Precedence drift risk** — if S05 does not explicitly state “S03 = route truth; S04 = execution truth,” future operators may still jump straight into older notes.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Structured documentation workflow | `doc-coauthoring` | installed |
| Review/refinement of plan/doc artifacts | `document-review` | available |
