---
id: S01
parent: M001
milestone: M001
provides:
  - Canonical local surface inventory with replayable counts, representative anchors, and explicit absent-local / external-HPC proof boundaries.
  - Drift-boundary appendix separating current Phase 4 signals from historical/superseded references and unresolved proof gaps.
  - Compact re-entry note with verification snapshot, open risks, and the latest recorded Stage 1 / Stage 2 HPC commands.
requires:
  []
affects:
  - S02
  - S03
  - S05
key_files:
  - .gsd/milestones/M001/slices/S01/S01-INVENTORY.md
  - .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md
  - docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md
  - .gsd/KNOWLEDGE.md
  - .gsd/REQUIREMENTS.md
  - .gsd/DECISIONS.md
key_decisions:
  - Keep `S01-INVENTORY.md` as the frozen replayable fact base and place route interpretation in `S01-DRIFT-BOUNDARIES.md`.
  - Treat missing `results/`, `temp/`, and unreachable memory paths as absent-local proof boundaries rather than evidence of nonexistence.
  - Weight the latest changelog entries and late stash summaries above older still-`active` plans when route signals disagree.
patterns_established:
  - Freeze audit evidence with replayable commands inside the inventory so later slices can refresh facts without blind exploration.
  - Split audit deliverables into a raw-facts inventory and a separate interpretation appendix to avoid mixing stable evidence with route judgment.
  - Pair canonical `.gsd` artifacts with a compact Chinese-friendly stash note so operator recovery does not depend on rereading long history traces.
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M001/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-06T20:11:49.627Z
blocker_discovered: false
---

# S01: Canonical Surface Inventory

**Published the canonical local repository inventory, drift-boundary appendix, and re-entry note that freeze M001’s evidence surface for downstream audit slices.**

## What Happened

S01 turned the previously scattered repository state into three operator-facing artifacts. First, T01 wrote `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` as the raw evidence freeze, capturing replayable counts and representative anchors across `src/WA`, `scripts/`, `tests/`, `docs/plans`, `docs/stashes`, `docs/datasets`, `todos/`, `config/datasets.yaml`, and worktree state. The inventory records 56 Python source files under `src/WA`, 54 operational scripts, 71 test files with 418 collected tests, 20 plan files, 147 stash files, 9 dataset reference files, and 6 TODO files, while explicitly marking `results/`, `temp/`, the older `.claude` memory path, and `/lustre/...` data roots as absent-local or external/HPC-only proof boundaries. Second, T02 preserved that file as the frozen fact base and added `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` as a separate interpretation layer, classifying current Phase 4 signals, historical/superseded documents, and unresolved proof-boundary gaps without pretending to have fresh HPC proof. Third, the slice wrote `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` as a compact Chinese-friendly recovery note that tells the next operator what to read first, what was verified, what remains risky, and which Stage 1 / Stage 2 HPC commands now represent the latest recorded continuation path. Along the way, S01 also captured two reusable knowledge rules for later slices: the GSD worktree cannot assume the old `.claude` memory path is reachable, and recent changelog + stash evidence can outweigh an older still-`active` plan when route drift is the question. The slice deliberately stopped short of declaring the canonical route; it delivered the evidence surfaces S02 and S03 need so they can do that judgment on top of a stable fact base.

## Verification

Re-ran `python -m pytest --collect-only -q`, which successfully collected 418 tests with only the previously known NumPy binary-compatibility runtime warning during import bootstrap. Re-ran every slice-plan verification check: the inventory file exists and retains all required section headings; the inventory still contains the required command anchors and explicit `results/` / `temp/` proof-boundary references; the drift appendix and re-entry note both exist; the drift appendix contains the required section headings; the inventory cross-links the drift appendix; and the re-entry note contains `S01-INVENTORY.md`, `S01-DRIFT-BOUNDARIES.md`, `Verification Snapshot`, and `Open Risks`. All checks passed in the current worktree.

## Requirements Advanced

- R002 — Froze the surface map and evidence sources that S02 will convert into the evidence-graded phase and module state matrix.
- R003 — Separated current-signal and historical/superseded route references so S03 can decide the canonical continuation path on top of a stable evidence base.
- R007 — Documented absent-local versus external/HPC-only proof boundaries for ignored artifact trees, unreachable memory paths, and `/lustre/...` dataset roots.
- R008 — Created a compact Chinese-friendly re-entry note that points future sessions to canonical artifacts, verification commands, and current HPC command anchors.

## Requirements Validated

- R001 — `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` plus `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` now provide a canonical, replayable full-project inventory across code, scripts, tests, docs, TODOs, and proof boundaries; all slice verification checks passed, and `python -m pytest --collect-only -q` collected 418 tests successfully.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Added `.gsd/KNOWLEDGE.md` entries and the T01 freeze stash note beyond the minimum file list so later slices inherit the worktree memory-path boundary and route-drift weighting rules. The planned inventory/appendix/re-entry outputs and verification contract stayed intact.

## Known Limitations

S01 cannot prove the current existence or freshness of ignored local artifact trees (`results/`, `temp/`), the older `.claude` memory path, Stage-1 pixel-statistics outputs, or any `/lustre/...` dataset/staging roots from this worktree. It also does not yet declare the final canonical continuation route; that evidence-weighting judgment is intentionally deferred to S02/S03.

## Follow-ups

S02 should build the evidence-graded phase/module matrix directly on top of `S01-INVENTORY.md` and the proof-boundary rules frozen here. S03 should use `S01-DRIFT-BOUNDARIES.md`, the latest Phase 4 stashes, and `CHANGELOG.md` to finalize the canonical route and stale-route register. A later execution milestone should replay the recorded Stage 1 / Stage 2 commands on HPC to retire the remaining remote-proof gaps.

## Files Created/Modified

- `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` — Frozen canonical inventory of repository surfaces, counts, representative anchors, proof boundaries, and replayable commands.
- `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` — Interpretation appendix separating current signals, historical/superseded references, and unresolved proof-boundary gaps.
- `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` — Chinese-friendly recovery note with read order, verification snapshot, open risks, and latest recorded HPC commands.
- `.gsd/KNOWLEDGE.md` — Captured reusable worktree memory-path and route-drift weighting rules discovered during S01.
- `.gsd/REQUIREMENTS.md` — Marked R001 validated with S01 evidence and proof references.
- `.gsd/DECISIONS.md` — Recorded requirement-status and audit evidence-model decisions introduced by S01.
