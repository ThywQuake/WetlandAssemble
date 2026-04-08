---
estimated_steps: 10
estimated_files: 7
skills_used:
  - document-review
  - doc-coauthoring
---

# T02: Finish the risk register and publish the compact re-entry handoff

Close S03 by turning the route classification into a reusable operator handoff that carries forward the unresolved proof gaps instead of hiding them.

## Steps

1. Finish the `Risk Register` and `Requirement Coverage` sections in `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`, covering stage-numbering drift, 2026-04-06 changelog self-conflict, HPC-only proof gaps for the Stage-1 / Stage-2 chain, GWD30 input divergence between the regional lane and trend probe lane, and the misleading weight of old active plans/tests.
2. Write `docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md` as the compact Chinese-friendly pointer note that tells operators to read the canonical S03 doc first, lists the current route and the routes to avoid, and preserves the still-open HPC/proof boundaries with `--no-skip` command wording.
3. Add a `CHANGELOG.md` breadcrumb for the canonical route audit and the stash-note pointer so later slices can recover the new route judgment without replaying the full S03 artifact history.

## Must-Haves

- [ ] The finished canonical doc advances `R003`, `R004`, and `R005` explicitly and does not overstate unresolved HPC proof as completed work.
- [ ] The stash note and changelog both point back to `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` instead of creating a second competing source of truth.

## Done when

- The canonical doc includes the risk register plus requirement coverage, the Chinese-friendly stash note exists, and `CHANGELOG.md` records both artifacts as the new route-audit breadcrumbs.

## Inputs

- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
- `docs/stashes/2026-04-06-007-phase4-berkeley-mask-bbox-oom-fix.md`
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md`
- `docs/stashes/2026-04-05-007-phase41-gwd30-manifest-list-hpc-sharding.md`
- `docs/stashes/2026-04-05-009-phase41-gwd30-pixel-reduce-then-mask-merge.md`
- `docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md`
- `docs/plans/2026-03-19-005-feat-phase4-trend-analysis-plan.md`
- `docs/plans/2026-03-23-feat-phase4-trend-analysis-implementation-plan.md`
- `CHANGELOG.md`

## Expected Output

- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
- `docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md`
- `CHANGELOG.md`

## Verification

`rg -n '^## (Risk Register|Requirement Coverage)$' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
`rg -n 'R003|R004|R005|HPC-only proof gap|_staging|historical/stale' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
`test -s docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md`
`rg -n 'S03-ROUTE-AUDIT-RISK-REGISTER.md|当前推荐路线|避免|Open Proof Gaps|--no-skip' docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md`
`rg -n 'S03-ROUTE-AUDIT-RISK-REGISTER.md|route audit|risk register|docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md' CHANGELOG.md`
