---
id: S02
parent: M002
milestone: M002
provides:
  - Stable contract families for trend surfaces, trend regional summaries, trend agreement surfaces, and trend agreement summaries.
  - A canonical `scripts/run_phase4_trend_contract.py` entrypoint for canonical-subset or explicit-region orchestration.
  - Semantic reload helpers in `WA.visualization.phase4` that reopen trend summaries and agreement summaries by contract semantics.
requires:
  []
affects:
  - S04
  - S05
  - S06
key_files:
  - src/WA/comparison/evidence_contract.py
  - src/WA/comparison/trend_contract.py
  - scripts/run_phase4_trend_contract.py
  - src/WA/visualization/phase4.py
  - tests/test_comparison/test_evidence_contract.py
  - tests/test_comparison/test_trend_contract.py
  - tests/test_visualization/test_phase4.py
  - src/WA/test_selection.py
  - CHANGELOG.md
  - docs/stashes/2026-04-08-018-m002-s02-t01-trend-contract.md
  - docs/stashes/2026-04-08-019-m002-s02-t02-trend-contract-runner.md
key_decisions:
  - D032 — trend agreement participant-set keys use sorted dataset ids joined with '+' so filenames stay deterministic without colliding with the contract '__' separator.
  - D033 — the trend-contract runner only supports gwd30, giems_mc, swamps, and wad2m until more datasets have explicit trend-proof coverage.
patterns_established:
  - Keep `trends.py` and `trend_agreement.py` pure compute modules and push all contract-facing naming/metadata/writer logic into dedicated adapter layers.
  - Use semantic reload helpers for downstream consumption instead of reconstructing trend or agreement filenames by hand.
  - Prefer visible `--skip`/`--no-skip` resume behavior plus reload logging over silent cache reuse for Phase 4 orchestration.
observability_surfaces:
  - Runner logs `trend-load`, `trend-write`, `agreement`, and `region-done` stages with dataset/region or participant-set context.
  - Reload helpers log `stage=reload` for trend-summary and trend-agreement-summary loads.
  - Failure messages include stage plus `dataset_id`, `region_id`, or `participant_set_key` so partial contract writes are easier to diagnose.
drill_down_paths:
  - .gsd/milestones/M002/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S02/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-08T13:03:42.026Z
blocker_discovered: false
---

# S02: Trend-correctness backbone on the shared contract

**S02 moved Phase 4 trend outputs onto the shared evidence contract with stable trend artifact families, a canonical contract-aware runner, and semantic reload helpers for downstream slices.**

## What Happened

S02 closed the trend-contract gap between the existing Phase 4 trend math and the shared evidence contract introduced in S01.

## What this slice delivered

### 1. Contract-stable trend artifact families and writer layer
- `src/WA/comparison/evidence_contract.py` now defines four dedicated artifact families: `trend_surface`, `trend_regional_summary`, `trend_agreement_surface`, and `trend_agreement_summary`.
- `src/WA/comparison/trend_contract.py` became the single adapter layer that owns deterministic relpaths, contract metadata export, strict pre-write validation, region-scoped summary cleanup, and agreement participant-set naming.
- Per-dataset trend outputs now persist the five expected fields — `sens_slope`, `p_value`, `z_score`, `significant`, and `trend_direction` — as contract NetCDF surfaces, paired with region-scoped CSV summaries.
- Agreement outputs now persist one contract surface and one contract summary per region using a deterministic participant-set key derived from sorted dataset ids joined by `+`, so later consumers do not have to infer membership from ad hoc filenames.
- The writer layer rejects malformed metadata, missing required summary columns, non-computed results, empty agreement overlap results, and ambiguous legacy summary tables that still mix the scoped region row with a duplicated `global` row.

### 2. Canonical contract runner and semantic reload surfaces
- `scripts/run_phase4_trend_contract.py` now provides the canonical trend-contract orchestration entrypoint for `--subset canonical` or explicit `--region` runs.
- The runner composes the existing `load_trend_surface()` + `compute_pixel_trends()` + `compute_trend_agreement()` math instead of absorbing logic from `scripts/hpc_probe_trends.py`, which remains diagnostic-only.
- Runtime knobs stay explicit and aligned with the live Phase 4 route: `--standardized-dir`, `--output-root`, `--aggregation`, `--start-year`, `--end-year`, `--progress`, and visible `--skip/--no-skip` behavior.
- `--skip` is now resume-aware: if the contract trend surface and summary already exist, the runner reloads the persisted trend surface and reuses it for agreement generation instead of recomputing the dataset×region trend from scratch.
- `src/WA/visualization/phase4.py` now reloads trend regional summaries and trend-agreement summaries by contract semantics, with explicit missing-output and mixed-participant validation, so downstream slices can consume these artifacts without filename guessing.

## Patterns established for downstream slices
- Keep compute modules pure and move all contract-facing behavior — relpaths, metadata, summary normalization, participant naming, and writer validation — into dedicated adapter layers.
- For multi-dataset agreement artifacts, sort dataset ids first and store the joined participant-set key explicitly; downstream readers should reopen by semantics, not by filename heuristics.
- For long-running Phase 4 orchestration, visible `--skip`/`--no-skip` behavior plus semantic reloads are the preferred recovery path; do not silently recompute agreement inputs that already exist on disk.
- Downstream consumers should use `WA.visualization.phase4` reload helpers rather than manually reconstructing trend summary or agreement-summary paths.

## Operational Readiness (Q8)
- **Health signal:** `python scripts/run_phase4_trend_contract.py --help` now exposes the contract scope, supported dataset set, and the narrow-first `--no-skip` HPC ladder. Runtime logging emits `trend-load`, `trend-write`, `agreement`, and `region-done` stages with dataset/region or participant-set context. Reload helpers also log `stage=reload` context for trend-summary and trend-agreement-summary access.
- **Failure signal:** the runner wraps failures with stage, `dataset_id`, `region_id`, or `participant_set_key`; the writer/reload layer rejects malformed metadata, missing artifacts, non-computed results, and mixed participant metadata explicitly rather than inferring through partial state.
- **Recovery procedure:** rerun the narrow-first single-region command with `--no-skip` to rebuild from scratch, then expand to `--subset canonical --no-skip`. If a prior run already wrote trend surfaces and summaries, rerun with default `--skip` to reload persisted trend surfaces and resume agreement work at the dataset×region boundary.
- **Monitoring gaps:** local tests prove the contract wiring, reload semantics, and failure surfaces, but this slice did not produce fresh HPC runtime proof. Ten-region scale behavior and support for datasets outside `gwd30`, `giems_mc`, `swamps`, and `wad2m` remain future proof boundaries.

## What the next slices should assume
- S04 can now treat trend outputs as first-class contract artifacts under stable families rather than as in-memory `TrendResult` / `TrendAgreementResult` objects or legacy probe tables.
- The stable artifact families are:
  - `trend_surfaces/<region>/...`
  - `trend_regional_summaries/<region>/...`
  - `trend_agreement_surfaces/<region>/...`
  - `trend_agreement_summaries/<region>/...`
- The canonical re-entry ladder for fresh runtime proof is now:
  1. `python scripts/run_phase4_trend_contract.py --region amazon --dataset-id wad2m --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --aggregation annual --start-year 2016 --end-year 2016 --no-skip`
  2. `python scripts/run_phase4_trend_contract.py --subset canonical --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --aggregation annual --start-year 2016 --end-year 2016 --no-skip`
- Any attempt to widen dataset coverage beyond the four supported ids should be treated as a new proof task, not as an automatic extension of the current runner.


## Verification

All slice-plan verification checks passed in this closer pass.

- `ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_contract.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py` ✅
- `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py -q` ✅ (`16 passed`)
- `ruff check scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md` ✅
- `python scripts/run_phase4_trend_contract.py --help` ✅
- `python -m pytest tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_visualization/test_phase4.py -q` ✅ (`46 passed`)
- `python scripts/run_related_tests.py src/WA/comparison/trend_contract.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py` ✅

Additional guard verification also passed:
- `python -m pytest tests/test_test_selection.py -q` ✅ (`4 passed`)
- `python -m pytest tests/` ✅ (`457 passed`)

These checks prove deterministic artifact-family wiring, explicit CLI/help behavior, semantic reload success and failure surfaces, related-test routing, and full local regression stability.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor but intentional deviations from the original task wording: (1) the writer layer requires the configured output root to pre-exist so missing-root failures stay explicit before any artifact write; only the contract-family subdirectories are created underneath it, and (2) `CHANGELOG.md` was kept content-equivalent but wrapped in a Ruff-compatible form because the required slice lint command parses it as Python in this repo.

## Known Limitations

Fresh HPC/runtime proof is still pending. The runner is intentionally limited to `gwd30`, `giems_mc`, `swamps`, and `wad2m` until more datasets gain explicit trend-proof coverage, and ten-region runtime/I/O behavior remains unverified outside local tests.

## Follow-ups

1. Run the narrow-first HPC smoke test:
   `python scripts/run_phase4_trend_contract.py --region amazon --dataset-id wad2m --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --aggregation annual --start-year 2016 --end-year 2016 --no-skip`
2. Then run the canonical subset proof:
   `python scripts/run_phase4_trend_contract.py --subset canonical --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --aggregation annual --start-year 2016 --end-year 2016 --no-skip`
3. Have S04 consume `WA.visualization.phase4` semantic reload helpers instead of reconstructing trend paths manually.
4. Treat any expansion beyond the four supported trend datasets as a fresh proof slice, not as a default extension of this runner.

## Files Created/Modified

- `src/WA/comparison/evidence_contract.py` — Added dedicated trend and trend-agreement artifact families to the shared evidence contract.
- `src/WA/comparison/trend_contract.py` — Implemented deterministic writer/validator helpers for trend and agreement contract artifacts.
- `scripts/run_phase4_trend_contract.py` — Added the canonical contract-aware trend runner with explicit dataset/region stage logging and skip-aware reload behavior.
- `src/WA/visualization/phase4.py` — Added semantic reload helpers for contract trend summaries and trend-agreement summaries.
- `tests/test_comparison/test_evidence_contract.py` — Locked the new trend artifact families in the shared contract tests.
- `tests/test_comparison/test_trend_contract.py` — Locked relpath determinism, metadata validation, summary cleanup, and agreement participant-key behavior.
- `tests/test_visualization/test_phase4.py` — Covered trend reload happy paths, missing-output failures, mixed-participant rejection, and CLI argument validation.
- `src/WA/test_selection.py` — Mapped the trend-contract runner into the Phase 4 related-test family.
- `CHANGELOG.md` — Recorded the new trend-contract runner/reload-helper work while keeping the file Ruff-compatible for this repo.
- `docs/stashes/2026-04-08-018-m002-s02-t01-trend-contract.md` — Saved the compact T01 recovery summary for the trend contract writer layer.
- `docs/stashes/2026-04-08-019-m002-s02-t02-trend-contract-runner.md` — Saved the compact T02 recovery summary with HPC next-step commands.
