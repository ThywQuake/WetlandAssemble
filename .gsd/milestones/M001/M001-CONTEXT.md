# M001: Current-State Audit and Recovery Control Plane

**Gathered:** 2026-04-07
**Status:** Ready for planning

## Project Description

This milestone exists because the repository is already a “很凌乱的工作空间” with “很多工作痕迹”. The immediate need is not new feature work, but to “弄清楚已经做了什么和将要做什么”, and to do that as a standalone milestone with thorough analysis. The project already contains substantial code, tests, scripts, results, plans, stashes, and memory files; what is missing is one authoritative, evidence-backed current-state view.

## Why This Milestone

Further implementation would be low-trust without first reconstructing the current control plane. Multiple phases appear implemented, recent route pivots exist, old routes still remain in the repo, and local evidence is not the same thing as real HPC proof. M001 solves that by producing a repository-wide audit that separates what is real, what is stale, what is only locally supported, and where the next executable route starts.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Open one canonical audit and see what has already been done, what is still current, and what remains next across the whole repository.
- Resume work from a concrete recommended route without re-reading broad stash history or accidentally following stale scripts.

### Entry point / environment

- Entry point: repository audit artifacts produced by M001, backed by direct reads of code, tests, scripts, plans, stashes, results, and git state
- Environment: local development workspace, with remote HPC state treated as an external proof surface rather than assumed local fact
- Live dependencies involved: PKU HPC result/state references, standardized data layout conventions, Earth Engine-related download/probe surfaces as referenced repository integration points

## Completion Class

- Contract complete means: the inventory, evidence-graded state matrix, route audit, risk register, and next-step execution map all exist and cite concrete repository evidence.
- Integration complete means: code, docs, tests, scripts, stashes, results, and branch state have been reconciled into one consistent current-state picture with a recommended mainline.
- Operational complete means: local proof and HPC-only proof are explicitly separated, and no remote completion is implied without evidence.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- A fresh re-entry can identify the current recommended route and the known stale/non-recommended routes without replaying the full historical discussion trail.
- A fresh re-entry can inspect each major phase or module and see its status grade together with the evidence behind that grade.
- The milestone does not blur local tests/stashes/results with remote HPC proof where those are materially different.

## Risks and Unknowns

- Local evidence may overstate runtime truth — recent stash notes and tests can diverge from actual HPC state, especially after route pivots.
- Phase 4 has accumulated multiple GWD30 paths — old reducers, newer pixel-stat builders, and route pivots can all look current if not explicitly graded.
- Result folders and temp artifacts may mix outputs from older routes, old branches, or partial reruns — provenance is not automatically obvious.
- Historic phase summaries may be directionally correct but still lag the current branch’s real state.

## Existing Codebase / Prior Art

- `src/WA/` — main code surface with `loaders`, `comparison`, `validation`, `visualization`, and `utils`
- `tests/` — broad verification surface spanning loaders, comparisons, validation flows, visualization, scripts, and Phase 4 routes
- `docs/plans/` and `docs/stashes/` — prior intent, implementation summaries, pivots, and handoff history across phases
- `../../.claude/projects/-Users-mac-Code-WA/memory/` — restored state summaries, project overview, and prior phase-status claims
- `results/` and `temp/` — artifact surfaces that may confirm or contradict written claims

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R001 — Builds the full-project current-state inventory.
- R002 — Produces the evidence-graded phase/module state matrix.
- R003 — Identifies the canonical route to continue from.
- R004 — Names stale or misleading routes explicitly.
- R005 — Records open risks and unresolved proof gaps.
- R006 — Ends with a concrete next-step execution map.
- R007 — Separates local proof from HPC proof.
- R008 — Leaves behind a compact recovery pack for future re-entry.

## Scope

### In Scope

- Full-project average scan across code, tests, scripts, docs, plans, stashes, results, temp surfaces, and TODO traces
- Evidence grading of major phases, modules, and workflows
- Canonical-route identification, stale-route audit, and risk register
- Concrete next-step execution map for the next milestone/session
- Compact operator-facing recovery artifacts

### Out of Scope / Non-Goals

- Continuing scientific feature implementation, trend-analysis expansion, or new analysis modules during M001
- Large-scale repository cleanup, broad refactors, or restructuring while the audit is being established
- Declaring HPC completion where only local evidence exists

## Technical Constraints

- `config/` must not be modified without approval.
- HPC workflow is rsync-based, not git-based; the user syncs code manually.
- HPC commands should use `--no-skip`, not `--skip-existing`.
- Errors and cache reuse must remain visible rather than silently suppressed.
- Default target year is 2016 unless a concrete reason overrides it.
- GWD30 handling and WAD2M return-shape rules remain project-level invariants and must be preserved in the audit.

## Integration Points

- PKU HPC standardized data/results trees — many workflow claims ultimately depend on these remote artifacts
- `src/WA` runtime modules — the code surface being audited for current route and state
- `docs/plans`, `docs/stashes`, and memory files — intent and execution evidence used to reconstruct status
- `results/` and `temp/` outputs — artifact surfaces used to compare claimed vs visible completion
- Git branch/worktree status — current local integration surface

## Open Questions

- Which locally claimed completions still hold on real HPC state after the latest route pivots? — likely deferred to the first follow-on execution milestone.
- Which retained scripts should later be marked stale, frozen, or removed? — M001 should identify candidates, not perform cleanup.
- After the audit, should continuation start directly from the currently recommended Phase 4 route or reopen an older unresolved proof gap first? — M001 must answer this with evidence.
