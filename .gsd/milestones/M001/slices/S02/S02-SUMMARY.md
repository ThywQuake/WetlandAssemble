---
id: S02
parent: M001
milestone: M001
provides:
  - Canonical evidence-graded phase/module matrix with D002 grades and explicit `Local evidence` versus `HPC / external proof` columns.
  - An explicit Phase 4 route split between the current Stage-1 / Stage-2 regional chain and the historical full-tropics reducer path.
  - A compact Chinese-friendly re-entry note plus validated requirement evidence for R002 and R007.
requires:
  - slice: S01
    provides: Frozen inventory and drift-boundary appendix used as the fact base for grading.
affects:
  []
key_files:
  - .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
  - docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md
  - .gsd/REQUIREMENTS.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - CHANGELOG.md
key_decisions:
  - Keep one canonical S02 matrix artifact with shared D002 grades and per-row `Local evidence` / `HPC / external proof` fields.
  - Treat the 2026-04-06 Stage-1 / Stage-2 regional chain as the current Phase 4 route and the 2026-04-05 full-tropics reducer chain as a separate historical/stale path.
  - Grade module families by the phase that actually proves that implementation surface instead of auto-downgrading validated core modules because later continuation phases remain unverified.
  - Keep cross-phase visualization surfaces at `implemented-but-unverified` unless fresh end-to-end outputs and the current runtime path are proven together.
patterns_established:
  - Convert a frozen inventory into one reader-facing matrix instead of scattering grade judgments across many stash notes.
  - Preserve chronology inside the matrix when newer changelog/stash evidence supersedes an older still-present route.
  - Pair a canonical `.gsd` artifact with a compact Chinese-friendly stash note so later slices can recover context before drilling into the full matrix.
  - Close requirement validation with explicit `Requirement Coverage` and `Open Proof Gaps` sections rather than vague narrative claims.
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T04-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T05-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-06T21:35:30.658Z
blocker_discovered: false
---

# S02: Phase & Module State Matrix

**Published the canonical evidence-graded phase/module matrix, validated R002 and R007 against it, and left a compact re-entry note that separates local proof from HPC-only gaps.**

## What Happened

S02 turned S01's frozen inventory and drift-boundary appendix into the canonical evidence-graded state matrix for M001. T01 created `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`, restated the D002 grading contract, and classified the early/core phases from Phase 1 through Phase 3.5 under a uniform `Grade / Local evidence / HPC / external proof / Why this grade` schema. T02 extended the same matrix through Phase 3.6, Phase 3.6.1, Phase 3.7, and Phase 4, making chronology explicit by splitting the current 2026-04-06 Stage-1 / Stage-2 regional chain from the older 2026-04-05 full-tropics reducer route that later evidence demoted to `historical/stale path`.

T03 translated those phase judgments into concrete module-family rows for loaders and comparison cores, and T04 finished the higher-level validation, analysis, and visualization families. The matrix now covers loader/classification surfaces, standardized input paths, rough/fine comparison cores, GEE reference validation, Phase 2.6 metrics, Phase 3.6 disagreement analysis, Phase 3.7 hotspot/plotting, Phase 4 regional/trends, and shared visualization surfaces. It also closes with `Requirement Coverage` and `Open Proof Gaps`, so downstream readers can immediately see which surfaces are locally proven today and which ones still require real HPC or external proof.

T05 closed the slice by validating `R002` and `R007` against the finished matrix, writing `docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md` as the compact Chinese-friendly recovery note, and persisting the non-obvious grading rules into `.gsd/DECISIONS.md` and `.gsd/KNOWLEDGE.md`. The result is a single reader-facing artifact that prevents future slices from re-synthesizing status from scattered plans, changelog entries, and stash notes. No plan-invalidating blocker was discovered.

## Verification

Re-ran the full slice-plan verification bundle against the final matrix, requirements file, and re-entry note. All commands passed: the matrix exists; it contains `Grading Contract`, `Phase Matrix`, `Module Matrix`, `Requirement Coverage`, and `Open Proof Gaps`; it covers every required early/core and late-phase row; it carries the D002 vocabulary and required stash/changelog/source/test anchors; `.gsd/REQUIREMENTS.md` renders both `R002` and `R007` as validated against the matrix; and the compact re-entry note includes the canonical matrix path, `Verification`, `Open HPC Gaps`, and the `Stage 1` / `Stage 2` Phase 4 continuation commands.

Verification command bundle:
```bash
test -s .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n '^## (Grading Contract|Phase Matrix)$' .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n 'Phase 1|Phase 1.1|Phase 1.5|Phase 1.6|Phase 2|Phase 2.5|Phase 2.6|Phase 3|Phase 3.5' .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n 'validated|implemented-but-unverified|historical/stale path|unclear|Local evidence|HPC / external proof|Why this grade' .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n 'Phase 3.6|Phase 3.6.1|Phase 3.7|Phase 4 current Stage-1 / Stage-2 route|Phase 4 historical full-tropics reducer route' .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n '2026-03-31-022|2026-04-01-011|2026-04-01-002|2026-04-01-004|2026-04-06-003|2026-04-06-005|2026-04-06-008' .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n '^## Module Matrix$|loaders/classification|standardized loader|standardization & GWD30 staging|rough comparison|fine-grained comparison' .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n 'src/WA/standardized_loader.py|src/WA/standardize.py|src/WA/comparison/rough_binary.py|src/WA/comparison/fine_grained.py|tests/test_standardized_loader.py|tests/test_standardize.py|tests/test_comparison/test_harmonize.py|tests/test_comparison/test_fine_grained.py' .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n 'validation/GEE references|Phase 2.6 regional metrics|Phase 3.6 global disagreement|Phase 3.7 hotspot/plotting|Phase 4 regional/trends|visualization surfaces|Requirement Coverage|Open Proof Gaps' .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
rg -n 'src/WA/validation/s2_reference.py|src/WA/comparison/phase26.py|src/WA/comparison/phase36.py|src/WA/comparison/phase4_regional.py|src/WA/comparison/trends.py|src/WA/visualization/phase37.py|src/WA/visualization/phase4.py|tests/test_comparison/test_phase4_regional.py|tests/test_comparison/test_trends.py|tests/test_phase3_6_analysis.py' .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
test -s docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md
rg -n 'R002|R007' .gsd/REQUIREMENTS.md
rg -n 'S02-PHASE-MODULE-MATRIX.md|Verification|Open HPC Gaps|Stage 1|Stage 2' docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md
```

Because S02 only changed audit artifacts and requirement metadata, structural verification was the correct proof class for this slice.

## Requirements Advanced

- R003 — Made the current-vs-historical Phase 4 split explicit so S03 can start from the right continuation branch instead of re-deriving chronology from plans and stash history.
- R005 — Consolidated unresolved GEE/HPC boundaries into `Open Proof Gaps`, turning scattered uncertainty into one reusable risk handoff surface.
- R008 — Added the compact Chinese-friendly re-entry note that points future operators first to the canonical matrix, then to the remaining proof targets.

## Requirements Validated

- R002 — `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` restates the D002 grading contract and classifies all required phases and module families with concrete evidence anchors.
- R007 — The same matrix separates `Local evidence` from `HPC / external proof` for every phase/module row and closes with `Requirement Coverage` plus `Open Proof Gaps`.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

No plan-invalidating deviation was discovered. In addition to the matrix and re-entry note, S02 persisted reusable grading rules in `.gsd/DECISIONS.md` and `.gsd/KNOWLEDGE.md`, and T05 confirmed that requirement updates should be serialized when the rendered `.gsd/REQUIREMENTS.md` file is itself part of the verification surface.

## Known Limitations

S02 documents but does not retire the remaining remote proof gaps. Fresh GEE-backed truth-reference runs, a current Phase 3.6 global rerun on real staged GWD30 tiles, a fresh Phase 3.7 end-to-end hotspot/global rendering pass, and the recommended Phase 4 Stage-1 / Stage-2 HPC chain all remain external/HPC-only proof work. The slice also still inherits S01's absent-local boundary for ignored `results/` and `temp/` trees plus remote `/lustre/...` data roots.

## Follow-ups

- S03 should consume the Phase 4 current-vs-historical split and `Open Proof Gaps` sections first to build the route audit and risk register.
- S04 should derive the ordered continuation path from the matrix instead of replaying already-validated local surfaces.
- The concrete HPC proof commands still worth running are:

```bash
python scripts/build_phase4_gwd30_pixel_stats.py --year 2020 --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --aggregation monthly --worker-count 1 --no-skip
bash scripts/submit_phase4_gwd30_pixel_stats.sh --aggregation monthly --worker-count 1 --cpus 1 --time 480 --partition C064M0256G --no-skip
python scripts/run_phase4_regional.py --dataset-id gwd30 --region amazon --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --start-year 2013 --end-year 2022 --no-skip
```

## Files Created/Modified

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` — Canonical phase/module evidence matrix with D002 grades, phase rows, module rows, requirement coverage, and open proof gaps.
- `docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md` — Compact Chinese-friendly re-entry note pointing operators to the matrix, verification commands, Phase 4 route split, and remaining HPC-only gaps.
- `.gsd/REQUIREMENTS.md` — R002 and R007 now validate directly against the canonical S02 matrix.
- `.gsd/DECISIONS.md` — Recorded the module-family grading rule, visualization proof-boundary rule, and requirement-status decisions introduced by S02.
- `.gsd/KNOWLEDGE.md` — Captured reusable grading/proof-boundary rules and the serialized requirement-update gotcha for later slices.
- `CHANGELOG.md` — Added breadcrumbs for the finished matrix, late-phase split, module-family coverage, and re-entry note.
