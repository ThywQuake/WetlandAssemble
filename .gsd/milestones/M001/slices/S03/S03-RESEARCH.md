# S03 — Research

**Date:** 2026-04-07

## Summary

S03 directly owns `R003`, `R004`, and `R005`. This slice is documentation-first, but it cannot be solved by reading plans alone because the Phase 4 route text drifted within 48 hours. The strongest evidence order is: S02 matrix → current source code → 2026-04-06 changelog/stashes → older 2026-04-05 full-tropics stashes/plans. Read in that order. That sequence shows the repo now contains three different Phase 4 route families: (1) the current GWD30 continuation path (`Stage 1 pixel-stats -> Stage 2 regional tables`), (2) a still-present but superseded full-tropics reducer chain, and (3) an older broad trend-analysis lane (`trends.py` / `trend_agreement.py` / `hpc_probe_trends.py`) that is partially implemented but not wired into a canonical batch runner.

The main S03 deliverable should therefore be one canonical route-audit artifact, not another narrative summary. It should explicitly separate **Current recommended route**, **Supporting but non-primary routes**, and **Historical/stale routes**, then close with a risk register. This follows the installed `doc-coauthoring` / `document-review` pattern: keep one reader-facing canonical doc, cite exact files and commands, and avoid scattering route judgment across more stash notes.

Do not treat `status: active` in old Phase 4 plan files as current truth. Newer 2026-04-06 changelog + stash evidence overrides them, and the code confirms the current `gwd30` regional path now reads `results/phase4/pixel_stats/.../tile_manifest.json` rather than the old full-tropics cache or direct `_staging` restore. Also note one important mismatch for the risk register: `hpc_probe_trends.py` still loads GWD30 from `_staging` via `load_trend_surface()`, so the trend-probe lane is not yet aligned with the newer Stage-1 pixel-stats regional lane.

## Recommendation

Create `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` as the canonical S03 artifact with four required blocks:

1. **Current recommended routes**
   - Primary mainline: `scripts/build_phase4_gwd30_pixel_stats.py`
   - Primary HPC batch wrapper: `scripts/submit_phase4_gwd30_pixel_stats.sh`
   - Next local/HPC continuation: `scripts/run_phase4_regional.py`
   - State clearly that this route currently closes **regional table generation**, not the full region-targeted trend-analysis story.

2. **Supporting but non-primary routes**
   - `scripts/hpc_probe_trends.py` + `src/WA/comparison/trends.py` / `trend_agreement.py`
   - classify as diagnostic/supporting, not the canonical continuation entrypoint, because it still reads GWD30 staged tiles directly from `_staging` and no `scripts/run_phase4_trend_analysis.py` exists.

3. **Historical/stale or misleading routes**
   - full-tropics reducer chain:
     `scripts/submit_phase4_gwd30_tropical_shards.sh`
     `scripts/build_phase4_gwd30_shard_lists.py`
     `scripts/run_phase4_gwd30_tropical_shard.py`
     `scripts/reduce_phase4_gwd30_tropical_shards.py`
   - stale broad plan expectations:
     `docs/plans/2026-03-19-005-feat-phase4-trend-analysis-plan.md`
     `docs/plans/2026-03-23-feat-phase4-trend-analysis-implementation-plan.md`
     `docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md`
   - explain why each can mislead: still marked `active`, still referenced by tests/docs, or still mentions missing/bypassed entrypoints.

4. **Risk register**
   - stage-numbering drift (`Stage 2 regional integration` vs `Stage 2 region-targeted trend analysis` vs implied `Stage 3`)
   - changelog drift on 2026-04-06 (same section describes both pixel-stats manifests and direct `_staging` restore)
   - HPC-only proof gap for the new Stage-1/Stage-2 route
   - unaligned GWD30 inputs between regional lane (pixel stats) and trend probe lane (staged tiles)
   - old active plans and tested old scripts make stale routes look current

Keep S03 doc-only unless a contradiction forces a tiny metadata update. A small Chinese re-entry stash note under `docs/stashes/` is worth producing after the canonical doc, but S03 should treat the `.gsd` artifact as the source of truth and the stash note as a pointer only.

## Implementation Landscape

### Key Files

- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` — new canonical artifact to create; should hold the current/supporting/stale route tables plus the risk register for `R003` / `R004` / `R005`.
- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` — canonical upstream evidence base; already splits Phase 4 into current Stage-1 / Stage-2 vs historical full-tropics reducer and lists open proof gaps. Start here.
- `src/WA/comparison/phase4_regional.py` — source-of-truth for the current regional `gwd30` path. `compute_phase4_region_dataset_table()` dispatches `gwd30` to `build_phase4_gwd30_monthly_series_from_pixel_stats_tiles()`, which reads `results/phase4/pixel_stats/.../tile_manifest.json`.
- `scripts/build_phase4_gwd30_pixel_stats.py` — current Stage-1 builder entrypoint; writes Stage-1 tile manifests consumed by the current regional route.
- `scripts/submit_phase4_gwd30_pixel_stats.sh` — current HPC batch wrapper for Stage-1; uses per-year jobs and respects `--no-skip`.
- `scripts/run_phase4_regional.py` — current Stage-2 entrypoint, but it builds/writes regional tables only. Important for S03 because several notes casually call this “trend analysis,” which overstates what the script actually does.
- `src/WA/comparison/trends.py` — still owns `load_trend_surface()`, `compute_pixel_trends()`, and `build_gwd30_native_pixel_statistics_tiles()`. The GWD30 trend path still restores `_staging/gwd30_<year>/stage_shard_*.json`, so it is a supporting route, not the same as the current regional pixel-stats chain.
- `scripts/hpc_probe_trends.py` — current diagnostic probe for trend code. Useful as a secondary route in the audit, but not the canonical continuation entrypoint.
- `scripts/submit_phase4_gwd30_tropical_shards.sh` — strong stale-route marker; still present and still has tests, but newer 2026-04-06 evidence explicitly demotes it after HPC OOMs.
- `tests/test_comparison/test_phase4_regional.py` — proves both old and new `phase4_regional.py` helper surfaces exist; cite carefully because passing tests do not mean the route is still recommended.
- `tests/test_comparison/test_trends.py` — proves the broad trend-analysis code exists, including GWD30 staged-tile loading, but does not prove that broad trend route is the current continuation path.
- `tests/test_submit_phase4_gwd30_pixel_stats.py` — evidence that the current submit wrapper exists and produces the expected SLURM scripts.
- `tests/test_submit_phase4_gwd30_tropical_shards.py` — evidence that the stale full-tropics submit wrapper still exists and therefore can still mislead operators.
- `docs/stashes/2026-04-06-003-phase4-conversation-summary.md` — strongest compact current-route summary: new Stage-1 builder, old reducer OOM, current route recommendation, and explicit HPC gap.
- `docs/stashes/2026-04-06-005-phase4-stage2-pixel-stats-regional-integration.md` — strongest evidence that `run_phase4_regional.py` now consumes Stage-1 pixel-statistics tiles.
- `docs/stashes/2026-04-06-007-phase4-berkeley-mask-bbox-oom-fix.md` — proof that a real remaining risk sat before Stage-2 tile processing, which matters for the risk register.
- `docs/stashes/2026-04-06-008-phase4-recall-entry.md` — explicit operator-facing recommendation to resume from Stage 1 / Stage 2 instead of the old full-tropics reducer route.
- `docs/stashes/2026-04-05-007-phase41-gwd30-manifest-list-hpc-sharding.md` and `docs/stashes/2026-04-05-009-phase41-gwd30-pixel-reduce-then-mask-merge.md` — best historical/stale-route evidence for the full-tropics reducer chain.
- `docs/stashes/2026-04-05-003-phase4-gwd30-staged-trend-loading.md` — best evidence that the trend probe lane remained `_staging`-based and never became the same route as the newer pixel-stats regional lane.
- `docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md` — still `status: active` but now partly stale because its described regional path no longer matches the actual pixel-stats code path.
- `docs/plans/2026-03-19-005-feat-phase4-trend-analysis-plan.md` and `docs/plans/2026-03-23-feat-phase4-trend-analysis-implementation-plan.md` — background only. They still describe a broad Phase 4 batch workflow, but `scripts/run_phase4_trend_analysis.py` is missing, so these files should be cited as stale/misleading background, not live entrypoint docs.
- `CHANGELOG.md` — route timeline. Use it for chronology, but do not treat every bullet as internally consistent; the 2026-04-06 section contains both the newer pixel-stats description and an older direct `_staging` description.

### Build Order

1. **Lock the current code truth first.**
   Read `src/WA/comparison/phase4_regional.py`, `scripts/build_phase4_gwd30_pixel_stats.py`, `scripts/submit_phase4_gwd30_pixel_stats.sh`, and `scripts/run_phase4_regional.py` first. This prevents S03 from copying stale plan language about full-tropics caches or generic “trend analysis.”
2. **Then classify the competing route families.**
   Compare 2026-04-06 stash/changelog evidence against 2026-04-05 stash/plan evidence and split routes into:
   current mainline / supporting secondary / historical-stale.
3. **Then write the risk register.**
   Only after route classification should S03 record risks, because several risks are actually route-confusion problems rather than runtime bugs.
4. **Only then produce a compact stash note.**
   Keep the canonical reasoning in the `.gsd` artifact and use the stash note as a short Chinese re-entry pointer for S05/S04.

### Verification Approach

For a doc-only S03 implementation, structural verification is the correct proof class:

```bash
test -s .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md
rg -n '^## (Current Recommended Routes|Supporting but Non-Primary Routes|Historical/Stale or Misleading Routes|Risk Register|Requirement Coverage)$' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md
rg -n 'scripts/build_phase4_gwd30_pixel_stats.py|scripts/submit_phase4_gwd30_pixel_stats.sh|scripts/run_phase4_regional.py|scripts/hpc_probe_trends.py|scripts/submit_phase4_gwd30_tropical_shards.sh' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md
rg -n 'docs/stashes/2026-04-06-003|docs/stashes/2026-04-06-005|docs/stashes/2026-04-06-007|docs/stashes/2026-04-06-008|docs/stashes/2026-04-05-007|docs/stashes/2026-04-05-009|docs/plans/2026-04-05-phase41-gwd30-full-period-stage-optimization-plan.md|docs/plans/2026-03-23-feat-phase4-trend-analysis-implementation-plan.md' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md
rg -n 'R003|R004|R005' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md
```

If execution also writes the compact re-entry stash, add:

```bash
test -s docs/stashes/*m001-s03*route*audit*.md
```

Do **not** use passing tests alone as route truth. In this slice, tests are evidence that old and new surfaces still exist, not proof that they are equally current.

## Constraints

- S03 directly serves `R003`, `R004`, and `R005`; do not drift into S04-style execution mapping beyond naming the current entrypoints and handoff risks.
- Prefer the S02 matrix and actual current code over older `status: active` plan files when they disagree.
- Do not claim HPC success for the new Stage-1 / Stage-2 chain; the latest evidence still leaves that as external proof.
- Follow project HPC conventions in any cited commands: use `--no-skip`, not `--skip-existing`.
- Current live worktree status is clean (`git status --short` returned no output), so the old “many untracked files” warning in `2026-04-06-008` should be recorded as historical context, not a live risk in this worktree.

## Common Pitfalls

- **Collapsing all Phase 4 paths into one “current route”** — avoid this. There are at least three distinct route families in the repo, and S03 loses value if it merges them back together.
- **Using plan front matter as truth** — several Phase 4 plans still say `status: active`, but newer 2026-04-06 stash/changelog evidence and current code paths supersede them.
- **Calling `run_phase4_regional.py` a full trend-analysis runner** — it currently writes regional series tables; it is not the missing batch runner described in older plans.
- **Treating `hpc_probe_trends.py` as the primary continuation path** — it is a diagnostic/supporting route and still uses `_staging` GWD30 inputs, unlike the newer pixel-stats regional chain.
- **Repeating historical dirty-tree warnings** — the old recall note mentions a dirty worktree, but the current S03 worktree is clean.

## Open Risks

- **Stage vocabulary drift** — “Stage 2” is used for both regional integration and future region-targeted trend analysis in different notes; S03 should define a canonical glossary.
- **Changelog self-conflict on 2026-04-06** — the same date block describes both the pixel-stats manifest route and a direct `_staging` restore route for regional GWD30; S03 should mark source-code-backed truth as authoritative.
- **Trend/mainline divergence** — the regional `gwd30` route uses Stage-1 pixel stats, but `hpc_probe_trends.py` / `load_trend_surface()` still use staged-tile merges from `_staging`.
- **Missing batch runner** — older plans still mention `scripts/run_phase4_trend_analysis.py`, but that file is missing, so broad “Phase 4 complete” language is misleading if read as an operator entrypoint.
- **Old reducer path still looks alive** — the full-tropics shard/reduce scripts remain in tree, have tests, and have detailed plans/stashes, so they are easy to mistake for the mainline unless S03 explicitly demotes them.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Structured audit documentation | `doc-coauthoring` | available |
| Refining existing plan/doc surfaces before handoff | `document-review` | available |
