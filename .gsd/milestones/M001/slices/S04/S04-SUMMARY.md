---
id: S04
parent: M001
milestone: M001
provides:
  - A canonical execution-order artifact that tells the next operator what to read first, what to run first, what proves success, and which stale routes or flags to avoid.
  - A compact Chinese-friendly breadcrumb plus refreshed project metadata that point back to the canonical S04 map instead of creating a second source of truth.
requires:
  - slice: S02
    provides: The Phase 4 proof-boundary row and Open Proof Gaps baseline that S04 sequences into an operator run order.
  - slice: S03
    provides: The authoritative Phase 4 route-truth judgment and stale-route demotions that S04 converts into a concrete continuation ladder.
affects:
  - S05
key_files:
  - .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md
  - docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md
  - CHANGELOG.md
  - .gsd/REQUIREMENTS.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - Treat `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` as a sequencing layer that operationalizes S03 route truth plus S02 proof boundaries rather than replacing either source.
  - Freeze the first execution ladder as direct Stage 1 `--year 2016 --no-skip`, then Stage 2 `gwd30 + amazon + 2016-2016 --no-skip`, and only widen after those proofs pass.
  - Keep the Chinese stash note and changelog entry as breadcrumbs back to the canonical S04 map instead of letting them become alternate execution maps.
patterns_established:
  - When the main risk is route mis-entry rather than missing code, ship one canonical execution-order artifact that combines read order, commands, proof targets, and avoid-first guardrails.
  - Use exact artifact paths and log markers as exit criteria so future HPC reruns can be judged without reinterpretation.
  - Keep recovery breadcrumbs subordinate to canonical `.gsd` artifacts so compressed notes do not regain authority over the primary source.
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M001/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S04/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-06T22:42:58.150Z
blocker_discovered: false
---

# S04: Next-Step Execution Map

**Published the canonical execution-order map that tells the next operator what to read first, what to run first, what files prove success, and which stale Phase 4 routes and flags to avoid.**

## What Happened

S04 turned the S03 route judgment plus the S02 proof-boundary matrix into one concrete continuation artifact. T01 created `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` and explicitly framed it as a sequencing layer: S03 remains route truth, S02 remains proof boundary, and S04 tells the operator how to act on those conclusions without re-arguing route history. The map fixes the narrow-first ladder as direct Stage 1 `scripts/build_phase4_gwd30_pixel_stats.py --year 2016 --no-skip`, then Stage 2 `scripts/run_phase4_regional.py --dataset-id gwd30 --region amazon --start-year 2016 --end-year 2016 --no-skip`, with broader wrappers or wider year ranges deferred until those proofs pass. It also locks the proof contract to the exact artifact paths and log marker that matter: `results/phase4/pixel_stats/gwd30/gwd30_2016/monthly/tile_manifest.json`, the Berkeley-valid regional mask cache, the GWD30 regional cache, `results/phase4/tables/amazon.csv`, and the `Phase4 cache write: gwd30_native_pixel_stats` log line. T02 then completed the slice-level handoff around that canonical map. It added explicit `Requirement Coverage` for R006 while preserving inherited R003 and R005 boundaries, wrote `docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md` as a compact Chinese-friendly breadcrumb back to the canonical map, and updated `CHANGELOG.md` plus `.gsd/REQUIREMENTS.md` so the ordered continuation route is easy to recover without implying that a fresh HPC rerun already happened. During slice closeout, R006 validation was recorded in `.gsd/DECISIONS.md` as D020, `.gsd/KNOWLEDGE.md` gained an explicit S04 execution-map precedence rule with the narrow-first ladder, and `.gsd/PROJECT.md` was refreshed so S05 inherits S04 as the execution-order source of truth.

## Verification

All nine slice-plan checks passed: the canonical map exists; its `Canonical Read Order`, `Ordered Continuation Path`, `Proof Targets / Exit Criteria`, `Do Not Touch First`, and `Requirement Coverage` sections are present; the live entry scripts, stale route family, missing runner, and stale flags are named explicitly; the proof-target section contains the exact Stage-1 log marker plus the required Stage-1 and Stage-2 artifact paths; the Chinese-friendly stash breadcrumb exists and contains the `2016`, `amazon`, `当前`, `避免`, and `--no-skip` markers; `.gsd/REQUIREMENTS.md` maps R006 to the canonical S04 artifact; and `CHANGELOG.md` points back to the canonical map and breadcrumb. `gsd_milestone_status` confirmed S04 had 2/2 tasks complete. Verification stayed artifact-driven because S04 changed documentation and metadata only.

## Requirements Advanced

- R003 — Operationalized the S03 route-truth judgment into an explicit operator ladder without reopening route classification.
- R005 — Preserved the open proof-gap boundary by binding route success to the exact Stage-1 and Stage-2 proof artifacts and log marker.

## Requirements Validated

- R006 — `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` now provides the milestone’s concrete, ordered continuation route, including the canonical read order, the narrow-first `2016 -> amazon` execution ladder, exact proof targets, and the avoid-first guardrails.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

S04 clarifies execution order but does not itself produce fresh HPC proof: the Stage-1 builder and Stage-2 regional runner still need to be rerun remotely with `--no-skip` before the route counts as freshly re-proven. The broad wrapper and default invocations still exist and still widen silently if a future operator omits year, dataset, or region filters. `scripts/hpc_probe_trends.py` remains a supporting diagnostic lane rather than a converged mainline.

## Follow-ups

S05 should package the S01/S02/S03/S04 canonical artifacts into a compact recovery pack and must point readers back to S04 for the actual command ladder instead of duplicating it. The next real execution milestone should rerun Stage 1 for `--year 2016 --no-skip` and Stage 2 for `gwd30 + amazon + 2016-2016 --no-skip` on HPC, then check the exact S04 proof-target artifacts before widening scope.

## Files Created/Modified

- `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` — Canonical execution-order artifact sequencing S03 route truth plus S02 proof boundaries into the narrow-first `2016 -> amazon` ladder with exact proof targets and avoid-first guardrails.
- `docs/stashes/2026-04-07-008-m001-s04-next-step-execution-map-reentry.md` — Compact Chinese-friendly breadcrumb pointing operators back to the canonical S04 execution map while preserving the `--no-skip` narrow-first ladder.
- `CHANGELOG.md` — 2026-04-07 breadcrumb entry linking the changelog back to the canonical S04 execution map and compact stash note.
- `.gsd/REQUIREMENTS.md` — Requirement register now maps R006 validation to the finished S04 execution map artifact.
- `.gsd/DECISIONS.md` — Decision register now includes D020 recording R006 as validated by the S04 execution map.
- `.gsd/KNOWLEDGE.md` — Knowledge base now records S04 execution-map precedence and the fixed narrow-first `2016 -> amazon` recovery ladder.
- `.gsd/PROJECT.md` — Project state refreshed so downstream slices inherit S04 as complete and treat the execution map as the run-order source of truth.
