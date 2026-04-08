---
estimated_steps: 11
estimated_files: 8
skills_used: []
---

# T04: Classify validation, analysis, and visualization surfaces

## Description

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

## Inputs

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- `src/WA/validation/s2_reference.py`
- `src/WA/comparison/phase26.py`
- `src/WA/comparison/phase36.py`
- `src/WA/comparison/phase4_regional.py`
- `src/WA/comparison/trends.py`
- `src/WA/visualization/phase37.py`
- `src/WA/visualization/phase4.py`
- `tests/test_comparison/test_phase4_regional.py`
- `tests/test_comparison/test_trends.py`
- `tests/test_phase3_6_analysis.py`
- `docs/stashes/2026-04-01-004-phase37-hotspots-implementation.md`

## Expected Output

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`

## Verification

`rg -n "validation/GEE references|Phase 2.6 regional metrics|Phase 3.6 global disagreement|Phase 3.7 hotspot/plotting|Phase 4 regional/trends|visualization surfaces|Requirement Coverage|Open Proof Gaps" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
`rg -n "src/WA/validation/s2_reference.py|src/WA/comparison/phase26.py|src/WA/comparison/phase36.py|src/WA/comparison/phase4_regional.py|src/WA/comparison/trends.py|src/WA/visualization/phase37.py|src/WA/visualization/phase4.py|tests/test_comparison/test_phase4_regional.py|tests/test_comparison/test_trends.py|tests/test_phase3_6_analysis.py" .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
