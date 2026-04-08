---
id: T02
parent: S01
milestone: M001
key_files:
  - .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md
  - .gsd/milestones/M001/slices/S01/S01-INVENTORY.md
  - docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Keep `S01-INVENTORY.md` as the frozen evidence artifact and move route interpretation into a separate drift appendix instead of recomputing the inventory snapshot.
  - Weight late changelog entries and terminal stash summaries above older active plans when current-route signals disagree.
duration: 
verification_result: passed
completed_at: 2026-04-06T20:07:01.752Z
blocker_discovered: false
---

# T02: Added the drift-boundary appendix and Chinese-friendly re-entry note, and cross-linked them from the frozen S01 inventory.

**Added the drift-boundary appendix and Chinese-friendly re-entry note, and cross-linked them from the frozen S01 inventory.**

## What Happened

Reviewed the latest high-signal Phase 4 plan, changelog entries, and stash summaries against the older planning/history documents already identified by research, then wrote `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` to separate `current-signal`, `historical` / `superseded`, and proof-boundary surfaces. Updated `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` with a minimal follow-up link so the T01 inventory remains the raw evidence freeze while later slices can find the interpretation layer. Wrote `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` as a compact Chinese-friendly operator note covering read order, canonical outputs, replay commands, verification pointers, open risks, and current HPC commands. Also captured one reusable repo rule in `.gsd/KNOWLEDGE.md`: newer changelog and terminal stash summaries can outweigh an older still-`active` plan when route drift is the question.

## Verification

Re-ran the carried-forward T01 inventory checks plus the new T02 appendix/re-entry-note checks. Verified that the frozen inventory still exists and retains its required section headings and command anchors, that the new drift appendix and re-entry note both exist, that the appendix contains the required section headings, that the inventory cross-links the appendix, and that the re-entry note includes `S01-INVENTORY.md`, `S01-DRIFT-BOUNDARIES.md`, `Verification Snapshot`, and `Open Risks`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -s .gsd/milestones/M001/slices/S01/S01-INVENTORY.md` | 0 | ✅ pass | 4ms |
| 2 | `rg -n '^## (Runtime Code Surface|Operational Script Surface|Verification Surface|Planning and History Surface|Dataset, TODO, and Config Surface|Git and Worktree State|Artifact Presence and Proof Boundaries|Command Appendix)$' .gsd/milestones/M001/slices/S01/S01-INVENTORY.md` | 0 | ✅ pass | 14ms |
| 3 | `rg -n 'python -m pytest --collect-only -q|git status --short --branch|results/|temp/' .gsd/milestones/M001/slices/S01/S01-INVENTORY.md` | 0 | ✅ pass | 5ms |
| 4 | `test -s .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md && test -s docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` | 0 | ✅ pass | 2ms |
| 5 | `rg -n '^## (Current Signals|Historical / Superseded Signals|Proof Boundaries|Handoff to S02 and S03)$' .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` | 0 | ✅ pass | 5ms |
| 6 | `rg -n 'S01-DRIFT-BOUNDARIES.md' .gsd/milestones/M001/slices/S01/S01-INVENTORY.md` | 0 | ✅ pass | 5ms |
| 7 | `rg -n 'S01-INVENTORY.md|S01-DRIFT-BOUNDARIES.md|Open Risks|Verification Snapshot' docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md` | 0 | ✅ pass | 5ms |

## Deviations

Added one extra `.gsd/KNOWLEDGE.md` note beyond the written task plan because the repo has a non-obvious route-drift rule: newer changelog + terminal stash summaries can partially supersede an older plan that is still marked `active`. Preserved the T01 inventory counts as a frozen snapshot and only added a cross-link rather than recomputing the inventory.

## Known Issues

`results/`, `temp/`, the older `.claude` memory path, and all `/lustre/...` dataset/output surfaces remain proof-boundary gaps from this GSD worktree. The appendix can classify those gaps, but it still cannot prove current HPC artifact existence.

## Files Created/Modified

- `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`
- `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md`
- `docs/stashes/2026-04-07-002-m001-s01-inventory-reentry.md`
- `.gsd/KNOWLEDGE.md`
