# Knowledge

## 2026-04-09 — Trend submit preflight must use the selected repo interpreter

- `scripts/submit_phase4_trend_contract.sh` should resolve regions with the explicit `--python-bin` / repo environment, not bare `python3`.
- The wrapper imports `WA.comparison.evidence_contract` during preflight region resolution, and that import path can transitively require the repo's scientific stack before any job scripts are generated.
- If the wrapper fails before submission with `ModuleNotFoundError` followed by `No regions resolved for submission`, inspect the preflight interpreter first; the selector or regions file may be fine.

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

## 2026-04-09 — Trend checkpoints must separate requested windows from actual result coverage

- In this repo’s Phase 4 trend path, the user-requested window (for example `2000-01-01 .. 2004-12-31`) does not always match the last actual timestamp in the loaded surface (`2004-12-01` for month-start series).
- For resumable trend checkpoints, store both the requested window and the actual result time range; otherwise a valid checkpoint can be rejected later as "mixed metadata" just because the dataset cadence uses month starts or yearly anchors.
- This matters for `src/WA/comparison/trends.py`, where the checkpoint key should stay tied to the requested rerun window while the reloaded `TrendResult` still needs the actual observed time bounds for agreement math.

## 2026-04-09 — `run_related_tests.py` is advisory, not executable verification

- In this repo, `python scripts/run_related_tests.py <changed-paths...>` only prints the matched categories and the recommended pytest command; it does **not** run the tests for you.
- When a task or slice says to use related tests for verification, treat `run_related_tests.py` as the selector and then execute the suggested `python -m pytest ...` subset separately if you still owe a real test run.
- This matters for closeout work like M002/S04 where the combined Phase 4 related subset is broader than the focused task-level tests and is the practical replacement for a full-suite rerun.

## 2026-04-09 — `resolve_phase4_region_ids(..., [])` is not a neutral no-op

- In this repo, `src/WA/comparison/phase4_regional.py::resolve_phase4_region_ids(...)` treats an empty requested list as "all macro + priority regions", not as "no explicit selection".
- When a CLI needs to distinguish `--subset ten` from `--region ...`, inspect the raw `--region` args before calling that helper; otherwise a subset-only call can be misclassified as an ambiguous mixed selector.
- This matters for `scripts/run_phase4_regional.py`, which must preserve legacy no-arg behavior while still letting the contract-backed `ten` subset route stay explicit and reproducible.

## 2026-04-09 — NetCDF-safe string coords for contract percentage surfaces

- In this repo’s current NumPy/xarray/netCDF4 stack, building a `dataset_id` coordinate from a pandas index can produce NumPy `StringDType`, which `to_netcdf()` rejects with `unsupported dtype for netCDF4 variable`.
- For contract-backed multi-dataset percentage surfaces, force string-like coordinates such as `dataset_id` and `dataset_year_label` onto fixed-width unicode arrays before writing the NetCDF.
- This matters for `src/WA/comparison/percentage_backbone.py`, where the restored percentage contract surface stores a dataset stack and would otherwise fail at write time even though the xarray object looks valid in memory.

## 2026-04-09 — Classification contract must cross-check Phase 3.7 manifest ids, not just region filters

- In this repo, a Phase 3.7 hotspot CSV can look superficially valid for a target region even when one row’s `region_id` was mutated or the CSV drifted away from the manifest.
- For the restored Phase 4 classification contract, do not trust `phase3_7_hotspots_<year>.csv` by filtering `region_id` alone; first take the hotspot ids for that region from the Phase 3.7 manifest, then require the CSV rows for exactly those ids and reject any mixed-region mismatch.
- This matters for `src/WA/comparison/classification_contract.py`, where the adapter rewrites region hotspot families from the Phase 3.7 source trio and must fail closed on stale or hand-edited source tables.

## 2026-04-09 — Use readiness before wide ledger, and treat ledger failure as a diagnostic producer

- In this repo’s Phase 4 scale-out path, `scripts/run_phase4_scaleout_readiness.py` is the first operator check for `percentage / classification / trend` hotspot-family completeness across `--region`, `--subset canonical`, or `--subset ten`.
- Treat `missing` as “both manifest and CSV are absent”; treat partial pairs, semantic reload failures, mixed rows, or bad provenance as `partial` instead of collapsing everything into one missing state.
- `scripts/run_phase4_hotspot_ledger.py` remains fail-closed by design, but on failure it now auto-writes a single-region readiness CSV/JSON and logs family-specific paths/reasons. Use that report before re-running wide ledger jobs so operators do not debug from a naked first exception.

## 2026-04-09 — Unified-ledger reloads return parsed helper columns, not just CSV columns

- In this repo, `load_phase4_unified_hotspot_ledger(...)` / `load_contract_unified_hotspot_ledger(...)` return the original ledger columns **plus** parsed helper columns like `contract_metadata` and `line_specific`.
- If a downstream pack/export wants a deterministic CSV, re-select `UNIFIED_HOTSPOT_LEDGER_COLUMNS` before writing; otherwise pandas will serialize Python dict reprs for those helper columns and quietly change the output schema.
- This matters for `src/WA/visualization/phase4_pack.py`, which needs the semantic reload convenience in memory but must preserve the ledger’s stable on-disk column contract in the derived hotspot table.

## 2026-04-09 — Strict paper-pack proof depends on hotspot-family readiness, not just pack-safe reloads

- In this repo’s Phase 4 paper-pack path, semantic reload of percentage/classification/trend summaries and the unified ledger is **not** sufficient for a strict complete-pack claim.
- `build_phase4_evidence_pack_proof(...)` also depends on the three hotspot-family contract artifacts (`hotspot_manifest`, `classification_hotspot_manifest`, `trend_hotspot_manifest`) because scale-out readiness is the gate that authorizes a complete-pack claim.
- This matters for local dry runs and fixture design: a paper pack can render figures/tables from pack inputs while strict proof still reports `incomplete` until the readiness hotspot families exist and reload cleanly.

## 2026-04-09 — Pack consumers must reopen trend agreement through public contract helpers

- In this repo, trend-agreement semantic reopen is now owned by `src/WA/comparison/trend_contract.py`; downstream pack code should use the public comparison helpers or the thin wrappers in `src/WA/visualization/phase4.py`, not script-private helpers from `scripts/run_phase4_trend_contract.py`.
- Keep pair validation (surface + summary presence, `participant_set_key`, overlap window, and `region_id` checks) in the comparison layer so every caller gets the same fail-closed diagnostics.
- This matters for future paper-pack or proof code: guessing agreement filenames or duplicating reload logic will drift faster than the science contract and hides the exact `region_id` / participant context when a pair is malformed.

## 2026-04-09 — Auto-mode cannot satisfy the project HPC sync route without interactive OTP

- The project `sync-hpc` route resolves to `rsync`/`ssh` against `2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/`, with a Mac-local wrapper under `/Users/mac/.ssh/script/with_pkuhpc_auth.sh` in the normal user workflow.
- Inside this non-interactive container, the host is reachable, but both raw `ssh` and `rsync` fail at `OTP Verification Fail!` / `Permission denied (keyboard-interactive)` because there is no interactive terminal or `ssh-askpass` path to satisfy the challenge.
- For HPC-only tasks, treat that as an external execution boundary and preserve exact rerun commands/proof notes rather than misdiagnosing the stop state as a producer-code failure.

## 2026-04-09 — Trend submit wrapper tests must delegate to a dependency-complete repo Python

- `scripts/submit_phase4_trend_contract.sh` imports `WA.comparison.evidence_contract` during preflight region resolution, which can transitively require repo dependencies like `yaml` before any job script is emitted.
- The standalone `pytest` toolchain may execute under a different interpreter from the repo venv, so fake-repo tests that make `--python-bin` fall back to `sys.executable` can fail with `ModuleNotFoundError: yaml` even when the real repo dry-run works.
- In `tests/test_submit_phase4_trend_contract.py`, point the fake repo interpreter at `.venv/bin/python` (or another dependency-complete repo interpreter) so failures reflect wrapper logic and not harness interpreter drift.

## 2026-04-09 — Use `uv run --with pytest --python .venv/bin/python` when repo deps and pytest live in split envs

- In this repo snapshot, `.venv/bin/python` has the scientific stack (`numpy`, `pandas`, `xarray`) but no `pytest`, while the standalone `pytest` tool runs under Python 3.14 and cannot import the repo’s Python 3.13 wheels.
- The working verification recipe is `uv run --with pytest --python .venv/bin/python python -m pytest ...`, which creates a temporary runner that can see both `pytest` and the repo dependency set without mutating `.venv`.
- This matters for Phase 4 comparison tests: bare `pytest` / `uv run pytest` can fail at collection with `ModuleNotFoundError: numpy` even though the underlying code runs correctly under the repo interpreter.

## 2026-04-09 — Do not mistake local T04 readiness diagnostics for synced-back ten-region proof

- `python scripts/run_phase4_scaleout_readiness.py --subset ten ...` will happily write a deterministic subset-ten CSV/JSON even when every family is still missing; in that state `ready_region_ids` stays empty and `incomplete_region_ids` lists all ten contract regions.
- `python scripts/run_phase4_hotspot_ledger.py --subset ten ... --no-skip` fails closed on the first missing family and auto-writes only a single-region readiness diagnostic (for example `regions-amazon__...__scaleout_readiness.json`) plus `stage=ledger action=family-context` logs.
- Neither the all-missing subset-ten readiness report nor the single-region ledger diagnostic counts as S07 completion or S08 handoff proof; only authenticated, synced-back all-green readiness artifacts plus reopened representative ledgers do.
