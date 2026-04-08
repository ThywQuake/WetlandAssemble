---
id: T01
parent: S04
milestone: M001
key_files:
  - .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md
  - .gsd/milestones/M001/slices/S04/tasks/T01-SUMMARY.md
key_decisions:
  - Treat S03 as route truth and S02 as proof boundary, then keep S04 limited to sequencing the next operator actions instead of re-arguing route history.
duration: 
verification_result: passed
completed_at: 2026-04-06T22:29:48.474Z
blocker_discovered: false
---

# T01: Added the canonical S04 next-step execution map with a 2016/amazon narrow-first Phase 4 proof ladder and explicit stale-route guardrails.

**Added the canonical S04 next-step execution map with a 2016/amazon narrow-first Phase 4 proof ladder and explicit stale-route guardrails.**

## What Happened

Activated the requested documentation skills, read the live S03 route audit, S02 proof-boundary matrix, S04 research note, and the current Phase 4 entry scripts/tests, then wrote `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` as the single canonical continuation artifact. The map explicitly frames S03 as route truth and S02 as proof boundary, orders the next operator path as direct Stage 1 for `--year 2016` before the broad wrapper, then Stage 2 for `gwd30` + `amazon` + `2016-2016`, then broader runs only after those proofs pass. It also freezes the proof targets (`tile_manifest.json`, Berkeley-valid mask cache, GWD30 regional cache, regional table, and the `Phase4 cache write: gwd30_native_pixel_stats` log marker) and calls out the stale shard/reduce family, the missing `scripts/run_phase4_trend_analysis.py` route, the broad default invocations, and the stale CLI flags from older notes. I kept the task scoped to the canonical map only and left requirement/changelog/breadcrumb packaging for the later slice task that owns that work.

## Verification

Ran the task-plan structural verification checks against `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`. Verified the file exists and is non-empty, the required section headings are present, the map names the live entry scripts and stale routes/flags to avoid, and the proof-target section contains the exact Stage-1 log marker and artifact paths required by the plan.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -s .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` | 0 | ✅ pass | 5ms |
| 2 | `rg -n '^## (Canonical Read Order|Ordered Continuation Path|Proof Targets / Exit Criteria|Do Not Touch First)$' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` | 0 | ✅ pass | 15ms |
| 3 | `rg -n 'scripts/build_phase4_gwd30_pixel_stats.py|scripts/submit_phase4_gwd30_pixel_stats.sh|scripts/run_phase4_regional.py|scripts/hpc_probe_trends.py|scripts/submit_phase4_gwd30_tropical_shards.sh|scripts/run_phase4_gwd30_tropical_shard.py|scripts/reduce_phase4_gwd30_tropical_shards.py|run_phase4_trend_analysis.py|--berkeley-raw-path|--phase36-cache-dir|--gwd30-cache-dir|--gwd30-worker-count' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` | 0 | ✅ pass | 8ms |
| 4 | `rg -n 'results/phase4/pixel_stats/gwd30/gwd30_2016/monthly/tile_manifest.json|results/phase4/cache/masks/berkeley_valid/amazon_2016_2016.nc|results/phase4/cache/gwd30/amazon/regional_series.csv|results/phase4/tables/amazon.csv|Phase4 cache write: gwd30_native_pixel_stats' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` | 0 | ✅ pass | 6ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
- `.gsd/milestones/M001/slices/S04/tasks/T01-SUMMARY.md`
