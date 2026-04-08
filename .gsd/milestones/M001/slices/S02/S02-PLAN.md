# S02: Phase & Module State Matrix

**Goal:** Convert S01’s frozen inventory into one evidence-graded matrix of major phases and module families, explicitly separating locally proven state from HPC/external proof gaps.
**Demo:** After this: After this: each major phase and module has a status grade with evidence behind it, and local proof is clearly separated from HPC-only proof.

## Tasks
- [x] **T01: Added the canonical S02 grading contract and early/core phase rows to the phase matrix.** — ## Description

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
  - Estimate: 40m
  - Files: .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md, .gsd/milestones/M001/slices/S01/S01-INVENTORY.md, .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md, CHANGELOG.md, docs/stashes/2026-03-19-002-fix-phase1-loader-hpc-verified.md, docs/stashes/2026-03-22-001-phase2-closeout-rough-review-and-debug-summary.md, docs/stashes/2026-03-22-005-phase3-implementation-summary.md, docs/stashes/2026-03-31-015-phase26-wrap-up.md
  - Verify: `test -s .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "^## (Grading Contract|Phase Matrix)$" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "Phase 1|Phase 1.1|Phase 1.5|Phase 1.6|Phase 2|Phase 2.5|Phase 2.6|Phase 3|Phase 3.5" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "validated|implemented-but-unverified|historical/stale path|unclear|Local evidence|HPC / external proof|Why this grade" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- [x] **T02: Added late-phase matrix rows and split Phase 4 into the current Stage-1 / Stage-2 route versus the historical full-tropics reducer route.** — ## Description

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
  - Estimate: 35m
  - Files: .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md, CHANGELOG.md, docs/stashes/2026-03-31-022-phase36-gwd30-tile-reduce-handoff.md, docs/stashes/2026-04-01-011-phase361-gwd30-hotspot-trace-diagnostics.md, docs/stashes/2026-04-01-002-phase37-global-500m-handoff.md, docs/stashes/2026-04-01-004-phase37-hotspots-implementation.md, docs/stashes/2026-04-06-003-phase4-conversation-summary.md, docs/stashes/2026-04-06-005-phase4-stage2-pixel-stats-regional-integration.md
  - Verify: `rg -n "Phase 3.6|Phase 3.6.1|Phase 3.7|Phase 4 current Stage-1 / Stage-2 route|Phase 4 historical full-tropics reducer route" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "2026-03-31-022|2026-04-01-011|2026-04-01-002|2026-04-01-004|2026-04-06-003|2026-04-06-005|2026-04-06-008" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "historical/stale path|implemented-but-unverified|HPC / external proof" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- [x] **T03: Added loader and comparison-core module rows to the S02 evidence matrix.** — ## Description

Translate the phase evidence into module-family rows for the loader and comparison core so S02 classifies the actual implementation surfaces, not only the historical phase labels.

## Steps

1. Add `Module Matrix` rows for `loaders/classification`, `standardized loader`, `standardization & GWD30 staging`, `rough comparison`, and `fine-grained comparison`.
2. For each row, cite representative `src/WA/...` anchors plus the paired regression tests that show what is locally covered today, and keep the same `Grade`, `Local evidence`, `HPC / external proof`, and `Why this grade` columns used in the phase table.
3. Reuse the early/core phase matrix decisions instead of inventing a second rubric; if a module spans multiple phases, explain that cross-phase linkage in `Why this grade` rather than duplicating evidence prose elsewhere.

## Must-Haves

- [ ] Every loader/comparison-core row references concrete source and test file paths from the current worktree.
- [ ] The module rows reuse the exact D002 grade vocabulary and preserve the same local-vs-HPC proof split used in the phase table.

## Done when

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` contains the first block of `Module Matrix` rows covering the loader and comparison-core families.
  - Estimate: 35m
  - Files: .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md, src/WA/standardized_loader.py, src/WA/standardize.py, src/WA/comparison/rough_binary.py, src/WA/comparison/fine_grained.py, tests/test_standardized_loader.py, tests/test_standardize.py, tests/test_comparison/test_harmonize.py
  - Verify: `rg -n "^## Module Matrix$|loaders/classification|standardized loader|standardization & GWD30 staging|rough comparison|fine-grained comparison" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "src/WA/standardized_loader.py|src/WA/standardize.py|src/WA/comparison/rough_binary.py|src/WA/comparison/fine_grained.py|tests/test_standardized_loader.py|tests/test_standardize.py|tests/test_comparison/test_harmonize.py|tests/test_comparison/test_fine_grained.py" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- [x] **T04: Classified the remaining validation, analysis, and visualization surfaces in the S02 evidence matrix.** — ## Description

Finish the module matrix with the higher-level analysis and visualization surfaces, then make the open proof gaps explicit where local tests are not enough to claim end-to-end validation.

## Steps

1. Add `Module Matrix` rows for `validation/GEE references`, `Phase 2.6 regional metrics`, `Phase 3.6 global disagreement`, `Phase 3.7 hotspot/plotting`, `Phase 4 regional/trends`, and `visualization surfaces`.
2. Use the current source files plus representative test anchors to explain which parts are locally exercised today and which parts still depend on HPC reruns, external data, or delayed plotting/runtime confirmation.
3. Add `Requirement Coverage` and `Open Proof Gaps` sections that explicitly map R002 and R007 to the completed matrix rows and summarize the remaining remote/HPC-only evidence boundaries.

## Must-Haves

- [ ] The higher-level module rows point to concrete `src/WA/...` anchors and at least one representative verification surface where local tests exist.
- [ ] `Requirement Coverage` and `Open Proof Gaps` clearly separate “implemented locally” from “still needs external/HPC proof” for downstream slices.

## Done when

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` contains the remaining module families plus the `Requirement Coverage` and `Open Proof Gaps` sections.
  - Estimate: 40m
  - Files: .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md, src/WA/validation/s2_reference.py, src/WA/comparison/phase26.py, src/WA/comparison/phase36.py, src/WA/comparison/phase4_regional.py, src/WA/comparison/trends.py, src/WA/visualization/phase37.py, src/WA/visualization/phase4.py
  - Verify: `rg -n "validation/GEE references|Phase 2.6 regional metrics|Phase 3.6 global disagreement|Phase 3.7 hotspot/plotting|Phase 4 regional/trends|visualization surfaces|Requirement Coverage|Open Proof Gaps" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "src/WA/validation/s2_reference.py|src/WA/comparison/phase26.py|src/WA/comparison/phase36.py|src/WA/comparison/phase4_regional.py|src/WA/comparison/trends.py|src/WA/visualization/phase37.py|src/WA/visualization/phase4.py|tests/test_comparison/test_phase4_regional.py|tests/test_comparison/test_trends.py|tests/test_phase3_6_analysis.py" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- [x] **T05: Validated R002/R007 against the canonical S02 matrix and added the Chinese re-entry note for Phase 4 and the remaining HPC-only gaps.** — ## Description

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
  - Estimate: 25m
  - Files: .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md, .gsd/REQUIREMENTS.md, docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md, docs/stashes/2026-04-06-008-phase4-recall-entry.md
  - Verify: `test -s docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md`
`rg -n "R002|R007" .gsd/REQUIREMENTS.md`
`rg -n "S02-PHASE-MODULE-MATRIX.md|Verification|Open HPC Gaps|Stage 1|Stage 2" docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md`
