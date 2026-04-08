---
estimated_steps: 10
estimated_files: 8
skills_used:
  - doc-coauthoring
  - document-review
---

# T01: Classify the live, supporting, and stale Phase 4 routes in one canonical audit artifact

Build the canonical S03 route-audit document first so route truth lives in one source of truth before any handoff note or changelog breadcrumb is written.

## Steps

1. Start `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` with a short evidence rule that treats the S02 matrix plus source-code-backed 2026-04-06 evidence as authoritative when older still-`active` plans disagree.
2. Populate `Current Recommended Routes`, `Supporting but Non-Primary Routes`, and `Historical/Stale or Misleading Routes` with concise tables that name the exact entry files, what each route actually does today, the strongest evidence anchors, and why the route is current, supporting, or stale.
3. Make the live chain explicit: `scripts/build_phase4_gwd30_pixel_stats.py` plus `scripts/submit_phase4_gwd30_pixel_stats.sh` feed `scripts/run_phase4_regional.py`, while `scripts/hpc_probe_trends.py` and the old full-tropics reducer lane remain non-primary or historical instead of interchangeable continuations.

## Must-Haves

- [ ] The canonical doc names the current mainline, the supporting diagnostic route, and the stale/misleading route family with concrete script/module paths.
- [ ] The current-route section states clearly that the recommended chain closes regional table generation today and does **not** imply the missing broad `run_phase4_trend_analysis.py` batch runner exists.

## Done when

- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` exists with the three route-classification sections and enough evidence anchors that a fresh reader can tell which entrypoints to continue from and which ones to avoid.

## Inputs

- `.gsd/milestones/M001/slices/S02/S02-PHASE-MODULE-MATRIX.md`
- `src/WA/comparison/phase4_regional.py`
- `src/WA/comparison/trends.py`
- `scripts/build_phase4_gwd30_pixel_stats.py`
- `scripts/submit_phase4_gwd30_pixel_stats.sh`
- `scripts/run_phase4_regional.py`
- `scripts/hpc_probe_trends.py`
- `docs/stashes/2026-04-06-003-phase4-conversation-summary.md`
- `docs/stashes/2026-04-06-005-phase4-stage2-pixel-stats-regional-integration.md`

## Expected Output

- `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`

## Verification

`test -s .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
`rg -n '^## (Current Recommended Routes|Supporting but Non-Primary Routes|Historical/Stale or Misleading Routes)$' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
`rg -n 'scripts/build_phase4_gwd30_pixel_stats.py|scripts/submit_phase4_gwd30_pixel_stats.sh|scripts/run_phase4_regional.py|scripts/hpc_probe_trends.py|scripts/submit_phase4_gwd30_tropical_shards.sh' .gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md`
