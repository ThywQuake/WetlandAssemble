# S01 — Research

**Date:** 2026-04-07

## Summary

S01 directly owns **R001 (Full-project current-state inventory)** and supplies raw evidence for **R002 (Evidence-graded state matrix)** and **R008 (Fast operator recovery pack)**. The repository already has broad, non-trivial local surfaces: `src/WA` has **56** Python files, `scripts/` has **54** operational entrypoints, `tests/` has **71** files, `docs/plans/` has **20** plan docs, `docs/stashes/` has **147** stash docs, `docs/datasets/` has **9** dataset references, `todos/` has **6** markdown TODOs, and the current test suite collects **418** tests via `python -m pytest --collect-only -q`. The current audit worktree is clean on branch `milestone/M001`, at commit `a8680b9`, which is also the head of `refactor/loader-reference-grid-alignment`.

The key inventory surprise is not missing code; it is **surface drift**. Early plans and memory-restore docs describe Phase 3/4 as not started or only partially started, while current code, tests, changelog, and late stashes show substantial implemented work across **Phase 2.6, Phase 3.6, Phase 3.6.1, Phase 3.7, and Phase 4**. The inventory therefore cannot be a plain file listing. It needs explicit tags such as `current-signal`, `historical`, `superseded`, `external/HPC-only`, and `absent-local` so later slices can reason from evidence instead of from stale intent documents.

The second important finding is that several in-scope surfaces are **referenced but unavailable in this worktree**. `results/` and `temp/` do not exist locally here, and the external memory path cited by project docs (`../../.claude/projects/-Users-mac-Code-WA/memory`) is also unavailable from this audit worktree. Because `.gitignore` excludes `results/` and `temp/`, local absence is expected and must be recorded as a proof-boundary fact, not silently treated as “no artifacts ever existed.” No installed skill directly automates this slice; follow the project contract instead: do not modify `config/`, preserve verification status and open risks, and leave compact evidence that future slices can reuse.

## Recommendation

Treat S01 as a **document-and-evidence slice**, not a code-feature slice. Build one canonical inventory artifact from direct filesystem, git, and test-collection evidence. Group it by surface: runtime code, operational scripts, verification surface, planning/history surface, GSD state, TODO surface, branch/commit state, and explicitly absent/external artifact surfaces.

Do **not** try to fully judge route correctness inside S01. Instead, collect the evidence paths that later slices need:
- which files/modules exist now,
- which docs are explicitly superseded,
- which late stashes/changelog entries act as current-route signals,
- which proof surfaces are unavailable locally.

Execution should also follow the project rule that quick recovery matters: in addition to the canonical inventory, leave a compact, skim-friendly summary for downstream slices and future re-entry. The planner should therefore scope at least one task for the main inventory and one task for a compact drift/proof-boundary appendix rather than mixing everything into a single undifferentiated narrative.

## Implementation Landscape

### Key Files

- `.gsd/REQUIREMENTS.md` — S01 owns R001 and supports R002/R008; use it to decide what the inventory must cover.
- `.gsd/milestones/M001/M001-CONTEXT.md` and `.gsd/milestones/M001/M001-ROADMAP.md` — define the audit contract, especially that `results/`, `temp/`, docs, tests, stashes, and branch state are all part of the surface map.
- `.gsd/PROJECT.md` — already contains a compact project summary; useful as a seed but not yet a complete inventory.
- `src/WA/config.py` — central config loader; important because `config/` is in-scope as evidence but not editable.
- `src/WA/classification.py` — classification crosswalk layer; high-signal shared utility referenced by major comparison phases.
- `src/WA/loaders/registry.py` — shows supported loader types and the explicit out-of-scope `lstm_wetland` rule.
- `src/WA/loaders/gwd30.py` — largest loader surface; contains staging, sharding, transform, merge, and rough/fine loading paths. This is a persistent high-risk/current-route surface.
- `src/WA/standardize.py` — standardized pipeline hub and staged chunk/rebucket logic; critical for understanding cache/staging architecture.
- `src/WA/comparison/phase36.py` — largest Phase 3.6 implementation and a major route anchor for current-state grading.
- `src/WA/comparison/phase4_regional.py` — current Phase 4 regional orchestration, including legacy retained paths plus newer pixel-stat/tile-cache routes.
- `src/WA/comparison/trends.py` — trend analysis plus Phase 4 Stage-1 native pixel-statistics builder.
- `scripts/` — 54 operational entrypoints. Main families observed: `plot_` **12**, `run_` **11**, `build_` **4**, `hpc_probe_` **4**, plus 7 submit/shell scripts. High-signal current files include:
  - `scripts/build_phase4_gwd30_pixel_stats.py`
  - `scripts/run_phase4_regional.py`
  - `scripts/run_phase3_6_global_entropy.py`
  - `scripts/find_phase3_7_hotspots.py`
  - `scripts/plot_phase3_7_metrics.py`
  - `scripts/standardize_datasets.py`
  - `scripts/submit_phase4_gwd30_pixel_stats.sh`
  - `scripts/submit_phase4_gwd30_tropical_shards.sh`
- `tests/` — 71 files, **418** collected tests. Highest-signal test modules by size/current route relevance:
  - `tests/test_standardize.py`
  - `tests/test_loaders/test_gwd30.py`
  - `tests/test_phase3_6_analysis.py`
  - `tests/test_comparison/test_phase4_regional.py`
  - `tests/test_comparison/test_trends.py`
- `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md` — early canonical plan; explicitly supersedes the draft below.
- `docs/plans/2026-03-18-feat-dataset-loaders-plan.md` — retained but explicitly superseded; important stale-surface example.
- `docs/plans/2026-03-19-002-feat-phase2345-comparison-trends-manifests-plan.md` — historically important, but stale for current state because it still says Phase 3/4 are not started.
- `docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md` — late/current planning signal around the Phase 4 GWD30 route pivot.
- `docs/stashes/2026-03-22-001-phase2-closeout-rough-review-and-debug-summary.md` — strong terminal summary for Phase 2 baseline.
- `docs/stashes/2026-03-31-015-phase26-wrap-up.md` — terminal summary for Phase 2.6 baseline.
- `docs/stashes/2026-03-31-022-phase36-gwd30-tile-reduce-handoff.md` — terminal summary for Phase 3.6 route and proof boundary.
- `docs/stashes/2026-04-01-002-phase37-global-500m-handoff.md` — terminal summary for Phase 3.7 global plotting route.
- `docs/stashes/2026-04-06-003-phase4-conversation-summary.md` — strongest compact statement that old full-tropics Phase 4 reducer is no longer recommended.
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md` — compact re-entry note pointing to Phase 4 Stage 2 as the active entrypoint.
- `CHANGELOG.md` — best compact source for the latest current-route changes; recent entries heavily favor Phase 3.6/3.7/4 and the Phase 4 GWD30 pivot.
- `config/datasets.yaml` — inventory anchor for dataset count, year coverage, region catalog, and the out-of-scope `lstm_wetland` mismatch.
- `docs/datasets/` — 9 dataset reference files; pair with `config/datasets.yaml` for dataset-surface inventory.
- `.gitignore` — explains why `results/` and `temp/` can be absent locally even when heavily referenced.
- `sync.sh` — confirms the rsync/HPC workflow boundary.

### Build Order

1. **Freeze local facts first** — branch/commit, top-level tree, file counts by major surface, current test-collection count, and local presence/absence of `results/`, `temp/`, and external memory path. This is the hard local evidence base for R001.
2. **Map runtime + operational surfaces** — summarize `src/WA` and `scripts/` by module family and high-signal files. This gives S02 concrete anchors for later state grading.
3. **Map verification surface** — record `tests/` structure plus the current `418` collected tests. This prevents later slices from relying on stale pass-count claims alone.
4. **Map planning/history drift** — inventory `docs/plans`, `docs/stashes`, `CHANGELOG.md`, and the most important memory-restore-style stash files, with explicit `current-signal` vs `historical/superseded` tags. This unblocks S03.
5. **Append proof-boundary section** — explicitly list absent local artifact surfaces and external references that cannot be inspected here. This is necessary so S02/S03 do not overstate proof.
6. **Leave a compact appendix** — preserve the exact commands and counts used for inventory generation so future re-entry can refresh S01 cheaply.

### Verification Approach

Use direct, replayable commands rather than narrative inference:

- Filesystem inventory:
  - `find . -maxdepth 2 -mindepth 1 | sort`
  - `find src/WA -maxdepth 3 -type f | sort`
  - `find docs/plans docs/stashes docs/datasets todos -type f | sort`
- Git / state surface:
  - `git status --short --branch`
  - `git log --oneline --decorate -n 12`
  - `git branch --all --list`
- Verification surface:
  - `python -m pytest --collect-only -q` (current evidence: **418 tests collected**)
- Optional code hotspot confirmation for later slices:
  - LSP symbol scans on `src/WA/loaders/gwd30.py`, `src/WA/standardize.py`, `src/WA/comparison/phase36.py`, `src/WA/comparison/phase4_regional.py`, `src/WA/comparison/trends.py`

A successful S01 implementation should end with one markdown inventory that cites these commands/results and clearly marks each surface as `present-local`, `absent-local`, `historical`, `superseded`, or `external/HPC-only`.

## Constraints

- `config/` is read-only for this slice; inventory may cite `config/*.yaml` but must not modify them.
- HPC workflow is rsync-based (`sync.sh`), so git state and HPC state are separate surfaces.
- `results/` and `temp/` are gitignored; local absence in this worktree is expected and must be recorded explicitly.
- The audit must not promote stash claims, changelog text, or test names into HPC proof.
- Project instructions require preserving verification status and open risks in compact form; the inventory should therefore capture commands run and unresolved proof gaps explicitly.

## Common Pitfalls

- **Treating retained plan docs as canonical** — several early plans are explicitly superseded or contradicted by later code/stashes; inventory must tag them, not flatten them.
- **Treating missing local artifact dirs as “no artifacts exist”** — here they are absent because of worktree / ignore boundaries, not because the project never produced them.
- **Treating external memory references as readable evidence** — the cited `../../.claude/.../memory` path is unavailable from this worktree and should be recorded as a blocker/gap.
- **Over-exploring phase internals during S01** — S01 needs surface coverage and evidence anchors, not deep algorithm audits of every phase.

## Open Risks

- The current worktree cannot inspect `results/`, `temp/`, or the external memory directory, so the S01 inventory can only record them as referenced-but-unavailable local surfaces.
- Phase 4 still has multiple retained GWD30 routes in code/docs (`_staging` restore, full-tropics cache, native pixel stats, Stage 2 regional integration). S01 should collect all evidence paths now and defer route judgment to S03.
- Stash history is dense enough that exhaustive chronological summarization will waste planner context; use terminal summaries and explicit drift examples first, then drill down only when contradictions appear.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| xarray | `tondevrel/scientific-agent-skills@xarray` | available via `npx skills add tondevrel/scientific-agent-skills@xarray` |
| rasterio | none found | no directly relevant skill found via `npx skills find "rasterio"` |