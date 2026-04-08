---
id: S05
parent: M002
milestone: M002
provides:
  - One shared ordered ten-region selector reused across regional, trend, readiness, and ledger CLIs.
  - Restored real contract producers for percentage, classification, and dataset-scoped trend outputs.
  - Explicit trend checkpoint + submit-wrapper surfaces for resumable HPC reruns.
  - A readiness gate that operators can inspect before attempting wide ledger builds.
  - Fail-closed ledger diagnostics that point directly at the missing or partial family.
requires:
  []
affects:
  - S06
key_files:
  - src/WA/comparison/evidence_contract.py
  - src/WA/comparison/percentage_backbone.py
  - src/WA/comparison/percentage_hotspots.py
  - src/WA/comparison/classification_contract.py
  - src/WA/comparison/trend_contract.py
  - src/WA/comparison/trends.py
  - src/WA/comparison/scaleout_readiness.py
  - scripts/run_phase4_percentage_contract.py
  - scripts/run_phase4_classification_contract.py
  - scripts/run_phase4_trend_contract.py
  - scripts/submit_phase4_trend_contract.sh
  - scripts/run_phase4_scaleout_readiness.py
  - scripts/run_phase4_hotspot_ledger.py
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-09-010-m002-s05-slice-closeout.md
key_decisions:
  - D043 — EvidenceContract is the single owner of the ordered `ten` subset and contract-aware CLIs must force explicit selector choice.
  - D044 — The percentage contract family is one ordered multi-dataset bundle per region, with GWD30 restored through Stage-1-backed surfaces.
  - D045 — The classification contract keeps `classification_key=canonical` for the fixed `g2017+glwd_v2+gwd30` participant set and rewrites Phase 3.7 hotspots instead of recomputing them.
  - D046 — Trend checkpoints are separate resumable cache surfaces while dataset-scoped trend contract outputs remain stable downstream artifacts.
  - D047 — Readiness distinguishes `missing` from `partial`, and ledger failures auto-write single-region readiness diagnostics.
patterns_established:
  - Use `EvidenceContract.resolve_regions(subset=...)` as the only shared owner of ordered wide-run region sets.
  - Separate stable contract outputs for downstream consumers from checkpoint/cache artifacts used only for rerun recovery.
  - Treat hotspot families as reusable only when manifest/data pairs and metadata reopen semantically; partial pairs fail closed.
  - Run wide Phase 4 work in the order producer -> readiness -> ledger instead of debugging from downstream ledger failures.
  - Keep HPC submit wrappers explicit about `--repo`, `--no-skip`, participant dataset lists, and one-region-per-job fanout.
observability_surfaces:
  - `stage=region-selector` logs with resolved `region_ids=[...]` before fanout.
  - Trend `stage=trend-load` and `stage=trend-write` logs that distinguish compute vs reload.
  - Deterministic readiness CSV/JSON reports under `results/phase4/scaleout_readiness/`.
  - Ledger family-context error logs with status/path/reason per metric family.
  - Auto-written single-region readiness diagnostics when ledger builds fail.
drill_down_paths:
  - .gsd/milestones/M002/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S05/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S05/tasks/T04-SUMMARY.md
  - .gsd/milestones/M002/slices/S05/tasks/T05-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-08T20:20:17.067Z
blocker_discovered: false
---

# S05: Ten-region scale-out with reproducible HPC-safe execution

**S05 froze one shared ordered ten-region selector, restored the real percentage/classification/trend Phase 4 producer chain, and added fail-closed readiness plus ledger diagnostics so the contract can widen from canonical regions to ten regions through reproducible HPC-safe execution surfaces.**

## What Happened

## Slice Outcome

S05 closed the **execution boundary** for ten-region scale-out. The important distinction is that this slice did **not** pretend the worktree already contains freshly generated ten-region science outputs; instead, it made the wide-run path explicit, contract-safe, resumable, and diagnosable.

### What actually shipped

- **T01 — shared selector contract**
  - `src/WA/comparison/evidence_contract.py` is now the single owner of ordered subset resolution for `canonical` and `ten`.
  - `scripts/run_phase4_regional.py`, `scripts/run_phase4_trend_contract.py`, and `scripts/run_phase4_hotspot_ledger.py` now reject `--subset` + `--region` ambiguity and log the resolved region list before fanout.
  - `run_phase4_regional.py` keeps its old no-arg macro+priority behavior as an explicit legacy route rather than silently redefining it as the contract ten-region path.
- **T02 — real percentage contract chain restored**
  - Added `src/WA/comparison/percentage_backbone.py`, `src/WA/comparison/percentage_hotspots.py`, and `scripts/run_phase4_percentage_contract.py`.
  - Percentage scale-out now uses one contract-backed multi-dataset bundle per region, including GWD30 restored through Stage-1 pixel-statistics manifests.
  - Hotspot JSON/CSV pairs are written atomically and reloaded semantically before reuse.
- **T03 — real classification contract chain restored**
  - Added `src/WA/comparison/classification_contract.py` and `scripts/run_phase4_classification_contract.py`.
  - The Phase 4 adapter reuses Phase 3.6 / 3.7 disagreement and hotspot science instead of duplicating it, preserves the full entropy/agreement/dominant-class payload, and fails closed on malformed source trios.
  - `src/WA/visualization/phase4.py` now exposes classification semantic reload helpers.
- **T04 — trend outputs + checkpoints + HPC wrapper restored**
  - Added `src/WA/comparison/trend_contract.py` and extended `src/WA/comparison/trends.py` so dataset-scoped `trend_surface` / `trend_regional_summary` artifacts are written and reopened semantically.
  - Trend wide runs now persist explicit region/dataset/aggregation/requested-window checkpoints before agreement.
  - Added `scripts/submit_phase4_trend_contract.sh`, which fans out one region per job, requires explicit `--repo`, and writes `--no-skip` into generated job commands.
- **T05 — readiness gate + family diagnostics**
  - Added `src/WA/comparison/scaleout_readiness.py` and `scripts/run_phase4_scaleout_readiness.py`.
  - Readiness scans now classify each `region × family` as `ready`, `missing`, or `partial` with explicit reason and artifact paths.
  - `scripts/run_phase4_hotspot_ledger.py` remains fail-closed, but it now logs family-specific context and auto-writes a single-region readiness report when a ledger build fails.

### What this means for downstream work

S05 establishes one explicit `amazon -> canonical -> ten` widening path across percentage, classification, trend, and unified-ledger surfaces without hand-written region lists, hidden defaults, or silent partial-cache reuse. Downstream slices should treat readiness as the operator-facing gate and the ledger as the final integrator, not the repair mechanism.

## Verification Summary

Slice-level verification was rerun on the assembled codebase and passed:

- `ruff check` over all S05 contract, runner, readiness, visualization, routing, and focused test files — **pass**
- `bash -n scripts/submit_phase4_gwd30_pixel_stats.sh scripts/submit_phase4_gwd30_regional_year_split.sh scripts/submit_phase4_gwd30_tropical_shards.sh scripts/submit_phase4_trend_contract.sh` — **pass**
- `python scripts/run_phase4_regional.py --help` — **pass**
- `python scripts/run_phase4_percentage_contract.py --help` — **pass**
- `python scripts/run_phase4_classification_contract.py --help` — **pass**
- `python scripts/run_phase4_trend_contract.py --help` — **pass**
- `python scripts/run_phase4_hotspot_ledger.py --help` — **pass**
- `python scripts/run_phase4_scaleout_readiness.py --help` — **pass**
- `python scripts/run_related_tests.py ...` for the restored percentage path and readiness/ledger path — **pass** as selector/advisory surfaces
- `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_phase4_regional.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_plot_tropical_wetland_025deg.py tests/test_comparison/test_classification_contract.py tests/test_visualization/test_phase4.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_submit_phase4_trend_contract.py tests/test_comparison/test_scaleout_readiness.py tests/test_comparison/test_hotspot_ledger.py tests/test_submit_phase4_gwd30_pixel_stats.py tests/test_submit_phase4_gwd30_regional_year_split.py tests/test_submit_phase4_gwd30_tropical_shards.py tests/test_test_selection.py -q` — **124 passed in 22.71s**

### Observability / diagnostic proof

Runtime-facing diagnostic surfaces were exercised locally:

- `python scripts/run_phase4_scaleout_readiness.py --region amazon ...` succeeded on an empty local `results/phase4` tree, wrote CSV/JSON readiness reports, and correctly marked percentage/classification/trend as `missing` with explicit artifact paths.
- `python scripts/run_phase4_hotspot_ledger.py --region amazon ... --no-skip` failed closed as designed, logged family-specific `status/path/reason` lines for all three families, and auto-wrote the matching single-region readiness diagnostic report.

These checks prove that the operator-facing diagnostics work even when wide-run artifacts are absent, which is the key failure mode S05 was meant to make visible.

## Operational Readiness (Q8)

- **Health signal:** readiness reports show `ready` for all three hotspot families in a region; trend logs show `stage=trend-load action=reload|compute` and `stage=trend-write action=ready|write|reload`; ledger writes the unified ledger path without family-context errors.
- **Failure signal:** readiness rows show `missing` or `partial` with manifest/table/surface/summary paths and a concrete reason; ledger exits non-zero, prints one family-context line per metric family, and points at the auto-written readiness report.
- **Recovery procedure:** rerun the missing producer family with explicit `--region` or `--subset ten` plus `--no-skip`; rerun readiness; only after readiness is satisfactory rerun the unified ledger.
- **Monitoring gaps:** there is still no live dashboard or automatic alerting for Phase 4 scale-out. Operators must inspect CLI logs plus readiness CSV/JSON outputs manually, and this worktree still lacks real ten-region external-input outputs for end-to-end runtime proof.

## Handoff to S06

S06 should treat S05 as the **ten-region contract-safe execution boundary**, then materialize the real ten-region outputs on HPC in this order: percentage producer, classification producer, trend submit wrapper, readiness scan, unified ledger. Only after those outputs exist and reopen cleanly should S06 build paper-facing tables, figures, and milestone-level integration proof.

## Verification

Passed the assembled slice verification surface: aggregate ruff check, all relevant CLI help surfaces, shell syntax checks for the submit wrappers, both required `run_related_tests.py` selector runs, a 17-file focused/broader Phase 4 pytest subset (`124 passed in 22.71s`), plus local readiness/ledger smoke checks showing that readiness writes deterministic CSV/JSON reports and ledger failures remain fail-closed with family-specific diagnostics and auto-written single-region readiness reports.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

No real ten-region external-input rerun was executed from this worktree during slice closeout; the local readiness/ledger smoke used an empty `results/phase4` tree to prove diagnostics, not science completeness. Repository-wide full-suite stability is still bounded by the pre-existing unrelated `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` red bar reported in task-level evidence.

## Follow-ups

Run the restored percentage and classification producers plus the trend submit wrapper on HPC for `--subset ten`, inspect the readiness report, build the ten-region unified ledger only after readiness passes, and use those materialized outputs as the S06 paper-pack input surface.

## Files Created/Modified

- `src/WA/comparison/evidence_contract.py` — Added the shared ordered `ten` selector and stricter subset/region validation.
- `src/WA/comparison/percentage_backbone.py` — Restored the contract-backed percentage surface/summary backbone, including GWD30 Stage-1 recovery.
- `src/WA/comparison/percentage_hotspots.py` — Added atomic percentage hotspot pair writing plus semantic reload validation.
- `src/WA/comparison/classification_contract.py` — Wrapped Phase 3.6 / 3.7 outputs into fail-closed Phase 4 classification contract artifacts.
- `src/WA/comparison/trend_contract.py` — Added dataset-scoped trend contract artifacts and reload helpers.
- `src/WA/comparison/trends.py` — Added explicit region/dataset checkpoint write/reload support for resumable trend reruns.
- `src/WA/comparison/scaleout_readiness.py` — Added semantic ten-region readiness inspection with ready/missing/partial classification.
- `scripts/submit_phase4_trend_contract.sh` — Added explicit `--repo`/`--no-skip` one-region-per-job trend fanout for HPC.
- `scripts/run_phase4_hotspot_ledger.py` — Preserved fail-closed ledger behavior while adding family diagnostics and auto-written readiness reports.
- `.gsd/PROJECT.md` — Refreshed the project state so S05 is represented as complete and S06 is the next execution target.
- `.gsd/KNOWLEDGE.md` — Recorded the readiness-vs-ledger diagnostic rule for future scale-out work.
- `docs/stashes/2026-04-09-010-m002-s05-slice-closeout.md` — Added a quick-reference slice closeout note with verification results and concrete HPC commands.
