---
estimated_steps: 10
estimated_files: 6
skills_used:
  - doc-coauthoring
  - document-review
---

# T02: Publish the compact breadcrumb and close R008 metadata around the S05 pack

Close the slice by adding a subordinate stash breadcrumb and refreshing the recovery metadata so `R008` validates against the new pack instead of leaving the next operator to rediscover the hierarchy manually.

## Steps

1. Write `docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md` as a short Chinese-friendly breadcrumb that points to `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` first and sends any actual execution copying back to S04.
2. Update `.gsd/REQUIREMENTS.md`, `.gsd/PROJECT.md`, and `CHANGELOG.md` so `R008` validates against the S05 pack, the current-state recovery stack now includes S05 as the top-level index, and the changelog leaves a breadcrumb back to the canonical pack and note.
3. Add one knowledge rule in `.gsd/KNOWLEDGE.md` that freezes the precedence order `S05 = first-stop recovery index`, `S03 = route truth`, `S04 = execution truth`, so future re-entry notes do not regain equal weight.

## Must-Haves

- [ ] The stash note stays subordinate to the canonical S05 pack and S04 map instead of becoming another recovery pack or execution map.
- [ ] `R008` is validated against the finished S05 pack, and the project/knowledge/changelog surfaces preserve the same precedence rule without implying that the HPC-only proof gap is closed.

## Done when

- The stash note exists, `R008` is validated in `.gsd/REQUIREMENTS.md`, `.gsd/PROJECT.md` reflects S05 as the top recovery layer, `CHANGELOG.md` links back to the pack/note, and `.gsd/KNOWLEDGE.md` records the precedence rule.

## Inputs

- `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/PROJECT.md`
- `CHANGELOG.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md`

## Expected Output

- `docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/PROJECT.md`
- `CHANGELOG.md`
- `.gsd/KNOWLEDGE.md`

## Verification

`test -s docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md`
`rg -n 'S05-OPERATOR-RECOVERY-PACK.md|S04-NEXT-STEP-EXECUTION-MAP.md|先读|canonical|breadcrumb' docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md`
`rg -n 'R008 \[continuity\] \(validated\)|S05-OPERATOR-RECOVERY-PACK.md' .gsd/REQUIREMENTS.md`
`rg -n 'S05|Operator Recovery Pack|S05-OPERATOR-RECOVERY-PACK.md' .gsd/PROJECT.md`
`rg -n 'S05-OPERATOR-RECOVERY-PACK.md|docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md' CHANGELOG.md`
`rg -n 'S05-OPERATOR-RECOVERY-PACK.md|S03-ROUTE-AUDIT-RISK-REGISTER.md|S04-NEXT-STEP-EXECUTION-MAP.md' .gsd/KNOWLEDGE.md`
