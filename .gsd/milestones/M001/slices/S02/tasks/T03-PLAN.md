---
estimated_steps: 11
estimated_files: 8
skills_used: []
---

# T03: Classify loader and comparison-core module families

## Description

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

## Inputs

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- `src/WA/standardized_loader.py`
- `src/WA/standardize.py`
- `src/WA/comparison/rough_binary.py`
- `src/WA/comparison/fine_grained.py`
- `tests/test_standardized_loader.py`
- `tests/test_standardize.py`
- `tests/test_comparison/test_harmonize.py`
- `tests/test_comparison/test_fine_grained.py`

## Expected Output

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`

## Verification

`rg -n "^## Module Matrix$|loaders/classification|standardized loader|standardization & GWD30 staging|rough comparison|fine-grained comparison" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "src/WA/standardized_loader.py|src/WA/standardize.py|src/WA/comparison/rough_binary.py|src/WA/comparison/fine_grained.py|tests/test_standardized_loader.py|tests/test_standardize.py|tests/test_comparison/test_harmonize.py|tests/test_comparison/test_fine_grained.py" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
