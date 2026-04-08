---
estimated_steps: 11
estimated_files: 6
skills_used: []
---

# T02: Separate drift signals, proof boundaries, and the quick re-entry note

## Description

Finish the slice by turning the raw inventory into an appendix that later slices can reason from and by leaving a compact operator-facing recovery note in `docs/stashes/`.

## Steps

1. Review the high-signal plans, changelog entries, and stash summaries already identified by research and group them into `current-signal`, `historical`, and `superseded` sets without yet deciding the final canonical route.
2. Write `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` so S02/S03 can see which evidence is current, which is stale, and which claims remain `external/HPC-only` or `absent-local` in this worktree.
3. Cross-link the appendix from `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` and write `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` as a concise Chinese-friendly recovery note covering outputs, verification commands, and open risks.

## Must-Haves

- [ ] The appendix explicitly separates current-route signals from stale/superseded references and from proof-boundary gaps.
- [ ] The recovery note points future re-entry to the canonical inventory, the appendix, the replayable commands, and the unresolved local-vs-HPC caveats.

## Done when

- `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` and `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` both exist, and the main inventory cross-links the appendix.

## Inputs

- `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
- `.gsd/milestones/M001/slices/S01/S01-RESEARCH.md`
- `CHANGELOG.md`
- `docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md`
- `docs/stashes/2026-04-06-003-phase4-conversation-summary.md`
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md`
- `.gitignore`

## Expected Output

- `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`
- `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md`
- `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md`

## Verification

`test -s .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md && test -s docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md`
`rg -n "^## (Current Signals|Historical / Superseded Signals|Proof Boundaries|Handoff to S02 and S03)$" .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`
`rg -n "S01-DRIFT-BOUNDARIES.md" .gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
`rg -n "S01-INVENTORY.md|S01-DRIFT-BOUNDARIES.md|Open Risks|Verification Snapshot" docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md`
