---
estimated_steps: 11
estimated_files: 8
skills_used: []
---

# T01: Draft the grading contract and early/core phase rows

## Description

Build the canonical grading contract and the early/core phase rows first so S02 directly advances R002 and R007 without reopening S01’s raw-inventory work.

## Steps

1. Restate the D002 grade vocabulary and the S01 local-vs-HPC proof-boundary rule at the top of `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`, including the rule that newer changelog/stash evidence outweighs stale `active` plans.
2. Populate the `Phase Matrix` rows for `Phase 1`, `Phase 1.1`, `Phase 1.5`, `Phase 1.6`, `Phase 2`, `Phase 2.5`, `Phase 2.6`, `Phase 3`, and `Phase 3.5` using the preselected S01 artifacts, changelog entries, and early stash summaries instead of a fresh repo audit.
3. Give every row the same columns — `Grade`, `Local evidence`, `HPC / external proof`, and `Why this grade` — and keep rows below `validated` whenever fresh runtime/HPC proof is missing.

## Must-Haves

- [ ] The grading contract names all four D002 grades exactly and cross-links `S01-INVENTORY.md` plus `S01-DRIFT-BOUNDARIES.md`.
- [ ] The early/core phase rows cover all named phases and make the local-vs-HPC proof split explicit instead of flattening them into a single status claim.

## Done when

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` exists with a `Grading Contract` section and a populated `Phase Matrix` covering `Phase 1` through `Phase 3.5`.

## Inputs

- `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
- `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`
- `CHANGELOG.md`
- `docs/stashes/2026-03-19-002-fix-phase1-loader-hpc-verified.md`
- `docs/stashes/2026-03-22-001-phase2-closeout-rough-review-and-debug-summary.md`
- `docs/stashes/2026-03-22-005-phase3-implementation-summary.md`
- `docs/stashes/2026-03-31-015-phase26-wrap-up.md`

## Expected Output

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`

## Verification

`test -s .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "^## (Grading Contract|Phase Matrix)$" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "Phase 1|Phase 1.1|Phase 1.5|Phase 1.6|Phase 2|Phase 2.5|Phase 2.6|Phase 3|Phase 3.5" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "validated|implemented-but-unverified|historical/stale path|unclear|Local evidence|HPC / external proof|Why this grade" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
