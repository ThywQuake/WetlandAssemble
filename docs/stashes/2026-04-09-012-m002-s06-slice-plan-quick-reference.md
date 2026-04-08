# M002 S06 Slice Plan Quick Reference

**Date:** 2026-04-09
**Branch:** main
**Status:** Planned S06 via `gsd_plan_slice`; added a derived-pack/strict-proof architecture decision.

---

## Key Changes

| File | Change |
|------|--------|
| `.gsd/milestones/M002/slices/S06/S06-PLAN.md` | Rewrote the slice plan with must-haves, threat surface, requirement impact, proof level, verification, diagnostics, and 3 executable tasks. |
| `.gsd/milestones/M002/slices/S06/tasks/T01-PLAN.md` | Added pack-safe reload-helper task and set `skills_used: [stash]`. |
| `.gsd/milestones/M002/slices/S06/tasks/T02-PLAN.md` | Added derived paper-pack module/CLI task and set `skills_used: [stash]`. |
| `.gsd/milestones/M002/slices/S06/tasks/T03-PLAN.md` | Added strict readiness/ledger proof task, HPC handoff expectations, and set `skills_used: [stash, sync-hpc]`. |
| `.gsd/DECISIONS.md` | Added D048: keep paper outputs in a derived pack root and require readiness + ledger before strict completion claims. |

## Verification

- `gsd_plan_slice`: planned successfully for `M002/S06`
- Plan self-audit: completed manually against requirement coverage, task dependencies, file-path inputs/outputs, and slice completion semantics
- Code tests: not run (planning-only change)

## Open Risks / TODOs

- Local worktree still lacks real ten-region science outputs; S06 implementation must treat HPC materialization as a prerequisite for final strict proof.
- The actual pack module/CLI and tests do not exist yet; T01-T03 are still to be executed.
- Final milestone proof depends on the explicit HPC ladder using `--no-skip`, not local smoke artifacts.

## Next Steps

1. Execute `M002/S06/T01` to promote public percentage/trend-agreement reload helpers.
2. Execute `M002/S06/T02` to build `src/WA/visualization/phase4_pack.py` and `scripts/run_phase4_evidence_pack.py`.
3. Execute `M002/S06/T03` to add strict readiness/ledger proof mode and hand off the exact HPC rerun commands.
