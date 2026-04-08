# Knowledge

## 2026-04-07 — GSD worktree memory-path boundary

- In the M001 GSD audit worktree, the project history path cited by older notes — `../../.claude/projects/-Users-mac-Code-WA/memory` — is **not** locally reachable and should be treated as `absent-local`.
- Do not assume that older recovery notes implying that memory path is readable still hold inside `.gsd/projects/.../worktrees/...` execution contexts.
- For audit work, prefer locally present evidence surfaces first (`docs/stashes/`, `docs/plans/`, `CHANGELOG.md`, `.gsd/*`) and record the `.claude` memory path as a proof boundary unless it is explicitly materialized.

## 2026-04-07 — Route-drift weighting for WA

- In this repo, an `active` plan file can become partially stale within a day if later `CHANGELOG.md` entries and terminal stash summaries record the implementation pivot.
- For current-route judgment, weight the latest changelog entries plus late stash summaries over older `active` plan text when they disagree, and treat the plan as intent/background unless newer evidence confirms it.

## 2026-04-07 — Phase 4 route-split rule for S02/S03

- When judging current Phase 4 state, treat the 2026-04-06 Stage-1 / Stage-2 regional chain as the live route and the 2026-04-05 full-tropics cache/reducer chain as `historical/stale path` unless newer evidence explicitly reopens it.
- Do not collapse those two Phase 4 branches into one status row: the point of the split is to preserve chronology and prevent stale full-tropics plans from being mistaken for the current re-entry path.

## 2026-04-07 — Module-family grading rule for S02

- When S02 grades a module family that spans multiple phases, grade the core module against the phase that actually proves that implementation surface; do not automatically downgrade it just because later presentation or continuation phases remain unverified.
- Example in this repo: the `fine-grained comparison` core in `src/WA/comparison/fine_grained.py` can stay `validated` from Phase 3 even though later Phase 3.6 / 3.7 hotspot-delivery paths still have HPC-only proof gaps.

## 2026-04-07 — Visualization-test boundary for S02

- In this repo, synthetic plotting tests that only prove PNG/cache writing (for example `tests/test_phase3_7_plotting.py` or `tests/test_visualization/test_phase4.py`) are sufficient evidence that the renderer exists, but **not** sufficient evidence that the end-to-end scientific output route is validated.
- When S02 grades cross-phase visualization families, keep them `implemented-but-unverified` unless there is fresh proof that the current real analysis outputs, remote imagery inputs, and HPC/runtime path were all exercised together.

## 2026-04-07 — Serialize GSD requirement updates

- In this repo's GSD tooling, running multiple `gsd_requirement_update` writes in parallel can leave `.gsd/REQUIREMENTS.md` rendered from only one of them even if each tool call reports success.
- Apply requirement updates sequentially and re-read `.gsd/REQUIREMENTS.md` after the write when the rendered requirement text is itself part of the task's verification surface.

## 2026-04-07 — S03 route-audit precedence for re-entry

- For Phase 4 continuation after M001/S03, treat `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` as the authoritative route-truth document.
- Use `docs/stashes/2026-04-07-004-m001-s03-route-audit-reentry.md` and the 2026-04-07 `CHANGELOG.md` bullets only as recovery breadcrumbs back to that canonical artifact, not as competing summaries.
- If older 2026-04-05/2026-04-06 plan, stash, or changelog text disagrees, prefer the S03 canonical audit plus current code unless newer evidence explicitly supersedes it.

## 2026-04-07 — S04 execution-map precedence and narrow-first ladder

- After M001/S04, treat `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` as the execution-order source of truth; it sequences S03 route truth plus S02 proof boundaries and should be used before copying commands from stash notes or changelog bullets.
- The safe first ladder is fixed as: direct Stage 1 `scripts/build_phase4_gwd30_pixel_stats.py --year 2016 --no-skip`, then Stage 2 `scripts/run_phase4_regional.py --dataset-id gwd30 --region amazon --start-year 2016 --end-year 2016 --no-skip`, then wider years or wrappers only after those proofs pass.
- Do not start with the broad submit wrapper or default invocations when re-entering Phase 4, because those surfaces silently fan out if year/dataset/region filters are omitted.

## 2026-04-07 — S05 recovery-pack precedence

- After M001/S05, treat `.gsd/milestones/M001/slices/S05/S05-OPERATOR-RECOVERY-PACK.md` as the first-stop recovery index, `.gsd/milestones/M001/slices/S03/S03-ROUTE-AUDIT-RISK-REGISTER.md` as route truth, and `.gsd/milestones/M001/slices/S04/S04-NEXT-STEP-EXECUTION-MAP.md` as execution truth.
- Later stash notes and changelog bullets must remain subordinate breadcrumbs back to those canonical artifacts; they do not regain equal weight just because they are newer or shorter.
- If a future re-entry note needs live commands or ordered continuation steps, send readers back to S04 instead of re-copying the ladder into another summary.

## 2026-04-07 — M001 closeout boundary

- Completing M001 means the audit/recovery control plane is verified and packaged; it does **not** mean the Stage-1 / Stage-2 Phase 4 route has been freshly re-proven on HPC.
- Future milestones should treat `M001-SUMMARY.md` plus the `S05 -> S03 -> S04 -> S02 -> S01` chain as planning truth, then still demand new HPC proof before promoting the current route from `current-but-unproven` to operationally revalidated.
- When a roadmap has no separate success-criteria section, use the slice overview `After this` outcomes as the practical milestone verification surface and check them against the owning canonical artifacts rather than inventing a second checklist.

## 2026-04-07 — Prefer related tests over full-suite reruns

- User override: do **not** default to `python -m pytest tests/` for routine code changes in this repo; prefer the smallest related pytest subset that matches the touched files.
- Use `docs/testing/test-categories.md` plus `python scripts/run_related_tests.py <changed-paths...>` to infer the default subset.
- Broaden beyond the related subset only when a patch crosses multiple test families, touches shared infrastructure, or the user explicitly asks for a broader run.

## 2026-04-09 — Phase 4 hotspot-family source of truth in this snapshot

- For M002/S04 work in this repo snapshot, the planner references `src/WA/comparison/percentage_hotspots.py` and `src/WA/comparison/classification_contract.py`, but those modules do **not** exist locally.
- The safe source of truth is the evidence-contract artifact semantics in `src/WA/comparison/evidence_contract.py` plus the on-disk family manifests/CSVs (`hotspot_manifest`, `classification_hotspot_manifest`, `trend_hotspot_manifest`), not the stale planner module paths.
- When extending the unified hotspot ledger, add semantic reloaders around those contract artifact families instead of inventing new imports just to match an outdated plan snapshot.

## 2026-04-09 — `run_related_tests.py` is advisory, not executable verification

- In this repo, `python scripts/run_related_tests.py <changed-paths...>` only prints the matched categories and the recommended pytest command; it does **not** run the tests for you.
- When a task or slice says to use related tests for verification, treat `run_related_tests.py` as the selector and then execute the suggested `python -m pytest ...` subset separately if you still owe a real test run.
- This matters for closeout work like M002/S04 where the combined Phase 4 related subset is broader than the focused task-level tests and is the practical replacement for a full-suite rerun.

## 2026-04-09 — `resolve_phase4_region_ids(..., [])` is not a neutral no-op

- In this repo, `src/WA/comparison/phase4_regional.py::resolve_phase4_region_ids(...)` treats an empty requested list as "all macro + priority regions", not as "no explicit selection".
- When a CLI needs to distinguish `--subset ten` from `--region ...`, inspect the raw `--region` args before calling that helper; otherwise a subset-only call can be misclassified as an ambiguous mixed selector.
- This matters for `scripts/run_phase4_regional.py`, which must preserve legacy no-arg behavior while still letting the contract-backed `ten` subset route stay explicit and reproducible.
