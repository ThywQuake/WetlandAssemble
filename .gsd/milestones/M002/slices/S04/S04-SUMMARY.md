---
id: S04
parent: M002
milestone: M002
provides:
  - Contract-backed trend hotspot manifest + CSV families keyed by deterministic participant-set ids.
  - A unified hotspot ledger artifact family that normalizes percentage, classification, and trend hotspots into stable long-form `analysis_object_id` rows.
  - Semantic Phase 4 reload helpers for trend hotspots and unified ledgers in `src/WA/visualization/phase4.py`.
  - Fail-closed Phase 4 runners and validation patterns that later slices can reuse during wider reruns.
requires:
  - slice: S01
    provides: Contract-stable percentage hotspot artifacts and the shared evidence-contract naming/metadata grammar that S04 reused.
  - slice: S02
    provides: Trend agreement surfaces/summaries plus participant-set key semantics that S04 extended into trend hotspot manifests.
  - slice: S03
    provides: Contract-backed classification hotspot artifacts that the unified ledger now reloads and normalizes alongside the other lines.
affects:
  - S05
  - S06
key_files:
  - src/WA/comparison/evidence_contract.py
  - src/WA/comparison/trend_hotspots.py
  - scripts/run_phase4_trend_contract.py
  - src/WA/comparison/hotspot_ledger.py
  - scripts/run_phase4_hotspot_ledger.py
  - src/WA/visualization/phase4.py
  - tests/test_comparison/test_evidence_contract.py
  - tests/test_comparison/test_trend_hotspots.py
  - tests/test_comparison/test_hotspot_ledger.py
  - tests/test_visualization/test_phase4.py
  - src/WA/test_selection.py
  - CHANGELOG.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D037 — trend hotspots are disagreement-first objects built from disputed agreement cells, ranked by `1 - agreement_ratio` with `slope_std` only as a tie-breaker.
  - D040 — the unified hotspot ledger must preserve family-local score semantics through `primary_score_name`, `primary_score_value`, `family_percentile`, and `line_specific_json` instead of collapsing everything into one fake raw score.
  - D041 — hotspot manifest/ledger reuse is fail-closed: only complete, metadata-valid, hash-valid artifact pairs are eligible for skip/reload behavior.
patterns_established:
  - Semantic reload helpers in `WA.visualization.phase4` are the supported downstream API for trend hotspots and unified ledgers.
  - Shared evidence objects should use atomic paired writes plus metadata/hash validation before any skip/reload path trusts them.
  - Cross-line comparison should normalize to long-form analysis objects with provenance, not erase family-specific meaning for the sake of one numeric rank.
  - When planner paths are stale, prefer on-disk evidence-contract artifact semantics over inventing new imports to satisfy the old plan text.
observability_surfaces:
  - `stage=agreement` and `stage=trend-hotspots` runner logs with `region` and `participant_set_key` context.
  - `stage=ledger` logs for build/reload decisions, family readiness, family normalization, and final ready state.
  - Semantic reload wrapper errors (`Phase4 semantic reload failed ...`) plus explicit fail-closed ledger errors for missing/malformed families.
drill_down_paths:
  - .gsd/milestones/M002/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S04/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-08T17:01:08.538Z
blocker_discovered: false
---

# S04: Unified hotspot ledger and cross-line evidence surfaces

**Closed the cross-line hotspot integration gap by adding contract-backed trend hotspot manifests, a unified hotspot ledger, semantic reload helpers, and fail-closed Phase 4 runners that normalize percentage, classification, and trend hotspots into one stable analysis object.**

## What Happened

# S04: Unified hotspot ledger and cross-line evidence surfaces

## Outcome

S04 closed the cross-line hotspot integration gap for the canonical subset. Percentage, classification, and trend hotspots now land on one shared contract surface instead of three unrelated file families. The trend line gained its missing contract-backed hotspot family, and the new unified ledger normalizes all three lines into one long-form `analysis_object_id` table that downstream slices can reopen semantically by `region_id + ledger_key` rather than reverse-engineering filenames.

## What this slice delivered

### T01 — Contract-backed trend hotspot family and semantic reload

- Extended the shared evidence contract so `trend_hotspot_manifest` is a first-class artifact family alongside the existing percentage, classification, trend-surface, and trend-summary outputs.
- Added `src/WA/comparison/trend_hotspots.py` to:
  - build deterministic `participant_set_key` values from sorted participant ids joined by `+`
  - select candidates only from `TrendAgreementResult.disputed`
  - rank them by `disagreement_score = 1 - agreement_ratio`
  - use `slope_std` only as the first tie-breaker instead of redefining “trend correctness” as slope magnitude
  - write paired JSON manifest + CSV hotspot tables atomically
  - validate participant metadata, bbox payloads, and table SHA-256 before reuse
- Added `scripts/run_phase4_trend_contract.py` as the real Phase 4 trend contract runner so agreement artifacts and trend hotspots are written/reloaded through one stage-tagged path.
- Added `load_phase4_contract_trend_hotspot_table(...)` to `src/WA/visualization/phase4.py`, giving downstream code one semantic reload API keyed by `region_id + participant_ids`.

### T02 — Unified hotspot ledger and semantic cross-line reload

- Added `src/WA/comparison/hotspot_ledger.py` to reopen the percentage, classification, and trend hotspot families semantically and normalize them into one long-form ledger.
- The ledger preserves family-local meaning instead of inventing fake cross-family raw-score comparability:
  - `metric_family`
  - `primary_score_name`
  - `primary_score_value`
  - `family_percentile`
  - `line_specific_json`
- Added stable `analysis_object_id` rows plus provenance columns for manifest/table/surface/summary paths so later comparison and figure code can trace every ledger row back to its source artifact family.
- Added `scripts/run_phase4_hotspot_ledger.py` as the thin ledger CLI with fail-closed writes: it refuses to emit a ledger unless all three hotspot families are present and semantically valid for the same region.
- Added `load_phase4_unified_hotspot_ledger(...)` in `src/WA/visualization/phase4.py`, so downstream slices can reopen the ledger by semantics instead of filename guessing.

## Patterns established

1. **Semantic reload is the contract boundary.** Downstream code should reopen Phase 4 hotspot artifacts by `region_id`, participant set, and ledger key through contract helpers instead of inferring stems from filenames.
2. **Fail-closed reuse is mandatory for shared evidence objects.** JSON manifest + CSV companion pairs are only reusable when both files exist and metadata/hash validation passes; partial or mixed pairs must be rejected.
3. **Cross-line comparison uses a long-form ledger, not a fake shared score.** Percentage coverage, classification entropy, and trend disagreement stay family-local via `primary_score_name/value` plus within-family percentiles.
4. **Participant-set keys stay deterministic across lines.** Sorted ids joined with `+` are now the stable contract token for trend-derived hotspot families and downstream ledger references.

## Downstream handoff

This slice gives S05 and S06 one stable hotspot analysis object per row. They can now:

- reopen trend hotspots semantically from contract-backed artifacts
- rebuild or reload one unified ledger per region without guessing source paths
- rank within each hotspot family while still comparing region/family/provenance side by side
- trace any ledger row back to its source hotspot manifest, source surface, and source summary

## Verification

All slice-plan verification passed locally:

- `ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py`
- `ruff check src/WA/comparison/hotspot_ledger.py src/WA/visualization/phase4.py scripts/run_phase4_hotspot_ledger.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md`
- `python scripts/run_phase4_trend_contract.py --help`
- `python scripts/run_phase4_hotspot_ledger.py --help`
- `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_visualization/test_phase4.py -q` → `18 passed`
- `python -m pytest tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q` → `15 passed`
- `python scripts/run_related_tests.py src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py`
- `python scripts/run_related_tests.py src/WA/comparison/hotspot_ledger.py scripts/run_phase4_hotspot_ledger.py src/WA/visualization/phase4.py src/WA/test_selection.py`
- `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_hotspot_ledger.py tests/test_comparison/test_phase4_regional.py tests/test_comparison/test_trend_hotspots.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_visualization/test_phase4.py tests/test_submit_phase4_gwd30_pixel_stats.py tests/test_submit_phase4_gwd30_regional_year_split.py tests/test_submit_phase4_gwd30_tropical_shards.py -q` → `79 passed`

Additional observability smoke confirmed the runtime surfaces promised by the slice:

- synthetic agreement/hotspot materialization emitted `stage=agreement` and `stage=trend-hotspots` logs with `region` and `participant_set_key`
- synthetic ledger rebuild emitted `stage=ledger action=build`, `action=family-ready`, `action=families-validated`, `action=family-normalized`, and `action=ready`
- semantic reload wrappers still raise the explicit `Phase4 semantic reload failed ...` message on missing artifacts

Per repo knowledge, the related Phase 4 subset is the preferred verification surface for this closeout instead of another full-suite rerun. The earlier task executions already documented the unrelated pre-existing full-suite failure at `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` plus a later full-suite exit `137`; S04 did not alter that separate boundary.

## Operational Readiness (Q8)

### Health signal

- `scripts/run_phase4_trend_contract.py` exposes distinct `stage=agreement` and `stage=trend-hotspots` logging with `region` and `participant_set_key` context.
- `scripts/run_phase4_hotspot_ledger.py` exposes `stage=ledger` logs for build/reload, family validation, normalization, and ready states.
- `load_phase4_contract_trend_hotspot_table(...)` and `load_phase4_unified_hotspot_ledger(...)` provide semantic reopen checks that prove the on-disk artifacts are structurally valid, not just present.

### Failure signal

- Missing or partial JSON/CSV hotspot pairs fail before they can be reused.
- Mixed-region families, malformed `contract_metadata_json`, malformed bbox payloads, and duplicate `analysis_object_id` candidates raise explicit errors.
- The ledger CLI exits non-zero and writes nothing when any required family is absent or invalid.

### Recovery procedure

1. Inspect the relevant manifest/table pair instead of trusting file existence alone.
2. Rebuild the upstream family with `--no-skip` if any trend hotspot or source family is partial or malformed.
3. For ledger failures, confirm percentage, classification, and trend hotspot families all exist for the same region and participant set.
4. Re-run one narrow region first (`amazon`) before widening to the canonical subset or ten-region scale-out.

### Monitoring gaps

- No slice-level telemetry yet summarizes ledger row counts, family shortfalls, or rebuild rates across many regions.
- Fresh HPC/runtime proof on real canonical outputs is still missing; current proof is contract-level and synthetic/local.
- S05 still needs to prove that the fail-closed skip/rebuild behavior remains stable under ten-region scale-out.

## Open limitations

- The unified ledger is intentionally a normalization surface, not a scientific claim that percentage, entropy, and disagreement are directly numerically comparable.
- Canonical-subset proof is still local/structural; fresh end-to-end HPC reruns on real outputs remain future work.
- The current source-of-truth for percentage and classification hotspot reload remains the evidence-contract manifest/CSV families, because the planner’s originally named module paths do not exist in this repo snapshot.

## HPC commands to run next

After rsyncing the updated repo to HPC, keep the narrow-first ladder and use `--no-skip`.

```bash
python scripts/run_phase4_trend_contract.py \
  --region amazon \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --output-root results/phase4 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --aggregation annual \
  --start-year 1990 \
  --end-year 2020 \
  --top-hotspots 10 \
  --no-skip
```

```bash
python scripts/run_phase4_hotspot_ledger.py \
  --region amazon \
  --output-root results/phase4 \
  --ledger-key canonical \
  --percentage-key canonical \
  --classification-key canonical \
  --trend-dataset-id gwd30 \
  --trend-dataset-id giems_mc \
  --trend-dataset-id topmodel \
  --trend-dataset-id swamps \
  --trend-dataset-id wad2m \
  --no-skip
```

```bash
python scripts/run_phase4_trend_contract.py \
  --subset canonical \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --output-root results/phase4 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --aggregation annual \
  --start-year 1990 \
  --end-year 2020 \
  --top-hotspots 10 \
  --no-skip
```

```bash
python scripts/run_phase4_hotspot_ledger.py \
  --subset canonical \
  --output-root results/phase4 \
  --ledger-key canonical \
  --percentage-key canonical \
  --classification-key canonical \
  --trend-dataset-id gwd30 \
  --trend-dataset-id giems_mc \
  --trend-dataset-id topmodel \
  --trend-dataset-id swamps \
  --trend-dataset-id wad2m \
  --no-skip
```


## Verification

Slice-plan verification passed with two focused Ruff gates, both CLI help surfaces, two focused pytest subsets (`18 + 15` passing tests), both related-test selector commands, and one combined Phase 4 related pytest subset (`79 passed`). Additional observability smoke confirmed `stage=agreement`, `stage=trend-hotspots`, and `stage=ledger` logging plus the semantic reload failure wrappers. Repo-wide full-suite issues remain the previously documented unrelated `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` failure and later exit `137`, not a new S04 regression.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The planner snapshot named `src/WA/comparison/percentage_hotspots.py` and `src/WA/comparison/classification_contract.py` as the percentage/classification sources for the ledger, but this repo snapshot only had the evidence-contract manifest/CSV families as reliable hotspot surfaces. S04 therefore implemented the ledger around artifact semantics rather than non-existent module paths. Slice closeout also followed repo knowledge by running the combined related Phase 4 pytest subset instead of re-running the full test suite again after the earlier task-level full-suite failures were already shown to be unrelated.

## Known Limitations

Fresh HPC/runtime proof on real canonical outputs is still missing. The unified ledger intentionally preserves family-local score semantics rather than inventing a directly comparable raw score across percentage, classification, and trend lines. Repo-wide full-suite pytest is still not a clean green surface in this snapshot because of the previously documented unrelated `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` failure and later exit `137`.

## Follow-ups

S05 should use the new ledger as its single hotspot analysis object while scaling the contract from the canonical subset to the ten-region set. The first operational proof ladder remains narrow-first: rebuild trend hotspots for `amazon` with `--no-skip`, rebuild the unified ledger for `amazon`, then widen to the canonical subset before attempting ten-region scale-out.

## Files Created/Modified

- `src/WA/comparison/evidence_contract.py` — Locked the new trend hotspot and unified hotspot ledger artifact families into the shared evidence contract.
- `src/WA/comparison/trend_hotspots.py` — Implemented participant-set key normalization, disagreement-first trend hotspot ranking, atomic manifest/table writes, and semantic reload validation.
- `scripts/run_phase4_trend_contract.py` — Added the real trend contract runner with dedicated agreement and trend-hotspot stages plus skip/reload validation.
- `src/WA/comparison/hotspot_ledger.py` — Implemented semantic reload of all hotspot families and long-form unified ledger normalization with provenance and fail-closed validation.
- `scripts/run_phase4_hotspot_ledger.py` — Added the thin unified-ledger CLI with explicit build/reload logging and all-family validation before writes.
- `src/WA/visualization/phase4.py` — Added semantic reload helpers for contract-backed trend hotspot tables and unified hotspot ledgers.
- `tests/test_comparison/test_trend_hotspots.py` — Pinned trend hotspot ranking, participant metadata, malformed payload failures, and stable relpaths.
- `tests/test_comparison/test_hotspot_ledger.py` — Pinned ledger normalization, duplicate/malformed-family failures, and ledger CLI fail-closed behavior.
- `tests/test_visualization/test_phase4.py` — Pinned semantic reload behavior and wrapped error messages for the new trend hotspot and unified ledger helpers.
- `src/WA/test_selection.py` — Kept the new S04 code paths inside the Phase 4 related-test routing surface.
- `CHANGELOG.md` — Recorded the user-facing trend-hotspot and unified-ledger additions for Phase 4.
