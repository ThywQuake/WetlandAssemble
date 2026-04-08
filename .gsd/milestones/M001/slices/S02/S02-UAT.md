# S02: Phase & Module State Matrix — UAT

**Milestone:** M001
**Written:** 2026-04-06T21:35:30.659Z

# S02: Phase & Module State Matrix — UAT

**Milestone:** M001  
**Written:** 2026-04-07

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S02 shipped a canonical audit matrix, requirement validation evidence, and a recovery note rather than new runtime code paths. Correctness therefore depends on section completeness, anchor integrity, and proof-boundary clarity.

## Preconditions

- Work from `/Users/mac/Code/WA/.gsd/worktrees/M001`.
- `rg` is available in the environment.
- The slice outputs already exist on disk.

## Smoke Test

Run:

```bash
test -s .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md \
  && test -s docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md \
  && rg -n '^## (Grading Contract|Phase Matrix|Module Matrix|Requirement Coverage|Open Proof Gaps)$' .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
```

**Expected:** the canonical matrix and the compact re-entry note both exist, and the matrix exposes all five required top-level sections.

## Test Cases

### 1. Grading contract and early/core phase rows are complete

1. Open `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`.
2. Confirm `## Grading Contract` restates all four D002 grades exactly: `validated`, `implemented-but-unverified`, `historical/stale path`, and `unclear`.
3. Confirm the contract cross-links `S01-INVENTORY.md` and `S01-DRIFT-BOUNDARIES.md` and explicitly separates `Local evidence` from `HPC / external proof`.
4. Confirm the `Phase Matrix` contains rows for `Phase 1`, `Phase 1.1`, `Phase 1.5`, `Phase 1.6`, `Phase 2`, `Phase 2.5`, `Phase 2.6`, `Phase 3`, and `Phase 3.5`.
5. Confirm each row uses the same four evidence columns and does not collapse local proof with HPC-only proof.
6. **Expected:** the early/core phases are fully classified under the shared grading contract, and the proof split is reader-visible in every row.

### 2. Late-phase rows preserve chronology and the Phase 4 route split

1. In the same matrix, locate the rows for `Phase 3.6`, `Phase 3.6.1`, `Phase 3.7`, `Phase 4 current Stage-1 / Stage-2 route`, and `Phase 4 historical full-tropics reducer route`.
2. Confirm the late-phase rows cite the expected stash/changelog anchors: `2026-03-31-022`, `2026-04-01-011`, `2026-04-01-002`, `2026-04-01-004`, `2026-04-06-003`, `2026-04-06-005`, and `2026-04-06-008`.
3. Confirm the current Phase 4 row explicitly describes the Stage-1 / Stage-2 regional chain as the live continuation path.
4. Confirm the historical Phase 4 row is explicitly marked `historical/stale path` and names the older full-tropics reducer route as the superseded branch.
5. **Expected:** the matrix makes the current-vs-historical Phase 4 split obvious without requiring the reader to re-open old plans or stash history.

### 3. Loader and comparison-core module rows point to concrete implementation anchors

1. Locate `## Module Matrix` in `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`.
2. Confirm the matrix contains rows for `loaders/classification`, `standardized loader`, `standardization & GWD30 staging`, `rough comparison`, and `fine-grained comparison`.
3. Confirm those rows cite current-worktree implementation and regression-test anchors including:
   - `src/WA/standardized_loader.py`
   - `src/WA/standardize.py`
   - `src/WA/comparison/rough_binary.py`
   - `src/WA/comparison/fine_grained.py`
   - `tests/test_standardized_loader.py`
   - `tests/test_standardize.py`
   - `tests/test_comparison/test_harmonize.py`
   - `tests/test_comparison/test_fine_grained.py`
4. Confirm `rough comparison` and `fine-grained comparison` remain `validated`, while standardized-input families remain below `validated` where HPC proof is still missing.
5. **Expected:** the module block classifies real code surfaces rather than only phase labels, while preserving the same D002 grading rules used in the phase table.

### 4. Higher-level validation, analysis, and visualization families expose remaining proof gaps

1. Confirm the module matrix also contains rows for `validation/GEE references`, `Phase 2.6 regional metrics`, `Phase 3.6 global disagreement`, `Phase 3.7 hotspot/plotting`, `Phase 4 regional/trends`, and `visualization surfaces`.
2. Confirm those rows cite the expected source/test anchors, including:
   - `src/WA/validation/s2_reference.py`
   - `src/WA/comparison/phase26.py`
   - `src/WA/comparison/phase36.py`
   - `src/WA/comparison/phase4_regional.py`
   - `src/WA/comparison/trends.py`
   - `src/WA/visualization/phase37.py`
   - `src/WA/visualization/phase4.py`
   - `tests/test_phase3_6_analysis.py`
   - `tests/test_comparison/test_phase4_regional.py`
   - `tests/test_comparison/test_trends.py`
3. Confirm the document ends with `## Requirement Coverage` and `## Open Proof Gaps`.
4. Confirm `Open Proof Gaps` explicitly names live GEE/auth boundaries, the missing fresh Phase 3.6 rerun, the unresolved Phase 3.7 end-to-end regeneration, and the still-unproven Phase 4 Stage-1 / Stage-2 HPC chain.
5. **Expected:** a downstream reader can tell which high-level analysis surfaces are locally implemented today and which ones still require external or HPC confirmation.

### 5. Requirements and recovery note point back to the canonical matrix

1. Open `.gsd/REQUIREMENTS.md`.
2. Confirm `R002` and `R007` are both marked `validated` and cite `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` as their validation evidence.
3. Open `docs/stashes/2026-04-07-003-m001-s02-phase-matrix-reentry.md`.
4. Confirm it names the canonical matrix path, includes a `Verification` section, explains `Open HPC Gaps`, and explicitly preserves the `Stage 1` / `Stage 2` Phase 4 continuation commands.
5. Confirm the note instructs S03/S05 to recover from the compact note first and then drill into the full matrix.
6. **Expected:** both requirement validation and operator recovery now flow through the same canonical S02 artifact instead of diverging into separate informal explanations.

## Edge Cases

- A row with strong local plotting tests must still remain `implemented-but-unverified` if the final science-facing output route depends on fresh HPC outputs or live external imagery.
- A module family that spans several phases should not be downgraded automatically just because a later presentation phase remains open; grade it against the phase that actually proves that module surface.
- The current Phase 4 route and the historical full-tropics reducer route must remain separate rows. If they are merged, route history becomes ambiguous again.
- The Stage-1 / Stage-2 commands in the recovery note are continuation/proof targets for HPC; they are not local pass criteria for this documentation slice.

