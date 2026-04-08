---
id: M001
title: "Current-State Audit and Recovery Control Plane"
status: complete
completed_at: 2026-04-06T23:23:44.851Z
key_decisions:
  - Kept M001 analysis-first and evidence-graded rather than mixing the audit with new scientific implementation or broad cleanup.
  - Separated raw evidence freeze (S01) from status, route, execution, and recovery interpretation layers (S02-S05).
  - Used S02 as the single canonical phase/module grading surface with explicit `Local evidence` versus `HPC / external proof` fields.
  - Set the current Phase 4 mainline to Stage-1 GWD30 pixel statistics feeding Stage-2 regional execution, while demoting stale full-tropics and missing-runner routes.
  - Froze a narrow-first `2016 -> amazon` execution ladder with exact proof targets before any scope widening.
  - Set recovery precedence to `S05 -> S03 -> S04 -> S02 -> S01` so compact notes remain breadcrumbs instead of competing sources of truth.
key_files:
  - .gsd/milestones/M001/slices/S01/S01-INVENTORY.md
  - .gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md
  - .gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md
  - .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md
  - .gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md
  - .gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md
  - docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md
  - CHANGELOG.md
  - .gsd/REQUIREMENTS.md
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
lessons_learned:
  - In this repository, recent changelog plus stash evidence can outweigh older still-active plans; route truth needs one canonical owner to prevent drift.
  - Documentary milestones still require integration verification: the artifact hierarchy and cross-links matter as much as individual file creation.
  - For Phase 4 re-entry, 'current route' and 'freshly proven on HPC' must remain separate states or the project will manufacture false closure.
  - Narrow-first commands with explicit year, dataset, and region filters are essential because broad Phase 4 wrappers silently widen scope on re-entry.
---

# M001: Current-State Audit and Recovery Control Plane

**M001 closed the repository audit by freezing canonical inventory, status, route, execution, and recovery artifacts and validating R001-R008 without claiming fresh HPC rerun proof.**

## What Happened

M001 stayed analysis-first from start to finish and assembled a layered recovery control plane rather than extending scientific implementation. S01 froze the replayable evidence base in `S01-INVENTORY.md` plus `S01-DRIFT-BOUNDARIES.md`, including explicit absent-local and external/HPC proof boundaries and a `python -m pytest --collect-only -q` run that collected 418 tests. S02 converted that fact base into the canonical evidence-graded phase/module matrix, made the current-vs-historical Phase 4 split explicit, and separated `Local evidence` from `HPC / external proof` across the matrix. S03 resolved route ambiguity by publishing one canonical Phase 4 route audit and risk register, setting Stage-1 pixel statistics feeding Stage-2 regional execution as the current mainline while demoting the older full-tropics reducer family and the missing broad batch runner. S04 converted that route truth plus the S02 proof boundary into the ordered narrow-first execution ladder, with exact proof targets and avoid-first guardrails. S05 then packaged the whole milestone into a first-stop operator recovery index and froze the precedence chain `S05 -> S03 -> S04 -> S02 -> S01` so later breadcrumbs stay subordinate to canonical artifacts.

For milestone closeout, `main` was not present in this repository, so the equivalent integration diff used `git diff --stat HEAD $(git merge-base HEAD refactor/loader-reference-grid-alignment) -- ':!.gsd/'`. That diff showed non-`.gsd/` changes in `CHANGELOG.md` and `docs/stashes/*`, confirming that M001 produced repository-visible outputs outside `.gsd/` even though it intentionally avoided runtime Python changes. I also verified milestone state with `gsd_milestone_status`, which showed all five slices complete with all tasks done, confirmed all slice summaries exist, and spot-checked the canonical artifact chain: the S02 matrix still exposes `Local evidence`, `HPC / external proof`, and `Open Proof Gaps`; the S03 audit still exposes `Current Recommended Routes`, `Historical/Stale or Misleading Routes`, and `Risk Register`; the S04 map still exposes `Canonical Read Order`, `Ordered Continuation Path`, `Proof Targets / Exit Criteria`, and `Do Not Touch First`; and the S05 pack still routes operators back to S01/S02/S03/S04 instead of duplicating them.

This milestone therefore delivers an authoritative audit and recovery control plane, not remote execution closure. The current continuation path is clear, the stale routes are named, the proof boundaries are explicit, and the next milestone can begin from a stable control surface. What remains open is the real HPC rerun gap: the Stage-1 GWD30 pixel-statistics builder and Stage-2 regional runner still need fresh proof in the target environment before the route counts as revalidated in execution terms.

## Decision Re-evaluation

| Decision | Still valid? | Closeout evidence | Revisit next milestone? |
| --- | --- | --- | --- |
| D001 — keep M001 as an analysis-first recovery milestone | Yes | All delivered outputs are audit/control-plane artifacts, and the milestone met its outcomes without mixing in new scientific implementation. | No |
| D002 — use evidence grades (`validated`, `implemented-but-unverified`, `historical/stale path`, `unclear`) | Yes | S02 became the shared grading surface consumed by S03, S04, and S05. | No |
| D006 — keep raw evidence freeze separate from interpretation | Yes | The S01 inventory/drift split was reused cleanly by downstream slices and reduced re-derivation. | No |
| D009 / D018 — current Phase 4 mainline is Stage-1 pixel stats feeding Stage-2 regional | Yes, conditionally | S03, S04, S05, REQUIREMENTS, PROJECT, and KNOWLEDGE all converge on the same route truth. | Yes — revisit only after fresh HPC proof lands |
| D019 — freeze the narrow-first `2016 -> amazon` ladder before widening | Yes, conditionally | S04 proof targets and S05 recovery guidance consistently point to the narrow-first ladder. | Yes — widen only after Stage-1/Stage-2 proof passes |
| D022 — recovery precedence is `S05 -> S03 -> S04 -> S02 -> S01` | Yes | The pack, breadcrumb, changelog, project state, and knowledge base all reinforce the same hierarchy. | No |

Horizontal checklist: none was defined in `M001-ROADMAP.md`, so no extra horizontal items remained open at closeout.

## Success Criteria Results

## Success Criteria Verification

- [x] **Canonical surface inventory exists, so re-entry no longer starts from blind exploration.**
  - Evidence: S01 produced `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` plus `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md`, captured replayable repository counts and proof boundaries, and verified the inventory with `python -m pytest --collect-only -q` collecting 418 tests.

- [x] **Each major phase and module has an evidence-backed status grade, with local proof separated from HPC-only proof.**
  - Evidence: S02 produced `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`; closeout spot-checks confirmed the matrix still contains `Local evidence`, `HPC / external proof`, and `Open Proof Gaps` and that R002/R007 are rendered as validated against it.

- [x] **Current recommended routes, stale/misleading routes, and risks are explicit.**
  - Evidence: S03 produced `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`; closeout spot-checks confirmed the `Current Recommended Routes`, `Historical/Stale or Misleading Routes`, and `Risk Register` sections remain present and aligned with the validated requirement text for R003-R005.

- [x] **There is a concrete continuation path showing where to enter next, what to verify first, and which routes to avoid touching first.**
  - Evidence: S04 produced `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md`; closeout spot-checks confirmed `Canonical Read Order`, `Ordered Continuation Path`, `Proof Targets / Exit Criteria`, and `Do Not Touch First` are present and that the narrow-first `2016 -> amazon` ladder remains the canonical next step.

- [x] **A future re-entry can recover control quickly from compact milestone artifacts instead of replaying the entire repository history.**
  - Evidence: S05 produced `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` plus `docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md`; closeout spot-checks confirmed the pack points operators back to S01/S02/S03/S04 by question rather than duplicating those surfaces.

- [x] **Repository-visible changes exist outside `.gsd/`.**
  - Evidence: because `main` does not exist in this repo, the equivalent integration diff was `git diff --stat HEAD $(git merge-base HEAD refactor/loader-reference-grid-alignment) -- ':!.gsd/'`; it showed non-`.gsd/` changes in `CHANGELOG.md` and `docs/stashes/*`. M001 remained documentary by design, but it did not collapse into `.gsd/`-only state.

## Definition of Done Results

## Definition of Done Verification

`M001-ROADMAP.md` does not define a separate Definition of Done section, so closeout used the milestone completion contract plus the roadmap slice overview as the definition-of-done surface.

- [x] **All slices complete.**
  - Evidence: `gsd_milestone_status` reported S01-S05 all `complete` with task counts `2/2`, `5/5`, `2/2`, `2/2`, and `2/2` respectively.

- [x] **All slice summaries exist.**
  - Evidence: closeout file checks confirmed `.gsd/milestones/M001/slices/S01/S01-SUMMARY.md` through `.gsd/milestones/M001/slices/S05/S05-SUMMARY.md` are all present and non-empty.

- [x] **Cross-slice integration points work.**
  - Evidence: spot-checks confirmed the canonical chain is intact: S02 still exposes proof-boundary grading; S03 still exposes current-vs-stale route judgment; S04 still exposes the ordered execution contract; and S05 still routes operators back to S01/S02/S03/S04 rather than creating a competing summary layer.

- [x] **Requirement outcomes are internally consistent with slice ownership.**
  - Evidence: `.gsd/REQUIREMENTS.md` already maps R001-S01, R002/R007-S02, R003/R004/R005-S03, R006-S04, and R008-S05, matching the actual delivered artifacts.

- [x] **Horizontal checklist addressed.**
  - Evidence: no `Horizontal Checklist` section exists in `M001-ROADMAP.md`, so there were no extra horizontal items to retire.

## Requirement Outcomes

## Requirement Status Transitions

- **R001 — active -> validated**
  - Evidence: `.gsd/milestones/M001/slices/S01/S01-INVENTORY.md` plus `.gsd/milestones/M001/slices/S01/S01-DRIFT-BOUNDARIES.md` provide the canonical inventory and proof-boundary freeze; S01 verification included `python -m pytest --collect-only -q` collecting 418 tests.

- **R002 — active -> validated**
  - Evidence: `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` restates D002, covers the full phase/module matrix, and cites concrete evidence anchors per row.

- **R003 — active -> validated**
  - Evidence: `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` names the current continuation chain as Stage-1 pixel-stats build/submit feeding `scripts/run_phase4_regional.py` and explicitly states that no repo-local broad `scripts/run_phase4_trend_analysis.py` mainline exists.

- **R004 — active -> validated**
  - Evidence: the S03 audit’s `Historical/Stale or Misleading Routes` section explicitly lists the demoted full-tropics reducer family, older `_staging`-as-mainline wording, and the missing planned batch runner, with misread risks.

- **R005 — active -> validated**
  - Evidence: the S03 `Risk Register` records stage-numbering drift, changelog self-conflict, the HPC-only rerun gap, GWD30 input divergence, and the misleading weight of older plans/tests.

- **R006 — active -> validated**
  - Evidence: `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` consolidates the canonical read order, narrow-first execution ladder, proof targets, and avoid-first guardrails.

- **R007 — active -> validated**
  - Evidence: the S02 matrix separates `Local evidence` from `HPC / external proof` across phase and module rows and closes with `Open Proof Gaps`.

- **R008 — active -> validated**
  - Evidence: `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` plus `docs/stashes/2026-04-07-009-m001-s05-operator-recovery-pack-reentry.md` provide a compact first-stop recovery layer that routes route truth back to S03 and execution copying back to S04.

## Unchanged Requirement States

- **Deferred remained deferred:** R020, R021, R022.
- **Out of scope remained out of scope:** R030, R031, R032.

All requirement transitions recorded during M001 are supported by concrete slice-owned artifacts and passed closeout re-verification.

## Deviations

No plan-invalidating deviations were found. One structural note: `M001-ROADMAP.md` did not carry separate Success Criteria, Definition of Done, or Horizontal Checklist sections, so closeout verification used the slice overview `After this` outcomes plus the required milestone completion checks (integration diff, slice completion, summary existence, and cross-artifact integration) as the verification contract.

## Follow-ups

Start M002 from the canonical recovery chain `S05 -> S03 -> S02 -> S04`. The first live proof to retire is still the narrow HPC rerun ladder from S04. Recommended commands to run on HPC after milestone closure are:

```bash
python scripts/build_phase4_gwd30_pixel_stats.py --year 2016 --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --aggregation monthly --worker-count 1 --no-skip
bash scripts/submit_phase4_gwd30_pixel_stats.sh --aggregation monthly --worker-count 1 --cpus 1 --time 480 --partition C064M0256G --no-skip
python scripts/run_phase4_regional.py --dataset-id gwd30 --region amazon --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --start-year 2016 --end-year 2016 --no-skip
```

Widen years, regions, or wrappers only after the Stage-1 log marker and S04 proof-target artifacts exist.
