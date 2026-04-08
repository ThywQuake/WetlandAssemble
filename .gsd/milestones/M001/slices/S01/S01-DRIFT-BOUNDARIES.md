# S01 Drift Boundaries

**Generated:** 2026-04-07  
**Scope:** Separate current-route signals, historical/superseded references, and proof-boundary gaps for the local M001 audit worktree.  
**Interpretation rule:** This appendix weights evidence already frozen in `S01-INVENTORY.md`; it does **not** claim fresh HPC proof or override direct runtime verification.

## Current Signals

These are the strongest local signals for present-day re-entry and route judgment.

| Surface | Tag | Why it currently matters | Boundary note |
|---|---|---|---|
| `CHANGELOG.md` entries dated `2026-04-06` | `current-signal` | Latest chronological local record says the recommended Phase 4 path moved away from the old full-tropics reducer/cache route and toward Stage-1 native pixel-statistics plus Stage-2 regional integration. | Proves the repository history narrative, not that remote HPC outputs still exist. |
| `docs/stashes/2026-04-06-003-phase4-conversation-summary.md` | `current-signal` | Explicitly states the old full-tropics reducer remains an HPC OOM risk and is no longer the recommended route. | Summary note only; still needs local/HPC confirmation when consuming artifacts. |
| `docs/stashes/2026-04-06-008-phase4-recall-entry.md` | `current-signal` | Gives the clearest operator-facing re-entry point: current phase is Phase 4, active subphase is Stage 2 regional integration, and the recommended commands target Stage 1 + Stage 2 rather than the old reducer. | Commands are documented, but this worktree does not prove their remote outputs. |
| `docs/stashes/2026-04-06-005-phase4-stage2-pixel-stats-regional-integration.md` | `current-signal` | Records the implemented switch from `_staging` restoration to Stage-1 pixel-statistics tile consumption in regional `gwd30` analysis. | Local implementation summary; Stage-1 output presence remains outside local proof. |
| `docs/stashes/2026-04-06-007-phase4-berkeley-mask-bbox-oom-fix.md` | `current-signal` | Shows the current Stage-2 path was still being actively repaired on 2026-04-06, including the latest documented regional-run retry command. | Fix summary is local evidence; successful HPC rerun is not proven here. |
| `docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md` | `current-signal` | Latest plan document explaining the Phase 4.1 pivot away from ad hoc region-specific staging and toward canonical staged inputs. | Treat as problem statement + design intent. Parts of its exact restore-only prescription were overtaken by 2026-04-06 implementation/stash evidence. |
| `CHANGELOG.md` entries dated `2026-04-05` about Stage-1 builder and Berkeley-valid-mask semantics | `current-signal` | These are still part of the active route because later 2026-04-06 notes build directly on them. | Read together with 2026-04-06 entries, not in isolation. |

## Historical / Superseded Signals

These references still matter as background or delivered-history evidence, but they should not be treated as the current route by default.

| Surface | Tag | Why it is not the primary current route signal | Residual value |
|---|---|---|---|
| `docs/plans/2026-03-18-feat-dataset-loaders-plan.md` | `superseded` | Explicitly superseded by `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`. | Useful only for early loader-foundation intent. |
| `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md` | `historical` | Early canonical plan for loader/comparison/truth workflow, but later code, tests, changelog, and stash history show substantial implementation beyond its “future work” framing. | Still authoritative for long-lived semantic decisions and dataset-mapping rationale. |
| `docs/plans/2026-03-19-002-feat-phase2345-comparison-trends-manifests-plan.md` | `historical` | Its phase-status table says Phase 3/4/5 were not started, which is contradicted by current local code/tests/changelog/stashes. | Useful as a design-history document and migration map from the predecessor project. |
| `docs/stashes/2026-03-22-002-memory-restore-summary.md` | `historical` | Its “next step = Phase 3” guidance is stale relative to the current Phase 4 evidence surface. It also assumes the older `.claude` memory path is readable. | Good example of why memory-restore notes need reweighting inside GSD worktrees. |
| `docs/stashes/2026-03-31-022-phase36-gwd30-tile-reduce-handoff.md` | `historical` | Describes a delivered Phase 3.6 handoff, not the current operator entry point. | Strong proof of what Phase 3.6 introduced and which HPC commands were once relevant. |
| `docs/stashes/2026-04-01-002-phase37-global-500m-handoff.md` | `historical` | Describes a delivered Phase 3.7 plotting state, not the active Phase 4 route. | Useful when later slices need Phase 3.7 output context or plotting provenance. |
| `CHANGELOG.md` entries dated `2026-04-05` about the full-tropics cache / sharded reducer / `submit_phase4_gwd30_tropical_shards.sh` route | `historical-route` | Later 2026-04-06 changelog and stash summaries say this route is retained but no longer recommended. | Useful as evidence of the route that existed before the Stage-1/Stage-2 pivot. |

## Proof Boundaries

These are the main places where the local worktree can describe a surface but cannot prove the underlying remote/runtime state.

| Boundary | Local fact we can prove | What remains unproven here |
|---|---|---|
| `results/` | `results/` is `absent-local` in this worktree, and `.gitignore` excludes it. | Whether `results/phase4/*`, `results/phase3.6/*`, or other output trees exist or are current on the repo root or HPC. |
| `temp/` | `temp/` is `absent-local`, and `.gitignore` excludes it. | Any historical temp artifacts, probe JSONs, or scratch outputs referenced by older notes. |
| `../../.claude/projects/-Users-mac-Code-WA/memory` | The path is `absent-local` from this GSD worktree. | The actual contents of older memory files cited by non-GSD recovery notes. |
| `/lustre/...` dataset and staging roots from `config/datasets.yaml` | The config names those paths, so the repo expects HPC-hosted data/staging roots. | The current contents, completeness, freshness, and accessibility of those HPC directories. |
| Stage-1 pixel-statistics tiles and manifests | Local notes/changelog repeatedly reference `results/phase4/pixel_stats/...` and Stage-1 tile manifests. | Whether those artifacts currently exist, are complete, or match the documented commands on HPC. |
| Historical verification claims in stashes | Stashes preserve earlier `pytest`, `ruff`, and HPC command outcomes as part of project history. | Whether those checks still pass now without re-running them in the present environment. |

Additional interpretation rules:

- Treat stash files and changelog entries as **evidence of what the team recorded**, not direct proof that external artifacts still exist.
- Treat local code/tests/docs/git state as **present-local proof**, because they are directly inspectable here.
- Treat any claim about HPC data, staged tiles, or ignored output trees as **external/HPC-only** or `absent-local` until refreshed by direct commands in the right environment.

## Handoff to S02 and S03

1. Use `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` as the raw local surface map and replayable command source.
2. Use this appendix to weight route evidence before making any canonical-state judgment.
3. For current-route re-entry, read in this order:
   1. `docs/stashes/2026-04-06-008-phase4-recall-entry.md`
   2. `docs/stashes/2026-04-06-003-phase4-conversation-summary.md`
   3. `CHANGELOG.md` entries from `2026-04-05` and `2026-04-06`
   4. `docs/stashes/2026-04-06-005-phase4-stage2-pixel-stats-regional-integration.md`
   5. `docs/stashes/2026-04-06-007-phase4-berkeley-mask-bbox-oom-fix.md`
   6. `docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md`
4. Use older plans/stashes only for semantic background, migration history, or proofs of already-delivered older phases.
5. Do **not** treat `results/`, `temp/`, `.claude` memory, or `/lustre/...` content as disproven just because they are missing here; classify them as proof-boundary gaps.
6. Before claiming anything is fresh, replay the relevant commands from the `Command Appendix` in `S01-INVENTORY.md` and, for HPC-only claims, run the documented HPC commands in the appropriate environment.
