---
estimated_steps: 11
estimated_files: 4
skills_used: []
---

# T05: Publish requirement closure and the Chinese re-entry note

## Description

Close the slice by pointing requirements and future operators at the canonical matrix instead of making later slices replay the same synthesis work.

## Steps

1. Review the finished matrix and update `.gsd/REQUIREMENTS.md` so R002 and R007 cite `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` as their validation evidence only if the matrix actually covers both the grade contract and the local-vs-HPC proof split.
2. Write `docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md` in Chinese-friendly style, summarizing what the matrix contains, how to interpret the Phase 4 current-vs-historical split, which verification commands still matter, and which proof gaps remain HPC-only.
3. Cross-link the re-entry note back to the canonical matrix so S03/S05 can recover from the compact note first and then drill down into the full artifact.

## Must-Haves

- [ ] R002 and R007 point to the finished matrix as their evidence source, not to an intermediate draft or vague prose.
- [ ] The Chinese re-entry note names the canonical matrix path, the verification commands, the current Phase 4 route split, and the remaining HPC-only gaps.

## Done when

- `.gsd/REQUIREMENTS.md` reflects the finished matrix evidence and `docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md` exists as the compact operator handoff for this slice.

## Inputs

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- `.gsd/REQUIREMENTS.md`
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md`
- `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md`

## Expected Output

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- `.gsd/REQUIREMENTS.md`
- `docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md`

## Verification

`test -s docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md`
`rg -n "R002|R007" .gsd/REQUIREMENTS.md`
`rg -n "S02-PHASE-MODULE-MATRIX.md|Verification|Open HPC Gaps|Stage 1|Stage 2" docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md`
