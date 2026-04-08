# S03: Route Audit & Risk Register

**Goal:** Publish one canonical route audit that classifies the current recommended Phase 4 continuation path, the still-usable supporting routes, and the stale or misleading routes, then records the risks and proof gaps future work must carry forward.
**Demo:** After this: After this: the project has an explicit list of current recommended routes, stale or misleading routes, and the risks attached to each one.

## Tasks
- [x] **T01: Added the canonical S03 Phase 4 route audit that names the current Stage-1/Stage-2 mainline and demotes the stale full-tropics and missing-runner routes.** — Build the canonical S03 route-audit document first so route truth lives in one source of truth before any handoff note or changelog breadcrumb is written.

## Steps

1. Start `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` with a short evidence rule that treats the S02 matrix plus source-code-backed 2026-04-06 evidence as authoritative when older still-`active` plans disagree.
2. Populate `Current Recommended Routes`, `Supporting but Non-Primary Routes`, and `Historical/Stale or Misleading Routes` with concise tables that name the exact entry files, what each route actually does today, the strongest evidence anchors, and why the route is current, supporting, or stale.
3. Make the live chain explicit: `scripts/build_phase4_gwd30_pixel_stats.py` plus `scripts/submit_phase4_gwd30_pixel_stats.sh` feed `scripts/run_phase4_regional.py`, while `scripts/hpc_probe_trends.py` and the old full-tropics reducer lane remain non-primary or historical instead of interchangeable continuations.

## Must-Haves

- [ ] The canonical doc names the current mainline, the supporting diagnostic route, and the stale/misleading route family with concrete script/module paths.
- [ ] The current-route section states clearly that the recommended chain closes regional table generation today and does **not** imply the missing broad `run_phase4_trend_analysis.py` batch runner exists.

## Done when

- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` exists with the three route-classification sections and enough evidence anchors that a fresh reader can tell which entrypoints to continue from and which ones to avoid.
  - Estimate: 35m
  - Files: .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md, .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md, src/WA/comparison/phase4_regional.py, src/WA/comparison/trends.py, scripts/build_phase4_gwd30_pixel_stats.py, scripts/submit_phase4_gwd30_pixel_stats.sh, scripts/run_phase4_regional.py, scripts/hpc_probe_trends.py
  - Verify: `test -s .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
`rg -n '^## (Current Recommended Routes|Supporting but Non-Primary Routes|Historical/Stale or Misleading Routes)$' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
`rg -n 'scripts/build_phase4_gwd30_pixel_stats.py|scripts/submit_phase4_gwd30_pixel_stats.sh|scripts/run_phase4_regional.py|scripts/hpc_probe_trends.py|scripts/submit_phase4_gwd30_tropical_shards.sh' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
- [x] **T02: Finalized the S03 route-audit risk/requirement coverage, added the Chinese-friendly re-entry stash note, and recorded changelog breadcrumbs that point back to the canonical audit.** — Close S03 by turning the route classification into a reusable operator handoff that carries forward the unresolved proof gaps instead of hiding them.

## Steps

1. Finish the `Risk Register` and `Requirement Coverage` sections in `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`, covering stage-numbering drift, 2026-04-06 changelog self-conflict, HPC-only proof gaps for the Stage-1 / Stage-2 chain, GWD30 input divergence between the regional lane and trend probe lane, and the misleading weight of old active plans/tests.
2. Write `docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md` as the compact Chinese-friendly pointer note that tells operators to read the canonical S03 doc first, lists the current route and the routes to avoid, and preserves the still-open HPC/proof boundaries with `--no-skip` command wording.
3. Add a `CHANGELOG.md` breadcrumb for the canonical route audit and the stash-note pointer so later slices can recover the new route judgment without replaying the full S03 artifact history.

## Must-Haves

- [ ] The finished canonical doc advances `R003`, `R004`, and `R005` explicitly and does not overstate unresolved HPC proof as completed work.
- [ ] The stash note and changelog both point back to `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` instead of creating a second competing source of truth.

## Done when

- The canonical doc includes the risk register plus requirement coverage, the Chinese-friendly stash note exists, and `CHANGELOG.md` records both artifacts as the new route-audit breadcrumbs.
  - Estimate: 30m
  - Files: .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md, docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md, CHANGELOG.md, docs/stashes/2026-04-06-007-phase4-berkeley-mask-bbox-oom-fix.md, docs/stashes/2026-04-06-008-phase4-recall-entry.md, docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md, docs/plans/2026-03-23-feat-phase4-trend-analysis-implementation-plan.md
  - Verify: `rg -n '^## (Risk Register|Requirement Coverage)$' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
`rg -n 'R003|R004|R005|HPC-only proof gap|_staging|historical/stale' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
`test -s docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md`
`rg -n 'S03-ROUTE-AUDIT-RISK-REGISTER.md|当前推荐路线|避免|Open Proof Gaps|--no-skip' docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md`
`rg -n 'S03-ROUTE-AUDIT-RISK-REGISTER.md|route audit|risk register|docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md' CHANGELOG.md`
