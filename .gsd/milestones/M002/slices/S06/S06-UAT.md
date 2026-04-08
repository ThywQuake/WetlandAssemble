# S06: Paper-ready evidence pack and milestone integration proof — UAT

**Milestone:** M002
**Written:** 2026-04-08T22:15:52.837Z

# S06 UAT — Paper-ready evidence pack and milestone integration proof

## Preconditions

1. The repo is synced to the target machine with the S06 code.
2. Python environment is installed and can run the Phase 4 CLIs plus pytest.
3. `results/phase4` and `results/figures/phase4_pack` are writable.
4. For the real ten-region proof on HPC:
   - standardized inputs exist under `/lustre/home/2200013429/Wetland_Assemble/data/standardized`
   - Stage-1-backed percentage inputs are available where the percentage contract expects them
   - Phase 3.6 / Phase 3.7 outputs exist for the classification adapter
   - the trend submit wrapper can submit one-region-per-job fanout
5. Use `--no-skip` on the upstream HPC science reruns when you want to prove regeneration rather than cache reuse.

## Test Case 1 — Pack-safe public reload helpers are the supported reopen surface

### Steps

1. Run:
   ```bash
   python scripts/run_phase4_trend_contract.py --help
   ```
2. Run:
   ```bash
   python -m pytest tests/test_comparison/test_trend_contract.py tests/test_visualization/test_phase4.py -q
   ```

### Expected outcomes

- The trend runner help exposes explicit subset/region and participant controls.
- The pytest run passes (`22 passed` in the current local closeout run).
- Malformed trend-agreement pairs fail with `region_id` and participant-set context instead of bubbling a naked path or metadata error.
- Downstream pack code can rely on the public comparison-layer helpers and phase4 wrappers rather than runner-private helpers.

## Test Case 2 — Derived pack builder writes only derived outputs and keeps deterministic relpaths

### Steps

1. Run:
   ```bash
   python scripts/run_phase4_evidence_pack.py --help
   ```
2. Run:
   ```bash
   python -m pytest tests/test_visualization/test_phase4_pack.py tests/test_visualization/test_phase4.py -q
   ```

### Expected outcomes

- Help text shows `--phase4-output-root`, `--pack-output-root`, `--subset`, and `--strict`.
- The pytest run passes (`28 passed` in the current local closeout run).
- Fixture-backed pack tests prove that figures, tables, summary, and manifest are written under the pack root, not back into `results/phase4`.
- Invalid pack roots inside the science contract tree, missing climatology coverage, or malformed ledger JSON fail closed and do not leave behind a fresh manifest.

## Test Case 3 — Related-test routing stays discoverable for the new pack surface

### Steps

1. Run:
   ```bash
   python scripts/run_related_tests.py src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py src/WA/test_selection.py
   ```
2. Run:
   ```bash
   python scripts/run_related_tests.py src/WA/visualization/phase4_pack.py scripts/run_phase4_evidence_pack.py
   ```

### Expected outcomes

- Both commands report the `phase4` category.
- The suggested pytest subset includes `tests/test_visualization/test_phase4_pack.py`.
- Operators can discover the verification surface for pack changes without guessing which tests belong to the new CLI/module.

## Test Case 4 — Real ten-region strict complete-pack proof on HPC

### Steps

1. Run the percentage producer:
   ```bash
   python scripts/run_phase4_percentage_contract.py \
     --subset ten \
     --output-root results/phase4 \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --surface-year 2016 \
     --start-year 1990 \
     --end-year 2020 \
     --no-skip
   ```
2. Run the classification producer:
   ```bash
   python scripts/run_phase4_classification_contract.py \
     --subset ten \
     --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
     --output-root results/phase4 \
     --year 2016 \
     --phase36-output-dir results/phase3.6 \
     --phase36-cache-dir results/cache/phase3_6 \
     --phase37-output-dir results/phase3.7_hotspots \
     --phase37-cache-dir results/cache/phase3_7 \
     --no-skip
   ```
3. Fan out the trend rerun:
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
4. Run readiness:
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
5. Run the unified ledger:
   ```bash
   python scripts/run_phase4_hotspot_ledger.py \
     --subset ten \
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
6. Run the strict paper-pack proof:
   ```bash
   python scripts/run_phase4_evidence_pack.py \
     --subset ten \
     --phase4-output-root results/phase4 \
     --pack-output-root results/figures/phase4_pack \
     --ledger-key canonical \
     --percentage-key canonical \
     --classification-key canonical \
     --trend-dataset-id gwd30 \
     --trend-dataset-id giems_mc \
     --trend-dataset-id topmodel \
     --trend-dataset-id swamps \
     --trend-dataset-id wad2m \
     --strict
   ```
7. Inspect:
   - `results/figures/phase4_pack/manifest.json`
   - `results/figures/phase4_pack/complete_pack_proof.json`
   - `results/figures/phase4_pack/complete_pack_proof.md`

### Expected outcomes

- The strict pack command exits `0` only after readiness rows are all `ready` and every requested unified ledger reopens cleanly.
- The manifest exists alongside the proof JSON/Markdown files.
- `complete_pack_proof.json` reports `proof_verdict: complete`, `complete_pack_claim_allowed: true`, the ordered ten resolved regions, and non-zero figure/table output counts.
- The pack root contains derived figures/tables/summary/proof artifacts, while `results/phase4` remains the science-contract input tree.

## Edge Case 1 — Non-strict incomplete proof stays inspectable but cannot claim completion

### Steps

1. Point `--phase4-output-root` at an incomplete Phase 4 tree (for example, before readiness/ledger are complete or with one hotspot family missing).
2. Run the pack CLI **without** `--strict`:
   ```bash
   python scripts/run_phase4_evidence_pack.py \
     --subset ten \
     --phase4-output-root results/phase4 \
     --pack-output-root results/figures/phase4_pack \
     --ledger-key canonical \
     --percentage-key canonical \
     --classification-key canonical \
     --trend-dataset-id gwd30 \
     --trend-dataset-id giems_mc \
     --trend-dataset-id topmodel \
     --trend-dataset-id swamps \
     --trend-dataset-id wad2m
   ```

### Expected outcomes

- The command returns `0` so operators can inspect the proof outputs.
- `complete_pack_proof.json` and `complete_pack_proof.md` are written.
- No fresh `manifest.json` is written.
- The proof verdict is `incomplete` and the blocking reasons name the missing/partial readiness or unified-ledger problem.

## Edge Case 2 — Strict mode fails closed on the same incomplete inputs

### Steps

1. Re-run the same incomplete-input command with `--strict`.

### Expected outcomes

- The command exits non-zero (`2` in the fixture-backed regression coverage).
- `complete_pack_proof.json` / `.md` still exist for debugging.
- `manifest.json` is absent.
- Logs include `stage=pack-proof action=incomplete` and the proof artifacts identify the blocking reason instead of silently downgrading to a best-effort complete-pack claim.

