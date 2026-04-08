# S04: Unified hotspot ledger and cross-line evidence surfaces — UAT

**Milestone:** M002
**Written:** 2026-04-08T17:01:08.538Z

# S04 UAT — Unified hotspot ledger and cross-line evidence surfaces

## Preconditions

1. Use a checkout that includes the S04 code paths:
   - `src/WA/comparison/trend_hotspots.py`
   - `src/WA/comparison/hotspot_ledger.py`
   - `scripts/run_phase4_trend_contract.py`
   - `scripts/run_phase4_hotspot_ledger.py`
   - `src/WA/visualization/phase4.py`
2. For real-data UAT, make sure one target region (start with `amazon`) has the upstream Phase 4 inputs available under `results/phase4` and the standardized data root is reachable.
3. If testing locally without real data, you may use the synthetic helpers already covered by the test suite; expected outcomes below still apply.
4. Keep `--no-skip` for rebuild checks so stale artifacts are not silently reused.

## Test Case 1 — Rebuild one trend hotspot family from the contract runner

**Goal:** prove the trend line now produces contract-backed hotspot artifacts with dedicated stage logging.

1. Run:
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
     --no-skip \
     --log-level INFO
   ```
2. Confirm the log stream shows both stages:
   - `stage=agreement ... action=write` or `action=reload`
   - `stage=trend-hotspots ... action=write` or `action=reload`
   - `stage=trend-hotspots ... action=ready`
3. Open the emitted hotspot CSV and confirm:
   - rows are only disputed cells
   - `participant_set_key` is the sorted `+`-joined id set
   - `hotspot_rank` is stable and starts at 1
   - `disagreement_score` is present
4. Open the paired manifest JSON and confirm it references both the agreement surface path and agreement summary path.

**Expected outcome:** one valid manifest + CSV pair exists under `results/phase4/trend_hotspot_manifests/<region>/`, and the logs clearly expose the dedicated trend-hotspot stage.

## Test Case 2 — Semantic reload of the trend hotspot family

**Goal:** prove downstream code can reopen the trend hotspot family by semantics rather than filename guessing.

1. In Python, run:
   ```python
   from WA.visualization.phase4 import load_phase4_contract_trend_hotspot_table

   bundle = load_phase4_contract_trend_hotspot_table(
       region_id="amazon",
       participant_ids=["gwd30", "giems_mc", "topmodel", "swamps", "wad2m"],
       output_root="results/phase4",
   )
   print(bundle.manifest.participant_set_key)
   print(bundle.table[["hotspot_rank", "disagreement_score"]].head())
   ```
2. Confirm the reload succeeds without manually constructing a filename.
3. Confirm `bundle.manifest.participant_set_key` is sorted and deterministic.
4. Confirm the table contains ranked hotspots and the expected contract metadata.

**Expected outcome:** the semantic reload succeeds and returns the same trend hotspot family that the CLI wrote.

## Test Case 3 — Rebuild one unified hotspot ledger

**Goal:** prove the three hotspot families now land on one shared analysis object surface.

1. Run:
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
     --no-skip \
     --log-level INFO
   ```
2. Confirm the log stream shows:
   - `stage=ledger ... action=build` or `action=reload`
   - `stage=ledger ... action=family-ready` for percentage and classification
   - `stage=ledger ... action=families-validated`
   - `stage=ledger ... action=family-normalized`
   - `stage=ledger ... action=ready`
3. Open the emitted ledger CSV and confirm:
   - `metric_family` includes exactly `percentage`, `classification`, and `trend`
   - `analysis_object_id` is unique per row
   - `primary_score_name` and `primary_score_value` are populated
   - provenance columns point back to source manifest/table/surface/summary artifacts

**Expected outcome:** one ledger CSV exists under `results/phase4/unified_hotspot_ledgers/<region>/` and it contains stable long-form analysis objects spanning all three hotspot families.

## Test Case 4 — Semantic reload of the unified ledger

**Goal:** prove later slices can reopen the unified ledger semantically.

1. In Python, run:
   ```python
   from WA.visualization.phase4 import load_phase4_unified_hotspot_ledger

   bundle = load_phase4_unified_hotspot_ledger(
       region_id="amazon",
       ledger_key="canonical",
       output_root="results/phase4",
   )
   print(bundle.table[["analysis_object_id", "metric_family", "primary_score_name"]].head())
   ```
2. Confirm the reload succeeds without reconstructing the filename manually.
3. Confirm the returned table includes `line_specific_json` / parsed line-specific payloads and provenance paths.

**Expected outcome:** semantic reload succeeds and exposes the same unified ledger rows written by the CLI.

## Edge Case 1 — Missing family must fail closed

**Goal:** prove the ledger runner writes nothing when any required family is absent.

1. Temporarily move or rename the classification hotspot manifest or CSV for `amazon`.
2. Re-run the ledger CLI from Test Case 3 with `--no-skip`.
3. Confirm the command exits non-zero.
4. Confirm the error mentions the missing classification hotspot family.
5. Confirm no new/updated unified ledger file is accepted as valid output for that run.

**Expected outcome:** the ledger runner fails closed and does not emit a partial ledger.

## Edge Case 2 — Semantic reload error wrapping

**Goal:** prove downstream reload failures remain explicit and actionable.

1. Point `load_phase4_contract_trend_hotspot_table(...)` or `load_phase4_unified_hotspot_ledger(...)` at a region/output root where the required artifacts are missing or intentionally malformed.
2. Confirm the raised exception includes the wrapper prefix `Phase4 semantic reload failed` plus the region/key context.

**Expected outcome:** downstream callers get one semantic error surface instead of a silent fallback or ambiguous filename miss.

