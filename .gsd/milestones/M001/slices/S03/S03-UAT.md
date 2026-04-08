# S03: Route Audit & Risk Register — UAT

**Milestone:** M001
**Written:** 2026-04-06T22:10:11.297Z

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S03 ships audit artifacts, route classification, and recovery breadcrumbs rather than executable runtime changes, so correctness is proven by the presence and contents of the generated documents.

## Preconditions

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md` already exists and remains the evidence-grade baseline.
- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` has been generated in this worktree.
- `docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md` and `CHANGELOG.md` are available locally.

## Smoke Test

Open `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` and confirm it contains `Current Recommended Routes`, `Supporting but Non-Primary Routes`, `Historical/Stale or Misleading Routes`, `Risk Register`, and `Requirement Coverage` in one canonical artifact.

## Test Cases

### 1. Current mainline is unambiguous

1. Read the `Current Recommended Routes` table in `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`.
2. Confirm the current route is stated as `scripts/build_phase4_gwd30_pixel_stats.py` or `scripts/submit_phase4_gwd30_pixel_stats.sh` feeding `scripts/run_phase4_regional.py`.
3. Confirm the same section explicitly says this route closes regional table generation today.
4. **Expected:** A fresh reader can identify the current mainline without consulting older plans or stash notes.

### 2. Supporting and stale routes are separated

1. Read the `Supporting but Non-Primary Routes` section.
2. Confirm `scripts/hpc_probe_trends.py` is described as a diagnostic/probe lane rather than the primary continuation path.
3. Read the `Historical/Stale or Misleading Routes` section.
4. Confirm the full-tropics shard/reduce family, older `_staging`-as-mainline wording, and the missing planned `scripts/run_phase4_trend_analysis.py` runner are all named explicitly.
5. **Expected:** The document distinguishes useful supporting routes from routes that should not be treated as the canonical continuation path.

### 3. Risks and recovery breadcrumbs carry forward the proof gaps

1. Read the `Risk Register` and `Requirement Coverage` sections in the canonical S03 audit.
2. Confirm the HPC-only proof gap, changelog self-conflict, stage-numbering drift, and GWD30 input divergence are all recorded without being presented as resolved.
3. Open `docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md`.
4. Confirm it points back to `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`, identifies the current route, lists routes to avoid, and preserves `--no-skip` HPC commands.
5. Open `CHANGELOG.md` and confirm the 2026-04-07 bullets reference both the canonical audit and the stash note as breadcrumbs.
6. **Expected:** The operator can recover the authoritative route quickly, while unresolved remote proof is still clearly visible as an open boundary.

## Edge Cases

### Older route evidence still exists in the tree

1. Compare the canonical S03 audit against older 2026-04-05 / 2026-04-06 plans, stashes, or changelog text that still reference direct `_staging` or full-tropics reducer flows.
2. **Expected:** The canonical S03 audit explicitly demotes those older paths and prevents them from being misread as the current mainline even though the old files and tests still exist.

## Failure Signals

- The canonical audit is missing one of the five required sections.
- The current route does not explicitly name the Stage-1 pixel-stats → Stage-2 regional chain.
- `scripts/hpc_probe_trends.py` is presented as interchangeable with the mainline rather than supporting-only.
- The stash note or changelog omits the pointer back to the canonical S03 audit.
- The document implies the HPC-only proof gap is already closed.

## Not Proven By This UAT

- No fresh HPC rerun of the Stage-1 / Stage-2 chain was performed here.
- This UAT does not prove that the trend probe input path and the regional Stage-1 pixel-stats route have been unified.
- This UAT does not prove that older stale scripts are safe to delete; it only proves they are now classified correctly for operators.

## Notes for Tester

- Treat `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` as the route-truth source.
- Use the stash note and changelog only as shortcuts back to that canonical document.
- If you later perform HPC verification, keep the `--no-skip` wording from the stash note so the proof run is fresh rather than cache-biased.
