# S02: Trend-correctness backbone on the shared contract — UAT

**Milestone:** M002
**Written:** 2026-04-08T13:03:42.026Z

# S02 UAT — Trend-correctness backbone on the shared contract

## Preconditions
- Python environment is installed for this repo and commands are run from the repository root.
- Local verification can write temporary files under the repo worktree.
- For HPC/runtime cases, standardized Phase 4 inputs are available under `/lustre/home/2200013429/Wetland_Assemble/data/standardized` and the operator can write to `results/phase4`.

## Test Case 1 — CLI exposes the contract surface and recovery ladder
1. Run:
   ```bash
   python scripts/run_phase4_trend_contract.py --help
   ```
2. Confirm the help output lists:
   - `--subset` and repeated `--region`
   - `--dataset-id`
   - `--skip/--no-skip`
   - supported dataset ids `gwd30, giems_mc, swamps, wad2m`
3. Confirm the epilog shows both of these narrow-first commands verbatim:
   - single-region smoke test with `--region amazon --dataset-id wad2m --no-skip`
   - canonical subset run with `--subset canonical --no-skip`

**Expected outcome:** help exits 0 and documents the contract scope plus the correct HPC re-entry ladder.

## Test Case 2 — Contract writer families remain deterministic
1. Run:
   ```bash
   python -m pytest tests/test_comparison/test_evidence_contract.py tests/test_comparison/test_trend_contract.py -q
   ```
2. Confirm the suite passes.

**Expected outcome:** the tests lock all four trend artifact families, deterministic relpaths, metadata JSON, participant-set key stability, malformed metadata rejection, missing output-root failures, and region-scoped cleanup of the duplicated legacy `global` row.

## Test Case 3 — Trend reload helpers work and fail explicitly
1. Run:
   ```bash
   python -m pytest tests/test_comparison/test_trend_contract.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_visualization/test_phase4.py -q
   ```
2. Confirm the suite passes.

**Expected outcome:**
- trend summary reload succeeds when a contract summary exists,
- agreement-summary reload succeeds even if participant ids are provided in different order,
- missing trend summary paths raise explicit `kind=trend_summary` failures,
- mixed participant metadata raises an explicit validation error,
- invalid CLI combinations such as `--subset canonical --region amazon` fail loudly instead of guessing.

## Test Case 4 — Related-test selection recognizes the new runner
1. Run:
   ```bash
   python scripts/run_related_tests.py src/WA/comparison/trend_contract.py scripts/run_phase4_trend_contract.py src/WA/visualization/phase4.py src/WA/test_selection.py
   ```
2. Confirm the output reports the `phase4` category.
3. Confirm the recommended pytest targets include the trend, agreement, Phase 4 visualization, and submit-script families.

**Expected outcome:** downstream operators can ask for the related-test set from the changed files and get the correct Phase 4 family instead of a stale or incomplete subset.

## Test Case 5 — Full local regression remains green
1. Run:
   ```bash
   python -m pytest tests/
   ```
2. Confirm the full suite passes.

**Expected outcome:** the new trend-contract writer, runner, reload helpers, selector update, and changelog compatibility change do not destabilize unrelated loader, comparison, validation, or visualization families.

## Test Case 6 — HPC smoke test writes one region/dataset contract package
1. On HPC, run:
   ```bash
   python scripts/run_phase4_trend_contract.py \
     --region amazon \
     --dataset-id wad2m \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --aggregation annual \
     --start-year 2016 \
     --end-year 2016 \
     --no-skip
   ```
2. Watch stdout/stderr for the stage logs `trend-load`, `trend-write`, and `agreement`.
3. Confirm these artifact families now exist for `amazon`:
   - `results/phase4/trend_surfaces/amazon/...`
   - `results/phase4/trend_regional_summaries/amazon/...`
   - `results/phase4/trend_agreement_surfaces/amazon/...`
   - `results/phase4/trend_agreement_summaries/amazon/...`
4. Open the generated summary CSVs and confirm they are region-scoped (`region_id=amazon`) with no duplicated legacy `global` row.

**Expected outcome:** one real contract package is produced with visible stage logging and stable artifact placement.

## Test Case 7 — HPC canonical subset run scales the same contract
1. After the single-region smoke test passes, run:
   ```bash
   python scripts/run_phase4_trend_contract.py \
     --subset canonical \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --aggregation annual \
     --start-year 2016 \
     --end-year 2016 \
     --no-skip
   ```
2. Confirm each canonical region receives trend surface, trend summary, agreement surface, and agreement summary artifacts under the same four contract families.
3. Confirm agreement summaries carry a deterministic `participant_set_key` built from the sorted dataset ids joined with `+`.

**Expected outcome:** the canonical subset closes on the same shared trend contract without falling back to probe-only outputs or filename guessing.

## Edge Case — Resume without recomputing persisted trend surfaces
1. After Test Case 6 or 7 has written artifacts, rerun the same command **without** `--no-skip` (default `--skip`).
2. Confirm the runner logs either `mode=reload` for trend surfaces or `mode=skip` for already-complete outputs.
3. Confirm the rerun does not require deleting prior trend artifacts to continue agreement work.

**Expected outcome:** partial or completed runs resume at the dataset×region boundary through semantic reloads rather than silent recomputation.
