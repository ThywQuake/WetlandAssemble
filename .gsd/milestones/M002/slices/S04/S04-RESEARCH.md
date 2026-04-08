# S04 — Research

**Date:** 2026-04-08

## Summary

S04 primarily owns **R105** (represent hotspots as one shared analysis object) and directly supports **R101** by making the three evidence lines consumable through one hotspot-facing contract surface. The codebase is already close on two of the three lines: percentage hotspots already exist as contract JSON/CSV pairs in `src/WA/comparison/percentage_hotspots.py`, and classification hotspots already exist as contract rewrites in `src/WA/comparison/classification_contract.py`. Trend outputs, however, still stop at contract **surfaces + summaries** in `src/WA/comparison/trend_contract.py` / `scripts/run_phase4_trend_contract.py`; there is still no trend hotspot manifest and no normalized cross-line ledger.

The lowest-risk route is a thin-adapter extension, not a refactor. First add a trend hotspot artifact family so all three lines truly have hotspot objects. Then add a small normalizer/ledger layer that reloads the three hotspot families semantically and emits one region-scoped ledger. Existing `src/WA/visualization/phase4.py` helpers already prove the right downstream pattern: loaders should reopen contract outputs by semantics, not by guessed filenames.

## Recommendation

1. **Close the missing trend hotspot family first.**
   - Add a new `trend_hotspot_manifest` artifact family to `src/WA/comparison/evidence_contract.py`.
   - Implement `src/WA/comparison/trend_hotspots.py` as the contract-facing writer/validator/reloader for trend hotspots.
   - Extend `scripts/run_phase4_trend_contract.py` with a `stage=trend_hotspots` step after agreement write/reload.
   - Recommended score semantics: `disagreement_score = 1 - agreement_ratio`, with `disputed == True` as the candidate mask and `slope_std` as the first tie-breaker. Do **not** rank trend hotspots by raw slope magnitude; that would mix “trend intensity” with “trend correctness/disagreement.”

2. **Then build one unified hotspot ledger.**
   - Add `src/WA/comparison/hotspot_ledger.py` that reloads percentage, classification, and trend hotspot tables through semantic contract helpers and normalizes them into one long-form region ledger.
   - Keep the contract addition minimal: add one `unified_hotspot_ledger` artifact family rather than proliferating multiple summary families up front.
   - Use a fixed dataset slot token such as `multi_line` / `all_lines` for the ledger artifact stem so naming stays deterministic and avoids `__` collisions.

3. **Put downstream reopeners in `src/WA/visualization/phase4.py`.**
   - Add `load_phase4_contract_trend_hotspot_table(...)`.
   - Add `load_phase4_unified_hotspot_ledger(...)`.
   - If a derived “cross-line comparison” table is useful, make it a library-level derived view from the ledger first; only promote it to a first-class contract family if later slices prove they need a stable on-disk relpath.

4. **Keep runners thin and fail closed.**
   - Add a thin `scripts/run_phase4_hotspot_ledger.py` runner that only reloads existing contract artifacts, validates completeness, and writes the ledger.
   - The ledger runner should write nothing for a region unless all required hotspot families are present and semantically valid.
   - Preserve visible `--skip` / `--no-skip` behavior and stage-tagged logging.

## Implementation Landscape

- `src/WA/comparison/evidence_contract.py`
  - Current owner of artifact-family semantics, strict `ArtifactKind` typing, and required-family validation.
  - S04 likely needs to add:
    - `trend_hotspot_manifest`
    - `unified_hotspot_ledger`
  - Update both the `ArtifactKind` union and the hard-coded required-family set in `EvidenceContract.__post_init__`.
  - Verification anchor: `tests/test_comparison/test_evidence_contract.py`.

- `src/WA/comparison/trend_contract.py`
  - Already owns stable trend/trend-agreement relpaths and participant-set keying:
    - `build_participant_set_key(...)`
    - `trend_agreement_surface_output_path(...)`
    - `trend_agreement_summary_output_path(...)`
  - S04 should reuse these helpers rather than inventing a second trend naming layer.
  - The agreement summary already carries the region-scoped summary fields the hotspot writer needs for context (`mean_agreement_ratio`, `fraction_disputed`, overlap window, `participant_ids_json`, `contract_metadata_json`).

- `src/WA/comparison/trend_agreement.py`
  - Supplies the only existing trend-disagreement semantics:
    - `agreement_ratio`
    - `robust_increase`
    - `robust_decrease`
    - `robust_stable`
    - `disputed`
    - `mean_slope`
    - `slope_std`
  - There is **no** hotspot selection here yet. This is the main scientific/contract seam S04 must close.

- `src/WA/comparison/percentage_hotspots.py`
  - Best pattern reference for quota allocation, local-max candidate filtering, AOI bbox construction, and JSON/CSV pair emission.
  - Reusable patterns/helpers:
    - `allocate_percentage_region_quotas(...)`
    - `_select_hotspot_candidates(...)`
    - `_build_hotspot_bbox(...)`
  - Recommendation: treat this file as a pattern source, not a refactor target. Only extract shared utilities if duplication becomes clearly painful.

- `src/WA/comparison/classification_contract.py`
  - Already rewrites Phase 3.7 outputs into contract hotspot pairs via `rewrite_phase37_hotspots_to_contract(...)`.
  - Useful normalized hotspot fields already exist in the CSV companion:
    - `participant_set_key`
    - `bbox`
    - `mean_entropy`
    - `max_entropy`
    - `quota`, `selected_count`, `shortfall`, `status`
    - `class_disagreement_summary_json`
    - `surface_output_path`, `summary_output_path`
    - `contract_metadata_json`
  - The ledger should consume these contract artifacts via semantic reload helpers, never the raw Phase 3.7 trio.

- `src/WA/visualization/phase4.py`
  - Existing semantic loaders already prove the right downstream pattern:
    - `load_phase4_contract_hotspot_table(...)` for percentage
    - `load_phase4_contract_classification_hotspot_table(...)`
    - `load_phase4_contract_trend_region_table(...)`
    - `load_phase4_contract_trend_agreement_summary(...)`
  - Natural S04 additions:
    - `load_phase4_contract_trend_hotspot_table(...)`
    - `load_phase4_unified_hotspot_ledger(...)`
    - optional derived cross-line comparison builder from the ledger
  - Keep file-path construction inside contract/path helpers; `phase4.py` should only reopen and validate semantically.

- `scripts/run_phase4_trend_contract.py`
  - Thin orchestrator already resolves regions/subsets, computes/reloads trend results, writes agreement artifacts, and logs stage-tagged progress.
  - Best place to attach trend hotspot generation after agreement write/reload.
  - Prefer extending this runner over inventing a second trend CLI.

- `scripts/run_phase4_percentage_contract.py`
  - Useful reference for thin orchestration + figure rebuild + visible `--skip` / `--no-skip`.
  - It also shows the current percentage dataset default set (`berkeley_rwawc`, `giems_mc`, `topmodel`, `swamps`, `wad2m`), which does **not** match the trend dataset set; the ledger must not assume the same participant list across lines.

- `scripts/run_phase4_classification_contract.py`
  - Best model for semantic reload gating and stage-tagged skip/rebuild behavior.
  - The ledger runner should behave similarly: validate semantically first, then decide whether a region can be skipped.

- **Recommended new files**
  - `src/WA/comparison/trend_hotspots.py` — trend hotspot writer / validator / reloader
  - `src/WA/comparison/hotspot_ledger.py` — normalize the three hotspot families into one long-form ledger
  - `scripts/run_phase4_hotspot_ledger.py` — thin reload/write runner
  - `tests/test_comparison/test_trend_hotspots.py`
  - `tests/test_comparison/test_hotspot_ledger.py`

- **Likely touched existing files**
  - `src/WA/comparison/evidence_contract.py`
  - `src/WA/visualization/phase4.py`
  - `scripts/run_phase4_trend_contract.py`
  - `tests/test_comparison/test_evidence_contract.py`
  - `tests/test_visualization/test_phase4.py`
  - `src/WA/test_selection.py`
  - `docs/testing/test-categories.md`
  - `CHANGELOG.md`

### Natural build order

1. **Trend hotspot family first**  
   Highest-risk gap. The ledger cannot honestly unify “all three lines” until trend has a hotspot artifact family.

2. **Unified ledger second**  
   Once all three hotspot tables exist, normalization is mostly contract plumbing and validation.

3. **Reload/runner surface last**  
   Add `phase4.py` helpers and the thin ledger CLI only after the row model is stable.

### Proposed shared ledger row model

Minimum common columns worth standardizing:
- `analysis_object_id` — globally unique composite key
- `metric_family` — `percentage` / `classification_disagreement` / `trend_agreement`
- `dataset_or_participant_key`
- `region_id`, `region_label`
- `hotspot_id`, `region_rank`
- `bbox_json`, `center_lon`, `center_lat`
- `primary_score_value`
- `primary_score_field`
- `primary_score_units`
- `score_percentile_within_family`
- `quota`, `selected_count`, `shortfall`, `status`
- `surface_output_path`, `summary_output_path`
- `contract_metadata_json`
- `line_specific_json` — preserves family-only extras without exploding the shared schema

This is safer than forcing one generic `hotspot_score` meaning across lines. Percentage `%`, classification entropy, and trend disagreement should stay explicit.

## Risks / Unknowns

- **Trend hotspot semantics are the main open choice.**  
  The safest first version is disagreement-first (`1 - agreement_ratio`) rather than slope-magnitude-first.

- **Hotspot IDs are not globally unique across the milestone.**  
  Percentage ids include dataset context; classification ids do not; trend ids will likely follow a third pattern. The ledger needs its own composite key.

- **Do not globally rank raw scores across families.**  
  Cross-line comparison should use family-local ranks/percentiles plus bbox/region context, not one merged raw-score sort.

- **The contract type surface is strict.**  
  Adding artifact kinds means updating the literal union, default semantics, and required-kind validation together.

- **If `docs/testing/test-categories.md` is touched, keep the raw-docstring wrapper.**  
  The repo’s Ruff gate parses that markdown as Python unless it stays wrapped; this is already recorded in project knowledge.

## Skill Suggestions

No directly relevant professional skill is already installed in `<available_skills>` for this xarray/pandas-heavy contract work.

Promising external skills, not installed:
- `npx skills add tondevrel/scientific-agent-skills@xarray`
- `npx skills add jeffallan/claude-skills@pandas-pro`

These are optional only; the repo already has the necessary native patterns.

## Verification

Focused local iteration:
- `ruff check src/WA/comparison/evidence_contract.py src/WA/comparison/trend_hotspots.py src/WA/comparison/hotspot_ledger.py src/WA/visualization/phase4.py scripts/run_phase4_trend_contract.py scripts/run_phase4_hotspot_ledger.py tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py src/WA/test_selection.py CHANGELOG.md`
- `python scripts/run_phase4_trend_contract.py --help`
- `python scripts/run_phase4_hotspot_ledger.py --help`
- `python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py tests/test_comparison/test_percentage_hotspots.py tests/test_comparison/test_classification_contract.py tests/test_comparison/test_trend_hotspots.py tests/test_comparison/test_hotspot_ledger.py tests/test_visualization/test_phase4.py -q`
- `python scripts/run_related_tests.py src/WA/comparison/trend_hotspots.py src/WA/comparison/hotspot_ledger.py scripts/run_phase4_trend_contract.py scripts/run_phase4_hotspot_ledger.py src/WA/visualization/phase4.py src/WA/test_selection.py`

Full regression before closing the slice:
- `python -m pytest tests/`

## HPC commands after S04 lands

Narrow-first, always visible `--no-skip`:

```bash
python scripts/run_phase4_percentage_contract.py \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2016 \
  --end-year 2016 \
  --no-skip
```

```bash
python scripts/run_phase4_trend_contract.py \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --aggregation annual \
  --start-year 2016 \
  --end-year 2016 \
  --no-skip
```

```bash
python scripts/run_phase4_classification_contract.py \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --year 2016 \
  --no-skip
```

```bash
python scripts/run_phase4_hotspot_ledger.py \
  --region amazon \
  --output-root results/phase4 \
  --no-skip
```

Then canonical subset:

```bash
python scripts/run_phase4_hotspot_ledger.py \
  --subset canonical \
  --output-root results/phase4 \
  --no-skip
```
