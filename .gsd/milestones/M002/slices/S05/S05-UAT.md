# S05: Ten-region scale-out with reproducible HPC-safe execution — UAT

**Milestone:** M002
**Written:** 2026-04-08T20:20:17.067Z

# S05 UAT — Ten-region scale-out with reproducible HPC-safe execution

## Preconditions

1. The repo is synced to the target machine with the S05 code.
2. Python environment is installed (`uv add` completed or equivalent venv ready).
3. `results/phase4` is writable.
4. For full producer tests on HPC:
   - standardized inputs exist under `/lustre/home/2200013429/Wetland_Assemble/data/standardized`
   - GWD30 Stage-1 pixel-statistics manifests/tiles exist where the percentage path expects them
   - Phase 3.6 / Phase 3.7 outputs exist for the classification adapter
5. Use explicit `--no-skip` when you want to prove regeneration rather than cache reuse.

## Test Case 1 — Shared selector surfaces are explicit and fail closed

### Steps

1. Run:
   ```bash
   python scripts/run_phase4_regional.py --help
   python scripts/run_phase4_trend_contract.py --help
   python scripts/run_phase4_hotspot_ledger.py --help
   ```
2. Confirm `--subset` is documented and includes `canonical` / `ten`.
3. Run an ambiguity check, for example:
   ```bash
   python scripts/run_phase4_hotspot_ledger.py --region amazon --subset ten --output-root results/phase4
   ```

### Expected outcomes

- Help text exposes the shared subset selector.
- The mixed `--region` + `--subset` invocation exits non-zero.
- The error names the ambiguity instead of silently broadening the run.

## Test Case 2 — Percentage contract runner can build a real one-region family

### Steps

1. Run:
   ```bash
   python scripts/run_phase4_percentage_contract.py \
     --region amazon \
     --output-root results/phase4 \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --surface-year 2016 \
     --start-year 2016 \
     --end-year 2016 \
     --no-skip
   ```
2. Inspect the logs for `stage=percentage-summary`, `stage=percentage-surface`, and `stage=percentage-hotspots`.
3. Check that these artifacts exist:
   - `results/phase4/surfaces/amazon/canonical__amazon__surface.nc`
   - `results/phase4/regional_summaries/amazon/canonical__amazon__regional_summary.csv`
   - `results/phase4/hotspot_manifests/amazon/canonical__amazon__hotspot_manifest.json`
   - `results/phase4/hotspot_manifests/amazon/canonical__amazon__hotspot_manifest.csv`

### Expected outcomes

- The runner resolves `amazon` without manual region lists.
- The surface, summary, and hotspot pair are written.
- The hotspot pair is complete; partial JSON/CSV output is not accepted as reusable state.

## Test Case 3 — Classification contract runner rewrites Phase 3.6/3.7 outputs into Phase 4 artifacts

### Steps

1. Run:
   ```bash
   python scripts/run_phase4_classification_contract.py \
     --region amazon \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --year 2016 \
     --phase36-output-dir results/phase3.6 \
     --phase36-cache-dir results/cache/phase3_6 \
     --phase37-output-dir results/phase3.7_hotspots \
     --phase37-cache-dir results/cache/phase3_7 \
     --no-skip
   ```
2. Check that these artifacts exist:
   - `results/phase4/classification_surfaces/amazon/canonical__amazon__classification_surface.nc`
   - `results/phase4/classification_regional_summaries/amazon/canonical__amazon__classification_regional_summary.csv`
   - `results/phase4/classification_hotspot_manifests/amazon/canonical__amazon__classification_hotspot_manifest.json`
   - `results/phase4/classification_hotspot_manifests/amazon/canonical__amazon__classification_hotspot_manifest.csv`
3. Confirm the logs show Phase 3.6 / Phase 3.7 staging rather than a new duplicate science path.

### Expected outcomes

- The adapter writes region-scoped contract outputs.
- The hotspot family provenance remains tied to `g2017+glwd_v2+gwd30`.
- Malformed or mixed-region Phase 3.7 source rows fail closed instead of being filtered silently.

## Test Case 4 — Trend contract runner writes checkpoints and supports reuse

### Steps

1. Run a fresh build:
   ```bash
   python scripts/run_phase4_trend_contract.py \
     --region amazon \
     --dataset-id gwd30 \
     --dataset-id giems_mc \
     --dataset-id topmodel \
     --dataset-id swamps \
     --dataset-id wad2m \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --aggregation annual \
     --start-year 1990 \
     --end-year 2020 \
     --top-hotspots 10 \
     --no-skip
   ```
2. Confirm that a checkpoint appears under `results/phase4/trend_checkpoints/amazon/`.
3. Confirm that dataset-scoped trend surfaces/summaries plus the agreement/hotspot family are written.
4. Re-run the same command **without** `--no-skip`.
5. Inspect the logs for `stage=trend-load action=reload` or `stage=trend-write action=ready|reload`.

### Expected outcomes

- The first run writes explicit checkpoint files before agreement.
- The second run reuses valid checkpoint/contract artifacts instead of recomputing the entire path.
- If checkpoint metadata mismatches the requested window or dataset, the runner fails loudly instead of silently reusing stale state.

## Test Case 5 — Trend submit wrapper produces one-region-per-job HPC fanout

### Steps

1. Run:
   ```bash
   bash scripts/submit_phase4_trend_contract.sh \
     --repo "$HOME/repos/WA" \
     --python-bin "$HOME/repos/WA/.venv/bin/python" \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --subset ten \
     --dataset-id gwd30 \
     --dataset-id giems_mc \
     --dataset-id topmodel \
     --dataset-id swamps \
     --dataset-id wad2m \
     --aggregation annual \
     --start-year 1990 \
     --end-year 2020 \
     --min-observations 5 \
     --min-overlap-years 5 \
     --top-hotspots 10 \
     --cpus 2 \
     --time 480 \
     --partition C064M0256G \
     --no-progress
   ```
2. Open the generated summary TSV.
3. Open one generated job script.

### Expected outcomes

- The wrapper refuses to run without explicit `--repo`.
- The summary TSV lists one region per job.
- The generated commands contain explicit `--region ...`, repeated `--dataset-id ...`, and `--no-skip`.

## Test Case 6 — Readiness scan reports complete or incomplete family status with paths

### Steps

1. After producer outputs exist, run:
   ```bash
   python scripts/run_phase4_scaleout_readiness.py \
     --subset ten \
     --output-root results/phase4 \
     --percentage-key canonical \
     --classification-key canonical \
     --trend-dataset-id gwd30 \
     --trend-dataset-id giems_mc \
     --trend-dataset-id topmodel \
     --trend-dataset-id swamps \
     --trend-dataset-id wad2m
   ```
2. Open the emitted CSV and JSON reports under `results/phase4/scaleout_readiness/`.

### Expected outcomes

- Every region has one row per metric family.
- Rows are classified as `ready`, `missing`, or `partial`.
- Each row includes a human-debuggable reason plus manifest/table/surface/summary paths.

## Test Case 7 — Ledger succeeds only after readiness is satisfied

### Steps

1. On a region marked ready, run:
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
2. Check for `results/phase4/unified_hotspot_ledgers/amazon/canonical__amazon__unified_hotspot_ledger.csv`.

### Expected outcomes

- The ledger build succeeds only when all three hotspot families are complete and semantically valid.
- The ledger contains unified rows keyed by stable analysis-object identifiers rather than family-local filenames alone.

## Edge Case — Incomplete family should fail closed and auto-write diagnostics

### Steps

1. Point the ledger command at an empty or intentionally incomplete `results/phase4` tree, or temporarily remove one hotspot manifest/CSV pair for the target region.
2. Run the same ledger command as Test Case 7.
3. Inspect the CLI logs and `results/phase4/scaleout_readiness/`.

### Expected outcomes

- The command exits non-zero.
- The logs print one family-context line per metric family with `status`, artifact paths, and `reason`.
- A single-region readiness CSV/JSON report is written automatically.
- The ledger CSV is **not** written as a partial artifact.
