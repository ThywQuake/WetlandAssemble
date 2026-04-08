# S04: Next-Step Execution Map — UAT

**Milestone:** M001
**Written:** 2026-04-06T22:42:58.151Z

# S04: Next-Step Execution Map — UAT

**Milestone:** M001
**Written:** 2026-04-07T03:29:11+08:00

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S04 ships a canonical execution map, a recovery breadcrumb, and requirement/changelog metadata rather than runtime code, so correctness is proven by document structure, command specificity, proof targets, and source-of-truth discipline.

## Preconditions

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` exists and remains the proof-boundary source.
- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` exists and remains the route-truth source.
- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` has been generated in this worktree.
- `docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md`, `CHANGELOG.md`, and `.gsd/REQUIREMENTS.md` are available locally.

## Smoke Test

Open `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` and confirm it contains `Canonical Read Order`, `Ordered Continuation Path`, `Proof Targets / Exit Criteria`, `Do Not Touch First`, and `Requirement Coverage` in one canonical artifact.

## Test Cases

### 1. Narrow-first continuation ladder is explicit

1. Read the `Canonical Read Order` section in `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`.
2. Confirm it tells the operator to read S03 first and the S02 Phase 4/Open Proof Gaps rows second.
3. Read the `Ordered Continuation Path` section.
4. Confirm the first runnable command is direct Stage 1 `scripts/build_phase4_gwd30_pixel_stats.py --year 2016 --no-skip` rather than the submit wrapper.
5. Confirm the second runnable command is Stage 2 `scripts/run_phase4_regional.py --dataset-id gwd30 --region amazon --start-year 2016 --end-year 2016 --no-skip`.
6. Confirm broader wrappers or wider year ranges appear only after the narrow `2016 -> amazon` proof steps.
7. **Expected:** A fresh operator can identify the first safe read order and first safe execution ladder without consulting older notes.

### 2. Success criteria are concrete and checkable

1. Read the `Proof Targets / Exit Criteria` section in the canonical S04 map.
2. Confirm Stage 1 success explicitly requires `results/phase4/pixel_stats/gwd30/gwd30_2016/monthly/tile_manifest.json` and the log marker `Phase4 cache write: gwd30_native_pixel_stats`.
3. Confirm Stage 2 success explicitly requires `results/phase4/cache/masks/berkeley_valid/amazon_2016_2016.nc`, `results/phase4/cache/gwd30/amazon/regional_series.csv`, and `results/phase4/tables/amazon.csv`.
4. Confirm the map says the route is not freshly re-proven until both Stage-1 and Stage-2 proof targets exist.
5. **Expected:** The operator knows exactly which files and log line to check before declaring the rerun successful.

### 3. Stale routes are blocked and breadcrumbs stay subordinate

1. Read the `Do Not Touch First` section in `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`.
2. Confirm it explicitly demotes the full-tropics shard/reduce family, the missing `scripts/run_phase4_trend_analysis.py` route, broad default invocations, and stale flags (`--berkeley-raw-path`, `--phase36-cache-dir`, `--gwd30-cache-dir`, `--gwd30-worker-count`).
3. Open `docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md`.
4. Confirm the stash note points back to `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`, restates the `2016 -> amazon` ladder in compact form, preserves `--no-skip`, and does not replace the canonical map.
5. Open `CHANGELOG.md` and confirm the 2026-04-07 entry points back to the canonical S04 map and the compact breadcrumb.
6. Open `.gsd/REQUIREMENTS.md` and confirm R006 validates against `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`.
7. **Expected:** Older routes and flags are visibly blocked, while the breadcrumb surfaces remain shortcuts back to the canonical execution map rather than alternate specifications.

## Edge Cases

### Older recovery notes still suggest broader or stale entry paths

1. Compare the S04 map against older 2026-04-05 / 2026-04-06 notes that mention full-tropics shard/reduce flows, missing broad runners, or stale CLI flags.
2. **Expected:** The canonical S04 map overrides those older cues by fixing the first safe route to narrow Stage 1 `2016` then narrow Stage 2 `amazon 2016-2016`, and by explicitly listing the stale families and flags to avoid.

## Failure Signals

- The canonical S04 map is missing one of the required five sections.
- The first commands are broad defaults instead of explicit narrow `2016` / `amazon` runs.
- The proof-target section omits the required file paths or the `Phase4 cache write: gwd30_native_pixel_stats` log marker.
- The stash note or changelog reads like a second execution map instead of a breadcrumb back to the canonical artifact.
- The documents imply the fresh HPC rerun already happened.

## Not Proven By This UAT

- No fresh HPC rerun of the Stage-1 builder or Stage-2 regional runner was performed here.
- This UAT does not prove that the proof-target files already exist on HPC; it proves only that the continuation contract now names them precisely.
- This UAT does not decide whether `scripts/hpc_probe_trends.py` should later converge with the Stage-1 pixel-stats input path.

## Notes for Tester

- Use S03 to answer “which route is current?” and S04 to answer “what exactly should I do first?”
- Treat the stash note and changelog entry only as shortcuts back to the canonical S04 map.
- If you later execute the rerun on HPC, keep the explicit `--no-skip` wording from S04 so the proof is fresh rather than cache-biased.

