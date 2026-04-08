# S01 Inventory

**Generated:** 2026-04-07
**Worktree:** `milestone/M001`
**HEAD:** `a8680b9` (`chore: init gsd`)
**Purpose:** Freeze the local, replayable repository evidence for R001 before later slices judge route correctness.
**Follow-up:** Route-drift classification now lives in `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`; keep this file as the raw evidence freeze and use the appendix for current-vs-historical interpretation.

## Snapshot

- `src/WA/`: `present-local` — **56** Python source files.
- `scripts/`: `present-local` — **54** operational entrypoints.
- `tests/`: `present-local` — **71** files (**70** Python test files + 1 notebook), **418** tests collected by `python -m pytest --collect-only -q`.
- `docs/plans/`: `present-local` — **20** plan files.
- `docs/stashes/`: `present-local` — **147** stash/history files.
- `docs/datasets/`: `present-local` — **9** dataset reference files.
- `todos/`: `present-local` — **6** TODO files.
- `results/`: `absent-local`.
- `temp/`: `absent-local`.
- `../../.claude/projects/-Users-mac-Code-WA/memory`: `absent-local` from this audit worktree.

## Runtime Code Surface

**Status:** `present-local`

Evidence:
- `find src/WA -type f -name '*.py' ! -path '*/__pycache__/*' | wc -l` → `56`
- Family counts:
  - `comparison`: `11`
  - `loaders`: `12`
  - `validation`: `6`
  - `visualization`: `7`
  - `utils`: `4`

Representative anchors:
- `src/WA/config.py` — config loader for repository-wide dataset definitions.
- `src/WA/classification.py` — unified wetland/water class mapping surface.
- `src/WA/standardize.py` — standardized staging / chunk / merge hub.
- `src/WA/loaders/registry.py` — loader registration boundary.
- `src/WA/loaders/gwd30.py` — high-risk GWD30 staging / tiling / reduce surface.
- `src/WA/comparison/phase36.py` — Phase 3.6 global disagreement route.
- `src/WA/comparison/phase4_regional.py` — current regional Phase 4 orchestration surface.
- `src/WA/comparison/trends.py` — Phase 4 trend + Stage-1 GWD30 pixel-statistics builder surface.
- `src/WA/visualization/phase4.py` — Phase 4 plotting/output surface.

Inventory note:
- `src/WA/` is not a thin prototype surface. It already contains loader, comparison, validation, visualization, batching, probe, and staging logic.
- `__pycache__/` exists locally but is not part of the canonical source count.

## Operational Script Surface

**Status:** `present-local`

Evidence:
- `find scripts -maxdepth 1 -type f | wc -l` → `54`
- Script family counts from local filenames:
  - `build`: `4`
  - `check`: `2`
  - `download`: `2`
  - `fetch`: `1`
  - `find`: `1`
  - `hpc_probe`: `4`
  - `inspect`: `2`
  - `list`: `1`
  - `merge`: `1`
  - `plot`: `12`
  - `redownload`: `1`
  - `reduce`: `2`
  - `run`: `11`
  - `stack`: `2`
  - `standardize`: `2`
  - `submit/shell`: `6`

Representative anchors:
- `scripts/standardize_datasets.py` — standardized dataset build entrypoint.
- `scripts/standardize_gwd30.py` — GWD30-specific standardization surface.
- `scripts/run_phase3_6_global_entropy.py` — Phase 3.6 execution anchor.
- `scripts/find_phase3_7_hotspots.py` — Phase 3.7 hotspot selection anchor.
- `scripts/build_phase4_gwd30_pixel_stats.py` — `current-signal` Stage-1 Phase 4 builder.
- `scripts/run_phase4_regional.py` — `current-signal` Stage-2 Phase 4 regional entrypoint.
- `scripts/reduce_phase4_gwd30_tropical_shards.py` — retained older reducer surface; inventory only, route judgment deferred.
- `scripts/submit_phase4_gwd30_pixel_stats.sh` — `current-signal` HPC submit surface for Stage 1.
- `sync.sh` — `present-local`, rsync/HPC workflow boundary.

Inventory note:
- The repo keeps both local runners and HPC submit/probe scripts side-by-side.
- Presence in `scripts/` does **not** imply the route is current; later slices must judge `current-signal` vs `historical` vs `stale` explicitly.

## Verification Surface

**Status:** `present-local`

Evidence:
- `find tests -type f ! -path '*/__pycache__/*' | wc -l` → `71`
- `find tests -type f -name '*.py' ! -path '*/__pycache__/*' | wc -l` → `70`
- `python -m pytest --collect-only -q` → `418 tests collected in 1.08s`
- Test family counts:
  - `tests/test_comparison`: `9`
  - `tests/test_loaders`: `12`
  - `tests/test_validation`: `6`
  - `tests/test_visualization`: `5`
  - top-level tests: `39`

Representative anchors:
- `tests/test_standardize.py` — major staging / chunk / GWD30 pipeline coverage.
- `tests/test_loaders/test_gwd30.py` — loader / staging / reduce / progress behavior for GWD30.
- `tests/test_phase3_6_analysis.py` — Phase 3.6 analysis route coverage.
- `tests/test_comparison/test_phase4_regional.py` — Phase 4 regional route coverage.
- `tests/test_comparison/test_trends.py` — Phase 4 trend and pixel-statistics coverage.
- `tests/test_validation/test_s2_reference.py` — GEE/S2 failure and success path coverage.

Inventory note:
- Local verification surface is broad and non-trivial.
- Test collection is evidence of maintained test entrypoints, not proof of HPC correctness.

## Planning and History Surface

**Status:** `present-local`

Evidence:
- `find docs/plans -maxdepth 1 -type f | wc -l` → `20`
- `find docs/stashes -maxdepth 1 -type f | wc -l` → `147`
- `find docs/datasets -maxdepth 1 -type f | wc -l` → `9`

Representative anchors and tags:
- `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md` — `historical`, but explicitly marked as superseding the earlier loader-only draft.
- `docs/plans/2026-03-18-feat-dataset-loaders-plan.md` — `superseded` by the file above.
- `docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md` — `current-signal` planning anchor for the latest Phase 4 GWD30 pivot.
- `docs/stashes/2026-04-06-003-phase4-conversation-summary.md` — `current-signal`; states the old full-tropics reduce route is no longer recommended.
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md` — `current-signal`; points re-entry to Phase 4 Stage 2 rather than the old reducer.
- `docs/stashes/2026-03-22-002-memory-restore-summary.md` — `historical`; useful as evidence of earlier state reconstruction, but its “next step is Phase 3” claim is no longer current.
- `CHANGELOG.md` — `present-local`, high-signal chronological summary of recent route pivots.
- `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, `.gsd/milestones/M001/M001-CONTEXT.md`, `.gsd/milestones/M001/slices/S01/S01-RESEARCH.md` — `present-local`, audit-contract inputs.

Inventory note:
- This surface contains both authoritative recent signals and retained stale intent. Later slices must not flatten them into a single truth source.

## Dataset, TODO, and Config Surface

**Status:** mixed — `present-local` config/docs, with several `external/HPC-only` paths referenced inside config

Evidence:
- `config/datasets.yaml` is `present-local`.
- `docs/datasets/` is `present-local` with **9** reference files.
- `todos/` is `present-local` with **6** TODO files.

Representative anchors:
- `config/datasets.yaml` — canonical local dataset catalog surface.
- `config/classification_mappings.yaml` — class mapping support surface.
- `docs/datasets/GWD30.md`, `docs/datasets/GLWD v2.md`, `docs/datasets/WAD2M.md` — local dataset notes.
- `todos/001-complete-p1-phase1-loader-foundation.md` through `todos/006-complete-p1-build-phase2-rough-region-data-generation.md` — retained TODO surface concentrated in early Phase 1 / Phase 2 work.

Config facts frozen from `config/datasets.yaml`:
- Dataset entries present locally in config: `9`
  - In-scope wetland surfaces include `berkeley_rwawc`, `g2017`, `giems_mc`, `glwd_v2`, `gwd30`, `swamps`, `topmodel`, `wad2m`.
  - `lstm_wetland` is configured but remains out of scope.
- Region catalog present locally in config: `tropical`, `subtropical`, `tropical_subtropical`, `global`.
- Several configured raw-data paths are `external/HPC-only`, including `/lustre/home/2200013429/Wetland_Assemble/data/GIEMS_MC/`, `/lustre/home/2200013429/Wetland_Assemble/data/GWD30/`, `/lustre/home/2200013429/Wetland_Assemble/data/SWAMPS/`, and `/lustre/home/2200013429/Wetland_Assemble/data/WAD2M/data/`.

Inventory note:
- The config surface is locally readable, but many data roots it names are not locally inspectable from this worktree.
- `.gitignore` explicitly ignores `results/`, `temp/`, and `.claude/`, which explains why some referenced artifact and memory surfaces are absent here.

## Git and Worktree State

**Status:** `present-local`

Evidence:
- `git status --short --branch` → `## milestone/M001` with no modified/untracked files before this task wrote inventory artifacts.
- `git branch --all --list` shows retained feature branches including `feat/phase1-loader-foundation`, `feat/phase2-rough-binary-modis-truth`, `feat/phase25-visualization`, `feat/phase35-comparison-visualization`, `feat/phase4-trend-analysis`, `refactor/loader-reference-grid-alignment`, and the active `milestone/M001`.
- `git log --oneline --decorate -n 12` shows `a8680b9 (HEAD -> milestone/M001, refactor/loader-reference-grid-alignment) chore: init gsd` at the current tip.
- `git worktree list` shows:
  - repo root worktree on `refactor/loader-reference-grid-alignment`
  - current GSD audit worktree on `milestone/M001`
  - retained codex and feature worktrees for older routes.

Inventory note:
- The same commit head is shared by both `milestone/M001` and `refactor/loader-reference-grid-alignment` at inventory time.
- Branch/worktree plurality is part of the current evidence surface and must be considered when later slices judge drift and route recency.

## Artifact Presence and Proof Boundaries

**Status:** mixed

Local presence/absence facts:
- `results/` — `absent-local`
- `temp/` — `absent-local`
- `../../.claude/projects/-Users-mac-Code-WA/memory` — `absent-local` from this audit worktree
- `docs/stashes/` — `present-local`
- `CHANGELOG.md` — `present-local`
- `config/datasets.yaml` — `present-local`

Boundary interpretation:
- `results/` and `temp/` are referenced throughout the repo, but `.gitignore` excludes both; local absence here is a proof-boundary fact, not evidence that those artifacts never existed.
- The project-level memory path is cited in older recovery notes, but it is not locally reachable from this worktree; treat it as an unavailable evidence surface for M001 unless separately materialized.
- Raw dataset roots under `/lustre/...` are `external/HPC-only`; local docs and tests can describe them, but cannot prove their current remote contents.
- Stash notes and changelog entries are valuable evidence surfaces, but they do **not** replace direct HPC verification.

## Command Appendix

The following commands were used to freeze this inventory and can be replayed by later slices.

### Repository / surface enumeration

```bash
find . -maxdepth 2 -mindepth 1 | sort
find src/WA -maxdepth 2 -type f | sort
find scripts -maxdepth 1 -type f | sort
find tests -maxdepth 2 -type f | sort
find docs/plans docs/stashes docs/datasets -maxdepth 1 -type f | sort
find todos -maxdepth 1 -type f | sort
```

### Canonical counts

```bash
find src/WA -type f -name '*.py' ! -path '*/__pycache__/*' | wc -l
find scripts -maxdepth 1 -type f | wc -l
find tests -type f ! -path '*/__pycache__/*' | wc -l
find tests -type f -name '*.py' ! -path '*/__pycache__/*' | wc -l
find docs/plans -maxdepth 1 -type f | wc -l
find docs/stashes -maxdepth 1 -type f | wc -l
find docs/datasets -maxdepth 1 -type f | wc -l
find todos -maxdepth 1 -type f | wc -l
```

Observed outputs at inventory time:
- `src/WA` Python files: `56`
- `scripts/` files: `54`
- `tests/` files: `71`
- `tests/` Python files: `70`
- `docs/plans/`: `20`
- `docs/stashes/`: `147`
- `docs/datasets/`: `9`
- `todos/`: `6`

### Git / worktree state

```bash
git status --short --branch
git branch --all --list
git log --oneline --decorate -n 12
git worktree list
```

Observed outputs at inventory time:
- Current branch: `milestone/M001`
- Current head: `a8680b9`
- Clean status before writing this inventory
- Shared head with `refactor/loader-reference-grid-alignment`

### Verification surface

```bash
python -m pytest --collect-only -q
```

Observed output at inventory time:
- `418 tests collected in 1.08s`
- One runtime warning from import bootstrap about NumPy binary compatibility; collection still completed.

### Presence / absence checks

```bash
for p in results temp todos scripts tests docs src/WA config/datasets.yaml CHANGELOG.md .gitignore; do
  if [ -e "$p" ]; then printf '%s present\n' "$p"; else printf '%s absent\n' "$p"; fi
done

if [ -d ../../.claude/projects/-Users-mac-Code-WA/memory ]; then
  echo 'memory_path_present'
else
  echo 'memory_path_absent'
fi
```

Observed outputs at inventory time:
- `results/` → absent
- `temp/` → absent
- `todos/`, `scripts/`, `tests/`, `docs/`, `src/WA/`, `config/datasets.yaml`, `CHANGELOG.md`, `.gitignore` → present
- memory path → `memory_path_absent`
