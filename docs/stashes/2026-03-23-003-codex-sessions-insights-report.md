# Codex Sessions Insights Report

**Date:** 2026-03-23
**Source:** `/Users/mac/.codex/sessions`
**Snapshot Rule:** excludes the current in-progress Codex session `019d1a27-3574-7142-8556-d7aa27b5f899`

## Scope

- Global snapshot: all historical Codex sessions captured in March 2026
- Primary deep dive: WA project sessions only (`/Users/mac/Code/WA`)
- Comparison lens: wetland lineage (`WA` + legacy `Wetland_Assemble`)
- Output pair: this Markdown report + machine-readable JSON sidecar

## Executive Summary

- Historical Codex snapshot contains **34** sessions across three projects: `WA` `14`, `Lightning` `15`, `Wetland_Assemble` `5`.
- WA historical line contains **14** sessions, of which **11** are substantive and **3** are minimal / interrupted.
- WA branch evolution is phase-shaped rather than ad hoc: `feat/phase1-loader-foundation` `4` sessions, `feat/phase2-rough-binary-modis-truth` `7`, `feat/phase3-fine-grained-entropy-s2` `1`.
- WA usage is terminal-heavy and verification-heavy: `exec_command` `1077`, `update_plan` `83`, `write_stdin` `50`, plus `pytest` `106`, `ruff` `103`, `mypy` `45` invocations.
- The strongest sustained friction is not feature design; it is project-state recovery and HPC realism: `GWD30`, `OOM`, `probe`, progress visibility, and command-boundary corrections.

## Global Snapshot

- All projects: sessions `34`, user messages `416`, assistant messages `1570`, commentary `1407`, final answers `154`.
- All-project top tools: `exec_command=2911, write_stdin=296, update_plan=219, spawn_agent=89, wait_agent=86, close_agent=36`.
- All-project validation pressure: `pytest=116, ruff=103, mypy=45`.
- Lightning is where Codex used delegation most heavily; WA stayed mostly single-agent and shell-centric.
- Wetland-lineage sessions (`WA` + `Wetland_Assemble`) account for the majority of verification activity and almost all branch-by-phase progression.

## WA Meta

- Sessions `14`, user messages `173`, assistant messages `683`, commentary `588`, final answers `95`.
- Historical active days: `2026-03-18=4, 2026-03-19=6, 2026-03-20=1, 2026-03-21=1, 2026-03-22=2`.
- Git commits observed in WA sessions: `3`.
- Long-session profile (substantive only): mean `550.3` min, median `407.8` min, max `1803.4` min.
- Longest substantive sessions all sit in Phase 2 / Phase 2.5 transition work, which matches the project’s deepest HPC and data-pipeline friction.

## WA Facets

- Outcomes: `fully_achieved=6, mostly_achieved=4, not_achieved=3, partially_achieved=1`.
- Session types: `context_recovery=1, single_focus_delivery=1, iterative_refinement=3, minimal=3, single_task=2, multi_task=3, transition_session=1`.
- Primary success modes: `good_explanations=3, correct_code_edits=2, good_debugging=2, none=3, multi_file_changes=2, documentation_closure=1, project_insight=1`.
- Goal categories: `documentation=4, code_implementation=3, testing=3, bug_fix=3, hpc_debug=3, warmup_minimal=3, memory_restoration=2, git_commit=1, performance_optimization=1, data_alignment=1, geometry_rigor=1, workflow_rule_capture=1, result_review=1, reference_imagery=1, planning=1, state_alignment=1, project_insights=1`.
- Friction counts: `hpc_environment=1, memory_pressure=3, data_alignment=1, user_boundary_correction=2, missing_progress_visibility=1, data_quality_gap=1, state_ambiguity=1`.

### What Codex Is Good At

- Strong verification discipline. WA sessions repeatedly run tests and linters instead of stopping at “reasoned fixes”.
- Phase-oriented execution. Branch history shows a clean sequence from loader foundation to rough comparison to fine-grained / S2 work.
- HPC realism awareness. OOM, probe throughput, resampling strategy, tiling rigor, and progress visibility are treated as first-class engineering constraints.
- Closure hygiene. Many sessions end by writing stash/memory artifacts, not just prose answers.

### Main Friction Patterns

- `memory_restoration` is frequent, which means project context still costs too much to reload.
- `memory_pressure` keeps clustering around `GWD30`, especially when probe, coarse-grid reduction, and batch workflows intersect.
- `user_boundary_correction` appears when Codex oversteps into manual git / sync territory instead of staying at the “give commands only” boundary.
- `missing_progress_visibility` and `data_quality_gap` show that the user cares not only about correctness, but also about observability and imagery quality in long-running download workflows.

## WA Hot Files

- Top code files by mention / command frequency in WA sessions:
  - `src/WA/rough_probe.py`: `98`
  - `src/WA/loaders/gwd30.py`: `73`
  - `src/WA/rough_batch.py`: `61`
  - `src/WA/loader_probe.py`: `49`
  - `src/WA/comparison/harmonize.py`: `46`
  - `src/WA/loaders/glwd.py`: `28`
  - `src/WA/utils/mgrs_tiling.py`: `16`
  - `src/WA/loaders/_shared.py`: `15`
  - `src/WA/modis_batch.py`: `12`
  - `src/WA/comparison/rough_binary.py`: `9`
- Top test files by mention / command frequency in WA sessions:
  - `tests/test_rough_probe.py`: `103`
  - `tests/test_loaders/test_gwd30.py`: `90`
  - `tests/test_rough_batch.py`: `56`
  - `tests/test_comparison/test_harmonize.py`: `53`
  - `tests/test_loader_probe.py`: `52`
  - `tests/test_loaders/test_glwd.py`: `31`
  - `tests/test_comparison/test_rough_binary.py`: `23`
  - `tests/test_mgrs_tiling.py`: `18`
  - `tests/test_hpc_probe_rough_binary_script.py`: `15`
  - `tests/test_modis_batch.py`: `13`

These hotspots show that the deepest Codex attention sat on `rough_probe`, `gwd30`, `rough_batch`, `loader_probe`, and `harmonize`, not on UI or scaffolding work.

## WA Session Table

| Date | Session | Branch | Outcome | Type | Core Goal |
|------|---------|--------|---------|------|-----------|
| 2026-03-18 | `019d0053` | `pre-branch` | `fully_achieved` | `context_recovery` | Read project docs, recover WA context, and write a reusable stash summary. |
| 2026-03-18 | `019d0067` | `pre-branch` | `fully_achieved` | `single_focus_delivery` | Implement and validate an HPC loader probe script, then commit the Phase 1 probe work. |
| 2026-03-18 | `019d009f` | `feat/phase1-loader-foundation` | `mostly_achieved` | `iterative_refinement` | Debug repeated HPC probe failures in Phase 1, especially PROJ conflicts, OOM behavior, and topmodel loading scope. |
| 2026-03-18 | `019d0213` | `feat/phase1-loader-foundation` | `not_achieved` | `minimal` | Minimal warm-up / interrupted session with no substantive task execution. |
| 2026-03-19 | `019d040d` | `feat/phase1-loader-foundation` | `not_achieved` | `minimal` | Minimal warm-up / interrupted session with no substantive task execution. |
| 2026-03-19 | `019d0425` | `feat/phase1-loader-foundation` | `fully_achieved` | `iterative_refinement` | Fix core Phase 1/2 comparison bugs around month-aware selection, loader behavior, and temporal harmonization. |
| 2026-03-19 | `019d051d` | `feat/phase2-rough-binary-modis-truth` | `not_achieved` | `minimal` | Minimal warm-up / interrupted session with no substantive task execution. |
| 2026-03-19 | `019d053b` | `feat/phase2-rough-binary-modis-truth` | `fully_achieved` | `single_task` | Rewrite `bbox_to_tiles()` rigorously so shifted GWD30 footprints are not lost during tile selection. |
| 2026-03-19 | `019d0555` | `feat/phase2-rough-binary-modis-truth` | `mostly_achieved` | `multi_task` | Advance Phase 2 batch generation while hardening GWD30 loading against OOM and capturing the outcome in stash documentation. |
| 2026-03-19 | `019d063b` | `feat/phase2-rough-binary-modis-truth` | `mostly_achieved` | `iterative_refinement` | Continue GWD30 sharding and reduce-chain hardening, then lock in command-boundary rules via stash summary. |
| 2026-03-20 | `019d09f0` | `feat/phase2-rough-binary-modis-truth` | `mostly_achieved` | `multi_task` | Inspect Phase 2 outputs, improve the review/download pipeline, and add concrete prioritization tooling for Landsat review. |
| 2026-03-21 | `019d1064` | `feat/phase2-rough-binary-modis-truth` | `fully_achieved` | `single_task` | Patch the closeout stash so Phase 2 completion is explicitly and accurately documented. |
| 2026-03-22 | `019d13a4` | `feat/phase2-rough-binary-modis-truth` | `partially_achieved` | `transition_session` | Align the latest Phase 3 plan with the current dirty worktree and branch state before executing the next phase. |
| 2026-03-22 | `019d164f` | `feat/phase3-fine-grained-entropy-s2` | `fully_achieved` | `multi_task` | Restore Phase 3 context and generate a local insight view over prior WA sessions. |

## Highest-Leverage Historical Sessions

- `019d09f0` on `2026-03-20` (`feat/phase2-rough-binary-modis-truth`): `1803.4` min, `multi_file_changes`, `Produced concrete Phase 2 utilities and review-priority outputs, while also surfacing UX and data-quality expectations around download workflows.`
- `019d063b` on `2026-03-19` (`feat/phase2-rough-binary-modis-truth`): `1031.1` min, `good_explanations`, `Captured the sharding/reduce lessons and codified command-boundary expectations, while Phase 2 HPC tuning remained active work.`
- `019d1064` on `2026-03-21` (`feat/phase2-rough-binary-modis-truth`): `907.7` min, `documentation_closure`, `Updated the Phase 2 closeout stash with a concrete deliverables section so future memory restores can rely on it.`
- `019d164f` on `2026-03-22` (`feat/phase3-fine-grained-entropy-s2`): `744.3` min, `project_insight`, `Recovered the current Phase 3 state, refreshed memory files, and produced a first-pass local `/insights` style summary for WA.`
- `019d13a4` on `2026-03-22` (`feat/phase2-rough-binary-modis-truth`): `540.5` min, `good_explanations`, `Clarified the latest plan and working-tree state, but intentionally stopped for confirmation rather than forcing a phase transition.`

## Rules Worth Promoting To Memory

- `GWD30` should be treated as the persistent HPC risk center; every new rough/fine workflow touching it should surface memory strategy explicitly.
- Codex should default to command-boundary respect for WA: give executable commands, do not assume sync/commit actions the user wants to do manually.
- Any long-running download or probe flow should expose progress clearly; silent success/failure is not acceptable for this project.
- Memory restore should keep phase status, hottest blockers, and last validated commands in a single low-friction place to reduce session startup cost.

## Deliverables

- JSON sidecar: `docs/stashes/2026-03-23-003-codex-sessions-insights-wa.json`
- Markdown report: `docs/stashes/2026-03-23-003-codex-sessions-insights-report.md`

## Note

- This is a local Codex reconstruction of Claude-style insights. `session-meta` fields come from direct JSONL aggregation; `facets` are inferred from prompts, tool traces, corrections, and final answers rather than being first-party Codex fields.
