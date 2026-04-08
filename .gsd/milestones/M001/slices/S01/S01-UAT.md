# S01: Canonical Surface Inventory — UAT

**Milestone:** M001
**Written:** 2026-04-06T20:11:49.627Z

# S01: Canonical Surface Inventory — UAT

**Milestone:** M001  
**Written:** 2026-04-07

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01 shipped audit artifacts and recovery notes rather than a runtime service, so correctness depends on artifact completeness, replayable commands, and cross-link integrity.

## Preconditions

- Work from `/Users/mac/Code/WA/.gsd/worktrees/M001`.
- `python`, `pytest`, and `rg` are available in the environment.
- The S01 task outputs exist on disk.

## Smoke Test

Run:

```bash
test -s .gsd/milestones/M001/slices/S01/S01-INVENTORY.md \
  && test -s .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md \
  && test -s docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md
```

**Expected:** all three canonical S01 artifacts exist and are non-empty.

## Test Cases

### 1. Inventory covers all required repository surfaces

1. Open `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md`.
2. Confirm it contains `Runtime Code Surface`, `Operational Script Surface`, `Verification Surface`, `Planning and History Surface`, `Dataset, TODO, and Config Surface`, `Git and Worktree State`, `Artifact Presence and Proof Boundaries`, and `Command Appendix`.
3. Confirm the snapshot includes counts for `src/WA`, `scripts/`, `tests/`, `docs/plans/`, `docs/stashes/`, `docs/datasets/`, and `todos/`.
4. Confirm the file explicitly marks `results/`, `temp/`, and the older `.claude` memory path as absent-local proof boundaries instead of silently ignoring them.
5. Confirm the command appendix includes replayable enumeration/count commands plus `python -m pytest --collect-only -q`.
6. **Expected:** the inventory is a self-contained, replayable full-project surface map with explicit proof-boundary labeling.

### 2. Drift appendix separates current signals from stale history

1. Open `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`.
2. Confirm it contains `Current Signals`, `Historical / Superseded Signals`, `Proof Boundaries`, and `Handoff to S02 and S03`.
3. Verify the current-signal table includes the latest 2026-04-05 / 2026-04-06 changelog and Phase 4 stash files.
4. Verify older March plans/stashes are explicitly marked historical or superseded instead of being flattened into the current route.
5. Verify `results/`, `temp/`, `.claude` memory, `/lustre/...` paths, and Stage-1 pixel-statistics artifacts are called out as proof-boundary gaps.
6. **Expected:** the appendix gives downstream slices a reliable way to distinguish fresh route signals from retained history and unresolved external-state claims.

### 3. Re-entry note is sufficient for fast operator recovery

1. Open `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md`.
2. Confirm the note points first to `S01-INVENTORY.md` and `S01-DRIFT-BOUNDARIES.md`.
3. Confirm it contains `Verification Snapshot`, `Open Risks`, and the latest recorded Stage 1 / Stage 2 HPC commands.
4. Follow the documented read order and confirm it prioritizes the latest Phase 4 recall/conversation stashes plus `CHANGELOG.md`.
5. **Expected:** a future operator can recover context and continue the audit without rescanning the repository from scratch.

### 4. Verification appendix still replays in the current worktree

1. Run `python -m pytest --collect-only -q`.
2. Run the `rg` checks from the S01 plan against `S01-INVENTORY.md`, `S01-DRIFT-BOUNDARIES.md`, and the re-entry note.
3. Confirm all commands exit successfully.
4. **Expected:** the frozen inventory, drift appendix, and recovery note remain internally consistent and reproducible.

## Edge Cases

- Missing `results/` and `temp/` directories must be treated as proof-boundary facts, not as evidence that prior outputs never existed.
- The older `../../.claude/projects/-Users-mac-Code-WA/memory` path may be unavailable inside a GSD worktree; the audit should fall back to locally present evidence surfaces.
- A plan file can remain marked `active` while newer changelog and stash entries partially supersede its route guidance; later slices must reweight evidence rather than trusting plan status alone.

