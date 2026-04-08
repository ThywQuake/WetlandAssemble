# S04: Next-Step Execution Map

**Goal:** Turn the S02 proof-boundary matrix and S03 route audit into one canonical, ordered execution map that tells the next operator exactly what to read first, what to run first, what files prove success, when to widen scope, and which stale paths or flags to avoid touching initially.
**Demo:** After this: After this: there is a concrete continuation path showing where to enter next, what to verify first, and which routes to avoid touching initially.

## Tasks
- [x] **T01: Added the canonical S04 next-step execution map with a 2016/amazon narrow-first Phase 4 proof ladder and explicit stale-route guardrails.** — Build the canonical S04 execution-map artifact first so the next operator can recover the correct continuation ladder from one source of truth before any breadcrumb or metadata updates are written.

## Steps

1. Start `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` with a short framing rule that treats `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` as the route-truth input and `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` as the proof-boundary input, then state clearly that S04 sequences those artifacts rather than replacing them.
2. Populate `Canonical Read Order` and `Ordered Continuation Path` with live-script commands only: read S03 first, read the S02 Phase 4/Open Proof Gaps rows second, run the direct Stage-1 builder for `--year 2016` with `--no-skip` before the broad submit wrapper, then run the matching `gwd30` / `amazon` / `2016-2016` Stage-2 regional command before widening to broader ranges.
3. Fill `Proof Targets / Exit Criteria` and `Do Not Touch First` with the exact proof files, the Stage-1 log marker, the stale shard/reduce family, the missing broad runner, and the stale CLI flags so a fresh operator can tell both what success looks like and what not to copy from older notes.

## Must-Haves

- [ ] The canonical doc names the exact current entry scripts, the narrow-first 2016/amazon proof order, and the exact artifact paths that prove Stage-1 and Stage-2 succeeded.
- [ ] The avoid list explicitly calls out the historical shard/reduce family, the missing `scripts/run_phase4_trend_analysis.py` route, the broad default invocations that silently fan out, and the stale flags from older stash notes.

## Done when

- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` exists with the read-order, execution-order, proof-target, and avoid-list sections populated from the live script surface rather than older stash snippets.
  - Estimate: 35m
  - Files: .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md, .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md, .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md, scripts/build_phase4_gwd30_pixel_stats.py, scripts/submit_phase4_gwd30_pixel_stats.sh, scripts/run_phase4_regional.py, scripts/hpc_probe_trends.py
  - Verify: `test -s .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
`rg -n '^## (Canonical Read Order|Ordered Continuation Path|Proof Targets / Exit Criteria|Do Not Touch First)$' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
`rg -n 'scripts/build_phase4_gwd30_pixel_stats.py|scripts/submit_phase4_gwd30_pixel_stats.sh|scripts/run_phase4_regional.py|scripts/hpc_probe_trends.py|scripts/submit_phase4_gwd30_tropical_shards.sh|scripts/run_phase4_gwd30_tropical_shard.py|scripts/reduce_phase4_gwd30_tropical_shards.py|run_phase4_trend_analysis.py|--berkeley-raw-path|--phase36-cache-dir|--gwd30-cache-dir|--gwd30-worker-count' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
`rg -n 'results/phase4/pixel_stats/gwd30/gwd30_2016/monthly/tile_manifest.json|results/phase4/cache/masks/berkeley_valid/amazon_2016_2016.nc|results/phase4/cache/gwd30/amazon/regional_series.csv|results/phase4/tables/amazon.csv|Phase4 cache write: gwd30_native_pixel_stats' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
- [x] **T02: Validated R006 against the canonical S04 next-step execution map and added a compact Chinese re-entry breadcrumb that points back to it.** — Close S04 by keeping the execution map canonical while still leaving the operator a compact Chinese-friendly re-entry breadcrumb and the formal requirement/changelog links that point back to it.

## Steps

1. Finish the `Requirement Coverage` section in `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`, making `R006` explicit and keeping the inherited `R003`/`R005` route-truth and proof-gap boundaries visible without re-arguing S03.
2. Write `docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md` as a compact Chinese-friendly pointer note that tells operators to read the canonical S04 map first, restates the 2016/amazon narrow-first ladder in condensed form, and preserves `--no-skip` wording plus the routes/flags to avoid.
3. Update `CHANGELOG.md` and `.gsd/REQUIREMENTS.md` so later slices can recover the new continuation map quickly and `R006` validates directly against `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`.

## Must-Haves

- [ ] The stash note and changelog both point back to the canonical S04 map instead of becoming a second source of truth.
- [ ] `.gsd/REQUIREMENTS.md` validates `R006` against the finished S04 map and does not imply the fresh HPC rerun already happened.

## Done when

- The canonical S04 map contains requirement coverage, the compact Chinese-friendly stash note exists, `CHANGELOG.md` records the breadcrumb, and `.gsd/REQUIREMENTS.md` maps `R006` to the canonical S04 artifact.
  - Estimate: 30m
  - Files: .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md, docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md, CHANGELOG.md, .gsd/REQUIREMENTS.md, .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md
  - Verify: `rg -n '^## Requirement Coverage$|R006|R003|R005' .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`
`test -s docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md`
`rg -n 'S04-NEXT-STEP-EXECUTION-MAP.md|2016|amazon|当前|避免|--no-skip' docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md`
`rg -n 'R006' .gsd/REQUIREMENTS.md`
`rg -n 'S04-NEXT-STEP-EXECUTION-MAP.md|next-step execution map|docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md' CHANGELOG.md`
