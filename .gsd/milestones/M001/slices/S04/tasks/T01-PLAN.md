---
estimated_steps: 10
estimated_files: 7
skills_used:
  - doc-coauthoring
  - document-review
---

# T01: Draft the canonical S04 execution map from the live Phase 4 route and proof surfaces

Build the canonical S04 execution-map artifact first so the next operator can recover the correct continuation ladder from one source of truth before any breadcrumb or metadata updates are written.

## Steps

1. Start `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` with a short framing rule that treats `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` as the route-truth input and `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` as the proof-boundary input, then state clearly that S04 sequences those artifacts rather than replacing them.
2. Populate `Canonical Read Order` and `Ordered Continuation Path` with live-script commands only: read S03 first, read the S02 Phase 4/Open Proof Gaps rows second, run the direct Stage-1 builder for `--year 2016` with `--no-skip` before the broad submit wrapper, then run the matching `gwd30` / `amazon` / `2016-2016` Stage-2 regional command before widening to broader ranges.
3. Fill `Proof Targets / Exit Criteria` and `Do Not Touch First` with the exact proof files, the Stage-1 log marker, the stale shard/reduce family, the missing broad runner, and the stale CLI flags so a fresh operator can tell both what success looks like and what not to copy from older notes.

## Must-Haves

- [ ] The canonical doc names the exact current entry scripts, the narrow-first 2016/amazon proof order, and the exact artifact paths that prove Stage-1 and Stage-2 succeeded.
- [ ] The avoid list explicitly calls out the historical shard/reduce family, the missing `scripts/run_phase4_trend_analysis.py` route, the broad default invocations that silently fan out, and the stale flags from older stash notes.

## Done when

- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` exists with the read-order, execution-order, proof-target, and avoid-list sections populated from the live script surface rather than older stash snippets.

## Inputs

- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- `scripts/build_phase4_gwd30_pixel_stats.py`
- `scripts/submit_phase4_gwd30_pixel_stats.sh`
- `scripts/run_phase4_regional.py`
- `scripts/hpc_probe_trends.py`

## Expected Output

- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`

## Verification

`test -s .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
`rg -n '^## (Canonical Read Order|Ordered Continuation Path|Proof Targets / Exit Criteria|Do Not Touch First)$' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
`rg -n 'scripts/build_phase4_gwd30_pixel_stats.py|scripts/submit_phase4_gwd30_pixel_stats.sh|scripts/run_phase4_regional.py|scripts/hpc_probe_trends.py|scripts/submit_phase4_gwd30_tropical_shards.sh|scripts/run_phase4_gwd30_tropical_shard.py|scripts/reduce_phase4_gwd30_tropical_shards.py|run_phase4_trend_analysis.py|--berkeley-raw-path|--phase36-cache-dir|--gwd30-cache-dir|--gwd30-worker-count' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
`rg -n 'results/phase4/pixel_stats/gwd30/gwd30_2016/monthly/tile_manifest.json|results/phase4/cache/masks/berkeley_valid/amazon_2016_2016.nc|results/phase4/cache/gwd30/amazon/regional_series.csv|results/phase4/tables/amazon.csv|Phase4 cache write: gwd30_native_pixel_stats' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
